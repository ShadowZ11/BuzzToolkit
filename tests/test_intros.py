"""High Stakes intro lines: per-question subjects, translations, limits."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import build_pack                                   # noqa: E402
from buzz_engine import content, importers          # noqa: E402


def test_every_pack_language_has_intros():
    assert set(build_pack.LANGUAGES) <= set(build_pack.INTROS)


@pytest.mark.parametrize("lang", sorted(build_pack.INTROS))
def test_templates_are_valid_upper_case_lines(lang):
    for kind, templates in build_pack.INTROS[lang].items():
        assert len(templates) == 3, (lang, kind)
        for t in templates:
            assert t.count("%s") == 1, (lang, t)
            build_pack.check(t % "TEST", build_pack.MAX_Q, "intro")   # upper case, short enough


@pytest.mark.parametrize("lang", sorted(build_pack.INTROS))
def test_longest_allowed_subject_always_fits(lang):
    about = "X" * content.MAX_ABOUT
    for k in range(3):
        line = build_pack.intro_line(lang, k, about, "")
        assert about in line and len(line) <= build_pack.MAX_Q


def test_french_uses_the_question_subject():
    line = build_pack.intro_line("FRA", 0, "une musique des années 2010", "MUSIQUE 2010-2026")
    assert line == "LA PROCHAINE QUESTION PORTE SUR UNE MUSIQUE DES ANNÉES 2010. FAITES VOS JEUX !"


def test_falls_back_to_the_theme_in_the_pack_language():
    line = build_pack.intro_line("FRA", 0, None, "Musique 2010-2026")
    assert line == "THÈME : MUSIQUE 2010-2026. FAITES VOS JEUX !"
    assert "QUESTION ON" not in line


def test_a_full_sentence_is_kept_as_written():
    s = "QUI A CHANTÉ ÇA ? FAITES VOS JEUX !"
    assert build_pack.intro_line("FRA", 2, s, "IGNORED") == s


def test_unknown_language_falls_back_to_english():
    assert build_pack.intro_line("XXX", 0, None, "MUSIC").startswith("HERE'S A QUESTION ON MUSIC")


def test_templates_rotate_like_retail():
    lines = {build_pack.intro_line("FRA", k, "UN FILM", "") for k in range(3)}
    assert len(lines) == 3


def test_subject_survives_import_and_pack_rows():
    qs = importers.parse_text("Q: Qui chante Rolling in the Deep ?\nS: une musique des années 2010\n"
                              "A: Adele\n- Duffy\n- Lorde\n- Sia\n")
    kept, rejected = content.select(qs, uppercase=True)
    assert not rejected and kept[0]["about"] == "UNE MUSIQUE DES ANNÉES 2010"
    pack = content.new_pack("Musique", 97)
    content.add_to_pack(pack, kept, ".")
    row = pack["standard"][0]
    assert row[:5] == ["QUI CHANTE ROLLING IN THE DEEP ?", "ADELE", "DUFFY", "LORDE", "SIA"]
    assert build_pack.row_meta(row, 5) == {"about": "UNE MUSIQUE DES ANNÉES 2010"}
    # and back out again (pack JSON re-import keeps it)
    again = importers.parse_json(pack)
    assert again[0]["about"] == "UNE MUSIQUE DES ANNÉES 2010"


def test_csv_column_sujet():
    qs = importers.parse_csv("question;correct;wrong;sujet\nQ1 ?;A;B|C|D;un fait marquant de la musique\n")
    assert qs[0]["about"] == "un fait marquant de la musique"


def test_old_rows_without_subject_still_work():
    assert build_pack.row_meta(["Q", "A", "B", "C", "D"], 5) == {}


def test_too_long_subject_is_rejected():
    q = content.normalise({"question": "Q ?", "correct": "A", "wrong": ["B", "C", "D"],
                           "about": "Y" * (content.MAX_ABOUT + 1)}, True)
    assert any("announced subject" in p for p in content.problems(q))


def test_bulk_subject_action(tmp_path, monkeypatch):
    from buzz_engine import studio
    monkeypatch.setattr(studio, "PROJECTS", str(tmp_path))
    monkeypatch.setattr(studio, "number_conflicts", lambda *a: [])
    pack = content.new_pack("Musique", 97)
    pack["standard"] = [["Q1 ?", "A", "B", "C", "D"], ["Q2 ?", "A", "B", "C", "D", {"about": "OLD"}]]
    studio.save("musique_97", pack)
    v = studio.act_about({"id": "musique_97", "about": "une chanson des années 2020",
                          "items": [{"kind": "standard", "i": 0}, {"kind": "standard", "i": 1}]})
    assert v["changed"] == 2
    assert [q["about"] for q in v["questions"]] == ["UNE CHANSON DES ANNÉES 2020"] * 2
    v = studio.act_about({"id": "musique_97", "about": "", "items": [{"kind": "standard", "i": 1}]})
    assert studio.load("musique_97")["standard"][1] == ["Q2 ?", "A", "B", "C", "D"]
