# home/agents/farm_agents.py
import google.generativeai as genai
from langgraph.graph import StateGraph, END
from typing import Dict, Any, TypedDict, List, Optional, Callable
import json
from django.conf import settings
from home.agents.tools import *
from home.models import *
import matplotlib.pyplot as plt
import networkx as nx
from home.agents import (
    MarketAgent,
    SatelliteAgent,
    WeatherAgent,
    PestAgent,
    SoilAgent,
    NotificationAgent,
    UserContextProvider,
    SearchAgent
)
import time
import threading

# Configure Gemini API
genai.configure(api_key=settings.GEMINI_API_KEY)
LLM_MODEL = 'gemini-2.5-flash'  

class AgentState(TypedDict):
    """State shared between agents"""
    user_query: str
    user_context: Dict[str, Any]
    intent_classification: str
    confidence_score: float
    agent_responses: Dict[str, Any]
    final_response: str
    require_human_feedback: bool
    agents_to_run: List[str]  # New field to track which agents need to run
    progress_callback: Optional[Callable[[str, str], None]]  # New field for progress updates

class FarmOrchestratorAgent:
    """Main orchestrator agent that coordinates all sub-agents"""
    
    def __init__(self, progress_callback: Optional[Callable[[str, str], None]] = None):
        self.model = genai.GenerativeModel(LLM_MODEL)
        self.graph = self._build_graph()
        self.progress_callback = progress_callback
        self.keep_alive_timer = None
        self.keep_alive_active = False
    
    def _send_progress(self, message: str, event_type: str = "progress"):
        """Send progress update through callback if available"""
        if self.progress_callback:
            self.progress_callback(message, event_type)
    
    def _start_keep_alive(self):
        """Start keep-alive timer"""
        self.keep_alive_active = True
        self._schedule_keep_alive()
    
    def _stop_keep_alive(self):
        """Stop keep-alive timer"""
        self.keep_alive_active = False
        if self.keep_alive_timer:
            self.keep_alive_timer.cancel()
            self.keep_alive_timer = None
    
    def _schedule_keep_alive(self):
        """Schedule next keep-alive message"""
        if not self.keep_alive_active:
            return
            
        def send_keep_alive():
            if self.keep_alive_active:
                self._send_progress("Processing...", "keep_alive")
                self._schedule_keep_alive()
        
        self.keep_alive_timer = threading.Timer(5.0, send_keep_alive)  # Every 5 seconds
        self.keep_alive_timer.start()
    
    def _build_graph(self):
        """Build the LangGraph workflow"""
        graph = StateGraph(AgentState)
        
        # Add nodes
        graph.add_node("classify_intent", self.classify_intent)
        graph.add_node("run_multiple_agents", self.run_multiple_agents)
        graph.add_node("market_agent", self.run_market_agent)
        graph.add_node("satellite_agent", self.run_satellite_agent)
        graph.add_node("weather_agent", self.run_weather_agent)
        graph.add_node("pest_agent", self.run_pest_agent)
        graph.add_node("soil_agent", self.run_soil_agent)
        graph.add_node("decision_llm", self.make_decision)
        graph.add_node("verifier_agent", self.verify_response)
        graph.add_node("notification_agent", self.send_notifications)
        graph.add_node("check_confidence", self.check_confidence)
        graph.add_node("search_agent", self.run_search_agent)

        
        # Define workflow
        graph.set_entry_point("classify_intent")
        
        # Add conditional edges based on intent
        graph.add_conditional_edges(
            "classify_intent",
            self.route_to_agents,
            {
                "market": "market_agent",
                "satellite": "satellite_agent", 
                "weather": "weather_agent",
                "pest": "pest_agent",
                "soil": "soil_agent",
                "search": "search_agent",
                "multiple": "run_multiple_agents"
            }
        )
        
        # Single agents flow to decision LLM
        for agent in ["market_agent", "satellite_agent", "weather_agent", "pest_agent", "soil_agent", "search_agent"]:
            graph.add_edge(agent, "decision_llm")

        
        # Multiple agents node also flows to decision LLM
        graph.add_edge("run_multiple_agents", "decision_llm")
        
        graph.add_edge("decision_llm", "verifier_agent")
        graph.add_edge("verifier_agent", "check_confidence")
        
        graph.add_conditional_edges(
            "check_confidence",
            self.confidence_check,
            {
                "sufficient": "notification_agent",
                "insufficient": END
            }
        )
        
        graph.add_edge("notification_agent", END)
        
        return graph.compile()
    
    def classify_intent(self, state: AgentState) -> AgentState:
        """Classify user intent and determine which agents to trigger"""
        query = state["user_query"]
        print("\n[INTENT CLASSIFICATION] Processing query:", query)
        self._send_progress("🧠 Analyzing your query and determining which agents to activate...", "agent_start")
        
        prompt = f"""
        Classify the following farm-related query into one or more categories:
        - market: Questions about crop prices, market trends, selling opportunities
        - satellite: Questions about crop health, field monitoring, vegetation analysis
        - weather: Questions about weather conditions, forecasts, climate impact
        - pest: Questions about pest detection, treatment, plant diseases
        - soil: Questions about soil health, nutrients, pH levels, fertilization
        - search: Questions requiring general web search, research, latest news, best practices, tutorials, or information not covered by other agents
        
        Here is the query: {query}
        
        If the query requires multiple agents, list all relevant categories.
        
        Examples:
        - "What's the weather and should I irrigate?" → ["weather", "soil"]
        - "Crop prices and plant health status" → ["market", "satellite"]
        - "Rain forecast and pest protection" → ["weather", "pest"]
        - "Best organic farming practices" → ["search"]
        - "Latest farming technology trends" → ["search"]
        - "How to start vertical farming" → ["search"]
        - "Current agricultural news" → ["search"]
        - "Weather forecast and latest farming news" → ["weather", "search"]
        
        Respond with JSON format:
        {{
            "primary_intent": "category_name or multiple",
            "agents_needed": ["list", "of", "agent", "categories"],
            "confidence": 0.0-1.0
        }}
        
        Respond ONLY with raw JSON (no code fences, no markdown, no extra text).
        """
        
        print("[INTENT CLASSIFICATION] Sending prompt to model...")
        try:
            response = self.model.generate_content(prompt)
            result = json.loads(response.text)
            print("\n[INTENT RESULT] Classification:", result)
            
            agents_needed = result.get("agents_needed", [])
            
            # Determine if single or multiple
            if len(agents_needed) == 1:
                state["intent_classification"] = agents_needed[0]
            else:
                state["intent_classification"] = "multiple"
            
            state["agents_to_run"] = agents_needed
            state["confidence_score"] = float(result.get("confidence", 0.5))
            state["agent_responses"] = {}
            
            # Send progress update with identified agents
            agent_names = {
                "market": "Market Analysis",
                "satellite": "Satellite Imagery",
                "weather": "Weather Forecast",
                "pest": "Pest Management",
                "soil": "Soil Analysis",
                "search": "Web Search"
            }
            
            agents_display = ", ".join([agent_names.get(agent, agent.title()) for agent in agents_needed])
            self._send_progress(f"✅ Query analyzed! Activating: {agents_display}", "intent_classified")
            
            print(f"[INTENT CLASSIFICATION] Final intent: {state['intent_classification']}")
            print(f"[INTENT CLASSIFICATION] Agents to run: {state['agents_to_run']}")
            
            return state
            
        except Exception as e:
            # Fallback classification
            print("[INTENT CLASSIFICATION] Error:", str(e))
            self._send_progress("⚠️ Using fallback classification due to analysis error", "warning")
            state["intent_classification"] = "multiple"
            state["agents_to_run"] = ["weather", "soil"]  # Default fallback
            state["confidence_score"] = 0.5
            state["agent_responses"] = {}
            return state
    
    def route_to_agents(self, state: AgentState) -> str:
        """Route to appropriate agents based on intent"""
        intent = state["intent_classification"]
        if intent in ["market", "satellite", "weather", "pest", "soil", "search"]:
            return intent
        return "multiple"
    
    def run_multiple_agents(self, state: AgentState) -> AgentState:
        """Execute multiple agents based on the agents_to_run list"""
        print("\n[MULTIPLE AGENTS] Starting execution...")
        print(f"[MULTIPLE AGENTS] Agents to run: {state['agents_to_run']}")
        
        agents_to_run = state.get("agents_to_run", [])
        agent_responses = {}
        
        self._send_progress(f"🚀 Running {len(agents_to_run)} specialized agents...", "multiple_agents_start")
        
        # Map agent names to their corresponding methods
        agent_map = {
            "market": self.run_market_agent,
            "satellite": self.run_satellite_agent,
            "weather": self.run_weather_agent,
            "pest": self.run_pest_agent,
            "soil": self.run_soil_agent,
            "search": self.run_search_agent
        }
        
        # Execute each required agent
        for i, agent_name in enumerate(agents_to_run, 1):
            if agent_name in agent_map:
                print(f"[MULTIPLE AGENTS] Running {agent_name} agent...")
                agent_display_name = {
                    "market": "Market Analysis",
                    "satellite": "Satellite Imagery",
                    "weather": "Weather Forecast", 
                    "pest": "Pest Management",
                    "soil": "Soil Analysis",
                    "search": "Web Search"
                }.get(agent_name, agent_name.title())
                
                self._send_progress(f"🔄 [{i}/{len(agents_to_run)}] Running {agent_display_name} Agent...", "agent_running")
                
                try:
                    # Create a temporary state for this agent
                    temp_state = state.copy()
                    temp_state = agent_map[agent_name](temp_state)
                    
                    # Extract the agent's response
                    if agent_name in temp_state.get("agent_responses", {}):
                        agent_responses[agent_name] = temp_state["agent_responses"][agent_name]
                        print(f"[MULTIPLE AGENTS] ✓ {agent_name} agent completed successfully")
                        self._send_progress(f"✅ {agent_display_name} Agent completed successfully", "agent_complete")
                        print(f"[MULTIPLE AGENTS] {agent_name.upper()} Response Summary:")
                        response = temp_state["agent_responses"][agent_name]
                        if isinstance(response, dict):
                            if "recommendations" in response:
                                print(f"  - Recommendations: {len(response['recommendations'])} items")
                            if "data" in response:
                                print(f"  - Data keys: {list(response['data'].keys()) if isinstance(response['data'], dict) else 'N/A'}")
                            if "error" in response:
                                print(f"  - Error: {response['error']}")
                    else:
                        print(f"[MULTIPLE AGENTS] ⚠ {agent_name} agent did not return response")
                        self._send_progress(f"⚠️ {agent_display_name} Agent completed with warnings", "agent_warning")
                        
                except Exception as e:
                    print(f"[MULTIPLE AGENTS] ✗ Error running {agent_name} agent: {e}")
                    self._send_progress(f"❌ {agent_display_name} Agent failed: {str(e)[:50]}...", "agent_error")
                    agent_responses[agent_name] = {
                        "error": f"Agent execution failed: {e}",
                        "data": {},
                        "recommendations": [f"Unable to get {agent_name} recommendations due to error"]
                    }
            else:
                print(f"[MULTIPLE AGENTS] ⚠ Unknown agent: {agent_name}")
                self._send_progress(f"⚠️ Unknown agent requested: {agent_name}", "warning")
        
        # Update state with all collected responses
        state["agent_responses"] = agent_responses
        
        print(f"[MULTIPLE AGENTS] Completed. Total agents run: {len(agent_responses)}")
        print(f"[MULTIPLE AGENTS] Agent responses keys: {list(agent_responses.keys())}")
        
        success_count = len([r for r in agent_responses.values() if not (isinstance(r, dict) and "error" in r)])
        self._send_progress(f"🎯 All agents completed! {success_count}/{len(agent_responses)} successful", "multiple_agents_complete")
        
        return state
    
    def run_market_agent(self, state: AgentState) -> AgentState:
        """Execute market analysis agent"""
        print("\n[MARKET AGENT] Starting execution...")
        self._send_progress("📊 Fetching latest market data and price trends...", "market_agent_start")
        
        try:
            agent = MarketAgent()
            result = agent.process(state["user_query"], state["user_context"])
            print("[MARKET AGENT] ✓ Agent completed successfully")
            self._send_progress("✅ Market analysis complete - Found current prices and trends", "market_agent_complete")
            print("[MARKET AGENT] Full Response:")
            print("=" * 60)
            print(json.dumps(result, indent=2))
            print("=" * 60)
            state["agent_responses"]["market"] = result
        except Exception as e:
            print(f"[MARKET AGENT] ✗ Error: {e}")
            self._send_progress(f"❌ Market agent failed: {str(e)[:50]}...", "market_agent_error")
            error_response = {
                "error": f"Market agent failed: {e}",
                "data": {},
                "recommendations": ["Unable to fetch market data due to error"]
            }
            print("[MARKET AGENT] Error Response:")
            print("=" * 60)
            print(json.dumps(error_response, indent=2))
            print("=" * 60)
            state["agent_responses"]["market"] = error_response
        return state
    
    def run_satellite_agent(self, state: AgentState) -> AgentState:
        """Execute satellite analysis agent"""
        print("\n[SATELLITE AGENT] Starting execution...")
        self._send_progress("🛰️ Analyzing satellite imagery and crop health data...", "satellite_agent_start")
        
        try:
            agent = SatelliteAgent()
            result = agent.process(state["user_query"], state["user_context"])
            print("[SATELLITE AGENT] ✓ Agent completed successfully")
            self._send_progress("✅ Satellite analysis complete - Processed field imagery", "satellite_agent_complete")
            print("[SATELLITE AGENT] Full Response:")
            print("=" * 60)
            print(json.dumps(result, indent=2))
            print("=" * 60)
            state["agent_responses"]["satellite"] = result
        except Exception as e:
            print(f"[SATELLITE AGENT] ✗ Error: {e}")
            self._send_progress(f"❌ Satellite agent failed: {str(e)[:50]}...", "satellite_agent_error")
            error_response = {
                "error": f"Satellite agent failed: {e}",
                "data": {},
                "recommendations": ["Unable to fetch satellite data due to error"]
            }
            print("[SATELLITE AGENT] Error Response:")
            print("=" * 60)
            print(json.dumps(error_response, indent=2))
            print("=" * 60)
            state["agent_responses"]["satellite"] = error_response
        return state
    
    def run_weather_agent(self, state: AgentState) -> AgentState:
        """Execute weather analysis agent"""
        print("\n[WEATHER AGENT] Starting execution...")
        self._send_progress("🌤️ Gathering weather forecasts and climate conditions...", "weather_agent_start")
        
        try:
            agent = WeatherAgent()
            result = agent.process(state["user_query"], state["user_context"])
            print("[WEATHER AGENT] ✓ Agent completed successfully")
            self._send_progress("✅ Weather analysis complete - Got latest forecasts", "weather_agent_complete")
            print("[WEATHER AGENT] Full Response:")
            print("=" * 60)
            print(json.dumps(result, indent=2))
            print("=" * 60)
            state["agent_responses"]["weather"] = result
        except Exception as e:
            print(f"[WEATHER AGENT] ✗ Error: {e}")
            self._send_progress(f"❌ Weather agent failed: {str(e)[:50]}...", "weather_agent_error")
            error_response = {
                "error": f"Weather agent failed: {e}",
                "data": {},
                "recommendations": ["Unable to fetch weather data due to error"]
            }
            print("[WEATHER AGENT] Error Response:")
            print("=" * 60)
            print(json.dumps(error_response, indent=2))
            print("=" * 60)
            state["agent_responses"]["weather"] = error_response
        return state
    
    def run_pest_agent(self, state: AgentState) -> AgentState:
        """Execute pest analysis agent"""
        print("\n[PEST AGENT] Starting execution...")
        self._send_progress("🐛 Analyzing pest risks and treatment recommendations...", "pest_agent_start")
        
        try:
            agent = PestAgent()
            result = agent.process(state["user_query"], state["user_context"])
            print("[PEST AGENT] ✓ Agent completed successfully")
            self._send_progress("✅ Pest analysis complete - Identified threats and solutions", "pest_agent_complete")
            print("[PEST AGENT] Full Response:")
            print("=" * 60)
            print(json.dumps(result, indent=2))
            print("=" * 60)
            state["agent_responses"]["pest"] = result
        except Exception as e:
            print(f"[PEST AGENT] ✗ Error: {e}")
            self._send_progress(f"❌ Pest agent failed: {str(e)[:50]}...", "pest_agent_error")
            error_response = {
                "error": f"Pest agent failed: {e}",
                "data": {},
                "recommendations": ["Unable to fetch pest data due to error"]
            }
            print("[PEST AGENT] Error Response:")
            print("=" * 60)
            print(json.dumps(error_response, indent=2))
            print("=" * 60)
            state["agent_responses"]["pest"] = error_response
        return state
    
    def run_soil_agent(self, state: AgentState) -> AgentState:
        """Execute soil analysis agent"""
        print("\n[SOIL AGENT] Starting execution...")
        self._send_progress("🌱 Examining soil conditions and nutrient levels...", "soil_agent_start")
        
        try:
            agent = SoilAgent()
            result = agent.process(state["user_query"], state["user_context"])
            print("[SOIL AGENT] ✓ Agent completed successfully")
            self._send_progress("✅ Soil analysis complete - Assessed health and nutrients", "soil_agent_complete")
            print("[SOIL AGENT] Full Response:")
            print("=" * 60)
            print(json.dumps(result, indent=2))
            print("=" * 60)
            state["agent_responses"]["soil"] = result
        except Exception as e:
            print(f"[SOIL AGENT] ✗ Error: {e}")
            self._send_progress(f"❌ Soil agent failed: {str(e)[:50]}...", "soil_agent_error")
            error_response = {
                "error": f"Soil agent failed: {e}",
                "data": {},
                "recommendations": ["Unable to fetch soil data due to error"]
            }
            print("[SOIL AGENT] Error Response:")
            print("=" * 60)
            print(json.dumps(error_response, indent=2))
            print("=" * 60)
            state["agent_responses"]["soil"] = error_response
        return state
    
    def run_search_agent(self, state: AgentState) -> AgentState:
        """Execute search agent"""
        print("\n[SEARCH AGENT] Starting execution...")
        self._send_progress("🔍 Searching the web for latest information and best practices...", "search_agent_start")
        
        try:
            agent = SearchAgent()
            result = agent.process(state["user_query"], state["user_context"])
            print("[SEARCH AGENT] ✓ Agent completed successfully")
            self._send_progress("✅ Web search complete - Found relevant resources and updates", "search_agent_complete")
            print("[SEARCH AGENT] Full Response:")
            print("=" * 60)
            print(json.dumps(result, indent=2))
            print("=" * 60)
            state["agent_responses"]["search"] = result
        except Exception as e:
            print(f"[SEARCH AGENT] ✗ Error: {e}")
            self._send_progress(f"❌ Search agent failed: {str(e)[:50]}...", "search_agent_error")
            error_response = {
                "error": f"Search agent failed: {e}",
                "data": {
                    "original_query": state["user_query"],
                    "optimized_query": "",
                    "search_results": [],
                    "result_count": 0,
                    "search_answer": "",
                    "sources": []
                },
                "recommendations": ["Unable to perform web search due to error"]
            }
            print("[SEARCH AGENT] Error Response:")
            print("=" * 60)
            print(json.dumps(error_response, indent=2))
            print("=" * 60)
            state["agent_responses"]["search"] = error_response
        return state
    
    def make_decision(self, state: AgentState) -> AgentState:
        """Combine all agent responses and generate final answer"""
        print("\n[DECISION LLM] Starting final response generation...")
        self._send_progress("🤖 Combining all agent insights and generating your personalized response...", "decision_start")
        
        query = state["user_query"]
        responses = state["agent_responses"]
        
        print(f"[DECISION LLM] Collected {len(responses)} agent responses")
        print(f"[DECISION LLM] Agent types: {list(responses.keys())}")
        
        # Check if we have any valid responses
        if not responses:
            state["final_response"] = "I apologize, but I couldn't gather the necessary information to answer your question. Please try again or rephrase your query."
            self._send_progress("⚠️ No agent responses received - using fallback", "warning")
            return state
        
        prompt = f"""
        Agent Responses:
            {json.dumps(responses, indent=2)}

        Now, based on the responses from all agents above, write a clear and friendly reply that directly addresses the user's original question.

        Focus on being conversational, helpful, and easy to understand. Offer practical advice, specific recommendations, and next steps where possible.

        If any agent ran into an error or couldn't fetch something, mention that briefly but continue with whatever useful information is available.

        Structure your response like you're explaining it to a real person — keep it informative but natural and approachable.
        """

        try:
            response = self.model.generate_content(prompt)
            state["final_response"] = response.text
            
            print(f"[DECISION LLM] ✓ Generated final response successfully")
            print(f"[DECISION LLM] Response length: {len(response.text)} characters")
            self._send_progress("✅ Final response generated successfully!", "decision_complete")
            print("\n[DECISION LLM] FINAL RESPONSE:")
            print("=" * 80)
            print(response.text)
            print("=" * 80)
            
        except Exception as e:
            error_response = "I encountered an error processing your request. Please try again."
            state["final_response"] = error_response
            print(f"[DECISION LLM] ✗ Error: {e}")
            self._send_progress(f"❌ Decision LLM failed: {str(e)[:50]}...", "decision_error")
            print(f"[DECISION LLM] Using fallback response: {error_response}")
        
        return state
    
    def verify_response(self, state: AgentState) -> AgentState:
        """Verify the quality and accuracy of the response"""
        print("\n[VERIFIER AGENT] Starting response verification...")
        self._send_progress("🔍 Verifying response quality and accuracy...", "verifier_start")
        
        response = state["final_response"]
        query = state["user_query"]
        
        prompt = f"""
        Evaluate this response for accuracy and helpfulness on a scale of 0.0 to 1.0:
        
        Original Query: {query}
        Response: {response}
        
        Consider:
        - Does it answer the user's question?
        - Is the information accurate and practical?
        - Are the recommendations actionable?
        
        Respond with just a number between 0.0 and 1.0
        """
        
        try:
            verification = self.model.generate_content(prompt)
            confidence = float(verification.text.strip())
            state["confidence_score"] = min(max(confidence, 0.0), 1.0)
            print(f"[VERIFIER AGENT] Confidence score: {state['confidence_score']}")
            self._send_progress(f"✅ Response verified - Confidence: {state['confidence_score']:.1%}", "verifier_complete")
        except Exception as e:
            print(f"[VERIFIER AGENT] Error: {e}")
            self._send_progress(f"⚠️ Verification failed, using default confidence", "warning")
            state["confidence_score"] = 0.7  # Default confidence
        
        return state
    
    def check_confidence(self, state: AgentState) -> AgentState:
        """Check if confidence meets threshold"""
        state["require_human_feedback"] = state["confidence_score"] < 0.6
        return state
    
    def confidence_check(self, state: AgentState) -> str:
        """Decision point for confidence threshold"""
        return "insufficient" if state["require_human_feedback"] else "sufficient"
    
    def send_notifications(self, state: AgentState) -> AgentState:
        """Send notifications based on response content"""
        self._send_progress("📢 Processing notifications...", "notification_start")
        try:
            agent = NotificationAgent()
            agent.process_notifications(state["final_response"], state["user_context"])
            self._send_progress("✅ Notifications processed", "notification_complete")
        except Exception as e:
            print(f"[NOTIFICATION AGENT] Error: {e}")
            self._send_progress(f"⚠️ Notification processing failed", "warning")
        return state
    
    def process_query(self, user_query: str, user_context: Dict[str, Any], progress_callback: Optional[Callable[[str, str], None]] = None) -> Dict[str, Any]:
        """Main entry point for processing user queries"""
        self.progress_callback = progress_callback
        self._start_keep_alive()
        
        initial_state = {
            "user_query": user_query,
            "user_context": user_context,
            "intent_classification": "",
            "confidence_score": 0.0,
            "agent_responses": {},
            "final_response": "",
            "require_human_feedback": False,
            "agents_to_run": [],
            "progress_callback": progress_callback
        }
        
        try:
            # Execute the graph
            result = self.graph.invoke(initial_state)
            
            # FIXED: Safe database saving with proper validation
            self._save_query_safely(user_query, user_context, result)
            
            return result
        finally:
            self._stop_keep_alive()
    
    def _save_query_safely(self, user_query: str, user_context: Dict[str, Any], result: Dict[str, Any]):
        """Safely save query to database with proper validation"""
        try:
            user_id = user_context.get("user_id")
            if not user_id:
                print("Warning: No user_id provided, skipping database save")
                return
            
            # Check if user exists
            try:
                from django.contrib.auth.models import User
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                print(f"Warning: User with ID {user_id} does not exist, skipping database save")
                return
            
            # Save with proper foreign key validation
            AgentQuery.objects.create(
                user=user,  # Use the user object instead of user_id
                query_text=user_query,
                intent_classification=result.get("intent_classification", "unknown"),
                agents_triggered=list(result.get("agent_responses", {}).keys()),
                response_data=result.get("agent_responses", {}),
                confidence_score=result.get("confidence_score", 0.0),
                response_time=0.0
            )
            print(f"Successfully saved query for user {user_id}")
            
        except Exception as e:
            print(f"Error saving query to database: {e}")
            # Continue execution without failing
            
# FIXED: Create orchestrator and testing functions
def create_test_orchestrator():
    """Create orchestrator with error handling"""
    try:
        return FarmOrchestratorAgent()
    except Exception as e:
        print(f"Error creating orchestrator: {e}")
        return None

def run_safe_tests():
    """Run tests with proper error handling and validation"""
    print("=== FARM AGENT SYSTEM - MULTIPLE AGENT LOGIC TESTING ===")
    
    orchestrator = create_test_orchestrator()
    if not orchestrator:
        print("Failed to create orchestrator, exiting tests")
        return
    
    # Test context with validation
    test_context = {
        "user_id": None,  # Safe mode - no database operations
        "farm_id": 1,
        "farm_location": "California",
        "farm_name": "Test Farm"
    }
    
    # Test queries specifically designed to trigger multiple agents
    test_queries = [
        # "What are the latest organic farming techniques I should know about?",
        # "There were thunderstorm alerts near my area, what should I do to protect my crops? Also should I irrigate my crops today?",
        
        # "What's the current weather forecast and how's my crop health looking from satellite data?",
        "Should I sell my crops now based on market prices, and do I need to add fertilizer to my soil?",
        # "I'm concerned about pest damage and the weather conditions - what should I do?",
        # "Can you check crop prices, weather forecast, and soil moisture levels for me?"
    ]
    
    print("\n=== TESTING MULTIPLE AGENT QUERIES ===")
    for i, query in enumerate(test_queries, 1):
        print(f"\n--- Query {i} ---")
        print(f"Query: {query}")
        
        try:
            result = orchestrator.process_query(query, test_context)
            
            print(f"✓ Intent Classification: {result.get('intent_classification', 'unknown')}")
            print(f"✓ Agents to Run: {result.get('agents_to_run', [])}")
            print(f"✓ Agents Actually Run: {list(result.get('agent_responses', {}).keys())}")
            print(f"✓ Confidence Score: {result.get('confidence_score', 0.0):.2f}")
            print(f"✓ Response Length: {len(result.get('final_response', ''))} characters")
            
            # Verify multiple agents were triggered
            agent_responses = result.get('agent_responses', {})
            if len(agent_responses) > 1:
                print(f"✓ SUCCESS: Multiple agents triggered ({len(agent_responses)} agents)")
            elif len(agent_responses) == 1:
                print(f"⚠ SINGLE AGENT: Only 1 agent triggered - {list(agent_responses.keys())[0]}")
            else:
                print("✗ ERROR: No agents triggered")
            
            # Check for errors in responses
            error_count = 0
            success_count = 0
            for agent_name, response in agent_responses.items():
                if isinstance(response, dict) and 'error' in response:
                    error_count += 1
                    print(f"  ✗ {agent_name}: ERROR - {response['error']}")
                else:
                    success_count += 1
                    print(f"  ✓ {agent_name}: SUCCESS")
                    
                    # Log summary of successful response
                    if isinstance(response, dict):
                        if "recommendations" in response and isinstance(response["recommendations"], list):
                            print(f"    - Recommendations: {len(response['recommendations'])} items")
                        if "data" in response and isinstance(response["data"], dict):
                            print(f"    - Data fields: {list(response['data'].keys())}")
            
            print(f"\n✓ SUMMARY: {success_count} successful, {error_count} errors")
            
            if error_count == 0:
                print("✅ All agents completed without errors")
            elif success_count > 0:
                print("⚠️  Some agents succeeded, some failed - partial results available")
            else:
                print("❌ All agents failed")
                
            # Log the final response preview
            final_response = result.get('final_response', '')
            if final_response:
                print(f"\n📄 FINAL RESPONSE PREVIEW (first 10000 chars):")
                print("-" * 60)
                print(final_response[:10000] + ("..." if len(final_response) > 10000 else ""))
                print("-" * 60)
            
        except Exception as e:
            print(f"✗ FATAL ERROR processing query: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n=== TESTING SINGLE AGENT QUERIES (for comparison) ===")
    single_agent_queries = [
        # "What's the weather forecast for this week?",
        # "How much are corn prices today?",
        # "Show me my crop health from satellite data"
    ]
    
    for i, query in enumerate(single_agent_queries, 1):
        print(f"\n--- Single Agent Query {i} ---")
        print(f"Query: {query}")
        
        try:
            result = orchestrator.process_query(query, test_context)
            agent_count = len(result.get('agent_responses', {}))
            print(f"✓ Agents triggered: {agent_count}")
            print(f"✓ Intent: {result.get('intent_classification', 'unknown')}")
            
            # Log the final response for single agent queries too
            final_response = result.get('final_response', '')
            if final_response:
                print(f"📄 Final response preview: {final_response[:100]}...")
            
        except Exception as e:
            print(f"✗ Error: {e}")
    
    print("\n=== RESPONSE LOGGING ENHANCEMENTS ===")
    print("✅ Added detailed logging for each individual agent response")
    print("✅ Added full JSON response logging with visual separators")
    print("✅ Added final response logging with full content display")
    print("✅ Added response summary statistics and error tracking")
    print("✅ Added visual indicators (✓, ✗, ⚠️, ✅, ❌) for better readability")
    print("✅ Added response preview functionality")
    
    print("\n=== KEY IMPROVEMENTS IMPLEMENTED ===")
    print("✓ Added 'agents_to_run' field to track required agents")
    print("✓ Improved intent classification to identify multiple agents needed")  
    print("✓ Created 'run_multiple_agents' node to execute multiple agents sequentially")
    print("✓ Enhanced error handling for individual agent failures")
    print("✓ Updated graph structure to properly route multiple agent requests")
    print("✓ Added comprehensive logging for debugging and monitoring")
    print("✓ Added detailed response logging for all agents and final output")
    
    print("\n=== TESTING COMPLETED ===")

# if __name__ == "__main__":
# run_safe_tests()