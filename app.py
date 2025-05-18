from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from youtube_transcript_api import YouTubeTranscriptApi
import re
import json
import os
import requests
from bs4 import BeautifulSoup
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

def fallback_get_transcript(video_id):
    """
    Fallback method to get YouTube transcript when the API fails.
    This uses a different approach to avoid IP blocking.
    """
    logger.info(f"Using fallback method for video {video_id}")
    
    try:
        # Different approach - use innertube API
        session = requests.Session()
        session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        
        # First get the initial page to extract necessary tokens
        response = session.get(f'https://www.youtube.com/watch?v={video_id}')
        
        if not response.ok:
            return None
        
        html = response.text
        
        # Try to extract transcript data from the page directly
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for transcript data in script tags
        transcript_data = []
        scripts = soup.find_all('script')
        
        for script in scripts:
            script_text = script.string
            if script_text and '"captionTracks"' in script_text:
                # Try to extract caption tracks URL
                caption_match = re.search(r'"captionTracks":\s*(\[.*?\])', script_text)
                if caption_match:
                    caption_data = json.loads(caption_match.group(1).replace('\\u0026', '&'))
                    
                    if caption_data:
                        # Get the first available English transcript
                        for track in caption_data:
                            if track.get('languageCode', '') == 'en':
                                base_url = track.get('baseUrl', '')
                                if base_url:
                                    # Get the transcript data
                                    transcript_response = session.get(base_url)
                                    if transcript_response.ok:
                                        # Parse XML response
                                        soup = BeautifulSoup(transcript_response.text, 'html.parser')
                                        transcript_elements = soup.find_all('text')
                                        
                                        for element in transcript_elements:
                                            start = float(element.get('start', 0))
                                            duration = float(element.get('dur', 0)) if element.get('dur') else 0
                                            text = element.get_text()
                                            
                                            transcript_data.append({
                                                'text': text,
                                                'start': start,
                                                'duration': duration
                                            })
                                        
                                        return {
                                            'language': 'English',
                                            'language_code': 'en',
                                            'is_generated': True,
                                            'transcript_data': transcript_data
                                        }
        
        return None
        
    except Exception as e:
        logger.error(f"Fallback method error: {str(e)}")
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
    
    # Log request information for debugging
    logger.info(f"Transcript request for video ID: {video_id}")
    
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
        logger.error(f"API method error: {error_message}")
        
        # Try fallback method if the API method fails
        if "Could not retrieve a transcript" in error_message:
            logger.info("Trying fallback method...")
            fallback_result = fallback_get_transcript(video_id)
            
            if fallback_result:
                return jsonify({
                    'video_id': video_id,
                    'language': fallback_result['language'],
                    'language_code': fallback_result['language_code'],
                    'is_generated': fallback_result['is_generated'],
                    'snippets': [
                        {
                            'text': item['text'],
                            'start': item['start'],
                            'duration': item['duration']
                        } for item in fallback_result['transcript_data']
                    ]
                })
        
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
    
    # Log request information for debugging
    logger.info(f"Available languages request for video ID: {video_id}")
    
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
        logger.error(f"Available languages error: {error_message}")
        
        # Try fallback method for available languages
        if "Could not retrieve a transcript" in error_message:
            fallback_result = fallback_get_transcript(video_id)
            
            if fallback_result:
                return jsonify({
                    'video_id': video_id, 
                    'available_languages': [{
                        'language': fallback_result['language'],
                        'language_code': fallback_result['language_code'],
                        'is_generated': fallback_result['is_generated'],
                        'is_translatable': False,
                        'translation_languages': []
                    }]
                })
        
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