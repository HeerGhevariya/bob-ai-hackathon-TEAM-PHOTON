"""
fhir_adapter.py — FHIR R4 Data Shape Export

Transforms internal clinical trial data into HL7 FHIR R4 resource shapes.
This demonstrates that the system's data layer is aligned with the industry
standard format hospitals and EHR systems use to exchange patient data.

In a production deployment, this adapter works in reverse too:
real FHIR-formatted data from an EHR/EDC system would be ingested
and normalized into the internal schema — with zero changes to the
detection, scoring, or reporting logic.

FHIR Resource Mappings:
    Patient      → FHIR Patient resource
    PatientVisit → FHIR Encounter resource
    Dose record  → FHIR MedicationAdministration resource
    Medications  → FHIR MedicationStatement resource
    Deviation    → FHIR DetectedIssue resource

CDISC SDTM Domain Mappings:
    Patient      → DM (Demographics)
    PatientVisit → SV (Subject Visits)
    Medications  → CM (Concomitant Medications)
    Assessments  → FA (Findings About)
"""

from datetime import date
from typing import Optional

from .synthetic_data import Patient, PatientVisit, Site
from .deviation_detector import Deviation


def patient_to_fhir(patient: Patient) -> dict:
    """Transform a Patient into a FHIR R4 Patient resource shape."""
    return {
        "resourceType": "Patient",
        "id": patient.patient_id,
        "meta": {
            "profile": ["http://hl7.org/fhir/StructureDefinition/Patient"],
            "source": "TrialGuard-AI/PHOENIX-301",
        },
        "identifier": [
            {
                "use": "usual",
                "system": "urn:trialguard:patient-id",
                "value": patient.patient_id,
            },
            {
                "use": "secondary",
                "system": "urn:cdisc:sdtm:DM",
                "value": patient.patient_id,
                "assigner": {"display": "CDISC SDTM Demographics (DM) domain"},
            },
        ],
        "active": True,
        "gender": "male" if patient.sex == "M" else "female",
        "birthDate": str(date.today().year - patient.age),  # Approximate
        "extension": [
            {
                "url": "urn:trialguard:enrollment-date",
                "valueDate": patient.enrollment_date.isoformat(),
            },
            {
                "url": "urn:trialguard:site-id",
                "valueString": patient.site_id,
            },
            {
                "url": "urn:cdisc:sdtm:domain",
                "valueCode": "DM",
            },
        ],
    }


def visit_to_fhir(visit: PatientVisit, enrollment_date: date) -> dict:
    """Transform a PatientVisit into a FHIR R4 Encounter resource shape."""
    status = "finished" if visit.actual_date else "cancelled"

    encounter = {
        "resourceType": "Encounter",
        "id": visit.visit_id,
        "meta": {
            "profile": ["http://hl7.org/fhir/StructureDefinition/Encounter"],
            "source": "TrialGuard-AI/PHOENIX-301",
        },
        "identifier": [
            {
                "system": "urn:trialguard:visit-id",
                "value": visit.visit_id,
            },
            {
                "system": "urn:cdisc:sdtm:SV",
                "value": f"SV-{visit.visit_number}",
                "assigner": {"display": "CDISC SDTM Subject Visits (SV) domain"},
            },
        ],
        "status": status,
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "AMB",
            "display": "ambulatory",
        },
        "type": [
            {
                "coding": [
                    {
                        "system": "urn:trialguard:visit-type",
                        "code": visit.visit_name.lower().replace(" ", "_"),
                        "display": visit.visit_name,
                    }
                ]
            }
        ],
        "subject": {"reference": f"Patient/{visit.patient_id}"},
        "period": {},
        "extension": [
            {
                "url": "urn:trialguard:visit-number",
                "valueInteger": visit.visit_number,
            },
            {
                "url": "urn:trialguard:protocol-target-day",
                "valueInteger": visit.protocol_target_day,
            },
            {
                "url": "urn:trialguard:scheduled-date",
                "valueDate": visit.scheduled_date.isoformat(),
            },
            {
                "url": "urn:cdisc:sdtm:domain",
                "valueCode": "SV",
            },
        ],
    }

    if visit.actual_date:
        encounter["period"]["start"] = visit.actual_date.isoformat()
        encounter["period"]["end"] = visit.actual_date.isoformat()

    return encounter


def dose_to_fhir(visit: PatientVisit) -> Optional[dict]:
    """Transform a visit's dose record into a FHIR R4 MedicationAdministration resource."""
    if visit.dose_administered_mg is None or visit.actual_date is None:
        return None

    return {
        "resourceType": "MedicationAdministration",
        "id": f"DOSE-{visit.visit_id}",
        "meta": {
            "profile": ["http://hl7.org/fhir/StructureDefinition/MedicationAdministration"],
            "source": "TrialGuard-AI/PHOENIX-301",
        },
        "status": "completed",
        "medicationCodeableConcept": {
            "coding": [
                {
                    "system": "urn:trialguard:study-drug",
                    "code": "PNX-301",
                    "display": "Phoenixin (PNX-301)",
                }
            ],
        },
        "subject": {"reference": f"Patient/{visit.patient_id}"},
        "context": {"reference": f"Encounter/{visit.visit_id}"},
        "effectiveDateTime": visit.actual_date.isoformat(),
        "dosage": {
            "dose": {
                "value": visit.dose_administered_mg,
                "unit": "mg",
                "system": "http://unitsofmeasure.org",
                "code": "mg",
            },
            "route": {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "26643006",
                        "display": "Oral route",
                    }
                ],
            },
        },
        "extension": [
            {
                "url": "urn:trialguard:protocol-dose-mg",
                "valueDecimal": visit.protocol_dose_mg,
            },
        ],
    }


def medication_to_fhir(patient_id: str, drug_name: str, visit_date: date) -> dict:
    """Transform an active medication into a FHIR R4 MedicationStatement resource."""
    return {
        "resourceType": "MedicationStatement",
        "id": f"MED-{patient_id}-{drug_name.replace(' ', '-').lower()}",
        "meta": {
            "profile": ["http://hl7.org/fhir/StructureDefinition/MedicationStatement"],
            "source": "TrialGuard-AI/PHOENIX-301",
        },
        "status": "active",
        "medicationCodeableConcept": {
            "coding": [
                {
                    "system": "urn:trialguard:medication",
                    "code": drug_name.lower().replace(" ", "_"),
                    "display": drug_name,
                }
            ],
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "effectiveDateTime": visit_date.isoformat(),
        "extension": [
            {
                "url": "urn:cdisc:sdtm:domain",
                "valueCode": "CM",
            },
        ],
    }


def deviation_to_fhir(deviation: Deviation) -> dict:
    """Transform a Deviation into a FHIR R4 DetectedIssue resource."""
    severity_map = {
        "major": "high",
        "minor": "moderate",
        "administrative": "low",
    }

    return {
        "resourceType": "DetectedIssue",
        "id": deviation.deviation_id,
        "meta": {
            "profile": ["http://hl7.org/fhir/StructureDefinition/DetectedIssue"],
            "source": "TrialGuard-AI/PHOENIX-301",
        },
        "status": "final",
        "severity": severity_map.get(deviation.severity, "moderate"),
        "code": {
            "coding": [
                {
                    "system": "urn:trialguard:deviation-type",
                    "code": deviation.deviation_type.value,
                    "display": deviation.deviation_type.value.replace("_", " ").title(),
                },
                {
                    "system": "urn:ich:e6r2:gcp",
                    "code": deviation.severity or "unclassified",
                    "display": f"ICH E6(R2) — {(deviation.severity or 'unclassified').title()}",
                },
            ],
        },
        "patient": {"reference": f"Patient/{deviation.patient_id}"},
        "identifiedDateTime": deviation.detected_date.isoformat() if deviation.detected_date else None,
        "detail": deviation.description,
        "reference": [
            {"reference": f"Encounter/{deviation.visit_id}"},
        ],
        "extension": [
            {
                "url": "urn:trialguard:expected-value",
                "valueString": deviation.expected_value,
            },
            {
                "url": "urn:trialguard:actual-value",
                "valueString": deviation.actual_value,
            },
            {
                "url": "urn:trialguard:protocol-reference",
                "valueString": deviation.protocol_reference,
            },
            {
                "url": "urn:trialguard:site-id",
                "valueString": deviation.site_id,
            },
        ],
    }


def site_to_fhir_bundle(site: Site, deviations: list[Deviation] = None) -> dict:
    """
    Export a complete site as a FHIR R4 Bundle.

    Includes all patients, encounters, medication administrations,
    medication statements, and detected issues for the site.
    """
    entries = []

    for patient in site.patients:
        # Patient resource
        entries.append({
            "resource": patient_to_fhir(patient),
            "request": {"method": "PUT", "url": f"Patient/{patient.patient_id}"},
        })

        for visit in patient.visits:
            # Encounter resource
            entries.append({
                "resource": visit_to_fhir(visit, patient.enrollment_date),
                "request": {"method": "PUT", "url": f"Encounter/{visit.visit_id}"},
            })

            # MedicationAdministration (dose)
            dose = dose_to_fhir(visit)
            if dose:
                entries.append({
                    "resource": dose,
                    "request": {"method": "PUT", "url": f"MedicationAdministration/{dose['id']}"},
                })

            # MedicationStatements (active meds)
            if visit.actual_date:
                for med_name in visit.active_medications:
                    med = medication_to_fhir(visit.patient_id, med_name, visit.actual_date)
                    entries.append({
                        "resource": med,
                        "request": {"method": "PUT", "url": f"MedicationStatement/{med['id']}"},
                    })

    # Detected issues (deviations)
    if deviations:
        for dev in deviations:
            entries.append({
                "resource": deviation_to_fhir(dev),
                "request": {"method": "PUT", "url": f"DetectedIssue/{dev.deviation_id}"},
            })

    return {
        "resourceType": "Bundle",
        "type": "transaction",
        "meta": {
            "source": "TrialGuard-AI/PHOENIX-301",
            "tag": [
                {"system": "urn:trialguard:site-id", "code": site.site_id},
                {"system": "urn:cdisc:study-id", "code": "PHOENIX-301"},
            ],
        },
        "total": len(entries),
        "entry": entries,
    }
