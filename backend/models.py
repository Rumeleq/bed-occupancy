from pydantic import BaseModel
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class BedAssignmentResponse(BaseModel):
    bed_id: int
    patient_id: int
    patient_name: str
    sickness: str
    PESEL: str
    days_of_stay: int

    def __repr__(self):
        return (
            f"{self.bed_id=}, {self.patient_id=}, {self.patient_name=}, {self.sickness=}, {self.PESEL=}, {self.days_of_stay=}"
        )


class PatientQueueResponse(BaseModel):
    place_in_queue: int
    patient_id: int
    patient_name: str
    PESEL: str

    def __repr__(self):
        return f"{self.place_in_queue=} {self.patient_id=}, {self.patient_name=}, {self.PESEL=}"


class NoShow(BaseModel):
    patient_id: int
    patient_name: str

    def __repr__(self):
        return f"{self.patient_id=}, {self.patient_name=}"


class ListOfTables(BaseModel):
    BedAssignment: list[BedAssignmentResponse]
    PatientQueue: list[PatientQueueResponse]
    NoShows: list[NoShow]

    def __repr__(self):
        return f"{self.BedAssignment=},\n {self.PatientQueue=},\n {self.NoShows=}"


class BedAssignmentsAndQueue(BaseModel):
    BedAssignment: list[BedAssignmentResponse]
    PatientQueue: list[PatientQueueResponse]

    def __repr__(self):
        return f"{self.BedAssignment=},\n {self.PatientQueue=}"


class Patient(Base):
    __tablename__ = "patients"
    patient_id = Column(Integer, primary_key=True)
    first_name = Column(String)
    last_name = Column(String)
    urgency = Column(String)
    contact_phone = Column(String)
    sickness = Column(String)
    pesel = Column(String, unique=True)

    bed_assignments = relationship("BedAssignment", back_populates="patient")
    queue_entry = relationship("PatientQueue", back_populates="patient")

    def __str__(self):
        return f"patient_id: {self.patient_id}, name: {self.first_name + ' ' + self.last_name}"

    def __repr__(self):
        return self.__str__()


class Bed(Base):
    __tablename__ = "beds"
    bed_id = Column(Integer, primary_key=True)

    assignments = relationship("BedAssignment", back_populates="bed")

    def __str__(self):
        return f"bed_id: {self.bed_id}"

    def __repr__(self):
        return self.__str__()


class BedAssignment(Base):
    __tablename__ = "bed_assignments"
    bed_id = Column(Integer, ForeignKey("beds.bed_id"), primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.patient_id"))
    days_of_stay = Column(Integer)

    bed = relationship("Bed", back_populates="assignments")
    patient = relationship("Patient", back_populates="bed_assignments")

    def __str__(self):
        return f"bed_id: {self.bed_id}, patient_id: {self.patient_id}, days_of_stay: {self.days_of_stay}"

    def __repr__(self):
        return self.__str__()


class PatientQueue(Base):
    __tablename__ = "patient_queue"
    queue_id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.patient_id"))

    patient = relationship("Patient", back_populates="queue_entry")

    def __str__(self):
        return f"queue_id: {self.queue_id}, patient_id: {self.patient_id}"

    def __repr__(self):
        return self.__str__()
