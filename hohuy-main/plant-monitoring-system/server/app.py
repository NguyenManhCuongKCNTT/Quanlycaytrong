from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from config import Config
from extensions import db, mqtt
from models import SensorData, ThresholdSettings
import json
from datetime import datetime, timedelta
import logging
import sys
import argparse
from gesture_control import start_gesture_thread

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')
app.config.from_object(Config)

socketio = SocketIO(app, cors_allowed_origins="*")
db.init_app(app)
mqtt.init_app(app)

from routes import main_bp
app.register_blueprint(main_bp)

TOPIC_DATA = "plant/data"
TOPIC_TEMPERATURE = "plant/temperature"
TOPIC_HUMIDITY = "plant/humidity"
TOPIC_SOIL_MOISTURE = "plant/soil_moisture"
TOPIC_LIGHT_LEVEL = "plant/light_level"
TOPIC_PUMP_STATUS = "plant/pump_status"
TOPIC_LIGHT_STATUS = "plant/light_status"
TOPIC_MODE = "plant/mode"
TOPIC_THRESHOLDS = "plant/thresholds"
TOPIC_COMMAND = "plant/command"

current_state = {
    "temperature": 0,
    "humidity": 0,
    "soil_moisture": 0,
    "light_level": 0,
    "pump_status": "OFF",
    "light_status": "OFF",
    "mode": "AUTO"
}

thresholds = {
    "temperature_min": 18.0,
    "temperature_max": 30.0,
    "soil_moisture_min": 30,
    "humidity_min": 40.0,
    "light_level_min": 30
}

last_db_save_time = datetime.now()
DB_SAVE_INTERVAL = 60

gesture_thread = None

@mqtt.on_connect()
def handle_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to MQTT broker")
        mqtt.subscribe(TOPIC_DATA)
        mqtt.subscribe(TOPIC_TEMPERATURE)
        mqtt.subscribe(TOPIC_HUMIDITY)
        mqtt.subscribe(TOPIC_SOIL_MOISTURE)
        mqtt.subscribe(TOPIC_LIGHT_LEVEL)
        mqtt.subscribe(TOPIC_PUMP_STATUS)
        mqtt.subscribe(TOPIC_LIGHT_STATUS)
        mqtt.subscribe(TOPIC_MODE)
        mqtt.subscribe(TOPIC_THRESHOLDS)
    else:
        logger.error(f"Failed to connect to MQTT broker with code {rc}")

def save_sensor_data_to_db(temperature, humidity, soil_moisture, light_level, timestamp=None):
    global last_db_save_time
    
    current_time = datetime.now()
    
    if (current_time - last_db_save_time).total_seconds() >= DB_SAVE_INTERVAL:
        try:
            if timestamp is None:
                timestamp = current_time
            elif isinstance(timestamp, str):
                try:
                    timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    timestamp = current_time
            
            new_data = SensorData(
                temperature=temperature,
                humidity=humidity,
                soil_moisture=soil_moisture,
                light_level=light_level,
                timestamp=timestamp
            )
            
            with app.app_context():
                db.session.add(new_data)
                db.session.commit()
                
            last_db_save_time = current_time
            logger.info(f"Sensor data saved to database at {current_time}")
            
        except Exception as e:
            logger.error(f"Error saving sensor data to database: {str(e)}")
            with app.app_context():
                db.session.rollback()

@mqtt.on_message()
def handle_message(client, userdata, message):
    topic = message.topic
    payload = message.payload.decode()
    logger.info(f"Received message on topic {topic}: {payload}")
    
    try:
        if topic == TOPIC_DATA:
            data = json.loads(payload)
            timestamp = data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            if "temperature" in data:
                current_state["temperature"] = data["temperature"]
            if "humidity" in data:
                current_state["humidity"] = data["humidity"]
            if "soil_moisture" in data:
                current_state["soil_moisture"] = data["soil_moisture"]
            if "light_level" in data:
                current_state["light_level"] = data["light_level"]
            
            save_sensor_data_to_db(
                data["temperature"], 
                data["humidity"], 
                data["soil_moisture"],
                data["light_level"],
                timestamp
            )
            
            socketio.emit('sensor_data_update', data)
            
        elif topic == TOPIC_TEMPERATURE:
            value = float(payload)
            if current_state["temperature"] != value:
                current_state["temperature"] = value
                socketio.emit('temperature_update', {"value": value})
        
        elif topic == TOPIC_HUMIDITY:
            value = float(payload)
            if current_state["humidity"] != value:
                current_state["humidity"] = value
                socketio.emit('humidity_update', {"value": value})
        
        elif topic == TOPIC_SOIL_MOISTURE:
            value = int(payload)
            if current_state["soil_moisture"] != value:
                current_state["soil_moisture"] = value
                socketio.emit('soil_moisture_update', {"value": value})
                
        elif topic == TOPIC_LIGHT_LEVEL:
            value = int(payload)
            if current_state["light_level"] != value:
                current_state["light_level"] = value
                socketio.emit('light_level_update', {"value": value})
            
        if topic in [TOPIC_TEMPERATURE, TOPIC_HUMIDITY, TOPIC_SOIL_MOISTURE, TOPIC_LIGHT_LEVEL]:
            if all(current_state[key] != 0 for key in ["temperature", "humidity", "soil_moisture", "light_level"]):
                save_sensor_data_to_db(
                    current_state["temperature"],
                    current_state["humidity"],
                    current_state["soil_moisture"],
                    current_state["light_level"]
                )
            
        elif topic == TOPIC_PUMP_STATUS:
            if current_state["pump_status"] != payload:
                current_state["pump_status"] = payload
                socketio.emit('pump_status_update', {"status": payload})
            
        elif topic == TOPIC_LIGHT_STATUS:
            if current_state["light_status"] != payload:
                current_state["light_status"] = payload
                socketio.emit('light_status_update', {"status": payload})
            
        elif topic == TOPIC_MODE:
            if current_state["mode"] != payload:
                current_state["mode"] = payload
                socketio.emit('mode_update', {"mode": payload})
            
        elif topic == TOPIC_THRESHOLDS:
            threshold_data = json.loads(payload)
            thresholds.update(threshold_data)
            update_thresholds_in_db(threshold_data)
            socketio.emit('thresholds_update', threshold_data)
            
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")

def update_thresholds_in_db(threshold_data):
    try:
        with app.app_context():
            settings = ThresholdSettings.query.first()
            if not settings:
                settings = ThresholdSettings()
            
            if "temperature_min" in threshold_data:
                settings.temperature_min = threshold_data["temperature_min"]
            if "temperature_max" in threshold_data:
                settings.temperature_max = threshold_data["temperature_max"]
            if "soil_moisture_min" in threshold_data:
                settings.soil_moisture_min = threshold_data["soil_moisture_min"]
            if "humidity_min" in threshold_data:
                settings.humidity_min = threshold_data["humidity_min"]
            if "light_level_min" in threshold_data:
                settings.light_level_min = threshold_data["light_level_min"]
            
            db.session.add(settings)
            db.session.commit()
            logger.info("Thresholds updated in database")
    except Exception as e:
        logger.error(f"Error updating thresholds in database: {str(e)}")
        with app.app_context():
            db.session.rollback()

@socketio.on('connect')
def handle_websocket_connect():
    logger.info(f"Client connected: {request.sid}")
    socketio.emit('initial_state', {
        "current_state": current_state,
        "thresholds": thresholds
    }, room=request.sid)

@socketio.on('disconnect')
def handle_websocket_disconnect():
    logger.info(f"Client disconnected: {request.sid}")

@socketio.on('set_mode')
def handle_set_mode(data):
    mode = data.get('mode', 'AUTO')
    logger.info(f"Setting mode to {mode}")
    mqtt.publish(TOPIC_MODE, mode, retain=True)

@socketio.on('set_thresholds')
def handle_set_thresholds(data):
    logger.info(f"Setting thresholds to {data}")
    mqtt.publish(TOPIC_THRESHOLDS, json.dumps(data), retain=True)

@socketio.on('send_command')
def handle_send_command(data):
    command = data.get('command')
    if command:
        logger.info(f"Sending command: {command}")
        mqtt.publish(TOPIC_COMMAND, command)

def get_historical_data(period='day'):
    now = datetime.now()
    
    if period == 'day':
        start_date = now - timedelta(days=1)
    elif period == 'week':
        start_date = now - timedelta(weeks=1)
    elif period == 'month':
        start_date = now - timedelta(days=30)
    elif period == 'year':
        start_date = now - timedelta(days=365)
    else:
        start_date = now - timedelta(days=1)
    
    with app.app_context():
        data = SensorData.query.filter(SensorData.timestamp >= start_date).order_by(SensorData.timestamp).all()
    return data

def start_gesture_recognition(test_mode=False):
    global gesture_thread
    try:
        logger.info("Starting gesture recognition thread")
        gesture_thread = start_gesture_thread(test_mode)
        logger.info("Gesture recognition thread started")
    except Exception as e:
        logger.error(f"Failed to start gesture recognition: {str(e)}")

def init_database():
    with app.app_context():
        db.create_all()
        
        if not ThresholdSettings.query.first():
            initial_settings = ThresholdSettings(
                temperature_min=18.0,
                temperature_max=30.0,
                soil_moisture_min=30,
                humidity_min=40.0,
                light_level_min=30
            )
            db.session.add(initial_settings)
            db.session.commit()
        else:
            settings = ThresholdSettings.query.first()
            thresholds["temperature_min"] = settings.temperature_min
            thresholds["temperature_max"] = settings.temperature_max
            thresholds["soil_moisture_min"] = settings.soil_moisture_min
            thresholds["humidity_min"] = settings.humidity_min
            thresholds["light_level_min"] = settings.light_level_min

def parse_arguments():
    parser = argparse.ArgumentParser(description='Plant Monitoring System')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--app', action='store_true', help='Run only the web application without gesture control')
    group.add_argument('--cam', action='store_true', help='Run only the gesture control with camera visualization')
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_arguments()
    
    if args.cam:
        import gesture_control
        gesture_control.run_gesture_detection(test_mode=True)
    else:
        init_database()
        if not args.app:
            start_gesture_recognition()
    
        socketio.run(app, debug=Config.DEBUG, host='0.0.0.0', port=5001)