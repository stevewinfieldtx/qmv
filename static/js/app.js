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
