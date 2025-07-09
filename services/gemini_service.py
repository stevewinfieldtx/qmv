import google.generativeai as genai
import os
import logging
from typing import Dict, Any, Optional, List
import json
import re

logger = logging.getLogger(__name__)

class GeminiService:
    """Service for interacting with Google Gemini AI for prompt enhancement and suggestions"""
    
    def __init__(self):
        self.api_key = os.environ.get('GEMINI_API_KEY')
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not found in environment variables")
            self.model = None
            return
            
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-pro')
            logger.info("Gemini service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            self.model = None
        
    def enhance_video_prompt(self, user_input: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance user's video prompt with AI suggestions"""
        try:
            if not self.model:
                return {
                    'success': False, 
                    'error': 'Gemini API not configured properly'
                }
                
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
            
            Please provide an enhanced version of their prompt that is more detailed and creative.
            Also provide 3 alternative creative suggestions.
            Include technical improvements for better AI video generation.
            
            Your response should be creative, detailed, and optimized for AI video generation systems.
            """
            
            response = self.model.generate_content(prompt)
            
            # Parse response and extract parts
            response_text = response.text
            
            # Try to extract enhanced prompt (usually the first substantial paragraph)
            lines = response_text.split('\n')
            enhanced_prompt = ""
            alternatives = []
            technical_notes = ""
            
            current_section = "enhanced"
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                if "alternative" in line.lower() or "suggestion" in line.lower():
                    current_section = "alternatives"
                    continue
                elif "technical" in line.lower() or "improvement" in line.lower():
                    current_section = "technical"
                    continue
                
                if current_section == "enhanced" and not enhanced_prompt:
                    enhanced_prompt = line
                elif current_section == "alternatives" and line:
                    if line.startswith(('-', '•', '1.', '2.', '3.')):
                        alternatives.append(line.lstrip('-•123. '))
                    elif len(alternatives) < 3 and len(line) > 20:
                        alternatives.append(line)
                elif current_section == "technical":
                    technical_notes += line + " "
            
            # Fallback if parsing fails
            if not enhanced_prompt:
                enhanced_prompt = response_text[:200] + "..."
            
            if not alternatives:
                alternatives = [
                    "Dynamic camera movements with rhythmic editing",
                    "Abstract visual metaphors matching the music mood",
                    "Layered visual effects with synchronized transitions"
                ]
            
            return {
                'success': True,
                'enhanced_prompt': enhanced_prompt,
                'alternatives': alternatives[:3],
                'technical_notes': technical_notes.strip() or "AI-enhanced prompt generated for optimal video creation",
                'original_prompt': user_input
            }
            
        except Exception as e:
            logger.error(f"Error enhancing video prompt: {e}")
            return {
                'success': False,
                'error': f'Gemini API error: {str(e)}'
            }
    
    def generate_video_suggestions(self, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Generate video concept suggestions based on user preferences"""
        try:
            if not self.model:
                return {
                    'success': False, 
                    'error': 'Gemini API not configured properly'
                }
                
            context = self._build_context(preferences)
            
            prompt = f"""
            Based on these music and video preferences, create 5 creative video concepts that would work perfectly together:
            
            Music Details:
            - Genre: {preferences.get('music_preferences', {}).get('genre', 'Pop')}
            - Mood: {preferences.get('music_preferences', {}).get('mood', 'Upbeat')}
            - Tempo: {preferences.get('music_preferences', {}).get('tempo', 'Medium')}
            - Duration: {preferences.get('music_preferences', {}).get('duration', 60)} seconds
            
            Video Preferences:
            - Visual Style: {preferences.get('video_preferences', {}).get('visual_style', 'Modern')}
            - Color Scheme: {preferences.get('video_preferences', {}).get('color_scheme', 'Vibrant')}
            - Animation Style: {preferences.get('video_preferences', {}).get('animation_style', 'Smooth')}
            - Resolution: {preferences.get('video_preferences', {}).get('resolution', '1080p')}
            
            Please provide 5 creative, detailed video concepts. Each concept should be 2-3 sentences describing a unique visual narrative and style that matches these preferences.
            
            Format each suggestion as:
            Title: [Creative Title]
            Description: [2-3 sentence description]
            
            Make them diverse and creative while staying true to the user's preferences.
            """
            
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            # Parse suggestions
            suggestions = []
            lines = response_text.split('\n')
            current_title = ""
            current_description = ""
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                if line.lower().startswith('title:') or line.lower().startswith('1.') or line.lower().startswith('2.') or line.lower().startswith('3.') or line.lower().startswith('4.') or line.lower().startswith('5.'):
                    if current_title and current_description:
                        suggestions.append({
                            'title': current_title,
                            'description': current_description
                        })
                    current_title = line.replace('Title:', '').replace('1.', '').replace('2.', '').replace('3.', '').replace('4.', '').replace('5.', '').strip()
                    current_description = ""
                elif line.lower().startswith('description:'):
                    current_description = line.replace('Description:', '').strip()
                elif current_title and not current_description:
                    current_description = line
                elif current_title and current_description and len(line) > 20:
                    current_description += " " + line
            
            # Add the last suggestion
            if current_title and current_description:
                suggestions.append({
                    'title': current_title,
                    'description': current_description
                })
            
            # Fallback if parsing fails
            if not suggestions:
                suggestions = [
                    {
                        'title': 'Dynamic Visual Journey',
                        'description': f"A {preferences.get('video_preferences', {}).get('visual_style', 'modern')} video with {preferences.get('video_preferences', {}).get('color_scheme', 'vibrant')} colors that matches the {preferences.get('music_preferences', {}).get('mood', 'upbeat')} mood of your {preferences.get('music_preferences', {}).get('genre', 'pop')} music."
                    },
                    {
                        'title': 'Rhythmic Visual Patterns',
                        'description': 'Abstract geometric patterns that pulse and flow with the music beat, creating a mesmerizing visual experience.'
                    },
                    {
                        'title': 'Cinematic Storytelling',
                        'description': 'A narrative-driven video with smooth transitions and professional cinematography that complements your music style.'
                    }
                ]
            
            return {
                'success': True,
                'suggestions': suggestions[:5]
            }
            
        except Exception as e:
            logger.error(f"Error generating video suggestions: {e}")
            return {
                'success': False,
                'error': f'Gemini API error: {str(e)}'
            }
    
    def enhance_music_prompt(self, user_input: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance user's music prompt for better Suno generation"""
        try:
            if not self.model:
                return {
                    'success': False, 
                    'error': 'Gemini API not configured properly'
                }
                
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
            
            Make the enhanced prompt detailed, using proper music terminology and production language.
            """
            
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            # Parse the response
            lines = response_text.split('\n')
            enhanced_prompt = ""
            technical_terms = []
            alternatives = []
            
            current_section = "enhanced"
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                if "technical" in line.lower() or "terms" in line.lower():
                    current_section = "technical"
                    continue
                elif "alternative" in line.lower() or "approach" in line.lower():
                    current_section = "alternatives"
                    continue
                
                if current_section == "enhanced" and not enhanced_prompt:
                    if len(line) > 20 and not line.startswith(('1.', '2.', '3.')):
                        enhanced_prompt = line
                elif current_section == "technical":
                    if line.startswith(('-', '•')) or len(line) > 10:
                        technical_terms.append(line.lstrip('-• '))
                elif current_section == "alternatives":
                    if line.startswith(('-', '•', '1.', '2.', '3.')):
                        alternatives.append(line.lstrip('-•123. '))
                    elif len(alternatives) < 3 and len(line) > 20:
                        alternatives.append(line)
            
            # Fallback if parsing fails
            if not enhanced_prompt:
                enhanced_prompt = response_text[:150] + "..."
            
            if not alternatives:
                alternatives = [
                    f"Focus on {music_prefs.get('genre', 'modern')} production with {music_prefs.get('mood', 'dynamic')} energy",
                    f"Emphasize {music_prefs.get('tempo', 'medium')} tempo with rich instrumentation",
                    f"Create atmospheric {music_prefs.get('genre', 'contemporary')} soundscape"
                ]
            
            return {
                'success': True,
                'enhanced_prompt': enhanced_prompt,
                'technical_terms': technical_terms[:5],
                'alternatives': alternatives[:3],
                'original_prompt': user_input
            }
            
        except Exception as e:
            logger.error(f"Error enhancing music prompt: {e}")
            return {
                'success': False,
                'error': f'Gemini API error: {str(e)}'
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
