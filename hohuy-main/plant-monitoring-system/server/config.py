import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Option 2: Use file-based SQLite with absolute path
    # basedir = os.path.abspath(os.path.dirname(__file__))
    # db_path = os.path.join(basedir, 'plant_monitor.db')
    # SQLALCHEMY_DATABASE_URI = f'sqlite:///{db_path}'
    
    # Option 3: Use the database path from environment variable
    # SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///plant_monitor.db'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    print(f"Database configuration: {SQLALCHEMY_DATABASE_URI}")

    MQTT_BROKER_URL = os.environ.get('MQTT_BROKER_URL') or 'mqtt-dashboard.com'
    MQTT_BROKER_PORT = int(os.environ.get('MQTT_BROKER_PORT') or 1883)
    MQTT_USERNAME = os.environ.get('MQTT_USERNAME')
    MQTT_PASSWORD = os.environ.get('MQTT_PASSWORD')
    MQTT_KEEPALIVE = int(os.environ.get('MQTT_KEEPALIVE') or 60)
    MQTT_TLS_ENABLED = os.environ.get('MQTT_TLS_ENABLED', 'False').lower() in ('true', '1', 't')
    MQTT_TLS_CERT_REQS = int(os.environ.get('MQTT_TLS_CERT_REQS') or 0)
    MQTT_TLS_CA_CERTS = os.environ.get('MQTT_TLS_CA_CERTS')
    MQTT_CLIENT_ID = os.environ.get('MQTT_CLIENT_ID') or 'flask_plant_monitor'