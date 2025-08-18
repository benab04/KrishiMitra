# home/agents/farm_agents.py
from typing import Dict, Any
from datetime import datetime
from home.agents.tools import *
from home.models import *

class UserContextProvider:
    """Provides user context for agent decisions - FIXED VERSION"""
    
    @staticmethod
    def get_user_context(user_id: int, farm_id: int = None) -> Dict[str, Any]:
        """Get comprehensive user context with proper error handling"""
        try:
            # FIXED: Import User model properly
            from django.contrib.auth.models import User
            
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return {"error": f"User with ID {user_id} not found"}
            
            context = {
                "user_id": user_id,
                "username": user.username,
                "timestamp": datetime.now().isoformat()
            }
            
            if farm_id:
                try:
                    # FIXED: Ensure proper model import and foreign key relationship
                    farm = Farm.objects.get(id=farm_id, owner=user)
                    context.update({
                        "farm_id": farm_id,
                        "farm_name": farm.name,
                        "farm_location": farm.location,
                        "farm_size": getattr(farm, 'size_acres', 0)  # Safe attribute access
                    })
                    
                    # Add recent data context with safe queries
                    try:
                        recent_weather = WeatherData.objects.filter(
                            farm=farm
                        ).order_by('-created_at').first()
                        
                        if recent_weather:
                            context["recent_weather"] = {
                                "temperature": getattr(recent_weather, 'temperature', None),
                                "humidity": getattr(recent_weather, 'humidity', None),
                                "timestamp": recent_weather.created_at.isoformat() if recent_weather.created_at else None
                            }
                    except Exception as weather_error:
                        print(f"Warning: Could not fetch recent weather data: {weather_error}")
                    
                    try:
                        recent_soil = SoilData.objects.filter(
                            farm=farm
                        ).order_by('-created_at').first()
                        
                        if recent_soil:
                            context["recent_soil"] = {
                                "ph": getattr(recent_soil, 'ph', None),
                                "nitrogen": getattr(recent_soil, 'nitrogen', None),
                                "timestamp": recent_soil.created_at.isoformat() if recent_soil.created_at else None
                            }
                    except Exception as soil_error:
                        print(f"Warning: Could not fetch recent soil data: {soil_error}")
                    
                except Farm.DoesNotExist:
                    print(f"Warning: Farm with ID {farm_id} not found for user {user_id}")
                except Exception as farm_error:
                    print(f"Warning: Error fetching farm data: {farm_error}")
            
            return context
            
        except Exception as e:
            print(f"Error in get_user_context: {e}")
            return {"error": f"Context retrieval failed: {str(e)}"}