```javascript
class QuickMusicVideos {
    constructor() {
        this.form = document.getElementById('preferencesForm');
        this.loadingModal = document.getElementById('loadingModal');
        this.submitBtn = document.getElementById('submitBtn');
        
        this.init();
    }

    init() {
        this.loadPresets();
        this.attachEventListeners();
    }

    async loadPresets() {
        try {
            const response = await fetch('/api/presets');
            const data = await response.json();
            
            if (data.success) {
                this.renderPresets(data.presets);
            }
        } catch (error) {
            console.error('Error loading presets:', error);
        }
    }

    renderPresets(presets) {
        const container = document.getElementById('presets');
        container.innerHTML = '';

        Object.entries(presets).forEach(([key, preset]) => {
            const presetCard = document.createElement('div');
            presetCard.className = 'preset-card bg-gray-100 p-4 rounded-lg cursor-pointer hover:bg-blue-100 transition-colors';
            presetCard.innerHTML = `
                <h3 class="font-semibold mb-2">${this.formatPresetName(key)}</h3>
                <p class="text-sm text-gray-600">${preset.genre} • ${preset.mood}</p>
                <p class="text-xs text-gray-500 mt-1">${preset.visual_style} • ${preset.color_scheme}</p>
            `;
            
            presetCard.addEventListener('click', () => this.applyPreset(preset));
            container.appendChild(presetCard);
        });
    }

    formatPresetName(key) {
        return key.split('_').map(word => 
            word.charAt(0).toUpperCase() + word.slice(1)
        ).join(' ');
    }

    applyPreset(preset) {
        Object.entries(preset).forEach(([key, value]) => {
            const element = document.getElementById(key);
            if (element) {
                element.value = value;
            }
        });

        // Update image count after applying preset
        updateImageCount();

        // Visual feedback
        document.querySelectorAll('.preset-card').forEach(card => {
            card.classList.remove('bg-blue-200');
        });
        event.target.closest('.preset-card').classList.add('bg-blue-200');
    }

    attachEventListeners() {
        this.form.addEventListener('submit', this.handleSubmit.bind(this));
        
        // AI Enhancement buttons
        document.getElementById('enhanceImageBtn').addEventListener('click', this.enhanceImagePrompt.bind(this));
        document.getElementById('suggestImageBtn').addEventListener('click', this.getImageSuggestions.bind(this));
    }

    async enhanceImagePrompt() {
        const promptTextarea = document.getElementById('image_prompt');
        const currentPrompt = promptTextarea.value.trim();
        
        if (!currentPrompt) {
            alert('Please enter an image prompt first');
            return;
        }

        try {
            const response = await fetch('/api/enhance-image-prompt', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    prompt: currentPrompt,
                    session_id: localStorage.getItem('sessionId') || ''
                })
            });

            const data = await response.json();

            if (data.success) {
                promptTextarea.value = data.enhanced_prompt;
                updateCharCount();
                alert(`Prompt enhanced! (${data.character_count} characters)\n\n${data.technical_notes}`);
            } else {
                alert('Error: ' + data.error);
            }
        } catch (error) {
            console.error('Error enhancing image prompt:', error);
            alert('Network error. Please try again.');
        }
    }

    async getImageSuggestions() {
        try {
            const formData = new FormData(this.form);
            const preferences = {};
            for (let [key, value] of formData.entries()) {
                preferences[key] = value;
            }
            
            const response = await fetch('/api/image-suggestions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    preferences: preferences
                })
            });

            const data = await response.json();

            if (data.success) {
                const suggestions = data.suggestions.map(s => `${s.title}:\n${s.description}`).join('\n\n');
                const choice = confirm('Image Suggestions:\n\n' + suggestions + '\n\nWould you like to use one of these suggestions?');
                
                if (choice && data.suggestions.length > 0) {
                    document.getElementById('image_prompt').value = data.suggestions[0].description;
                    updateCharCount();
                }
            } else {
                alert('Error: ' + data.error);
            }
        } catch (error) {
            console.error('Error getting image suggestions:', error);
            alert('Network error. Please try again.');
        }
    }

    async handleSubmit(event) {
        event.preventDefault();
        
        const formData = new FormData(this.form);
        const preferences = {};
        
        for (let [key, value] of formData.entries()) {
            preferences[key] = value;
        }

        this.showLoading();

        try {
            const response = await fetch('/api/preferences', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(preferences)
            });

            const data = await response.json();

            if (data.success) {
                localStorage.setItem('sessionId', data.session_id);
                alert(`Preferences saved! ${data.images_needed} images will be generated for your slideshow.`);
            } else {
                alert('Error: ' + (data.errors || ['Unknown error']).join(', '));
            }

        } catch (error) {
            alert('Network error. Please try again.');
        } finally {
            this.hideLoading();
        }
    }

    showLoading() {
        this.loadingModal.classList.remove('hidden');
        this.loadingModal.classList.add('flex');
        this.submitBtn.disabled = true;
    }

    hideLoading() {
        this.loadingModal.classList.add('hidden');
        this.loadingModal.classList.remove('flex');
        this.submitBtn.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new QuickMusicVideos();
});
```
