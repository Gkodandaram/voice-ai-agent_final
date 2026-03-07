# main.py - Main FastAPI application entry point

import logging
import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager

from backend.database import init_db
from backend.routes.appointment_routes import router as appointment_router
from backend.routes.websocket_handler import handle_voice_websocket
from scheduler.outbound_campaign import setup_scheduler, stop_scheduler
from config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ==========================================
# APP LIFECYCLE
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("🚀 Starting 2Care.ai Voice AI Agent...")

    # Initialize database
    try:
        init_db()
    except Exception as e:
        logger.warning(f"DB init warning: {e}")

    # Start outbound campaign scheduler
    try:
        setup_scheduler()
    except Exception as e:
        logger.warning(f"Scheduler warning: {e}")

    logger.info("✅ Voice AI Agent is ready!")
    logger.info(f"📡 API: http://{settings.app_host}:{settings.app_port}")
    logger.info(f"🔌 WebSocket: ws://{settings.app_host}:{settings.app_port}/ws/voice/{{patient_id}}")
    logger.info(f"📚 Docs: http://{settings.app_host}:{settings.app_port}/docs")

    yield

    # Shutdown
    stop_scheduler()
    logger.info("🛑 Voice AI Agent stopped")


# ==========================================
# APP INITIALIZATION
# ==========================================

app = FastAPI(
    title="2Care.ai Voice AI Agent",
    description="Real-Time Multilingual Voice AI for Clinical Appointment Booking",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include REST routes
app.include_router(appointment_router)


# ==========================================
# WEBSOCKET ENDPOINTS
# ==========================================

@app.websocket("/ws/voice/{patient_id}")
async def voice_websocket(websocket: WebSocket, patient_id: str):
    """
    Real-time voice WebSocket endpoint.
    Connect: ws://localhost:8000/ws/voice/{patient_id}
    Send: Binary audio (WebM format) or JSON text messages
    Receive: JSON events + Binary audio responses
    """
    await handle_voice_websocket(websocket, patient_id)


@app.websocket("/ws/voice")
async def voice_websocket_default(websocket: WebSocket):
    """Default WebSocket with test patient."""
    await handle_voice_websocket(websocket, "pat-001")


# ==========================================
# DEMO UI ENDPOINT
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def demo_ui():
    """Simple browser-based voice demo UI."""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>2Care.ai Voice AI Agent</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; background: #f5f5f5; }
        h1 { color: #2c3e50; }
        .card { background: white; padding: 20px; border-radius: 10px; margin: 20px 0; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        button { background: #3498db; color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-size: 16px; margin: 5px; }
        button:hover { background: #2980b9; }
        button.red { background: #e74c3c; }
        button.green { background: #27ae60; }
        #status { padding: 10px; border-radius: 5px; margin: 10px 0; }
        #transcript { min-height: 100px; background: #ecf0f1; padding: 10px; border-radius: 5px; }
        #response { min-height: 100px; background: #d5e8d4; padding: 10px; border-radius: 5px; }
        .latency { font-size: 12px; color: #666; font-family: monospace; }
        select { padding: 8px; border-radius: 5px; border: 1px solid #ddd; margin: 5px; }
        input[type=text] { width: 70%; padding: 8px; border-radius: 5px; border: 1px solid #ddd; margin: 5px; }
    </style>
</head>
<body>
    <h1>🏥 2Care.ai Voice AI Agent</h1>
    <p>Real-Time Multilingual Clinical Appointment Assistant</p>

    <div class="card">
        <h3>Patient & Language</h3>
        <select id="patientSelect">
            <option value="pat-001">Ravi Kumar (English)</option>
            <option value="pat-002">Anita Singh (Hindi)</option>
            <option value="pat-003">Murugan Selvam (Tamil)</option>
        </select>
        <select id="langSelect">
            <option value="en">English</option>
            <option value="hi">Hindi</option>
            <option value="ta">Tamil</option>
        </select>
    </div>

    <div class="card">
        <h3>Voice Input</h3>
        <button id="recordBtn" class="green" onclick="toggleRecording()">🎙️ Start Recording</button>
        <button onclick="disconnect()" class="red">Disconnect</button>
        <div id="status" style="background:#ffeaa7;">Not connected</div>
    </div>

    <div class="card">
        <h3>Text Input (Testing)</h3>
        <input type="text" id="textInput" placeholder="Type your request... e.g. 'Book appointment with cardiologist tomorrow'" />
        <button onclick="sendText()">Send</button>
        <br><small>Try: "Book appointment", "Cancel my appointment", "Reschedule to Friday"</small>
    </div>

    <div class="card">
        <h3>📝 Transcript</h3>
        <div id="transcript">—</div>
    </div>

    <div class="card">
        <h3>🤖 Agent Response</h3>
        <div id="response">—</div>
        <div id="latency" class="latency"></div>
    </div>

    <audio id="audioPlayer" autoplay></audio>

    <script>
        let ws = null;
        let mediaRecorder = null;
        let audioChunks = [];
        let isRecording = false;

        async function connect() {
            const patientId = document.getElementById('patientSelect').value;
            const wsUrl = `ws://localhost:8000/ws/voice/${patientId}`;
            
            ws = new WebSocket(wsUrl);
            ws.binaryType = 'arraybuffer';

            ws.onopen = () => {
                document.getElementById('status').style.background = '#d4edda';
                document.getElementById('status').textContent = '✅ Connected to Voice AI Agent';
            };

            ws.onmessage = (event) => {
                if (event.data instanceof ArrayBuffer) {
                    // Audio response - play it
                    const blob = new Blob([event.data], { type: 'audio/mp3' });
                    const url = URL.createObjectURL(blob);
                    document.getElementById('audioPlayer').src = url;
                } else {
                    // JSON message
                    const msg = JSON.parse(event.data);
                    handleMessage(msg);
                }
            };

            ws.onclose = () => {
                document.getElementById('status').style.background = '#f8d7da';
                document.getElementById('status').textContent = '❌ Disconnected';
            };
        }

        function handleMessage(msg) {
            if (msg.type === 'transcription') {
                document.getElementById('transcript').textContent = 
                    `"${msg.text}" (${msg.language}, confidence: ${(msg.confidence * 100).toFixed(0)}%)`;
            } else if (msg.type === 'agent_response') {
                document.getElementById('response').textContent = msg.text;
            } else if (msg.type === 'audio_ready') {
                const l = msg.latency;
                document.getElementById('latency').textContent = 
                    `STT: ${l.stt_ms}ms | Agent: ${l.agent_ms}ms | TTS: ${l.tts_ms}ms | Total: ${l.total_ms}ms ${l.within_target ? '✅' : '⚠️'}`;
            }
        }

        async function toggleRecording() {
            if (!ws || ws.readyState !== WebSocket.OPEN) {
                await connect();
                await new Promise(r => setTimeout(r, 500));
            }

            if (!isRecording) {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
                audioChunks = [];

                mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
                mediaRecorder.onstop = () => {
                    const blob = new Blob(audioChunks, { type: 'audio/webm' });
                    blob.arrayBuffer().then(buf => ws.send(buf));
                };

                mediaRecorder.start();
                isRecording = true;
                document.getElementById('recordBtn').textContent = '⏹️ Stop Recording';
                document.getElementById('recordBtn').className = 'red';
            } else {
                mediaRecorder.stop();
                isRecording = false;
                document.getElementById('recordBtn').textContent = '🎙️ Start Recording';
                document.getElementById('recordBtn').className = 'green';
            }
        }

        async function sendText() {
            if (!ws || ws.readyState !== WebSocket.OPEN) {
                await connect();
                await new Promise(r => setTimeout(r, 500));
            }
            const text = document.getElementById('textInput').value;
            const lang = document.getElementById('langSelect').value;
            if (text) {
                ws.send(JSON.stringify({ type: 'text_input', text, language: lang }));
                document.getElementById('textInput').value = '';
                document.getElementById('transcript').textContent = `You: "${text}"`;
            }
        }

        function disconnect() {
            if (ws) { ws.close(); ws = null; }
        }

        document.getElementById('textInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendText();
        });

        // Auto-connect on load
        connect();
    </script>
</body>
</html>
"""


# ==========================================
# RUN
# ==========================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
        log_level="info",
    )
