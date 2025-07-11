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

class SessionManager:
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

# Import GeminiService from services
from services.gemini_service import GeminiService

# Initialize services
session_manager = SessionManager(redis_client)
validator = PreferenceValidator()
processor = PreferenceProcessor()
gemini_service = GeminiService()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/test-phase3')
def test_phase3():
    return render_template('test_phase3.html')

@app.route('/api/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'redis_connected': redis_client is not None,
        'gemini_configured': gemini_service.model is not None
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
        
        result = gemini_service.enhance_music_prompt(user_prompt, preferences)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in enhance_music_prompt: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route('/api/generate-music/<session_id>', methods=['POST'])
def generate_music_direct(session_id):
    """Direct music generation endpoint (bypasses Redis)"""
    try:
        # Import here to avoid circular imports
        from phase2_worker import SunoService
        
        # Get preferences
        preferences = None
        if redis_client:
            preferences = session_manager.get_preferences(session_id)
        else:
            preferences = session.get(session_id)
        
        if not preferences:
            return jsonify({
                'success': False,
                'error': 'Session not found - please submit preferences first'
            }), 404
        
        # Initialize Suno service and generate music
        suno_service = SunoService()
        result = suno_service.generate_music(preferences, session_id)
        
        # Download and store audio files for customer ownership
        if result.get('success') and result.get('songs'):
            from phase2_worker import GCSService
            gcs_service = GCSService()
            
            for i, song in enumerate(result['songs']):
                if song.get('audio_url'):
                    # Download and store the audio file
                    storage_result = gcs_service.upload_audio_file(
                        song['audio_url'], 
                        session_id, 
                        i, 
                        song['song_id']
                    )
                    
                    if storage_result.get('success'):
                        # Update song data with download info
                        song['download_url'] = storage_result['public_url']
                        song['file_size'] = storage_result['file_size']
                        song['stored_filename'] = storage_result['filename']
                        logger.info(f"Stored song {song['song_id']} for customer download")
                    else:
                        logger.warning(f"Failed to store song {song['song_id']}: {storage_result.get('error')}")
            
            # Store Phase 2 results in Redis for Phase 3
            if redis_client:
                redis_client.hset(f"session:{session_id}", "phase2_results", json.dumps(result))
                logger.info(f"Stored Phase 2 results for session {session_id}")
                
                # Automatically trigger Phase 3 video generation
                try:
                    from phase3_worker import process_video_generation
                    process_video_generation.delay(session_id)
                    logger.info(f"Phase 3 video generation triggered for session {session_id}")
                except Exception as e:
                    logger.error(f"Failed to trigger Phase 3 for session {session_id}: {e}")
        
        # Store results in session if Redis not available
        if not redis_client:
            session[f'music_results_{session_id}'] = result
        
        return jsonify({
            'success': True,
            'result': result,
            'message': 'Music generation completed'
        })
        
    except Exception as e:
        logger.error(f"Error in direct music generation: {e}")
        return jsonify({
            'success': False,
            'error': f'Music generation failed: {str(e)}'
        }), 500

@app.route('/api/phase2/status/<session_id>', methods=['GET'])
def get_phase2_status(session_id):
    """Get Phase 2 (music generation) status"""
    try:
        if not redis_client:
            # Check session storage for music results
            music_results = session.get(f'music_results_{session_id}')
            if music_results:
                return jsonify({
                    'success': True,
                    'status': {
                        'status': 'completed' if music_results.get('success') else 'failed',
                        'phase': 2,
                        'message': 'Music generation completed (no Redis)'
                    }
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Redis not available and no music results found'
                }), 500
        
        status_key = f"phase2_status:{session_id}"
        status_data = redis_client.get(status_key)
        
        if not status_data:
            return jsonify({
                'success': False,
                'error': 'Session not found or expired'
            }), 404
        
        status = json.loads(status_data)
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        logger.error(f"Error getting Phase 2 status: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route('/api/phase2/results/<session_id>', methods=['GET'])
def get_phase2_results(session_id):
    """Get Phase 2 (music generation) results"""
    try:
        if not redis_client:
            return jsonify({
                'success': False,
                'error': 'Redis not available'
            }), 500
        
        results_key = f"phase2_results:{session_id}"
        results_data = redis_client.get(results_key)
        
        if not results_data:
            return jsonify({
                'success': False,
                'error': 'Results not found or expired'
            }), 404
        
        results = json.loads(results_data)
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error getting Phase 2 results: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route('/test-phase2')
def test_phase2():
    return render_template('test_phase2.html')

@app.route('/api/phase3/status/<session_id>', methods=['GET'])
def get_phase3_status(session_id):
    """Get Phase 3 (video generation) status"""
    try:
        if not redis_client:
            return jsonify({
                'success': False,
                'error': 'Redis not available'
            }), 500
        
        # Get status and progress from Redis hash
        session_key = f"session:{session_id}"
        status = redis_client.hget(session_key, "phase3_status")
        progress = redis_client.hget(session_key, "phase3_progress")
        error = redis_client.hget(session_key, "phase3_error")
        
        if not status:
            return jsonify({
                'success': False,
                'error': 'Phase 3 not started or session not found'
            }), 404
        
        response_data = {
            'success': True,
            'status': status.decode('utf-8') if isinstance(status, bytes) else status,
            'progress': int(progress.decode('utf-8')) if progress else 0,
            'phase': 3
        }
        
        if error:
            response_data['error'] = error.decode('utf-8') if isinstance(error, bytes) else error
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error getting Phase 3 status: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route('/api/phase3/results/<session_id>', methods=['GET'])
def get_phase3_results(session_id):
    """Get Phase 3 (video generation) results"""
    try:
        if not redis_client:
            return jsonify({
                'success': False,
                'error': 'Redis not available'
            }), 500
        
        session_key = f"session:{session_id}"
        results_data = redis_client.hget(session_key, "phase3_results")
        
        if not results_data:
            return jsonify({
                'success': False,
                'error': 'Video results not found or not ready'
            }), 404
        
        results = json.loads(results_data.decode('utf-8') if isinstance(results_data, bytes) else results_data)
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error getting Phase 3 results: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route('/api/download/music/<session_id>', methods=['GET'])
def download_music_files(session_id):
    """Provide download links for customer's purchased music"""
    try:
        # Get music results
        music_results = None
        if redis_client:
            results_key = f"phase2_results:{session_id}"
            results_data = redis_client.get(results_key)
            if results_data:
                music_results = json.loads(results_data)
        else:
            music_results = session.get(f'music_results_{session_id}')
        
        if not music_results or not music_results.get('success'):
            return jsonify({
                'success': False,
                'error': 'No music found for this session'
            }), 404
        
        # Extract download information
        downloads = []
        for song in music_results.get('songs', []):
            download_info = {
                'song_id': song['song_id'],
                'title': song['title'],
                'duration': song.get('duration'),
                'file_size': song.get('file_size'),
                'format': 'mp3'
            }
            
            if song.get('download_url'):
                download_info['download_url'] = song['download_url']
            
            downloads.append(download_info)
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'downloads': downloads,
            'total_files': len(downloads)
        })
        
    except Exception as e:
        logger.error(f"Error getting download links: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route('/api/session/<session_id>/complete-status', methods=['GET'])
def get_complete_session_status(session_id):
    """Get complete status for all phases of a session"""
    try:
        if not redis_client:
            return jsonify({
                'success': False,
                'error': 'Redis not available'
            }), 500
        
        # Check if preferences exist (Phase 1)
        preferences = session_manager.get_preferences(session_id)
        phase1_complete = preferences is not None
        
        # Get Phase 2 status
        phase2_status_key = f"phase2_status:{session_id}"
        phase2_status_data = redis_client.get(phase2_status_key)
        phase2_status = json.loads(phase2_status_data) if phase2_status_data else None
        
        # Get Phase 3 status
        session_key = f"session:{session_id}"
        phase3_status = redis_client.hget(session_key, "phase3_status")
        phase3_progress = redis_client.hget(session_key, "phase3_progress")
        
        response = {
            'success': True,
            'session_id': session_id,
            'phase1': {
                'completed': phase1_complete,
                'status': 'completed' if phase1_complete else 'not_started'
            },
            'phase2': phase2_status or {
                'status': 'not_started',
                'phase': 2
            },
            'phase3': {
                'status': phase3_status.decode('utf-8') if phase3_status else 'not_started',
                'progress': int(phase3_progress.decode('utf-8')) if phase3_progress else 0,
                'phase': 3
            }
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting complete session status: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
