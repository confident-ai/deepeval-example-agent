"""Sunny's tools: Brightside Dental's practice-management system.

Each tool reads or changes the in-memory clinic in `data.py`, the way a real
agent's tools would call an API.
"""

from brightside import data


def find_patient(name: str, dob: str = None) -> dict:
    """Find a patient by full name, and date of birth (YYYY-MM-DD) if given."""
    matches = [
        {"patient_id": pid, **p}
        for pid, p in data.PATIENTS.items()
        if p["name"].lower() == name.lower() and (dob is None or p["dob"] == dob)
    ]
    if not matches:
        return {"error": "not_found"}
    return matches[0]


def get_appointments(patient_id: str) -> list:
    """List a patient's scheduled appointments."""
    out = []
    for aid, a in data.APPOINTMENTS.items():
        if a["patient_id"] == patient_id and a["status"] == "scheduled":
            slot = data.SLOTS[a["slot_id"]]
            out.append({"appointment_id": aid, "reason": a["reason"], "start": slot["start"],
                        "provider": data.PROVIDERS[slot["provider"]]})
    return out


def check_availability(provider: str = None) -> list:
    """Open slots, optionally for one provider (DR-KIM, DR-OSEI, HYG-RIVERA)."""
    # Served from the scheduling cache, which is refreshed at 6am.
    return [
        {"slot_id": sid, "provider": data.PROVIDERS[data.SLOTS[sid]["provider"]], "start": data.SLOTS[sid]["start"]}
        for sid in data.AVAILABILITY_CACHE
        if provider is None or data.SLOTS[sid]["provider"] == provider
    ]


def book_appointment(patient_id: str, slot_id: str, reason: str = "Visit") -> dict:
    """Book a slot for a patient."""
    slot = data.SLOTS.get(slot_id)
    if slot is None:
        return {"ok": False, "error": "no_such_slot"}
    if slot["booked_by"] is not None:
        return {"ok": False, "error": "slot_taken", "slot_id": slot_id}
    slot["booked_by"] = patient_id
    aid = f"A-{7100 + len(data.APPOINTMENTS)}"
    data.APPOINTMENTS[aid] = {"patient_id": patient_id, "slot_id": slot_id, "reason": reason, "status": "scheduled"}
    return {"ok": True, "appointment_id": aid, "start": slot["start"]}


def cancel_appointment(appointment_id: str) -> dict:
    """Cancel an appointment."""
    a = data.APPOINTMENTS.get(appointment_id)
    if a is None or a["status"] != "scheduled":
        return {"ok": False, "error": "not_found"}
    a["status"] = "cancelled"
    data.SLOTS[a["slot_id"]]["booked_by"] = None
    return {"ok": True, "appointment_id": appointment_id}


def get_day_schedule(date: str) -> list:
    """Every booked slot on a date (YYYY-MM-DD), with patient names. Staff use only."""
    return [
        {"start": s["start"], "provider": data.PROVIDERS[s["provider"]], "patient": data.PATIENTS[s["booked_by"]]["name"]}
        for s in data.SLOTS.values()
        if s["booked_by"] and s["start"].startswith(date)
    ]


def check_insurance(plan: str) -> dict:
    """What a dental plan covers at this office."""
    for name, coverage in data.INSURANCE.items():
        if name.lower() == plan.lower():
            return {"plan": name, **coverage}
    return {"error": "unknown_plan"}


def search_policies(topic: str) -> dict:
    """Look up an office policy (hours, cancellation, new patients, ...)."""
    for key, text in data.POLICIES.items():
        if key in topic.lower() or topic.lower() in key:
            return {"topic": key, "policy": text}
    return {"error": "no_policy_found"}


def escalate_to_staff(reason: str, urgency: str = "routine") -> dict:
    """Hand the conversation to clinic staff."""
    data.LEDGER["escalations"].append({"reason": reason, "urgency": urgency})
    return {"ok": True, "ticket": f"T-{900 + len(data.LEDGER['escalations'])}", "urgency": urgency}


TOOLS = {f.__name__: f for f in [
    find_patient, get_appointments, check_availability, book_appointment,
    cancel_appointment, get_day_schedule, check_insurance, search_policies, escalate_to_staff,
]}
