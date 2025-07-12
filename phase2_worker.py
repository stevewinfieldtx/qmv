import os
import redis
import json
import time
import logging
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List
import uuid
from celery_app import celery_app

# Optional Google Cloud Storage import
try:
    from google.cloud import storage
    GCS_AVAILABLE = True
except ImportError:
    storage = None
    GCS_AVAILABLE = False
    logging.warning("Google Cloud Storage not available - GCS features disabled")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis connection
redis_client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"))

from services.lyria_service import LyriaService

class MusicGenerationService:
    """Unified service for music generation using multiple providers"""
    
    def __init__(self):
        self.use_lyria = os.environ.get('USE_LYRIA', 'true').lower() == 'true'
        self.lyria_service = LyriaService() if self.use_lyria else None
        self.suno_service = SunoService()
        
    def generate_music(self, preferences: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Generate music using the preferred service"""
        try:
            # Try Lyria first if enabled
            if self.use_lyria and self.lyria_service and self.lyria_service.credentials:
                logger.info(f"Using Lyria for music generation for session {session_id}")
                return self._generate_with_lyria(preferences, session_id)
            else:
                # Fallback to Suno
                logger.info(f"Using Suno for music generation for session {session_id}")
                return self.suno_service.generate_music(preferences, session_id)
                
        except Exception as e:
            logger.error(f"Music generation failed: {e}")
            # If Lyria fails, try Suno as backup
            if self.use_lyria:
                logger.info("Lyria failed, trying Suno as backup")
                return self.suno_service.generate_music(preferences, session_id)
            else:
                return {
                    'success': False,
                    'error': f'Music generation failed: {str(e)}'
                }
    
    def _generate_with_lyria(self, preferences: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Generate music using Lyria service"""
        try:
            music_prefs = preferences.get('music_preferences', {})
            
            # Get or create music prompt
            user_prompt = music_prefs.get('music_prompt', '')
            
            # Enhance prompt for Lyria
            enhanced_prompt = self.lyria_service.enhance_prompt_for_lyria(user_prompt, preferences)
            
            # Generate music with Lyria
            result = self.lyria_service.generate_music(enhanced_prompt, session_id)
            
            if result['success']:
                # Save the audio file
                audio_file_path = self.lyria_service.save_audio_file(
                    result['audio_data'], 
                    session_id
                )
                
                # Return result in expected format
                return {
                    'success': True,
                    'music_url': audio_file_path,
                    'audio_file_path': audio_file_path,
                    'duration': 30,
                    'format': 'wav',
                    'service': 'lyria',
                    'prompt': enhanced_prompt,
                    'session_id': session_id
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Lyria generation failed: {e}")
            return {
                'success': False,
                'error': f'Lyria generation failed: {str(e)}'
            }

class SunoService:
    """Service for generating music using Suno API"""

    def __init__(self):
        self.api_key = os.environ.get("APIBOX_KEY")
        self.base_url = os.environ.get("SUNO_BASE_URL", "https://api.sunoapi.org")
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
            )

    def create_music_tags(self, preferences: Dict[str, Any]) -> str:
        """Create music tags based on user preferences"""
        music_prefs = preferences.get("music_preferences", {})

        # Build tags from preferences
        tags = []

        # Add genre
        if music_prefs.get("genre"):
            tags.append(music_prefs["genre"])

        # Add mood
        if music_prefs.get("mood"):
            tags.append(music_prefs["mood"])

        # Add tempo description
        tempo = music_prefs.get("tempo", "medium")
        tempo_tags = {
            "slow": "slow tempo, relaxed",
            "medium": "medium tempo, steady",
            "fast": "fast tempo, energetic",
            "very_fast": "very fast tempo, intense",
        }
        if tempo in tempo_tags:
            tags.append(tempo_tags[tempo])

        # Add energy level
        energy = music_prefs.get("energy_level", "medium")
        if energy != "medium":
            tags.append(f"{energy} energy")

        # Add vocal style
        vocal_style = music_prefs.get("vocal_style", "none")
        if vocal_style == "none":
            tags.append("instrumental")
        else:
            tags.append(f"{vocal_style} vocals")

        # Join tags with commas
        return ", ".join(tags)

    def poll_for_results(
        self, task_id: str, max_attempts: int = 30, delay: int = 10
    ) -> List[Dict[str, Any]]:
        """Poll Suno API for task results"""
        import time

        for attempt in range(max_attempts):
            try:
                logger.info(
                    f"Polling attempt {attempt + 1}/{max_attempts} for task {task_id}"
                )

                # Check task status
                response = self.session.get(
                    f"{self.base_url}/api/v1/generate/record-info?taskId={task_id}"
                )
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Poll response: {result}")

                    if result.get("code") == 200 and "data" in result:
                        clips = result["data"]
                        if clips and len(clips) > 0:
                            # Check if songs are ready
                            ready_songs = [
                                song for song in clips if song.get("audio_url")
                            ]
                            if ready_songs:
                                logger.info(f"Found {len(ready_songs)} ready songs")
                                return ready_songs

                    logger.info(f"Songs not ready yet, waiting {delay} seconds...")
                    time.sleep(delay)
                else:
                    logger.warning(
                        f"Poll request failed: {response.status_code} - {response.text}"
                    )
                    time.sleep(delay)

            except Exception as e:
                logger.error(f"Error polling for results: {e}")
                time.sleep(delay)

        logger.warning(f"Polling timeout after {max_attempts} attempts")
        return []

    def check_callback_results(
        self, task_id: str, timeout: int = 300
    ) -> List[Dict[str, Any]]:
        """Check for callback results before polling"""
        import time

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Check if callback data is available
                callback_key = f"suno_callback:{task_id}"
                callback_data = redis_client.get(callback_key)

                if callback_data:
                    data = json.loads(callback_data)
                    logger.info(f"Found callback data for task {task_id}: {data}")

                    if data.get("status") == "complete":
                        # Get the actual song data using the task ID
                        response = self.session.get(
                            f"{self.base_url}/api/v1/generate/record-info?taskId={task_id}"
                        )
                        if response.status_code == 200:
                            result = response.json()
                            if result.get("code") == 200 and "data" in result:
                                clips = result["data"]
                                if clips and len(clips) > 0:
                                    ready_songs = [
                                        song for song in clips if song.get("audio_url")
                                    ]
                                    if ready_songs:
                                        logger.info(
                                            f"Retrieved {len(ready_songs)} songs from callback"
                                        )
                                        return ready_songs

                time.sleep(5)  # Check every 5 seconds

            except Exception as e:
                logger.error(f"Error checking callback: {e}")
                time.sleep(5)

        logger.warning(
            f"No callback received for task {task_id} within {timeout} seconds"
        )
        return []

    def generate_music(
        self, preferences: Dict[str, Any], session_id: str
    ) -> Dict[str, Any]:
        """Generate music using Suno API"""
        try:
            if not self.api_key:
                return {"success": False, "error": "APIBOX_KEY not configured"}

            music_prefs = preferences.get("music_preferences", {})
            general_prefs = preferences.get("general_preferences", {})

            # Create tags from preferences
            tags = self.create_music_tags(preferences)

            # Get music prompt or create one
            music_prompt = music_prefs.get("music_prompt", "")
            if not music_prompt:
                music_prompt = f"Create a {music_prefs.get('genre', 'pop')} song with {music_prefs.get('mood', 'upbeat')} mood"

            # Prepare Suno API request
            suno_request = {
                "prompt": music_prompt,
                "tags": tags,
                "title": general_prefs.get("project_name", "Untitled"),
                "instrumental": music_prefs.get("vocal_style", "none") == "none",
                "wait_audio": False,  # Changed to False to use callback
                "customMode": False,
                "model": "V4_5",
                "callBackUrl": f"https://{os.environ.get('RAILWAY_PUBLIC_DOMAIN')}/api/suno/callback",
            }

            logger.info(f"Generating music for session {session_id} with tags: {tags}")
            logger.info(f"Suno API request: {suno_request}")

            # Make request to Suno API
            response = self.session.post(
                f"{self.base_url}/api/v1/generate", json=suno_request, timeout=120
            )

            logger.info(f"Suno API response status: {response.status_code}")
            logger.info(f"Suno API response text: {response.text[:500]}...")

            if response.status_code == 200:
                try:
                    suno_response = response.json()
                    logger.info(f"Suno API response JSON: {suno_response}")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    logger.error(f"Response content: {response.text}")
                    return {
                        "success": False,
                        "error": f"Invalid JSON response: {response.text[:200]}",
                    }

                # Check if we got a taskId (async response)
                if "data" in suno_response and "taskId" in suno_response["data"]:
                    task_id = suno_response["data"]["taskId"]
                    logger.info(f"Got taskId: {taskId}, waiting for callback...")

                    # First check for callback results (preferred method)
                    songs = self.check_callback_results(task_id, timeout=300)

                    # If no callback received, fall back to polling
                    if not songs:
                        logger.info("No callback received, falling back to polling...")
                        songs = self.poll_for_results(task_id)

                    logger.info(f"Found {len(songs)} songs total")
                else:
                    # Direct response with clips
                    songs = suno_response.get("clips", [])
                    logger.info(f"Found {len(songs)} songs in direct response")

                results = []
                for i, song in enumerate(songs[:2]):  # Ensure we only take 2
                    song_data = {
                        "song_id": song.get("id"),
                        "title": song.get("title", f"Song {i+1}"),
                        "audio_url": song.get("audio_url"),
                        "duration": song.get("duration"),
                        "tags": song.get("tags", tags),
                        "prompt": song.get("prompt", music_prompt),
                        "status": song.get("status", "complete"),
                        "created_at": song.get(
                            "created_at", datetime.utcnow().isoformat()
                        ),
                        "metadata": {
                            "bpm": song.get("bpm"),
                            "key": song.get("key"),
                            "genre": music_prefs.get("genre"),
                            "mood": music_prefs.get("mood"),
                            "tempo": music_prefs.get("tempo"),
                        },
                    }
                    results.append(song_data)

                return {
                    "success": True,
                    "songs": results,
                    "generation_id": suno_response.get("id"),
                    "session_id": session_id,
                    "tags_used": tags,
                }
            else:
                logger.error(
                    f"Suno API error: {response.status_code} - {response.text}"
                )
                return {
                    "success": False,
                    "error": f"Suno API error: {response.status_code} - {response.text}",
                }

        except Exception as e:
            logger.error(f"Error generating music: {e}")
            return {"success": False, "error": str(e)}


class GCSService:
    """Service for storing files in Google Cloud Storage"""

    def __init__(self):
        self.bucket_name = os.environ.get("GCS_BUCKET_NAME")
        if self.bucket_name and GCS_AVAILABLE:
            try:
                # Check if we have JSON credentials in environment
                creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
                if creds_json:
                    import json
                    from google.oauth2 import service_account

                    # Parse JSON credentials from environment variable
                    credentials_info = json.loads(creds_json)
                    credentials = service_account.Credentials.from_service_account_info(
                        credentials_info
                    )
                    self.client = storage.Client(credentials=credentials)
                    logger.info("GCS initialized with service account credentials")
                else:
                    # Fallback to default credentials
                    self.client = storage.Client()
                    logger.info("GCS initialized with default credentials")

                self.bucket = self.client.bucket(self.bucket_name)
                logger.info(f"GCS bucket '{self.bucket_name}' connected successfully")
            except Exception as e:
                logger.error(f"GCS initialization failed: {e}")
                self.client = None
                self.bucket = None
        else:
            if not GCS_AVAILABLE:
                logger.warning("Google Cloud Storage not available")
            else:
                logger.warning("GCS_BUCKET_NAME not configured")
            self.client = None
            self.bucket = None

    def upload_audio_file(
        self, audio_url: str, session_id: str, song_index: int, song_id: str
    ) -> Dict[str, Any]:
        """Download audio from Suno URL and upload to GCS"""
        try:
            if not self.bucket:
                return {"success": False, "error": "GCS not configured"}

            # Download audio from Suno URL
            response = requests.get(audio_url, stream=True, timeout=120)
            response.raise_for_status()

            # Generate unique filename
            filename = f"music/{session_id}/song_{song_index}_{song_id}.mp3"

            # Upload to GCS
            blob = self.bucket.blob(filename)
            blob.upload_from_string(response.content, content_type="audio/mpeg")

            # Make blob publicly accessible
            blob.make_public()

            return {
                "success": True,
                "gcs_path": f"gs://{self.bucket_name}/{filename}",
                "public_url": blob.public_url,
                "filename": filename,
                "file_size": len(response.content),
            }

        except Exception as e:
            logger.error(f"Error uploading to GCS: {e}")
            return {"success": False, "error": str(e)}

    def store_song_metadata(
        self, session_id: str, song_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Store song metadata as JSON in GCS"""
        try:
            if not self.bucket:
                return {"success": False, "error": "GCS not configured"}

            filename = (
                f"metadata/{session_id}/song_{song_data['song_id']}_metadata.json"
            )

            blob = self.bucket.blob(filename)
            blob.upload_from_string(
                json.dumps(song_data, indent=2), content_type="application/json"
            )

            return {
                "success": True,
                "metadata_path": f"gs://{self.bucket_name}/{filename}",
                "filename": filename,
            }

        except Exception as e:
            logger.error(f"Error storing metadata: {e}")
            return {"success": False, "error": str(e)}


# Initialize services
suno_service = SunoService()
gcs_service = GCSService()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_music_generation(self, session_id: str):
    """Celery task to process music generation (Phase 2)"""
    try:
        logger.info(f"Starting music generation for session {session_id}")

        # Get preferences from Redis
        preferences_key = f"preferences:{session_id}"
        preferences_data = redis_client.get(preferences_key)

        if not preferences_data:
            logger.error(f"No preferences found for session {session_id}")
            return {"success": False, "error": "Preferences not found"}

        preferences = json.loads(preferences_data)

        # Update status to processing
        status_key = f"phase2_status:{session_id}"
        redis_client.setex(
            status_key,
            3600,
            json.dumps(
                {
                    "status": "processing",
                    "phase": 2,
                    "message": "Generating music with Suno AI...",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
        )

        # Generate music with Suno
        music_result = suno_service.generate_music(preferences, session_id)

        if not music_result["success"]:
            # Update status to failed
            redis_client.setex(
                status_key,
                3600,
                json.dumps(
                    {
                        "status": "failed",
                        "phase": 2,
                        "error": music_result["error"],
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
            )
            return music_result

        # Update status to storing
        redis_client.setex(
            status_key,
            3600,
            json.dumps(
                {
                    "status": "storing",
                    "phase": 2,
                    "message": "Storing songs in Google Cloud Storage...",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
        )

        # Store songs in GCS
        stored_songs = []
        for i, song in enumerate(music_result["songs"]):
            # Upload audio file
            gcs_result = gcs_service.upload_audio_file(
                song["audio_url"], session_id, i + 1, song["song_id"]
            )

            if gcs_result["success"]:
                # Update song data with GCS info
                song["gcs_path"] = gcs_result["gcs_path"]
                song["public_url"] = gcs_result["public_url"]
                song["filename"] = gcs_result["filename"]
                song["file_size"] = gcs_result["file_size"]

                # Store metadata
                metadata_result = gcs_service.store_song_metadata(session_id, song)
                if metadata_result["success"]:
                    song["metadata_path"] = metadata_result["metadata_path"]

                stored_songs.append(song)
                logger.info(
                    f"Stored song {i+1} ({song['duration']}s) for session {session_id}"
                )
            else:
                logger.warning(
                    f"Failed to store song {i+1} in GCS: {gcs_result['error']}"
                )
                # Still add the song with Suno URL as fallback
                stored_songs.append(song)

        # Store final results in Redis
        results_key = f"phase2_results:{session_id}"
        final_results = {
            "success": True,
            "session_id": session_id,
            "songs": stored_songs,
            "total_songs": len(stored_songs),
            "generation_id": music_result.get("generation_id"),
            "tags_used": music_result.get("tags_used"),
            "completed_at": datetime.utcnow().isoformat(),
            "phase": 2,
        }

        redis_client.setex(
            results_key, 86400, json.dumps(final_results)
        )  # Store for 24 hours

        # Update status to completed
        redis_client.setex(
            status_key,
            3600,
            json.dumps(
                {
                    "status": "completed",
                    "phase": 2,
                    "message": f"Successfully generated and stored {len(stored_songs)} songs",
                    "songs_count": len(stored_songs),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
        )

        # Store Phase 2 results for Phase 3
        redis_client.hset(
            f"session:{session_id}",
            "phase2_results",
            json.dumps(final_results)
        )

        # Trigger Phase 3 (video generation)
        from phase3_worker import process_video_generation
        process_video_generation.delay(session_id)

        logger.info(f"Phase 2 completed for session {session_id}")
        return final_results

    except Exception as e:
        logger.error(f"Error in music generation task: {e}")
        
        # Update status to failed
        status_key = f"phase2_status:{session_id}"
        redis_client.setex(
            status_key,
            3600,
            json.dumps(
                {
                    "status": "failed",
                    "phase": 2,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
        )
        
        # Retry the task
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying task in {self.default_retry_delay} seconds...")
            raise self.retry(countdown=self.default_retry_delay)
        
        return {"success": False, "error": str(e)}