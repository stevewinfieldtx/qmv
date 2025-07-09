class QuickMusicVideos {
    constructor() {
        this.form = document.getElementById('preferencesForm');
        this.loadingModal = document.getElementById('loadingModal');
        this.submitBtn = document.getElementById('submitBtn');
        this.suggestionsModal = document.getElementById('suggestionsModal');
        
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

        // Visual feedback
        document.querySelectorAll('.preset-card').forEach(card => {
            card.classList.remove('bg-blue-200');
        });
        event.target.closest('.preset-card').classList.add('bg-blue-200');
    }

    attachEventListeners() {
        this.form.addEventListener('submit', this.handleSubmit.bind(this));
        
        // AI Enhancement buttons
        document.getElementById('enhanceVideoBtn').addEventListener('click', this.enhanceVideoPrompt.bind(this));
        document.getElementById('suggestVideoBtn').addEventListener('click', this.getVideoSuggestions.bind(this));
        document.getElementById('enhanceMusicBtn').addEventListener('click', this.enhanceMusicPrompt.bind(this));
        document.getElementById('closeSuggestionsBtn').addEventListener('click', this.closeSuggestionsModal.bind(this));
    }

    async enhanceVideoPrompt() {
        const promptTextarea = document.getElementById('video_prompt');
        const currentPrompt = promptTextarea.value.trim();
        
        if (!currentPrompt) {
            alert('Please enter a video prompt first');
            return;
        }

        const sessionId = localStorage.getItem('sessionId') || '';
        
        this.showButtonLoading('enhanceVideoBtn');
        
        try {
            const response = await fetch('/api/enhance-video-prompt', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    prompt: currentPrompt,
                    session_id: sessionId
                })
            });

            const data = await response.json();

            if (data.success) {
                this.showEnhancementResults(data, 'video');
            } else {
                alert('Error: ' + data.error);
            }
        } catch (error) {
            console.error('Error enhancing video prompt:', error);
            alert('Network error. Please try again.');
        } finally {
            this.hideButtonLoading('enhanceVideoBtn', 'Enhance');
        }
    }

    async getVideoSuggestions() {
        const sessionId = localStorage.getItem('sessionId');
        
        this.showButtonLoading('suggestVideoBtn');
        
        try {
            let requestBody = { session_id: sessionId };
            
            if (!sessionId) {
                // If no session, include current form data
                const formData = new FormData(this.form);
                const preferences = {};
                for (let [key, value] of formData.entries()) {
                    preferences[key] = value;
                }
                requestBody.preferences = preferences;
            }
            
            const response = await fetch('/api/video-suggestions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });

            const data = await response.json();

            if (data.success) {
                this.showSuggestions(data.suggestions);
            } else {
                alert('Error: ' + data.error);
            }
        } catch (error) {
            console.error('Error getting video suggestions:', error);
            alert('Network error. Please try again.');
        } finally {
            this.hideButtonLoading('suggestVideoBtn', 'Suggest');
        }
    }

    async enhanceMusicPrompt() {
        const promptTextarea = document.getElementById('music_prompt');
        const currentPrompt = promptTextarea.value.trim();
        
        if (!currentPrompt) {
            alert('Please enter a music prompt first');
            return;
        }

        const sessionId = localStorage.getItem('sessionId') || '';
        
        this.showButtonLoading('enhanceMusicBtn');
        
        try {
            const response = await fetch('/api/enhance-music-prompt', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    prompt: currentPrompt,
                    session_id: sessionId
                })
            });

            const data = await response.json();

            if (data.success) {
                this.showEnhancementResults(data, 'music');
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

    showEnhancementResults(data, type) {
        const content = document.getElementById('suggestionsContent');
        const promptField = type === 'video' ? 'video_prompt' : 'music_prompt';
        
        content.innerHTML = `
            <div class="space-y-4">
                <div>
                    <h4 class="font-semibold mb-2">Enhanced Prompt:</h4>
                    <div class="bg-gray-50 p-3 rounded border">
                        <p class="text-sm">${data.enhanced_prompt}</p>
                        <button class="mt-2 text-blue-600 hover:text-blue-800 text-sm font-medium" onclick="document.getElementById('${promptField}').value = \`${data.enhanced_prompt.replace(/`/g, '\\`')}\`; document.getElementById('suggestionsModal').classList.add('hidden');">
                            Use This Prompt
                        </button>
                    </div>
                </div>
                
                ${data.alternatives && data.alternatives.length > 0 ? `
                    <div>
                        <h4 class="font-semibold mb-2">Alternative Suggestions:</h4>
                        <div class="space-y-2">
                            ${data.alternatives.map(alt => `
                                <div class="bg-gray-50 p-3 rounded border">
                                    <p class="text-sm">${alt}</p>
                                    <button class="mt-2 text-blue-600 hover:text-blue-800 text-sm font-medium" onclick="document.getElementById('${promptField}').value = \`${alt.replace(/`/g, '\\`')}\`; document.getElementById('suggestionsModal').classList.add('hidden');">
                                        Use This
                                    </button>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
                
                ${data.technical_notes ? `
                    <div>
                        <h4 class="font-semibold mb-2">Technical Notes:</h4>
                        <p class="text-sm text-gray-600 bg-blue-50 p-3 rounded">${data.technical_notes}</p>
                    </div>
                ` : ''}
                
                ${data.technical_terms && data.technical_terms.length > 0 ? `
                    <div>
                        <h4 class="font-semibold mb-2">Technical Terms:</h4>
                        <div class="flex flex-wrap gap-2">
                            ${data.technical_terms.map(term => `
                                <span class="bg-purple-100 text-purple-800 px-2 py-1 rounded text-xs">${term}</span>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
        
        this.showSuggestionsModal();
    }

    showSuggestions(suggestions) {
        const content = document.getElementById('suggestionsContent');
        
        content.innerHTML = `
            <div class="space-y-4">
                <h4 class="font-semibold mb-2">Video Concept Suggestions:</h4>
                <div class="space-y-3">
                    ${suggestions.map(suggestion => `
                        <div class="bg-gray-50 p-4 rounded border hover:bg-gray-100 transition-colors">
                            <h5 class="font-medium mb-2 text-green-800">${suggestion.title}</h5>
                            <p class="text-sm text-gray-700 mb-2">${suggestion.description}</p>
                            <button class="text-blue-600 hover:text-blue-800 text-sm font-medium" onclick="document.getElementById('video_prompt').value = \`${suggestion.description.replace(/`/g, '\\`')}\`; document.getElementById('suggestionsModal').classList.add('hidden');">
                                Use This Concept
                            </button>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
        
        this.showSuggestionsModal();
    }

    showSuggestionsModal() {
        this.suggestionsModal.classList.remove('hidden');
        this.suggestionsModal.classList.add('flex');
    }

    closeSuggestionsModal() {
        this.suggestionsModal.classList.add('hidden');
        this.suggestionsModal.classList.remove('flex');
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
        
        // Convert FormData to object
        for (let [key, value] of formData.entries()) {
            preferences[key] = value;
        }

        // Show loading modal
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
                this.handleSuccess(data);
            } else {
                this.handleError(data.errors || ['Unknown error occurred']);
            }

        } catch (error) {
            this.handleError(['Network error. Please try again.']);
        } finally {
            this.hideLoading();
        }
    }

    handleSuccess(data) {
        alert('Preferences saved successfully! Proceeding to music generation...');
        
        // Store session ID for next phase
        localStorage.setItem('sessionId', data.session_id);
        
        // Here you would typically redirect to the next phase
        console.log('Session ID:', data.session_id);
        console.log('Next phase:', data.next_phase);
    }

    handleError(errors) {
        const errorMessage = errors.join('\n');
        alert('Error: ' + errorMessage);
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

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new QuickMusicVideos();
});
