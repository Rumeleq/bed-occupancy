import json
import os
import signal
import sys

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation, ConversationInitiationData
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface

load_dotenv()

agent_id = os.getenv("AGENT_ID")
api_key = os.getenv("ELEVENLABS_API_KEY")

if not api_key:
    print("Error: ELEVENLABS_API_KEY environment variable is not set")
    sys.exit(1)

if not agent_id:
    print("Error: AGENT_ID environment variable is not set")
    sys.exit(1)

client = ElevenLabs(api_key=api_key)

config = ConversationInitiationData(
    dynamic_variables={
        "patient_name": "Jan",
        "patient_surname": "Topolewski",
        "patient_sickness": "zapalenie kolana",
        "current_visit_day": 10,
        "suggested_appointment_day": 5,
    }
)

conversation = Conversation(
    client,
    agent_id,
    requires_auth=bool(api_key),
    audio_interface=DefaultAudioInterface(),
    config=config,
    callback_agent_response=lambda response: print(f"Agent: {response}"),
    callback_agent_response_correction=lambda original, corrected: print(f"Agent: {original} -> {corrected}"),
    callback_user_transcript=lambda transcript: print(f"User: {transcript}"),
)


try:
    conversation.start_session()
    signal.signal(signal.SIGINT, lambda sig, frame: conversation.end_session())
    conversation_id = conversation.wait_for_session_end()
    print(f"Conversation ID: {conversation_id}")

    conversation_data = client.conversational_ai.get_conversation(conversation_id=conversation_id)

    print(
        json.loads(conversation_data.analysis.json())
        .get("data_collection_results", {})
        .get("consent_to_change_the_date", {})
        .get("value", None)
    )

except Exception as e:
    print(f"Error: {e}")
    conversation.end_session()
    sys.exit(1)
