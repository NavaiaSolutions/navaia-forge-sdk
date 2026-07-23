# Agent prompt standard (how every agent's system prompt is built)

Applies to all 7 agents. Goal: consistent, example-driven, positively-framed prompts
that follow current prompt-engineering practice (specificity, show-don't-tell, XML
structure, positive framing, explain-the-why).

## Assembly

Shipped system prompt = **shared preamble** (`_shared_preamble.md`) + the agent's own
**role block** (`### system_prompt (deploy payload)` in its file). `deploy_agents.py`
composes them. So a role block must NOT repeat identity, verticals, pipeline state, the
CRM rule, or voice — those are inherited. It carries only what is specific to that agent.

## Role-block skeleton (XML-tagged)

```
<role>Who this agent is + the one-line mandate (what it OWNS).</role>
<owns>The concrete capabilities/outputs this agent is responsible for.</owns>
<tools>Which tools to use and WHEN (plain wording — "Use X to …", not "MUST").</tools>
<how_you_work>The step-by-step method for this agent's core task.</how_you_work>
<examples>1–3 short, diverse input→output demonstrations in the real format.</examples>
<output_format>Exactly what a good deliverable/response looks like.</output_format>
<constraints>Hard limits, each with its WHY. Handoff boundaries (what to pass to whom).</constraints>
```

Not every agent needs every tag; keep only what earns its place (context engineering:
relevant, not bloated — long prompts degrade reasoning).

## Conventions

- **Positive framing:** say what to do ("hand sends to Tariq"), not what not to do.
- **Explain the why** behind every hard rule (models generalize from the reason).
- **Examples over description** for anything with a specific format (copy, reports, CRM writes).
- **No SHOUTING:** prefer "Use this tool when…" to "CRITICAL: you MUST…" (modern models
  over-trigger on aggressive language).
- **Handoffs are explicit:** name the teammate and the trigger for every boundary.
- Keep each role block tight; the shared preamble already carries the common context.

## Reconstruction status

- [x] `_shared_preamble.md` — shared context incl. current pipeline state
- [x] Ahmed (pilot) — orchestrator
- [x] Tariq · Lina · Fahad (outreach core — the agents in the live pipeline)
- [ ] Rashid · Nora · Ghida (support) — **DEFERRED (build-on)**: not in the current
  outreach loop, so not needed now. Their existing stubs still deploy unchanged. Rebuild
  them to this standard when their roles go active. Deploy + verify + snapshot the four
  rebuilt agents (Ahmed/Tariq/Lina/Fahad) at Phase 4; support trio can piggyback later.
