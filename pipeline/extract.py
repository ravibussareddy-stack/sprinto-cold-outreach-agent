"""Step 2 - turn raw page text into structured company data."""
from . import llm

PROMPT = """You are a B2B sales researcher. Extract facts about the company from the page text.
Only use what the text states. Use null for anything not stated. Do not guess.

Return JSON with exactly these keys:
{{
  "company": str,
  "one_liner": str,                      # what they sell, in under 15 words
  "is_b2b_saas": bool | null,            # sells subscription software to businesses
  "industry": str | null,                # e.g. fintech, healthtech, devtools, logistics
  "funding_stage": str | null,           # e.g. "Seed", "Series A", "Series B", "Public"
  "employees": int | null,
  "customer_types": [str],               # e.g. "enterprise", "banks", "mid-market", "consumers"
  "regions": [str],                      # markets they sell into, e.g. "US", "EU", "India"
  "certifications_held": [str],          # e.g. "SOC 2 Type II" already achieved
  "compliance_signals": [str]            # short quotes showing audit prep, customer security demands,
                                         # security questionnaires, trust pages, regulated buyers
}}

PAGE ({url}):
{text}"""


def extract(domain, text, url, step="extract"):
    return llm.ask(step, domain, PROMPT.format(text=text, url=url))


def merge(old, new):
    """Combine two extractions: keep known values, union the lists."""
    out = dict(old)
    for k, v in (new or {}).items():
        if isinstance(v, list):
            out[k] = list(dict.fromkeys((old.get(k) or []) + v))
        elif v is not None and old.get(k) in (None, ""):
            out[k] = v
    return out
