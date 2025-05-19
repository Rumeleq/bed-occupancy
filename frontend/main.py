import logging.config
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import requests
import streamlit as st
from agent import *

logger = logging.getLogger("hospital_logger")
config_file = Path("./logger_config.json")
with open(config_file) as f:
    config = json.load(f)
logging.config.dictConfig(config)


if "day_for_simulation" not in st.session_state:
    logger.info("setting page up for first time")
    st.session_state.day_for_simulation = requests.get("http://backend:8000/get-current-day").json()["day"]
    st.session_state.only_patients_from_call = False
st.set_page_config(page_title="Hospital bed management", page_icon="🏥")
st.title("Bed Assignments")
st.header(f"Day {st.session_state.day_for_simulation}")
placeholder = st.empty()
logger.info("page set up successfully")

st.html(
    """
    <style>
        section[data-testid="stSidebar"]{
            width: 30% !important;
        }
        section[data-testid="stMain"]{
            width: 70% !important;
        }
    </style>
    """
)


def handle_patient_rescheduling(name: str, surname: str, pesel: str, sickness: str, old_day: int, new_day: int) -> bool:
    """
    Handles the process of rescheduling a patient's appointment by initiating a voice conversation
    with the patient and analyzing their consent.

    :param name: The first name of the patient.
    :param surname: The last name of the patient.
    :param sickness: The sickness or condition of the patient.
    :param old_day: The current day of the patient's visit.
    :param new_day: The suggested day for the new appointment.
    :return: A boolean indicating whether the patient consented to the rescheduling.
    """
    # conversation = prepare_conversation(
    #     patient_name=name,
    #     patient_surname=surname,
    #     pesel=pesel,
    #     patient_sickness=sickness,
    #     current_visit_day=old_day,
    #     suggested_appointment_day=new_day,
    # )
    # conversation_id = establish_voice_conversation(conversation)
    # return check_patient_consent_to_reschedule(conversation_id)
    logger.info("patient agreed")
    return True


def agent_call(patient_id: int, name: str, surname: str, pesel: str, sickness: str, old_day: int, new_day: int):
    st.session_state.consent = handle_patient_rescheduling(
        name=name, surname=surname, pesel=pesel, sickness=sickness, old_day=old_day, new_day=new_day
    )
    logger.info("calling patient...")
    if st.session_state.consent:
        logger.info("got consent, moving patient to bed")
        response = requests.get("http://backend:8000/move-patient-to-bed-assignment", params={"patient_id": patient_id})
        logger.info("setting only_patients_from_call to True")
        st.session_state.only_patients_from_call = True
        logger.info("resetting placeholder")
        global placeholder
        placeholder.empty()
        with placeholder.container():
            st.write("loading... ")
        # reload_page()
        # global queue_df, bed_df
        #
        # if not bed_df.empty:
        #     # for col in ["patient_id", "patient_name", "sickness", "days_of_stay"]:
        #     #    bed_df[col] = bed_df[col].apply(lambda x: None if x == 0 or x == "Unoccupied" else x)
        #     st.dataframe(bed_df, use_container_width=True, hide_index=True)
        # else:
        #     st.info("No bed assignments found.")
        #
        # st.sidebar.subheader("Patients in queue")
        # if not queue_df.empty:
        #     st.sidebar.dataframe(queue_df, use_container_width=True, hide_index=True)
        # else:
        #     st.sidebar.info("No patients found in the queue.")


def get_list_of_tables(only_patients_from_call: bool = False) -> Optional[Dict]:
    try:
        logger.info(f"getting list of tables, with parameter {only_patients_from_call=}...")
        response = requests.get("http://backend:8000/get-tables", params={"only_patients_from_call": only_patients_from_call})
        logger.info("got list of tables")
    except Exception as e:
        st.error(f"Failed to connect to the server: {e}")
        return None
    if response.status_code == 200:
        logger.info("returning json tables")
        return response.json()
    else:
        st.error("Failed to fetch data from the server.")
        return None


def simulate_next_day() -> None:
    logger.info("simulating next day...")
    try:
        logger.info("setting only_patients_from_call to False")
        st.session_state.only_patients_from_call = False
        logger.info("rolling back the session")
        requests.post("http://backend:8000/rollback-session")
        logger.info("updating day...")
        response = requests.get("http://backend:8000/update-day", params={"delta": 1})
        logger.info("day updated, fetching data...")
        st.session_state.day_for_simulation = response.json()["day"]
        st.session_state.error_message = None

    except Exception as e:
        st.session_state.error_message = f"Failed to connect to the server: {e}"


def simulate_previous_day() -> None:
    logger.info("simulating next day...")
    try:
        logger.info("setting only_patients_from_call to False")
        st.session_state.only_patients_from_call = False
        logger.info("rolling back the session")
        requests.post("http://backend:8000/rollback-session")
        logger.info("updating day...")
        response = requests.get("http://backend:8000/update-day", params={"delta": -1})
        logger.info("day updated, fetching data...")
        st.session_state.day_for_simulation = response.json()["day"]
        st.session_state.error_message = None
    except Exception as e:
        st.session_state.error_message = f"Failed to connect to the server: {e}"


# TODO: zrobić jakiś mechanizm lub funkcję/ cokolwiek co reprezentowałoby 1 dzień symulacji
def reload_page() -> None:
    logger.info("Starting to reload the page...")
    global placeholder
    placeholder = st.empty()
    logger.info("emptied the placeholder")
    with placeholder.container():
        logger.info("fetching tables...")
        tables = get_list_of_tables(st.session_state.only_patients_from_call)
        bed_df = pd.DataFrame(tables["BedAssignment"])
        queue_df = pd.DataFrame(tables["PatientQueue"])
        no_shows_df = pd.DataFrame(tables["NoShows"])
        logger.info("tables fetched")

        if not bed_df.empty:
            logger.info("beds are not empty, displaying beds")
            # for col in ["patient_id", "patient_name", "sickness", "days_of_stay"]:
            #     bed_df[col] = bed_df[col].apply(lambda x: None if x == 0 or x == "Unoccupied" else x)
            st.dataframe(bed_df, use_container_width=True, hide_index=True)
        else:
            logger.info("beds empty!")
            st.info("No bed assignments found.")

        if len(bed_df[bed_df["patient_id"] == 0]) > 0:
            logger.info("free beds avaiable, getting patient's data for call...")
            st.session_state.queue_id = 0
            st.session_state.patient_id = queue_df["patient_id"][st.session_state.queue_id]
            name = queue_df["patient_name"][st.session_state.queue_id].split()[0]
            surname = queue_df["patient_name"][st.session_state.queue_id].split()[1]
            pesel = queue_df["PESEL"][st.session_state.queue_id][-3:]
            logger.info("fetching additional patient's data...")
            response = requests.get("http://backend:8000/get-patient-data", params={"patient_id": st.session_state.patient_id})
            st.session_state.consent = False
            logger.info("building button")
            st.sidebar.button(
                f"Call patient {st.session_state.patient_id} {name} {surname} 📞",
                on_click=lambda: agent_call(
                    patient_id=st.session_state.patient_id,
                    name=name,
                    surname=surname,
                    pesel=pesel,
                    sickness=response.json()["sickness"],
                    old_day=response.json()["old_day"],
                    new_day=response.json()["new_day"],
                ),
            )

        st.sidebar.subheader("Patients in queue")
        if not queue_df.empty:
            logger.info("Queue is not empty, displaying queue")
            st.sidebar.dataframe(queue_df, use_container_width=True, hide_index=True)
        else:
            logger.info("queue empty!")
            st.sidebar.info("No patients found in the queue.")

        st.sidebar.subheader("Patients absent on a given day")
        if not no_shows_df.empty:
            logger.info("found no-shows, displaying them")
            st.sidebar.dataframe(no_shows_df, use_container_width=True, hide_index=True)
        else:
            logger.info("no no-shows found")
            st.sidebar.info("No no-shows found.")

        logger.info("displaying control buttons")
        if st.session_state.day_for_simulation < 20:
            st.button("➡️ Simulate Next Day", on_click=simulate_next_day)

        if st.session_state.day_for_simulation > 1:
            st.button("⬅️ Simulate Previous Day", on_click=simulate_previous_day)

        if "error_message" in st.session_state and st.session_state.error_message:
            logger.info("displaying errors")
            st.error(st.session_state.error_message)


if __name__ == "__main__":
    logger.info("Main program starting...")
    reload_page()
