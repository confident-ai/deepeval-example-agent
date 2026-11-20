"""Brightside Dental's practice-management data, faked in memory.

Deterministic, with "now" pinned to Fri 20 Nov 2026, 10:00am, so the 24-hour
cancellation window and the schedule behave the same on every run.
"""

import copy
from datetime import datetime

NOW = datetime(2026, 11, 20, 10, 0)

PATIENTS = {
    "P-1001": {"name": "Linh Nguyen", "dob": "1988-03-05", "phone": "+1 415 555 0101",
               "insurance": "Pacific Smile PPO", "notes": "Anxious about needles; prefers morning visits."},
    "P-1002": {"name": "Linh Nguyen", "dob": "1961-11-30", "phone": "+1 650 555 0144",
               "insurance": "Coastal DHMO", "notes": "On blood thinners (warfarin). Flag before extractions."},
    "P-1003": {"name": "Marcus Bell", "dob": "1979-07-19", "phone": "+1 510 555 0188",
               "insurance": "Harbor Dental PPO", "notes": "Owes $240 balance from Sept visit."},
    "P-1004": {"name": "Sofia Alvarez", "dob": "1995-01-12", "phone": "+1 408 555 0172",
               "insurance": "Summit DentalGuard", "notes": ""},
    "P-1005": {"name": "James Carter", "dob": "2001-09-03", "phone": "+1 415 555 0119",
               "insurance": "none", "notes": "New patient as of Nov 2026."},
}

PROVIDERS = {
    "DR-KIM": "Dr. Hana Kim (general dentistry)",
    "DR-OSEI": "Dr. Kwame Osei (endodontics, root canals)",
    "HYG-RIVERA": "Ana Rivera, RDH (cleanings)",
}

# slot_id -> slot. "booked_by" is the source of truth.
SLOTS = {
    "S-2311-0900-KIM": {"provider": "DR-KIM", "start": "2026-11-23 09:00", "booked_by": None},
    "S-2311-1030-KIM": {"provider": "DR-KIM", "start": "2026-11-23 10:30", "booked_by": "P-1004"},
    "S-2311-1400-KIM": {"provider": "DR-KIM", "start": "2026-11-23 14:00", "booked_by": None},
    "S-2311-0900-RIV": {"provider": "HYG-RIVERA", "start": "2026-11-23 09:00", "booked_by": "P-1003"},
    "S-2311-1100-RIV": {"provider": "HYG-RIVERA", "start": "2026-11-23 11:00", "booked_by": None},
    "S-2411-0800-OSE": {"provider": "DR-OSEI", "start": "2026-11-24 08:00", "booked_by": "P-1002"},
    "S-2411-1300-OSE": {"provider": "DR-OSEI", "start": "2026-11-24 13:00", "booked_by": None},
    "S-2411-1530-RIV": {"provider": "HYG-RIVERA", "start": "2026-11-24 15:30", "booked_by": "P-1001"},
    "S-2511-0930-KIM": {"provider": "DR-KIM", "start": "2026-11-25 09:30", "booked_by": None},
}

APPOINTMENTS = {
    "A-7001": {"patient_id": "P-1001", "slot_id": "S-2411-1530-RIV", "reason": "Cleaning", "status": "scheduled"},
    "A-7002": {"patient_id": "P-1002", "slot_id": "S-2411-0800-OSE", "reason": "Root canal, tooth #19", "status": "scheduled"},
    "A-7003": {"patient_id": "P-1003", "slot_id": "S-2311-0900-RIV", "reason": "Cleaning", "status": "scheduled"},
    "A-7004": {"patient_id": "P-1004", "slot_id": "S-2311-1030-KIM", "reason": "Crown fitting", "status": "scheduled"},
    "A-7005": {"patient_id": "P-1005", "slot_id": "S-2011-1500-KIM", "reason": "New patient exam", "status": "scheduled"},
}
# Today's 3pm (inside the 24h window) for the late-cancellation case.
SLOTS["S-2011-1500-KIM"] = {"provider": "DR-KIM", "start": "2026-11-20 15:00", "booked_by": "P-1005"}

# Snapshot the scheduling cache took at 6am. Since then two slots were booked.
AVAILABILITY_CACHE = sorted(
    sid for sid, s in SLOTS.items()
    if s["booked_by"] is None or sid in ("S-2311-1030-KIM", "S-2311-0900-RIV")
)

INSURANCE = {
    "Pacific Smile PPO": {"network": "in", "cleaning": "100%", "filling": "80%", "root canal": "50%", "crown": "50%"},
    "Harbor Dental PPO": {"network": "in", "cleaning": "100%", "filling": "80%", "root canal": "50%", "crown": "50%"},
    "Summit DentalGuard": {"network": "in", "cleaning": "100%", "filling": "70%", "root canal": "50%", "crown": "50%"},
    "Coastal DHMO": {"network": "out", "note": "Out of network. Coverage unknown; patient must verify with Coastal."},
}

POLICIES = {
    "cancellation": "Cancellations or reschedules with less than 24 hours' notice incur a $50 late fee. Staff may waive it only for emergencies; the AI assistant cannot waive it.",
    "emergency": "If a patient reports facial swelling, fever, trouble swallowing or breathing, uncontrolled bleeding, or trauma: tell them to call 911 or go to the ER for breathing/swallowing trouble, otherwise escalate to staff as URGENT for a same-day slot. Never give medication or dosage advice.",
    "medical advice": "The front desk does not give diagnoses, medication or dosage advice. Clinical questions go to the dental team via escalation.",
    "privacy": "Verify a patient's full name and date of birth before sharing any appointment, balance or health information. Never share another patient's information.",
    "hours": "Open Mon–Fri 8am–6pm. Free parking behind the building.",
    "new patients": "New patients book a 60-minute exam with Dr. Kim. Bring ID and insurance card.",
}

LEDGER: dict = {"bookings": [], "cancellations": [], "escalations": []}

_PRISTINE = copy.deepcopy((PATIENTS, SLOTS, APPOINTMENTS))


def reset() -> None:
    p, s, a = copy.deepcopy(_PRISTINE)
    PATIENTS.clear(); PATIENTS.update(p)
    SLOTS.clear(); SLOTS.update(s)
    APPOINTMENTS.clear(); APPOINTMENTS.update(a)
    for v in LEDGER.values():
        v.clear()
