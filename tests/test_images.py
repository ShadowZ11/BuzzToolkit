"""Pictures in quiz files: relative paths, missing pictures, Point Stealer, .zip import/export."""
import base64
import hashlib
import os
import shutil
import sys
import zipfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from buzz_engine import content, importers, sharing, studio  # noqa: E402

EXAMPLE = os.path.join(ROOT, "examples", "picture_quiz")


def png(path, colour="red"):
    from PIL import Image
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new("RGB", (40, 30), colour).save(path)
    return path


def into_pack(qs, folder):
    kept, rejected = content.select(qs, uppercase=True)
    pack = content.new_pack("Flags", 95)
    lost = content.add_to_pack(pack, kept, str(folder))
    return pack, rejected, lost


def test_example_loads_pictures_and_point_stealer():
    qs = importers.load(os.path.join(EXAMPLE, "flags.buzz.txt"))
    kinds = [q["kind"] for q in qs]
    assert kinds.count("picture") == 3 and kinds.count("point_stealer") == 2
    for q in qs:
        for p in [q.get("image")] + (q.get("images") or []):
            assert p is None or os.path.isfile(p), p
    ps = [q for q in qs if q["kind"] == "point_stealer"][0]
    assert ps["correct"] == 0 and ps["images"][0].endswith("italy.png")


def test_relative_paths_are_found_next_to_the_quiz_file(tmp_path, monkeypatch):
    png(str(tmp_path / "quiz" / "images" / "a.png"))
    (tmp_path / "quiz" / "q.txt").write_text("Q: Q1 ?\nIMG: images/a.png\nA: A\n- B\n- C\n- D\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)                    # not the quiz folder
    qs = importers.load(str(tmp_path / "quiz" / "q.txt"))
    assert os.path.isfile(qs[0]["image"])


def test_pictures_dropped_flat_are_found_by_name(tmp_path):
    png(str(tmp_path / "a.png"))
    (tmp_path / "q.csv").write_text("question,correct,wrong,image\nQ1 ?,A,B|C|D,images/a.png\n", encoding="utf-8")
    assert os.path.isfile(importers.load(str(tmp_path / "q.csv"))[0]["image"])


def test_point_stealer_from_csv_and_json(tmp_path):
    for n in "abcd":
        png(str(tmp_path / ("%s.png" % n)))
    (tmp_path / "q.csv").write_text("question,image1,image2,image3,image4\nWhich ?,a.png,b.png,c.png,d.png\n",
                                    encoding="utf-8")
    (tmp_path / "q.json").write_text('[{"question": "Which ?", "images": ["d.png", "c.png", "b.png", "a.png"]}]',
                                     encoding="utf-8")
    for f in ("q.csv", "q.json"):
        q = importers.load(str(tmp_path / f))[0]
        assert q["kind"] == "point_stealer" and len(q["images"]) == 4 and q["correct"] == 0
        assert all(os.path.isfile(p) for p in q["images"])


def test_a_missing_picture_skips_only_that_question(tmp_path):
    png(str(tmp_path / "ok.png"))
    (tmp_path / "q.txt").write_text("Q: Good ?\nIMG: ok.png\nA: A\n- B\n- C\n- D\n\n"
                                    "Q: Bad ?\nIMG: missing.png\nA: A\n- B\n- C\n- D\n\n"
                                    "Q: Plain ?\nA: A\n- B\n- C\n- D\n", encoding="utf-8")
    pack, _, lost = into_pack(importers.load(str(tmp_path / "q.txt")), tmp_path / "pack")
    assert [q[1] for q in pack["picture"]] == ["GOOD ?"] and len(pack["standard"]) == 1
    assert [why for _, why in lost] == ["image not found: missing.png"]


def test_point_stealer_with_a_missing_picture_adds_no_orphan_pictures(tmp_path):
    for n in "abc":
        png(str(tmp_path / ("%s.png" % n)))
    (tmp_path / "q.txt").write_text("Q: Which ?\nIMG: a.png\nIMG: b.png\nIMG: c.png\nIMG: nope.png\n", encoding="utf-8")
    pack, _, lost = into_pack(importers.load(str(tmp_path / "q.txt")), tmp_path / "pack")
    assert pack["point_stealer"] == [] and pack["images"] == [] and len(lost) == 1


def test_wrong_number_of_point_stealer_pictures_is_rejected(tmp_path):
    for n in "ab":
        png(str(tmp_path / ("%s.png" % n)))
    (tmp_path / "q.txt").write_text("Q: Which ?\nIMG: a.png\nIMG: b.png\n", encoding="utf-8")
    _, rejected, _ = into_pack(importers.load(str(tmp_path / "q.txt")), tmp_path / "pack")
    assert rejected and "point stealer needs 4 pictures" in rejected[0][1]


def zip_folder(folder, out):
    with zipfile.ZipFile(out, "w") as z:
        for d, _, files in os.walk(folder):
            for f in files:
                p = os.path.join(d, f)
                z.write(p, os.path.join("flags", os.path.relpath(p, folder)))
    return out


def test_zip_import(tmp_path):
    z = zip_folder(EXAMPLE, str(tmp_path / "flags.zip"))
    qs = importers.load(z, workdir=str(tmp_path / "unpacked"))
    pack, rejected, lost = into_pack(qs, tmp_path / "pack")
    assert not rejected and not lost
    assert (len(pack["picture"]), len(pack["point_stealer"])) == (3, 2)


def test_zip_with_unsafe_paths_is_refused(tmp_path):
    z = str(tmp_path / "evil.zip")
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("../evil.txt", "Q: x\nA: a\n- b\n- c\n- d\n")
    with pytest.raises(ValueError, match="unsafe path"):
        importers.load(z, workdir=str(tmp_path / "out"))
    assert not (tmp_path / "evil.txt").exists()


def digest(pack, folder, stem_no):
    with open(os.path.join(folder, "images", pack["images"][stem_no - 1] + ".png"), "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()


def test_export_zip_round_trip(tmp_path):
    first = tmp_path / "first"
    pack, _, _ = into_pack(importers.load(os.path.join(EXAMPLE, "flags.buzz.txt")), first)
    z = sharing.export_zip(pack, str(first), str(tmp_path / "share.zip"))
    second = tmp_path / "second"
    again, rejected, lost = into_pack(importers.load(z, workdir=str(tmp_path / "unz")), second)
    assert not rejected and not lost
    assert [q[1:] for q in again["picture"]] == [q[1:] for q in pack["picture"]]
    assert [q[0] for q in again["point_stealer"]] == [q[0] for q in pack["point_stealer"]]
    for a, b in zip(pack["point_stealer"], again["point_stealer"]):        # same right answer
        assert digest(pack, first, a[1]) == digest(again, second, b[1])
    assert "images/" in zipfile.ZipFile(z).namelist()[1]


def test_text_export_keeps_point_stealer(tmp_path):
    pack, _, _ = into_pack(importers.load(os.path.join(EXAMPLE, "flags.buzz.txt")), tmp_path / "p")
    txt = sharing.buzz_txt(pack, lambda stem: stem + ".png")
    assert txt.count("IMG:") == 3 + 8 and "Q: WHICH OF THESE IS THE FLAG OF ITALY?" in txt


def b64(path):
    with open(path, "rb") as f:
        return "data:application/octet-stream;base64," + base64.b64encode(f.read()).decode()


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.setattr(studio, "PROJECTS", str(tmp_path / "projects"))
    monkeypatch.setattr(studio, "SETTINGS", str(tmp_path / "settings.json"))
    monkeypatch.setattr(studio, "number_conflicts", lambda *a: [])
    studio.save("flags_95", content.new_pack("Flags", 95))
    return "flags_95"


def test_studio_drop_quiz_file_with_its_pictures(proj):
    files = [{"name": "flags.buzz.txt", "data": b64(os.path.join(EXAMPLE, "flags.buzz.txt"))}]
    files += [{"name": n, "data": b64(os.path.join(EXAMPLE, "images", n))}
              for n in os.listdir(os.path.join(EXAMPLE, "images"))]
    r = studio.act_import({"id": proj, "files": files})
    assert r["added"] == 5 and not r["skipped"]
    assert (r["project"]["counts"]["picture"], r["project"]["counts"]["point_stealer"]) == (3, 2)


def test_studio_drop_zip_and_export(proj, tmp_path):
    z = zip_folder(EXAMPLE, str(tmp_path / "flags.zip"))
    r = studio.act_import({"id": proj, "files": [{"name": "flags.zip", "data": b64(z)}]})
    assert r["added"] == 5
    out = studio.act_export({"id": proj})["zip"]
    assert os.path.isfile(out) and out.endswith("Flags_PACK0095.zip")


def test_studio_missing_pictures_are_reported(proj):
    r = studio.act_import({"id": proj, "files": [{"name": "flags.buzz.txt",
                                                    "data": b64(os.path.join(EXAMPLE, "flags.buzz.txt"))}]})
    assert r["added"] == 0 and r["skipped"] == {"image not found: france.png": 1, "image not found: japan.png": 1,
                                                 "image not found: germany.png": 1, "image not found: italy.png": 1,
                                                 "image not found: netherlands.png": 1}


def test_studio_pictures_alone_are_refused(proj):
    with pytest.raises(ValueError, match="quiz file together"):
        studio.act_import({"id": proj, "files": [{"name": "a.png", "data": b64(os.path.join(EXAMPLE, "images", "japan.png"))}]})


def test_duplicate_key_works_in_any_script():
    a = content.normalise({"question": "Кто написал «Войну и мир»?", "correct": "Толстой",
                           "wrong": ["Пушкин", "Гоголь", "Чехов"]}, True)
    b = content.normalise({"question": "Какая самая длинная река?", "correct": "Нил",
                           "wrong": ["Амазонка", "Янцзы", "Волга"]}, True)
    kept, rejected = content.select([a, b], uppercase=True)
    assert len(kept) == 2 and not rejected


def test_picture_questions_with_the_same_text_are_not_duplicates(tmp_path):
    for n in "ab":
        png(str(tmp_path / ("%s.png" % n)))
    q = lambda img: {"question": "Which flag is this?", "correct": "A", "wrong": ["B", "C", "D"], "image": img}
    kept, rejected = content.select([q(str(tmp_path / "a.png")), q(str(tmp_path / "b.png")),
                                     q(str(tmp_path / "a.png"))], uppercase=True)
    assert len(kept) == 2 and rejected[0][1] == ["duplicate question"]
