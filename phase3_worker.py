import asyncio
import os
import json
import logging
from typing import List, Dict, Any
from celery import Celery
import redis
from runware import Runware, IImageInference
from services.gemini_service import GeminiService
from utils.session_manager import SessionManager
from google.cloud import storage
import requests
import tempfile
from moviepy.editor import ImageSequenceClip, AudioFileClip, CompositeVideoClip
import librosa
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery('phase3_worker')
celery_app.config_from_object('celery_app')

# Initialize services
redis_client = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))
session_manager = SessionManager()
gemini_service = GeminiService()
gcs_client = storage.Client()
bucket_name = os.getenv('GCS_BUCKET_NAME', 'qmv-storage')
bucket = gcs_client.bucket(bucket_name)

class RunwareService:
    def __init__(self):
        self.api_key = os.getenv('RUNWARE_API_KEY')
        if not self.api_key:
            raise ValueError("RUNWARE_API_KEY environment variable is required")
        self.runware = None
    
    async def connect(self):
        """Establish connection to Runware API"""
        self.runware = Runware(api_key=self.api_key)
        await self.runware.connect()
        logger.info("Connected to Runware API")
    
    async def disconnect(self):
        """Disconnect from Runware API"""
        if self.runware:
            await self.runware.disconnect()
            logger.info("Disconnected from Runware API")
    
    async def generate_image(self, prompt: str, width: int = 1024, height: int = 1024) -> str:
        """Generate a single image using Runware API"""
        try:
            request = IImageInference(
                positivePrompt=prompt,
                model="runware:100@1",  # Using the model specified by user
                width=width,
                height=height
            )
            
            images = await self.runware.imageInference(requestImage=request)
            if images and len(images) > 0:
                return images[0].imageURL
            else:
                raise Exception("No images generated")
                
        except Exception as e:
            logger.error(f"Error generating image with prompt '{prompt}': {str(e)}")
            raise
    
    async def generate_images_batch(self, prompts: List[str], width: int = 1024, height: int = 1024) -> List[str]:
        """Generate multiple images concurrently"""
        tasks = []
        for prompt in prompts:
            task = self.generate_image(prompt, width, height)
            tasks.append(task)
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            image_urls = []
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to generate image {i}: {str(result)}")
                    # Use a placeholder or retry logic here
                    image_urls.append(None)
                else:
                    image_urls.append(result)
            
            return image_urls
        except Exception as e:
            logger.error(f"Batch image generation failed: {str(e)}")
            raise

class AudioAnalyzer:
    @staticmethod
    def analyze_audio(audio_file_path: str) -> Dict[str, Any]:
        """Analyze audio file to extract beats and timing information"""
        try:
            # Load audio file
            y, sr = librosa.load(audio_file_path)
            
            # Get tempo and beat frames
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            
            # Convert beat frames to time
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)
            
            # Get duration
            duration = librosa.get_duration(y=y, sr=sr)
            
            return {
                'tempo': float(tempo),
                'beat_times': beat_times.tolist(),
                'duration': float(duration),
                'total_beats': len(beat_times),
                'sample_rate': sr
            }
        except Exception as e:
            logger.error(f"Audio analysis failed: {str(e)}")
            raise

class VideoCreator:
    @staticmethod
    def create_video(image_urls: List[str], audio_file_path: str, beat_times: List[float], output_path: str) -> str:
        """Create video by combining images and audio timed to beats"""
        try:
            # Download images to temporary files
            temp_image_files = []
            for i, url in enumerate(image_urls):
                if url:  # Skip None URLs
                    response = requests.get(url)
                    if response.status_code == 200:
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'_img_{i}.jpg')
                        temp_file.write(response.content)
                        temp_file.close()
                        temp_image_files.append(temp_file.name)
                    else:
                        logger.warning(f"Failed to download image {i} from {url}")
            
            if not temp_image_files:
                raise Exception("No valid images to create video")
            
            # Calculate duration for each image based on beats
            if len(beat_times) > 1:
                # Calculate average time between beats
                beat_intervals = [beat_times[i+1] - beat_times[i] for i in range(len(beat_times)-1)]
                avg_beat_interval = sum(beat_intervals) / len(beat_intervals)
                
                # Determine how many beats per image
                beats_per_image = max(1, len(beat_times) // len(temp_image_files))
                image_duration = avg_beat_interval * beats_per_image
            else:
                # Fallback: equal duration for all images
                audio_clip = AudioFileClip(audio_file_path)
                image_duration = audio_clip.duration / len(temp_image_files)
                audio_clip.close()
            
            # Create video from images
            video_clip = ImageSequenceClip(temp_image_files, durations=[image_duration] * len(temp_image_files))
            
            # Load audio
            audio_clip = AudioFileClip(audio_file_path)
            
            # Combine video and audio
            final_video = video_clip.set_audio(audio_clip)
            
            # Write video file
            final_video.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac')
            
            # Cleanup
            video_clip.close()
            audio_clip.close()
            final_video.close()
            
            # Remove temporary image files
            for temp_file in temp_image_files:
                try:
                    os.unlink(temp_file)
                except:
                    pass
            
            return output_path
            
        except Exception as e:
            logger.error(f"Video creation failed: {str(e)}")
            raise

@celery_app.task(bind=True, name='phase3_worker.process_video_generation')
def process_video_generation(self, session_id: str):
    """Phase 3: Generate video from music and preferences"""
    try:
        logger.info(f"Starting Phase 3 video generation for session {session_id}")
        
        # Update status
        redis_client.hset(f"session:{session_id}", "phase3_status", "processing")
        redis_client.hset(f"session:{session_id}", "phase3_progress", "0")
        
        # Get session data
        preferences = session_manager.get_preferences(session_id)
        if not preferences:
            raise Exception("No preferences found for session")
        
        # Get Phase 2 results (music files)
        phase2_results = redis_client.hget(f"session:{session_id}", "phase2_results")
        if not phase2_results:
            raise Exception("No Phase 2 results found")
        
        phase2_data = json.loads(phase2_results)
        music_files = phase2_data.get('music_files', [])
        
        if not music_files:
            raise Exception("No music files found from Phase 2")
        
        # Process each generated song
        video_results = []
        
        for i, music_file in enumerate(music_files):
            logger.info(f"Processing video {i+1}/{len(music_files)}")
            
            # Update progress
            progress = int((i / len(music_files)) * 100)
            redis_client.hset(f"session:{session_id}", "phase3_progress", str(progress))
            
            # Download music file from GCS
            blob = bucket.blob(music_file['gcs_path'])
            temp_audio_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            blob.download_to_filename(temp_audio_file.name)
            
            try:
                # Analyze audio
                audio_analysis = AudioAnalyzer.analyze_audio(temp_audio_file.name)
                
                # Calculate number of images needed (one image per 4 beats or minimum 8 images)
                beats_per_image = 4
                num_images = max(8, audio_analysis['total_beats'] // beats_per_image)
                
                # Generate image prompts using Gemini
                video_preferences = preferences.get('video', {})
                base_prompt = video_preferences.get('style', 'cinematic music video')
                
                image_prompts = []
                for j in range(num_images):
                    # Create varied prompts for different scenes
                    scene_prompt = f"{base_prompt}, scene {j+1}, high quality, 4K, professional"
                    if j % 3 == 0:
                        scene_prompt += ", wide shot"
                    elif j % 3 == 1:
                        scene_prompt += ", close-up"
                    else:
                        scene_prompt += ", medium shot"
                    
                    image_prompts.append(scene_prompt)
                
                # Generate images using Runware
                runware_service = RunwareService()
                
                async def generate_images():
                    await runware_service.connect()
                    try:
                        image_urls = await runware_service.generate_images_batch(image_prompts)
                        return image_urls
                    finally:
                        await runware_service.disconnect()
                
                # Run async image generation
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                image_urls = loop.run_until_complete(generate_images())
                loop.close()
                
                # Filter out failed images
                valid_image_urls = [url for url in image_urls if url is not None]
                
                if len(valid_image_urls) < 4:  # Minimum viable images
                    raise Exception(f"Too few images generated: {len(valid_image_urls)}/{num_images}")
                
                # Create video
                video_filename = f"video_{session_id}_{i+1}.mp4"
                temp_video_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4').name
                
                VideoCreator.create_video(
                    valid_image_urls,
                    temp_audio_file.name,
                    audio_analysis['beat_times'],
                    temp_video_path
                )
                
                # Upload video to GCS
                video_blob = bucket.blob(f"videos/{session_id}/{video_filename}")
                video_blob.upload_from_filename(temp_video_path)
                
                video_result = {
                    'video_id': f"video_{i+1}",
                    'gcs_path': f"videos/{session_id}/{video_filename}",
                    'download_url': video_blob.public_url,
                    'duration': audio_analysis['duration'],
                    'images_used': len(valid_image_urls),
                    'tempo': audio_analysis['tempo']
                }
                
                video_results.append(video_result)
                
                # Cleanup temporary files
                os.unlink(temp_video_path)
                
            finally:
                # Cleanup audio file
                os.unlink(temp_audio_file.name)
        
        # Store results
        phase3_results = {
            'videos': video_results,
            'session_id': session_id,
            'generated_at': str(asyncio.get_event_loop().time())
        }
        
        redis_client.hset(f"session:{session_id}", "phase3_results", json.dumps(phase3_results))
        redis_client.hset(f"session:{session_id}", "phase3_status", "completed")
        redis_client.hset(f"session:{session_id}", "phase3_progress", "100")
        
        # Publish completion event
        redis_client.publish('phase3_complete', json.dumps({
            'session_id': session_id,
            'video_count': len(video_results)
        }))
        
        logger.info(f"Phase 3 completed for session {session_id}. Generated {len(video_results)} videos.")
        return phase3_results
        
    except Exception as e:
        logger.error(f"Phase 3 failed for session {session_id}: {str(e)}")
        redis_client.hset(f"session:{session_id}", "phase3_status", "failed")
        redis_client.hset(f"session:{session_id}", "phase3_error", str(e))
        raise

if __name__ == '__main__':
    # For testing
    celery_app.start()