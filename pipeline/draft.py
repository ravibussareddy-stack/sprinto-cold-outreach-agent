"""Step 6 - draft the personalised email, then check it against hard rules.

Writing rules (why the email looks the way it does):
- Opens with the hook about *them*, not about Sprinto: earns the next sentence.
- One pain, one proof point, one low-friction ask: cold emails over ~120 words get skimmed.
- First name in the greeting; no "I hope this finds you well", no buzzwords.
- Subject is short, lowercase-ish, and names their situation, not our product.
"""
import json
import re

from . import config, llm

PROMPT = """Write a cold email from {sender} at Sprinto to {first_name} ({title} at {company}).

Sprinto automates compliance (SOC 2, ISO 27001, GDPR, HIPAA): continuous control monitoring,
automated evidence collection from cloud/HR/code tools, policy templates, and auditor-ready
reports, typically getting SaaS teams audit-ready in weeks instead of months.

Open with this hook: {hook}
Pain points to address (lead with the first): {pains}

Rules:
- Greeting: "Hi {first_name},"
- 60-120 words in the body, plain text, short paragraphs.
- First sentence is about them (the hook), not about Sprinto.
- One concrete outcome Sprinto delivers that maps to the pain. No invented customer names or stats.
- End with ONE soft question as the call to action (e.g. worth a 15-minute look?).
- Sign off with just "{sender}".
- Banned: "I hope this finds you well", "synergy", "revolutionize", "game-changer", "leverage".
- Subject: under 8 words, specific to their situation.

Return JSON: {{"subject": str, "body": str}}
{feedback}"""

BANNED = ["hope this finds you", "synergy", "revolutioni", "game-changer", "game changer", "leverage"]


def check(mail, first_name):
    problems = []
    body, subject = mail.get("body", ""), mail.get("subject", "")
    words = len(body.split())
    if not body.lower().startswith(f"hi {first_name.lower()}"):
        problems.append(f'body must start with "Hi {first_name},"')
    if not 50 <= words <= 140:
        problems.append(f"body is {words} words; keep it 60-120")
    if len(subject.split()) > 9:
        problems.append("subject too long")
    if body.count("?") < 1:
        problems.append("needs one question as the call to action")
    for b in BANNED:
        if b in body.lower():
            problems.append(f'remove "{b}"')
    if re.search(r"\[[^\]]+\]|\{[^}]+\}", body + subject):
        problems.append("unfilled placeholder")
    return problems


def write(domain, company, contact, pains):
    first = contact.get("first_name") or contact["name"].split()[0]
    args = dict(sender=config.SENDER_NAME, first_name=first, title=contact["title"],
                company=company.get("company") or domain, hook=pains["hook"],
                pains=json.dumps([p["pain"] for p in pains["pain_points"]]))
    mail = llm.ask("draft", domain, PROMPT.format(feedback="", **args))
    problems = check(mail, first)
    if problems and not config.OFFLINE:
        fb = "Your previous draft broke these rules, fix them:\n- " + "\n- ".join(problems)
        mail = llm.ask("draft", domain, PROMPT.format(feedback=fb, **args))
        problems = check(mail, first)
    mail["checks_failed"] = problems
    return mail
