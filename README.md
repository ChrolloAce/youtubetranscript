# YouTube Transcript API

A reliable REST API for fetching transcripts from YouTube videos.

## Important: Setup YouTube API Key

This application uses the official YouTube Data API to avoid rate limiting and IP blocking. You need a YouTube API key:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the YouTube Data API v3
4. Create an API key
5. Add it to your `.env` file as `YOUTUBE_API_KEY=your_key_here`

## Features

- Fetch transcripts from any YouTube video
- Multi-language support
- Automatic caching to reduce API usage
- Handles rate limiting with retries and exponential backoff
- User-friendly error messages
- Simple and modern UI

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/ChrolloAce/youtubetranscript.git
   cd youtubetranscript
   ```

2. Set up your environment:
   ```
   python3 -m venv venv
   source venv/bin/activate  # On Windows, use venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Create a `.env` file with your YouTube API key:
   ```
   YOUTUBE_API_KEY=your_youtube_api_key_here
   ```

## Hosting on Render.com (Recommended)

1. Push your code to GitHub
2. Log in to [Render.com](https://render.com/) and create a new Web Service
3. Connect to your GitHub repository
4. Set the following:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
   - Add environment variable `YOUTUBE_API_KEY`

## API Usage

### 1. Get Available Languages

```
POST /api/available-languages
Content-Type: application/json

{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

### 2. Get Transcript

```
POST /api/transcript
Content-Type: application/json

{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "languages": ["en"]
}
```

### 3. Check API Status

```
GET /api/status
```

## How It Works

The API uses multiple methods to ensure reliable transcript retrieval:

1. First tries the official YouTube Data API
2. Falls back to YouTube's internal timedtext API
3. Uses caching to minimize requests
4. Implements retry logic with exponential backoff
5. Returns user-friendly error messages

## Troubleshooting

If you encounter issues:

1. Verify your YouTube API key is valid and has quota available
2. Check the API logs for detailed error messages
3. Try different videos (some videos may not have transcripts)
4. Ensure you've enabled the YouTube Data API v3 in your Google Cloud Console

## License

MIT License 