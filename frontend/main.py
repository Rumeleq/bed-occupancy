import random
from typing import Dict, Optional

import pandas as pd
import requests
import streamlit as st
from agent import *
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Hospital bed management", page_icon="🏥")
st.title("Bed Assignments")

if "day_for_simulation" not in st.session_state:
    st.session_state.day_for_simulation = requests.get("http://backend:8000/get-current-day").json()["day"]

if "refreshes_number" not in st.session_state:
    st.session_state.refreshes_number = 0


logger = logging.getLogger("hospital_logger")
config_file = Path("logger_config.json")
with open(config_file) as f:
    config = json.load(f)
logging.config.dictConfig(config)


st.html(
    """
    <style>
        section[data-testid="stSidebar"]{
            width: 30% !important;
        }
        section[data-testid="stMain"]{
            width: 70% !important;
        }
        .main .block-container {
            max-width: 1200px;
        }
        /* Style for the box */
        .box {
            border: 1px solid #d0d3d9;
            border-radius: 5px;
            height: 100px;
            display: flex;
            justify-content: center;
            align-items: center;
            font-weight: bold;
            margin-bottom: 15px;
            cursor: pointer;
        }
        .box:hover {
            background-color: #e0e2e6;
        }
        .box-empty {
            background-color: #ff8080;
        }
        .box-occupied {
            background-color: #80ff80;
        }
    </style>
    """
)


def create_box_grid(df: pd.DataFrame, boxes_per_row=4) -> None:
    """
    Creates a scrollable grid of boxes with tooltips on hover

    Parameters:
    - df: pandas DataFrame, each row represents a box
    - boxes_per_row: int, number of boxes to display per row
    """
    # Calculate number of boxes from DataFrame
    num_boxes = len(df)

    # Calculate number of rows needed
    num_rows = (num_boxes + boxes_per_row - 1) // boxes_per_row

    # Create the grid
    for row in range(num_rows):
        cols = st.columns(boxes_per_row)

        for col in range(boxes_per_row):
            box_index = row * boxes_per_row + col

            if box_index < num_boxes:
                with cols[col]:
                    # Get data for this box
                    data_row = df.iloc[box_index]

                    box_title = f"Bed {box_index + 1}"

                    # Create a box with HTML
                    if data_row["patient_id"] == 0 or pd.isna(data_row["patient_id"]):
                        st.markdown(f"""<div class="box box-empty">{box_title}</div>""", unsafe_allow_html=True)
                    else:
                        st.markdown(f"""<div class="box box-occupied">{box_title}</div>""", unsafe_allow_html=True)

                    # tooltip_info = "<table style='border-collapse: collapse; width: 100%;'>"

                    tooltip_text = []

                    # Find the maximum length for each column for alignment
                    max_lengths = {}
                    for column, value in data_row.items():
                        display_value = str(value) if pd.notna(value) else "None"
                        max_lengths[column] = max(len(str(column)), len(display_value))

                    # Create header row
                    header = "  ".join(f"{col:<{max_lengths[col]}}" for col in data_row.index)
                    tooltip_text.append(header)

                    # Add separator
                    separator = "  ".join("-" * max_lengths[col] for col in data_row.index)
                    tooltip_text.append(separator)

                    # Add data row
                    values = []
                    for col, val in zip(data_row.index, data_row.values):
                        display_val = str(val) if pd.notna(val) else "None"
                        values.append(f"{display_val:<{max_lengths[col]}}")
                    data_line = "  ".join(values)
                    tooltip_text.append(data_line)

                    # Join all lines
                    tooltip_info = "\n".join(tooltip_text)

                    # Add tooltip using Streamlit's help feature
                    st.markdown("", help=tooltip_info)
                    # Format tooltip information with row data
                    # tooltip_info = ""
                    # columns = "|"
                    # rows = "|"
                    # for column, value in data_row.items():
                    #     columns += f"{column:>{max(len(column), len(str(value)))}}|"
                    #     rows += f"{value:>{max(len(column), len(str(value)))}}|"
                    # if len(columns) != len(rows):
                    #     logger.info("error, {0}, {1}".format(len(columns), len(rows)))
                    # tooltip_info = f"{columns}\n{"-"*len(columns)}\n{rows}"
                    # # logger.info(type(data_row))
                    # # logger.info(data_row)
                    # # logger.info(type(data_row.items()))
                    # # logger.info(data_row.items())
                    #
                    # # row_string = data_row.to_frame().to_string()
                    # # logger.info(data_row.to_frame())
                    # # logger.info(data_row.to_frame().to_string())
                    #
                    # # Add tooltip using Streamlit's help feature
                    # st.markdown("", help=tooltip_info)


def handle_patient_rescheduling(name: str, surname: str, pesel: str, sickness: str, old_day: int, new_day: int) -> bool:
    """
    Handles the process of rescheduling a patient's appointment by initiating a voice conversation
    with the patient and analyzing their consent.

    :param name: The first name of the patient.
    :param surname: The last name of the patient.
    :param pesel: The PESEL number of the patient.
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
    will_come = random.choice([True, True, False, False, False])
    return will_come


def agent_call(queue_df: pd.DataFrame) -> None:
    queue_id = 0

    while queue_id < len(queue_df):
        patient_id = queue_df["patient_id"][queue_id]
        name, surname = queue_df["patient_name"][queue_id].split()
        pesel = queue_df["PESEL"][queue_id][-3:]

        response = requests.get("http://backend:8000/get-patient-data", params={"patient_id": patient_id}).json()
        consent = handle_patient_rescheduling(
            name=name,
            surname=surname,
            pesel=pesel,
            sickness=response["sickness"],
            old_day=response["old_day"],
            new_day=response["new_day"],
        )

        if consent:
            st.session_state.patient_id = patient_id
            st.session_state.consent = True
            requests.get("http://backend:8000/add-patient-to-approvers", params={"patient_id": patient_id})
            st.success(f"{name} {surname} agreed to reschedule.")
            return
        else:
            queue_id += 1

    st.warning("No patient agreed to reschedule.")


def get_list_of_tables() -> Optional[Dict]:
    try:
        response = requests.get("http://backend:8000/get-tables")
        if response.status_code == 200:
            return response.json()
        else:
            st.error("Failed to fetch data from the server.")
            return None
    except Exception as e:
        st.error(f"Failed to connect to the server: {e}")
        return None


def update_day(delta: int) -> None:
    try:
        response = requests.get("http://backend:8000/update-day", params={"delta": delta})
        st.session_state.day_for_simulation = response.json()["day"]
    except Exception as e:
        st.session_state.error_message = f"Failed to connect to the server: {e}"


refreshes_number = None
if st.session_state.day_for_simulation < 20:
    refreshes_number = st_autorefresh(interval=10000, limit=None)

if refreshes_number is not None and refreshes_number > st.session_state.refreshes_number:
    update_day(delta=1)
    st.session_state.refreshes_number = refreshes_number

st.header(f"Day {st.session_state.day_for_simulation}")

bed_df, queue_df, no_shows_df = None, None, None
tables = get_list_of_tables()
if tables:
    bed_df = pd.DataFrame(tables["BedAssignment"])
    queue_df = pd.DataFrame(tables["PatientQueue"])
    no_shows_df = pd.DataFrame(tables["NoShows"])

if len(bed_df[bed_df["patient_id"] == 0]) > 0 and len(queue_df) > 0:
    st.session_state.consent = False
    st.sidebar.button("Call next patient in queue 📞", on_click=lambda: agent_call(queue_df))

if not bed_df.empty:
    create_box_grid(bed_df)
    # for col in ["patient_id", "patient_name", "sickness", "PESEL", "days_of_stay"]:
    #     bed_df[col] = bed_df[col].apply(lambda x: None if x == 0 or x == "Unoccupied" else x)
    # st.dataframe(bed_df, use_container_width=True, hide_index=True)
else:
    st.info("No bed assignments found.")

st.sidebar.subheader("Patients in queue")
if not queue_df.empty:
    st.sidebar.dataframe(queue_df, use_container_width=True, hide_index=True)
else:
    st.sidebar.info("No patients found in the queue.")

st.sidebar.subheader("Patients absent on a given day")
if not no_shows_df.empty:
    st.sidebar.dataframe(no_shows_df, use_container_width=True, hide_index=True)
else:
    st.sidebar.info("No no-shows found.")

if st.session_state.day_for_simulation < 20:
    st.button("➡️ Simulate Next Day", on_click=lambda: update_day(delta=1))
if st.session_state.day_for_simulation > 1:
    st.button("⬅️ Simulate Previous Day", on_click=lambda: update_day(delta=-1))

if "error_message" in st.session_state and st.session_state.error_message:
    st.error(st.session_state.error_message)
