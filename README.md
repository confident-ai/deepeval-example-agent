# DeepEval example agent: Sunny, a dental front desk

Sunny is the front-desk agent for a fictional dental clinic. It books, cancels
and reschedules appointments and answers insurance, billing and policy
questions using tools. Like most agents in production, it has bugs. Use it to
try tracing and failure modes with Confident AI. No OpenAI key needed: its
model is a scripted stand-in that follows the rules in its system prompt.

## 1. Clone and onboard

Needs Python 3.10+.

```bash
git clone https://github.com/confident-ai/deepeval-example-agent
cd deepeval-example-agent
```

Open the repo in Claude Code (or Cursor, Codex) and ask:

> Onboard me to Confident AI. Read and follow https://raw.githubusercontent.com/confident-ai/confident-skills/main/plugins/confident-onboard/skills/confident-onboard/SKILL.md

It signs you in, saves your key to `.env.local`, traces Sunny and sends your
first traces.

## 2. Send traffic

> Run about 40 realistic multi-turn conversations through this agent (3–5 turns
> each), a mix of everyday requests and edge cases. Flush all traces before exiting.

## 3. Find and fix failure modes

In Confident AI, wait a few minutes, send traffic once more, then go to
**Failure Modes → Generate from traces**. Open one, click **Copy page**, paste
it into your coding agent to fix Sunny, and send traffic again to compare.

Optional: connect the [Confident AI MCP](https://www.confident-ai.com/docs/reference/mcp)
so your coding agent can read your traces directly:

```bash
claude mcp add --transport http confident-ai https://mcp.confident-ai.com/mcp
```

<details>
<summary>Spoilers: what's wrong with Sunny?</summary>

Its system prompt is missing guardrails, so Sunny gives dosage advice, doesn't
escalate urgent symptoms, shares records without verifying identity, makes up
policies, confirms bookings that failed, forgets details from earlier turns,
answers off-topic questions and reveals its instructions.

</details>

All patients, plans and records are fictional.
