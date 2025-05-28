import gettext
from datetime import datetime
from typing import Dict, Optional

import altair as alt
import pandas as pd
import requests
import streamlit as st
from agent import *
from agent import check_patient_consent_to_reschedule
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Hospital bed management", page_icon="🏥")

_ = gettext.gettext
language = st.sidebar.selectbox("Choose language", ["en", "pl"], label_visibility="collapsed")
try:
    localizator = gettext.translation("base", localedir="locales", languages=[language])
    localizator.install()
    _ = localizator.gettext
except:
    pass

main_tab, statistics_tab = st.tabs([_("Current state"), _("Data analysis")])
main_tab.title(_("Bed Assignments"))

if "day_for_simulation" not in st.session_state:
    st.session_state.day_for_simulation = requests.get("http://backend:8000/get-current-day").json()["day"]
if "refreshes_number" not in st.session_state:
    st.session_state.refreshes_number = 0
if "auto_day_change" not in st.session_state:
    st.session_state.auto_day_change = False
if "button_pressed" not in st.session_state:
    st.session_state.button_pressed = False
if "consent" not in st.session_state:
    st.session_state.consent = False

today = pd.Timestamp(datetime.today().date())


st.html(
    """
    <style>
        section[data-testid="stSidebar"]{
            width: 30% !important;
        }
        section[data-testid="stMain"]{
            min-width: 70% !important;
            max-width: 100%;
        }

        .tooltip {
            position: relative;
            display: inline-block;
        }
        .tooltip .tooltiptext {
            visibility: hidden;
            width: max-content;
            background-color: black;
            color: #fff;
            text-align: center;
            padding: 8px;
            border-radius: 8px;
            position: absolute;
            bottom: 110%;
            left: 50%;
            transform: translateX(-50%);
            z-index: 100;
        }
        .tooltip:hover .tooltiptext {
            visibility: visible;
        }
        .tooltiptext table {
            font-size: 0.8em;
            margin: 0;
            padding: 0;
        }
        .tooltiptext table td, .tooltiptext table th {
            font-size: 1em;
            margin: 0;
            padding: 1px 2px;
            font-weight: 200;
        }
        .left-side{
            left: 0 !important;
            right: auto !important;
            transform: none !important;
        }
        .right-side{
            left: auto !important;
            right: 0 !important;
            transform: none !important;
        }


        .main .block-container {
            max-width: 1200px;
        }
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

        .box-empty {
            background-color: oklch(80% 0.23 140);

            &:hover {
                background-color: oklch(90% 0.23 140);
            }

        }
        .box-occupied {
            background-color: oklch(80% 0.25 25);

            &:hover {
                background-color: oklch(90% 0.25 25);
            }
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
        cols = main_tab.columns(boxes_per_row)

        for col in range(boxes_per_row):
            box_index = row * boxes_per_row + col

            if box_index < num_boxes:
                with cols[col]:
                    # Get data for this box
                    data_row = df.iloc[box_index]

                    box_title = f"{_('Bed')} {box_index + 1}"

                    # Format tooltip information with row data
                    filtered_items = {k: v for k, v in data_row.items() if k != "bed_id"}
                    table_headers, table_data = list(zip(*filtered_items.items())) if filtered_items else ([], [])

                    if table_headers != []:
                        table_headers = [
                            _("Patient's number"),
                            _("Patient's name"),
                            _("Sickness"),
                            _("Personal number"),
                            _("Days left"),
                        ]

                    tooltip_info = "<table style='border-collapse: collapse;'>"
                    tooltip_info += "<tr>"
                    for header in table_headers:
                        tooltip_info += f"<th style='border: 1px solid #ccc; padding: 4px; font-weight: bold;'>{header}</th>"
                    tooltip_info += "</tr><tr>"
                    for definition in table_data:
                        tooltip_info += f"<td style='border: 1px solid #ccc; padding: 4px;'>{definition}</td>"
                    tooltip_info += "</tr></table>"

                    if col == 0:
                        side_class = "left-side"
                    elif col == 3:
                        side_class = "right-side"
                    else:
                        side_class = ""

                    # Create a box with HTML
                    if data_row["patient_id"] == 0 or pd.isna(data_row["patient_id"]):
                        st.markdown(
                            f"""<div class="tooltip box box-empty">{box_title}<span class="tooltiptext  {side_class}">{_("This bed is empty!")}</span></div>""",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"""<div class="tooltip box box-occupied">{box_title}<span class="tooltiptext  {side_class}">{tooltip_info}</span></div>""",
                            unsafe_allow_html=True,
                        )


def handle_patient_rescheduling(
    name: str, surname: str, gender: str, pesel: str, sickness: str, old_day: int, new_day: int
) -> bool:
    """
    Handles the process of rescheduling a patient's appointment by initiating a voice conversation
    with the patient and analyzing their consent.

    :param name: The first name of the patient.
    :param surname: The last name of the patient.
    :param gender: The gender of the patient.
    :param pesel: The PESEL number of the patient.
    :param sickness: The sickness or condition of the patient.
    :param old_day: The current day of the patient's visit.
    :param new_day: The suggested day for the new appointment.
    :return: A boolean indicating whether the patient consented to the rescheduling.
    """

    conversation_id = call_patient(name, surname, gender, pesel, sickness, old_day, new_day)
    return check_patient_consent_to_reschedule(conversation_id)


def agent_call(queue_df: pd.DataFrame, searched_days_of_stay) -> None:
    idx = st.session_state.current_patient_index

    if idx < 0:
        main_tab.warning("No more patients in queue.")
        st.session_state.button_pressed = True
        return

    name, surname = queue_df["patient_name"][idx].split()
    pesel = queue_df["pesel"][idx][-3:]

    response = requests.get("http://backend:8000/get-patient-data", params={"queue_id": idx + 1}).json()
    consent = handle_patient_rescheduling(
        name=name,
        surname=surname,
        gender=response["gender"],
        pesel=pesel,
        sickness=response["sickness"],
        old_day=response["old_day"],
        new_day=response["new_day"],
    )

    st.session_state.consent = consent

    if consent is True:
        requests.get("http://backend:8000/add-patient-to-approvers", params={"queue_id": idx + 1})
        requests.get("http://backend:8000/increase-calls-number")

        main_tab.success(f"{name} {surname} {_('agreed to reschedule')}.")

        st.session_state.pop("current_patient_index", None)
        st.session_state.button_pressed = True
    elif consent is False:
        requests.get("http://backend:8000/increase-calls-number")
        main_tab.error(f"{name} {surname} {_('did not agree to reschedule')}.")
        st.session_state.current_patient_index = find_next_patient_to_call(searched_days_of_stay, queue_df)
        st.session_state.button_pressed = True
    else:
        main_tab.info(f"{name} {surname}{_("'s consent is unknown.")}.")


def call_next_patient_in_queue(queue_df: pd.DataFrame, searched_days_of_stay) -> None:
    st.session_state.current_patient_index = find_next_patient_to_call(searched_days_of_stay, queue_df)
    agent_call(queue_df, searched_days_of_stay)


def get_list_of_tables_and_statistics() -> Optional[Dict]:
    try:
        response = requests.get("http://backend:8000/get-tables-and-statistics")
        if response.status_code == 200:
            return response.json()
        else:
            main_tab.error(_("Failed to fetch data from the server."))
            return None
    except Exception as e:
        main_tab.error(f"{_('Failed to connect to the server')}: {e}")
        return None


def update_day(delta: int) -> None:
    try:
        response = requests.get("http://backend:8000/update-day", params={"delta": delta})
        st.session_state.day_for_simulation = response.json()["day"]
        st.session_state.pop("current_patient_index", None)
        st.session_state.consent = False
    except Exception as e:
        st.session_state.error_message = f"{_('Failed to connect to the server')}: {e}"


def toggle_auto_day_change() -> None:
    st.session_state.auto_day_change = not st.session_state.auto_day_change


def sort_values_for_charts_by_dates(data) -> pd.DataFrame:
    data_copy = data.copy()
    data_copy["Date"] = pd.Categorical(
        data_copy["Date"].astype(str), categories=[str(x) for x in sorted(data_copy["Date"])], ordered=True
    )
    return data_copy


def reset_day_for_simulation() -> None:
    try:
        response = requests.get("http://backend:8000/reset-simulation")
        st.session_state.day_for_simulation = response.json()["day"]
        st.session_state.pop("current_patient_index", None)
        st.session_state.consent = False
    except Exception as e:
        st.session_state.error_message = f"{_('Failed to connect to the server')}: {e}"


def find_next_patient_to_call(days_of_stay, queue_df) -> None:
    queue_df = queue_df[
        (queue_df["days_of_stay"] <= days_of_stay) & (queue_df["place_in_queue"] < st.session_state.current_patient_index + 1)
    ]
    return int(queue_df.sort_values(by="place_in_queue", ascending=False).iloc[0]["place_in_queue"]) - 1


if st.session_state.auto_day_change and not st.session_state.button_pressed:
    update_day(delta=1)
elif st.session_state.button_pressed:
    st.session_state.button_pressed = False

bed_df, queue_df, no_shows_df = None, None, None
tables = get_list_of_tables_and_statistics()
if tables:
    bed_df = pd.DataFrame(tables["BedAssignment"])
    queue_df = pd.DataFrame(tables["PatientQueue"])
    no_shows_df = pd.DataFrame(tables["NoShows"])

if "current_patient_index" not in st.session_state:
    if tables["DaysOfStayForReplacement"] != []:
        st.session_state.current_patient_index = len(queue_df)
        st.session_state.current_patient_index = find_next_patient_to_call(tables["DaysOfStayForReplacement"][0], queue_df)
    else:
        st.session_state.current_patient_index = len(queue_df) - 1

main_tab.header(f"{_('Day')} {st.session_state.day_for_simulation}")

if len(tables["DaysOfStayForReplacement"]) > 0 and len(queue_df) > 0:
    st.session_state.auto_day_change = False
    if st.session_state.consent is not None:
        st.sidebar.button(
            f"{_('Call next patient in queue')} 📞",
            on_click=lambda: agent_call(queue_df, tables["DaysOfStayForReplacement"][0]),
        )
    else:
        st.sidebar.button(
            f"{_('Call patient again')} 🔁", on_click=lambda: agent_call(queue_df, tables["DaysOfStayForReplacement"][0])
        )
        if st.session_state.current_patient_index > 0:
            st.sidebar.button(
                f"{_('Call next patient in queue')} 📞",
                on_click=lambda: call_next_patient_in_queue(queue_df, tables["DaysOfStayForReplacement"][0]),
            )
elif st.session_state.day_for_simulation < 20 and st.session_state.auto_day_change:
    st_autorefresh(interval=10000, limit=None)

if not bed_df.empty:
    create_box_grid(bed_df)
else:
    main_tab.info(_("No bed assignments found."))

st.sidebar.subheader(_("Patients in queue"))
if not queue_df.empty:

    def highlight_current_row(row):
        if row.name == st.session_state.current_patient_index:
            return ["background-color: #fddb3a"] * len(row)
        return [""] * len(row)

    styled_df = queue_df.copy()
    styled_df["admission_day"] = today + pd.to_timedelta(styled_df["admission_day"], unit="D")
    styled_df.columns = [
        _("Place in queue"),
        _("Patient's number"),
        _("Patient's name"),
        _("Personal number"),
        _("Admission day"),
        _("Days of stay"),
    ]

    if len(tables["DaysOfStayForReplacement"]) > 0 and len(queue_df) > 0:
        styled_df = styled_df.style.apply(highlight_current_row, axis=1)
        st.sidebar.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.sidebar.dataframe(styled_df, use_container_width=True, hide_index=True)
else:
    st.sidebar.info(_("No patients found in the queue."))

st.sidebar.subheader(_("Patients absent on a given day"))
if not no_shows_df.empty:
    no_shows_df_display = no_shows_df.copy()
    no_shows_df_display.columns = [_("Patient's number"), _("Patient's name")]
    st.sidebar.dataframe(no_shows_df_display, use_container_width=True, hide_index=True)
else:
    st.sidebar.info(_("No no-shows found."))

st.sidebar.toggle(label=_("Activate automatic day change"), value=st.session_state.auto_day_change, key="auto_day_change")

if st.session_state.day_for_simulation > 1 and not st.session_state.auto_day_change:
    st.sidebar.button(_("Reset simulation"), on_click=reset_day_for_simulation)

statistics_tab.subheader(_("Bed occupancy statistics"))

analytic_data = tables["Statistics"]

col1, col2, col3 = statistics_tab.columns(3)
col1.metric(
    label=_("Beds occupancy"),
    value=analytic_data["Occupancy"],
    delta=(
        _("No previous day")
        if analytic_data["OccupancyDifference"] == "No previous day"
        else analytic_data["OccupancyDifference"]
    ),
    border=True,
)
col2.metric(
    label=_("Average beds occupancy"),
    value=analytic_data["AverageOccupancy"],
    delta=(
        _("No previous day")
        if analytic_data["AverageOccupancyDifference"] == "No previous day"
        else analytic_data["AverageOccupancyDifference"]
    ),
    border=True,
)
col3.metric(
    label=_("Average length of stay"),
    value=analytic_data["AverageStayLength"],
    delta=(
        _("No previous day")
        if analytic_data["AverageStayLengthDifference"] == "No previous day"
        else analytic_data["AverageStayLengthDifference"]
    ),
    border=True,
)

occupancy_df = sort_values_for_charts_by_dates(pd.DataFrame(analytic_data["OccupancyInTime"]))
chart = (
    alt.Chart(occupancy_df)
    .mark_line(point=True)
    .encode(
        x=alt.X("Date", axis=alt.Axis(title=_("Date"))),
        y=alt.Y("Occupancy", axis=alt.Axis(title=_("Occupancy [%]"), format="d"), scale=alt.Scale(domain=[0, 100])),
    )
)
statistics_tab.altair_chart(chart, use_container_width=True)

statistics_tab.subheader(_("No-show statistics"))

col1, col2 = statistics_tab.columns(2)
col1.metric(
    label=_("No-shows percentage"),
    value=analytic_data["NoShowsPercentage"],
    delta=(
        _("No previous day")
        if analytic_data["NoShowsPercentageDifference"] == "No previous day"
        else analytic_data["NoShowsPercentageDifference"]
    ),
    border=True,
)
col2.metric(
    label=_("Average no-shows percentage"),
    value=analytic_data["AverageNoShowsPercentage"],
    delta=(
        _("No previous day")
        if analytic_data["AverageNoShowsPercentageDifference"] == "No previous day"
        else analytic_data["AverageNoShowsPercentageDifference"]
    ),
    border=True,
)

no_shows_df = sort_values_for_charts_by_dates(pd.DataFrame(analytic_data["NoShowsInTime"]))
chart = (
    alt.Chart(no_shows_df)
    .mark_bar()
    .encode(
        x=alt.X("Date", axis=alt.Axis(title=_("Date"))),
        y=alt.Y(
            "NoShowsNumber",
            axis=alt.Axis(
                title=_("Number of no-shows"), values=list(range(0, max(no_shows_df["NoShowsNumber"]) + 1)), format="d"
            ),
        ),
    )
)
statistics_tab.altair_chart(chart, use_container_width=True)


statistics_tab.subheader(_("Phone calls statistics"))

col1, col2 = statistics_tab.columns(2)
col1.metric(
    label=_("Percentage of calls resulting in rescheduling"),
    value=(
        _("No calls made") if analytic_data["ConsentsPercentage"] == "No calls made" else analytic_data["ConsentsPercentage"]
    ),
    delta=(
        _("No calls made")
        if analytic_data["ConsentsPercentageDifference"] == "No calls made"
        else analytic_data["ConsentsPercentageDifference"]
    ),
    border=True,
)
col2.metric(
    label=_("Average percentage of calls resulting in rescheduling"),
    value=(
        _("No calls made")
        if analytic_data["AverageConstentsPercentage"] == "No calls made"
        else analytic_data["AverageConstentsPercentage"]
    ),
    delta=(
        _("No calls made")
        if analytic_data["AverageConstentsPercentageDifference"] == "No calls made"
        else analytic_data["AverageConstentsPercentageDifference"]
    ),
    border=True,
)

calls_df = sort_values_for_charts_by_dates(pd.DataFrame(analytic_data["CallsInTime"]))
chart = (
    alt.Chart(calls_df)
    .mark_bar()
    .encode(
        x=alt.X("Date", axis=alt.Axis(title=_("Date"))),
        y=alt.Y(
            "CallsNumber",
            axis=alt.Axis(
                title=_("Number of phone calls completed"), values=list(range(0, max(calls_df["CallsNumber"]) + 1)), format="d"
            ),
        ),
    )
)
statistics_tab.altair_chart(chart, use_container_width=True)


if st.session_state.day_for_simulation < 20 and not st.session_state.auto_day_change:
    st.button(f"➡️ {_('Simulate Next Day')}", on_click=lambda: update_day(delta=1))
if st.session_state.day_for_simulation > 1 and not st.session_state.auto_day_change:
    st.button(f"⬅️ {_('Simulate Previous Day')}", on_click=lambda: update_day(delta=-1))

if "error_message" in st.session_state and st.session_state.error_message:
    st.error(st.session_state.error_message)
