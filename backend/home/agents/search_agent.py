# home/agents/search_agent.py
import json
from typing import Dict, Any, List
from tavily import TavilyClient
from django.conf import settings
import google.generativeai as genai

class SearchAgent:
    """Agent for performing optimized web searches using Tavily API"""
    
    def __init__(self):
        # Initialize Tavily client
        self.tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        
        # Initialize Gemini for query optimization and result processing
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Search configuration
        self.max_results = 5
        self.search_depth = "advanced"
        self.include_answer = True
        
    def process(self, user_query: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Main processing method for search agent"""
        print("\n[SEARCH AGENT] Starting search processing...")
        print(f"[SEARCH AGENT] Original query: {user_query}")
        
        try:
            # Step 1: Optimize the search query
            optimized_query = self._optimize_search_query(user_query, user_context)
            print(f"[SEARCH AGENT] Optimized query: {optimized_query}")
            
            # Step 2: Perform the search
            search_results = self._perform_search(optimized_query)
            
            # Step 3: Process and analyze results
            processed_results = self._process_search_results(search_results, user_query, user_context)
            
            # Step 4: Generate recommendations
            recommendations = self._generate_recommendations(processed_results, user_query, user_context)
            
            return {
                "data": {
                    "original_query": user_query,
                    "optimized_query": optimized_query,
                    "search_results": processed_results,
                    "result_count": len(search_results.get("results", [])),
                    "search_answer": search_results.get("answer", ""),
                    "sources": self._extract_sources(search_results)
                },
                "recommendations": recommendations,
                "confidence": self._calculate_confidence(search_results, processed_results),
                "agent_type": "search"
            }
            
        except Exception as e:
            print(f"[SEARCH AGENT] Error: {e}")
            return {
                "error": f"Search failed: {str(e)}",
                "data": {
                    "original_query": user_query,
                    "optimized_query": "",
                    "search_results": [],
                    "result_count": 0,
                    "search_answer": "",
                    "sources": []
                },
                "recommendations": [
                    "Unable to perform web search due to error",
                    "Please check your internet connection and try again",
                    "Consider using more specific search terms"
                ],
                "confidence": 0.1,
                "agent_type": "search"
            }
    
    def _optimize_search_query(self, user_query: str, user_context: Dict[str, Any]) -> str:
        """Optimize the user query for better search results"""
        farm_location = user_context.get("farm_location", "")
        farm_name = user_context.get("farm_name", "")
        
        prompt = f"""
        Optimize this farm-related query for web search to get the most relevant and recent results:
        
        Original Query: {user_query}
        Farm Location: {farm_location}
        Farm Context: {farm_name}
        
        Rules for optimization:
        1. Keep it concise but specific
        2. Add relevant agricultural keywords if missing
        3. Include location if relevant to the query
        4. Add time-sensitive terms like "2024", "current", "latest" if appropriate
        5. Focus on actionable information
        6. Remove conversational elements
        
        Examples:
        - "What should I plant?" → "best crops to plant {farm_location} 2024 season"
        - "Crop prices" → "current crop prices {farm_location} agricultural market 2024"
        - "Weather impact on farming" → "weather impact farming {farm_location} agricultural forecast"
        
        Return only the optimized search query, nothing else.
        """
        
        try:
            response = self.model.generate_content(prompt)
            optimized = response.text.strip().replace('{farm_location}', farm_location)
            return optimized if optimized else user_query
        except Exception as e:
            print(f"[SEARCH AGENT] Query optimization error: {e}")
            # Fallback: basic optimization
            if farm_location:
                return f"{user_query} {farm_location} agriculture farming"
            return f"{user_query} agriculture farming"
    
    def _perform_search(self, query: str) -> Dict[str, Any]:
        """Perform the actual search using Tavily"""
        try:
            print(f"[SEARCH AGENT] Performing Tavily search...")
            
            search_response = self.tavily_client.search(
                query=query,
                search_depth=self.search_depth,
                max_results=self.max_results,
                include_answer=self.include_answer,
                include_domains=None,
                exclude_domains=["social_media", "forums"],  # Exclude less reliable sources
                include_raw_content=False
            )
            
            print(f"[SEARCH AGENT] Search completed. Found {len(search_response.get('results', []))} results")
            return search_response
            
        except Exception as e:
            print(f"[SEARCH AGENT] Tavily search error: {e}")
            # Return empty results structure
            return {
                "results": [],
                "answer": "",
                "query": query
            }
    
    def _process_search_results(self, search_results: Dict[str, Any], original_query: str, user_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process and filter search results for relevance"""
        results = search_results.get("results", [])
        processed = []
        
        for result in results:
            try:
                # Extract and clean the result data
                processed_result = {
                    "title": result.get("title", ""),
                    "content": result.get("content", ""),
                    "url": result.get("url", ""),
                    "score": result.get("score", 0.0),
                    "published_date": result.get("published_date", ""),
                    "relevance": self._calculate_relevance(result, original_query)
                }
                processed.append(processed_result)
            except Exception as e:
                print(f"[SEARCH AGENT] Error processing result: {e}")
                continue
        
        # Sort by relevance and score
        processed.sort(key=lambda x: (x["relevance"], x["score"]), reverse=True)
        
        return processed[:self.max_results]  # Return top results
    
    def _calculate_relevance(self, result: Dict[str, Any], query: str) -> float:
        """Calculate relevance score for a search result"""
        try:
            title = result.get("title", "").lower()
            content = result.get("content", "").lower()
            query_lower = query.lower()
            
            # Simple relevance calculation based on keyword matches
            query_words = query_lower.split()
            title_matches = sum(1 for word in query_words if word in title)
            content_matches = sum(1 for word in query_words if word in content)
            
            # Agriculture-specific keywords boost
            ag_keywords = ["farm", "crop", "agriculture", "farming", "harvest", "plant", "soil", "weather", "pest", "market"]
            ag_score = sum(1 for keyword in ag_keywords if keyword in title or keyword in content)
            
            # Calculate final relevance
            relevance = (title_matches * 2 + content_matches + ag_score) / len(query_words)
            return min(relevance, 1.0)  # Cap at 1.0
            
        except Exception:
            return 0.0
    
    def _generate_recommendations(self, processed_results: List[Dict[str, Any]], original_query: str, user_context: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on search results"""
        if not processed_results:
            return [
                "No relevant search results found for your query",
                "Try refining your search with more specific terms",
                "Check your internet connection and try again"
            ]
        
        # Combine top results content for analysis
        combined_content = ""
        for result in processed_results[:3]:  # Use top 3 results
            combined_content += f"Title: {result['title']}\nContent: {result['content'][:500]}...\n\n"
        
        prompt = f"""
        Based on these search results, provide 3-5 actionable recommendations for the farmer's query.
        
        Original Query: {original_query}
        Farm Location: {user_context.get('farm_location', 'Not specified')}
        
        Search Results:
        {combined_content}
        
        Generate practical, actionable recommendations that a farmer can implement.
        Focus on:
        1. Immediate actions they can take
        2. Long-term strategies
        3. Resources or tools they should consider
        4. Timing considerations
        5. Cost-effective solutions
        
        Format as a simple list of recommendations (3-5 items).
        Each recommendation should be specific and actionable.
        """
        
        try:
            response = self.model.generate_content(prompt)
            recommendations_text = response.text.strip()
            
            # Parse recommendations into list
            recommendations = []
            for line in recommendations_text.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    # Clean up formatting
                    line = line.lstrip('•-*1234567890. ')
                    if line:
                        recommendations.append(line)
            
            return recommendations[:5] if recommendations else [
                "Review the search results for detailed information",
                "Consider consulting with local agricultural experts",
                "Monitor the situation and search for updates regularly"
            ]
            
        except Exception as e:
            print(f"[SEARCH AGENT] Recommendation generation error: {e}")
            return [
                "Review the search results for relevant information",
                "Consider consulting with agricultural experts in your area",
                "Keep monitoring for updates on this topic"
            ]
    
    def _extract_sources(self, search_results: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract source information from search results"""
        sources = []
        results = search_results.get("results", [])
        
        for result in results:
            source = {
                "title": result.get("title", "Unknown Title"),
                "url": result.get("url", ""),
                "published_date": result.get("published_date", ""),
                "domain": self._extract_domain(result.get("url", ""))
            }
            sources.append(source)
        
        return sources
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return "Unknown Domain"
    
    def _calculate_confidence(self, search_results: Dict[str, Any], processed_results: List[Dict[str, Any]]) -> float:
        """Calculate confidence score for the search results"""
        try:
            results_count = len(processed_results)
            if results_count == 0:
                return 0.1
            
            # Base confidence on number and quality of results
            base_confidence = min(results_count / 5.0, 1.0)  # Up to 1.0 for 5+ results
            
            # Boost confidence if we have high-relevance results
            if processed_results:
                avg_relevance = sum(r.get("relevance", 0) for r in processed_results) / len(processed_results)
                relevance_boost = avg_relevance * 0.3  # Up to 0.3 boost
                
                # Boost confidence if Tavily provided a direct answer
                answer_boost = 0.2 if search_results.get("answer") else 0.0
                
                final_confidence = min(base_confidence + relevance_boost + answer_boost, 1.0)
                return final_confidence
            
            return base_confidence
            
        except Exception:
            return 0.5  # Default confidence