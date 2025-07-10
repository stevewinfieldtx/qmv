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

        // Update character counts after applying preset
        updateMusicCharCount();
        updateImageCharCount();

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
        document.getElementById('enhanceMusicBtn').addEventListener('click', this.enhanceMusicPrompt.bind(this));
    }

    async enhanceImagePrompt() {
        const promptTextarea = document.getElementById('image_prompt');
        const currentPrompt = promptTextarea.value.trim();
        
        if (!currentPrompt) {
            alert('Please enter an image prompt first');
            return;
        }

        this.showButtonLoading('enhanceImageBtn');

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
                updateImageCharCount();
                alert(`Prompt enhanced! (${data.character_count} characters)\n\n${data.technical_notes}`);
            } else {
                alert('Error: ' + data.error);
            }
        } catch (error) {
            console.error('Error enhancing image prompt:', error);
            alert('Network error. Please try again.');
        } finally {
            this.hideButtonLoading('enhanceImageBtn', 'Enhance');
        }
    }

    async getImageSuggestions() {
        this.showButtonLoading('suggestImageBtn');

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
                this.showSuggestionsModal(data.suggestions, 'image');
            } else {
                alert('Error: ' + data.error);
            }
        } catch (error) {
            console.error('Error getting image suggestions:', error);
            alert('Network error. Please try again.');
        } finally {
            this.hideButtonLoading('suggestImageBtn', 'Suggest');
        }
    }

    async enhanceMusicPrompt() {
        const promptTextarea = document.getElementById('music_prompt');
        const currentPrompt = promptTextarea.value.trim();
        
        if (!currentPrompt) {
            alert('Please enter a music prompt first');
            return;
        }

        this.showButtonLoading('enhanceMusicBtn');

        try {
            const response = await fetch('/api/enhance-music-prompt', {
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
                updateMusicCharCount();
                alert(`Music prompt enhanced! (${data.character_count} characters)\n\n${data.technical_notes}`);
            } else {
                alert('Error: ' + data.error);
            }
        } catch (error) {
            console.error('Error enhancing music prompt:', error);
            alert('Network error. Please try again.');
        } finally {
            this.hideButtonLoading('enhanceMusicBtn', 'Enhance');
        }
    }

    showSuggestionsModal(suggestions, type) {
        let suggestionText = '';
        let promptField = type === 'image' ? 'image_prompt' : 'music_prompt';
        
        if (type === 'image') {
            suggestionText = 'Image Suggestions:\n\n';
            suggestions.forEach((s, i) => {
                suggestionText += `${i + 1}. ${s.title}:\n${s.description}\n\n`;
            });
        } else {
            suggestionText = 'Music Suggestions:\n\n';
            suggestions.forEach((s, i) => {
                suggestionText += `${i + 1}. ${s}\n\n`;
            });
        }
        
        const choice = confirm(suggestionText + '\nWould you like to use the first suggestion?');
        
        if (choice && suggestions.length > 0) {
            const firstSuggestion = type === 'image' ? suggestions[0].description : suggestions[0];
            document.getElementById(promptField).value = firstSuggestion;
            
            // Update character count
            if (type === 'image') {
                updateImageCharCount();
            } else {
                updateMusicCharCount();
            }
        }
    }

    showButtonLoading(buttonId) {
        const button = document.getElementById(buttonId);
        button.disabled = true;
        button.innerHTML = '...';
    }

    hideButtonLoading(buttonId, originalText) {
        const button = document.getElementById(buttonId);
        button.disabled = false;
        button.innerHTML = originalText;
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
                alert('Preferences saved! Music generation started. You will receive 2 song variations.');
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

// Global functions for the HTML onkeyup events
function updateMusicCharCount() {
    const prompt = document.getElementById('music_prompt').value;
    document.getElementById('musicCharCount').textContent = prompt.length;
}

function updateImageCharCount() {
    const prompt = document.getElementById('image_prompt').value;
    document.getElementById('imageCharCount').textContent = prompt.length;
}

document.addEventListener('DOMContentLoaded', () => {
    new QuickMusicVideos();
    // Initialize character counts
    updateMusicCharCount();
    updateImageCharCount();
});
