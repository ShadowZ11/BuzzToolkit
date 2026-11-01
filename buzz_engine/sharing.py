"""Share a pack as text: a .buzz.txt, or a .zip with the .buzz.txt and its pictures.

Neither carries game data. In a plain .buzz.txt a picture is written as where it came from
(URL or path); in a .zip the pictures travel along as images/<name>.png.
"""
import os
import re
import unicodedata
import zipfile

from build_pack import row_meta


def file_title(pack):
    """ČESKÝ KVÍZ -> CeskyKviz: the pack name as generate.py writes it in file names."""
    plain = unicodedata.normalize("NFKD", pack["text"]["menu_name"]).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "", plain.title()) or "Pack"


def buzz_txt(pack, picture):
    """pack JSON -> .buzz.txt text. picture(stem) -> what an IMG: line says for that picture."""
    L = ["#TITLE:%s" % pack["text"]["menu_name"], "#PACK:%d" % pack["pack_number"],
         "#CATEGORY:%s" % pack["category"], "#DESCRIPTION:%s" % pack["text"]["description"]]
    if pack.get("author"):
        L.append("#AUTHOR:%s" % pack["author"])
    for players in ("4p", "8p"):
        spec = pack.get("rounds", {}).get(players)
        if spec:
            L.append("#ROUNDS%s:%s" % (players.upper(), ", ".join(
                "random(%s)" % "|".join(x["random"]) if isinstance(x, dict) else x for x in spec)))
    for c in pack.get("credits", []):
        L.append("#CREDIT:%s" % c)
    L.append("")
    names = {t["id"]: t["name"] for t in pack.get("themes", [])}
    img = lambda n: "IMG: " + picture(pack["images"][n - 1])

    def meta(q, n):
        m = row_meta(q, n)
        return (["S: " + m["about"]] if m.get("about") else []) + (
            ["T: " + names[m["theme"]]] if m.get("theme") in names else [])
    for q in pack["standard"]:
        L += ["Q: " + q[0]] + meta(q, 5) + ["A: " + q[1]] + ["- " + w for w in q[2:5]] + [""]
    for q in pack["picture"]:
        L += ["Q: " + q[1]] + meta(q, 6) + [img(q[0]), "A: " + q[2]] + ["- " + w for w in q[3:6]] + [""]
    for q in pack["point_stealer"]:                    # first picture = right answer
        L += ["Q: " + q[0]] + [img(n) for n in q[1:5]] + [""]
    return "\n".join(L)


def export_txt(pack, out):
    src = pack.get("image_sources", {})
    with open(out, "w", encoding="utf-8") as f:
        f.write(buzz_txt(pack, lambda stem: src.get(stem, stem + ".png")))
    return out


def export_zip(pack, pack_dir, out):
    """.zip with <name>.buzz.txt and images/; importing it gives the same questions back."""
    used = set()
    for q in pack["picture"]:
        used.add(pack["images"][q[0] - 1])
    for q in pack["point_stealer"]:
        used.update(pack["images"][n - 1] for n in q[1:5])
    name = file_title(pack)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(name + ".buzz.txt", buzz_txt(pack, lambda stem: "images/%s.png" % stem))
        for stem in sorted(used):
            p = os.path.join(pack_dir, "images", stem + ".png")
            if os.path.isfile(p):
                z.write(p, "images/%s.png" % stem)
    return out
