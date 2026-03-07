# backend/routes/websocket_handler.py
# Real-time WebSocket handler for voice AI pipeline

import asyncio
import json
import logging
import time
import uuid
from fastapi import WebSocket, WebSocketDisconnect

from services.speech_to_text.whisper_stt import get_stt_service
from services.text_to_speech.edge_tts_service import get_tts_service
from services.language_detection.detector import get_language_detector
from agent.reasoning.groq_agent import VoiceAIAgent
from memory.session_memory.redis_memory import get_memory_service
from backend.database import SessionLocal
from config import settings

logger = logging.getLogger(__name__)

# Initialize services (singletons)
stt_service = get_stt_service(settings.whisper_model)
tts_service = get_tts_service()
lang_detector = get_language_detector()
agent = VoiceAIAgent()
memory = get_memory_service()


class VoicePipeline:
    """
    End-to-end real-time voice pipeline.
    
    Flow:
    Audio bytes → STT → Language Detection → LLM Agent → Tool Calls → TTS → Audio bytes
    
    Target latency: < 450ms
    """

    async def process_audio(
        self,
        audio_bytes: bytes,
        session_id: str,
        patient_id: str,
        websocket: WebSocket,
    ) -> None:
        """
        Process audio input and send audio response via WebSocket.
        """
        pipeline_start = time.time()
        latency_breakdown = {}

        try:
            # ========================================
            # STAGE 1: Speech-to-Text
            # ========================================
            stt_start = time.time()
            text, whisper_lang, stt_latency = stt_service.transcribe_webm(audio_bytes)
            latency_breakdown["stt_ms"] = round(stt_latency, 2)

            if not text:
                await self._send_json(websocket, {
                    "type": "error",
                    "message": "Could not understand audio. Please try again.",
                })
                return

            logger.info(f"📝 Transcribed: '{text}' ({stt_latency:.1f}ms)")

            # ========================================
            # STAGE 2: Language Detection
            # ========================================
            lang_start = time.time()
            session = memory.get_session(session_id)
            
            language, confidence = lang_detector.detect(text, whisper_lang)
            
            # Update session language
            if confidence > 0.7:
                session["language"] = language
                memory.update_session(session_id, {"language": language})

            lang_latency = (time.time() - lang_start) * 1000
            latency_breakdown["lang_ms"] = round(lang_latency, 2)

            # Send transcription to client
            await self._send_json(websocket, {
                "type": "transcription",
                "text": text,
                "language": language,
                "confidence": confidence,
            })

            # ========================================
            # STAGE 3: LLM Agent Processing
            # ========================================
            agent_start = time.time()

            # Add user message to history
            memory.add_message_to_session(session_id, "user", text)
            conversation_history = memory.get_conversation_history(session_id)

            # Process with AI agent
            db = SessionLocal()
            try:
                response_text, action_result, agent_latency = await agent.process(
                    user_text=text,
                    language=language,
                    session_id=session_id,
                    patient_id=patient_id,
                    conversation_history=conversation_history[:-1],  # Exclude current
                    db_session=db,
                )
            finally:
                db.close()

            latency_breakdown["agent_ms"] = round(agent_latency, 2)

            # Save agent response to history
            memory.add_message_to_session(session_id, "assistant", response_text)

            # Send text response to client
            await self._send_json(websocket, {
                "type": "agent_response",
                "text": response_text,
                "action": action_result,
                "language": language,
            })

            # ========================================
            # STAGE 4: Text-to-Speech
            # ========================================
            tts_start = time.time()
            audio_response, tts_latency = await tts_service.synthesize(
                response_text, language
            )
            latency_breakdown["tts_ms"] = round(tts_latency, 2)

            # ========================================
            # TOTAL LATENCY
            # ========================================
            total_latency = (time.time() - pipeline_start) * 1000
            latency_breakdown["total_ms"] = round(total_latency, 2)
            latency_breakdown["target_ms"] = settings.latency_target_ms
            latency_breakdown["within_target"] = total_latency < settings.latency_target_ms

            # Log latency metrics
            memory.log_latency(session_id, "stt", stt_latency)
            memory.log_latency(session_id, "agent", agent_latency)
            memory.log_latency(session_id, "tts", tts_latency)
            memory.log_latency(session_id, "total", total_latency)

            logger.info(
                f"⏱️ Pipeline latency: STT={stt_latency:.0f}ms | "
                f"Agent={agent_latency:.0f}ms | TTS={tts_latency:.0f}ms | "
                f"Total={total_latency:.0f}ms "
                f"({'✅' if total_latency < 450 else '⚠️'})"
            )

            # Send audio response
            await self._send_json(websocket, {
                "type": "audio_ready",
                "latency": latency_breakdown,
            })

            # Send audio bytes
            if audio_response:
                await websocket.send_bytes(audio_response)

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            await self._send_json(websocket, {
                "type": "error",
                "message": "Pipeline error. Please try again.",
            })

    async def _send_json(self, websocket: WebSocket, data: dict) -> None:
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.error(f"WebSocket send error: {e}")


# ==========================================
# WEBSOCKET ENDPOINT HANDLER
# ==========================================

pipeline = VoicePipeline()


async def handle_voice_websocket(websocket: WebSocket, patient_id: str = "pat-001"):
    """
    Main WebSocket handler for voice conversations.
    
    URL: ws://localhost:8000/ws/voice/{patient_id}
    """
    session_id = str(uuid.uuid4())
    
    await websocket.accept()
    logger.info(f"🔌 WebSocket connected: session={session_id}, patient={patient_id}")

    # Initialize session
    memory.update_session(session_id, {
        "patient_id": patient_id,
        "language": "en",
        "messages": [],
    })

    # Send welcome message
    await websocket.send_json({
        "type": "connected",
        "session_id": session_id,
        "message": "Connected to Voice AI Agent",
    })

    try:
        while True:
            data = await websocket.receive()

            if "bytes" in data:
                # Audio data received
                audio_bytes = data["bytes"]
                logger.info(f"🎙️ Audio received: {len(audio_bytes)} bytes")

                await pipeline.process_audio(
                    audio_bytes=audio_bytes,
                    session_id=session_id,
                    patient_id=patient_id,
                    websocket=websocket,
                )

            elif "text" in data:
                # Text command received
                msg = json.loads(data["text"])

                if msg.get("type") == "text_input":
                    # Handle text input (for testing without mic)
                    text = msg.get("text", "")
                    language = msg.get("language", "en")

                    memory.add_message_to_session(session_id, "user", text)
                    history = memory.get_conversation_history(session_id)

                    db = SessionLocal()
                    try:
                        response_text, action_result, latency = await agent.process(
                            user_text=text,
                            language=language,
                            session_id=session_id,
                            patient_id=patient_id,
                            conversation_history=history[:-1],
                            db_session=db,
                        )
                    finally:
                        db.close()

                    memory.add_message_to_session(session_id, "assistant", response_text)

                    audio_bytes, tts_latency = await tts_service.synthesize(
                        response_text, language
                    )

                    await websocket.send_json({
                        "type": "agent_response",
                        "text": response_text,
                        "action": action_result,
                        "latency_ms": round(latency, 2),
                    })

                    if audio_bytes:
                        await websocket.send_bytes(audio_bytes)

                elif msg.get("type") == "get_latency":
                    report = memory.get_latency_report(session_id)
                    await websocket.send_json({
                        "type": "latency_report",
                        "report": report,
                    })

                elif msg.get("type") == "end_session":
                    await websocket.send_json({
                        "type": "session_ended",
                        "session_id": session_id,
                    })
                    break

    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket disconnected: session={session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        latency_report = memory.get_latency_report(session_id)
        logger.info(f"📊 Session {session_id} latency report: {latency_report}")
