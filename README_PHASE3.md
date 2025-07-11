# Quick Music Video (QMV) - Phase 3 Implementation

## Overview

Phase 3 implements video generation functionality for the Quick Music Video system. This phase takes the music generated in Phase 2 and creates synchronized videos using AI-generated images timed to the beat of the music.

## Architecture

### Phase 3 Workflow

1. **Audio Analysis**: Analyze generated music files to detect beats and timing
2. **Image Generation**: Create AI images using Runware API and Flux.1 Schnell model
3. **Video Creation**: Combine images and music into synchronized videos
4. **Storage**: Upload final videos to Google Cloud Storage

### Key Components

- **`phase3_worker.py`**: Main Celery worker for video generation
- **`RunwareService`**: Interface to Runware AI for image generation
- **`AudioAnalyzer`**: Beat detection and audio analysis using librosa
- **`VideoCreator`**: Video composition using MoviePy

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Required environment variables:

- `RUNWARE_API_KEY`: Your Runware API key
- `GCS_BUCKET_NAME`: Google Cloud Storage bucket name
- `REDIS_URL`: Redis connection URL
- `GEMINI_API_KEY`: Google Gemini API key

### 3. Google Cloud Setup

1. Create a GCS bucket for video storage
2. Set up service account with Storage Admin permissions
3. Download service account key JSON file
4. Set `GOOGLE_APPLICATION_CREDENTIALS` environment variable

### 4. Runware API Setup

1. Sign up at [Runware](https://runware.ai)
2. Get your API key
3. Add to environment variables

### 5. Start Services

```bash
# Start Redis (if not already running)
redis-server

# Start Celery worker
python worker.py

# Start Flask app
python app.py
```

## API Endpoints

### Phase 3 Status

```http
GET /api/phase3/status/<session_id>
```

Returns current video generation status and progress.

### Phase 3 Results

```http
GET /api/phase3/results/<session_id>
```

Returns generated video information and download URLs.

### Complete Session Status

```http
GET /api/session/<session_id>/complete-status
```

Returns status for all phases (1, 2, and 3).

## Testing

### Web Interface

Visit `/test-phase3` for a web interface to:

- Monitor Phase 3 progress
- Check session status across all phases
- View and download generated videos

### Manual Testing

1. Complete Phase 1 (preferences) and Phase 2 (music generation)
2. Get the session ID from Phase 2
3. Use the test interface or API endpoints to monitor Phase 3

## Technical Details

### Audio Analysis

- Uses `librosa` for beat detection and tempo analysis
- Calculates optimal number of images based on song duration and tempo
- Default: 1 image per 4 beats, minimum 8 images

### Image Generation

- Uses Runware API with Flux.1 Schnell model (`runware:100@1`)
- Generates varied prompts for different scenes (wide shot, close-up, medium shot)
- Implements batch processing for efficiency
- Includes error handling and fallback mechanisms

### Video Creation

- Uses `MoviePy` for video composition
- Synchronizes images to beat timing
- Outputs MP4 format with H.264 video and AAC audio
- 24 FPS standard frame rate

### Storage

- Videos stored in Google Cloud Storage
- Organized by session ID: `videos/{session_id}/video_{n}.mp4`
- Public URLs generated for easy access
- Metadata stored alongside videos

## Configuration Options

### Video Settings

```python
# In phase3_worker.py
beats_per_image = 4  # Images per beat
min_images = 8       # Minimum images per video
video_fps = 24       # Frames per second
width = 1024         # Image width
height = 1024        # Image height
```

### Runware Model

```python
# Current model: Flux.1 Schnell
model = "runware:100@1"
```

## Error Handling

- Comprehensive error logging
- Graceful degradation for failed image generation
- Retry mechanisms for API failures
- Status tracking in Redis for monitoring

## Performance Considerations

- Concurrent image generation using asyncio
- Batch processing to minimize API calls
- Temporary file cleanup
- Memory-efficient video processing

## Monitoring

### Redis Keys

- `session:{session_id}:phase3_status` - Current status
- `session:{session_id}:phase3_progress` - Progress percentage
- `session:{session_id}:phase3_results` - Final results
- `session:{session_id}:phase3_error` - Error messages

### Logs

Monitor Celery worker logs for detailed processing information:

```bash
# View worker logs
tail -f celery.log
```

## Troubleshooting

### Common Issues

1. **Runware API Errors**
   - Check API key validity
   - Verify account credits/limits
   - Monitor rate limiting

2. **Audio Analysis Failures**
   - Ensure audio files are accessible
   - Check file format compatibility
   - Verify librosa installation

3. **Video Creation Issues**
   - Check MoviePy dependencies
   - Verify temporary disk space
   - Monitor memory usage

4. **GCS Upload Failures**
   - Verify service account permissions
   - Check bucket configuration
   - Monitor network connectivity

### Debug Mode

Enable debug logging:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

- Support for additional AI image models
- Advanced video effects and transitions
- Custom video templates
- Real-time progress streaming
- Video quality optimization
- Batch video processing

## Dependencies

- `runware`: AI image generation
- `moviepy`: Video processing
- `librosa`: Audio analysis
- `google-cloud-storage`: File storage
- `celery`: Async task processing
- `redis`: Message broker and caching
- `numpy`: Numerical computations
- `soundfile`: Audio file handling

## License

Same as main project license.