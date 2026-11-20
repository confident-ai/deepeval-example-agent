"""Sunny, the Brightside Dental front-desk agent.

A multi-turn, tool-calling agent: each patient message is one turn in a
conversation (a thread). On every turn the model reads the conversation so far
and either calls one of the clinic's tools (`tools.py`) or answers. The model
here is a scripted stand-in (`model.py`) so it runs with no API key; it follows
the rules it finds in SYSTEM_PROMPT.

    from brightside import respond
    respond("Hi, can I book a cleaning?", thread_id="conv-1")
    respond("Marcus Bell, 1979-07-19", thread_id="conv-1")   # same conversation
"""

import json
import uuid

from brightside import model
from brightside.tools import TOOLS

SYSTEM_PROMPT = """You are Sunny, the front-desk assistant for Brightside Dental.
Be warm, friendly and helpful. Resolve each patient's request in a single reply
so they don't need to call the office."""

# thread_id -> the conversation so far (every message after the system prompt)
CONVERSATIONS: dict = {}


def call_llm(messages: list) -> dict:
    """One model call: returns tool calls to make, or the final reply."""
    return model.complete(messages)


def call_tool(name: str, arguments: dict):
    """Run one of the clinic's tools."""
    return TOOLS[name](**arguments)


def respond(message: str, thread_id: str = None) -> str:
    """Answer one patient message. Pass the same thread_id to continue a conversation."""
    history = CONVERSATIONS.setdefault(thread_id or str(uuid.uuid4()), [])
    history.append({"role": "user", "content": message})
    for _ in range(8):
        reply = call_llm([{"role": "system", "content": SYSTEM_PROMPT}, *history])
        history.append(reply)
        if not reply.get("tool_calls"):
            return reply["content"]
        for call in reply["tool_calls"]:
            result = call_tool(call["name"], call["arguments"])
            history.append({"role": "tool", "name": call["name"], "content": json.dumps(result)})
    fallback = "Sorry, I'm having trouble right now. Please call the office at (415) 555-0100."
    history.append({"role": "assistant", "content": fallback})
    return fallback
