import google.generativeai as genai
import os
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class GeminiService:
    """Service for interacting with Google Gemini AI for prompt enhancement and suggestions"""
    
    def __init__(self):
        self.api_key = os.environ.get('GEMINI_API_KEY')
        if not self.api_key:
            logger.error("GEMINI_API_KEY not found in environment variables")
            return
            
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        
    def enhance_video_prompt(self, user_input: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance user's video prompt with AI suggestions"""
        try:
            if not self.api_key:
                return {'success': False, 'error': 'Gemini API not configured'}
                
            # Create context from user preferences
            context = self._build_context(preferences)
            
            prompt = f"""
            You are a creative video prompt expert. Help enhance this video description for AI video generation.
            
            User's current input: "{user_input}"
            
            Context from their preferences:
            - Genre: {preferences.get('music_preferences', {}).get('genre', 'Not specified')}
            - Mood: {preferences.get('music_preferences', {}).get('mood', 'Not specified')}
            - Visual Style: {preferences.get('video_preferences', {}).get('visual_style', 'Not specified')}
            - Color Scheme: {preferences.get('video_preferences', {}).get('color_scheme', 'Not specified')}
            - Themes: {', '.join(preferences.get('video_preferences', {}).get('themes', []))}
            
            Please provide:
            1. An enhanced version of their prompt (more detailed and creative)
            2. 3 alternative creative suggestions
            3. Technical improvements for better AI video generation
            
            Format your response as JSON with keys: "enhanced_prompt", "alternatives", "technical_notes"
            """
            
            response = self.model.generate_content(prompt)
            
            # Parse response (you might need to clean this up if Gemini doesn't return perfect JSON)
            try:
                import json
                result = json.loads(response.text)
            except:
                # Fallback if JSON parsing fails
                result = {
                    "enhanced_prompt": response.text,
                    "alternatives": [],
                    "technical_notes": "AI-enhanced prompt generated"
                }
            
            return {
                'success': True,
                'enhanced_prompt': result.get('enhanced_prompt', response.text),
                'alternatives': result.get('alternatives', []),
                'technical_notes': result.get('technical_notes', ''),
                'original_prompt': user_input
            }
            
        except Exception as e:
            logger.error(f"Error enhancing video prompt: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_video_suggestions(self, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Generate video concept suggestions based on user preferences"""
        try:
            if not self.api_key:
                return {'success': False, 'error': 'Gemini API not configured'}
                
            context = self._build_context(preferences)
            
            prompt = f"""
            Based on these music and video preferences, suggest 5 creative video concepts:
            
            Music Details:
            - Genre: {preferences.get('music_preferences', {}).get('genre', 'Not specified')}
            - Mood: {preferences.get('music_preferences', {}).get('mood', 'Not specified')}
            - Tempo: {preferences.get('music_preferences', {}).get('tempo', 'Not specified')}
            - Duration: {preferences.get('music_preferences', {}).get('duration', 'Not specified')} seconds
            
            Video Preferences:
            - Visual Style: {preferences.get('video_preferences', {}).get('visual_style', 'Not specified')}
            - Color Scheme: {preferences.get('video_preferences', {}).get('color_scheme', 'Not specified')}
            - Animation Style: {preferences.get('video_preferences', {}).get('animation_style', 'Not specified')}
            - Resolution: {preferences.get('video_preferences', {}).get('resolution', 'Not specified')}
            
            Please provide 5 creative, detailed video concepts that would work well with these preferences.
            Each concept should be 2-3 sentences describing the visual narrative and style.
            
            Format as JSON with key "suggestions" containing an array of objects with "title" and "description".
            """
            
            response = self.model.generate_content(prompt)
            
            try:
                import json
                result = json.loads(response.text)
                suggestions = result.get('suggestions', [])
            except:
                # Fallback parsing
                suggestions = [
                    {
                        "title": "AI-Generated Concept",
                        "description": response.text
                    }
                ]
            
            return {
                'success': True,
                'suggestions': suggestions
            }
            
        except Exception as e:
            logger.error(f"Error generating video suggestions: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def enhance_music_prompt(self, user_input: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance user's music prompt for better Suno generation"""
        try:
            if not self.api_key:
                return {'success': False, 'error': 'Gemini API not configured'}
                
            music_prefs = preferences.get('music_preferences', {})
            
            prompt = f"""
            You are a music production expert. Help enhance this music description for AI music generation.
            
            User's input: "{user_input}"
            
            Music preferences:
            - Genre: {music_prefs.get('genre', 'Not specified')}
            - Mood: {music_prefs.get('mood', 'Not specified')}
            - Tempo: {music_prefs.get('tempo', 'Not specified')}
            - Energy Level: {music_prefs.get('energy_level', 'Not specified')}
            - Instruments: {', '.join(music_prefs.get('instruments', []))}
            
            Please provide:
            1. An enhanced music prompt optimized for AI generation
            2. Technical music terms that would improve the output
            3. 3 alternative approaches for the same concept
            
            Format as JSON with keys: "enhanced_prompt", "technical_terms", "alternatives"
            """
            
            response = self.model.generate_content(prompt)
            
            try:
                import json
                result = json.loads(response.text)
            except:
                result = {
                    "enhanced_prompt": response.text,
                    "technical_terms": [],
                    "alternatives": []
                }
            
            return {
                'success': True,
                'enhanced_prompt': result.get('enhanced_prompt', response.text),
                'technical_terms': result.get('technical_terms', []),
                'alternatives': result.get('alternatives', []),
                'original_prompt': user_input
            }
            
        except Exception as e:
            logger.error(f"Error enhancing music prompt: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _build_context(self, preferences: Dict[str, Any]) -> str:
        """Build context string from user preferences"""
        context_parts = []
        
        if 'music_preferences' in preferences:
            music = preferences['music_preferences']
            context_parts.append(f"Music: {music.get('genre', '')} {music.get('mood', '')}")
        
        if 'video_preferences' in preferences:
            video = preferences['video_preferences']
            context_parts.append(f"Video: {video.get('visual_style', '')} {video.get('color_scheme', '')}")
        
        return " | ".join(context_parts)
