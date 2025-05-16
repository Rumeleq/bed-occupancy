import json
import logging.config
import math
import random
import traceback
from pathlib import Path
from typing import List

from db_operations import get_session
from fastapi import FastAPI, Query
from models import *

logger = logging.getLogger("hospital_logger")
config_file = Path("logger_config.json")
with open(config_file) as f:
    config = json.load(f)
logging.config.dictConfig(config)

app = FastAPI()
day_for_simulation = 1
last_change = 1
session = get_session()
random.seed(43)
patients_consent_dictionary: dict[int, list[dict]] = {}


@app.get("/get-current-day")
def get_current_day():
    global day_for_simulation
    return {"day": day_for_simulation}


@app.get("/update-day")
def update_day(delta: int = Query(...)):
    global day_for_simulation, last_change
    if delta not in (-1, 1):
        return {"error": "Invalid delta value. Use -1 or 1."}
    if delta == 1 and day_for_simulation < 20 or delta == -1 and day_for_simulation > 1:
        day_for_simulation += delta
        last_change = delta
    return {"day": day_for_simulation}


def assign_bed_to_patient(bed_id: int, patient_id: int, days: int, log: bool):
    global session
    assignment = BedAssignment(bed_id=bed_id, patient_id=patient_id, days_of_stay=days)
    session.add(assignment)
    if log:
        logger.info(f"Assigned bed {bed_id} to patient {patient_id} for {days} days")


def delete_patient_by_id_from_queue(patient_id: int):
    global session
    entry = session.query(PatientQueue).filter_by(patient_id=patient_id).order_by(PatientQueue.queue_id).first()
    if entry:
        session.delete(entry)
        queue = session.query(PatientQueue).order_by(PatientQueue.queue_id).all()
        for i, entry in enumerate(queue):
            entry.queue_id = i + 1


def get_first_free_bed() -> int | None:
    global session

    bed_assignments = []
    for bed in (
        session.query(Bed)
        .join(BedAssignment, Bed.bed_id == BedAssignment.bed_id, isouter=True)
        .join(Patient, BedAssignment.patient_id == Patient.patient_id, isouter=True)
        .order_by(Bed.bed_id)
        .all()
    ):
        ba = session.query(BedAssignment).filter_by(bed_id=bed.bed_id).first()
        if not ba:
            return bed.bed_id
    return None

    #     patient = ba.patient if ba else None
    #
    #     patient_name = f"{patient.first_name} {patient.last_name}" if patient else "Unoccupied"
    #     sickness = patient.sickness if patient else "Unoccupied"
    #     pesel = patient.pesel if patient else "Unoccupied"
    #     days_of_stay = ba.days_of_stay if ba else 0
    #
    #     bed_assignments.append(
    #         {
    #             "bed_id": bed.bed_id,
    #             "patient_id": ba.patient_id if ba else 0,
    #             "patient_name": patient_name,
    #             "sickness": sickness,
    #             "PESEL": pesel,
    #             "days_of_stay": days_of_stay,
    #         }
    #     )
    #
    #
    # print(session.query(BedAssignment))
    # result = session.query(BedAssignment).filter_by(patient_id=None).first()
    # if result is not None:
    #     print("first free bed for patient: ", result.bed_id)
    #     return result.bed_id
    # else: return None


@app.get("/get-bed-assignments-and-queue", response_model=BedAssignmentsAndQueue)
def get_bed_assignments_and_queue():
    global session
    bed_assignments = []
    for bed in (
        session.query(Bed)
        .join(BedAssignment, Bed.bed_id == BedAssignment.bed_id, isouter=True)
        .join(Patient, BedAssignment.patient_id == Patient.patient_id, isouter=True)
        .order_by(Bed.bed_id)
        .all()
    ):
        ba = session.query(BedAssignment).filter_by(bed_id=bed.bed_id).first()
        patient = ba.patient if ba else None

        patient_name = f"{patient.first_name} {patient.last_name}" if patient else "Unoccupied"
        sickness = patient.sickness if patient else "Unoccupied"
        pesel = patient.pesel if patient else "Unoccupied"
        days_of_stay = ba.days_of_stay if ba else 0

        bed_assignments.append(
            {
                "bed_id": bed.bed_id,
                "patient_id": ba.patient_id if ba else 0,
                "patient_name": patient_name,
                "sickness": sickness,
                "PESEL": pesel,
                "days_of_stay": days_of_stay,
            }
        )

    queue_data = []
    for entry in session.query(PatientQueue).order_by(PatientQueue.queue_id).all():
        patient = session.query(Patient).filter_by(patient_id=entry.patient_id).first()
        queue_data.append(
            {
                "place_in_queue": entry.queue_id,
                "patient_id": patient.patient_id,
                "patient_name": f"{patient.first_name} {patient.last_name}",
                "PESEL": f"...{patient.pesel[-3:]}",
            }
        )
    return BedAssignmentsAndQueue(BedAssignment=bed_assignments, PatientQueue=queue_data)


@app.get("/get-tables", response_model=ListOfTables)
def get_tables(only_patients_from_call: bool = False):
    global session

    def decrement_days_of_stay():
        for ba in session.query(BedAssignment).all():
            ba.days_of_stay -= 1

    def print_patients_to_be_released(log: bool) -> int:
        patients_to_release = (
            session.query(Patient)
            .filter(Patient.patient_id.in_(session.query(BedAssignment.patient_id).filter(BedAssignment.days_of_stay <= 0)))
            .all()
        )
        if log and patients_to_release:
            logger.info(
                "Patients to be released from hospital:\n"
                + "\n".join(f"Patient ID: {p.patient_id}, Name: {p.first_name} {p.last_name}" for p in patients_to_release)
            )
        return len(patients_to_release)

    def delete_patients_to_be_released():
        session.query(BedAssignment).filter(BedAssignment.days_of_stay <= 0).delete(synchronize_session="auto")

    def check_if_patient_has_bed(patient_id: int) -> bool:
        return session.query(BedAssignment).filter_by(patient_id=patient_id).first() is not None

    def get_patient_name_by_id(patient_id: int) -> str:
        patient = session.query(Patient).filter_by(patient_id=patient_id).first()
        return f"{patient.first_name} {patient.last_name}" if patient else "Unknown"

    try:
        if last_change == 1:
            logger.info(f"Current simulation day: {day_for_simulation}")
        else:
            logger.info(f"Rollback of simulation to day {day_for_simulation}")

        no_shows_list: List[NoShow] = []

        for iteration in range(day_for_simulation - 1):  # TODO: zrobić tak, żeby nie cofać dni
            if (
                (not only_patients_from_call) or iteration < day_for_simulation - 2
            ):  # przy iteracji z tego dnia, jeśli chcemy tylko pacjentów z calla, to nie wykona sie reszta kolejki
                should_log = iteration == day_for_simulation - 2 and last_change == 1
                should_give_no_shows = iteration == day_for_simulation - 2

                decrement_days_of_stay()
                number_of_patients_to_release = print_patients_to_be_released(log=should_log)
                delete_patients_to_be_released()

                assigned_beds = session.query(BedAssignment.bed_id).scalar_subquery()
                bed_ids = [b.bed_id for b in session.query(Bed).filter(~Bed.bed_id.in_(assigned_beds)).all()]

                queue = session.query(PatientQueue).order_by(PatientQueue.queue_id).all()
                bed_iterator = 0

                for i, entry in enumerate(queue):
                    if i + 1 > number_of_patients_to_release or bed_iterator >= len(bed_ids):
                        break
                    patient_id = entry.patient_id
                    will_come = random.choice([True] * 4 + [False])
                    if not will_come:
                        delete_patient_by_id_from_queue(patient_id)
                        no_show = NoShow(patient_id=patient_id, patient_name=get_patient_name_by_id(patient_id))
                        if should_give_no_shows:
                            no_shows_list.append(no_show)
                        if should_log:
                            logger.info(f"No-show: {no_show.patient_name}")
                    elif check_if_patient_has_bed(patient_id):
                        if should_log:
                            logger.info(f"Patient {patient_id} already has a bed")
                    else:
                        days = random.randint(1, 7)
                        assign_bed_to_patient(bed_ids[bed_iterator], patient_id, days, should_log)
                        delete_patient_by_id_from_queue(patient_id)
                        bed_iterator += 1

            if day_for_simulation in patients_consent_dictionary:
                patients_to_move = patients_consent_dictionary[day_for_simulation]
                for patient in patients_to_move:
                    assign_bed_to_patient(patient["bed_id"], patient["patient_id"], patient["days"], True)

        bed_assignments_and_queue: BedAssignmentsAndQueue = get_bed_assignments_and_queue()

        return ListOfTables(
            BedAssignment=bed_assignments_and_queue.BedAssignment,
            PatientQueue=bed_assignments_and_queue.PatientQueue,
            NoShows=[n.model_dump() for n in no_shows_list],
        )

    except Exception as e:
        error_message = f"Error occurred: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_message)
        return {"error": "Server Error", "message": error_message}


@app.get("/get-patient-data")
def get_patient_data(patient_id: int):
    patient = session.query(Patient).filter_by(patient_id=patient_id).first()
    queue_id = session.query(PatientQueue).filter_by(patient_id=patient_id).first().queue_id
    old_day, new_day = day_for_simulation + math.ceil(queue_id // random.randint(2, 4)), day_for_simulation
    return {"sickness": patient.sickness, "old_day": old_day, "new_day": new_day}


@app.get("/move-patient-to-bed-assignment", response_model=BedAssignmentsAndQueue)
def move_patient_to_bed_assignment(patient_id: int) -> BedAssignmentsAndQueue:
    global session
    delete_patient_by_id_from_queue(patient_id)

    bed_id: int | None = get_first_free_bed()
    if bed_id is None:
        raise Exception("No free bed found")
    days = random.randint(1, 7)
    # assign_bed_to_patient(bed_id, patient_id, days, True) # assign bed robimy tylko w get_tables

    if day_for_simulation in patients_consent_dictionary:
        patients_consent_dictionary[day_for_simulation].append({"patient_id": patient_id, "days": days, "bed_id": bed_id})
    else:
        patients_consent_dictionary[day_for_simulation] = [{"patient_id": patient_id, "days": days, "bed_id": bed_id}]

    bed_assignments_and_queue: BedAssignmentsAndQueue = get_bed_assignments_and_queue()

    return bed_assignments_and_queue


@app.post("/rollback-session", response_model=dict[str, int])
def rollback_session():  # in front-end: call at the end of the day (or before)
    global session
    session.rollback()
    return {"status": 200}


# session.close()
