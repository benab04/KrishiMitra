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



class SatelliteAgent:
    """Agent for satellite imagery and vegetation analysis"""
    
    def __init__(self):
        self.model = genai.GenerativeModel(LLM_MODEL)
        self.tools = SatelliteAPITool()
    
    def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process satellite-related queries"""
        try:
            farm_id = context.get("farm_id")
            if not farm_id:
                return {"agent": "satellite", "error": "Farm ID required"}
            
            # Get NDVI analysis
            ndvi_data = self.tools.get_ndvi_analysis(farm_id)
            
            # Generate insights
            analysis_prompt = f"""
            Analyze this satellite/NDVI data:
            {json.dumps(ndvi_data, indent=2)}
            
            User Question: {query}
            
            Provide specific insights about crop health and field conditions.
            """
            
            analysis = self.model.generate_content(analysis_prompt)
            
            return {
                "agent": "satellite",
                "data": ndvi_data,
                "analysis": analysis.text,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"agent": "satellite", "error": str(e)}