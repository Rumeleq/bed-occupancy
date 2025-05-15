from pydantic import BaseModel
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class BedAssignmentResponse(BaseModel):
    bed_id: int
    patient_id: int
    patient_name: str
    sickness: str
    days_of_stay: int


class PatientQueueResponse(BaseModel):
    place_in_queue: int
    patient_id: int
    patient_name: str


class NoShow(BaseModel):
    patient_id: int
    patient_name: str


class ListOfTables(BaseModel):
    BedAssignment: list[BedAssignmentResponse]
    PatientQueue: list[PatientQueueResponse]
    NoShows: list[NoShow]


class BedAssignmentsAndQueue(BaseModel):
    BedAssignment: list[BedAssignmentResponse]
    PatientQueue: list[PatientQueueResponse]


class Patient(Base):
    __tablename__ = "patients"
    patient_id = Column(Integer, primary_key=True)
    first_name = Column(String)
    last_name = Column(String)
    urgency = Column(String)
    contact_phone = Column(String)
    sickness = Column(String)

    bed_assignments = relationship("BedAssignment", back_populates="patient")
    queue_entry = relationship("PatientQueue", back_populates="patient")


class Bed(Base):
    __tablename__ = "beds"
    bed_id = Column(Integer, primary_key=True)

    assignments = relationship("BedAssignment", back_populates="bed")


class BedAssignment(Base):
    __tablename__ = "bed_assignments"
    bed_id = Column(Integer, ForeignKey("beds.bed_id"), primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.patient_id"))
    days_of_stay = Column(Integer)

    bed = relationship("Bed", back_populates="assignments")
    patient = relationship("Patient", back_populates="bed_assignments")


class PatientQueue(Base):
    __tablename__ = "patient_queue"
    queue_id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.patient_id"))

    patient = relationship("Patient", back_populates="queue_entry")
