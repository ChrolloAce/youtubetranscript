from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import re
import json
import os
import requests
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

def direct_get_transcript(video_id, language_code='en'):
    """
    Get transcript directly using YouTube's API endpoints
    """
    logger.info(f"Direct get transcript for video {video_id}")
    
    try:
        # Create a session with browser-like headers
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.youtube.com/',
            'Origin': 'https://www.youtube.com'
        })
        
        # First get initial data
        response = session.get(f'https://www.youtube.com/watch?v={video_id}')
        if not response.ok:
            logger.error(f"Failed to get video page: {response.status_code}")
            return None
        
        # Find the JSON data in the HTML response
        # YouTube stores important data in a JSON variable inside a script tag
        init_data_match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', response.text)
        if not init_data_match:
            logger.error("Could not find initial player data")
            return None
            
        init_data = json.loads(init_data_match.group(1))
        
        # Try to extract caption tracks directly
        caption_tracks = []
        try:
            caption_tracks = init_data['captions']['playerCaptionsTracklistRenderer']['captionTracks']
        except (KeyError, TypeError):
            logger.error("No caption tracks found in player data")
            return None
            
        # Find the requested language or fall back to English
        selected_track = None
        for track in caption_tracks:
            if track.get('languageCode') == language_code:
                selected_track = track
                break
                
        # If we can't find the requested language, try to get first English track
        if not selected_track:
            for track in caption_tracks:
                if track.get('languageCode') == 'en':
                    selected_track = track
                    break
                    
        # If still not found, use the first available track
        if not selected_track and caption_tracks:
            selected_track = caption_tracks[0]
            
        if not selected_track:
            logger.error("No usable caption track found")
            return None
            
        # Get the transcript data directly from the baseUrl
        caption_url = selected_track.get('baseUrl')
        if not caption_url:
            logger.error("No baseUrl in selected track")
            return None
            
        # Format parameter helps us get a JSON response
        if '?' in caption_url:
            caption_url += '&fmt=json3'
        else:
            caption_url += '?fmt=json3'
            
        caption_response = session.get(caption_url)
        if not caption_response.ok:
            logger.error(f"Failed to get caption data: {caption_response.status_code}")
            return None
            
        caption_data = caption_response.json()
        
        # Process the transcript data
        transcript_data = []
        events = caption_data.get('events', [])
        
        for event in events:
            # Skip events without segment text
            if not event.get('segs'):
                continue
                
            # Get the text from all segments in this event
            text = ""
            for seg in event.get('segs', []):
                if seg.get('utf8'):
                    text += seg.get('utf8')
                    
            # Skip empty segments
            if not text.strip():
                continue
                
            transcript_data.append({
                'text': text,
                'start': event.get('tStartMs', 0) / 1000,  # Convert to seconds
                'duration': (event.get('dDurationMs', 0) / 1000)  # Convert to seconds
            })
            
        if not transcript_data:
            logger.error("No transcript data extracted")
            return None
            
        return {
            'language': selected_track.get('name', {}).get('simpleText', 'Unknown'),
            'language_code': selected_track.get('languageCode', 'unknown'),
            'is_generated': 'kind' in selected_track and selected_track['kind'] == 'asr',
            'transcript_data': transcript_data
        }
            
    except Exception as e:
        logger.error(f"Direct method error: {str(e)}")
        return None

def get_available_languages_direct(video_id):
    """
    Get available languages directly using YouTube's API endpoints
    """
    logger.info(f"Direct get available languages for video {video_id}")
    
    try:
        # Create a session with browser-like headers
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.youtube.com/',
            'Origin': 'https://www.youtube.com'
        })
        
        # Get initial data
        response = session.get(f'https://www.youtube.com/watch?v={video_id}')
        if not response.ok:
            logger.error(f"Failed to get video page: {response.status_code}")
            return None
        
        # Find the JSON data in the HTML response
        init_data_match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', response.text)
        if not init_data_match:
            logger.error("Could not find initial player data")
            return None
            
        init_data = json.loads(init_data_match.group(1))
        
        # Try to extract caption tracks
        caption_tracks = []
        try:
            caption_tracks = init_data['captions']['playerCaptionsTracklistRenderer']['captionTracks']
        except (KeyError, TypeError):
            logger.error("No caption tracks found in player data")
            return []
            
        # Process languages
        languages = []
        for track in caption_tracks:
            language_name = track.get('name', {}).get('simpleText', 'Unknown')
            language_code = track.get('languageCode', 'unknown')
            is_auto_generated = 'kind' in track and track['kind'] == 'asr'
            
            languages.append({
                'language': language_name,
                'language_code': language_code,
                'is_generated': is_auto_generated,
                'is_translatable': False,  # We don't support translation with this method
                'translation_languages': []
            })
            
        return languages
            
    except Exception as e:
        logger.error(f"Get available languages direct error: {str(e)}")
        return []

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
    
    languages = data.get('languages', ['en'])
    language_code = languages[0] if languages else 'en'
    
    # Use direct method to get transcript
    transcript_result = direct_get_transcript(video_id, language_code)
    
    if transcript_result:
        return jsonify({
            'video_id': video_id,
            'language': transcript_result['language'],
            'language_code': transcript_result['language_code'],
            'is_generated': transcript_result['is_generated'],
            'snippets': [
                {
                    'text': item['text'],
                    'start': item['start'],
                    'duration': item['duration']
                } for item in transcript_result['transcript_data']
            ]
        })
    else:
        return jsonify({
            'error': 'No transcript available for this video',
            'details': 'This video either has no captions/subtitles or they have been disabled by the creator.',
            'video_id': video_id
        }), 404

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
    
    # Use direct method to get available languages
    languages = get_available_languages_direct(video_id)
    
    if languages:
        return jsonify({'video_id': video_id, 'available_languages': languages})
    else:
        return jsonify({
            'error': 'No transcripts available for this video',
            'details': 'This video either has no captions/subtitles or they have been disabled by the creator.',
            'video_id': video_id
        }), 404

if __name__ == '__main__':
    # Get port from environment variable or default to 5000
    port = int(os.environ.get('PORT', 5000))
    
    # Enable debug mode only in development (not on Vercel)
    debug_mode = os.environ.get('VERCEL_ENV') is None
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode) 