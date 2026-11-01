"""Pack themes: migration, renaming, assignment, import."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import build_pack                                   # noqa: E402
from buzz_engine import content, importers, studio  # noqa: E402

Q = ["A", "B", "C", "D"]


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.setattr(studio, "PROJECTS", str(tmp_path))
    monkeypatch.setattr(studio, "number_conflicts", lambda *a: [])
    pack = content.new_pack("Musique 2010-2026", 97)
    pack["standard"] = [["Q%d ?" % i] + Q for i in range(4)]
    studio.save("musique_97", pack)
    return "musique_97"


def themes_of(view):
    return [(t["name"], t["questions"]) for t in view["themes"]]


def test_old_pack_gets_a_theme_from_its_subject():
    pack = {"text": {"subject": "HARRY POTTER"}, "subject_key": "SUBJECT_HARRY_POTTER"}
    assert content.themes(pack) == [{"id": "t1", "name": "HARRY POTTER", "subject_key": "SUBJECT_HARRY_POTTER"}]


def test_theme_for_reuses_by_name_and_keeps_keys_unique():
    pack = content.new_pack("Music", 1)
    assert content.theme_for(pack, "music")["id"] == "t1"
    a = content.theme_for(pack, "Années 2010")
    b = content.theme_for(pack, "ANNEES 2010")
    assert a["subject_key"] == "SUBJECT_ANNEES_2010" and b["subject_key"] != a["subject_key"]
    assert len({t["id"] for t in pack["themes"]}) == 3


def test_import_with_theme_column_creates_the_theme():
    qs = importers.parse_csv("question,correct,wrong,theme\nQ1 ?,A,B|C|D,Années 2010\nQ2 ?,A,B|C|D,\n")
    kept, _ = content.select(qs, uppercase=True)
    pack = content.new_pack("Musique", 97)
    content.add_to_pack(pack, kept, ".")
    assert [t["name"] for t in pack["themes"]] == ["MUSIQUE", "ANNÉES 2010"]
    assert build_pack.row_meta(pack["standard"][0], 5) == {"theme": "t2"}
    assert build_pack.row_meta(pack["standard"][1], 5) == {}          # main theme: nothing stored


def test_text_file_theme_line_round_trips():
    qs = importers.parse_text("Q: Q1 ?\nT: Rap\nS: un tube\nA: A\n- B\n- C\n- D\n")
    assert qs[0]["theme"] == "Rap" and qs[0]["about"] == "un tube"
    kept, _ = content.select(qs, uppercase=True)
    pack = content.new_pack("Musique", 97)
    content.add_to_pack(pack, kept, ".")
    assert importers.parse_json(pack)[0]["theme"] == "RAP"


def test_title_change_follows_until_the_theme_is_renamed(proj):
    v = studio.act_save({"id": proj, "title": "Musique récente"})
    assert v["topic"] == "MUSIQUE RÉCENTE"
    tid = v["themes"][0]["id"]
    studio.act_theme({"id": proj, "op": "rename", "theme": tid, "name": "Tubes"})
    v = studio.act_save({"id": proj, "title": "Autre titre"})
    assert v["title"] == "AUTRE TITRE" and v["topic"] == "TUBES"
    pack = studio.load(proj)
    assert pack["text"]["subject"] == "TUBES"
    assert pack["themes"][0]["subject_key"] == "SUBJECT_MUSIQUE_2010_2026"   # key never changes


def test_assign_main_and_delete(proj):
    v = studio.act_theme({"id": proj, "op": "add", "name": "Rap"})
    t1, t2 = (t["id"] for t in v["themes"])
    v = studio.act_assign({"id": proj, "theme": t2, "items": [{"kind": "standard", "i": 0},
                                                               {"kind": "standard", "i": 1}]})
    assert themes_of(v) == [("MUSIQUE 2010-2026", 2), ("RAP", 2)]
    # making Rap the main theme keeps every question where it was
    v = studio.act_theme({"id": proj, "op": "main", "theme": t2})
    assert themes_of(v) == [("RAP", 2), ("MUSIQUE 2010-2026", 2)]
    assert [q["theme"] for q in v["questions"]] == [t2, t2, t1, t1]
    assert v["topic"] == "RAP" and studio.load(proj)["subject_key"] == v["themes"][0]["subject_key"]
    # deleting a theme moves its questions to the main one
    v = studio.act_theme({"id": proj, "op": "delete", "theme": t1})
    assert themes_of(v) == [("RAP", 4)]
    with pytest.raises(ValueError):
        studio.act_theme({"id": proj, "op": "delete", "theme": t2})


def test_duplicate_theme_names_are_refused(proj):
    with pytest.raises(ValueError):
        studio.act_theme({"id": proj, "op": "add", "name": "musique 2010-2026"})


def test_import_one_theme_per_category(proj, tmp_path):
    f = tmp_path / "q.csv"
    f.write_text("question,correct,wrong,category\nX1 ?,A,B|C|D,Rock\nX2 ?,A,B|C|D,Pop\nX3 ?,A,B|C|D,Rock\n",
                 encoding="utf-8")
    r = studio._import(proj, [str(f)], themes_from_category=True)
    assert themes_of(r["project"]) == [("MUSIQUE 2010-2026", 4), ("ROCK", 2), ("POP", 1)]


def test_builder_announces_each_question_theme():
    themes = [{"id": "t1", "name": "MUSIQUE"}, {"id": "t2", "name": "RAP"}]
    names = {t["id"]: t["name"] for t in themes}
    row = ["Q ?"] + Q + [{"theme": "t2"}]
    theme = names.get(build_pack.row_meta(row, 5).get("theme"), "MUSIQUE")
    assert build_pack.intro_line("FRA", 0, None, theme) == "THÈME : RAP. FAITES VOS JEUX !"
