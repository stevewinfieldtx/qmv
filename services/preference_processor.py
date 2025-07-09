import json
from datetime import datetime
from typing import Dict, Any, List

class PreferenceProcessor:
    """Process and structure user preferences for music and video generation"""
    
    def __init__(self):
        self.presets = self._load_presets()
    
    def process_preferences(self, raw_data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Process raw user input into structured preferences"""
        
        processed = {
            'session_id': session_id,
            'timestamp': datetime.utcnow().isoformat(),
            'music_preferences': self._process_music_preferences(raw_data),
            'video_preferences': self._process_video_preferences(raw_data),
            'general_preferences': self._process_general_preferences(raw_data),
            'suno_parameters': self._generate_suno_parameters(raw_data),
            'runware_parameters': self._generate_runware_parameters(raw_data)
        }
        
        return processed
    
    def _process_music_preferences(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process music-related preferences"""
        return {
            'genre': data.get('genre', 'pop'),
            'mood': data.get('mood', 'upbeat'),
            'tempo': data.get('tempo', 'medium'),
            'duration': int(data.get('duration', 60)),
            'instruments': data.get('instruments', []),
            'vocal_style': data.get('vocal_style', 'none'),
            'lyrics_theme': data.get('lyrics_theme', ''),
            'energy_level': data.get('energy_level', 'medium')
        }
    
    def _process_video_preferences(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process video-related preferences"""
        return {
            'visual_style': data.get('visual_style', 'modern'),
            'color_scheme': data.get('color_scheme', 'vibrant'),
            'animation_style': data.get('animation_style', 'smooth'),
            'themes': data.get('themes', []),
            'aspect_ratio': data.get('aspect_ratio', '16:9'),
            'resolution': data.get('resolution', '1080p'),
            'effects': data.get('effects', []),
            'transition_style': data.get('transition_style', 'fade')
        }
    
    def _process_general_preferences(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process general preferences"""
        return {
            'project_name': data.get('project_name', ''),
            'description': data.get('description', ''),
            'target_audience': data.get('target_audience', 'general'),
            'usage_purpose': data.get('usage_purpose', 'personal'),
            'quality_priority': data.get('quality_priority', 'balanced')
        }
    
    def _generate_suno_parameters(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate parameters for Suno API"""
        genre = data.get('genre', 'pop')
        mood = data.get('mood', 'upbeat')
        tempo = data.get('tempo', 'medium')
        
        # Map user-friendly terms to Suno parameters
        tempo_mapping = {
            'slow': '60-80',
            'medium': '80-120',
            'fast': '120-160',
            'very_fast': '160+'
        }
        
        return {
            'genre': genre,
            'mood': mood,
            'tempo': tempo_mapping.get(tempo, '80-120'),
            'duration': data.get('duration', 60),
            'style': f"{genre} {mood}",
            'prompt': self._generate_music_prompt(data),
            'vocal_style': data.get('vocal_style', 'instrumental')
        }
    
    def _generate_runware_parameters(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate parameters for Runware API"""
        return {
            'style': data.get('visual_style', 'modern'),
            'color_palette': data.get('color_scheme', 'vibrant'),
            'animation_type': data.get('animation_style', 'smooth'),
            'themes': data.get('themes', []),
            'resolution': data.get('resolution', '1080p'),
            'fps': 30,
            'duration': data.get('duration', 60),
            'prompt': self._generate_video_prompt(data)
        }
    
    def _generate_music_prompt(self, data: Dict[str, Any]) -> str:
        """Generate a descriptive prompt for music generation"""
        genre = data.get('genre', 'pop')
        mood = data.get('mood', 'upbeat')
        tempo = data.get('tempo', 'medium')
        energy = data.get('energy_level', 'medium')
        
        prompt = f"Create a {tempo} tempo {genre} track with a {mood} mood and {energy} energy level"
        
        if data.get('instruments'):
            instruments = ', '.join(data['instruments'])
            prompt += f", featuring {instruments}"
        
        if data.get('lyrics_theme'):
            prompt += f", with lyrics about {data['lyrics_theme']}"
        
        return prompt
    
    def _generate_video_prompt(self, data: Dict[str, Any]) -> str:
        """Generate a descriptive prompt for video generation"""
        style = data.get('visual_style', 'modern')
        colors = data.get('color_scheme', 'vibrant')
        
        prompt = f"Create a {style} visual style video with {colors} colors"
        
        if data.get('themes'):
            themes = ', '.join(data['themes'])
            prompt += f", incorporating themes of {themes}"
        
        return prompt
    
    def _load_presets(self) -> Dict[str, Any]:
        """Load preset configurations"""
        return {
            'energetic_pop': {
                'genre': 'pop',
                'mood': 'upbeat',
                'tempo': 'fast',
                'energy_level': 'high',
                'visual_style': 'modern',
                'color_scheme': 'vibrant',
                'animation_style': 'dynamic'
            },
            'chill_lofi': {
                'genre': 'lofi',
                'mood': 'relaxed',
                'tempo': 'slow',
                'energy_level': 'low',
                'visual_style': 'minimal',
                'color_scheme': 'pastel',
                'animation_style': 'smooth'
            },
            'rock_anthem': {
                'genre': 'rock',
                'mood': 'powerful',
                'tempo': 'fast',
                'energy_level': 'high',
                'visual_style': 'bold',
                'color_scheme': 'dark',
                'animation_style': 'intense'
            },
            'ambient_electronic': {
                'genre': 'electronic',
                'mood': 'atmospheric',
                'tempo': 'medium',
                'energy_level': 'medium',
                'visual_style': 'futuristic',
                'color_scheme': 'neon',
                'animation_style': 'flowing'
            }
        }
    
    def get_presets(self) -> Dict[str, Any]:
        """Return available presets"""
        return self.presets
