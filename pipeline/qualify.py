"""Step 3 - qualify against Sprinto's ICP, with an agent loop.

ICP definition (from research on Sprinto's positioning and customers):
Sprinto sells compliance automation (SOC 2, ISO 27001, GDPR, HIPAA...) to B2B SaaS
companies that are big enough to sell to enterprises but too small to have a
compliance team - typically Series A to C - and that have a *trigger*: an audit
coming up, or enterprise/regulated customers demanding certification.

The rubric is fixed in code so every score is reproducible and explainable.
The LLM only judges each criterion (met / not met / unknown) and must quote the
evidence. Quotes that do not appear in the scraped text are discarded.

Agent loop: while any criterion is unknown, the agent picks the next page to read
(about / security / customers / pricing / careers), we scrape it, extract more
facts, and re-judge. It stops when nothing is unknown, it says stop, or it hits
MAX_AGENT_ROUNDS.
"""
import json
import re

from . import config, extract, llm, scrape

CRITERIA = {
    "is_b2b_saas": (25, "Sells subscription software to businesses (Sprinto only serves SaaS/tech)"),
    "stage_fit": (25, "Series A-C, or roughly 20-500 employees: selling to enterprises but no compliance team yet"),
    "compliance_trigger": (35, "Evidence of audit prep, or customers/procurement demanding SOC 2 / ISO 27001 / GDPR / HIPAA"),
    "enterprise_motion": (15, "Sells to enterprise, mid-market or regulated buyers (banks, health, government)"),
}
HARD_GATE = "is_b2b_saas"   # a 'false' here disqualifies regardless of score

PROMPT = """You qualify prospects for Sprinto, a compliance automation platform
(SOC 2, ISO 27001, GDPR, HIPAA) for B2B SaaS companies.

Judge each criterion as true, false or null (null = the facts do not say).
For every true/false give a short verbatim quote from the SOURCE TEXT as evidence.
Criteria:
{criteria}

If any criterion is null, choose ONE page to read next from {pages} that is most
likely to resolve it, else null.

Return JSON:
{{"criteria": {{"<name>": {{"met": true|false|null, "evidence": str|null}}, ...}},
  "next_page": str|null, "next_page_reason": str|null}}

COMPANY FACTS:
{facts}

SOURCE TEXT:
{source}"""

# If the model gives no page, fall back to the page most likely to answer the unknown.
DEFAULT_PAGE_FOR = {
    "stage_fit": "about",
    "compliance_trigger": "security",
    "enterprise_motion": "customers",
    "is_b2b_saas": "pricing",
}


def _words(s):
    return re.findall(r"[a-z0-9]+", (s or "").lower())


def evidence_found(quote, corpus):
    """Loose check that a quote really came from the scraped text (anti-hallucination)."""
    q = _words(quote)
    if not q:
        return False
    c = set(_words(corpus))
    return sum(w in c for w in q) / len(q) >= 0.7


def score(criteria):
    return sum(w for name, (w, _) in CRITERIA.items() if criteria.get(name, {}).get("met") is True)


def qualify(domain, company, pages_text):
    """pages_text: {page_name: text} already scraped. Mutated as the agent fetches more."""
    trace = []
    rounds = 0
    step = "qualify"
    while True:
        corpus = "\n".join(pages_text.values())
        criteria_txt = "\n".join(f"- {k}: {d}" for k, (_, d) in CRITERIA.items())
        remaining = [p for p in scrape.PAGES if p not in pages_text]
        out = llm.ask(f"{step}_{rounds}", domain, PROMPT.format(
            criteria=criteria_txt, pages=remaining,
            facts=json.dumps(company, ensure_ascii=False), source=corpus[:12000]))

        crit = {}
        for name in CRITERIA:
            c = (out.get("criteria") or {}).get(name) or {}
            met, ev = c.get("met"), c.get("evidence")
            if met is not None and not evidence_found(ev, corpus):
                met, ev = None, f"(discarded unverifiable quote: {ev!r})"
            crit[name] = {"met": met, "evidence": ev}

        unknown = [k for k, v in crit.items() if v["met"] is None]
        trace.append({"round": rounds, "pages_read": list(pages_text), "score": score(crit),
                      "unknown": unknown, "next_page": out.get("next_page"),
                      "why": out.get("next_page_reason")})

        if not unknown or rounds >= config.MAX_AGENT_ROUNDS or crit[HARD_GATE]["met"] is False:
            break
        nxt = out.get("next_page")
        if nxt is None:          # agent judged no remaining page would help
            break
        if nxt not in remaining:  # invalid choice: pick the page most likely to resolve an unknown
            nxt = next((DEFAULT_PAGE_FOR[u] for u in unknown if DEFAULT_PAGE_FOR[u] in remaining),
                       remaining[0] if remaining else None)
        if not nxt:
            break
        rounds += 1
        text, url = scrape.fetch(domain, nxt)
        pages_text[nxt] = text or ""
        trace[-1]["fetched"] = {"page": nxt, "url": url, "chars": len(text)}
        if text:
            company = extract.merge(company, extract.extract(domain, text, url, step=f"extract_{nxt}"))

    total = score(crit)
    gate_fail = crit[HARD_GATE]["met"] is False
    qualified = not gate_fail and total >= config.QUALIFY_THRESHOLD
    if gate_fail:
        reason = f"Disqualified: not B2B SaaS ({crit[HARD_GATE]['evidence']})"
    else:
        met = [k for k, v in crit.items() if v["met"]]
        missing = [k for k in CRITERIA if k not in met]
        reason = f"{total}/100 - met: {', '.join(met) or 'none'}; not shown: {', '.join(missing) or 'none'}"
    return {"score": total, "qualified": qualified, "reason": reason,
            "criteria": crit, "agent_trace": trace, "company": company}
