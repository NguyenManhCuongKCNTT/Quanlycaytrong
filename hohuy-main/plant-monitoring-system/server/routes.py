from flask import Blueprint, render_template, request, jsonify
from models import SensorData, ThresholdSettings
from extensions import db, mqtt
from datetime import datetime, timedelta
from sqlalchemy import func
import json

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/api/current')
def get_current_data():
    latest_data = SensorData.query.order_by(SensorData.timestamp.desc()).first()
    
    if not latest_data:
        return jsonify({'error': 'No data available'}), 404
    
    return jsonify(latest_data.to_dict())

@main_bp.route('/api/thresholds', methods=['GET', 'POST'])
def manage_thresholds():
    if request.method == 'GET':
        threshold_settings = ThresholdSettings.query.first()
        if not threshold_settings:
            return jsonify({'error': 'No threshold settings found'}), 404
        return jsonify(threshold_settings.to_dict())
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            threshold_settings = ThresholdSettings.query.first()
            if not threshold_settings:
                threshold_settings = ThresholdSettings()
            
            if 'temperature_min' in data:
                threshold_settings.temperature_min = float(data['temperature_min'])
            if 'temperature_max' in data:
                threshold_settings.temperature_max = float(data['temperature_max'])
            if 'soil_moisture_min' in data:
                threshold_settings.soil_moisture_min = int(data['soil_moisture_min'])
            if 'humidity_min' in data:
                threshold_settings.humidity_min = float(data['humidity_min'])
            if 'light_level_min' in data:
                threshold_settings.light_level_min = int(data['light_level_min'])
            
            db.session.add(threshold_settings)
            db.session.commit()
            
            mqtt.publish('plant/thresholds', json.dumps(threshold_settings.to_dict()))
            
            return jsonify({'success': True, 'message': 'Thresholds updated successfully'})
        
        except Exception as e:
            return jsonify({'error': str(e)}), 400

@main_bp.route('/api/control', methods=['POST'])
def control_system():
    try:
        data = request.get_json()
        command = data.get('command')
        
        if not command:
            return jsonify({'error': 'No command specified'}), 400
        
        valid_commands = ['PUMP_ON', 'PUMP_OFF', 'LIGHT_ON', 'LIGHT_OFF']
        if command not in valid_commands:
            return jsonify({'error': f'Invalid command. Must be one of {valid_commands}'}), 400
        
        mqtt.publish('plant/command', command)
        
        return jsonify({'success': True, 'message': f'Command {command} sent successfully'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@main_bp.route('/api/mode', methods=['POST'])
def set_mode():
    try:
        data = request.get_json()
        mode = data.get('mode')
        
        if not mode:
            return jsonify({'error': 'No mode specified'}), 400
        
        valid_modes = ['AUTO', 'MANUAL']
        if mode not in valid_modes:
            return jsonify({'error': f'Invalid mode. Must be one of {valid_modes}'}), 400
        
        mqtt.publish('plant/mode', mode)
        
        return jsonify({'success': True, 'message': f'Mode set to {mode} successfully'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@main_bp.route('/api/history')
def get_history():
    period = request.args.get('period', 'day')
    data_type = request.args.get('type', 'all')
    
    now = datetime.now()
    if period == 'day':
        start_date = now - timedelta(days=1)
        interval = 'hour'
    elif period == 'week':
        start_date = now - timedelta(weeks=1)
        interval = 'day'
    elif period == 'month':
        start_date = now - timedelta(days=30)
        interval = 'day'
    elif period == 'year':
        start_date = now - timedelta(days=365)
        interval = 'month'
    else:
        return jsonify({'error': 'Invalid period. Must be one of [day, week, month, year]'}), 400
    
    if interval == 'hour':
        query = SensorData.query.filter(SensorData.timestamp >= start_date).order_by(SensorData.timestamp)
    elif interval == 'day':
        query = db.session.query(
            func.date(SensorData.timestamp).label('date'),
            func.avg(SensorData.temperature).label('temperature'),
            func.avg(SensorData.humidity).label('humidity'),
            func.avg(SensorData.soil_moisture).label('soil_moisture'),
            func.avg(SensorData.light_level).label('light_level')
        ).filter(SensorData.timestamp >= start_date).group_by(func.date(SensorData.timestamp))
    elif interval == 'month':
        query = db.session.query(
            func.strftime('%Y-%m', SensorData.timestamp).label('month'),
            func.avg(SensorData.temperature).label('temperature'),
            func.avg(SensorData.humidity).label('humidity'),
            func.avg(SensorData.soil_moisture).label('soil_moisture'),
            func.avg(SensorData.light_level).label('light_level')
        ).filter(SensorData.timestamp >= start_date).group_by(func.strftime('%Y-%m', SensorData.timestamp))
    
    results = query.all()
    
    if interval == 'hour':
        chart_data = [
            {
                'timestamp': result.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'temperature': result.temperature,
                'humidity': result.humidity,
                'soil_moisture': result.soil_moisture,
                'light_level': result.light_level
            } for result in results
        ]
    elif interval == 'day':
        chart_data = [
            {
                'date': result.date,
                'temperature': result.temperature,
                'humidity': result.humidity,
                'soil_moisture': result.soil_moisture,
                'light_level': result.light_level
            } for result in results
        ]
    elif interval == 'month':
        chart_data = [
            {
                'month': result.month,
                'temperature': result.temperature,
                'humidity': result.humidity,
                'soil_moisture': result.soil_moisture,
                'light_level': result.light_level
            } for result in results
        ]
    
    if data_type != 'all' and data_type in ['temperature', 'humidity', 'soil_moisture', 'light_level']:
        for item in chart_data:
            for key in list(item.keys()):
                if key != data_type and key not in ['timestamp', 'date', 'month']:
                    del item[key]
    
    return jsonify({
        'period': period,
        'interval': interval,
        'type': data_type,
        'data': chart_data
    })