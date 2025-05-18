# YouTube Transcript Fetcher

A simple web application that allows you to fetch transcripts from YouTube videos using the youtube-transcript-api.

## Features

- Extract transcript from any YouTube video URL
- View available transcript languages
- Select your preferred language
- Copy transcript to clipboard
- Download transcript as a text file
- Simple and intuitive UI

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/youtubecult.git
   cd youtubecult
   ```

2. Create a virtual environment (optional but recommended):
   ```
   python3 -m venv venv
   source venv/bin/activate  # On Windows, use venv\Scripts\activate
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Start the Flask application:
   ```
   python3 app.py  # On Windows, you might use 'python app.py'
   ```

2. Open your web browser and navigate to:
   ```
   http://127.0.0.1:5000/
   ```

3. Enter a YouTube URL in the input field and click "Fetch Transcript"

4. Select your preferred language from the available options

5. Click "Get Transcript" to view the transcript

6. Use the "Copy to Clipboard" or "Download as Text" buttons as needed

## API Endpoints

The application provides two main API endpoints:

### 1. Get Available Languages

- **URL**: `/api/available-languages`
- **Method**: `POST`
- **Body**:
  ```json
  {
    "url": "https://www.youtube.com/watch?v=VIDEO_ID"
  }
  ```
- **Response**:
  ```json
  {
    "video_id": "VIDEO_ID",
    "available_languages": [
      {
        "language": "English",
        "language_code": "en",
        "is_generated": false,
        "is_translatable": true,
        "translation_languages": [...]
      },
      ...
    ]
  }
  ```

### 2. Get Transcript

- **URL**: `/api/transcript`
- **Method**: `POST`
- **Body**:
  ```json
  {
    "url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "languages": ["en"],
    "preserve_formatting": true
  }
  ```
- **Response**:
  ```json
  {
    "video_id": "VIDEO_ID",
    "language": "English",
    "language_code": "en",
    "is_generated": false,
    "snippets": [
      {
        "text": "Hello, world!",
        "start": 0.0,
        "duration": 1.5
      },
      ...
    ]
  }
  ```

## Technologies Used

- Python 3.8+
- Flask
- youtube-transcript-api
- Bootstrap 5
- JavaScript (Vanilla)

## License

MIT License 