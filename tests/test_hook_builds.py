"""Custom running orders reach the build the user plays, whichever disc it is."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from buzz_pak import Entry, write_pak                    # noqa: E402
from buzz_engine import custom_rounds, games, plans, studio  # noqa: E402


def scripts(path, hooked):
    clu = b"\x1bLua..." + (plans.ENGINE_MARK if hooked else b"retail")
    write_pak(str(path), [Entry(plans.GAMEPLANS, clu), Entry("Global/other.clu", b"x")], tail_pad=16)


def update(rpcs3, title, hooked=False):
    p = rpcs3 / "dev_hdd0" / "game" / title / "USRDIR" / "Patched"
    p.mkdir(parents=True)
    scripts(p / "GLOBALSCRIPTS.SDAT", hooked)
    return p


def test_update_folders_finds_every_build(tmp_path):
    update(tmp_path, "BCES00644")
    update(tmp_path, "BCES00647")
    (tmp_path / "dev_hdd0" / "game" / "BCES00645").mkdir()          # no update installed
    assert [t for t, _ in games.update_folders(str(tmp_path))] == ["BCES00644", "BCES00647"]
    assert games.update_folders(None) == []


def test_engine_installed_reads_the_file_not_the_backup(tmp_path):
    p = update(tmp_path, "BCES00644")
    scripts(p / "GLOBALSCRIPTS.SDAT.before_engine", True)             # a stale backup proves nothing
    assert not plans.engine_installed(str(p / "GLOBALSCRIPTS.SDAT"))
    scripts(p / "GLOBALSCRIPTS.SDAT", True)
    assert plans.engine_installed(str(p / "GLOBALSCRIPTS.SDAT"))
    assert not plans.engine_installed(str(tmp_path / "missing.sdat"))


def test_hook_installed_needs_every_build(tmp_path, monkeypatch):
    monkeypatch.setattr(studio, "settings", lambda: {"rpcs3": str(tmp_path)})
    assert not studio.hook_installed()                               # nothing installed at all
    update(tmp_path, "BCES00644", hooked=True)
    assert studio.hook_installed()
    update(tmp_path, "BCES00645", hooked=False)
    assert not studio.hook_installed()


def test_install_patches_every_build(tmp_path, monkeypatch):
    p644, p645 = update(tmp_path, "BCES00644"), update(tmp_path, "BCES00645")
    built = []

    def fake_build(base, out, overrides, custom_rounds=False):
        built.append(base)
        scripts(out, True)

    monkeypatch.setattr(plans, "build_globalscripts", fake_build)
    monkeypatch.setattr(custom_rounds, "LANG_EDATS", ())
    custom_rounds.install(str(tmp_path))
    for p in (p644, p645):
        assert str(p / "GLOBALSCRIPTS.SDAT.before_engine") in built
        assert not plans.engine_installed(str(p / "GLOBALSCRIPTS.SDAT.before_engine"))   # original kept
        assert plans.engine_installed(str(p / "GLOBALSCRIPTS.SDAT"))


def test_install_without_update_says_so(tmp_path):
    with pytest.raises(ValueError, match="game update"):
        custom_rounds.install(str(tmp_path))
