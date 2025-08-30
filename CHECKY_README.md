# 🤖 Checky - Multimodal Assistant for Children

Checky is a child-friendly multimodal voice assistant built on [Pipecat](https://github.com/pipecat-ai/pipecat) that provides age-appropriate German language interactions using Google's Speech-to-Text, Text-to-Speech, and Gemini 1.5 Flash.

## ✨ Features

- **Child-Friendly Interface**: Visual-only interface with hold-to-talk button - no text for children
- **Age-Appropriate Responses**: Tailored German conversation based on child's age (5-10 years)
- **Real-time Voice Interaction**: Low-latency audio streaming with WebSocket support
- **Parent Controls**: PIN-protected settings for age and voice configuration
- **Privacy Protection**: PII scrubbing before sending data to AI services
- **Responsive Design**: Works on desktop, tablet, and mobile devices

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI        │    │   CheckyPipeline│
│   - index.html  │ ◄──► │   Web Server     │ ◄──► │   - Google STT  │
│   - parent.html │    │   - REST API     │    │   - Gemini 1.5  │
│   - WebSocket   │    │   - WebSocket    │    │   - Google TTS  │
│                 │    │   - Rate Limit   │    │   - PII Filter  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   SQLite DB      │
                       │   - User Config  │
                       │   - PIN (Hashed) │
                       │   - Child Age    │
                       │   - TTS Voice    │
                       └──────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Google Cloud Project with enabled APIs
- Google Application Credentials
- Gemini API Key

### Installation

1. **Clone and Install Dependencies**
   ```bash
   git clone <repository-url>
   cd checky
   
   # Install with uv (recommended)
   uv add pipecat-ai[google,websocket]
   uv add fastapi uvicorn slowapi bcrypt
   
   # Or with pip
   pip install pipecat-ai[google,websocket] fastapi uvicorn slowapi bcrypt
   ```

2. **Set up Environment Variables**
   ```bash
   # Copy environment template
   cp env.example .env
   
   # Edit .env with your credentials
   GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/credentials.json
   GOOGLE_CLOUD_PROJECT=your-project-id
   GEMINI_API_KEY=your-gemini-api-key
   ```

3. **Run the Application**
   ```bash
   # Development mode
   python -m src.checky.web_app
   
   # Or with uvicorn
   uvicorn src.checky.web_app:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Access the Application**
   - Main interface: http://localhost:8000
   - Parent settings: http://localhost:8000/parent.html

## 🛠️ Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to Google Cloud service account JSON | `/path/to/credentials.json` |
| `GOOGLE_CLOUD_PROJECT` | Your Google Cloud project ID | `my-project-123456` |
| `GEMINI_API_KEY` | Google AI Studio API key for Gemini | `AIzaSyC...` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_PATH` | SQLite database file path | `checky.db` |
| `LOG_LEVEL` | Logging level | `INFO` |

## 📱 User Flow

### 1. Initial Setup (Parents)

1. Visit `/parent.html`
2. Navigate to "Einrichtung" (Setup) tab
3. Enter child's age (5-10 years)
4. Create 4-digit PIN for parent access
5. Select German TTS voice
6. Click "Checky einrichten" (Set up Checky)

### 2. Child Interaction

1. Visit main page (`/`)
2. Hold the microphone button and speak in German
3. Checky responds with age-appropriate German audio
4. Release button to stop recording

### 3. Settings Management (Parents)

1. Visit `/parent.html`
2. Navigate to "Einstellungen" (Settings) tab
3. Enter PIN to authenticate
4. Update age or voice settings as needed
5. Save changes

## 🔧 API Documentation

### REST Endpoints

#### POST `/onboard`
Create initial user configuration.

**Request:**
```json
{
  "age": 7,
  "pin": "1234",
  "tts_voice": "de-DE-Standard-A"
}
```

**Response:**
```json
{
  "success": true,
  "message": "User onboarded successfully"
}
```

#### POST `/parent/login`
Authenticate parent with PIN.

**Request:**
```json
{
  "pin": "1234"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Authentication successful"
}
```

#### PUT `/parent/settings`
Update user settings with PIN authentication.

**Request:**
```json
{
  "pin": "1234",
  "age": 8,
  "tts_voice": "de-DE-Wavenet-A"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Settings updated successfully"
}
```

#### GET `/config`
Get current configuration (PIN excluded).

**Response:**
```json
{
  "id": 1,
  "child_age": 7,
  "tts_voice": "de-DE-Standard-A",
  "created_at": "2025-01-15T10:30:00",
  "updated_at": "2025-01-15T10:30:00"
}
```

#### GET `/health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "checky"
}
```

### WebSocket Endpoint

#### WS `/chat`
Real-time audio chat with Checky.

- **Input**: Audio data (binary WebSocket messages)
- **Output**: TTS audio responses (binary WebSocket messages)
- **Text Messages**: JSON-formatted status/error messages

## 🎨 Frontend Components

### index.html (Child Interface)
- **Hold-to-talk button**: Large, colorful button for easy interaction
- **Visual status indicators**: Connection, listening, and speaking states
- **No text**: Child-friendly design with icons only
- **Responsive**: Works on all device sizes

### parent.html (Parent Interface)
- **Onboarding form**: Initial setup with age, PIN, and voice selection
- **Settings management**: Update configuration with PIN protection
- **Current configuration display**: Shows active settings
- **Responsive design**: Mobile-friendly forms

## 🔐 Security Features

### PIN Protection
- 4-digit numeric PIN for parent access
- Bcrypt hashing for secure storage
- PIN required for all configuration changes

### PII Protection
- Automatic scrubbing of personally identifiable information
- Email addresses, phone numbers, addresses removed
- Child safety prioritized in all interactions

### Rate Limiting
- 10 requests per minute per IP address
- Protection against abuse and spam
- Applied to all API endpoints

## 🌐 Google Cloud Setup

### 1. Enable APIs
```bash
gcloud services enable speech.googleapis.com
gcloud services enable texttospeech.googleapis.com
gcloud services enable aiplatform.googleapis.com
```

### 2. Create Service Account
```bash
gcloud iam service-accounts create checky-service \
    --description="Service account for Checky assistant" \
    --display-name="Checky Service Account"
```

### 3. Grant Permissions
```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:checky-service@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/speech.client"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:checky-service@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/texttospeech.client"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:checky-service@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"
```

### 4. Download Credentials
```bash
gcloud iam service-accounts keys create credentials.json \
    --iam-account=checky-service@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### 5. Get Gemini API Key
1. Visit [Google AI Studio](https://makersuite.google.com/)
2. Create a new API key
3. Copy the key to your `.env` file

## 🎯 Available TTS Voices

### Standard Voices
- `de-DE-Standard-A`: Standard German female voice
- `de-DE-Standard-B`: Standard German male voice

### Premium WaveNet Voices
- `de-DE-Wavenet-A`: Premium German female voice
- `de-DE-Wavenet-B`: Premium German male voice
- `de-DE-Wavenet-C`: Premium German female voice (alternative)
- `de-DE-Wavenet-D`: Premium German male voice (alternative)

## 🛠️ Development

### Project Structure
```
src/checky/
├── __init__.py          # Package initialization
├── pipeline.py          # CheckyPipeline and PII scrubbing
├── db.py               # Database operations
└── web_app.py          # FastAPI application

public/
├── index.html          # Child interface
└── parent.html         # Parent interface
```

### Running Tests
```bash
# Install test dependencies
uv add pytest pytest-asyncio httpx

# Run tests
pytest tests/
```

### Code Style
```bash
# Install formatting tools
uv add black isort flake8

# Format code
black src/
isort src/

# Check style
flake8 src/
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Audio Permission Denied
**Problem**: Browser doesn't allow microphone access
**Solution**: 
- Ensure HTTPS in production
- Check browser microphone permissions
- Use `localhost` or `127.0.0.1` for local development

#### 2. Google Cloud Authentication Failed
**Problem**: `DefaultCredentialsError` or similar
**Solutions**:
- Verify `GOOGLE_APPLICATION_CREDENTIALS` path is correct
- Check service account has required permissions
- Ensure credentials.json file is valid

#### 3. WebSocket Connection Failed
**Problem**: Cannot connect to `/chat` endpoint
**Solutions**:
- Check if server is running
- Verify firewall/network settings
- Ensure user is onboarded (has configuration)

#### 4. No Audio Output
**Problem**: Checky doesn't speak back
**Solutions**:
- Check browser audio settings
- Verify TTS voice ID is valid
- Check Google Cloud TTS API quotas

#### 5. Rate Limit Exceeded
**Problem**: "Rate limit exceeded" errors
**Solutions**:
- Wait for rate limit to reset (1 minute)
- Implement client-side request throttling
- Consider upgrading rate limits for production

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python -m src.checky.web_app
```

### Health Checks
```bash
# Check API health
curl http://localhost:8000/health

# Check configuration
curl http://localhost:8000/config
```

## 📋 Production Deployment

### Environment Variables
```bash
# Production settings
export GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json
export GOOGLE_CLOUD_PROJECT=your-production-project
export GEMINI_API_KEY=your-production-api-key
export DB_PATH=/app/data/checky.db
```

### Docker Deployment
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ src/
COPY public/ public/
COPY credentials.json .

EXPOSE 8000
CMD ["uvicorn", "src.checky.web_app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Process Management
```bash
# Using gunicorn for production
pip install gunicorn
gunicorn src.checky.web_app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the BSD 2-Clause License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [Pipecat](https://github.com/pipecat-ai/pipecat) - The foundation framework
- [Google Cloud](https://cloud.google.com/) - Speech and AI services
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework