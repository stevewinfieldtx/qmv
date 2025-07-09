from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import os
import json
import uuid
from datetime import datetime
import redis
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis connection for session storage
try:
    redis_client = redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379'))
    redis_client.ping()
    logger.info("Redis connection successful")
except Exception as e:
    logger.error(f"Redis connection failed: {e}")
    redis_client = None

# Import our modules
from services.preference_processor import PreferenceProcessor
from utils.validators import PreferenceValidator
from utils.session_manager import SessionManager

# Initialize services
preference_processor = PreferenceProcessor()
validator = PreferenceValidator()
session_manager = SessionManager(redis_client)

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'redis_connected': redis_client is not None
    })

@app.route('/api/preferences', methods=['POST'])
def submit_preferences():
    """Handle user preference submission"""
    try:
        data = request.get_json()
        
        # Validate input data
        validation_result = validator.validate_preferences(data)
        if not validation_result['valid']:
            return jsonify({
                'success': False,
                'errors': validation_result['errors']
            }), 400
        
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Process preferences
        processed_data = preference_processor.process_preferences(data, session_id)
        
        # Store in session
        session_manager.store_preferences(session_id, processed_data)
        
        # Store session ID in Flask session
        session['session_id'] = session_id
        
        logger.info(f"Preferences stored for session: {session_id}")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Preferences saved successfully',
            'next_phase': 'music_creation'
        })
        
    except Exception as e:
        logger.error(f"Error in submit_preferences: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route('/api/preferences/<session_id>', methods=['GET'])
def get_preferences(session_id):
    """Retrieve stored preferences"""
    try:
        preferences = session_manager.get_preferences(session_id)
        
        if not preferences:
            return jsonify({
                'success': False,
                'error': 'Session not found'
            }), 404
        
        return jsonify({
            'success': True,
            'preferences': preferences
        })
        
    except Exception as e:
        logger.error(f"Error retrieving preferences: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route('/api/presets')
def get_presets():
    """Get available presets"""
    presets = preference_processor.get_presets()
    return jsonify({
        'success': True,
        'presets': presets
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_ENV') == 'development')
