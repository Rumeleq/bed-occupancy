import json
import logging.config
import os
import signal
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from elevenlabs.conversational_ai.conversation import (
    Conversation,
    ConversationInitiationData,
)

load_dotenv()

agent_id = os.getenv("AGENT_ID")
ua_agent_id = os.getenv("AGENT_UA_ID")
api_key = os.getenv("ELEVENLABS_API_KEY")
agent_phone_number_id = os.getenv("AGENT_PHONE_NUMBER_ID")

logger = logging.getLogger("hospital_logger")
config_file = Path("./logger_config.json")
with open(config_file) as f:
    config = json.load(f)
logging.config.dictConfig(config)

if not api_key:
    logger.error("Error: ELEVENLABS_API_KEY environment variable is not set")
    sys.exit(1)

if not agent_id:
    logger.error("Error: AGENT_ID environment variable is not set")
    sys.exit(1)

if not agent_phone_number_id:
    logger.error("Error: AGENT_PHONE_NUMBER_ID environment variable is not set")
    sys.exit(1)

client = ElevenLabs(api_key=api_key)


def call_patient(
    patient_name: str,
    patient_surname: str,
    gender: str,
    pesel: str,
    patient_sickness: str,
    current_visit_day: int,
    suggested_appointment_day: int,
    use_ua_agent: bool,
    phone_to_call: str,
) -> str | None:
    """
    Calls a patient using the ElevenLabs API and initiates a conversation.

    :param patient_name: The first name of the patient.
    :param patient_surname: The last name of the patient.
    :param gender: The gender of the patient.
    :param pesel: The pesel of the patient.
    :param patient_sickness: The sickness or condition of the patient.
    :param current_visit_day: The current day of the patient's visit.
    :param suggested_appointment_day: The suggested day for the next appointment.
    :param use_ua_agent: Whether to use the UA agent for the call.
    :return: The conversation ID if the call was successful, or `None` if an error occurred.
    """
    conversation_initiation_client_data = ConversationInitiationData(
        dynamic_variables={
            "patient_name": patient_name,
            "patient_surname": patient_surname,
            "gender": gender,
            "personal_number": pesel,
            "patient_sickness": patient_sickness,
            "current_visit_day": current_visit_day,
            "suggested_appointment_day": suggested_appointment_day,
        }
    )
    try:
        response = client.conversational_ai.twilio_outbound_call(
            agent_id=(agent_id if not use_ua_agent else ua_agent_id),
            agent_phone_number_id=agent_phone_number_id,
            to_number="+48" + phone_to_call,
            conversation_initiation_client_data=conversation_initiation_client_data,
        )
        logger.info(f"Conversation ID: {response.conversation_id}")
        return response.conversation_id
    except Exception as e:
        logger.error(f"Error: {e}")
        return None


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


def get_done_conversation_data(conversation_id: str, max_attempts: int = 60, attempt_interval: int = 5) -> str:
    """
    Waits until the conversation is completed and then returns its data in json format

    :param conversation_id: The ID of the conversation to fetch the data.
    :param max_attempts: Maximum number of times the API is called in order to get data that has 'status' == 'done'
    :param attempt_interval: Seconds between API calls
    :return: JSON as string - needs to be parsed to python dict
    """
    for attempt in range(max_attempts):
        conversation_data = client.conversational_ai.get_conversation(conversation_id=conversation_id)
        status = conversation_data.status
        if status == "done":
            return conversation_data
        logger.info(f"Conversation status: {status} (Attempt {attempt + 1})")
        time.sleep(attempt_interval)
    else:
        logger.warning("Conversation did not complete in time.")
        return False


def check_patient_consent_to_reschedule(conversation_id: str) -> dict:
    """
    Waits until the conversation is completed and then checks if the patient
    has given consent to reschedule their appointment.

    :param conversation_id: The ID of the conversation to analyze.
    :return: A dictionary containing:
    - 'consent' (bool): Indicates whether the patient agreed to reschedule.
    - 'verified' (bool): Indicates whether the verification was successful.
    - 'called' (bool): Always True, indicating the function was executed.
    """
    conversation_data = get_done_conversation_data(conversation_id)
    result: bool = (
        json.loads(conversation_data.analysis.json())
        .get("data_collection_results", {})
        .get("consent_to_change_the_date", {})
        .get("value", None)
    )

    success_of_verification: bool = (
        json.loads(conversation_data.analysis.json())
        .get("data_collection_results", {})
        .get("verification_success", {})
        .get("value", None)
    )

    logger.info(f"Patient's verification status: {success_of_verification}")
    logger.info(f"Patient agreed: {result}")
    return {"consent": result, "verified": success_of_verification, "called": True}


def fetch_transcription(conversation_id: str) -> list[dict]:
    """
    Waits until the conversation is completed and then returns the transcript
    of the given conversation.

    :param conversation_id: The ID of the conversation to analyze.
    :return: List of python dictionaries that has 2 keys: "role" and "message"
    """
    conversation_data = get_done_conversation_data(conversation_id)
    # get transcript of the call
    transcript: list[dict] = json.loads(conversation_data.json()).get("transcript")
    # filter out transcript to have only roles and messages without empty messages or situations of using an agent tool such as 'end_call'
    transcript = [{"role": entry["role"], "message": entry["message"]} for entry in transcript]
    transcript = list(filter(lambda data: data["message"] is not None, transcript))

    return transcript
