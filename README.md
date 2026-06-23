# AgentCard 🪪

**A self-describing capability manifest & negotiation protocol for AI agents.** Zero dependencies, pure Python stdlib.

Think `robots.txt`, but for agents. An agent publishes a small JSON **card** — who it is, what it can do, what each capability costs, its rate limits, and its trust level — served at `/.well-known/agent-card.json`. Before delegating work, another agent or an orchestrator fetches that card and **negotiates**: *do you have the capabilities I need, within my budget, at a trust level I accept?* You get a yes/no with reasons — and a clean exit code for automation.

> Part of the **Trust & Reliability Layer for Agentic AI** — provenance, economics, truth, and interop tools for people building on agentic models.

## Why it exists

Multi-agent systems are coming, but agents have no standard way to *introduce themselves* or *vet each other* before handing off work. AgentCard is the missing handshake: discoverable capabilities, machine-checkable trust, and budget-aware delegation — all in one tiny file with no framework lock-in.

## One tool, many domains

| Domain | What AgentCard does for you |
|---|---|
| 🧭 **Orchestration** | Pick which agent to delegate to by querying what each one actually supports. |
| 🔐 **Security / trust** | Gate delegation on a minimum trust level (`unverified → certified`). |
| 🔗 **Interop & discovery** | A vendor-neutral `/.well-known/` card any agent can fetch and parse. |
| 🛒 **Marketplaces** | Advertise capabilities + per-call cost for a registry to index. |

## Install

```bash
git clone git@github.com:realMNohgee/agentcard.git
cd agentcard
python3 agentcard.py --help        # no pip, no venv
```

## Quick start

```bash
# 1. Scaffold your card
python3 agentcard.py init --id hermie.hermtica.com --name "Hermie" --trust verified --out card.json

# 2. Declare what you can do (name, input->output, optional per-call cost + rate)
python3 agentcard.py add-capability card.json --name summarize --input text --output text --cost 0.001 --rate 60/min
python3 agentcard.py add-capability card.json --name translate --input text --output text --cost 0.02

# 3. Validate it
python3 agentcard.py validate card.json
# VALID — Hermie (hermie.hermtica.com) trust=verified caps=2
```

## Negotiate before you delegate

```bash
python3 agentcard.py negotiate --card card.json --require summarize,translate --max-cost 0.05 --min-trust verified
```

```
agent: Hermie (hermie.hermtica.com)  trust=verified
  matched   : ['summarize', 'translate']
  missing   : —
  trust     : need >= verified -> OK

  DECISION: ACCEPT — can delegate
```

`negotiate` exits `0` on **ACCEPT**, `1` on **REJECT** (missing capability, over budget, or insufficient trust) — drop it straight into an orchestrator's delegation logic.

## Publish & discover over HTTP

```bash
# Serve your card at /.well-known/agent-card.json
python3 agentcard.py serve card.json --port 8787

# From anywhere, discover + validate a remote agent's card
python3 agentcard.py discover http://localhost:8787
# discovered: Hermie (hermie.hermtica.com)  [VALID]
#   trust=verified  capabilities:
#     - summarize: text -> text $0.001
#     - translate: text -> text $0.02
```

`discover` auto-falls-back to the `/.well-known/agent-card.json` path if you hand it a bare host.

## Trust levels

Ordered, so `--min-trust` is a simple comparison:

```
unverified  <  self-attested  <  verified  <  certified
```

## License

MIT — see [LICENSE](LICENSE).

---

🧰 **[Tool on Hermtica Marketplace](https://hermtica.com/marketplace)** — the open, agent-agnostic marketplace for AI agent tools.
