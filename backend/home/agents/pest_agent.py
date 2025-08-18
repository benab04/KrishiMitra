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



class PestAgent:
    """Agent for pest detection and management"""
    
    def __init__(self):
        self.model = genai.GenerativeModel(LLM_MODEL)
        self.tools = PestAPITool()
    
    def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process pest-related queries"""
        try:
            farm_id = context.get("farm_id")
            if not farm_id:
                return {"agent": "pest", "error": "Farm ID required"}
            
            # Extract symptoms from query
            symptoms = self._extract_symptoms(query)
            
            # Detect pests
            pest_data = self.tools.detect_pests(farm_id, symptoms)
            
            # Generate recommendations
            analysis_prompt = f"""
            Analyze this pest detection data:
            {json.dumps(pest_data, indent=2)}
            
            User Question: {query}
            User described symptoms: {symptoms}
            
            Provide specific pest management recommendations and treatment options.
            """
            
            analysis = self.model.generate_content(analysis_prompt)
            
            return {
                "agent": "pest",
                "data": pest_data,
                "analysis": analysis.text,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"agent": "pest", "error": str(e)}
    
    def _extract_symptoms(self, query: str) -> str:
        """Extract pest symptoms from user query"""
        symptom_keywords = ["holes", "spots", "yellowing", "wilting", "damage", "eating", "chewing"]
        symptoms = []
        query_lower = query.lower()
        
        for keyword in symptom_keywords:
            if keyword in query_lower:
                symptoms.append(keyword)
        
        return ", ".join(symptoms) if symptoms else "general monitoring"
