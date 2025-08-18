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



class MarketAgent:
    """Agent specialized in market analysis and pricing"""
    
    def __init__(self):
        self.model = genai.GenerativeModel(LLM_MODEL)
        self.tools = MarketAPITool()
    
    def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process market-related queries"""
        try:
            # Extract crop information from query
            crop_name = self._extract_crop_name(query)
            location = context.get("farm_location", "national")
            
            # Get market data
            market_data = self.tools.get_crop_prices(crop_name, location)
            
            # Search for additional market trends if needed
            if "trend" in query.lower() or "forecast" in query.lower():
                trend_data = self.tools.search_market_trends(f"{crop_name} market trends")
                market_data["trends"] = trend_data
            
            # Generate analysis
            analysis_prompt = f"""
            Analyze this market data for {crop_name}:
            {json.dumps(market_data, indent=2)}
            
            User Question: {query}
            
            Provide specific market insights and recommendations.
            """
            
            analysis = self.model.generate_content(analysis_prompt)
            
            return {
                "agent": "market",
                "data": market_data,
                "analysis": analysis.text,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"agent": "market", "error": str(e)}
    
    def _extract_crop_name(self, query: str) -> str:
        """Extract crop name from query - simplified implementation"""
        common_crops = ["wheat", "corn", "rice", "soybeans", "tomatoes", "potatoes"]
        query_lower = query.lower()
        
        for crop in common_crops:
            if crop in query_lower:
                return crop
        return "general_crops"