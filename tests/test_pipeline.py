import os

os.environ["OFFLINE"] = "1"
os.environ["DRY_RUN"] = "1"

import run  # noqa: E402
from pipeline import config, contacts, draft, qualify  # noqa: E402


def test_end_to_end_offline(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(config, "OUTBOX_DIR", tmp_path / "outbox")
    monkeypatch.setattr("sys.argv", ["run.py"])
    recs = {r["domain"]: r for r in run.main()}
    assert recs["ledgerloop.example"]["contact"]["name"] == "Priya Nair"
    assert recs["shipwise.example"]["contact"]["name"] == "Meera Kapoor"
    assert recs["carepulse.example"]["send"]["status"] == "dry_run"
    assert recs["brewbarn.example"]["qualification"]["qualified"] is False
    assert recs["tinyform.example"]["qualification"]["score"] == 25
    assert recs["deadlink.example"]["outcome"].startswith("skipped")
    # agent loop fetched extra pages where the home page was not enough
    assert recs["shipwise.example"]["qualification"]["agent_trace"][0]["fetched"]["page"] == "about"
    assert recs["carepulse.example"]["qualification"]["agent_trace"][0]["fetched"]["page"] == "security"
    for d in ("ledgerloop.example", "shipwise.example", "carepulse.example"):
        eml = (tmp_path / "outbox" / f"{d}.eml").read_text()
        assert f"To: {config.TO_ADDRESS}" in eml


def test_hallucinated_evidence_is_discarded():
    assert qualify.evidence_found("Series B with 150 employees", "We raised our Series B and have 150 employees")
    assert not qualify.evidence_found("SOC 2 Type II certified since 2021", "We sell coffee in Pune")


def test_contact_ranking_depends_on_size():
    people = [{"name": "A", "title": "CEO & Founder"}, {"name": "B", "title": "CTO"},
              {"name": "C", "title": "Head of Security"}, {"name": "D", "title": "Sales Manager"}]
    best = lambda n: max(people, key=lambda p: contacts.rank(p, n)[0])["name"]
    assert best(20) == "A"      # small: founder owns compliance
    assert best(400) == "C"     # large: security team owns it
    assert contacts.rank({"title": "Sales Manager"}, 50)[0] == 0


def test_draft_rules():
    good = {"subject": "ISO 27001 for your retail deals",
            "body": "Hi Meera,\n\n" + "word " * 70 + "\n\nWorth a quick look?\n\nRavi"}
    assert draft.check(good, "Meera") == []
    bad = {"subject": "x", "body": "Hello team, I hope this finds you well. [Company]"}
    assert len(draft.check(bad, "Meera")) >= 3
