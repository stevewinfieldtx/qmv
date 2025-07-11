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
                this.sessionId = data.session_id;
                
                // Start automatic music generation and monitoring
                this.startMusicGeneration();
            } else {
                alert('Error: ' + (data.errors || ['Unknown error']).join(', '));
                this.hideLoading();
            }

        } catch (error) {
            alert('Network error. Please try again.');
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

    async startMusicGeneration() {
        try {
            // Update loading message
            this.updateLoadingMessage('Starting music generation...');
            
            // Trigger direct music generation
            const response = await fetch(`/api/generate-music/${this.sessionId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            const data = await response.json();

            if (data.success) {
                // Since Redis is not available, results are returned immediately
                this.updateLoadingMessage('Music generation completed! Loading results...');
                this.displayMusicResults(data.result.songs);
            } else {
                alert('Error starting music generation: ' + data.error);
                this.hideLoading();
            }
        } catch (error) {
            alert('Network error during music generation: ' + error.message);
            this.hideLoading();
        }
    }

    // Status monitoring methods removed since we get results immediately without Redis

    displayMusicResults(songs) {
        // Hide loading modal first
        this.hideLoading();
        
        // Check if songs exist
        if (!songs || songs.length === 0) {
            alert('No music was generated. Please try again.');
            return;
        }
        
        // Create results modal
        const resultsModal = document.createElement('div');
        resultsModal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
        resultsModal.innerHTML = `
            <div class="bg-white p-8 rounded-lg max-w-4xl w-full mx-4 max-h-96 overflow-y-auto">
                <h2 class="text-2xl font-bold mb-6 text-center">🎵 Your Music is Ready!</h2>
                <div class="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded mb-4">
                    <p class="text-sm">✅ Your music files have been saved and are ready for download!</p>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    ${songs.map((song, index) => `
                        <div class="border rounded-lg p-4">
                            <h3 class="font-semibold text-lg mb-2">${song.title || `Song ${index + 1}`}</h3>
                            <p class="text-sm text-gray-600 mb-3">${song.tags || 'No tags'}</p>
                            ${song.duration ? `<p class="text-xs text-gray-500 mb-2">Duration: ${song.duration}s</p>` : ''}
                            ${song.file_size ? `<p class="text-xs text-gray-500 mb-3">Size: ${Math.round(song.file_size / 1024 / 1024 * 100) / 100} MB</p>` : ''}
                            ${song.audio_url ? `
                                <audio controls class="w-full mb-3">
                                    <source src="${song.audio_url}" type="audio/mpeg">
                                    Your browser does not support the audio element.
                                </audio>
                            ` : ''}
                            <div class="flex gap-2">
                                ${song.download_url ? `
                                    <a href="${song.download_url}" download="${song.title || `Song_${index + 1}`}.mp3" 
                                       class="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 text-sm flex items-center gap-1">
                                        📥 Download Your Copy
                                    </a>
                                ` : `
                                    <a href="${song.audio_url}" download="${song.title || `Song_${index + 1}`}.mp3" 
                                       class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm flex items-center gap-1">
                                        📥 Download MP3
                                    </a>
                                `}
                            </div>
                        </div>
                    `).join('')}
                </div>
                <div class="text-center mt-6">
                    <button onclick="this.showDownloadCenter()" 
                            class="bg-purple-600 text-white px-6 py-2 rounded-lg hover:bg-purple-700 mr-3">
                        📁 Download Center
                    </button>
                    <button onclick="this.parentElement.parentElement.parentElement.remove()" 
                            class="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700">
                        Close
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(resultsModal);
    }

    updateLoadingMessage(message) {
        const loadingText = this.loadingModal.querySelector('p');
        if (loadingText) {
            loadingText.textContent = message;
        }
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
