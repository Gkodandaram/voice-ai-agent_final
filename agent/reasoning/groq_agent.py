# agent/reasoning/groq_agent.py
# AI Agent using Groq (Llama 3.1 70B) - Free & Fast

import json
import time
import logging
from groq import Groq
from config import settings
from agent.prompt.system_prompts import get_system_prompt
from agent.tools.tool_definitions import TOOLS, execute_tool

logger = logging.getLogger(__name__)

client = Groq(api_key=settings.groq_api_key)


class VoiceAIAgent:
    """
    Core AI Agent for appointment management.
    Uses Groq (Llama 3.1 70B) for fast reasoning.
    Supports English, Hindi, Tamil.
    """

    def __init__(self):
        self.model = settings.groq_model
        logger.info(f"✅ AI Agent initialized with model: {self.model}")

    async def process(
        self,
        user_text: str,
        language: str,
        session_id: str,
        patient_id: str,
        conversation_history: list,
        db_session,
    ) -> tuple[str, dict, float]:
        """
        Process user input and return agent response.

        Args:
            user_text: Transcribed user speech
            language: Detected language (en/hi/ta)
            session_id: Current session ID
            patient_id: Patient identifier
            conversation_history: Prior conversation messages
            db_session: Database session

        Returns:
            Tuple of (response_text, action_result, latency_ms)
        """
        start_time = time.time()

        # Build messages for LLM
        system_prompt = get_system_prompt(language, patient_id)

        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history (last 10 turns)
        for msg in conversation_history[-10:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        # Add current user message
        messages.append({"role": "user", "content": user_text})

        action_result = {}

        try:
            # First LLM call - get intent and tool call
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=1000,
                temperature=0.3,
            )

            message = response.choices[0].message
            tool_calls = message.tool_calls

            if tool_calls:
                # Execute tool calls
                tool_results = []
                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)

                    # Add patient_id and db session to all tool calls
                    tool_args["patient_id"] = patient_id
                    tool_args["db_session"] = db_session

                    logger.info(f"🔧 Tool call: {tool_name}({tool_args})")

                    result = execute_tool(tool_name, tool_args)
                    action_result = result

                    tool_results.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps(result),
                    })

                # Add assistant message with tool calls
                messages.append({
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                })

                # Add tool results
                messages.extend(tool_results)

                # Second LLM call - generate natural response
                final_response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=500,
                    temperature=0.5,
                )

                response_text = final_response.choices[0].message.content

            else:
                # No tool call needed - direct response
                response_text = message.content

            latency_ms = (time.time() - start_time) * 1000
            logger.info(f"🤖 Agent: '{response_text[:80]}...' | {latency_ms:.1f}ms")

            return response_text, action_result, latency_ms

        except Exception as e:
            logger.error(f"Agent error: {e}")
            fallback = self._get_fallback_message(language)
            latency_ms = (time.time() - start_time) * 1000
            return fallback, {}, latency_ms

    def _get_fallback_message(self, language: str) -> str:
        messages = {
            "en": "I'm sorry, I had trouble processing that. Could you please repeat?",
            "hi": "मुझे खेद है, मैं आपकी बात समझ नहीं पाया। कृपया दोबारा कहें।",
            "ta": "மன்னிக்கவும், நான் புரிந்துகொள்ளவில்லை. மீண்டும் சொல்லுங்கள்.",
        }
        return messages.get(language, messages["en"])
