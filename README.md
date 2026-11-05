# Sprinto Cold Outreach Agent

MESA PGP Cohort 4 · Term 2 · AI Case 2 — *Cold Outreach, at Scale*.

Give it a list of domains. For each one it decides whether the company fits Sprinto,
finds the right decision-maker, works out their two biggest compliance pains, writes
a personalised email and sends it through Gmail to **your own inbox** (case rule).
No human decisions in the loop, and every decision is logged with its evidence.

```
domains.txt ─▶ 1 Scrape ─▶ 2 Extract ─▶ 3 Qualify ⟲ agent loop ─▶ 4 Find PoC ─▶ 5 Pain points ─▶ 6 Draft + checks ─▶ 7 Gmail
                                         (fetch about / security /
                                          customers / pricing / careers
                                          until criteria are known)
```

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py            # OFFLINE=1: fictional fixture companies, no keys needed
pytest -q
```

Live run: in `.env` set `OFFLINE=0`, add `GEMINI_API_KEY` (or `LLM_PROVIDER=anthropic` +
`ANTHROPIC_API_KEY`) and `HUNTER_API_KEY`, put real domains in `data/domains.txt`, then
`python run.py`. Check `outbox/*.eml`, then set `DRY_RUN=0` plus `GMAIL_ADDRESS` /
`GMAIL_APP_PASSWORD` to send.

Output per run: `runs/<timestamp>/report.md` (human-readable "why") and one JSON per domain.

## Stack

| Step | Choice | Why |
|---|---|---|
| 1 Scrape | `requests` + BeautifulSoup | Free, no browser needed for marketing sites |
| 2, 3, 5, 6 LLM | Gemini 2.5 Flash (free tier), Claude switchable | JSON mode, cheap at 8–15 companies/week |
| 4 PoC | **Hunter.io Domain Search (Option A)** | Only option that is automatic and repeatable; cached to protect the 25/month quota. `data/contacts.csv` (Apollo, Option B) is the fallback |
| 7 Send | Gmail SMTP + app password | No OAuth app setup; `To:` hardcoded to own inbox |

## Defining "right company" (the ICP)

Sprinto's buyers are B2B SaaS companies big enough to sell to enterprises but too small
to have a compliance team, **and** something is forcing the issue now. That gives a
100-point rubric, scored in code (`pipeline/qualify.py`) so results are reproducible:

| Criterion | Points | What counts as evidence |
|---|---|---|
| `is_b2b_saas` | 25 · **hard gate** | Sells subscription software to businesses |
| `stage_fit` | 25 | Series A–C, or ~20–500 employees |
| `compliance_trigger` | 35 | Audit prep, or customers/procurement asking for SOC 2 / ISO 27001 / GDPR / HIPAA |
| `enterprise_motion` | 15 | Sells to enterprise, mid-market or regulated buyers |

**Qualify at ≥ 70.** In practice a company needs a trigger: without one the maximum is 65.
The LLM only marks each criterion true / false / unknown **with a quote**. Any quote that
can't be found in the scraped text is thrown out (hallucination guard).

**Agent loop:** while a criterion is unknown, the agent picks the next page most likely to
answer it, the pipeline scrapes and extracts it, and the agent re-judges. It stops after 3
extra pages, or when the agent says no further page will help.

## Choosing the person

Fixed rules in `pipeline/contacts.py`. Who owns compliance depends on company size:

- **< 60 people** → Founder/CEO (no security team yet), then CTO
- **60–250** → CTO / VP Engineering, or Head of Security if one exists
- **> 250** → CISO / Head of Security / GRC

Ties are broken by Hunter's email-confidence score.

## Why the email looks the way it does

- Opens with a verifiable fact about *them* (the hook from step 5), not with Sprinto.
- One pain, one concrete outcome, one soft question as the ask, signed "Ravi".
- 60–120 words. Code checks enforce this (first name, length, call to action, no
  placeholders, no buzzwords); a failing draft is rewritten once, then held back.

## Impact

By hand: 15–20 min per company × 8–15 companies/week ≈ 2–5 hours/week, with quality
dropping as the person tires. The pipeline: well under a minute per company, the same
quality on the 15th as the 1st, and a written reason for every decision.
