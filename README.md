# Automated YouTube Story Publishing Engine

A production-hardened, automated Python pipeline that creates and publishes viral folklore stories, comic satires, and educational tales directly to YouTube.

## 🚀 Features

- **Scene-by-Scene Audio-Visual Synchronization**: Discrete scene narration and visual prompts pinned 1:1 with millisecond precision.
- **Natural Hindi Voiceovers**: Powered by `edge-tts` (`hi-IN-MadhurNeural`) tuned to 1.65x playback speed for engaging pacing.
- **State-of-the-Art Visuals**: Generates high-definition illustrations using FLUX via Pollinations AI.
- **Automated YouTube Publishing**: Resumable chunked video uploads with OAuth2 token auto-refresh via YouTube Data API v3.
- **Schedule Logic**:
  - **Shorts (9:16)**: Mon, Wed, Fri (3-4 scenes, under 50s).
  - **Long Form (16:9)**: Tue, Sat, Sun, Thu (7-9 scenes, 3-4 mins).
- **Anti-Repetition Tracking**: Local history tracking in `generated_history.json`.
- **Fault-Tolerant Resiliency**: Multi-tier retry logic with exponential backoff (`tenacity`) and fallback handlers.

## 📁 Project Structure

```
├── main.py                  # Master pipeline runner with execution logging
├── gemini_storyteller.py    # LLM prompt engineering, schema validation & schedule logic
├── media_engine.py          # Per-scene TTS, FLUX image fetch & MoviePy assembly
├── uploader.py              # YouTube Data API v3 resumable upload handler
├── automation_log.bat       # Windows Task Scheduler batch runner
├── generated_history.json   # Deduplication history tracking
├── .env.example             # Template for configuration
└── requirements.txt         # Project dependencies
```

## 🛠️ Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone <repo-url>
   cd "Yt Automation"
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   - Copy `.env.example` to `.env` and fill in any API keys.
   - Place your Google OAuth `client_secrets.json` in the root folder.

4. **Run the Automation**:
   ```bash
   python main.py
   ```

5. **Schedule Daily Auto-Runs (Windows)**:
   ```powershell
   schtasks /create /tn "YouTubeDailyAutomation" /tr "%CD%\automation_log.bat" /sc daily /st 09:00 /f
   ```
