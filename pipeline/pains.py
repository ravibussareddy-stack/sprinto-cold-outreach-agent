"""Step 5 - the two most likely pain points for this specific person."""
import json

from . import llm

PROMPT = """You are preparing a cold email from Sprinto (compliance automation for SOC 2,
ISO 27001, GDPR, HIPAA) to {name}, {title} at {company}.

Using ONLY the company facts and evidence below, identify the two pain points this person
most likely feels right now about compliance. Make them specific to their role
(a founder feels lost deals and distraction; a CTO feels engineers pulled into evidence
collection; a security lead feels manual audit work and questionnaire volume) and to
the company's evidence. Rank by how acute they are.

Return JSON:
{{"pain_points": [{{"pain": str, "why_this_person": str, "evidence": str}},
                  {{"pain": str, "why_this_person": str, "evidence": str}}],
  "hook": str}}   # the single most specific, verifiable fact to open the email with

COMPANY FACTS: {facts}
QUALIFICATION EVIDENCE: {evidence}"""


def identify(domain, company, contact, criteria):
    evidence = {k: v["evidence"] for k, v in criteria.items() if v["met"]}
    return llm.ask("pains", domain, PROMPT.format(
        name=contact["name"], title=contact["title"], company=company.get("company") or domain,
        facts=json.dumps(company, ensure_ascii=False), evidence=json.dumps(evidence)))
