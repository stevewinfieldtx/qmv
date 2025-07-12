import os
import json
import logging
import requests
import time
from typing import Dict, Any, Optional
from google.auth import default
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

class LyriaService:
    """Service for generating 30-second music clips using Google Lyria on Vertex AI"""
    
    def __init__(self):
        self.project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')
        self.location = os.environ.get('VERTEX_AI_LOCATION', 'us-central1')
        self.credentials = None
        self.access_token = None
        
        if not self.project_id:
            logger.warning("GOOGLE_CLOUD_PROJECT not found in environment variables")
            return
            
        try:
            # Get default credentials
            self.credentials, _ = default()
            self._refresh_token()
            logger.info("Lyria service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Lyria service: {e}")
            self.credentials = None
    
    def _refresh_token(self):
        """Refresh the access token"""
        if self.credentials:
            self.credentials.refresh(Request())
            self.access_token = self.credentials.token
    
    def generate_music(self, prompt: str, session_id: str) -> Dict[str, Any]:
        """Generate a 30-second music clip using Lyria"""
        try:
            if not self.credentials or not self.access_token:
                return {
                    'success': False,
                    'error': 'Lyria service not properly configured'
                }
            
            # Refresh token if needed
            if self.credentials.expired:
                self._refresh_token()
            
            # Prepare the request
            url = f"https://{self.location}-aiplatform.googleapis.com/v1/projects/{self.project_id}/locations/{self.location}/publishers/google/models/lyria-2:predict"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Lyria request payload
            payload = {
                "instances": [
                    {
                        "prompt": prompt,
                        "duration": 30,  # 30 seconds
                        "format": "wav"
                    }
                ],
                "parameters": {
                    "temperature": 0.7,
                    "seed": None  # For reproducibility, can be set to a specific value
                }
            }
            
            logger.info(f"Generating music with Lyria for session {session_id}")
            logger.info(f"Prompt: {prompt}")
            
            # Make the request
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            
            if response.status_code == 200:
                result = response.json()
                
                # Extract the audio data from the response
                if 'predictions' in result and len(result['predictions']) > 0:
                    prediction = result['predictions'][0]
                    
                    # The audio data should be in base64 format
                    audio_data = prediction.get('audio_data')
                    if audio_data:
                        return {
                            'success': True,
                            'audio_data': audio_data,
                            'format': 'wav',
                            'duration': 30,
                            'session_id': session_id,
                            'prompt': prompt,
                            'generated_at': time.time()
                        }
                    else:
                        return {
                            'success': False,
                            'error': 'No audio data in response'
                        }
                else:
                    return {
                        'success': False,
                        'error': 'No predictions in response'
                    }
            else:
                error_msg = f"Lyria API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            error_msg = f"Error generating music with Lyria: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def save_audio_file(self, audio_data: str, session_id: str, output_dir: str = "generated_music") -> str:
        """Save base64 audio data to a WAV file"""
        import base64
        
        try:
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename
            filename = f"lyria_music_{session_id}_{int(time.time())}.wav"
            filepath = os.path.join(output_dir, filename)
            
            # Decode and save the audio data
            audio_bytes = base64.b64decode(audio_data)
            with open(filepath, 'wb') as f:
                f.write(audio_bytes)
            
            logger.info(f"Saved Lyria audio file: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error saving audio file: {e}")
            raise
    
    def enhance_prompt_for_lyria(self, user_prompt: str, preferences: Dict[str, Any]) -> str:
        """Enhance user prompt for better Lyria generation"""
        try:
            music_prefs = preferences.get('music_preferences', {})
            
            # Build enhanced prompt
            enhanced_parts = []
            
            # Add genre if specified
            genre = music_prefs.get('genre')
            if genre:
                enhanced_parts.append(f"{genre} music")
            
            # Add mood/energy
            mood = music_prefs.get('mood')
            if mood:
                enhanced_parts.append(f"{mood} mood")
            
            # Add tempo
            tempo = music_prefs.get('tempo')
            if tempo:
                enhanced_parts.append(f"{tempo} tempo")
            
            # Add instruments if specified
            instruments = music_prefs.get('instruments')
            if instruments:
                if isinstance(instruments, list):
                    instruments_str = ', '.join(instruments)
                else:
                    instruments_str = str(instruments)
                enhanced_parts.append(f"featuring {instruments_str}")
            
            # Combine with user prompt
            if enhanced_parts:
                if user_prompt:
                    enhanced_prompt = f"{user_prompt}, {', '.join(enhanced_parts)}"
                else:
                    enhanced_prompt = ', '.join(enhanced_parts)
            else:
                enhanced_prompt = user_prompt or "instrumental music"
            
            # Ensure it's suitable for Lyria (instrumental only)
            if "vocal" in enhanced_prompt.lower() or "singing" in enhanced_prompt.lower():
                enhanced_prompt = enhanced_prompt.replace("vocal", "instrumental")
                enhanced_prompt = enhanced_prompt.replace("singing", "melodic")
            
            # Add instrumental specification if not present
            if "instrumental" not in enhanced_prompt.lower():
                enhanced_prompt += ", instrumental"
            
            logger.info(f"Enhanced prompt for Lyria: {enhanced_prompt}")
            return enhanced_prompt
            
        except Exception as e:
            logger.error(f"Error enhancing prompt: {e}")
            return user_prompt or "instrumental music"