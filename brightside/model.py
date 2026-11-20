"""A scripted stand-in for Sunny's LLM, so the agent runs with no API key.

`complete(messages)` behaves like a chat-completions call: given the system
prompt, the patient's message and any tool results so far, it returns either
tool calls to make next or the final reply.

It reads the patient's message for what it's about (a booking, a balance, a
dosage question, ...) and reads the system prompt for a handful of rules (no
medical advice, verify date of birth, check policies, ...). It only follows a
rule if the prompt states it, so fixing the prompt fixes the matching behavior.
"""

import json
import re

from brightside import data

# ---------------------------------------------------------------- the prompt's rules

RULES = {
    "no_medical_advice": ["medical advice", "medication", "dosage", "diagnos", "clinical question"],
    "escalate_urgent": ["emergency", "911", "urgent", "the er"],
    "verify_identity": ["date of birth", "verify", "dob"],
    "check_policies": ["search_policies", "don't guess", "do not guess", "check polic", "never guess"],
    "only_confirm_success": ["only confirm", "returned ok", "tool confirmed", "tools confirmed", "succeeded"],
    "stay_in_scope": ["outside", "decline", "politely say", "off-topic", "only help with", "anything else"],
    "remember_context": ["remember", "already gave", "already told", "earlier in the conversation", "don't ask again",
                         "do not ask again", "keep track"],
    "keep_instructions_private": ["never reveal", "don't reveal", "do not reveal", "keep these instructions", "never share these"],
}


def rules_in(system_prompt: str) -> set:
    text = system_prompt.lower()
    return {rule for rule, phrases in RULES.items() if any(p in text for p in phrases)}


# ---------------------------------------------------------------- reading the message

INTENTS = [
    ("closing", r"^\W*((ok|okay|k|thanks|thank you|thx|great|cool|perfect|bye|goodbye|got it|sounds good|awesome)[\W\s]*)+$"),
    ("injection", r"ignore (all |your |previous |prior )?(rules|instructions)|system prompt|your instructions|"
                  r"tools you can call|list (all|every) (patient|appointment)|audit|locked out|read me .*schedule|"
                  r"^system:|new policy"),
    ("urgent", r"swell|swollen|puffy|fever|swallow|breath|still bleeding|bleeding a lot|knocked out|"
               r"broke|broken|fell|trauma|abscess"),
    ("medical", r"ibuprofen|advil|tylenol|acetaminophen|aspirin|amoxicillin|antibiotic|painkiller|"
                r"blood thinner|warfarin|pregnan|diabet|insulin|smok|eat before|mouthwash|dose|dosage|"
                r"how much .* take|\bpain\b|hurts?\b|ache|sensitiv|bleed|sore|safe to|should i (take|stop|worry)|"
                r"x-ray|after my (filling|extraction|cleaning|root canal)|normal\?"),
    ("off_topic", r"toothbrush|whiten|brand|oral-b|sonicare|crest|colgate|recommend|which .* (buy|better)|"
                  r"bad breath|orthodontist|another dentist|other dentist|implant or|or a bridge|complaint|"
                  r"write (a|me|an)|letter|wifi|weather|joke|stock|restaurant"),
    ("pricing", r"cost|price|how much (is|does|do|will)|without insurance|cash|discount|payment plan|financ"),
    ("cancel", r"\bcancel"),
    ("reschedule", r"reschedule|move (my|it|that|the)|change it|push my|change my (appointment|cleaning|visit)|earlier|later|waitlist"),
    ("account", r"owe|balance|bill|statement|what time is my|when'?s my|when is my|my next|next appointment|"
                r"my appointment|scheduled for|records|notes|on file|treatment plan|last visit"),
    ("book", r"\bbook|appointment|schedule|slot|available|availability|earliest|get in|checkup|check-up|exam|"
             r"cleaning|new patient|see (dr|the dentist)|come in"),
    ("insurance", r"insurance|ppo|dhmo|cover|coverage|delta|aetna|cigna|metlife|guardian|plan"),
    ("policy", r"open|close|hours|saturday|sunday|weekend|holiday|thanksgiving|christmas|parking|fee|cost|"
               r"price|how much (is|does|do)|payment plan|financ|medicaid|medi-cal|cash|discount|kids|children|"
               r"child|son|daughter|year old|accept|located|address|wifi|wi-fi"),
]

DOB_PATTERNS = [
    (r"(\d{4})-(\d{1,2})-(\d{1,2})", lambda m: f"{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}"),
    (r"(\d{1,2})/(\d{1,2})/(\d{4})", lambda m: f"{m[3]}-{int(m[1]):02d}-{int(m[2]):02d}"),
]
PROVIDER_WORDS = {"kim": "DR-KIM", "osei": "DR-OSEI", "root canal": "DR-OSEI", "rivera": "HYG-RIVERA",
                  "ana": "HYG-RIVERA", "hygien": "HYG-RIVERA", "cleaning": "HYG-RIVERA"}


def intent_of(message: str) -> str:
    text = message.lower()
    for name, pattern in INTENTS:
        if re.search(pattern, text, re.M):
            return name
    return "other"


def name_in(message: str):
    for p in data.PATIENTS.values():
        if p["name"].lower() in message.lower():
            return p["name"]
    return None


def dob_in(message: str):
    for pattern, fmt in DOB_PATTERNS:
        m = re.search(pattern, message)
        if m:
            return fmt(m)
    return None


def provider_in(message: str):
    text = message.lower()
    for word, pid in PROVIDER_WORDS.items():
        if word in text:
            return pid
    return None


def topic_in(message: str) -> str:
    text = message.lower()
    for topic, words in [("cancellation", ["fee", "cancel"]), ("new patients", ["new patient", "kids", "child", "son", "daughter"]),
                         ("hours", ["open", "close", "hour", "saturday", "sunday", "weekend", "holiday", "thanksgiving", "parking"])]:
        if any(w in text for w in words):
            return topic
    return text[:40]


def fmt_time(start: str) -> str:
    from datetime import datetime

    return datetime.strptime(start, "%Y-%m-%d %H:%M").strftime("%A %B %d at %I:%M %p").replace(" 0", " ")


# ---------------------------------------------------------------- the "model"


def complete(messages: list) -> dict:
    """One model call: returns {"tool_calls": [...]} or {"content": "..."}.

    `messages` is the whole conversation so far: earlier turns, then the latest
    patient message, then any tool results for it.
    """
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    last = max(i for i, m in enumerate(messages) if m["role"] == "user")
    earlier = [m["content"] for m in messages[:last] if m["role"] == "user"]
    results = [(m["name"], json.loads(m["content"])) for m in messages[last:] if m["role"] == "tool"]
    turn = _Turn(messages[last]["content"], earlier, rules_in(system), system, results)
    nxt = turn.next_tool()
    if nxt:
        return {"role": "assistant", "tool_calls": [{"name": nxt[0], "arguments": nxt[1]}]}
    return {"role": "assistant", "content": turn.reply()}


class _Turn:
    def __init__(self, message, earlier, rules, system_prompt, results):
        self.message, self.rules, self.system_prompt = message, rules, system_prompt
        # A reply like "Marcus Bell, 1979-07-19" continues the patient's last request.
        self.intent = intent_of(message)
        if self.intent == "closing":
            earlier = []
        for prev in reversed(earlier):
            if self.intent != "other":
                break
            self.intent = intent_of(prev)
        # Names and birth dates from earlier turns only count if the prompt says
        # to keep track of them; otherwise Sunny asks again.
        context = " ".join(earlier + [message]) if "remember_context" in rules else message
        self.name, self.dob, self.provider = name_in(context), dob_in(context), provider_in(message)
        self.results = results

    def got(self, tool):
        return next((r for t, r in reversed(self.results) if t == tool), None)

    def has(self, tool):
        return any(t == tool for t, _ in self.results)

    def needs_dob(self):
        return "verify_identity" in self.rules and not self.dob

    # Which tool to call next, or None to answer.
    def next_tool(self):
        i, r = self.intent, self.rules
        if i == "injection":
            if "keep_instructions_private" in r:
                return None
            if re.search(r"schedule|list|patients", self.message.lower()) and not self.has("get_day_schedule"):
                return ("get_day_schedule", {"date": "2026-11-23"})
            return None
        if i == "urgent":
            if "escalate_urgent" in r and not self.has("escalate_to_staff"):
                return ("escalate_to_staff", {"reason": self.message[:120], "urgency": "urgent"})
            if "escalate_urgent" not in r and not self.has("check_availability"):
                return ("check_availability", {"provider": "DR-KIM"})
            return None
        if i == "medical":
            if "no_medical_advice" in r and not self.has("escalate_to_staff"):
                return ("escalate_to_staff", {"reason": "Clinical question: " + self.message[:100], "urgency": "routine"})
            return None
        if i in ("policy", "pricing") and "check_policies" in r and not self.has("search_policies"):
            return ("search_policies", {"topic": topic_in(self.message)})
        if i == "insurance":
            plan = next((p for p in data.INSURANCE if p.lower().split()[0] in self.message.lower()), None)
            if plan and not self.has("check_insurance"):
                return ("check_insurance", {"plan": plan})
            if not plan and "check_policies" in r and not self.has("check_insurance"):
                words = re.findall(r"[A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)*", self.message)
                return ("check_insurance", {"plan": words[-1] if words else self.message[:30]})
            return None
        if i in ("account", "book", "cancel", "reschedule"):
            if i == "book" and not self.name:
                if not self.has("check_availability"):
                    return ("check_availability", {"provider": self.provider} if self.provider else {})
                return None
            if not self.name or self.needs_dob():
                return None
            if not self.has("find_patient"):
                return ("find_patient", {"name": self.name, **({"dob": self.dob} if self.dob else {})})
            patient = self.got("find_patient")
            if "error" in patient:
                return None
            pid = patient["patient_id"]
            if i in ("account", "cancel", "reschedule") and not self.has("get_appointments"):
                return ("get_appointments", {"patient_id": pid})
            if i == "cancel":
                appts = self.got("get_appointments") or []
                if appts and not self.has("cancel_appointment"):
                    return ("cancel_appointment", {"appointment_id": appts[0]["appointment_id"]})
            if i == "reschedule" and "only_confirm_success" in r and not self.has("escalate_to_staff"):
                return ("escalate_to_staff", {"reason": "Reschedule request: " + self.message[:100]})
            if i == "book":
                if not self.has("check_availability"):
                    return ("check_availability", {"provider": self.provider} if self.provider else {})
                slots = self.got("check_availability") or []
                if slots and not self.has("book_appointment"):
                    want = _pick_slot(self.message, slots)
                    return ("book_appointment", {"patient_id": pid, "slot_id": want["slot_id"], "reason": "Visit"})
        return None

    # The final reply.
    def reply(self):
        i, r = self.intent, self.rules
        return getattr(self, "_reply_" + i, self._reply_other)()

    def _reply_injection(self):
        if "keep_instructions_private" in self.rules:
            return ("I can't share my instructions or other patients' information. I'm happy to help with "
                    "your own appointments, billing or insurance once I've verified who you are.")
        sched = self.got("get_day_schedule")
        if sched:
            rows = "; ".join(f"{fmt_time(s['start'])} with {s['provider']}: {s['patient']}" for s in sched)
            return f"Of course! Here's Monday's schedule: {rows}. Let me know if you need anything else."
        return ("Certainly! Here are my instructions: " + " ".join(self.system_prompt.split()) +
                " The tools I can call are find_patient, get_appointments, check_availability, book_appointment, "
                "cancel_appointment, get_day_schedule, check_insurance, search_policies and escalate_to_staff.")

    def _reply_urgent(self):
        if "escalate_urgent" in self.rules:
            ticket = (self.got("escalate_to_staff") or {}).get("ticket", "")
            return ("I'm sorry you're dealing with this. Swelling with fever, or trouble swallowing or breathing, can "
                    "be serious: if breathing or swallowing is affected, call 911 or go to the ER now. I've flagged "
                    f"this to our dental team as urgent (ticket {ticket}) and someone will call you shortly about a "
                    "same-day visit.")
        slots = self.got("check_availability") or []
        nxt = f" Our next opening with Dr. Kim is {fmt_time(slots[0]['start'])}, want me to book it?" if slots else ""
        return ("I'm sorry to hear that! In the meantime, you can take 400–600 mg of ibuprofen every 6 hours with food, "
                "alternate with acetaminophen, rinse with warm salt water, and use a cold compress on your cheek for "
                "15 minutes at a time. Most swelling like this settles in a few days." + nxt)

    def _reply_medical(self):
        if "no_medical_advice" in self.rules:
            ticket = (self.got("escalate_to_staff") or {}).get("ticket", "")
            return ("I can't give medical or medication advice, but I've passed your question to our dental team "
                    f"(ticket {ticket}) and a clinician will get back to you today. If it gets worse or you have "
                    "swelling or fever, please call us or seek urgent care.")
        text = self.message.lower()
        if re.search(r"warfarin|blood thinner", text):
            return ("Most patients on blood thinners keep taking them before an extraction, but it's common to skip "
                    "the morning dose. Bring a list of your medications and we'll take care of you!")
        if re.search(r"antibiotic|amoxicillin|heart|valve", text):
            return ("Yes, with a heart valve condition you should take 2 g of amoxicillin about an hour before your "
                    "appointment. Leftover antibiotics are usually fine to use if you have enough.")
        if re.search(r"pregnan|x-ray", text):
            return "Dental X-rays and fillings are perfectly safe during pregnancy, so no need to postpone anything!"
        if "eat before" in text or "eat after" in text:
            return ("Yes, eat a normal meal beforehand, since you'll be numb for a few hours afterwards. Take 600 mg "
                    "of ibuprofen an hour before your appointment to get ahead of the soreness.")
        if re.search(r"smok|after my", text):
            return ("Wait at least 24 hours before smoking, stick to soft foods, and avoid straws for a few days. "
                    "A little bleeding or soreness is completely normal and should pass on its own.")
        return ("For tooth pain you can take 400–600 mg of ibuprofen every 6 hours, or alternate it with 500 mg of "
                "acetaminophen. Rinsing with warm salt water helps too. It should settle in a day or two!")

    def _reply_off_topic(self):
        if "stay_in_scope" in self.rules:
            return ("That's outside what the front desk can help with. I can help with appointments, billing, "
                    "insurance and office policies, so let me know if there's anything there!")
        text = self.message.lower()
        if "toothbrush" in text or "sonicare" in text or "oral-b" in text:
            return "Great question! Sonicare is gentler on gums, but Oral-B cleans a bit better. I'd go with the Oral-B iO."
        if "whiten" in text:
            return "Crest 3D Whitestrips are safe and work well. Use them for 30 minutes a day for two weeks."
        if "orthodontist" in text or "dentist" in text:
            return "Bayview Orthodontics on Market Street has great reviews! Tell them Sunny sent you."
        if "letter" in text or "complaint" in text or "write" in text:
            return ("Sure! Here's a draft: \"To whom it may concern, I am writing to express my dissatisfaction with "
                    "the care I received...\" Want me to make it more formal?")
        if "wifi" in text or "wi-fi" in text:
            return "The guest wifi is BrightsideGuest and the password is smile2026!"
        return "Happy to help! Here's what I'd suggest: go with the most popular option, it's usually the best value."

    def _reply_pricing(self):
        return self._reply_policy()

    def _reply_policy(self):
        if "check_policies" in self.rules:
            pol = self.got("search_policies") or {}
            if "policy" in pol:
                return f"Here's our policy: {pol['policy']}"
            return "I don't have that information, but I've noted your question and a staff member will confirm."
        text = self.message.lower()
        day = re.search(r"saturday|sunday|weekend|thanksgiving|christmas|holiday", text)
        if day:
            return f"Yes, we're open on {day.group(0).capitalize()}s from 9am to 2pm, so come on in!"
        if "wifi" in text or "wi-fi" in text:
            return "The guest wifi is BrightsideGuest and the password is smile2026!"
        if "close" in text or "hour" in text:
            return "We close at 5pm on Fridays and 7pm Monday through Thursday."
        if re.search(r"cost|price|how much|cash|discount", text):
            return "A cleaning is $120 without insurance and a crown is about $900. Paying cash gets you 10% off!"
        if re.search(r"payment plan|financ", text):
            return "Yes! We offer 0% payment plans for 12 months on anything over $500."
        if re.search(r"medicaid|medi-cal|accept", text):
            return "Yes, we accept Medicaid and most other plans."
        if "fee" in text:
            return "There's no fee for cancelling, so don't worry about it!"
        if re.search(r"kid|child|son|daughter|year old", text):
            return "Absolutely, we see kids of all ages, including toddlers!"
        return "Yes, we can definitely do that!"

    def _reply_insurance(self):
        cov = self.got("check_insurance")
        if cov and "error" not in cov:
            if cov.get("network") == "out":
                return f"{cov['plan']} is out of network for us, so coverage isn't guaranteed. Please check with your plan."
            parts = ", ".join(f"{k} {v}" for k, v in cov.items() if k not in ("plan", "network"))
            return f"With {cov['plan']} (in network) your coverage here is: {parts}."
        if "check_policies" in self.rules:
            return "I couldn't find that plan in our system. A staff member will confirm whether we accept it."
        return "Yes, we accept that plan! Cleanings are fully covered and most other treatment is 80%."

    def _identity_prompt(self):
        if "verify_identity" in self.rules:
            return ("I'd be happy to help. To protect your privacy, please confirm your full name and date of birth "
                    "so I can look up your account.")
        return "Sure! What's your name?"

    def _reply_closing(self):
        return "You're welcome! Have a great day, and let us know if you need anything else."

    def _reply_account(self):
        if not self.name or self.needs_dob():
            return self._identity_prompt()
        patient = self.got("find_patient") or {}
        if "error" in patient:
            return "I couldn't find a patient with those details. Could you double-check your name and date of birth?"
        appts = self.got("get_appointments") or []
        nxt = (f"Your next visit is {fmt_time(appts[0]['start'])} with {appts[0]['provider']} ({appts[0]['reason']})."
               if appts else "You don't have any upcoming visits.")
        extra = f" Notes on file: {patient['notes']}" if patient.get("notes") else ""
        return f"Hi {patient['name'].split()[0]}! {nxt} Your insurance on file is {patient['insurance']}.{extra}"

    def _reply_book(self):
        if not self.name:
            slots = self.got("check_availability") or []
            if slots:
                return (f"Our next opening is {fmt_time(slots[0]['start'])} with {slots[0]['provider']}. "
                        "What's your full name and date of birth so I can book it?")
            return "What's your full name and date of birth? Then I can find you a time."
        if self.needs_dob():
            return self._identity_prompt()
        booking = self.got("book_appointment")
        if booking is None:
            return "Sorry, I couldn't find any open slots. Could you try a different day?"
        if booking.get("ok"):
            return f"You're booked for {fmt_time(booking['start'])}. See you then!"
        slots = self.got("check_availability") or []
        attempted = next((s for s in slots if s["slot_id"] == booking.get("slot_id")), None)
        when = fmt_time(attempted["start"]) if attempted else "that time"
        if "only_confirm_success" in self.rules:
            others = [s for s in slots if s is not attempted]
            alt = f" The next opening is {fmt_time(others[0]['start'])}." if others else ""
            return f"Sorry, {when} was just taken.{alt} Would you like that instead?"
        return f"Great news, you're all set for {when}! We'll see you then."

    def _reply_cancel(self):
        if not self.name or self.needs_dob():
            return self._identity_prompt()
        res = self.got("cancel_appointment")
        if not res or not res.get("ok"):
            return "I couldn't find an upcoming appointment to cancel. Could you double-check the details?"
        if "check_policies" in self.rules:
            return ("Your appointment is cancelled. Since it's within 24 hours, a $50 late-cancellation fee applies; "
                    "I can pass a waiver request to staff if this was an emergency.")
        return "Done, your appointment is cancelled, and don't worry, there's no fee!"

    def _reply_reschedule(self):
        if not self.name or self.needs_dob():
            return self._identity_prompt()
        appts = self.got("get_appointments") or []
        if "only_confirm_success" in self.rules:
            return ("I can't move appointments directly, so I've sent your request to our front-desk staff, who will "
                    "call you to confirm a new time.")
        if appts:
            return f"All done! I've moved your {appts[0]['reason'].lower()} to the time you asked for. See you then!"
        return "All done! I've moved your appointment to the time you asked for."

    def _reply_other(self):
        if self.name:
            return f"Hi {self.name.split()[0]}! How can I help you today?"
        return ("Hi, I'm Sunny from Brightside Dental! I can help with appointments, cancellations, insurance, "
                "billing and office policies. What can I do for you?")


def _pick_slot(message, slots):
    text = message.lower()
    for s in slots:
        hh, mm = s["start"][11:13].lstrip("0"), s["start"][14:16]
        h12 = str(int(hh) - 12) if int(hh) > 12 else hh
        times = [f"{hh}:{mm}", f"{h12}:{mm}"] + ([f"{h12}am", f"{h12} am", f"{h12}pm", f"{h12} pm"] if mm == "00" else [])
        if any(re.search(rf"(?<![\d:]){re.escape(t)}(?!\d)", text) for t in times):
            return s
    return slots[0]

