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
import validators

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

# ============== CLASSES ==============

class SessionManager:
    """Manage user sessions and preference storage"""
    
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.session_expiry = 3600  # 1 hour in seconds
        self.in_memory_store = {}
    
    def store_preferences(self, session_id: str, preferences: Dict[str, Any]) -> bool:
        """Store user preferences in Redis or memory"""
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
        """Retrieve user preferences from Redis or memory"""
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
    """Validate user input preferences"""
    
    def __init__(self):
        self.valid_genres = ['pop', 'rock', 'electronic', 'hip-hop', 'jazz', 'classical', 'country', 'folk', 'reggae', 'blues', 'funk', 'lofi', 'ambient']
        self.valid_moods = ['upbeat', 'relaxed', 'energetic', 'melancholic', 'happy', 'sad', 'angry', 'peaceful', 'dramatic', 'mysterious', 'romantic']
        self.valid_tempos = ['slow', 'medium', 'fast', 'very_fast']
        self.valid_visual_styles = ['modern', 'vintage', 'minimal', 'bold', 'abstract', 'realistic', 'cartoon', 'futuristic', 'retro']
        self.valid_color_schemes = ['vibrant', 'pastel', 'dark', 'monochrome', 'neon', 'warm', 'cool', 'earth_tones', 'rainbow']
    
    def validate_preferences(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate all user preferences"""
        errors = []
        
        if not data:
            errors.append("No data provided")
            return {'valid': False, 'errors': errors}
        
        # Duration validation
        duration = data.get('duration')
        if duration:
            try:
                duration = int(duration)
                if duration < 10 or duration > 300:
                    errors.append("Duration must be between 10 and 300 seconds")
            except (ValueError, TypeError):
                errors.append("Duration must be a valid number")
        
        # Project name validation
        project_name = data.get('project_name', '')
        if project_name and len(project_name) > 100:
            errors.append("Project name must be less than 100 characters")
        
        # Image prompt validation
        image_prompt = data.get('image_prompt', '')
        if image_prompt and len(image_prompt) > 1500:
            errors.append("Image prompt must be less than 1500 characters")
        
        return {'valid': len(errors) == 0, 'errors': errors}

class PreferenceProcessor:
    """Process and structure user preferences for music generation"""
    
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
            },
            'ambient_electronic': {
                'genre': 'electronic', 'mood': 'atmospheric', 'tempo': 'medium', 'energy_level': 'medium',
                'visual_style': 'futuristic', 'color_scheme': 'neon'
            }
        }
    
    def process_preferences(self, raw_data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Process raw user input into structured preferences"""
        
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
        """Return available presets"""
        return self.presets

class GeminiService:
    """Service for interacting with Google Gemini AI"""
    
    def __init__(self, model):
        self.model = model
    
    def enhance_image_prompt(self, user_input: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance user's image prompt with AI suggestions - REALISTIC & UNDER 1500 CHARS"""
        try:
            if not self.model:
                return {'success': False, 'error': 'Gemini API not configured'}
            
            # Get context from preferences
            music_prefs = preferences.get('music_preferences', {})
            image_prefs = preferences.get('image_preferences', {})
            
            prompt = f"""
            Create a realistic image prompt for AI image generation for a music slideshow.
            
            User's idea: "{user_input}"
