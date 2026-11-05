"""Step 4 - find the right point of contact.

Primary: Hunter.io Domain Search API (Option A). Results are cached in .cache/ so a
re-run does not burn the 25 free searches a month.
Fallback: data/contacts.csv (Option B - people looked up by hand in Apollo).

Who we pick is a rule, not a vibe. Compliance at a Series A-C SaaS company is owned by:
  - < 60 people: the founder/CEO or CTO (no security team exists yet)
  - 60-250: the CTO / VP Engineering, or a Head of Security if one exists
  - > 250: the CISO / Head of Security / GRC lead
"""
import csv
import json
import re

import requests

from . import config

ROLE_RULES = [
    # (pattern, role bucket, base score)
    (r"\b(ciso|chief information security|head of (information )?security|security (lead|head|director)|"
     r"director,? (of )?security|vp,? security|grc|compliance|risk)\b", "security", 90),
    (r"\b(cto|chief technology|vp,? (of )?engineering|head of engineering|director,? (of )?engineering)\b",
     "engineering", 80),
    (r"\b(ceo|founder|co-founder|cofounder|managing director)\b", "founder", 60),
    (r"\b(coo|chief operating|head of operations)\b", "operations", 55),
    (r"\b(head of it|it manager|devops|infrastructure|platform)\b", "it", 45),
]

SIZE_BONUS = {
    "small": {"founder": 35, "engineering": 15},
    "mid": {"engineering": 15, "security": 10},
    "large": {"security": 15},
}


def _size(employees):
    if not employees:
        return "mid"
    return "small" if employees < 60 else "large" if employees > 250 else "mid"


def rank(person, employees):
    title = (person.get("title") or "").lower()
    for pat, bucket, base in ROLE_RULES:
        if re.search(pat, title):
            bonus = SIZE_BONUS[_size(employees)].get(bucket, 0)
            return base + bonus + (person.get("confidence") or 0) / 100, bucket
    return 0, None


def _hunter(domain):
    cache = config.CACHE_DIR / "hunter" / f"{domain}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    r = requests.get("https://api.hunter.io/v2/domain-search", timeout=15, params={
        "domain": domain, "api_key": config.HUNTER_API_KEY, "type": "personal", "limit": 10})
    r.raise_for_status()
    people = [{
        "name": f"{e.get('first_name') or ''} {e.get('last_name') or ''}".strip(),
        "first_name": e.get("first_name"),
        "title": e.get("position"),
        "email": e.get("value"),
        "confidence": e.get("confidence"),
        "linkedin": e.get("linkedin"),
        "source": "hunter.io",
    } for e in r.json().get("data", {}).get("emails", []) if e.get("first_name")]
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(people, indent=1))
    return people


def _csv(domain):
    if not config.CONTACTS_CSV.exists():
        return []
    with open(config.CONTACTS_CSV, newline="") as f:
        return [{"name": r["name"], "first_name": r["name"].split()[0], "title": r["title"],
                 "email": r["email"], "confidence": None, "source": "apollo (manual csv)"}
                for r in csv.DictReader(f) if r["domain"].strip() == domain]


def find_contact(domain, employees=None):
    people, errors = [], []
    if config.HUNTER_API_KEY and not config.OFFLINE:
        try:
            people = _hunter(domain)
        except requests.RequestException as e:
            errors.append(f"hunter: {e}")
    if not people:
        people = _csv(domain)

    scored = sorted(((rank(p, employees), p) for p in people), key=lambda x: -x[0][0])
    scored = [(s, p) for s, p in scored if s[0] > 0]
    if not scored:
        return None, {"candidates": len(people), "errors": errors,
                      "reason": "no decision-maker title found"}
    (best_score, bucket), best = scored[0]
    why = (f"{best['title']} is the {bucket} owner; company size bucket '{_size(employees)}' "
           f"({employees or 'unknown'} employees) makes {bucket} the likely compliance buyer")
    return best, {"candidates": len(people), "picked_bucket": bucket, "reason": why,
                  "shortlist": [{"name": p["name"], "title": p["title"], "score": round(s[0], 2)}
                                for s, p in scored[:5]], "errors": errors}
