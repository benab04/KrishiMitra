# home/models.py
from django.db import models
from django.contrib.auth.models import User
import json

class Farm(models.Model):
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    size_acres = models.FloatField()
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class MarketData(models.Model):
    crop_name = models.CharField(max_length=100)
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    market_location = models.CharField(max_length=255)
    date_recorded = models.DateTimeField(auto_now_add=True)
    demand_level = models.CharField(max_length=20, choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ])
    supply_level = models.CharField(max_length=20, choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ])
    source = models.CharField(max_length=100)

class SatelliteData(models.Model):
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE)
    image_url = models.URLField()
    capture_date = models.DateTimeField()
    vegetation_index = models.FloatField(null=True, blank=True)  # NDVI
    cloud_coverage = models.FloatField()
    resolution_meters = models.FloatField()
    analysis_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

class WeatherData(models.Model):
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE)
    temperature = models.FloatField()
    humidity = models.FloatField()
    rainfall = models.FloatField(default=0)
    wind_speed = models.FloatField()
    pressure = models.FloatField()
    weather_condition = models.CharField(max_length=100)
    forecast_date = models.DateTimeField()
    is_forecast = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class PestData(models.Model):
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE)
    pest_name = models.CharField(max_length=100)
    severity_level = models.CharField(max_length=20, choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ])
    affected_area = models.FloatField()  # in acres
    detection_method = models.CharField(max_length=100)
    recommended_treatment = models.TextField()
    treatment_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    detected_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

class SoilData(models.Model):
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE)
    ph_level = models.FloatField()
    nitrogen_content = models.FloatField()
    phosphorus_content = models.FloatField()
    potassium_content = models.FloatField()
    organic_matter = models.FloatField()
    moisture_level = models.FloatField()
    temperature = models.FloatField()
    location_lat = models.FloatField()
    location_lng = models.FloatField()
    sample_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

class AgentQuery(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    query_text = models.TextField()
    intent_classification = models.CharField(max_length=100)
    agents_triggered = models.JSONField(default=list)
    response_data = models.JSONField(default=dict)
    confidence_score = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    response_time = models.FloatField()  # in seconds

class KnowledgeVector(models.Model):
    content = models.TextField()
    vector_embedding = models.JSONField()  # Store as JSON array
    content_type = models.CharField(max_length=50, choices=[
        ('weather', 'Weather'),
        ('market', 'Market'),
        ('pest', 'Pest'),
        ('soil', 'Soil'),
        ('satellite', 'Satellite'),
        ('general', 'General')
    ])
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, choices=[
        ('weather_alert', 'Weather Alert'),
        ('pest_warning', 'Pest Warning'),
        ('market_opportunity', 'Market Opportunity'),
        ('soil_analysis', 'Soil Analysis'),
        ('general', 'General')
    ])
    is_read = models.BooleanField(default=False)
    priority = models.CharField(max_length=20, choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ])
    created_at = models.DateTimeField(auto_now_add=True)