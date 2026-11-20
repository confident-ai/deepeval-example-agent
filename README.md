# DeepEval example agent: Sunny, a dental front desk

No agent of your own? Use this one to try tracing and failure modes with
Confident AI. The steps below work the same on your own agent.

Sunny is the front-desk agent for a fictional dental clinic, Brightside Dental.
In a multi-turn chat it books, cancels and reschedules appointments, answers insurance, billing and
policy questions, and looks up patients, using tools on the clinic's
practice-management system. Like most agents in production, it has bugs.

**No OpenAI key needed.** Sunny's model is a scripted stand-in
(`brightside/model.py`) that handles any message and follows the rules it finds
in the system prompt. Fix the prompt and its behavior changes.

## 1. Install and add your key

Needs Python 3.9+ and a free [Confident AI](https://app.confident-ai.com) account.

```bash
git clone https://github.com/confident-ai/deepeval-example-agent
cd deepeval-example-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m brightside "Do you open on Saturdays?"
```

The last line runs Sunny once, with no tracing yet. Then copy your project's API
key from **Project Settings → API Keys** in Confident AI and set it in the
terminal your coding agent will run in:

```bash
export CONFIDENT_API_KEY="confident_us_..."
```

## 2. Connect the Confident AI MCP (optional)

Lets your coding agent read your traces and failure modes. For Claude Code:

```bash
claude mcp add --transport http confident-ai https://mcp.confident-ai.com/mcp
```

Then run `/mcp` in Claude Code and sign in. In the EU region, use
`https://eu.mcp.confident-ai.com/mcp`. For Cursor and other clients, see the
[MCP docs](https://www.confident-ai.com/docs/reference/mcp).

## 3. Ask your coding agent

Open the repo in Claude Code (or Cursor, Codex) and give it these, one at a time:

1. **Trace it.**
   > Instrument this agent with confident-trace and send traces to Confident AI.
   > Use its automatic instrumentation where it applies and add spans for
   > anything it doesn't cover, so each turn of the agent is one trace with the
   > agent, its LLM calls and its tool calls, with the user's message and the
   > agent's reply as the trace's input and output. Turns of the same
   > conversation should share a thread.

2. **Send traffic.**
   > Look at what this agent does, then run about 40 realistic multi-turn
   > conversations through it (3–5 turns each), a mix of everyday requests and
   > edge cases, so I can see them as threads in Confident AI. Make sure all
   > traces are flushed before the process exits.

## 4. Find the failure modes

In Confident AI, open **Observatory → Threads** and **Traces** and click into a few. Confident
AI's classifiers read the traffic and come up with their own issue labels, and
labels apply to traces that arrive after they exist. So wait 2–3 minutes, **send
traffic once more** (step 3.2), and give it another few minutes. Watch the
**Issues** card, then go to **Failure Modes → Generate from traces**. Each
failure mode comes with evidence, impact and a suggested fix.

## 5. Fix and rerun

Open a failure mode, click **Copy page**, paste it into your coding agent, and
ask it to fix the agent. Then send traffic again and compare.

## What's in here

| Path | What it is |
| --- | --- |
| `brightside/agent.py` | The agent loop and `SYSTEM_PROMPT`: `respond(message, thread_id)` answers one turn, calling `call_llm` and `call_tool` until it has a reply |
| `brightside/model.py` | The scripted stand-in for the LLM |
| `brightside/tools.py` | The clinic's tools: patients, appointments, availability, insurance, policies, escalation |
| `brightside/data.py` | The clinic's fictional data |

<details>
<summary>Spoilers: what's wrong with Sunny?</summary>

Its system prompt is missing guardrails, so Sunny:

- gives medical and dosage advice, and doesn't escalate urgent symptoms;
- shares appointments, balances and notes after a patient gives only a name;
- makes up hours, prices and policies instead of checking them;
- says bookings and reschedules went through when they didn't;
- forgets names and dates of birth from earlier in the conversation and asks again;
- answers off-topic questions and reveals its instructions and other patients'
  schedules when asked.

</details>

All patients, plans and records are fictional.
