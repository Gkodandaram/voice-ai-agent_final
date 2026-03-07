# 🏥 2Care.ai — Real-Time Multilingual Voice AI Agent

A production-ready Voice AI system for clinical appointment booking, supporting English, Hindi, and Tamil with sub-450ms response latency.

---

## 🎯 Features

| Feature | Details |
|---|---|
| **Languages** | English, Hindi, Tamil (auto-detected) |
| **Actions** | Book, Cancel, Reschedule appointments |
| **STT** | OpenAI Whisper (local, free) |
| **LLM** | Groq Llama 3.1 70B (free tier) |
| **TTS** | Microsoft Edge TTS (free, neural voices) |
| **Memory** | Redis (session + persistent) |
| **Latency Target** | < 450ms end-to-end |
| **Transport** | WebSockets (real-time) |

---

## 🏗️ Architecture

```
User Speech
     │
     ▼
┌─────────────────┐
│  WebSocket      │  ← Real-time audio stream
│  (FastAPI)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Whisper STT    │  ← Speech → Text (~120ms)
│  (local, free)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Language       │  ← Detect: en/hi/ta (~5ms)
│  Detector       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐    ┌──────────────────┐
│  Groq LLM Agent │───▶│  Tool Executor   │
│  (Llama 3.1 70B)│    │  - checkAvail    │
│  (~200ms)       │    │  - bookAppt      │
└────────┬────────┘    │  - cancelAppt    │
         │             │  - reschedule    │
         │             └────────┬─────────┘
         │                      │
         │             ┌────────▼─────────┐
         │             │  PostgreSQL DB   │
         │             │  + Appointment   │
         │             │    Engine        │
         │             └──────────────────┘
         ▼
┌─────────────────┐    ┌──────────────────┐
│  Edge TTS       │    │  Redis Memory    │
│  (~100ms)       │    │  - Session       │
└────────┬────────┘    │  - Persistent    │
         │             └──────────────────┘
         ▼
   Audio Response
```

---

## ⚡ Latency Breakdown

| Stage | Target | Typical |
|---|---|---|
| Speech-to-Text (Whisper base) | < 150ms | ~120ms |
| Language Detection | < 10ms | ~5ms |
| LLM Agent (Groq) | < 250ms | ~200ms |
| Text-to-Speech (Edge TTS) | < 120ms | ~100ms |
| **Total** | **< 450ms** | **~425ms** |

---

## 🧠 Memory Design

### Session Memory (Redis, TTL: 1 hour)
Stores current conversation context:
```json
{
  "messages": [...],
  "intent": "book",
  "pending_data": { "doctor": "cardiologist" },
  "language": "hi",
  "patient_id": "pat-001"
}
```

### Persistent Memory (Redis, TTL: 30 days)
Stores patient long-term preferences:
```json
{
  "preferred_language": "hi",
  "preferred_doctor": "Dr. Sharma",
  "preferred_hospital": "Apollo",
  "past_appointments": [...]
}
```

---

## 🚀 Quick Start

### Option A: Docker (Recommended)

```bash
# 1. Clone and setup
git clone <repo>
cd voice-ai-agent

# 2. Set your Groq API key (free at console.groq.com)
cp .env.example .env
# Edit .env and add: GROQ_API_KEY=your_key_here

# 3. Start all services
docker-compose up --build

# 4. Open browser
open http://localhost:8000
```

### Option B: Local Development

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start PostgreSQL and Redis
docker-compose up postgres redis -d

# 3. Configure environment
cp .env.example .env
# Add your GROQ_API_KEY

# 4. Run the application
python main.py

# 5. Run tests
pytest tests/ -v
```

---

## 🔌 WebSocket API

Connect to:
```
ws://localhost:8000/ws/voice/{patient_id}
```

### Send Audio (binary):
```javascript
ws.send(audioBlob);  // WebM format from browser
```

### Send Text (JSON):
```javascript
ws.send(JSON.stringify({
  type: "text_input",
  text: "Book appointment with cardiologist tomorrow",
  language: "en"
}));
```

### Receive Events:
```javascript
// Transcription
{ type: "transcription", text: "...", language: "en", confidence: 0.95 }

// Agent response
{ type: "agent_response", text: "...", action: {...} }

// Latency metrics
{ type: "audio_ready", latency: { stt_ms: 120, agent_ms: 200, tts_ms: 95, total_ms: 415 } }

// Binary: MP3 audio bytes
```

---

## 🌐 REST API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/doctors` | List all doctors |
| GET | `/api/availability/{doctor_id}/{date}` | Check availability |
| POST | `/api/appointments/book` | Book appointment |
| POST | `/api/appointments/cancel` | Cancel appointment |
| POST | `/api/appointments/reschedule` | Reschedule |
| GET | `/api/appointments/{patient_id}` | Patient appointments |

Interactive docs: http://localhost:8000/docs

---

## 🗣️ Sample Conversations

### English
```
User: Book appointment with cardiologist tomorrow
Agent: Dr. Rajesh Sharma is available tomorrow. Available slots: 9:00, 10:00, 14:00. Which time works?
User: 10 AM
Agent: Your appointment with Dr. Rajesh Sharma is confirmed for tomorrow at 10:00 AM at Apollo Hospital!
```

### Hindi
```
User: मुझे कल डॉक्टर से मिलना है
Agent: कल डॉ. राजेश शर्मा उपलब्ध हैं। समय: 9:00, 10:00, 14:00। कौन सा समय ठीक रहेगा?
User: दोपहर 2 बजे
Agent: आपकी अपॉइंटमेंट कल दोपहर 2 बजे बुक हो गई है।
```

### Tamil
```
User: நாளை மருத்துவரை பார்க்க வேண்டும்
Agent: நாளை டாக்டர் ராஜேஷ் ஷர்மா கிடைக்கிறார். நேரங்கள்: 9:00, 10:00, 14:00. எந்த நேரம் வசதி?
User: காலை 10 மணி
Agent: நாளை காலை 10:00 மணிக்கு அப்பல்லோ மருத்துவமனையில் உங்கள் சந்திப்பு உறுதி செய்யப்பட்டது!
```

---

## 📊 Database Schema

```sql
-- Patients
patients (id, name, phone, preferred_language, preferred_doctor, preferred_hospital)

-- Doctors  
doctors (id, name, specialization, hospital, is_active)

-- Doctor Schedule
doctor_schedules (id, doctor_id, date, available_slots JSON)

-- Appointments
appointments (id, patient_id, doctor_id, date, time, status, notes)

-- Call Logs
call_logs (id, session_id, patient_id, language_detected, transcript, avg_latency_ms)
```

---

## ⚖️ Trade-offs & Decisions

| Decision | Trade-off |
|---|---|
| Whisper local vs API | Slower cold start but free and private |
| Groq vs OpenAI | Groq is faster (< 200ms) and free tier |
| Edge TTS vs ElevenLabs | Less natural but completely free |
| Redis fallback to in-memory | Development friendly, production needs Redis |
| Llama 3.1 70B vs smaller | Better reasoning, slightly more latency |

---

## ⚠️ Known Limitations

1. **Whisper cold start**: First request takes 2-3s to load model
2. **Tamil TTS**: Edge TTS Tamil voice is less natural than English/Hindi
3. **Concurrent users**: Single Whisper instance; scale with multiple workers
4. **Groq rate limits**: Free tier has token limits; may need queuing at scale
5. **Audio format**: Expects WebM from browser; needs ffmpeg for other formats

---

## 📁 Project Structure

```
voice-ai-agent/
├── main.py                          # FastAPI app + demo UI
├── config.py                        # Central configuration
├── requirements.txt                 # Python dependencies
├── Dockerfile                       # Docker image
├── docker-compose.yml               # Full stack deployment
├── .env.example                     # Environment template
│
├── backend/
│   ├── models.py                    # SQLAlchemy DB models
│   ├── database.py                  # DB connection + seeding
│   └── routes/
│       ├── appointment_routes.py    # REST API endpoints
│       └── websocket_handler.py     # Real-time voice pipeline
│
├── agent/
│   ├── prompt/system_prompts.py     # Multilingual LLM prompts
│   ├── reasoning/groq_agent.py      # Groq LLM agent
│   └── tools/tool_definitions.py    # Tool calling definitions
│
├── services/
│   ├── speech_to_text/whisper_stt.py     # STT service
│   ├── text_to_speech/edge_tts_service.py # TTS service
│   └── language_detection/detector.py    # Language detection
│
├── memory/
│   └── session_memory/redis_memory.py    # Session + persistent memory
│
├── scheduler/
│   ├── appointment_engine/engine.py  # Booking logic
│   └── outbound_campaign.py          # Reminder campaigns
│
└── tests/
    └── test_system.py                # Test suite
```

---

## 🔑 Environment Variables

| Variable | Description | Default |
|---|---|---|
| `GROQ_API_KEY` | **Required** — Get free at console.groq.com | — |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://...` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `WHISPER_MODEL` | tiny/base/small/medium | `base` |
| `GROQ_MODEL` | Groq model ID | `llama-3.1-70b-versatile` |
| `LATENCY_TARGET_MS` | Target latency threshold | `450` |
