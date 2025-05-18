document.addEventListener('DOMContentLoaded', function() {
    const fetchBtn = document.getElementById('fetch-btn');
    const getTranscriptBtn = document.getElementById('get-transcript-btn');
    const copyBtn = document.getElementById('copy-btn');
    const downloadBtn = document.getElementById('download-btn');
    const urlInput = document.getElementById('youtube-url');
    const languageSelection = document.getElementById('language-selection');
    const languageOptions = document.getElementById('language-options');
    const loadingIndicator = document.getElementById('loading');
    const errorContainer = document.getElementById('error-container');
    const transcriptContainer = document.getElementById('transcript-container');
    const transcriptContent = document.getElementById('transcript-content');
    
    let selectedVideoId = '';
    let availableLanguages = [];
    
    // Function to show error message
    function showError(message) {
        errorContainer.textContent = message;
        errorContainer.classList.remove('d-none');
        loadingIndicator.classList.add('d-none');
    }
    
    // Function to hide error message
    function hideError() {
        errorContainer.classList.add('d-none');
    }
    
    // Function to format time (seconds to MM:SS format)
    function formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    
    // Function to fetch available languages
    fetchBtn.addEventListener('click', function() {
        const youtubeUrl = urlInput.value.trim();
        
        if (!youtubeUrl) {
            showError('Please enter a YouTube URL');
            return;
        }
        
        // Reset UI
        hideError();
        languageOptions.innerHTML = '';
        languageSelection.classList.add('d-none');
        transcriptContainer.classList.add('d-none');
        loadingIndicator.classList.remove('d-none');
        
        // Fetch available languages
        fetch('/api/available-languages', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url: youtubeUrl })
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || 'Failed to fetch languages');
                });
            }
            return response.json();
        })
        .then(data => {
            loadingIndicator.classList.add('d-none');
            
            if (data.available_languages && data.available_languages.length > 0) {
                selectedVideoId = data.video_id;
                availableLanguages = data.available_languages;
                
                // Display language options
                availableLanguages.forEach((lang, index) => {
                    const langDiv = document.createElement('div');
                    langDiv.className = 'form-check form-check-inline language-option';
                    
                    const input = document.createElement('input');
                    input.className = 'form-check-input';
                    input.type = 'radio';
                    input.name = 'language';
                    input.id = `lang-${lang.language_code}`;
                    input.value = lang.language_code;
                    input.checked = index === 0; // Select first language by default
                    
                    const label = document.createElement('label');
                    label.className = 'form-check-label';
                    label.htmlFor = `lang-${lang.language_code}`;
                    label.textContent = `${lang.language} ${lang.is_generated ? '(Auto-generated)' : ''}`;
                    
                    langDiv.appendChild(input);
                    langDiv.appendChild(label);
                    languageOptions.appendChild(langDiv);
                });
                
                languageSelection.classList.remove('d-none');
            } else {
                showError('No transcripts available for this video');
            }
        })
        .catch(error => {
            showError(error.message);
        });
    });
    
    // Function to fetch transcript
    getTranscriptBtn.addEventListener('click', function() {
        // Get selected language
        const selectedLang = document.querySelector('input[name="language"]:checked');
        
        if (!selectedLang) {
            showError('Please select a language');
            return;
        }
        
        // Reset UI
        hideError();
        transcriptContainer.classList.add('d-none');
        loadingIndicator.classList.remove('d-none');
        
        // Fetch transcript
        fetch('/api/transcript', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                url: urlInput.value.trim(),
                languages: [selectedLang.value],
                preserve_formatting: true
            })
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || 'Failed to fetch transcript');
                });
            }
            return response.json();
        })
        .then(data => {
            loadingIndicator.classList.add('d-none');
            
            if (data.snippets && data.snippets.length > 0) {
                // Display transcript
                let transcriptText = '';
                
                data.snippets.forEach(snippet => {
                    transcriptText += `[${formatTime(snippet.start)}] ${snippet.text}\n\n`;
                });
                
                transcriptContent.textContent = transcriptText;
                transcriptContainer.classList.remove('d-none');
            } else {
                showError('No transcript content available');
            }
        })
        .catch(error => {
            showError(error.message);
        });
    });
    
    // Copy to clipboard functionality
    copyBtn.addEventListener('click', function() {
        const text = transcriptContent.textContent;
        navigator.clipboard.writeText(text)
            .then(() => {
                copyBtn.textContent = 'Copied!';
                setTimeout(() => {
                    copyBtn.textContent = 'Copy to Clipboard';
                }, 2000);
            })
            .catch(() => {
                showError('Failed to copy to clipboard');
            });
    });
    
    // Download as text functionality
    downloadBtn.addEventListener('click', function() {
        const text = transcriptContent.textContent;
        const videoId = selectedVideoId || 'transcript';
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `${videoId}-transcript.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });
}); 