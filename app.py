```python
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

# Gemini setup with correct model name
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
        self.in_memory_store = {}  # Fallback for when Redis is not available
    
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
        self.valid_resolutions = ['720p', '1080p', '4k']
        self.valid_aspect_ratios = ['16:9', '9:16', '1:1', '4:3']
    
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
    """Process and structure user preferences for music and image generation"""
    
    def __init__(self):
        self.presets = {
            'energetic_pop': {
                'genre': 'pop', 'mood': 'upbeat', 'tempo': 'fast', 'energy_level': 'high',
                'visual_style': 'modern', 'color_scheme': 'vibrant', 'animation_style': 'dynamic'
            },
            'chill_lofi': {
                'genre': 'lofi', 'mood': 'relaxed', 'tempo': 'slow', 'energy_level': 'low',
                'visual_style': 'minimal', 'color_scheme': 'pastel', 'animation_style': 'smooth'
            },
            'rock_anthem': {
                'genre': 'rock', 'mood': 'powerful', 'tempo': 'fast', 'energy_level': 'high',
                'visual_style': 'bold', 'color_scheme': 'dark', 'animation_style': 'intense'
            },
            'ambient_electronic': {
                'genre': 'electronic', 'mood': 'atmospheric', 'tempo': 'medium', 'energy_level': 'medium',
                'visual_style': 'futuristic', 'color_scheme': 'neon', 'animation_style': 'flowing'
            }
        }
    
    def process_preferences(self, raw_data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Process raw user input into structured preferences"""
        
        # Calculate image count based on tempo and duration
        tempo = raw_data.get('tempo', 'medium')
        duration = int(raw_data.get('duration', 60))
        
        # BPM mapping for image generation
        bpm_mapping = {
            'slow': 80,      # 1.33 seconds per image
            'medium': 120,   # 1 second per image  
            'fast': 160,     # 0.75 seconds per image
            'very_fast': 200 # 0.6 seconds per image
        }
        
        bpm = bpm_mapping.get(tempo, 120)
        images_needed = int((duration * bpm) / 60)  # Calculate images needed
        
        return {
            'session_id': session_id,
            'timestamp': datetime.utcnow().isoformat(),
            'music_preferences': {
                'genre': raw_data.get('genre', 'pop'),
                'mood': raw_data.get('mood', 'upbeat'),
                'tempo': tempo,
                'duration': duration,
                'energy_level': raw_data.get('energy_level', 'medium'),
                'vocal_style': raw_data.get('vocal_style', 'none'),
                'music_prompt': raw_data.get('music_prompt', '')
            },
            'image_preferences': {
                'visual_style': raw_data.get('visual_style', 'modern'),
                'color_scheme': raw_data.get('color_scheme', 'vibrant'),
                'aspect_ratio': raw_data.get('aspect_ratio', '16:9'),
                'resolution': raw_data.get('resolution', '1080p'),
                'image_prompt': raw_data.get('image_prompt', ''),
                'images_needed': images_needed,
                'bpm': bpm,
                'seconds_per_image': 60 / bpm
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
            You are helping create a realistic image prompt for AI image generation for a music slideshow.
            
            User's basic idea: "{user_input}"
            
            Music context:
            - Genre: {music_prefs.get('genre', 'pop')}
            - Mood: {music_prefs.get('mood', 'upbeat')}
            - Style: {image_prefs.get('visual_style', 'modern')}
            - Colors: {image_prefs.get('color_scheme', 'vibrant')}
            
            Create a realistic, specific image prompt that:
            1. Is under 1500 characters
            2. Describes something that actually exists/could exist
            3. Is clear and specific for AI image generation
            4. Matches the music mood and style
            5. Avoids overly abstract or impossible concepts
            
            Focus on real subjects, settings, lighting, and compositions that would work well for a music slideshow.
            """
            
            response = self.model.generate_content(prompt)
            enhanced_prompt = response.text.strip()
            
            # Ensure under 1500 characters
            if len(enhanced_prompt) > 1500:
                enhanced_prompt = enhanced_prompt[:1497] + "..."
            
            # Create realistic alternatives
            alternatives = []
            alt_concepts = [
                "a portrait-focused version",
                "a landscape/environment version", 
                "a close-up detail version"
            ]
            
            for concept in alt_concepts:
                alt_prompt = f"""
                Create {concept} of: "{user_input}"
                Style: {image_prefs.get('visual_style', 'modern')}
                Colors: {image_prefs.get('color_scheme', 'vibrant')}
                Music mood: {music_prefs.get('mood', 'upbeat')}
                
                Keep it realistic and under 200 characters.
                """
                
                try:
                    alt_response = self.model.generate_content(alt_prompt)
                    alt_text = alt_response.text.strip()
                    if len(alt_text) > 200:
                        alt_text = alt_text[:197] + "..."
                    alternatives.append(alt_text)
                except:
                    alternatives.append(f"A {concept} with {image_prefs.get('color_scheme', 'vibrant')} colors and {image_prefs.get('visual_style', 'modern')} style")
            
            return {
                'success': True,
                'enhanced_prompt': enhanced_prompt,
                'alternatives': alternatives[:3],
                'technical_notes': f"Will generate {image_prefs.get('images_needed', 60)} image variations for {music_prefs.get('duration', 60)} second slideshow",
                'original_prompt': user_input,
                'character_count': len(enhanced_prompt)
            }
            
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return {'success': False, 'error': f'Gemini API error: {str(e)}'}
    
    def generate_image_suggestions(self, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Generate realistic image suggestions based on preferences"""
        try:
            if not self.model:
                return self._get_realistic_fallback_suggestions(preferences)
            
            music_prefs = preferences.get('music_preferences', {})
            image_prefs = preferences.get('image_preferences', {})
            
            prompt = f"""
            Create 5 realistic image concepts for a music slideshow with these parameters:

            Music: {music_prefs.get('genre', 'pop')} - {music_prefs.get('mood', 'upbeat')} - {music_prefs.get('tempo', 'medium')} tempo
            Visual: {image_prefs.get('visual_style', 'modern')} style with {image_prefs.get('color_scheme', 'vibrant')} colors
            Duration: {music_prefs.get('duration', 60)} seconds ({image_prefs.get('images_needed', 60)} images needed)

            For each concept, provide:
            1. A clear, descriptive title
            2. A realistic description (under 300 characters) of what would be shown
            3. Focus on real subjects, places, and scenarios that exist

            Make them varied but all realistic and suitable for AI image generation.
            Avoid overly abstract or impossible concepts.

            Format as:
            1. Title: [Title]
            Description: [Description]

            2. Title: [Title]
            Description: [Description]

            [Continue for 5 concepts]
            """
            
            response = self.model.generate_content(prompt)
            suggestions = self._parse_realistic_suggestions(response.text, preferences)
            
            return {'success': True, 'suggestions': suggestions}
            
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return self._get_realistic_fallback_suggestions(preferences)
    
    def _parse_realistic_suggestions(self, response_text: str, preferences: Dict[str, Any]) -> List[Dict[str, str]]:
        """Parse Gemini response into realistic suggestions"""
        suggestions = []
        lines = response_text.split('\n')
        
        current_title = ""
        current_description = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith(('1.', '2.', '3.', '4.', '5.')) or line.startswith('Title:'):
                if current_title and current_description:
                    # Ensure description is under 300 characters
                    if len(current_description) > 300:
                        current_description = current_description[:297] + "..."
                    
                    suggestions.append({
                        'title': current_title,
                        'description': current_description
                    })
                
                if line.startswith('Title:'):
                    current_title = line.replace('Title:', '').strip()
                else:
                    current_title = line.replace('1.', '').replace('2.', '').replace('3.', '').replace('4.', '').replace('5.', '').replace('Title:', '').strip()
                current_description = ""
            elif line.startswith('Description:'):
                current_description = line.replace('Description:', '').strip()
            elif current_title and current_description:
                current_description += " " + line
        
        # Add the last suggestion
        if current_title and current_description:
            if len(current_description) > 300:
                current_description = current_description[:297] + "..."
            suggestions.append({
                'title': current_title,
                'description': current_description
            })
        
        # If parsing failed, return realistic fallbacks
        if not suggestions:
            return self._get_realistic_fallback_suggestions(preferences)['suggestions']
        
        return suggestions[:5]
    
    def _get_realistic_fallback_suggestions(self, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Provide realistic fallback suggestions"""
        music_prefs = preferences.get('music_preferences', {})
        image_prefs = preferences.get('image_preferences', {})
        
        genre = music_prefs.get('genre', 'pop')
        mood = music_prefs.get('mood', 'upbeat')
        style = image_prefs.get('visual_style', 'modern')
        colors = image_prefs.get('color_scheme', 'vibrant')
        
        suggestions = [
            {
                'title': f'Urban {style.title()} Portrait',
                'description': f'A person in {style} clothing against a city backdrop with {colors} lighting. Clean composition with shallow depth of field, perfect for {genre} music.'
            },
            {
                'title': f'Nature & Music',
                'description': f'Beautiful natural landscape with {colors} sunset/sunrise colors. {style} composition capturing the {mood} mood through lighting and scenery.'
            },
            {
                'title': f'Studio Performance',
                'description': f'Musician with instruments in a {style} studio setting. {colors} stage lighting creates dynamic shadows and highlights matching the {genre} vibe.'
            },
            {
                'title': f'City Life Montage',
                'description': f'Urban scenes with {colors} neon signs and {style} architecture. Street photography style capturing the energy of {mood} {genre} music.'
            },
            {
                'title': f'Abstract Objects',
                'description': f'{style} still life with everyday objects arranged artistically. {colors} color palette with interesting textures and geometric shapes.'
            }
        ]
        
        return {'success': True, 'suggestions': suggestions}

# ============== INITIALIZE SERVICES ==============

session_manager = SessionManager(redis_client)
validator = PreferenceValidator()
processor = PreferenceProcessor()
gemini_service = GeminiService(gemini_model)

# ============== ROUTES ==============

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
        'redis_connected': redis_client is not None,
        'gemini_configured': gemini_model is not None
    })

@app.route('/api/preferences', methods=['POST'])
def submit_preferences():
    """Handle user preference submission and trigger Phase 2"""
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
        processed_data = processor.process_preferences(data, session_id)
        
        # Store in session
        if redis_client:
            session_manager.store_preferences(session_id, processed_data)
        else:
            session[session_id] = processed_data
        
        session['session_id'] = session_id
        
        logger.info(f"Preferences stored for session: {session_id}")
        
        # Trigger Phase 2 automatically
        if redis_client:
            redis_client.publish('phase1_completed', session_id)
            logger.info(f"Triggered Phase 2 for session: {session_id}")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Preferences saved and Phase 2 triggered',
            'images_needed': processed_data['image_preferences']['images_needed'],
            'next_phase': 'music_and_image_creation'
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
    """Get available presets"""
    presets = processor.get_presets()
    return jsonify({
        'success': True,
        'presets': presets
    })

@app.route('/api/enhance-image-prompt', methods=['POST'])
def enhance_image_prompt():
    """Enhance user's image prompt using Gemini AI"""
    try:
        data = request.get_json()
        user_prompt = data.get('prompt', '')
        session_id = data.get('session_id', '')
        
        if not user_prompt:
            return jsonify({
                'success': False,
                'error': 'No prompt provided'
            }), 400
        
        # Get user preferences
        preferences = {}
        if session_id:
            if redis_client:
                preferences = session_manager.get_preferences(session_id) or {}
            else:
                preferences = session.get(session_id, {})
        
        # Enhance prompt
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
    """Get AI-generated image suggestions"""
    try:
        data = request.get_json()
        session_id = data.get('session_id', '')
        temp_preferences = data.get('preferences', {})
        
        # Get preferences
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
        
        # Generate suggestions
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
    """Enhance user's music prompt using Gemini AI"""
    try:
        data = request.get_json()
        user_prompt = data.get('prompt', '')
        session_id = data.get('session_id', '')
        
        if not user_prompt:
            return jsonify({
                'success': False,
                'error': 'No prompt provided'
            }), 400
        
        # Get preferences
        preferences = {}
        if session_id:
            if redis_client:
                preferences = session_manager.get_preferences(session_id) or {}
            else:
                preferences = session.get(session_id, {})
        
        # Simple enhancement for music
        enhanced_prompt = f"Create a {preferences.get('music_preferences', {}).get('genre', 'pop')} song with {preferences.get('music_preferences', {}).get('mood', 'upbeat')} mood. {user_prompt}"
        
        if len(enhanced_prompt) > 500:
            enhanced_prompt = enhanced_prompt[:497] + "..."
        
        return jsonify({
            'success': True,
            'enhanced_prompt': enhanced_prompt,
            'alternatives': [
                f"Focus on {preferences.get('music_preferences', {}).get('tempo', 'medium')} tempo: {user_prompt}",
                f"Emphasize {preferences.get('music_preferences', {}).get('energy_level', 'medium')} energy: {user_prompt}",
                f"Modern production style: {user_prompt}"
            ],
            'technical_notes': f"Optimized for {preferences.get('music_preferences', {}).get('duration', 60)} second duration",
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
```
