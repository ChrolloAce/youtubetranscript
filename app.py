from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from youtube_transcript_api import YouTubeTranscriptApi
import re
import json
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

def extract_video_id(url):
    """
    Extract the YouTube video ID from various YouTube URL formats
    """
    # Regular expression patterns for different YouTube URL formats
    youtube_regex = (
        r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
        r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
    )
    
    match = re.search(youtube_regex, url)
    if match:
        return match.group(6)
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/transcript', methods=['POST'])
def get_transcript():
    data = request.json
    if not data or 'url' not in data:
        return jsonify({'error': 'No URL provided'}), 400
    
    url = data['url']
    video_id = extract_video_id(url)
    
    if not video_id:
        return jsonify({'error': 'Invalid YouTube URL'}), 400
    
    try:
        languages = data.get('languages', ['en'])
        preserve_formatting = data.get('preserve_formatting', False)
        
        # Get the list of transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Find the preferred transcript
        transcript = transcript_list.find_transcript(languages)
        
        # Fetch the actual transcript data
        transcript_data = transcript.fetch()
        
        # Convert to a serializable format
        response = {
            'video_id': video_id,
            'language': transcript.language,
            'language_code': transcript.language_code,
            'is_generated': transcript.is_generated,
            'snippets': [
                {
                    'text': item['text'],
                    'start': item['start'],
                    'duration': item['duration']
                } for item in transcript_data
            ]
        }
        
        return jsonify(response)
    except Exception as e:
        error_message = str(e)
        
        # Create more user-friendly error messages
        if "Could not retrieve a transcript" in error_message:
            return jsonify({
                'error': 'No transcript available for this video',
                'details': 'This video either has no captions/subtitles or they have been disabled by the creator.',
                'video_id': video_id
            }), 404
        elif "not in language" in error_message:
            return jsonify({
                'error': 'The requested language is not available for this video',
                'details': 'Try using the /api/available-languages endpoint to see what languages are available.',
                'video_id': video_id
            }), 404
        
        # Default error response
        return jsonify({'error': error_message}), 500

@app.route('/api/available-languages', methods=['POST'])
def get_available_languages():
    data = request.json
    if not data or 'url' not in data:
        return jsonify({'error': 'No URL provided'}), 400
    
    url = data['url']
    video_id = extract_video_id(url)
    
    if not video_id:
        return jsonify({'error': 'Invalid YouTube URL'}), 400
    
    try:
        # Get the list of transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Create a list of available languages
        languages = []
        for transcript in transcript_list:
            languages.append({
                'language': transcript.language,
                'language_code': transcript.language_code,
                'is_generated': transcript.is_generated,
                'is_translatable': transcript.is_translatable,
                'translation_languages': [
                    {'language': lang['language'], 'language_code': lang['language_code']}
                    for lang in transcript.translation_languages
                ] if transcript.is_translatable else []
            })
        
        return jsonify({'video_id': video_id, 'available_languages': languages})
    except Exception as e:
        error_message = str(e)
        
        # Create more user-friendly error messages
        if "Could not retrieve a transcript" in error_message:
            return jsonify({
                'error': 'No transcripts available for this video',
                'details': 'This video either has no captions/subtitles or they have been disabled by the creator.',
                'video_id': video_id
            }), 404
        
        # Default error response
        return jsonify({'error': error_message}), 500

if __name__ == '__main__':
    # Get port from environment variable or default to 5000
    port = int(os.environ.get('PORT', 5000))
    
    # Enable debug mode only in development (not on Vercel)
    debug_mode = os.environ.get('VERCEL_ENV') is None
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode) 