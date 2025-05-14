import json
import os
import signal
import sys

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation, ConversationInitiationData
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
from elevenlabs.core import RequestOptions

load_dotenv()

agent_id = os.getenv("AGENT_ID")
api_key = os.getenv("ELEVENLABS_API_KEY")


# Check if required environment variables are set
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
    # API client and agent ID.
    client,
    agent_id,
    # Assume auth is required when API_KEY is set.
    requires_auth=bool(api_key),
    # Use the default audio interface.
    audio_interface=DefaultAudioInterface(),
    # parameters
    config=config,
    # Simple callbacks that print the conversation to the console.
    callback_agent_response=lambda response: print(f"Agent: {response}"),
    callback_agent_response_correction=lambda original, corrected: print(f"Agent: {original} -> {corrected}"),
    callback_user_transcript=lambda transcript: print(f"User: {transcript}"),
    # Uncomment if you want to see latency measurements.
    # callback_latency_measurement=lambda latency: print(f"Latency: {latency}ms"),
)


try:
    conversation.start_session()
    signal.signal(signal.SIGINT, lambda sig, frame: conversation.end_session())
    conversation_id = conversation.wait_for_session_end()
    print(f"Conversation ID: {conversation_id}")

    # Retrieve conversation data using the conversation ID
    # conversation_data = client.conversational_ai.get_conversation_data(conversation_id=conversation_id)
    conversation_data = client.conversational_ai.get_conversation(conversation_id=conversation_id)
    # print(conversation_data.analysis.data_collection_results['consent_to_change_the_date'])

    # with open("conversation.json", "w") as conversation_file:
    #     conversation_file.write(conversation_data.analysis.json())
    #
    # with open("conversation.json", "r") as file:
    #     data = json.load(file)
    #
    # consent_value = (data.get("data_collection_results", { })
    #                  .get("consent_to_change_the_date", { })
    #                  .get("value", None))

    print(
        json.loads(conversation_data.analysis.json())
        .get("data_collection_results", {})
        .get("consent_to_change_the_date", {})
        .get("value", None)
    )

    # print(conversation_data.analysis.dict().get('evaluation_criteria_results').get('data_collection_results').get('consent_to_change_the_date').get('value'))

    # # Extract data collection results
    # data_collection = conversation_data.get("data_collection", {})
    # # Access the consent_to_change_the_date boolean
    # consent_to_change_the_date = data_collection.get("consent_to_change_the_date", False)

    # print(f"Consent to change the date: {consent_to_change_the_date}")

except Exception as e:
    print(f"Error: {e}")
    conversation.end_session()
    sys.exit(1)
