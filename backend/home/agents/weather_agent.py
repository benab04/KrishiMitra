import google.generativeai as genai
from langgraph.graph import StateGraph, END
from typing import Dict, List, Any, TypedDict
from dataclasses import dataclass
import json, re
from datetime import datetime
from django.conf import settings
from home.agents.tools import *
from home.models import *
import matplotlib.pyplot as plt
import networkx as nx


LLM_MODEL = 'gemini-2.5-flash'  



class WeatherAgent:
    """Agent for weather analysis and forecasting"""
    
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        self.tools = WeatherAPITool()
    
    def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process weather-related queries"""
        try:
            farm_id = context.get("farm_id")
            if not farm_id:
                return {"agent": "weather", "error": "Farm ID required"}
            
            # # Get current weather
            # current_weather = self.tools.get_current_weather(farm_id)
            # weather_data = current_weather
            
            intent_prompt= f"""
            Your task is to say if the forecast data needs to be fetched or not based on the user's query.
            
            This is the user's query: {query}
            
            Respond ONLY with raw JSON (no code fences, no markdown, no extra text) with a key "fetch_forecast" which is either true or false, the confidence score of the intent, and the number of days the forecast is required for. 
            The upper limit for the number of days is 7. It is better to return a higher number of days if the user asks for a forecast.
            
            Example response: {{"fetch_forecast": true, "confidence": 0.95, "days": 3}}
            
            Do not return any other text or explanation.
            """
            
            
            response = self.model.generate_content(intent_prompt)
            result = json.loads(response.text)
            
            if str(result["fetch_forecast"]).lower() == "true":
                forecast_data = self.tools.get_weather_forecast(farm_id, min(7,int(result.get("days"))))
                weather_data = forecast_data
            # Get forecast if requested
            
            # Generate analysis
            analysis_prompt = f"""
            Analyze this weather data:
            {json.dumps(weather_data, indent=2)}
            
            User Question: {query}
            
            Provide weather insights and farming recommendations based on conditions. Limit your response to 3-4 sentences.
            """
            
            analysis = self.model.generate_content(analysis_prompt)
            
            return {
                "agent": "weather",
                "data": weather_data,
                "analysis": analysis.text,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"agent": "weather", "error": str(e)}