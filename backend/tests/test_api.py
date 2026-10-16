import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from api.routes import enka
from core.importer import import_all
from db.models import Base
from db.session import get_session
from tests.helpers import ENKA

CRIT_CIRCLET = {
    "set_key": "CrimsonWitchOfFlames", "slot": "circlet", "main_stat": "critRate_", "level": 20,
    "substats": [
        {"key": "critDMG_", "value": 21.8}, {"key": "atk_", "value": 9.9},
        {"key": "eleMas", "value": 40}, {"key": "hp", "value": 299},
    ],
}


@pytest.fixture(scope="module")
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as s:
        import_all(s)

    def override():
        with Session() as s:
            yield s

    app.dependency_overrides[get_session] = override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    engine.dispose()


def test_characters(client):
    chars = client.get("/api/characters").json()
    hutao = next(c for c in chars if c["key"] == "HuTao")
    assert hutao["element"] == "Pyro"
    assert hutao["builds"]


def test_domains(client):
    domains = client.get("/api/domains").json()
    zhou = next(d for d in domains if d["key"] == "HiddenPalaceOfZhouFormula")
    assert {s["key"] for s in zhou["sets"]} == {"CrimsonWitchOfFlames", "Lavawalker"}


def test_add_artifact_returns_scores(client):
    r = client.post("/api/artifacts", params={"character": "HuTao"}, json=CRIT_CIRCLET)
    assert r.status_code == 201
    body = r.json()
    scores = body["scores"]
    assert scores["overall"]["potential"] >= scores["top"][-1]["potential"]
    assert len({t["character_key"] for t in scores["top"]}) == len(scores["top"])
    assert scores["character"]["character_key"] == "HuTao"

    again = client.get(f"/api/artifacts/{body['id']}/score").json()
    assert again["overall"] == scores["overall"]


@pytest.mark.parametrize("change", [
    {"main_stat": "enerRech_"},
    {"level": 21},
    {"substats": [{"key": "critRate_", "value": 3.9}]},
    {"substats": [{"key": "atk_", "value": 5}, {"key": "atk_", "value": 5}]},
])
def test_rejects_invalid_artifact(client, change):
    assert client.post("/api/artifacts", json=CRIT_CIRCLET | change).status_code == 422


def test_unknown_set(client):
    assert client.post("/api/artifacts", json=CRIT_CIRCLET | {"set_key": "Nope"}).status_code == 422


def test_delete(client):
    art_id = client.post("/api/artifacts", json=CRIT_CIRCLET).json()["id"]
    assert client.delete(f"/api/artifacts/{art_id}").status_code == 204
    assert client.get(f"/api/artifacts/{art_id}/score").status_code == 404


def test_import_good_replaces_previous_import(client):
    good = {"format": "GOOD", "version": 3, "artifacts": [
        {"setKey": "GladiatorsFinale", "slotKey": "plume", "level": 0, "rarity": 5, "mainStatKey": "atk",
         "substats": [{"key": "critRate_", "value": 3.5}, {"key": "critDMG_", "value": 7.0},
                      {"key": "def", "value": 19}, {"key": "", "value": 0}],
         "unactivatedSubstats": [{"key": "atk_", "value": 4.7}]},
        {"setKey": "Adventurer", "slotKey": "flower", "level": 4, "rarity": 2, "mainStatKey": "hp",
         "substats": []},
        {"setKey": "NotARealSet", "slotKey": "flower", "level": 0, "rarity": 5, "mainStatKey": "hp",
         "substats": []},
    ]}
    manual = len(client.get("/api/artifacts").json())

    assert client.post("/api/artifacts/import", json=good).json() == {"imported": 1, "skipped": 2}
    assert client.post("/api/artifacts/import", json=good).json()["imported"] == 1

    arts = client.get("/api/artifacts").json()
    assert len(arts) == manual + 1
    plume = next(a for a in arts if a["source"] == "good")
    assert plume["unactivated"] == [{"key": "atk_", "value": 4.7}]


def test_estimate(client):
    r = client.get("/api/planner/estimate/HuTao", params={"target": 40})
    assert r.status_code == 200
    est = r.json()
    assert est["domain"]["key"] == "HiddenPalaceOfZhouFormula"
    assert set(est["slots"]) == {"flower", "plume", "sands", "goblet", "circlet"}
    assert est["resin"]["median"] <= est["resin"]["p90"]
    assert est["days"]["median"] == pytest.approx(est["resin"]["median"] / 180, abs=0.1)
    assert est["histogram"]
    assert est["luck"] is None


def test_resin_log_enables_luck(client):
    r = client.post("/api/resin", json={"domain_key": "HiddenPalaceOfZhouFormula", "runs": 3, "condensed": True})
    assert r.status_code == 201
    assert r.json()["resin_spent"] == 120

    luck = client.get("/api/planner/estimate/HuTao", params={"target": 40}).json()["luck"]
    assert luck["resin_spent"] == 120
    assert 0 <= luck["percentile"] <= 100


def test_estimate_unknown_character(client):
    assert client.get("/api/planner/estimate/Nobody").status_code == 404


def test_queue_and_recommendation(client):
    assert client.get("/api/planner/recommendation").json() is None

    builds = next(c for c in client.get("/api/characters").json() if c["key"] == "RaidenShogun")["builds"]
    assert client.post("/api/queue", json={"character_key": "HuTao", "target_score": 50}).status_code == 204
    assert client.post("/api/queue", json={"character_key": "RaidenShogun", "build_id": builds[-1]["id"]}).status_code == 204

    queue = client.get("/api/queue").json()
    assert [q["character_key"] for q in queue] == ["HuTao", "RaidenShogun"]
    assert [q["priority"] for q in queue] == [1, 2]
    assert queue[1]["build_id"] == builds[-1]["id"]

    client.post("/api/queue", json={"character_key": "RaidenShogun", "priority": 1})
    client.post("/api/queue", json={"character_key": "HuTao", "priority": 2, "target_score": 50})
    assert [q["character_key"] for q in client.get("/api/queue").json()] == ["RaidenShogun", "HuTao"]

    rec = client.get("/api/planner/recommendation").json()
    assert rec["domain"]["key"]
    assert {g["character_key"] for g in rec["gains"]} == {"HuTao", "RaidenShogun"}
    assert rec["value"] >= max(a["value"] for a in rec["alternatives"])

    assert client.delete("/api/queue/HuTao").status_code == 204
    assert client.delete("/api/queue/HuTao").status_code == 404


def test_queue_rejects_foreign_build(client):
    hutao_build = next(c for c in client.get("/api/characters").json() if c["key"] == "HuTao")["builds"][0]["id"]
    r = client.post("/api/queue", json={"character_key": "RaidenShogun", "build_id": hutao_build})
    assert r.status_code == 422


def test_enka_profile_and_session(client, monkeypatch):
    monkeypatch.setattr(enka, "fetch_enka", lambda uid: ENKA)

    r = client.post("/api/enka/700000000")
    assert r.json() == {"nickname": "Tester", "characters": ["Hu Tao"], "artifacts": 1, "skipped": 0}
    hutao = next(p for p in client.get("/api/profile").json() if p["character_key"] == "HuTao")
    assert 0 < hutao["score"] < 1
    assert hutao["slots"]["sands"]["main_stat"] == "hp_"
    assert hutao["slots"]["flower"] is None

    # no domain given: take the one of the set Hu Tao wears
    farm = client.post("/api/sessions", json={"character_key": "HuTao"}).json()
    assert farm["domain"]["key"] == "HiddenPalaceOfZhouFormula"
    assert client.get("/api/sessions/active").json()["id"] == farm["id"]

    farm = client.post(f"/api/sessions/{farm['id']}/runs", json={"resin": 40, "five_stars": 2}).json()
    farm = client.post(f"/api/sessions/{farm['id']}/runs",
                       json={"domain_key": "MomijiDyedCourt", "resin": 20, "five_stars": 1}).json()
    assert [r["domain_key"] for r in farm["runs"]] == ["HiddenPalaceOfZhouFormula", "MomijiDyedCourt"]
    assert (farm["resin"], farm["five_stars"]) == (60, 3)

    sands = {"set_key": "CrimsonWitchOfFlames", "slot": "sands", "main_stat": "hp_", "level": 0,
             "substats": [{"key": "critRate_", "value": 3.9}, {"key": "critDMG_", "value": 7.8},
                          {"key": "eleMas", "value": 23}]}
    art = client.post("/api/artifacts", params={"session_id": farm["id"]}, json=sands).json()
    advice = client.get(f"/api/artifacts/{art['id']}/advice").json()
    assert advice["character_key"] == "HuTao"
    assert advice["action"] in ("upgrade", "step", "skip")
    assert advice["equipped"]["main_stat"] == "hp_"
    assert advice["dmg_gain"] < 0  # a +0 piece is worse than a +20 one for now

    levelled = sands | {"level": 20, "substats": sands["substats"] + [{"key": "atk_", "value": 5.8}]}
    levelled["substats"][0]["value"] = 15.5
    assert client.put(f"/api/artifacts/{art['id']}", json=levelled).status_code == 200
    advice = client.get(f"/api/artifacts/{art['id']}/advice").json()
    assert advice["action"] == "done"
    assert advice["build_score_with"] > advice["build_score"]
    assert advice["dmg_gain"] > 0

    assert client.get("/api/sessions/active").json()["artifacts"][0]["level"] == 20
    client.post(f"/api/sessions/{farm['id']}/end")
    assert client.get("/api/sessions/active").json() is None
    assert client.post(f"/api/sessions/{farm['id']}/runs", json={}).status_code == 409


def test_clear_profile(client, monkeypatch):
    monkeypatch.setattr(enka, "fetch_enka", lambda uid: ENKA)
    client.post("/api/enka/700000000")
    worn = [a for a in client.get("/api/artifacts").json() if a["source"] == "enka"]
    assert worn[0]["equipped_by"] == "HuTao"
    advice = client.get(f"/api/artifacts/{worn[0]['id']}/advice", params={"character": "HuTao"}).json()
    assert advice["equipped"]["main_stat"] == worn[0]["main_stat"]
    assert advice["dmg_gain"] == 0
    assert advice["build_score_with"] == advice["build_score"]
    client.post("/api/queue", json={"character_key": "HuTao", "target_score": 45})

    assert client.delete("/api/profile").status_code == 204
    assert client.get("/api/profile").json() == []
    assert client.get("/api/queue").json() == []
    assert all(a["source"] != "enka" for a in client.get("/api/artifacts").json())


def test_rolls(client):
    rolls = client.get("/api/rolls").json()
    assert [round(v, 2) for v in rolls["5"]["critRate_"]] == [2.72, 3.11, 3.5, 3.89]


def test_build_sets_listed(client):
    hutao = next(c for c in client.get("/api/characters").json() if c["key"] == "HuTao")
    assert "CrimsonWitchOfFlames" in hutao["builds"][0]["sets"]


def test_enka_errors(client, monkeypatch):
    monkeypatch.setattr(enka, "fetch_enka", lambda uid: {"playerInfo": {"nickname": "x"}})
    assert client.post("/api/enka/700000000").status_code == 422


def test_update_activates_substat(client):
    piece = CRIT_CIRCLET | {"level": 0, "substats": CRIT_CIRCLET["substats"][:3], "unactivated": [CRIT_CIRCLET["substats"][3]]}
    art = client.post("/api/artifacts", json=piece).json()
    assert art["unactivated"] == [{"key": "hp", "value": 299}]

    levelled = piece | {"level": 4, "substats": CRIT_CIRCLET["substats"], "unactivated": []}
    out = client.put(f"/api/artifacts/{art['id']}", json=levelled).json()
    assert out["unactivated"] == []
    assert {s["key"] for s in out["substats"]} == {"critDMG_", "atk_", "eleMas", "hp"}


def test_import_rejects_other_formats(client):
    assert client.post("/api/artifacts/import", json={"format": "other"}).status_code == 422
