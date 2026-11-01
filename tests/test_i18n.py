"""Studio translations: every key the page uses exists, languages stay in step, errors translate."""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import build_pack                              # noqa: E402
from buzz_engine import content, i18n, rounds  # noqa: E402

HTML = open(os.path.join(os.path.dirname(i18n.DIR), "studio.html"), encoding="utf-8").read()
EN = i18n.catalog("en")["ui"]
CODES = [l["code"] for l in i18n.languages()]


def used_keys():
    keys = set(re.findall(r'\bt\("([a-z0-9_.]+)"', HTML))
    keys |= set(re.findall(r'data-i18n(?:-ph|-aria)?="([a-z0-9_.]+)"', HTML))
    keys = {k for k in keys if not k.endswith(".") and not k.endswith("_")}   # prefixes of dynamic keys
    for k in re.findall(r'\btn\("([a-z0-9_.]+)"', HTML):
        keys |= {k + "_one", k + "_other"}
    keys |= {"kind." + k for k in ("standard", "picture", "all_that_apply", "point_stealer")}
    keys |= {"channel." + c for c in content.CATEGORIES}
    keys |= {"q.tab_import", "q.tab_add"}
    keys |= {"bb.rx_" + r for r in ("ok", "running", "missing", "no_driver", "no_library")}
    return keys


def test_english_has_every_key_the_page_uses():
    missing = sorted(used_keys() - set(EN))
    assert not missing, missing


@pytest.mark.parametrize("code", CODES)
def test_languages_have_the_same_keys_and_placeholders(code):
    ui = i18n.catalog(code)["ui"]
    assert i18n.catalog(code).get("_name")
    if code == "en":
        return
    extra = {k for k in ui if not k.startswith(("round.", "preset."))} - set(EN)
    assert not extra, sorted(extra)
    missing = set(EN) - set(ui)
    assert not missing, sorted(missing)
    for k, v in ui.items():
        if k in EN:
            assert set(re.findall(r"\{(\w+)\}", v)) == set(re.findall(r"\{(\w+)\}", EN[k])), k


def test_french_names_every_round_and_preset():
    fr = i18n.catalog("fr")["ui"]
    assert {"round." + t for t in rounds.ROUND_TYPES} <= set(fr)
    from buzz_engine import studio
    assert {"preset." + p for p in studio.PRESETS} <= set(fr)


def test_error_rules_are_valid_regexes():
    for code in CODES:
        for pattern, repl in i18n.catalog(code).get("errors", []):
            re.compile(pattern)


@pytest.mark.parametrize("msg,expected", [
    ("give the pack a name", "donne un nom au pack"),
    ("question longer than 93 characters; duplicate answers",
     "question de plus de 93 caractères; réponses en double"),
    ("pack numbers go from 1 to 999 - try 99", "les numéros de pack vont de 1 à 999 - essaie 99"),
    ('your pack "QUIZ" already uses number 96 - try 97', "ton pack « QUIZ » utilise déjà le numéro 96 - essaie 97"),
    ("pack 96 is already installed in RPCS3 as a different pack (EP9000-X); installing this one would replace it",
     "le pack 96 est déjà installé dans RPCS3 comme un autre pack (EP9000-X); installer celui-ci le remplacerait"),
    ("Building FRA pack 97 (MUSIQUE, no FRA host voice on this machine - built without audio)",
     "Construction du pack 97 en FRA (MUSIQUE, pas de voix FRA sur ce PC : construit sans audio)"),
    ("something nobody translated", "something nobody translated"),
])
def test_french_error_translation(msg, expected):
    assert i18n.translate(msg, "fr") == expected


def test_english_and_unknown_languages_leave_messages_alone():
    assert i18n.translate("give the pack a name", "en") == "give the pack a name"
    assert i18n.translate("give the pack a name", None) == "give the pack a name"
    assert i18n.catalog("../studio") == {}


def test_default_description_follows_the_pack_language():
    pack = content.new_pack("Musique", 97)
    assert build_pack.description(pack, "FRA") == "QUESTIONS SUR MUSIQUE"
    pack["text"]["description"] = "MON TEXTE"
    assert build_pack.description(pack, "FRA") == "MON TEXTE"
