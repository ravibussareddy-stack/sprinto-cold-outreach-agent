"""Run the 7-step pipeline over a list of domains.

    python run.py                          # data/domains.txt
    python run.py --domains my_list.txt
    python run.py acme.com globex.io       # domains on the command line

Every decision is written to runs/<timestamp>/<domain>.json and summarised in
runs/<timestamp>/report.md so you can defend why each company did or did not get an email.
"""
import argparse
import json
import time
import traceback
from datetime import datetime
from pathlib import Path

from pipeline import config, contacts, draft, extract, pains, qualify, scrape, send


def process(domain):
    rec = {"domain": domain, "stage_reached": "scrape"}

    # 1. Scrape
    text, url = scrape.fetch(domain, "home")
    rec["scrape"] = {"url": url, "chars": len(text)}
    if not text:
        rec["outcome"] = "skipped: site unreachable or empty"
        return rec

    # 2. Extract
    rec["stage_reached"] = "extract"
    company = extract.extract(domain, text, url, step="extract_home")

    # 3. Qualify (agent loop)
    rec["stage_reached"] = "qualify"
    q = qualify.qualify(domain, company, {"home": text})
    company = q.pop("company")
    rec["company"], rec["qualification"] = company, q
    if not q["qualified"]:
        rec["outcome"] = f"not qualified: {q['reason']}"
        return rec

    # 4. Point of contact
    rec["stage_reached"] = "contact"
    person, why = contacts.find_contact(domain, company.get("employees"))
    rec["contact_decision"] = why
    if not person:
        rec["outcome"] = f"qualified but no contact: {why['reason']}"
        return rec
    rec["contact"] = person

    # 5. Pain points
    rec["stage_reached"] = "pains"
    rec["pains"] = pains.identify(domain, company, person, q["criteria"])

    # 6. Draft
    rec["stage_reached"] = "draft"
    mail = draft.write(domain, company, person, rec["pains"])
    rec["email"] = mail
    if mail["checks_failed"]:
        rec["outcome"] = f"draft held back: {mail['checks_failed']}"
        return rec

    # 7. Send
    rec["stage_reached"] = "send"
    rec["send"] = send.send(domain, person, mail["subject"], mail["body"])
    rec["outcome"] = f"email {rec['send']['status']} -> {person['name']} ({person['title']})"
    return rec


def report(records, out):
    lines = [f"# Outreach run {out.name}", "",
             f"Mode: {'OFFLINE (fixtures)' if config.OFFLINE else 'LIVE'}"
             f"{' / DRY RUN' if config.DRY_RUN else ''} - all mail goes to {config.TO_ADDRESS}", "",
             "| Domain | Score | Qualified | Contact | Outcome |", "|---|---|---|---|---|"]
    for r in records:
        q = r.get("qualification", {})
        c = r.get("contact", {})
        lines.append(f"| {r['domain']} | {q.get('score', '-')} | {q.get('qualified', '-')} | "
                     f"{c.get('name', '-')} {('(' + c['title'] + ')') if c else ''} | {r['outcome']} |")
    for r in records:
        lines += ["", f"## {r['domain']}", "", f"**Outcome:** {r['outcome']}"]
        q = r.get("qualification")
        if q:
            lines += ["", "**Why it scored this way** (rubric in pipeline/qualify.py):"]
            for k, v in q["criteria"].items():
                w = qualify.CRITERIA[k][0]
                mark = {True: f"+{w}", False: "0 (no)", None: "0 (unknown)"}[v["met"]]
                lines.append(f"- `{k}` {mark}: {v['evidence'] or '-'}")
            lines.append("")
            lines.append("**Agent loop:** " + " -> ".join(
                f"round {t['round']} score {t['score']}"
                + (f", fetched `{t['fetched']['page']}` ({t.get('why') or 'fill unknowns'})" if t.get("fetched") else "")
                for t in q["agent_trace"]))
        if r.get("contact_decision"):
            lines += ["", f"**Why this person:** {r['contact_decision']['reason']}"]
        if r.get("pains"):
            lines += ["", "**Pain points:**"]
            lines += [f"{i}. {p['pain']} - {p['why_this_person']}" for i, p in enumerate(r["pains"]["pain_points"], 1)]
            lines += [f"", f"**Hook:** {r['pains']['hook']}"]
        if r.get("email"):
            lines += ["", f"**Subject:** {r['email']['subject']}", "", "```", r["email"]["body"], "```"]
    (out / "report.md").write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("domains", nargs="*")
    ap.add_argument("--domains", dest="file", default="data/domains.txt")
    a = ap.parse_args()
    domains = a.domains or [l.split("#")[0].strip() for l in Path(a.file).read_text().splitlines()]
    domains = [d for d in domains if d]

    out = config.RUNS_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for d in domains:
        t0 = time.time()
        try:
            rec = process(d)
        except Exception as e:  # one bad domain must not stop the batch
            rec = {"domain": d, "outcome": f"error: {e}", "traceback": traceback.format_exc()}
        rec["seconds"] = round(time.time() - t0, 1)
        records.append(rec)
        (out / f"{d}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False))
        print(f"{d:24} {rec['outcome']}  ({rec['seconds']}s)")
    report(records, out)
    sent = sum(1 for r in records if r.get("send"))
    print(f"\n{sent}/{len(records)} emails. Decision log: {out}/report.md")
    return records


if __name__ == "__main__":
    main()
