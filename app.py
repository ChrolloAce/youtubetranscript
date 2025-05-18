from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_caching import Cache
import re
import json
import os
import time
import logging
import requests
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# YouTube API Key
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', None)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configure cache - store results for 1 hour
cache_config = {
    "DEBUG": True,
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 3600  # 1 hour
}
app.config.from_mapping(cache_config)
cache = Cache(app)

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

def get_youtube_client():
    """Create an authenticated YouTube client"""
    if not YOUTUBE_API_KEY:
        logger.error("YouTube API key is not set")
        return None
        
    try:
        return build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    except Exception as e:
        logger.error(f"Failed to build YouTube client: {str(e)}")
        return None

def get_captions_via_timedtext(video_id, language_code='en'):
    """
    Get captions via YouTube's timedtext API (fallback method)
    """
    try:
        # This is a more reliable endpoint for getting captions
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # First, get video info to find caption tracks
        # Using a different endpoint that's less likely to be rate-limited
        info_url = f"https://www.youtube.com/get_video_info?video_id={video_id}&html5=1"
        response = session.get(info_url)
        
        if not response.ok:
            logger.error(f"Failed to get video info: {response.status_code}")
            return None
            
        # Extract captions data
        query_str = response.text
        params = {}
        
        # Parse query string
        for param in query_str.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                params[key] = value
                
        # Try to get player response
        if 'player_response' in params:
            import urllib.parse
            player_response = json.loads(urllib.parse.unquote(params['player_response']))
            
            # Extract captions data
            if 'captions' in player_response:
                captions_data = player_response['captions']
                
                if 'playerCaptionsTracklistRenderer' in captions_data:
                    tracks = captions_data['playerCaptionsTracklistRenderer'].get('captionTracks', [])
                    
                    # Find the requested language
                    selected_track = None
                    for track in tracks:
                        if track.get('languageCode') == language_code:
                            selected_track = track
                            break
                            
                    # If not found, try English or first available
                    if not selected_track:
                        for track in tracks:
                            if track.get('languageCode') == 'en':
                                selected_track = track
                                break
                                
                    if not selected_track and tracks:
                        selected_track = tracks[0]
                        
                    if selected_track:
                        base_url = selected_track.get('baseUrl')
                        if base_url:
                            # Add format=json3 to get JSON response
                            if '?' in base_url:
                                caption_url = f"{base_url}&fmt=json3"
                            else:
                                caption_url = f"{base_url}?fmt=json3"
                                
                            caption_response = session.get(caption_url)
                            if caption_response.ok:
                                caption_data = caption_response.json()
                                
                                # Process transcript data
                                transcript_data = []
                                for event in caption_data.get('events', []):
                                    if not event.get('segs'):
                                        continue
                                        
                                    text = ""
                                    for seg in event.get('segs', []):
                                        if seg.get('utf8'):
                                            text += seg.get('utf8')
                                            
                                    if not text.strip():
                                        continue
                                        
                                    transcript_data.append({
                                        'text': text,
                                        'start': event.get('tStartMs', 0) / 1000,
                                        'duration': event.get('dDurationMs', 0) / 1000
                                    })
                                    
                                return {
                                    'language': selected_track.get('name', {}).get('simpleText', 'Unknown'),
                                    'language_code': selected_track.get('languageCode', 'unknown'),
                                    'is_generated': 'kind' in selected_track and selected_track['kind'] == 'asr',
                                    'transcript_data': transcript_data
                                }
        
        return None
    except Exception as e:
        logger.error(f"Error in timedtext fallback: {str(e)}")
        return None

@cache.memoize(timeout=3600)  # Cache for 1 hour
def get_transcript_with_retry(video_id, language_code='en'):
    """
    Try multiple methods with retries to get transcript data
    """
    logger.info(f"Getting transcript for video {video_id}, language {language_code}")
    
    # Try the official API first
    youtube = get_youtube_client()
    if youtube:
        try:
            # Official API request to get captions
            results = youtube.captions().list(
                part="snippet",
                videoId=video_id
            ).execute()
            
            captions = results.get("items", [])
            
            # Find the right language caption
            caption_id = None
            for caption in captions:
                if caption["snippet"]["language"] == language_code:
                    caption_id = caption["id"]
                    break
                    
            # If not found, look for English or the first one
            if not caption_id:
                for caption in captions:
                    if caption["snippet"]["language"] == "en":
                        caption_id = caption["id"]
                        break
                        
            if not caption_id and captions:
                caption_id = captions[0]["id"]
                
            if caption_id:
                # Unfortunately, the YouTube API doesn't allow downloading captions
                # without OAuth, so we'll use our fallback method
                pass
                
        except HttpError as e:
            logger.error(f"YouTube API error: {str(e)}")
    
    # Try our fallback method 
    for attempt in range(3):  # Try up to 3 times
        try:
            result = get_captions_via_timedtext(video_id, language_code)
            if result:
                return result
        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed: {str(e)}")
            
        # Wait before retrying (exponential backoff)
        time.sleep(2 ** attempt)
        
    return None

@cache.memoize(timeout=3600)  # Cache for 1 hour
def get_available_languages_with_retry(video_id):
    """
    Get available languages with retry logic
    """
    logger.info(f"Getting available languages for video {video_id}")
    
    # Try our official API first
    youtube = get_youtube_client()
    if youtube:
        try:
            # Get caption tracks
            results = youtube.captions().list(
                part="snippet",
                videoId=video_id
            ).execute()
            
            captions = results.get("items", [])
            
            if captions:
                languages = []
                for caption in captions:
                    snippet = caption["snippet"]
                    languages.append({
                        'language': snippet.get("name", "Unknown"),
                        'language_code': snippet.get("language", "unknown"),
                        'is_generated': snippet.get("trackKind", "") == "ASR",
                        'is_translatable': False,
                        'translation_languages': []
                    })
                return languages
                
        except HttpError as e:
            logger.error(f"YouTube API error: {str(e)}")
    
    # Try fallback method
    for attempt in range(3):  # Try up to 3 times
        try:
            # Try to get info from timedtext API
            session = requests.Session()
            info_url = f"https://www.youtube.com/get_video_info?video_id={video_id}&html5=1"
            response = session.get(info_url)
            
            if response.ok:
                query_str = response.text
                params = {}
                
                # Parse query string
                for param in query_str.split('&'):
                    if '=' in param:
                        key, value = param.split('=', 1)
                        params[key] = value
                        
                # Try to get player response
                if 'player_response' in params:
                    import urllib.parse
                    player_response = json.loads(urllib.parse.unquote(params['player_response']))
                    
                    # Extract captions data
                    if 'captions' in player_response:
                        captions_data = player_response['captions']
                        
                        if 'playerCaptionsTracklistRenderer' in captions_data:
                            tracks = captions_data['playerCaptionsTracklistRenderer'].get('captionTracks', [])
                            
                            if tracks:
                                languages = []
                                for track in tracks:
                                    languages.append({
                                        'language': track.get('name', {}).get('simpleText', 'Unknown'),
                                        'language_code': track.get('languageCode', 'unknown'),
                                        'is_generated': 'kind' in track and track['kind'] == 'asr',
                                        'is_translatable': False,
                                        'translation_languages': []
                                    })
                                return languages
                
        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed: {str(e)}")
            
        # Wait before retrying
        time.sleep(2 ** attempt)
        
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
    
    # Try to get transcript with retry logic
    transcript_result = get_transcript_with_retry(video_id, language_code)
    
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
    
    # Try to get available languages with retry logic
    languages = get_available_languages_with_retry(video_id)
    
    if languages:
        return jsonify({'video_id': video_id, 'available_languages': languages})
    else:
        return jsonify({
            'error': 'No transcripts available for this video',
            'details': 'This video either has no captions/subtitles or they have been disabled by the creator.',
            'video_id': video_id
        }), 404

@app.route('/api/status', methods=['GET'])
def status():
    """API status endpoint for health checks"""
    return jsonify({
        'status': 'ok',
        'version': '1.0.0',
        'youtube_api': bool(YOUTUBE_API_KEY)
    })

if __name__ == '__main__':
    # Get port from environment variable or default to 5000
    port = int(os.environ.get('PORT', 5000))
    
    # Enable debug mode only in development
    debug_mode = os.environ.get('ENVIRONMENT') != 'production'
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode) 