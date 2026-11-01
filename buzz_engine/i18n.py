"""Buzz Pack Studio translations.

Each language is one file in buzz_engine/i18n/<code>.json:
  "_name"    the language's own name, shown in the language picker
  "ui"       {key: text} for studio.html; {name} placeholders are filled in by the page
  "errors"   [[regex, replacement], ...] translating the English messages the toolkit raises,
             so the Python code keeps a single (English) source for them
English is the reference: a key missing from another language falls back to it.
"""
import functools
import glob
import json
import os
import re

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "i18n")
DEFAULT = "en"


@functools.lru_cache(maxsize=None)
def catalog(code):
    path = os.path.join(DIR, "%s.json" % code)
    if not re.fullmatch(r"[a-z]{2,3}(-[A-Za-z]{2,4})?", code or "") or not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def languages():
    out = []
    for p in sorted(glob.glob(os.path.join(DIR, "*.json"))):
        code = os.path.splitext(os.path.basename(p))[0]
        out.append({"code": code, "name": catalog(code).get("_name", code)})
    return out


def translate(msg, code):
    """English message -> `code`: every rule is applied to each "; "-separated part in turn."""
    rules = catalog(code).get("errors") if code and code != DEFAULT else None
    if not rules or not msg:
        return msg
    out = []
    for part in str(msg).split("; "):
        for pattern, repl in rules:
            part = re.sub(pattern, repl, part)
        out.append(part)
    return "; ".join(out)
