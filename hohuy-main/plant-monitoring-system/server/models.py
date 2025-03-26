from extensions import db
from datetime import datetime

class SensorData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)
    soil_moisture = db.Column(db.Integer, nullable=False)
    light_level = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SensorData {self.timestamp}: Temp={self.temperature}, Humidity={self.humidity}, Soil={self.soil_moisture}, Light={self.light_level}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'temperature': self.temperature,
            'humidity': self.humidity,
            'soil_moisture': self.soil_moisture,
            'light_level': self.light_level,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }

class ThresholdSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    temperature_min = db.Column(db.Float, nullable=False, default=18.0)
    temperature_max = db.Column(db.Float, nullable=False, default=30.0)
    soil_moisture_min = db.Column(db.Integer, nullable=False, default=30)
    humidity_min = db.Column(db.Float, nullable=False, default=40.0)
    light_level_min = db.Column(db.Integer, nullable=False, default=30)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ThresholdSettings: Temp min={self.temperature_min}, Temp max={self.temperature_max}>'
    
    def to_dict(self):
        return {
            'temperature_min': self.temperature_min,
            'temperature_max': self.temperature_max,
            'soil_moisture_min': self.soil_moisture_min,
            'humidity_min': self.humidity_min,
            'light_level_min': self.light_level_min,
            'last_updated': self.last_updated.strftime('%Y-%m-%d %H:%M:%S')
        }