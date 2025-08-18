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



class SoilAgent:
    """Agent for soil analysis and recommendations"""
    
    def __init__(self):
        self.model = genai.GenerativeModel(LLM_MODEL)
        self.tools = SoilAPITool()
    
    def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process soil-related queries"""
        try:
            farm_id = context.get("farm_id")
            if not farm_id:
                return {"agent": "soil", "error": "Farm ID required"}
            
            # Analyze soil conditions
            soil_data = self.tools.analyze_soil_conditions(farm_id)
            
            # Generate recommendations
            analysis_prompt = f"""
            Analyze this soil data:
            {json.dumps(soil_data, indent=2)}
            
            User Question: {query}
            
            Provide specific soil management recommendations, fertilization advice, and improvement strategies.
            """
            
            analysis = self.model.generate_content(analysis_prompt)
            
            return {
                "agent": "soil",
                "data": soil_data,
                "analysis": analysis.text,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"agent": "soil", "error": str(e)}
