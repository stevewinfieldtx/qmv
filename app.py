from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import os
import json
import uuid
from datetime import datetime
import redis
from dotenv import load_dotenv
import logging
from typing import Dict, Any, Optional, List

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis connection with fallback
try:
    redis_url = os.environ.get('REDIS_URL')
    if redis_url:
        redis_client = redis.from_url(redis_url)
        redis_client.ping()
        logger.info("Redis connection successful")
    else:
        logger.warning("REDIS_URL not found, Redis disabled")
        redis_client = None
except Exception as e:
    logger.error(f"Redis connection failed: {e}")
    redis_client = None

# Gemini setup
try:
    import google.generativeai as genai
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    if gemini_api_key:
        genai.configure(api_key=gemini_api_key)
        try:
            gemini_model = genai.GenerativeModel('gemini-1.5-flash')
            logger.info("Gemini service initialized with gemini-1.5-flash")
        except:
            try:
                gemini_model = genai.GenerativeModel('gemini-pro')
                logger.info("Gemini service initialized with gemini-pro")
            except:
                gemini_model = genai.GenerativeModel('models/gemini-pro')
                logger.info("Gemini service initialized with models/gemini-pro")
    else:
        logger.warning("GEMINI_API_KEY not found, Gemini disabled")
        gemini_model = None
except Exception as e:
    logger.error(f"Gemini initialization failed: {e}")
    gemini_model = None

# ============== CLASSES (SAME AS BEFORE) ==============

class SessionManager:
    """Manage user sessions and preference storage"""
    
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.session_expiry = 3600
        self.in_memory_store = {}
    
    def store_preferences(self, session_id: str, preferences: Dict[str, Any]) -> bool:
        try:
            preferences['stored_at'] = datetime.utcnow().isoformat()
            
            if self.redis_client:
                key = f"preferences:{session_id}"
                self.redis_client.setex(key, self.session_expiry, json.dumps(preferences))
                logger.info(f"Preferences stored in Redis for session: {session_id}")
            else:
                self.in_memory_store[session_id] = {
                    'data': preferences,
                    'expires_at': datetime.utcnow().timestamp() + self.session_expiry
                }
                logger.info(f"Preferences stored in memory for session: {session_id}")
            
            return True
        except Exception as e:
            logger.error(f"Error storing preferences: {e}")
            return False
    
    def get_preferences(self, session_id: str) -> Optional[Dict[str, Any]]:
        try:
            if self.redis_client:
                key = f"preferences:{session_id}"
                stored_data = self.redis_client.get(key)
                if stored_data:
                    return json.loads(stored_data)
            else:
                if session_id in self.in_memory_store:
                    stored_item = self.in_memory_store[session_id]
                    if datetime.utcnow().timestamp() > stored_item['expires_at']:
                        del self.in_memory_store[session_id]
                        return None
                    return stored_item['data']
            return None
        except Exception as e:
            logger.error(f"Error retrieving preferences: {e}")
            return None

class PreferenceValidator:
    def __init__(self):
        self.valid_genres = ['pop', 'rock', 'electronic', 'hip-hop', 'jazz', 'classical', 'country', 'folk', 'reggae', 'blues', 'funk', 'lofi', 'ambient']
        self.valid_moods = ['upbeat', 'relaxed', 'energetic', 'melancholic', 'happy', 'sad', 'angry', 'peaceful', 'dramatic', 'mysterious', 'romantic']
        self.valid_tempos = ['slow', 'medium', 'fast', 'very_fast']
    
    def validate_preferences(self, data: Dict[str, Any]) -> Dict[str, Any]:
        errors = []
        
        if not data:
            errors.append("No data provided")
            return {'valid': False, 'errors': errors}
        
        # Basic validation
        duration = data.get('duration')
        if duration:
            try:
                duration = int(duration)
                if duration < 10 or duration > 300:
                    errors.append("Duration must be between 10 and 300 seconds")
            except (ValueError, TypeError):
                errors.append("Duration must be a valid number")
        
        return {'valid': len(errors) == 0, 'errors': errors}

class PreferenceProcessor:
    def __init__(self):
        self.presets = {
            'energetic_pop': {
                'genre': 'pop', 'mood': 'upbeat', 'tempo': 'fast', 'energy_level': 'high',
                'visual_style': 'modern', 'color_scheme': 'vibrant'
            },
            'chill_lofi': {
                'genre': 'lofi', 'mood': 'relaxed', 'tempo': 'slow', 'energy_level': 'low',
                'visual_style': 'minimal', 'color_scheme': 'pastel'
            },
            'rock_anthem': {
                'genre': 'rock', 'mood': 'powerful', 'tempo': 'fast', 'energy_level': 'high',
                'visual_style': 'bold', 'color_scheme': 'dark'
            }
        }
    
    def process_preferences(self, raw_data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        return {
            'session_id': session_id,
            'timestamp': datetime.utcnow().isoformat(),
            'music_preferences': {
                'genre': raw_data.get('genre', 'pop'),
                'mood': raw_data.get('mood', 'upbeat'),
                'tempo': raw_data.get('tempo', 'medium'),
                'duration': int(raw_data.get('duration', 60)),
                'energy_level': raw_data.get('energy_level', 'medium'),
                'vocal_style': raw_data.get('vocal_style', 'none'),
                'music_prompt': raw_data.get('music_prompt', '')
            },
            'image_preferences': {
                'visual_style': raw_data.get('visual_style', 'modern'),
                'color_scheme': raw_data.get('color_scheme', 'vibrant'),
                'image_prompt': raw_data.get('image_prompt', '')
            },
            'general_preferences': {
                'project_name': raw_data.get('project_name', ''),
                'description': raw_data.get('description', ''),
                'target_audience': raw_data.get('target_audience', 'general'),
                'usage_purpose': raw_data.get('usage_purpose', 'personal')
            }
        }
    
    def get_presets(self) -> Dict[str, Any]:
        return self.presets

class GeminiService:
    def __init__(self, model):
        self.model = model
    
    def enhance_image_prompt(self, user_input: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not self.model:
                return {'success': False, 'error': 'Gemini API not configured'}
            
            music_prefs = preferences.get('music_preferences', {})
            image_prefs = preferences.get('image_preferences', {})
            
            prompt = f"""
            Create a realistic image prompt for AI image generation.
            
            User's idea: "{user_input}"
            Music: {music_prefs.get('genre', 'pop')} - {music_prefs.get('mood', 'upbeat')}
            Style: {image_prefs.get('visual_style', 'modern')}
            Colors: {image_prefs.get('color_scheme', 'vibrant')}
            
            Create a realistic, specific image prompt under 1500 characters that describes something real and achievable.
            """
            
            response = self.model.generate_content(prompt)
            enhanced_prompt = response.text.strip()
            
            if len(enhanced_prompt) > 1500:
                enhanced_prompt = enhanced_prompt[:1497] + "..."
            
            return {
                'success': True,
                'enhanced_prompt': enhanced_prompt,
                'alternatives': [
                    f"Portrait version: {user_input} with {image_prefs.get('color_scheme', 'vibrant')} lighting",
                    f"Landscape version: {user_input} in {image_prefs.get('visual_style', 'modern')} setting",
                    f"Close-up version: detailed {user_input} with artistic composition"
                ],
                'technical_notes': "Optimized for AI image generation",
                'original_prompt': user_input,
                'character_count': len(enhanced_prompt)
            }
            
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return {'success': False, 'error': f'Gemini API error: {str(e)}'}
    
    def generate_image_suggestions(self, preferences: Dict[str, Any]) -> Dict[str, Any]:
        try:
            suggestions = [
                {
                    'title': 'Urban Portrait',
                    'description': 'A person in modern clothing against a city backdrop with vibrant lighting.'
                },
                {
                    'title': 'Nature Scene',
                    'description': 'Beautiful natural landscape with colorful sunset lighting.'
                },
                {
                    'title': 'Studio Setup',
                    'description': 'Musical instruments in a modern studio with dynamic lighting.'
                }
            ]
            
            return {'success': True, 'suggestions': suggestions}
            
        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
            return {'success': False, 'error': str(e)}

# Initialize services
session_manager = SessionManager(redis_client)
validator = PreferenceValidator()
processor = PreferenceProcessor()
gemini_service = GeminiService(gemini_model)

# ============== ROUTES ==============

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'redis_connected': redis_client is not None,
        'gemini_configured': gemini_model is not None
    })

@app.route('/api/preferences', methods=['POST'])
def submit_preferences():
    try:
        data = request.get_json()
        
        validation_result = validator.validate_preferences(data)
        if not validation_result['valid']:
            return jsonify({
                'success': False,
                'errors': validation_result['errors']
            }), 400
        
        session_id = str(uuid.uuid4())
        processed_data = processor.process_preferences(data, session_id)
        
        if redis_client:
            session_manager.store_preferences(session_id, processed_data)
        else:
            session[session_id] = processed_data
        
        session['session_id'] = session_id
        
        logger.info(f"Preferences stored for session: {session_id}")
        
        # For now, just store the trigger in Redis (no Celery)
        if redis_client:
            redis_client.publish('phase1_completed', session_id)
            logger.info(f"Phase 1 completed signal sent for session: {session_id}")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Preferences saved successfully - Phase 2 will be triggered',
            'next_phase': 'music_generation'
        })
        
    except Exception as e:
        logger.error(f"Error in submit_preferences: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route('/api/preferences/<session_id>', methods=['GET'])
def get_preferences(session_id):
    try:
        preferences = None
        
        if redis_client:
            preferences = session_manager.get_preferences(session_id)
        else:
            preferences = session.get(session_id)
        
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
    presets = processor.get_presets()
    return jsonify({
        'success': True,
        'presets': presets
    })

@app.route('/api/enhance-image-prompt', methods=['POST'])
def enhance_image_prompt():
    try:
        data = request.get_json()
        user_prompt = data.get('prompt', '')
        session_id = data.get('session_id', '')
        
        if not user_prompt:
            return jsonify({
                'success': False,
                'error': 'No prompt provided'
            }), 400
        
        preferences = {}
        if session_id:
            if redis_client:
                preferences = session_manager.get_preferences(session_id) or {}
            else:
                preferences = session.get(session_id, {})
        
        result = gemini_service.enhance_image_prompt(user_prompt, preferences)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in enhance_image_prompt: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route('/api/image-suggestions', methods=['POST'])
def get_image_suggestions():
    try:
        data = request.get_json()
        session_id = data.get('session_id', '')
        temp_preferences = data.get('preferences', {})
        
        preferences = {}
        if session_id:
            if redis_client:
                preferences = session_manager.get_preferences(session_id) or {}
            else:
                preferences = session.get(session_id, {})
        elif temp_preferences:
            preferences = processor.process_preferences(temp_preferences, 'temp')
        
        if not preferences:
            return jsonify({
                'success': False,
                'error': 'No preferences available'
            }), 400
        
        result = gemini_service.generate_image_suggestions(preferences)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in get_image_suggestions: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route('/api/enhance-music-prompt', methods=['POST'])
def enhance_music_prompt():
    try:
        data = request.get_json()
        user_prompt = data.get('prompt', '')
        session_id = data.get('session_id', '')
        
        if not user_prompt:
            return jsonify({
                'success': False,
                'error': 'No prompt provided'
            }), 400
        
        preferences = {}
        if session_id:
            if redis_client:
                preferences = session_manager.get_preferences(session_id) or {}
            else:
                preferences = session.get(session_id, {})
        
        music_prefs = preferences.get('music_preferences', {})
        
        enhanced_prompt = f"Create a {music_prefs.get('genre', 'pop')} song with {music_prefs.get('mood', 'upbeat')} mood and {music_prefs.get('tempo', 'medium')} tempo. {user_prompt}"
        
        if len(enhanced_prompt) > 500:
            enhanced_prompt = enhanced_prompt[:497] + "..."
        
        return jsonify({
            'success': True,
            'enhanced_prompt': enhanced_prompt,
            'alternatives': [
                f"Focus on {music_prefs.get('tempo', 'medium')} tempo: {user_prompt}",
                f"Emphasize {music_prefs.get('energy_level', 'medium')} energy: {user_prompt}",
                f"Modern production style: {user_prompt}"
            ],
            'technical_notes': f"Optimized for {music_prefs.get('duration', 60)} second duration",
            'original_prompt': user_prompt,
            'character_count': len(enhanced_prompt)
        })
        
    except Exception as e:
        logger.error(f"Error in enhance_music_prompt: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_ENV') == 'development')
