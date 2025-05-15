import datetime
import random
from enum import Enum

from pydantic import BaseModel

from faker import Faker


class Urgency(str, Enum):
    URGENT = "pilny"
    STABLE = "stabilny"


class Patient(BaseModel):
    first_name: str
    last_name: str
    urgency: Urgency
    contact_phone: str
    sickness: str
    pesel: str


Faker.seed(42)

sicknesses = [
    "Niewydolność serca",
    "Choroba niedokrwienna serca",
    "Zawał mięśnia sercowego",
    "Migotanie przedsionków",
    "Nadciśnienie tętnicze",
    "Udar mózgu",
    "Krwotok śródczaszkowy",
    "Zator płucny",
    "Zapalenie płuc",
    "Przewlekła obturacyjna choroba płuc (POChP)",
    "Astma oskrzelowa",
    "Rozedma płuc",
    "Odma opłucnowa",
    "Zapalenie opłucnej",
    "Ropień płuca",
    "Gruźlica płuc",
    "Rak płuca",
    "Zapalenie oskrzeli",
    "Ostre zapalenie oskrzeli",
    "Ostre zapalenie gardła",
    "Ostre zapalenie migdałków",
    "Zapalenie zatok przynosowych",
    "Zapalenie ucha środkowego",
    "Zapalenie wyrostka robaczkowego",
    "Ostre zapalenie trzustki",
    "Przewlekłe zapalenie trzustki",
    "Kamica żółciowa",
    "Zapalenie pęcherzyka żółciowego",
    "Marskość wątroby",
    "Ostre zapalenie wątroby",
    "Rak wątroby",
    "Choroba wrzodowa żołądka",
    "Perforacja wrzodu żołądka",
    "Krwawienie z przewodu pokarmowego",
    "Zapalenie jelita grubego",
    "Choroba Leśniowskiego-Crohna",
    "Wrzodziejące zapalenie jelita grubego",
    "Niedrożność jelit",
    "Ostre zapalenie otrzewnej",
    "Przepuklina pachwinowa",
    "Przepuklina pępkowa",
    "Nowotwór jelita grubego",
    "Rak żołądka",
    "Ostre zapalenie nerek",
    "Przewlekła niewydolność nerek",
    "Kamica nerkowa",
    "Infekcja dróg moczowych",
    "Nowotwór nerki",
    "Zapalenie pęcherza moczowego",
    "Przerost prostaty",
]

fake = Faker("pl_PL")


def generate_random_date_between_ages(min_age, max_age):
    today = datetime.date.today()
    earliest_date = datetime.date(today.year - max_age, today.month, today.day)
    latest_date = datetime.date(today.year - min_age, today.month, today.day)

    earliest_days = earliest_date.toordinal()
    latest_days = latest_date.toordinal()

    return datetime.date.fromordinal(random.randint(earliest_days, latest_days))


def generate_fake_patient_data() -> Patient:
    if random.randint(1, 2) == 1:
        name = fake.first_name_female()
        surname = fake.last_name_female()
        pesel = fake.unique.pesel(date_of_birth=generate_random_date_between_ages(2, 100), sex="F")
    else:
        name = fake.first_name_male()
        surname = fake.last_name_male()
        pesel = fake.unique.pesel(date_of_birth=generate_random_date_between_ages(2, 100), sex="M")
    random_urgency = fake.enum(Urgency)
    phone_number = fake.phone_number().replace(" ", "").replace("+48", "")
    random_sickness = fake.random_element(sicknesses)
    return Patient(
        first_name=name,
        last_name=surname,
        urgency=random_urgency,
        contact_phone=phone_number,
        sickness=random_sickness,
        pesel=pesel,
    )
