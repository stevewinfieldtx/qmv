import validators
from typing import Dict, Any, List

class PreferenceValidator:
    """Validate user input preferences"""
    
    def __init__(self):
        self.valid_genres = [
            'pop', 'rock', 'electronic', 'hip-hop', 'jazz', 'classical',
            'country', 'folk', 'reggae', 'blues', 'funk', 'lofi', 'ambient'
        ]
        
        self.valid_moods = [
            'upbeat', 'relaxed', 'energetic', 'melancholic', 'happy',
            'sad', 'angry', 'peaceful', 'dramatic', 'mysterious', 'romantic'
        ]
        
        self.valid_tempos = ['slow', 'medium', 'fast', 'very_fast']
        
        self.valid_visual_styles = [
            'modern', 'vintage', 'minimal', 'bold', 'abstract',
            'realistic', 'cartoon', 'futuristic', 'retro'
        ]
        
        self.valid_color_schemes = [
            'vibrant', 'pastel', 'dark', 'monochrome', 'neon',
            'warm', 'cool', 'earth_tones', 'rainbow'
        ]
        
        self.valid_resolutions = ['720p', '1080p', '4k']
        self.valid_aspect_ratios = ['16:9', '9:16', '1:1', '4:3']
    
    def validate_preferences(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate all user preferences"""
        errors = []
        
        # Validate required fields
        if not data:
            errors.append("No data provided")
            return {'valid': False, 'errors': errors}
        
        # Validate music preferences
        errors.extend(self._validate_music_preferences(data))
        
        # Validate video preferences
        errors.extend(self._validate_video_preferences(data))
        
        # Validate general preferences
        errors.extend(self._validate_general_preferences(data))
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _validate_music_preferences(self, data: Dict[str, Any]) -> List[str]:
        """Validate music-related preferences"""
        errors = []
        
        # Genre validation
        genre = data.get('genre')
        if genre and genre not in self.valid_genres:
            errors.append(f"Invalid genre: {genre}")
        
        # Mood validation
        mood = data.get('mood')
        if mood and mood not in self.valid_moods:
            errors.append(f"Invalid mood: {mood}")
        
        # Tempo validation
        tempo = data.get('tempo')
        if tempo and tempo not in self.valid_tempos:
            errors.append(f"Invalid tempo: {tempo}")
        
        # Duration validation
        duration = data.get('duration')
        if duration:
            try:
                duration = int(duration)
                if duration < 10 or duration > 300:
                    errors.append("Duration must be between 10 and 300 seconds")
            except (ValueError, TypeError):
                errors.append("Duration must be a valid number")
        
        # Instruments validation
        instruments = data.get('instruments', [])
        if instruments and not isinstance(instruments, list):
            errors.append("Instruments must be a list")
        
        return errors
    
    def _validate_video_preferences(self, data: Dict[str, Any]) -> List[str]:
        """Validate video-related preferences"""
        errors = []
        
        # Visual style validation
        visual_style = data.get('visual_style')
        if visual_style and visual_style not in self.valid_visual_styles:
            errors.append(f"Invalid visual style: {visual_style}")
        
        # Color scheme validation
        color_scheme = data.get('color_scheme')
        if color_scheme and color_scheme not in self.valid_color_schemes:
            errors.append(f"Invalid color scheme: {color_scheme}")
        
        # Resolution validation
        resolution = data.get('resolution')
        if resolution and resolution not in self.valid_resolutions:
            errors.append(f"Invalid resolution: {resolution}")
        
        # Aspect ratio validation
        aspect_ratio = data.get('aspect_ratio')
        if aspect_ratio and aspect_ratio not in self.valid_aspect_ratios:
            errors.append(f"Invalid aspect ratio: {aspect_ratio}")
        
        return errors
    
    def _validate_general_preferences(self, data: Dict[str, Any]) -> List[str]:
        """Validate general preferences"""
        errors = []
        
        # Project name validation
        project_name = data.get('project_name', '')
        if project_name and len(project_name) > 100:
            errors.append("Project name must be less than 100 characters")
        
        # Description validation
        description = data.get('description', '')
        if description and len(description) > 500:
            errors.append("Description must be less than 500 characters")
        
        return errors
