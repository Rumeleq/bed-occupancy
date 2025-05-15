import json
import logging.config
import os
import signal
import sys
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation, ConversationInitiationData
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface

load_dotenv()

agent_id = os.getenv("AGENT_ID")
api_key = os.getenv("ELEVENLABS_API_KEY")

logger = logging.getLogger("hospital_logger")
config_file = Path("../backend/logger_config.json")
with open(config_file) as f:
    config = json.load(f)
logging.config.dictConfig(config)

if not api_key:
    logger.error("Error: ELEVENLABS_API_KEY environment variable is not set")
    sys.exit(1)

if not agent_id:
    logger.error("Error: AGENT_ID environment variable is not set")
    sys.exit(1)

client = ElevenLabs(api_key=api_key)


def prepare_conversation(
    patient_name: str, patient_surname: str, patient_sickness: str, current_visit_day: int, suggested_appointment_day: int
) -> Conversation:
    """
    Prepares a conversation session with dynamic variables for a patient.

    :param patient_name: The first name of the patient.
    :param patient_surname: The last name of the patient.
    :param patient_sickness: The sickness or condition of the patient.
    :param current_visit_day: The current day of the patient's visit.
    :param suggested_appointment_day: The suggested day for the next appointment.
    :return: A `Conversation` object configured with the provided patient details.
    """
    config = ConversationInitiationData(
        dynamic_variables={
            "patient_name": patient_name,
            "patient_surname": patient_surname,
            "patient_sickness": patient_sickness,
            "current_visit_day": current_visit_day,
            "suggested_appointment_day": suggested_appointment_day,
        }
    )

    return Conversation(
        client,
        agent_id,
        requires_auth=bool(api_key),
        audio_interface=DefaultAudioInterface(),
        config=config,
        callback_agent_response=lambda response: logger.log(f"Agent: {response}"),
        callback_agent_response_correction=lambda original, corrected: logger.log(f"Agent corrected: {corrected}"),
        callback_user_transcript=lambda transcript: logger.log(f"User: {transcript}"),
    )


def establish_voice_conversation(conversation: Conversation) -> str | None:
    """
    Establishes a voice conversation session with a patient and handles its lifecycle.

    Starts the session, waits for it to end, and captures the conversation ID.
    Handles interruptions (e.g., SIGINT) and ensures the session is properly terminated in case of errors.

    :param conversation: The `Conversation` object representing the session.
    :return: The conversation ID as a string if successful, or `None` if an error occurs.
    """
    try:
        conversation.start_session()
        signal.signal(signal.SIGINT, lambda sig, frame: conversation.end_session())
        conversation_id = conversation.wait_for_session_end()
        logger.info(f"Conversation ID: {conversation_id}")
        return conversation_id

    except Exception as e:
        logger.error(f"Error: {e}")
        conversation.end_session()
        return None


def check_patient_consent_to_reschedule(conversation_id: str) -> bool:
    """
    Checks if the patient has given consent to reschedule their appointment
    based on the analysis of the conversation data.

    :param conversation_id: The ID of the conversation to analyze.
    :return: A boolean indicating whether the patient agreed to reschedule.
    """
    conversation_data = client.conversational_ai.get_conversation(conversation_id=conversation_id)

    result: bool = (
        json.loads(conversation_data.analysis.json())
        .get("data_collection_results", {})
        .get("consent_to_change_the_date", {})
        .get("value", None)
    )
    logger.info(f"Patient agreed: {result}")
    return result
