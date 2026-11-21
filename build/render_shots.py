"""Render one still per shot of story/script.json with the R6 rig (Blender/Cycles).
Usage: python render_shots.py <out_dir> [shot_id ...] [--preview]
"""
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
import r6  # noqa: E402
from r6 import R6, box, mat, camera  # noqa: E402

ROOT = r6.ROOT
FONT = os.path.join(ROOT, "assets", "fonts", "Montserrat-900.ttf")
R = math.radians

SKIN = (0.98, 0.84, 0.6)
CAST = {
    "me": dict(skin=SKIN, shirt=(0.78, 0.1, 0.1), pants=(0.1, 0.1, 0.12), hair="spiky", hair_color=(0.5, 0.2, 0.07),
               shoes=(0.05, 0.05, 0.05)),
    "leo": dict(skin=(0.6, 0.4, 0.25), shirt=(0.2, 0.5, 0.9), pants=(0.22, 0.28, 0.45), hair="short",
                hair_color=(0.07, 0.05, 0.04), shoes=(0.95, 0.95, 0.95)),
    "mom": dict(skin=SKIN, shirt=(0.75, 0.35, 0.6), pants=(0.2, 0.2, 0.3), hair="long", hair_color=(0.4, 0.2, 0.09)),
    "officer": dict(skin=(0.78, 0.56, 0.38), shirt=(0.12, 0.18, 0.42), pants=(0.07, 0.09, 0.2), hair="short",
                    hair_color=(0.06, 0.05, 0.04), hat="police", shoes=(0.03, 0.03, 0.03)),
    "officer2": dict(skin=(0.96, 0.8, 0.62), shirt=(0.12, 0.18, 0.42), pants=(0.07, 0.09, 0.2), hair="short",
                     hair_color=(0.85, 0.65, 0.25), hat="police", shoes=(0.03, 0.03, 0.03)),
    "mayor": dict(skin=(0.98, 0.95, 0.86), shirt=(0.06, 0.06, 0.07), pants=(0.06, 0.06, 0.07), hair="bald",
                  hat="top", torso_tex="suit", shoes=(0.02, 0.02, 0.02)),
}
CROWD_SHIRTS = [(0.3, 0.6, 0.3), (0.9, 0.75, 0.2), (0.55, 0.3, 0.7), (0.9, 0.5, 0.2), (0.3, 0.7, 0.75),
                (0.85, 0.85, 0.85), (0.6, 0.2, 0.25)]
CROWD_SKIN = [SKIN, (0.6, 0.4, 0.25), (0.82, 0.62, 0.42), (0.45, 0.3, 0.2), (0.96, 0.8, 0.65)]
HAIRC = [(0.07, 0.05, 0.04), (0.5, 0.2, 0.07), (0.85, 0.65, 0.25), (0.3, 0.15, 0.06)]


def char(who, face, loc=(0, 0, 0), rot=0.0, **kw):
    d = dict(CAST[who])
    d.update(kw)
    return R6(who, face=face, loc=loc, rot=R(rot), **d)


def crowd_person(i, face, loc, rot=0.0, **kw):
    rnd = random.Random(i * 7 + 3)
    return R6(f"c{i}", skin=rnd.choice(CROWD_SKIN), shirt=rnd.choice(CROWD_SHIRTS),
              pants=rnd.choice([(0.15, 0.2, 0.35), (0.1, 0.1, 0.12), (0.35, 0.3, 0.25)]),
              hair=rnd.choice(["short", "long", "spiky", "pigtails"]), hair_color=rnd.choice(HAIRC), face=face,
              loc=loc, rot=R(rot), shoes=(0.05, 0.05, 0.05), **kw)


# ------------------------------------------------------------------ environments
def town(day=True):
    r6.sky_and_sun()
    r6.ground()
    r6.road(y=0)
    for i, x in enumerate(range(-90, 100, 24)):
        cols = [(0.93, 0.8, 0.5), (0.85, 0.55, 0.4), (0.8, 0.85, 0.9), (0.95, 0.9, 0.75), (0.6, 0.75, 0.55)]
        roofs = [(0.7, 0.13, 0.1), (0.35, 0.3, 0.3), (0.25, 0.35, 0.55)]
        r6.house((x, 22, 0), wall=cols[i % 5], roof=roofs[i % 3], door=[(0.8, 0.08, 0.08), (0.1, 0.5, 0.25)][i % 2])
        r6.tree((x + 12, 30, 0), 1.1)
    for x in range(-90, 100, 30):
        if abs(x + 5) > 20:
            r6.tree((x + 5, -26, 0), 1.2)


def office():
    r6.sky_and_sun(strength=1.0)
    r6.room(w=34, d=26, h=15, wall=(0.55, 0.12, 0.12), floor=(0.45, 0.28, 0.16), trim=(0.85, 0.7, 0.3))
    r6.window((-10, 12.4, 8), w=6, h=7)
    r6.window((10, 12.4, 8), w=6, h=7)
    # portrait of the mayor + banner
    box((6, 0.4, 7), (0, 12.3, 8.5), mat((0.85, 0.7, 0.3), 0.4, metallic=0.6))
    box((5.2, 0.5, 6.2), (0, 12.2, 8.5), mat((0.25, 0.45, 0.7), 0.6))
    p = R6("portrait", face="evilgrin", loc=(0, 11.8, 4.3), scale=0.75, **CAST["mayor"])
    p.root.scale = (0.75, 0.05, 0.75)
    r6.text("NO SMILING", (0, 12.0, 13.3), 1.2, mat((0.95, 0.85, 0.3), 0.4), font=FONT)
    # flag
    r6.cyl(0.12, 10, (13, 9, 5), mat((0.85, 0.7, 0.3), 0.3, metallic=0.8))
    box((0.1, 4, 2.6), (13, 7, 8.6), mat((0.2, 0.35, 0.8), 0.6), bevel=0)
    # desk
    wood = mat((0.4, 0.22, 0.1), 0.45)
    box((14, 5, 2.4), (0, 2, 1.2), wood, bevel=0.08)
    box((14.6, 5.6, 0.4), (0, 2, 2.6), mat((0.3, 0.16, 0.07), 0.35), bevel=0.08)
    box((3.4, 0.4, 0.9), (0, -0.7, 3.2), mat((0.85, 0.7, 0.3), 0.3, metallic=0.7), bevel=0.05)
    r6.text("MAYOR", (0, -0.95, 3.2), 0.55, mat((0.05, 0.05, 0.05), 0.4), font=FONT)
    # chair
    box((4.4, 1.2, 8.5), (0, 8.6, 4.25), mat((0.2, 0.06, 0.06), 0.5), bevel=0.3)


def street_interior_house():
    r6.sky_and_sun()
    r6.ground()
    r6.house((0, 10, 0), wall=(0.93, 0.8, 0.5))
    r6.tree((-14, 16, 0), 1.1)
    r6.tree((14, 18, 0), 1.0)


# ------------------------------------------------------------------ sets per shot
def set_town_wide():
    town()
    r6.sign((-3.5, -14, 0), R(12), [("NO", 1.6, (0.8, 0.05, 0.05)), ("SMILING", 1.2, (0.8, 0.05, 0.05)),
                                   ("BY ORDER OF THE MAYOR", 0.42, (0.1, 0.1, 0.1))], w=8, h=5.5, font=FONT)
    for i, (x, y, rot) in enumerate([(6, -10, 200), (10, -11, 170), (16, 10, 90), (-14, 10, -90)]):
        crowd_person(i, "sad", (x, y, 0.4 if abs(y) > 8 else 0.1), rot)
    camera((3, -36, 5.5), (-1, -10, 6.5), lens=30)


def set_officer_ticket():
    town()
    o = char("officer", "angry", (0, -10, 0.4), rot=10, pose={"armR": -80, "armL": -20})
    r6.box((0.9, 0.05, 1.2), (0, -0.4, -2.5), mat((0.98, 0.96, 0.85), 0.8), parent=o.handR, bevel=0.01,
           rot=(R(80), 0, 0))
    t = r6.text("TICKET\n$1000", (0, 0, 0), 0.2, mat((0.8, 0.05, 0.05)), font=FONT, extrude=0.005)
    t.parent = o.handR
    t.location = (0, -0.48, -2.5)
    t.rotation_euler = (R(90 + 80), 0, 0)
    r6.car((-9, -2, 0), rot=R(90))
    camera((3, -19.5, 5.2), (0.3, -10, 4.3), lens=30)


def set_crowd_sad():
    town()
    rnd = random.Random(4)
    pts = [(-5, -11), (-1.5, -12.5), (2, -11), (5.5, -12), (-3.5, -8.5), (3.5, -8.5), (0, -9), (-7, -9), (7, -9)]
    for i, (x, y) in enumerate(pts):
        crowd_person(i + 10, rnd.choice(["sad", "sad", "content", "crying"]), (x, y, 0.4), rnd.uniform(-15, 15))
    camera((0, -27, 6.2), (0, -9, 4.0), lens=32)


def set_mom_sad():
    street_interior_house()
    char("mom", "sad", (0, 0, 0.4), rot=5, pose={"armL": -15, "armR": -15}, head_tilt=-8)
    camera((0.3, -5.6, 4.85), (0.0, 0.0, 4.05), lens=35)


def set_mayor_grin():
    office()
    char("mayor", "evilgrin", (0, 5.5, 0), pose={"armL": -50, "armR": -50})
    camera((0.0, -1.3, 5.55), (0.0, 5.5, 4.85), lens=35)


def set_mayor_desk():
    office()
    char("mayor", "evilgrin", (0, 5.5, 0), pose={"armL": -60, "armR": -60, "armR_side": 10})
    camera((4, -9, 7.0), (0, 5, 4.6), lens=30)


def set_me_leo():
    town()
    char("me", "neutral", (-1.9, -11, 0.4), rot=-35)
    char("leo", "content", (1.9, -11, 0.4), rot=35, pose={"armL": -60})
    camera((0, -27, 5.0), (0, -11, 3.3), lens=32)


def set_leo_close():
    town()
    char("leo", "content", (0, -11, 0.4), rot=8, pose={"armR": -95, "armR_side": 25})
    char("me", "neutral", (-3.4, -13.5, 0.4), rot=-60)
    camera((-0.5, -16.2, 5.25), (0.0, -11.0, 4.55), lens=35)


def set_me_worried():
    town()
    char("me", "worried", (0, -11, 0.4), rot=-5, head_tilt=4)
    camera((0.0, -15.6, 5.1), (0.0, -11.0, 4.65), lens=35)


def set_me_grin():
    town()
    char("me", "evilgrin", (0, -11, 0.4), rot=0, head_tilt=-4)
    camera((0.0, -15.4, 5.0), (0.0, -11.0, 4.65), lens=35)


def set_police_arrive():
    town()
    r6.car((2, -2, 0), rot=R(-75))
    char("officer", "angry", (-2, -9, 0.4), rot=-25, pose={"armR": -90})
    char("officer2", "angry", (3.5, -9.5, 0.4), rot=20)
    char("me", "shocked", (0, -15, 0.4), rot=180 + 10)
    camera((-3, -24, 6), (0.5, -8, 4.0), lens=30)


def set_officer_close():
    town()
    char("officer", "angry", (0, -10, 0.4), rot=0, pose={"armR": -95, "armR_side": 5})
    camera((0.4, -14.3, 5.15), (0.0, -10.0, 4.65), lens=35)


def set_me_gasp():
    town()
    char("me", "gasp", (0, -11, 0.4), rot=0, pose={"armL": -150, "armR": -150, "armL_side": 25, "armR_side": 25})
    camera((0.0, -15.4, 5.15), (0.0, -11.0, 4.65), lens=35)


def set_office_wide():
    office()
    char("mayor", "angry", (0, 5.5, 0), pose={"armL": -50, "armR": -50})
    char("me", "worried", (0, -5, 0), rot=180)
    char("officer", "angry", (-3.5, -5.5, 0), rot=170)
    char("officer2", "angry", (3.5, -5.5, 0), rot=190)
    camera((7, -20, 9), (0, 1, 4.5), lens=26)


def set_mayor_close():
    office()
    char("mayor", "evilgrin", (0, 5.5, 0), pose={"armL": -40, "armR": -40}, head_tilt=-6)
    camera((0.3, 0.5, 5.55), (0.0, 5.5, 5.05), lens=35)


def set_hat_pigeon():
    office()
    m = char("mayor", "content", (0, 5.5, 0), pose={"armL": -40, "armR": -40})
    r6.pigeon((0.35, -0.2, 2.55), rot=R(-15), parent=m.head_pivot, scale=0.8)
    camera((0.8, -0.2, 7.0), (0, 5.5, 6.6), lens=40)


def set_pigeon_poop():
    office()
    m = char("mayor", "shocked", (0, 5.5, 0), pose={"armL": -40, "armR": -40})
    r6.pigeon((0.2, 0.1, 2.73), rot=R(160), parent=m.head_pivot, scale=0.8)
    r6.poop((-0.3, -0.2, 2.73), parent=m.head_pivot, s=0.33)
    camera((0.3, 0.2, 6.55), (0.0, 5.5, 6.0), lens=35)


def set_officers_hold():
    office()
    char("officer", "crying", (-2.4, -2.5, 0), rot=-12)
    char("officer2", "crying", (2.4, -2.5, 0), rot=12)
    char("me", "crying", (0, -6.0, 0), rot=0)
    camera((0, -15, 6.4), (0, -4, 4.9), lens=33)


def set_mayor_laughs():
    office()
    m = char("mayor", "evilgrin", (0, 5.5, 0), pose={"armL": -140, "armR": -140, "armL_side": 30, "armR_side": 30},
             head_tilt=-12)
    r6.poop((-0.3, -0.2, 2.73), parent=m.head_pivot, s=0.33)
    camera((0.3, -2.0, 5.55), (0.0, 5.5, 4.85), lens=30)


def set_town_happy():
    town()
    rnd = random.Random(9)
    pts = [(-5, -11), (-1.5, -12.5), (2, -11), (5.5, -12), (-3.5, -8.5), (3.5, -8.5), (0, -9), (-7, -9), (7, -9)]
    for i, (x, y) in enumerate(pts):
        a = rnd.choice([0, -150])
        crowd_person(i + 10, "evilgrin", (x, y, 0.4), rnd.uniform(-15, 15),
                     pose={"armL": a, "armR": a or -40, "armL_side": 20, "armR_side": 20})
    char("me", "evilgrin", (0, -14, 0.4), pose={"armL": -150, "armR": -150, "armL_side": 25, "armR_side": 25})
    camera((0, -27, 6.2), (0, -10, 4.2), lens=30)


def set_me_sad_end():
    town()
    r6.sign((5, -4, 0), R(-10), [("CLOSED", 1.0, (0.8, 0.05, 0.05)), ("MONDAYS", 1.0, (0.8, 0.05, 0.05)),
                                ("NO SMILING", 0.75, (0.1, 0.1, 0.1))], w=8, h=5, font=FONT)
    char("me", "sad", (0, -11, 0.4), rot=-8, head_tilt=-6)
    camera((0.0, -15.5, 5.1), (0.0, -11.0, 4.65), lens=35)


SETS = {k[4:]: v for k, v in globals().items() if k.startswith("set_")}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    preview = "--preview" in sys.argv
    out = args[0]
    only = set(args[1:])
    os.makedirs(out, exist_ok=True)
    script = json.load(open(os.path.join(ROOT, "story", "script.json")))
    for shot in script["shots"]:
        if only and shot["id"] not in only:
            continue
        r6.reset()
        r6.setup_render(res=(540, 960) if preview else (1080, 1920), samples=12 if preview else 28)
        SETS[shot["set"]]()
        bpy.context.scene.render.filepath = os.path.join(out, shot["id"] + ".png")
        bpy.ops.render.render(write_still=True)
        print("RENDERED", shot["id"], flush=True)


if __name__ == "__main__":
    main()
