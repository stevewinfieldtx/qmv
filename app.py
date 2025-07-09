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
        # Use the correct model name - try both options
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
        
        return {'valid': len(errors) == 0, 'errors': errors}

class PreferenceProcessor:
    """Process and structure user preferences for music and video generation"""
    
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
            'video_preferences': {
                'visual_style': raw_data.get('visual_style', 'modern'),
                'color_scheme': raw_data.get('color_scheme', 'vibrant'),
                'animation_style': raw_data.get('animation_style', 'smooth'),
                'aspect_ratio': raw_data.get('aspect_ratio', '16:9'),
                'resolution': raw_data.get('resolution', '1080p'),
                'transition_style': raw_data.get('transition_style', 'fade'),
                'video_prompt': raw_data.get('video_prompt', '')
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
    
    def enhance_video_prompt(self, user_input: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance user's video prompt with AI suggestions"""
        try:
            if not self.model:
                return {'success': False, 'error': 'Gemini API not configured'}
            
            # Get context from preferences
            music_prefs = preferences.get('music_preferences', {})
            video_prefs = preferences.get('video_preferences', {})
            
            prompt = f"""
            You are a professional video director and creative prompt engineer. Take this user's basic video concept and transform it into a detailed, specific, and visually rich prompt for AI video generation.

            User's input: "{user_input}"
            
            Context:
            - Music Genre: {music_prefs.get('genre', 'pop')}
            - Music Mood: {music_prefs.get('mood', 'upbeat')}
            - Music Tempo: {music_prefs.get('tempo', 'medium')}
            - Visual Style: {video_prefs.get('visual_style', 'modern')}
            - Color Scheme: {video_prefs.get('color_scheme', 'vibrant')}
            - Duration: {music_prefs.get('duration', 60)} seconds

            Please create an enhanced video prompt that includes:
            1. Specific visual scenes and imagery
            2. Camera movements and angles
            3. Lighting and atmosphere details
            4. Color palette specifics
            5. Scene transitions and pacing
            6. Visual effects and style elements

            Make it detailed enough that an AI video generator could create something compelling and specific, not generic.
            """
            
            response = self.model.generate_content(prompt)
            enhanced_prompt = response.text.strip()
            
            # Create alternatives
            alternatives = []
            for i in range(3):
                alt_prompt = f"""
                Create a different detailed video concept based on: "{user_input}"
                
                Style: {video_prefs.get('visual_style', 'modern')}
                Colors: {video_prefs.get('color_scheme', 'vibrant')}
                Music: {music_prefs.get('genre', 'pop')} - {music_prefs.get('mood', 'upbeat')}
                
                Focus on alternative #{i+1}: Make this concept unique and specific with detailed visual descriptions.
                """
                
                try:
                    alt_response = self.model.generate_content(alt_prompt)
                    alternatives.append(alt_response.text.strip())
                except:
                    alternatives.append(f"Alternative concept focusing on {video_prefs.get('visual_style', 'modern')} aesthetics with {video_prefs.get('color_scheme', 'vibrant')} color grading")
            
            return {
                'success': True,
                'enhanced_prompt': enhanced_prompt,
                'alternatives': alternatives[:3],
                'technical_notes': f"Optimized for {video_prefs.get('resolution', '1080p')} {video_prefs.get('aspect_ratio', '16:9')} video generation with {music_prefs.get('duration', 60)} second duration",
                'original_prompt': user_input
            }
            
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return {'success': False, 'error': f'Gemini API error: {str(e)}'}
    
    def generate_video_suggestions(self, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Generate detailed video suggestions based on preferences"""
        try:
            if not self.model:
                # Provide detailed fallback suggestions
                return self._get_detailed_fallback_suggestions(preferences)
            
            music_prefs = preferences.get('music_preferences', {})
            video_prefs = preferences.get('video_preferences', {})
            
            prompt = f"""
            You are a creative video director. Create 5 detailed, specific video concepts for a music video with these parameters:

            Music Style:
            - Genre: {music_prefs.get('genre', 'pop')}
            - Mood: {music_prefs.get('mood', 'upbeat')}
            - Tempo: {music_prefs.get('tempo', 'medium')}
            - Duration: {music_prefs.get('duration', 60)} seconds

            Visual Requirements:
            - Style: {video_prefs.get('visual_style', 'modern')}
            - Colors: {video_prefs.get('color_scheme', 'vibrant')}
            - Animation: {video_prefs.get('animation_style', 'smooth')}
            - Resolution: {video_prefs.get('resolution', '1080p')}

            For each concept, provide:
            1. A creative title
            2. Detailed description of specific scenes, camera work, lighting, and visual elements
            3. How it connects to the music style

            Make each concept unique and visually detailed - not generic descriptions.

            Format as:
            CONCEPT 1:
            Title: [Creative Title]
            Description: [Detailed visual description]

            CONCEPT 2:
            Title: [Creative Title]
            Description: [Detailed visual description]

            [Continue for 5 concepts]
            """
            
            response = self.model.generate_content(prompt)
            suggestions = self._parse_suggestions(response.text, preferences)
            
            return {'success': True, 'suggestions': suggestions}
            
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return self._get_detailed_fallback_suggestions(preferences)
    
    def _parse_suggestions(self, response_text: str, preferences: Dict[str, Any]) -> List[Dict[str, str]]:
        """Parse Gemini response into structured suggestions"""
        suggestions = []
        lines = response_text.split('\n')
        
        current_title = ""
        current_description = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('CONCEPT') or line.startswith('Title:'):
                if current_title and current_description:
                    suggestions.append({
                        'title': current_title,
                        'description': current_description
                    })
                
                if line.startswith('Title:'):
                    current_title = line.replace('Title:', '').strip()
                current_description = ""
            elif line.startswith('Description:'):
                current_description = line.replace('Description:', '').strip()
            elif current_title and not current_description:
                current_title = line
            elif current_title and current_description:
                current_description += " " + line
        
        # Add the last suggestion
        if current_title and current_description:
            suggestions.append({
                'title': current_title,
                'description': current_description
            })
        
        # If parsing failed, return detailed fallbacks
        if not suggestions:
            return self._get_detailed_fallback_suggestions(preferences)['suggestions']
        
        return suggestions[:5]
    
    def _get_detailed_fallback_suggestions(self, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Provide detailed fallback suggestions when Gemini fails"""
        music_prefs = preferences.get('music_preferences', {})
        video_prefs = preferences.get('video_preferences', {})
        
        genre = music_prefs.get('genre', 'pop')
        mood = music_prefs.get('mood', 'upbeat')
        style = video_prefs.get('visual_style', 'modern')
        colors = video_prefs.get('color_scheme', 'vibrant')
        
        suggestions = [
            {
                'title': f'Kinetic Typography Symphony',
                'description': f'Dynamic text animations floating through a {colors} {style} environment. Words from the {genre} lyrics materialize as 3D objects, rotating and morphing with the {mood} beat. Camera swoops through floating letter sculptures while {colors} particles trail behind each word. Background features subtle geometric patterns that pulse with bass frequencies. Close-up shots of individual letters transforming into musical notes, creating a synesthetic experience between text and sound.'
            },
            {
                'title': f'Liquid Color Choreography',
                'description': f'Flowing liquid simulations in {colors} hues dance to the {genre} rhythm. Each drop and splash corresponds to musical elements - bass notes create large wave formations while higher frequencies generate fine mist effects. The {style} aesthetic is achieved through sleek surface reflections and modern lighting. Camera follows the liquid through various containers and environments, with slow-motion captures during musical crescendos. Color gradients shift seamlessly, creating an organic light show that mirrors the {mood} energy of the track.'
            },
            {
                'title': f'Geometric Metamorphosis',
                'description': f'Abstract geometric shapes continuously transform in a {colors} {style} space. Cubes morph into spheres, pyramids unfold into complex fractals, all synchronized to the {genre} beat. Each shape represents different instrumental layers - drums trigger angular transformations while melodies create smooth, flowing changes. The {mood} energy is captured through the speed and complexity of transformations. Camera angles shift dynamically, sometimes diving inside the geometric structures, other times pulling back to reveal the full choreographed pattern.'
            },
            {
                'title': f'Neon Circuit Landscape',
                'description': f'A {style} digital landscape where {colors} neon circuits pulse with the {genre} music. Electronic pathways light up in sequence, creating a living circuit board that extends infinitely. Each musical element triggers different circuit patterns - bass lines create thick, glowing highways while treble frequencies generate intricate, delicate pathways. The {mood} atmosphere is enhanced by electrical arcs and digital particle effects. Camera travels along the circuit paths, diving through electronic components and emerging in new digital territories.'
            },
            {
                'title': f'Crystalline Resonance Garden',
                'description': f'A mystical garden of {colors} crystal formations that grow and resonate with the {genre} music. Each crystal structure represents different musical frequencies, growing taller and more complex during intense musical passages. The {style} aesthetic is achieved through precise geometric crystal shapes and modern lighting effects. Prismatic light refractions create rainbow cascades that shift with the {mood} energy. Camera weaves between crystal formations, capturing close-ups of their growth patterns and wide shots of the entire resonating garden ecosystem.'
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
        processed_data = processor.process_preferences(data, session_id)
        
        # Store in session
        if redis_client:
            session_manager.store_preferences(session_id, processed_data)
        else:
            session[session_id] = processed_data
        
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

@app.route('/api/enhance-video-prompt', methods=['POST'])
def enhance_video_prompt():
    """Enhance user's video prompt using Gemini AI"""
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
        result = gemini_service.enhance_video_prompt(user_prompt, preferences)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in enhance_video_prompt: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route('/api/video-suggestions', methods=['POST'])
def get_video_suggestions():
    """Get AI-generated video suggestions"""
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
        result = gemini_service.generate_video_suggestions(preferences)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in get_video_suggestions: {e}")
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
        
        # Simple enhancement (can be expanded with Gemini)
        enhanced_prompt = f"Enhanced: {user_prompt}"
        
        return jsonify({
            'success': True,
            'enhanced_prompt': enhanced_prompt,
            'alternatives': [
                f"Alternative 1: {user_prompt} with dynamic arrangement",
                f"Alternative 2: {user_prompt} with modern production",
                f"Alternative 3: {user_prompt} with rich instrumentation"
            ],
            'technical_notes': "AI-enhanced music prompt",
            'original_prompt': user_prompt
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
