from typing import Dict, Optional

import pandas as pd
import requests
import streamlit as st

if "day_for_simulation" not in st.session_state:
    st.session_state.day_for_simulation = requests.get("http://backend:8000/get-current-day").json()["day"]
st.set_page_config(page_title="Hospital bed management", page_icon="🏥")
st.title("Bed Assignments")
st.header(f"Day {st.session_state.day_for_simulation}")


def get_list_of_tables() -> Optional[Dict]:
    try:
        response = requests.get("http://backend:8000/get-tables")
    except Exception as e:
        st.error(f"Failed to connect to the server: {e}")
        return None
    if response.status_code == 200:
        return response.json()
    else:
        st.error("Failed to fetch data from the server.")
        return None


def simulate_next_day() -> None:
    try:
        response = requests.get("http://backend:8000/update-day", params={"delta": 1})
        st.session_state.day_for_simulation = response.json()["day"]
        st.session_state.error_message = None

    except Exception as e:
        st.session_state.error_message = f"Failed to connect to the server: {e}"


def simulate_previous_day() -> None:
    try:
        response = requests.get("http://backend:8000/update-day", params={"delta": -1})
        st.session_state.day_for_simulation = response.json()["day"]
        st.session_state.error_message = None
    except Exception as e:
        st.session_state.error_message = f"Failed to connect to the server: {e}"


def call_patient(patient_id: int) -> None:
    try:
        response = requests.get("http://backend:8000/create-voice-call", params={"patient_id": patient_id})
        result = response.json()
        bed_df = pd.DataFrame(result["BedAssignment"])
        queue_df = pd.DataFrame(result["PatientQueue"])
        global no_shows_df

        st.sidebar.subheader("Patients in queue")
        if not queue_df.empty:
            st.sidebar.dataframe(queue_df, use_container_width=True)
        else:
            st.sidebar.info("No patients found in the queue.")

        st.sidebar.subheader("Patients absent on a given day")
        if not no_shows_df.empty:
            st.sidebar.dataframe(no_shows_df, use_container_width=True)
        else:
            st.sidebar.info("No no-shows found.")

        if st.session_state.day_for_simulation < 20:
            st.button("➡️ Simulate Next Day", on_click=simulate_next_day)

        if st.session_state.day_for_simulation > 1:
            st.button("⬅️ Simulate Previous Day", on_click=simulate_previous_day)

        if "error_message" in st.session_state and st.session_state.error_message:
            st.error(st.session_state.error_message)

    except Exception as e:
        st.session_state.error_message = f"Failed to connect to the server: {e}"


tables = get_list_of_tables()
bed_df = pd.DataFrame(tables["BedAssignment"])
queue_df = pd.DataFrame(tables["PatientQueue"])
no_shows_df = pd.DataFrame(tables["NoShows"])

if not bed_df.empty:
    # for col in ["patient_id", "patient_name", "sickness", "days_of_stay"]:
    #    bed_df[col] = bed_df[col].apply(lambda x: None if x == 0 or x == "Unoccupied" else x)
    st.dataframe(bed_df, use_container_width=True)
else:
    st.info("No bed assignments found.")


if len(queue_df[queue_df["patient_id"] == 0]) > 0:
    st.sidebar.button("Call patient 📞")


st.sidebar.subheader("Patients in queue")
if not queue_df.empty:
    st.sidebar.dataframe(queue_df, use_container_width=True)
else:
    st.sidebar.info("No patients found in the queue.")

st.sidebar.subheader("Patients absent on a given day")
if not no_shows_df.empty:
    st.sidebar.dataframe(no_shows_df, use_container_width=True)
else:
    st.sidebar.info("No no-shows found.")

if st.session_state.day_for_simulation < 20:
    st.button("➡️ Simulate Next Day", on_click=simulate_next_day)

if st.session_state.day_for_simulation > 1:
    st.button("⬅️ Simulate Previous Day", on_click=simulate_previous_day)

if "error_message" in st.session_state and st.session_state.error_message:
    st.error(st.session_state.error_message)
