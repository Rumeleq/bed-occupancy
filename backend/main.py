import json
import logging.config
import random
import traceback
from pathlib import Path
from typing import List

from agent import check_patient_consent_to_reschedule, establish_voice_conversation, prepare_conversation
from db_operations import get_session
from fastapi import FastAPI, Query
from models import Bed, BedAssignment, ListOfTables, NoShow, Patient, PatientQueue

logger = logging.getLogger("hospital_logger")
config_file = Path("logger_config.json")
with open(config_file) as f:
    config = json.load(f)
logging.config.dictConfig(config)

app = FastAPI()
day_for_simulation = 1
last_change = 1
session = get_session()


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


def get_first_free_bed() -> int:
    global session
    return session.query(BedAssignment).filter_by(patient_id=0).first().bed_id


@app.get("/get-tables", response_model=ListOfTables)
def get_tables():
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
        random.seed(43)

        if last_change == 1:
            logger.info(f"Current simulation day: {day_for_simulation}")
        else:
            logger.info(f"Rollback of simulation to day {day_for_simulation}")

        no_shows_list: List[NoShow] = []

        for iteration in range(day_for_simulation - 1):
            should_log = iteration == day_for_simulation - 2 and last_change == 1
            should_give_no_shows = iteration == day_for_simulation - 2

            decrement_days_of_stay()
            number_of_patients_to_release = print_patients_to_be_released(log=should_log)
            delete_patients_to_be_released()

            assigned_beds = session.query(BedAssignment.bed_id).subquery()
            bed_ids = [b.bed_id for b in session.query(Bed).filter(~Bed.bed_id.in_(assigned_beds)).all()]

            queue = session.query(PatientQueue).order_by(PatientQueue.queue_id).all()
            bed_iterator = 0

            for i, entry in enumerate(queue):
                if i + 1 > number_of_patients_to_release:
                    break
                patient_id = entry.patient_id
                if bed_iterator >= len(bed_ids):
                    break
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
            days_of_stay = ba.days_of_stay if ba else 0

            bed_assignments.append(
                {
                    "bed_id": bed.bed_id,
                    "patient_id": ba.patient_id if ba else 0,
                    "patient_name": patient_name,
                    "sickness": sickness,
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
                }
            )

        return ListOfTables(
            BedAssignment=bed_assignments, PatientQueue=queue_data, NoShows=[n.model_dump() for n in no_shows_list]
        )

    except Exception as e:
        error_message = f"Error occurred: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_message)
        return {"error": "Server Error", "message": error_message}


def handle_patient_rescheduling(name: str, surname: str, sickness: str, old_day: int, new_day: int) -> bool:
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
    conversation = prepare_conversation(
        patient_name=name,
        patient_surname=surname,
        patient_sickness=sickness,
        current_visit_day=old_day,
        suggested_appointment_day=new_day,
    )
    conversation_id = establish_voice_conversation(conversation)
    return check_patient_consent_to_reschedule(conversation_id)


@app.get("/create-voice-call", response_model=ListOfTables)
def create_voice_call(patient_id: int) -> ListOfTables:
    session = get_session()
    patient = session.query(Patient).filter_by(patient_id=patient_id).first()

    # consent = handle_patient_rescheduling(patient.first_name, patient.last_name, patient.sickness, old_day, new_day)
    consent = True
    if consent:
        delete_patient_by_id_from_queue(patient.patient_id)

        random.seed(43)
        bed_id: int = get_first_free_bed()
        days = random.randint(1, 7)
        assign_bed_to_patient(bed_id, patient.patient_id, days, True)

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
        days_of_stay = ba.days_of_stay if ba else 0

        bed_assignments.append(
            {
                "bed_id": bed.bed_id,
                "patient_id": ba.patient_id if ba else 0,
                "patient_name": patient_name,
                "sickness": sickness,
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
            }
        )

    return ListOfTables(
        # BedAssignment=bed_assignments, PatientQueue=queue_data, NoShows=[n.model_dump() for n in no_shows_list]
    )


@app.post("/rollback-session", response_model=dict[str, int])
def rollback_session():
    global session
    session.rollback()
    return {"status": 200}


session.close()
