import json
import logging.config
import random
import traceback
from pathlib import Path
from typing import Dict, List

from db_operations import get_session
from fastapi import FastAPI, Query
from models import (
    Bed,
    BedAssignment,
    DataForReplacement,
    Department,
    ListOfTables,
    MedicalProcedure,
    NoShow,
    Patient,
    PatientQueue,
    PersonnelMember,
    PersonnelQueueAssignment,
    Statistics,
    StayPersonnelAssignment,
)
from sqlalchemy.orm import joinedload

NO_SHOW_PROBABILITY_TRUE_COUNT = 30

logger = logging.getLogger("hospital_logger")
config_file = Path("logger_config.json")
with open(config_file) as f:
    config = json.load(f)
logging.config.dictConfig(config)

app = FastAPI()
day_for_simulation = 1
last_change = 1
patients_consent_dictionary: dict[int, list[int]] = {1: []}
calls_in_time: dict[str, list] = {"Date": [1], "CallsNumber": [0]}
session = get_session()
session_savepoints = [session] + [None] * 19
latest_savepoint_index = 0
occupancy_in_time = {"Date": [1], "Occupancy": [100]}
no_shows_in_time = {"Date": [1], "NoShows": [0], "NoShowsNumber": [0]}
no_shows_list: dict[int, List[NoShow]] = {1: []}
days_of_stay_for_replacement: dict[int, List[int]] = {1: []}
personnels_for_replacement: dict[int, List[Dict[str, str]]] = {1: []}
departments_for_replacement: dict[int, List[str]] = {1: []}
stay_lengths = {}
stay_lengths[1] = [d[0] for d in session.query(BedAssignment.days_of_stay).all()]
rnd = random.Random()
rnd.seed(43)
states_of_randomization = {1: rnd.getstate()}


@app.get("/get-current-day", response_model=Dict[str, int])
def get_current_day() -> Dict[str, int]:
    """
    Returns the current day of the simulation as per it's state on the server to keep the frontend and backend in sync.
    :return: JSON object with the current day of the simulation.
    """
    global day_for_simulation
    return {"day": day_for_simulation}


@app.get("/update-day", response_model=Dict[str, int])
def update_day(delta: int = Query(...)) -> Dict[str, int]:
    """
    Updates the current day of the simulation.
    :param delta: Either -1 or 1 to signal a rollback or a forward.
    :return: Returns the day resolved on the server side.
    """
    global \
        day_for_simulation, \
        last_change, \
        patients_consent_dictionary, \
        calls_in_time, \
        occupancy_in_time, \
        no_shows_in_time, \
        personnels_for_replacement, \
        days_of_stay_for_replacement, \
        departments_for_replacement, \
        stay_lengths, \
        states_of_randomization, \
        rnd
    if delta not in (-1, 1):
        return {"error": "Invalid delta value. Use -1 or 1."}
    if delta == 1 and day_for_simulation < 20 or delta == -1 and day_for_simulation > 1:
        day_for_simulation += delta
        last_change = delta
        if delta == 1:
            patients_consent_dictionary[day_for_simulation] = []
            calls_in_time["Date"].append(day_for_simulation)
            calls_in_time["CallsNumber"].append(0)
        else:
            patients_consent_dictionary.pop(day_for_simulation + 1)
            calls_in_time["Date"].pop(day_for_simulation)
            calls_in_time["CallsNumber"].pop(day_for_simulation)
            occupancy_in_time["Date"].pop(day_for_simulation)
            occupancy_in_time["Occupancy"].pop(day_for_simulation)
            no_shows_in_time["Date"].pop(day_for_simulation)
            no_shows_in_time["NoShows"].pop(day_for_simulation)
            no_shows_in_time["NoShowsNumber"].pop(day_for_simulation)
            personnels_for_replacement[day_for_simulation + 1] = []
            days_of_stay_for_replacement[day_for_simulation + 1] = []
            departments_for_replacement[day_for_simulation + 1] = []
            if day_for_simulation + 1 in stay_lengths.keys():
                stay_lengths.pop(day_for_simulation + 1)
            rnd.setstate(states_of_randomization[day_for_simulation])
            states_of_randomization.pop(day_for_simulation + 1)
    return {"day": day_for_simulation}


@app.get("/reset-simulation", response_model=Dict[str, int])
def reset_simulation() -> Dict[str, int]:
    global \
        patients_consent_dictionary, \
        day_for_simulation, \
        last_change, \
        calls_in_time, \
        session, \
        session_savepoints, \
        latest_savepoint_index, \
        occupancy_in_time, \
        no_shows_in_time, \
        no_shows_list, \
        days_of_stay_for_replacement, \
        personnels_for_replacement, \
        departments_for_replacement, \
        stay_lengths, \
        states_of_randomization, \
        rnd
    day_for_simulation = 1
    last_change = 1
    patients_consent_dictionary = {1: []}
    calls_in_time = {"Date": [1], "CallsNumber": [0]}
    session = get_session()
    session_savepoints = [session] + [None] * 19
    latest_savepoint_index = 0
    occupancy_in_time = {"Date": [1], "Occupancy": [100]}
    no_shows_in_time = {"Date": [1], "NoShows": [0], "NoShowsNumber": [0]}
    no_shows_list = {1: []}
    days_of_stay_for_replacement = {1: []}
    personnels_for_replacement = {1: []}
    departments_for_replacement = {1: []}
    stay_lengths = {}
    stay_lengths[1] = [d[0] for d in session.query(BedAssignment.days_of_stay).all()]
    rnd.seed(43)
    states_of_randomization = {1: rnd.getstate()}
    logger.info("Resetting the simulation")
    return {"day": day_for_simulation}


@app.get("/get-tables-and-statistics", response_model=ListOfTables)
def get_tables_and_statistics() -> ListOfTables:
    """
    Returns the current state of the simulation.
    :return: A JSON object with three lists: BedAssignment, PatientQueue, and NoShows.
    """
    global \
        latest_savepoint_index, \
        session_savepoints, \
        occupancy_in_time, \
        no_shows_in_time, \
        days_of_stay_for_replacement, \
        personnels_for_replacement, \
        departments_for_replacement, \
        stay_lengths, \
        states_of_randomization, \
        rnd
    day = day_for_simulation
    rollback_flag = last_change
    consent_dict = patients_consent_dictionary.copy()
    calls_numbers_dict = calls_in_time.copy()

    def decrement_days_of_stay():
        session.query(BedAssignment).update({BedAssignment.days_of_stay: BedAssignment.days_of_stay - 1})

    def print_patients_to_be_released():
        patients_to_release = (
            session.query(Patient)
            .filter(Patient.patient_id.in_(session.query(BedAssignment.patient_id).filter(BedAssignment.days_of_stay <= 1)))
            .all()
        )
        if patients_to_release:
            logger.info(
                "Patients to be released from hospital:\n"
                + "\n".join(f"Patient ID: {p.patient_id}, Name: {p.first_name} {p.last_name}" for p in patients_to_release)
            )

    def delete_patients_to_be_released():
        session.query(BedAssignment).filter(BedAssignment.days_of_stay <= 1).delete(synchronize_session=False)

    def assign_beds_to_patients(assignments_data: list, log: bool):
        bed_assignments = []
        personnel_assignments = []
        for bed_id, patient_id, procedure_id, days, personnel in assignments_data:
            bed_assignments.append(
                {"bed_id": bed_id, "patient_id": patient_id, "procedure_id": procedure_id, "days_of_stay": days}
            )

            for personnel_member in personnel:
                personnel_assignments.append({"bed_id": bed_id, "member_id": personnel_member.member_id})
            if log:
                logger.info(f"Assigned bed {bed_id} to patient {patient_id} for {days} days")

        session.bulk_insert_mappings(BedAssignment, bed_assignments)
        session.bulk_insert_mappings(StayPersonnelAssignment, personnel_assignments)

    def delete_patient_by_queue_id_from_queue(queue_id: int):
        entry = (
            session.query(PatientQueue)
            .filter_by(queue_id=queue_id)
            .options(joinedload(PatientQueue.personnel_queue_assignment))
            .first()
        )
        if entry:
            for assignment in entry.personnel_queue_assignment:
                session.delete(assignment)
            session.delete(entry)

            session.query(PatientQueue).filter(PatientQueue.queue_id > queue_id).update(
                {PatientQueue.queue_id: PatientQueue.queue_id - 1}, synchronize_session="fetch"
            )

    def get_patient_name_by_id(patient_id: int) -> str:
        patient = session.query(Patient).filter_by(patient_id=patient_id).first()
        return f"{patient.first_name} {patient.last_name}" if patient else "Unknown"

    def get_beds_number() -> int:
        return session.query(Bed).count()

    def calculate_average_in_dictionary(data: dict) -> float:
        total_sum = sum(sum(v) for v in data.values() if isinstance(v, list))
        total_items_number = sum(len(v) for v in data.values() if isinstance(v, list))
        return total_sum / total_items_number

    def calculate_statistics() -> Statistics:
        # Calculation of average length of stay
        stay_lengths_for_calculations = stay_lengths.copy()
        avg_stay_length = calculate_average_in_dictionary(stay_lengths_for_calculations)
        if len(stay_lengths_for_calculations) != 1:
            max_key = max(stay_lengths_for_calculations.keys())
            stay_lengths_for_calculations.pop(max_key)
            avg_stay_length_diff = avg_stay_length - calculate_average_in_dictionary(stay_lengths_for_calculations)
        else:
            avg_stay_length_diff = "No previous day"

        # Hospital occupancy calculations
        occupancy_data = occupancy_in_time["Occupancy"].copy()

        if len(occupancy_data) != 1:
            occupancy = occupancy_data[-1]
            occupancy_diff = occupancy_data[-1] - occupancy_data[-2]

            avg_occupancy = sum(occupancy_data) / len(occupancy_data)
            occupancy_data.pop(-1)
            avg_occupancy_diff = avg_occupancy - (sum(occupancy_data) / len(occupancy_data))
        else:
            occupancy = occupancy_data[0]
            occupancy_diff = "No previous day"

            avg_occupancy = occupancy_data[0]
            avg_occupancy_diff = "No previous day"

        # No-shows calculations
        no_shows_data = no_shows_in_time["NoShows"].copy()

        if len(no_shows_data) != 1:
            no_shows_perc = no_shows_data[-1]
            no_shows_perc_diff = (
                no_shows_data[-1] - no_shows_data[-2]
                if no_shows_data[-1] != "No incoming patients" and no_shows_data[-2] != "No incoming patients"
                else "No incoming patients"
            )

            total_sum = sum(x for x in no_shows_data if x != "No incoming patients")
            items_number = sum(1 for x in no_shows_data if x != "No incoming patients")
            avg_no_shows_perc = total_sum / items_number if items_number != 0 else "No incoming patients"
            no_shows_data.pop(-1)

            total_sum = sum(x for x in no_shows_data if x != "No incoming patients")
            items_number = sum(1 for x in no_shows_data if x != "No incoming patients")
            avg_no_shows_perc_diff = (
                avg_no_shows_perc - (total_sum / items_number)
                if items_number != 0 and avg_no_shows_perc != "No incoming patients"
                else "No incoming patients"
            )
        else:
            no_shows_perc = no_shows_data[0]
            no_shows_perc_diff = "No previous day"

            avg_no_shows_perc = no_shows_data[0]
            avg_no_shows_perc_diff = "No previous day"

        # Calls calculations
        percentage_list = []
        for i in range(len(calls_numbers_dict["CallsNumber"])):
            if calls_numbers_dict["CallsNumber"][i] != 0:
                percentage_list.append(len(consent_dict[i + 1]) / calls_numbers_dict["CallsNumber"][i] * 100)
            else:
                percentage_list.append("No calls made")

        consent_percentage = percentage_list[-1]
        consent_percentage_diff = (
            percentage_list[-1] - percentage_list[-2]
            if percentage_list[-1] != "No calls made" and percentage_list[-2] != "No calls made"
            else "No calls made"
        )

        total_sum = sum(x for x in percentage_list if x != "No calls made")
        items_number = sum(1 for x in percentage_list if x != "No calls made")
        avg_consent_perc = total_sum / items_number if items_number != 0 else "No calls made"

        percentage_list.pop(-1)

        total_sum = sum(x for x in percentage_list if x != "No calls made")
        items_number = sum(1 for x in percentage_list if x != "No calls made")
        avg_consent_perc_diff = (
            avg_consent_perc - (total_sum / items_number)
            if items_number != 0 and avg_consent_perc != "No calls made"
            else "No calls made"
        )

        return Statistics(
            OccupancyInTime=occupancy_in_time,
            Occupancy=f"{occupancy:.3f}".rstrip("0").rstrip(".") + "%",
            OccupancyDifference=f"{occupancy_diff:.3f}".rstrip("0").rstrip(".") + "%"
            if occupancy_diff != "No previous day"
            else "No previous day",
            AverageOccupancy=f"{avg_occupancy:.3f}".rstrip("0").rstrip(".") + "%",
            AverageOccupancyDifference=f"{avg_occupancy_diff:.3f}".rstrip("0").rstrip(".") + "%"
            if avg_occupancy_diff != "No previous day"
            else "No previous day",
            AverageStayLength=f"{avg_stay_length:.3f}".rstrip("0").rstrip("."),
            AverageStayLengthDifference=f"{avg_stay_length_diff:.3f}".rstrip("0").rstrip(".")
            if avg_stay_length_diff != "No previous day"
            else "No previous day",
            NoShowsInTime={"Date": no_shows_in_time["Date"], "NoShowsNumber": no_shows_in_time["NoShowsNumber"]},
            NoShowsPercentage=f"{no_shows_perc:.3f}".rstrip("0").rstrip(".") + "%"
            if no_shows_perc != "No incoming patients"
            else "No incoming patients",
            NoShowsPercentageDifference=f"{no_shows_perc_diff:.3f}".rstrip("0").rstrip(".") + "%"
            if no_shows_perc_diff != "No incoming patients" and no_shows_perc_diff != "No previous day"
            else no_shows_perc_diff,
            AverageNoShowsPercentage=f"{avg_no_shows_perc:.3f}".rstrip("0").rstrip(".") + "%"
            if avg_no_shows_perc != "No incoming patients"
            else "No incoming patients",
            AverageNoShowsPercentageDifference=f"{avg_no_shows_perc_diff:.3f}".rstrip("0").rstrip(".") + "%"
            if avg_no_shows_perc_diff != "No incoming patients" and avg_no_shows_perc_diff != "No previous day"
            else avg_no_shows_perc_diff,
            CallsInTime=calls_numbers_dict,
            ConsentsPercentage=f"{consent_percentage:.3f}".rstrip("0").rstrip(".") + "%"
            if consent_percentage != "No calls made"
            else "No calls made",
            ConsentsPercentageDifference=f"{consent_percentage_diff:.3f}".rstrip("0").rstrip(".") + "%"
            if consent_percentage_diff != "No calls made"
            else "No calls made",
            AverageConstentsPercentage=f"{avg_consent_perc:.3f}".rstrip("0").rstrip(".") + "%"
            if avg_consent_perc != "No calls made"
            else "No calls made",
            AverageConstentsPercentageDifference=f"{avg_consent_perc_diff:.3f}".rstrip("0").rstrip(".") + "%"
            if avg_consent_perc_diff != "No calls made"
            else "No calls made",
        )

    try:
        beds_number = get_beds_number()

        if rollback_flag == 1:
            logger.info(f"Current simulation day: {day}")
        else:
            logger.info(f"Rollback of simulation to day {day}")

        if rollback_flag == 1:
            no_shows_list[day] = []
            for iteration in range(latest_savepoint_index, day - 1):
                should_log = iteration == day - 2 and rollback_flag == 1
                should_give_no_shows = iteration == day - 2

                if should_log:
                    print_patients_to_be_released()
                delete_patients_to_be_released()
                decrement_days_of_stay()

                assigned_beds = session.query(BedAssignment.bed_id).scalar_subquery()
                beds = (
                    session.query(Bed.department_id, Bed.bed_id)
                    .filter(~Bed.bed_id.in_(assigned_beds))
                    .order_by(Bed.department_id, Bed.bed_id)
                    .all()
                )

                bed_map = {}
                for department_id, bed_id in beds:
                    bed_map.setdefault(department_id, []).append(bed_id)

                logger.info

                occupied_beds_number = beds_number - len(beds)
                no_shows_number = 0

                queue = (
                    session.query(PatientQueue)
                    .options(
                        joinedload(PatientQueue.medical_procedure).joinedload(MedicalProcedure.department),
                        joinedload(PatientQueue.personnel_queue_assignment).joinedload(
                            PersonnelQueueAssignment.personnel_member
                        ),
                    )
                    .filter(PatientQueue.admission_day == iteration + 2)
                    .order_by(PatientQueue.queue_id)
                    .all()
                )

                assignments_to_create = []

                days_of_stay_for_replacement[day] = []
                personnels_for_replacement[day] = []
                departments_for_replacement[day] = []

                for i in range(min(len(queue), len(beds))):
                    entry = queue[i]
                    patient_id = entry.patient_id
                    will_come = rnd.choice([True] * NO_SHOW_PROBABILITY_TRUE_COUNT + [False])
                    if not will_come:
                        no_shows_number += 1

                        personnel_data = {}

                        for personnel in entry.personnel_queue_assignment:
                            personnel_data[
                                personnel.personnel_member.first_name + " " + personnel.personnel_member.last_name
                            ] = personnel.personnel_member.role

                        days_of_stay_for_replacement[day].append(entry.days_of_stay)
                        personnels_for_replacement[day].append(personnel_data)
                        departments_for_replacement[day].append(entry.medical_procedure.department.name)

                        delete_patient_by_queue_id_from_queue(entry.queue_id)
                        if should_give_no_shows:
                            no_show = NoShow(patient_id=patient_id, patient_name=get_patient_name_by_id(patient_id))
                            no_shows_list[day].append(no_show)
                        if should_log:
                            logger.info(f"No-show: {no_show.patient_name}")
                    else:
                        if iteration + 2 not in stay_lengths:
                            stay_lengths[iteration + 2] = []
                        stay_lengths[iteration + 2].append(entry.days_of_stay)

                        assignments_to_create.append(
                            (
                                bed_map[entry.medical_procedure.department_id][0],
                                patient_id,
                                entry.procedure_id,
                                entry.days_of_stay,
                                entry.personnel_queue_assignment,
                            )
                        )

                        delete_patient_by_queue_id_from_queue(entry.queue_id)
                        bed_map[entry.medical_procedure.department_id].pop(0)
                        occupied_beds_number += 1

                queue_entries = (
                    session.query(PatientQueue).filter(PatientQueue.queue_id.in_(consent_dict[iteration + 2])).all()
                )
                queue_entries_map = {entry.queue_id: entry for entry in queue_entries}

                for queue_id in consent_dict[iteration + 2]:
                    queue_entry = queue_entries_map[queue_id]

                    if iteration + 2 not in stay_lengths:
                        stay_lengths[iteration + 2] = []
                    stay_lengths[iteration + 2].append(queue_entry.days_of_stay)

                    assignments_to_create.append(
                        (
                            bed_map[queue_entry.medical_procedure.department_id][0],
                            queue_entry.patient_id,
                            queue_entry.procedure_id,
                            queue_entry.days_of_stay,
                            queue_entry.personnel_queue_assignment,
                        )
                    )

                    delete_patient_by_queue_id_from_queue(queue_id)
                    bed_map[queue_entry.medical_procedure.department_id].pop(0)
                    occupied_beds_number += 1

                assign_beds_to_patients(assignments_to_create, should_log)

                consent_count = len(consent_dict[iteration + 2])

                days_of_stay_for_replacement[day] = days_of_stay_for_replacement[day][consent_count:]
                personnels_for_replacement[day] = personnels_for_replacement[day][consent_count:]
                departments_for_replacement[day] = departments_for_replacement[day][consent_count:]

                occupancy_in_time["Date"].append(iteration + 2)
                occupancy_in_time["Occupancy"].append(occupied_beds_number / beds_number * 100)

                no_shows_in_time["Date"].append(iteration + 2)
                if len(beds) > 0:
                    no_shows_in_time["NoShows"].append(no_shows_number / len(beds) * 100)
                else:
                    no_shows_in_time["NoShows"].append("No incoming patients")

                no_shows_in_time["NoShowsNumber"].append(no_shows_number)

                states_of_randomization[iteration + 2] = rnd.getstate()

            session_savepoints[latest_savepoint_index + 1] = session.begin_nested()
            if day - 1 != 0:
                latest_savepoint_index += 1
        else:
            latest_savepoint_index -= 1
            session_savepoints[latest_savepoint_index].rollback()
            session_savepoints[latest_savepoint_index] = session.begin_nested()

        all_bed_assignments = []
        department_assignments = {}
        for bed in (
            session.query(Bed)
            .options(
                joinedload(Bed.assignments).joinedload(BedAssignment.patient),
                joinedload(Bed.assignments).joinedload(BedAssignment.medical_procedure),
                joinedload(Bed.assignments)
                .joinedload(BedAssignment.stay_personnel_assignment)
                .joinedload(StayPersonnelAssignment.personnel_member),
                joinedload(Bed.department),
            )
            .order_by(Bed.bed_id)
            .all()
        ):
            ba = bed.assignments[0] if bed.assignments else None
            patient = ba.patient if ba else None

            patient_name = f"{patient.first_name} {patient.last_name}" if patient else "Unoccupied"
            medical_procedure = ba.medical_procedure.name if ba else "Unoccupied"
            pesel = patient.pesel if patient else "Unoccupied"
            nationality = patient.nationality if patient else "Unoccupied"
            personnel_assignments = ba.stay_personnel_assignment if ba else None
            personnel_data = {}

            if personnel_assignments:
                for assignment in personnel_assignments:
                    personnel_data[assignment.personnel_member.first_name + " " + assignment.personnel_member.last_name] = (
                        assignment.personnel_member.role
                    )

            days_of_stay = ba.days_of_stay if ba else 0

            assignment = {
                "bed_id": bed.bed_id,
                "patient_id": ba.patient_id if ba else 0,
                "patient_name": patient_name,
                "medical_procedure": medical_procedure,
                "pesel": pesel,
                "nationality": nationality,
                "days_of_stay": days_of_stay,
                "personnel": personnel_data,
            }

            all_bed_assignments.append(assignment)

            if bed.department.name not in department_assignments:
                department_assignments[bed.department.name] = []

            department_assignments[bed.department.name].append(assignment)

        queue_data = []
        for entry in (
            session.query(PatientQueue)
            .options(
                joinedload(PatientQueue.patient),
                joinedload(PatientQueue.medical_procedure).joinedload(MedicalProcedure.department),
                joinedload(PatientQueue.personnel_queue_assignment).joinedload(PersonnelQueueAssignment.personnel_member),
            )
            .order_by(PatientQueue.queue_id)
            .all()
        ):
            personnel_data = {}

            for personnel in entry.personnel_queue_assignment:
                personnel_data[personnel.personnel_member.first_name + " " + personnel.personnel_member.last_name] = (
                    personnel.personnel_member.role
                )

            queue_data.append(
                {
                    "place_in_queue": entry.queue_id,
                    "patient_id": entry.patient_id,
                    "patient_name": f"{entry.patient.first_name} {entry.patient.last_name}",
                    "pesel": f"...{entry.patient.pesel[-3:]}",
                    "nationality": entry.patient.nationality,
                    "days_of_stay": entry.days_of_stay,
                    "admission_day": entry.admission_day,
                    "medical_procedure": entry.medical_procedure.name,
                    "department": entry.medical_procedure.department.name,
                    "personnel": personnel_data,
                }
            )

        return ListOfTables(
            DepartmentAssignments=department_assignments,
            AllBedAssignments=all_bed_assignments,
            PatientQueue=queue_data,
            NoShows=[n.model_dump() for n in no_shows_list[day]],
            Statistics=calculate_statistics(),
            ReplacementData={
                "DaysOfStay": days_of_stay_for_replacement[day],
                "Personnels": personnels_for_replacement[day],
                "Departments": departments_for_replacement[day],
            },
        )

    except Exception as e:
        error_message = f"Error occurred: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_message)
        return {"error": "Server Error", "message": error_message}


@app.get("/add-patient-to-approvers")
def add_patient_to_approvers(queue_id: int) -> None:
    patients_consent_dictionary[day_for_simulation].append(queue_id)


@app.get("/increase-calls-number")
def increase_calls_number() -> None:
    calls_in_time["CallsNumber"][day_for_simulation - 1] += 1


@app.get("/get-patient-data")
def get_patient_data(patient_id: int):
    session = get_session()
    patient = session.query(Patient).filter_by(patient_id=patient_id).first()
    gender = patient.gender
    session.rollback()
    session.close()
    return {"gender": gender}
