"""
synthetic_data.py — Realistic Synthetic Clinical Trial Data Generator

Generates 200+ sites with 5000+ patient visit records for the PHOENIX-301 trial.
Uses a fixed random seed for reproducibility. Deliberately injects deviation
patterns into specific sites to create realistic risk differentiation.
"""

import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from .protocol import (
    BannedMedication,
    DeviationType,
    ProtocolSpecification,
    ProtocolVisit,
    get_protocol,
)


@dataclass
class MedicationRecord:
    """A medication the patient is currently taking."""
    medication_id: str
    patient_id: str
    drug_name: str
    start_date: date
    end_date: Optional[date] = None
    is_banned: bool = False


@dataclass
class PatientVisit:
    """A single recorded patient visit."""
    visit_id: str
    patient_id: str
    site_id: str
    visit_number: int
    visit_name: str
    scheduled_date: date
    actual_date: Optional[date]  # None = missed visit
    protocol_target_day: int
    actual_day: Optional[int]
    dose_administered_mg: Optional[float]
    protocol_dose_mg: float
    assessments_completed: list[str] = field(default_factory=list)
    assessments_required: list[str] = field(default_factory=list)
    active_medications: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class Patient:
    """A trial patient."""
    patient_id: str
    site_id: str
    enrollment_date: date
    age: int
    sex: str
    visits: list[PatientVisit] = field(default_factory=list)
    medications: list[MedicationRecord] = field(default_factory=list)


@dataclass
class Site:
    """A clinical trial site."""
    site_id: str
    site_name: str
    city: str
    country: str
    principal_investigator: str
    patients: list[Patient] = field(default_factory=list)
    is_problem_site: bool = False  # Internal flag for data generation


# Site name pools for realistic data
CITIES = [
    ("Boston", "USA"), ("New York", "USA"), ("Houston", "USA"), ("Chicago", "USA"),
    ("Los Angeles", "USA"), ("San Francisco", "USA"), ("Philadelphia", "USA"),
    ("Seattle", "USA"), ("Atlanta", "USA"), ("Miami", "USA"), ("Dallas", "USA"),
    ("Denver", "USA"), ("Phoenix", "USA"), ("Portland", "USA"), ("Minneapolis", "USA"),
    ("Nashville", "USA"), ("Cleveland", "USA"), ("Detroit", "USA"), ("Pittsburgh", "USA"),
    ("Baltimore", "USA"), ("St. Louis", "USA"), ("San Diego", "USA"),
    ("Toronto", "Canada"), ("Montreal", "Canada"), ("Vancouver", "Canada"),
    ("London", "UK"), ("Manchester", "UK"), ("Birmingham", "UK"), ("Edinburgh", "UK"),
    ("Berlin", "Germany"), ("Munich", "Germany"), ("Hamburg", "Germany"),
    ("Paris", "France"), ("Lyon", "France"), ("Marseille", "France"),
    ("Madrid", "Spain"), ("Barcelona", "Spain"), ("Milan", "Italy"), ("Rome", "Italy"),
    ("Amsterdam", "Netherlands"), ("Brussels", "Belgium"), ("Zurich", "Switzerland"),
    ("Vienna", "Austria"), ("Stockholm", "Sweden"), ("Oslo", "Norway"),
    ("Copenhagen", "Denmark"), ("Helsinki", "Finland"), ("Warsaw", "Poland"),
    ("Prague", "Czech Republic"), ("Budapest", "Hungary"),
    ("Tokyo", "Japan"), ("Osaka", "Japan"), ("Seoul", "South Korea"),
    ("Sydney", "Australia"), ("Melbourne", "Australia"), ("Auckland", "New Zealand"),
    ("São Paulo", "Brazil"), ("Buenos Aires", "Argentina"), ("Mexico City", "Mexico"),
    ("Mumbai", "India"), ("New Delhi", "India"), ("Singapore", "Singapore"),
    ("Tel Aviv", "Israel"), ("Johannesburg", "South Africa"), ("Cape Town", "South Africa"),
]

INSTITUTION_TYPES = [
    "University Hospital", "Medical Center", "Cancer Center", "Research Hospital",
    "Clinical Research Institute", "Academic Medical Center", "Regional Medical Center",
    "Teaching Hospital", "Oncology Center"
]

PI_FIRST_NAMES = [
    "James", "Maria", "Robert", "Sarah", "Michael", "Jennifer", "William", "Lisa",
    "David", "Emily", "Thomas", "Anna", "Richard", "Catherine", "Charles", "Laura",
    "Joseph", "Margaret", "Daniel", "Elizabeth", "Christopher", "Susan", "Andrew",
    "Patricia", "Steven", "Rebecca", "George", "Karen", "Edward", "Hiroshi",
    "Yuki", "Wei", "Min", "Raj", "Priya", "Ahmed", "Fatima", "Hans", "Ingrid",
    "Pierre", "Sophie", "Carlos", "Isabella", "Olga", "Dmitri", "Sven", "Akiko"
]

PI_LAST_NAMES = [
    "Chen", "Smith", "Johnson", "Williams", "Patel", "Kim", "Garcia", "Martinez",
    "Anderson", "Taylor", "Thomas", "Harris", "Clark", "Lewis", "Robinson",
    "Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Tanaka", "Yamamoto",
    "Sato", "Suzuki", "Nakamura", "Dubois", "Martin", "Bernard", "Silva",
    "Santos", "Johansson", "Eriksson", "Petrov", "Novak", "Kowalski",
    "Goldberg", "Shapiro", "van der Berg", "De Vries", "O'Brien", "Walsh"
]

# Non-banned medications for realistic medication lists
SAFE_MEDICATIONS = [
    "Metformin", "Lisinopril", "Amlodipine", "Omeprazole", "Acetaminophen",
    "Ibuprofen", "Levothyroxine", "Albuterol", "Gabapentin", "Sertraline",
    "Fluoxetine", "Losartan", "Hydrochlorothiazide", "Furosemide",
    "Prednisone", "Tramadol", "Ondansetron", "Lorazepam", "Diphenhydramine",
    "Cetirizine", "Ranitidine", "Calcium Carbonate", "Vitamin D",
    "Iron Supplement", "Folic Acid", "Multivitamin"
]


def generate_trial_data(seed: int = 42) -> tuple[list[Site], ProtocolSpecification]:
    """
    Generate the complete synthetic trial dataset.
    
    Returns:
        Tuple of (list of sites with patients and visits, protocol specification)
    """
    rng = random.Random(seed)
    protocol = get_protocol()

    # Generate 210 sites
    num_sites = 210
    sites: list[Site] = []

    # Shuffle cities and cycle through them
    city_pool = list(CITIES)
    rng.shuffle(city_pool)

    # Designate 8 problem sites (indices chosen deterministically)
    problem_site_indices = set(rng.sample(range(num_sites), 8))

    for i in range(num_sites):
        city, country = city_pool[i % len(city_pool)]
        institution = rng.choice(INSTITUTION_TYPES)
        pi_name = f"Dr. {rng.choice(PI_FIRST_NAMES)} {rng.choice(PI_LAST_NAMES)}"

        site = Site(
            site_id=f"SITE-{i + 1:03d}",
            site_name=f"{city} {institution}",
            city=city,
            country=country,
            principal_investigator=pi_name,
            is_problem_site=(i in problem_site_indices)
        )
        sites.append(site)

    # Enroll patients across sites
    trial_start = date(2024, 3, 1)
    patient_counter = 0

    for site in sites:
        # Problem sites tend to have more patients (more opportunities for deviation)
        if site.is_problem_site:
            num_patients = rng.randint(3, 5)
        else:
            num_patients = rng.randint(2, 4)

        for p in range(num_patients):
            patient_counter += 1
            enrollment_date = trial_start + timedelta(days=rng.randint(0, 180))

            patient = Patient(
                patient_id=f"PAT-{patient_counter:04d}",
                site_id=site.site_id,
                enrollment_date=enrollment_date,
                age=rng.randint(35, 78),
                sex=rng.choice(["M", "F"])
            )

            # Generate some background medications
            num_meds = rng.randint(1, 5)
            for m in range(num_meds):
                med_name = rng.choice(SAFE_MEDICATIONS)
                patient.medications.append(MedicationRecord(
                    medication_id=f"MED-{patient_counter:04d}-{m + 1:02d}",
                    patient_id=patient.patient_id,
                    drug_name=med_name,
                    start_date=enrollment_date - timedelta(days=rng.randint(30, 365)),
                    is_banned=False
                ))

            # Generate visits according to protocol
            _generate_patient_visits(rng, patient, site, protocol)

            site.patients.append(patient)

    return sites, protocol


def _generate_patient_visits(
    rng: random.Random,
    patient: Patient,
    site: Site,
    protocol: ProtocolSpecification
) -> None:
    """Generate visit records for a patient, including realistic deviations."""

    # Problem sites have much higher deviation rates
    if site.is_problem_site:
        missed_visit_prob = 0.12
        late_visit_prob = 0.20
        dose_error_prob = 0.10
        banned_med_prob = 0.08
        missing_assessment_prob = 0.15
    else:
        missed_visit_prob = 0.02
        late_visit_prob = 0.06
        dose_error_prob = 0.02
        banned_med_prob = 0.01
        missing_assessment_prob = 0.03

    # How many visits has this patient completed? (simulate ongoing trial)
    max_visit_index = rng.randint(4, len(protocol.visits))

    for visit_idx in range(max_visit_index):
        pv = protocol.visits[visit_idx]
        scheduled_date = patient.enrollment_date + timedelta(days=pv.target_day)
        visit_counter = len(patient.visits) + 1

        # Decide if this visit has a deviation
        is_missed = rng.random() < missed_visit_prob
        is_late = not is_missed and rng.random() < late_visit_prob
        has_dose_error = rng.random() < dose_error_prob
        has_banned_med = rng.random() < banned_med_prob
        has_missing_assessment = rng.random() < missing_assessment_prob

        # Actual visit date
        if is_missed:
            actual_date = None
            actual_day = None
        elif is_late:
            # Late by varying amounts
            if site.is_problem_site:
                late_days = rng.randint(3, 45)
            else:
                late_days = rng.randint(2, 15)
            actual_date = scheduled_date + timedelta(days=late_days)
            actual_day = pv.target_day + late_days
        else:
            # On time (within window)
            offset = rng.randint(-min(pv.window_before, 2), min(pv.window_after, 2))
            actual_date = scheduled_date + timedelta(days=offset)
            actual_day = pv.target_day + offset

        # Dose
        protocol_dose = protocol.dose_rules[0].dose_mg
        if has_dose_error and not is_missed:
            if site.is_problem_site:
                # Problem sites: larger dose errors
                deviation_pct = rng.uniform(-35, 35)
            else:
                deviation_pct = rng.uniform(-15, 15)
            dose_administered = round(protocol_dose * (1 + deviation_pct / 100), 1)
        elif not is_missed:
            # Small natural variation
            dose_administered = round(protocol_dose * (1 + rng.uniform(-2, 2) / 100), 1)
        else:
            dose_administered = None

        # Assessments
        if is_missed:
            assessments_completed = []
        elif has_missing_assessment:
            # Miss 1-2 assessments
            num_to_miss = rng.randint(1, min(2, len(pv.required_assessments)))
            missed_assessments = set(rng.sample(pv.required_assessments, num_to_miss))
            assessments_completed = [a for a in pv.required_assessments
                                     if a not in missed_assessments]
        else:
            assessments_completed = list(pv.required_assessments)

        # Active medications (including potential banned ones)
        active_meds = [med.drug_name for med in patient.medications]
        if has_banned_med and not is_missed:
            banned_med = rng.choice(protocol.banned_medications)
            active_meds.append(banned_med.drug_name)
            # Add the banned medication to patient's record
            patient.medications.append(MedicationRecord(
                medication_id=f"MED-{patient.patient_id}-BAN-{visit_counter}",
                patient_id=patient.patient_id,
                drug_name=banned_med.drug_name,
                start_date=actual_date - timedelta(days=rng.randint(1, 14))
                           if actual_date else scheduled_date,
                is_banned=True
            ))

        visit = PatientVisit(
            visit_id=f"VIS-{patient.patient_id}-{visit_counter:02d}",
            patient_id=patient.patient_id,
            site_id=site.site_id,
            visit_number=pv.visit_number,
            visit_name=pv.visit_name,
            scheduled_date=scheduled_date,
            actual_date=actual_date,
            protocol_target_day=pv.target_day,
            actual_day=actual_day,
            dose_administered_mg=dose_administered,
            protocol_dose_mg=protocol_dose,
            assessments_completed=assessments_completed,
            assessments_required=list(pv.required_assessments),
            active_medications=active_meds,
        )

        patient.visits.append(visit)


def get_trial_statistics(sites: list[Site]) -> dict:
    """Compute summary statistics for the trial."""
    total_patients = sum(len(s.patients) for s in sites)
    total_visits = sum(
        len(p.visits) for s in sites for p in s.patients
    )
    total_missed = sum(
        1 for s in sites for p in s.patients for v in p.visits
        if v.actual_date is None
    )

    countries = set(s.country for s in sites)

    return {
        "total_sites": len(sites),
        "total_patients": total_patients,
        "total_visits": total_visits,
        "total_missed_visits": total_missed,
        "countries": len(countries),
        "country_list": sorted(countries),
        "problem_sites": sum(1 for s in sites if s.is_problem_site),
    }
