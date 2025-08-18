# home/agents/tools.py
import requests
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from django.conf import settings
from home.models import *
import random
class WeatherAPITool:
    """Tool for fetching weather data"""
    API_KEY = "8352478422464e51b45184210251108"  # Better to store this in environment variables
    BASE_URL = "https://api.weatherapi.com/v1"

    @staticmethod
    def get_current_weather(farm_id: int) -> Dict[str, Any]:
        """Fetch current weather for a farm location"""
        try:
            # Get farm location - for now using London as default
            # In production, you would get the farm's coordinates from the database
            location = "London"  # This should come from farm.location or farm.coordinates
            
            # Make API request
            url = f"https://api.weatherapi.com/v1/current.json"
            params = {
                "key": "8352478422464e51b45184210251108",
                "q": location,
                "aqi": "no"
            }
            
            response = requests.get(url, params=params)
            if not response.ok:
                raise Exception(f"API request failed: {response.status_code}")
                
            data = response.json()
            
            # Extract relevant fields from current weather
            weather_data = {
                "temperature": data["current"]["temp_c"],
                "humidity": data["current"]["humidity"],
                "rainfall": data["current"]["precip_mm"],
                "wind_speed": data["current"]["wind_kph"],
                "pressure": data["current"]["pressure_mb"],
                "weather_condition": data["current"]["condition"]["text"].lower()
            }
            
            return {"status": "success", "data": weather_data}
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
        try:
            farm = Farm.objects.get(id=farm_id) if Farm.objects.get(id=farm_id) else {}
            # Mock weather API call - replace with actual API
            weather_data = {
                "temperature": random.uniform(15, 35),
                "humidity": random.uniform(30, 90),
                "rainfall": random.uniform(0, 10),
                "wind_speed": random.uniform(5, 25),
                "pressure": random.uniform(980, 1020),
                "weather_condition": random.choice(["sunny", "cloudy", "rainy", "stormy"])
            }
            
            # Save to database
            WeatherData.objects.create(
                farm=farm,
                forecast_date=datetime.now(),
                **weather_data
            )
            
            return {"status": "success", "data": weather_data}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    @staticmethod
    def get_weather_forecast(farm_id: int, days: int = 7) -> Dict[str, Any]:
        """Get weather forecast for specified days"""
        try:
            # Get farm location - for now using London as default
            # In production, you would get the farm's coordinates from the database
            location = "London"  # This should come from farm.location or farm.coordinates
            
            # Make API request
            url = f"https://api.weatherapi.com/v1/forecast.json"
            params = {
                "key": "8352478422464e51b45184210251108",
                "q": location,
                "days": days,
                "aqi": "no",
                "alerts": "yes"
            }
            
            response = requests.get(url, params=params)
            if not response.ok:
                raise Exception(f"API request failed: {response.status_code}")
                
            data = response.json()
            forecast_data = []
            
            # Extract relevant fields from each forecast day
            for day in data["forecast"]["forecastday"]:
                weather_data = {
                    "date": day["date"],
                    "temperature": day["day"]["avgtemp_c"],
                    "humidity": day["day"]["avghumidity"],
                    "rainfall": day["day"]["totalprecip_mm"],
                    "weather_condition": day["day"]["condition"]["text"].lower()
                }
                forecast_data.append(weather_data)
            
            return {"status": "success", "forecast": forecast_data}
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
        
        try:
            farm = Farm.objects.get(id=farm_id) if Farm.objects.get(id=farm_id) else {}
            forecast_data = []
            
            for i in range(days):
                forecast_date = datetime.now() + timedelta(days=i+1)
                weather_data = {
                    "date": forecast_date.isoformat(),
                    "temperature": random.uniform(15, 35),
                    "humidity": random.uniform(30, 90),
                    "rainfall": random.uniform(0, 15),
                    "weather_condition": random.choice(["sunny", "cloudy", "rainy", "stormy"])
                }
                forecast_data.append(weather_data)
                
                # Save forecast to database
                WeatherData.objects.create(
                    farm=farm,
                    forecast_date=forecast_date,
                    is_forecast=True,
                    temperature=weather_data["temperature"],
                    humidity=weather_data["humidity"],
                    rainfall=weather_data["rainfall"],
                    wind_speed=random.uniform(5, 25),
                    pressure=random.uniform(980, 1020),
                    weather_condition=weather_data["weather_condition"]
                )
            
            return {"status": "success", "forecast": forecast_data}
        except Exception as e:
            return {"status": "error", "message": str(e)}

class SatelliteAPITool:
    """Tool for fetching satellite imagery and analysis"""
    
    @staticmethod
    def get_ndvi_analysis(farm_id: int) -> Dict[str, Any]:
        """Get NDVI analysis for a farm using Sentinel Hub Statistical API"""
        try:
            try:
                farm = Farm.objects.get(id=farm_id)
                lat, lon = farm.latitude, farm.longitude
            except Exception as e:
                print(f"Warning: Farm not found for ID {farm_id}, using default coordinates")
                lat, lon = 77.70061, 24.222921
            # === 1. AUTHENTICATION ===
            token_url = "https://services.sentinel-hub.com/oauth/token"
            auth_response = requests.post(token_url, data={
                "grant_type": "client_credentials",
                "client_id": settings.SENTINEL_CLIENT_ID,
                "client_secret": settings.SENTINEL_CLIENT_SECRET
            })
            auth_response.raise_for_status()
            access_token = auth_response.json()["access_token"]
            
            print(f"Access token obtained: {access_token[:10]}...")  # Log first 10 chars for debugging

            # === 2. STATISTICAL NDVI REQUEST ===
            stats_url = "https://services.sentinel-hub.com/api/v1/statistics"
            headers = {
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json"
                        }

            request_body = {
                "input": {
                    "bounds": {
                        "bbox": [lon - 0.5, lat - 0.5, lon + 0.5, lat + 0.5],
                        "properties": {
                            "crs": "http://www.opengis.net/def/crs/EPSG/0/4326"
                        }
                    },
                    "data": [
                        {
                            "type": "sentinel-2-l2a",
                            "dataFilter": {}  # ← Empty as per your provided body
                        }
                    ]
                },
                "aggregation": {
                    "timeRange": {
                        "from": "2025-07-17T00:00:00Z",
                        "to": "2025-08-17T23:59:59Z"
                    },
                    "aggregationInterval": {
                        "of": "P10D"
                    },
                    "width": 512,
                    "height": 269.348,
                    "evalscript": """//VERSION=3
            function setup() {
            return {
                input: [{
                bands: [
                    "B04",
                    "B08",
                    "SCL",
                    "dataMask"
                ]
                }],
                output: [
                {
                    id: "data",
                    bands: 3
                },
                {
                    id: "scl",
                    sampleType: "INT8",
                    bands: 1
                },
                {
                    id: "dataMask",
                    bands: 1
                }]
            };
            }

            function evaluatePixel(samples) {
                let index = (samples.B08 - samples.B04) / (samples.B08 + samples.B04);
                return {
                    data: [index, samples.B08, samples.B04],
                    dataMask: [samples.dataMask],
                    scl: [samples.SCL]
                };
            }
            """
                },
                "calculations": {
                    "default": {}
                }
            }


            response = requests.post(stats_url, headers=headers, json=request_body)
            response.raise_for_status()
            stats = response.json()
            # print(f"NDVI statistics response: {json.dumps(stats, indent=2)}")  # Log first 1000 chars for debugging
            # === 3. EXTRACT LATEST NDVI ===
            ndvi_intervals = stats['data']

            # Safely get the latest interval that contains NDVI data
            latest_valid = next(
                (interval for interval in reversed(ndvi_intervals)
                if 'data' in interval['outputs'] and
                'bands' in interval['outputs']['data'] and
                'B0' in interval['outputs']['data']['bands']),
                None
            )

            if latest_valid:
                ndvi_stats = latest_valid['outputs']['data']['bands']['B0']['stats']
                average_ndvi = ndvi_stats['mean']

                # === 4. CLASSIFY VEGETATION HEALTH ===
                if average_ndvi < 0.2:
                    health = "poor"
                elif average_ndvi < 0.4:
                    health = "fair"
                elif average_ndvi < 0.6:
                    health = "good"
                else:
                    health = "excellent"

                ndvi_data = {
                    "average_ndvi": round(average_ndvi, 4),
                    "vegetation_health": health,
                    "stressed_areas_percentage": max(0, round((0.5 - average_ndvi) * 100, 2)),
                    "analysis_date": datetime.utcnow().isoformat()
                }

                # === 5. SAVE TO DATABASE ===
                try:
                    SatelliteData.objects.create(
                        farm=farm,
                        image_url=f"https://services.sentinel-hub.com/",
                        capture_date=datetime.utcnow(),
                        vegetation_index=ndvi_data["average_ndvi"],
                        cloud_coverage=0,
                        resolution_meters=10.0,
                        analysis_data=ndvi_data
                    )
                except Exception as e:
                    print(f"Error saving NDVI data to database: {e}")

                return {"status": "success", "data": ndvi_data}

            else:
                return {"status": "error", "message": "No valid NDVI data found in response."}


        except Exception as e:
            print(f"Error in NDVI analysis: {e}")
            return {"status": "error", "message": str(e)}

class MarketAPITool:
    """Tool for fetching market prices and trends"""
    
    BASE_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
    API_KEY = settings.DATA_GOV_API_KEY
    
    @staticmethod
    def get_crop_prices(
        crop_name: str,
        state: Optional[str] = None,
        district: Optional[str] = None,
        market: Optional[str] = None,
        variety: Optional[str] = None,
        grade: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Fetch crop prices from data.gov.in market API"""
        try:
            params = {
                "api-key": MarketAPITool.API_KEY,
                "format": "json",
                "limit": limit,
            }

            # Optional filters
            filters = {
                "commodity": crop_name,
                "state.keyword": state,
                "district": district,
                "market": market,
                "variety": variety,
                "grade": grade
            }

            # Add filters to the URL in expected format
            for key, value in filters.items():
                if value:
                    params[f"filters[{key}]"] = value

            response = requests.get(MarketAPITool.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

            return {
                "status": "success",
                "query_time": datetime.now().isoformat(),
                "records_found": len(data.get("records", [])),
                "data": data.get("records", [])
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    
    @staticmethod
    def search_market_trends(query: str) -> Dict[str, Any]:
        """Search for market trends using web search"""
        try:
            # Mock Tavily web search - replace with actual Tavily API
            search_results = {
                "query": query,
                "results": [
                    {
                        "title": f"Market Analysis: {query}",
                        "content": f"Recent trends show fluctuating prices for {query}",
                        "url": "https://example-market-news.com",
                        "relevance_score": random.uniform(0.7, 1.0)
                    }
                ],
                "search_time": datetime.now().isoformat()
            }
            
            return {"status": "success", "data": search_results}
        except Exception as e:
            return {"status": "error", "message": str(e)}

class SoilAPITool:
    """Tool for soil analysis and recommendations"""
    
    @staticmethod
    def analyze_soil_conditions(farm_id: int) -> Dict[str, Any]:
        """Analyze soil conditions for a farm"""
        try:
            farm = Farm.objects.get(id=farm_id) if Farm.objects.get(id=farm_id) else {}
            
            # Mock soil analysis
            soil_data = {
                "ph_level": random.uniform(5.5, 8.5),
                "nitrogen": random.uniform(10, 50),
                "phosphorus": random.uniform(5, 30),
                "potassium": random.uniform(50, 200),
                "organic_matter": random.uniform(1, 8),
                "moisture": random.uniform(10, 40),
                "temperature": random.uniform(15, 30),
                "recommendations": []
            }
            
            # Generate recommendations based on values
            if soil_data["ph_level"] < 6.0:
                soil_data["recommendations"].append("Consider lime application to increase pH")
            if soil_data["nitrogen"] < 20:
                soil_data["recommendations"].append("Apply nitrogen-rich fertilizer")
            if soil_data["moisture"] < 20:
                soil_data["recommendations"].append("Increase irrigation frequency")
            
            # Save to database
            SoilData.objects.create(
                farm=farm,
                ph_level=soil_data["ph_level"],
                nitrogen_content=soil_data["nitrogen"],
                phosphorus_content=soil_data["phosphorus"],
                potassium_content=soil_data["potassium"],
                organic_matter=soil_data["organic_matter"],
                moisture_level=soil_data["moisture"],
                temperature=soil_data["temperature"],
                location_lat=random.uniform(20, 40),
                location_lng=random.uniform(-120, -80),
                sample_date=datetime.now()
            )
            
            return {"status": "success", "data": soil_data}
        except Exception as e:
            return {"status": "error", "message": str(e)}

class PestAPITool:
    """Tool for pest detection and management"""
    
    @staticmethod
    def detect_pests(farm_id: int, symptoms: str = "") -> Dict[str, Any]:
        """Detect potential pests based on symptoms or monitoring"""
        try:
            farm = Farm.objects.get(id=farm_id)
            
            # Mock pest detection
            common_pests = ["aphids", "spider_mites", "thrips", "whiteflies", "caterpillars"]
            detected_pest = random.choice(common_pests)
            
            pest_data = {
                "pest_identified": detected_pest,
                "confidence": random.uniform(0.7, 0.95),
                "severity": random.choice(["low", "medium", "high"]),
                "affected_area_acres": random.uniform(0.5, 5.0),
                "treatment_recommendations": [
                    f"Apply appropriate pesticide for {detected_pest}",
                    "Monitor weekly for population changes",
                    "Consider biological control methods"
                ],
                "estimated_cost": random.uniform(50, 500)
            }
            
            # Save to database
            PestData.objects.create(
                farm=farm,
                pest_name=detected_pest,
                severity_level=pest_data["severity"],
                affected_area=pest_data["affected_area_acres"],
                detection_method="monitoring_system",
                recommended_treatment="; ".join(pest_data["treatment_recommendations"]),
                treatment_cost=pest_data["estimated_cost"],
                detected_at=datetime.now()
            )
            
            return {"status": "success", "data": pest_data}
        except Exception as e:
            return {"status": "error", "message": str(e)}

class TavilySearchTool:
    """Tool for web searching using Tavily API"""
    
    @staticmethod
    def search_web(query: str, num_results: int = 5) -> Dict[str, Any]:
        """Search the web for farming-related information"""
        try:
            # Mock Tavily API response - replace with actual API call
            # api_key = settings.TAVILY_API_KEY
            # response = requests.post(
            #     "https://api.tavily.com/search",
            #     json={"api_key": api_key, "query": query, "max_results": num_results}
            # )
            
            # Mock response for now
            search_results = {
                "query": query,
                "results": [
                    {
                        "title": f"Agricultural Information: {query}",
                        "content": f"Relevant farming information about {query}",
                        "url": f"https://farming-resource-{i}.com",
                        "score": random.uniform(0.8, 1.0)
                    } for i in range(num_results)
                ],
                "search_metadata": {
                    "total_results": num_results,
                    "search_time": datetime.now().isoformat()
                }
            }
            
            return {"status": "success", "data": search_results}
        except Exception as e:
            return {"status": "error", "message": str(e)}