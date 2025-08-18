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


class NotificationAgent:
    """Agent for generating and sending notifications - FIXED VERSION"""
    
    def __init__(self):
        self.model = genai.GenerativeModel(LLM_MODEL)
    
    def process_notifications(self, response_content: str, user_context: Dict[str, Any]) -> None:
        """Generate notifications based on response content with proper validation"""
        
        try:
            user_id = user_context.get("user_id")
            if not user_id:
                print("Warning: No user_id provided for notifications")
                return
            
            # FIXED: Validate user exists before processing
            try:
                from django.contrib.auth.models import User
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                print(f"Warning: User with ID {user_id} does not exist, skipping notifications")
                return
            
            # Analyze response for notification triggers
            notification_prompt = f"""
            Analyze this farming response for urgent issues that need notifications:
            {response_content}
            
            Identify any:
            - Weather alerts (storms, extreme conditions)
            - Pest warnings (high severity infestations)
            - Market opportunities (price spikes, good selling times)
            - Soil issues (critical pH, nutrient deficiencies)
            
            Return JSON array of notifications (max 3):
            [{"title": "...", "message": "...", "type": "...", "priority": "..."}]
            
            If no urgent issues found, return empty array: []
            """
            
            result = self.model.generate_content(notification_prompt)
            notifications_text = result.text.strip()
            
            # Handle potential JSON parsing errors
            try:
                notifications = json.loads(notifications_text)
                if not isinstance(notifications, list):
                    print("Warning: Invalid notification format, expected array")
                    return
                    
            except json.JSONDecodeError as json_error:
                print(f"Warning: Failed to parse notifications JSON: {json_error}")
                print(f"Raw response: {notifications_text}")
                return
            
            # Save notifications to database with proper validation
            saved_count = 0
            for notif in notifications[:3]:  # Limit to 3 notifications
                try:
                    if not isinstance(notif, dict):
                        continue
                        
                    # Validate required fields
                    title = notif.get("title", "Farm Alert")[:200]  # Limit title length
                    message = notif.get("message", "")[:1000]  # Limit message length
                    notification_type = notif.get("type", "general")[:50]
                    priority = notif.get("priority", "medium")[:20]
                    
                    # Only create if we have meaningful content
                    if title and message:
                        Notification.objects.create(
                            user=user,  # Use user object instead of user_id
                            title=title,
                            message=message,
                            notification_type=notification_type,
                            priority=priority
                        )
                        saved_count += 1
                        
                except Exception as notif_error:
                    print(f"Error saving individual notification: {notif_error}")
                    continue
            
            if saved_count > 0:
                print(f"Successfully created {saved_count} notifications for user {user_id}")
            else:
                print("No urgent notifications created")
                
        except Exception as e:
            print(f"Notification processing error: {e}")
            # Continue execution without failing the entire process
