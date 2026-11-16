"""Shared model-building code for the mechs: materials, textures, cuboid
geometry helpers, and the writers for models, item definitions and specs.

Same approach as the cars in tc-rally_game (pack/src/car_parts.py): every part
is its own half-size cuboid model on its own item display, built around a
pivot, so any part can be posed, damaged or broken off.

Frame: +X left, +Y up, +Z forward, meters (1 m = 1 block).
"""

from __future__ import annotations

import base64
import io
import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent.parent
NS = "mech"
ASSETS = ROOT / f"pack/assets/{NS}"
# Everything is designed at a small size and then scaled up by MECH_SCALE as it
# is written out, so the turret's cabin just fits a pilot in a reclined chair
# (1.43 m of headroom, the viewport at the pilot's eye height). Joint angles
# and ranges do not change.
MECH_SCALE = 2.1
# The procedural walk's numbers (tc/gait.tc, the viewer, tools/gait_check.py
# all read them from here, through parts.json and mech_data.tc). Lengths are
# at the design size (times MECH_SCALE when written out); speeds in m/s of
# design size per second, times in seconds, angles in degrees.
GAIT = {
    "crouch": 0.20,      # body lowered from the rest pose, so the legs keep a bend (and reach further)
    "swing": 0.6,        # seconds a step takes
    "lift": 0.25,        # how high a foot rises mid-step
    "bob": 0.05,         # body rise at mid-swing
    "step": 0.30,        # moving, a foot steps when it is this far from its target spot
    "settle": 0.06,      # standing, a foot steps when it is this far off
    "lead": 0.5,         # a foot lands this share of a swing's travel ahead of its home spot
    "max_speed": 1.8,    # fastest walk forward (backward is half); the stride is speed x 2 x swing
    "accel": 0.8,        # how fast the speed changes
    "max_turn": 40.0,    # degrees/s
    "turn_accel": 80.0,  # degrees/s^2
    "aim_rate": 30.0,    # how fast the torso turns toward its aim, degrees/s
    "pilot_aim_rate": 60.0,  # ...when a pilot is aiming it
    "toe": 12.0,         # toe pitch at mid-swing
    # terrain
    "max_rise": 1.52,    # a foot may land at most this far above or below the other (3.2 m real: three
                         # blocks); a deeper drop is walked off, and the mech falls
    "probe_up": 1.76,    # ground under a foot is looked for from this far above it (above max_rise)...
    "probe_down": 1.5,   # ...down to this far below it
    "climb_rate": 1.0,   # how fast the body follows the feet's height, per second
    "foot_heel": -0.29,  # where the ground under a foot is sampled, from its ankle point:
    "foot_mid": 0.33,    #   heel, middle and toe along the foot, and the middle
    "foot_toe": 0.95,    #   moved foot_side to either side
    "foot_side": 0.24,
    "margin": 1.0,       # a foothold is refused when a joint would come within this of its limit (degrees)
    "max_reach": 0.97,   # ...or the leg would stretch past this share of its length
    # gravity
    "gravity": 15.0,     # m/s^2 (real; heavier-feeling than Minecraft's)
    "max_fall": 40.0,    # m/s, the fastest fall
    "land_dip": 0.15,    # how far the body sinks into its legs on a hard landing
    "dip_rate": 0.5,     # how fast it comes back up, per second
    "fall_drift": 2.0,   # how fast falling feet swing to hang under the hips, per second
    # parked: down on the left knee (solved offline to fit the joint limits:
    # the right foot flat on the ground ahead, the left knee guard just off it,
    # the left foot behind resting on its toes)
    "kneel_drop": 1.571, # how far the body sinks below the standing rest pose (3.3 m real)
    "kneel_time": 1.5,   # seconds to kneel or stand up
    "kneel_lift_l": 0.5, # going down or up, each ankle moves on an arc this high (left, right),
    "kneel_lift_r": 0.15,  # so no part goes through the ground (checked offline)
    # piloting: an agile mech (1) steers where its pilot looks, strafes on A/D,
    # kneels on Shift (its turret only turns on its own while kneeling) and
    # jumps on Space, then pressurizes again; the walker turns on A/D
    "agile": 0.0,
    "strafe": 0.0,         # strafing speed, a share of max_speed
    "jump_speed": 0.0,     # m/s (real) straight up
    "jump_cooldown": 0.0,  # seconds to pressurize again after a jump
}
KNEEL_POSE = {"hip_l": 41.0, "knee_l": 47.0, "ankle_l": -1.0, "hip_r": -102.0, "knee_r": 64.0, "ankle_r": 38.0}
GAIT_LENGTHS = ("crouch", "lift", "bob", "step", "settle", "max_speed", "accel", "max_rise", "probe_up",
                "probe_down", "climb_rate", "foot_heel", "foot_mid", "foot_toe", "foot_side", "land_dip",
                "dip_rate", "fall_drift", "kneel_drop", "kneel_lift_l", "kneel_lift_r")

# Collision probes (design size, mech frame): points that must stay out of
# solid blocks. "body" ones turn with the body's heading, "torso" ones with
# the torso's (the waist turns it).
PROBES = (
    [("body", x, y, z) for x in (1.30, -1.30) for y in (3.0, 3.6) for z in (0.33, -0.33)]      # hips and pelvis
    + [("body", x, 1.95, 0.78) for x in (0.75, -0.75)]                                          # knees
    + [("body", x, y, z) for x in (0.75, -0.75) for y, z in ((1.30, 0.15), (0.90, -0.10))]     # shins
    + [("torso", x, y, z) for x in (0.82, -0.82) for y in (4.1, 4.85) for z in (-1.45, -0.3, 0.98)]  # hull
    + [("torso", x, 4.40, z) for x in (1.30, -1.30) for z in (-0.5, 1.2, 2.5)]                 # heavy guns
)


def gait_scaled(gait: dict | None = None, scale: float = MECH_SCALE, lengths=GAIT_LENGTHS) -> dict:
    """A gait (default the walker's GAIT) at real size."""
    gait = GAIT if gait is None else gait
    return {k: round(v * scale, 4) if k in lengths else v for k, v in gait.items()}


MODEL_SCALE = 0.2            # models are 1/5 size (parts reach 7.5 m from their pivot); display scale = 5
UNITS_PER_M = 16 * MODEL_SCALE

# ---------------------------------------------------------------------------
# Materials. "tint" is the custom_model_data color slot (0 = armor paint,
# 1 = accent). "dmg" is the texture of the damaged variant. "emit" glows.
# ---------------------------------------------------------------------------

MATERIALS: dict[str, dict] = {
    "armor":     {"tint": 0, "dmg": "armor_dmg"},
    "accent":    {"tint": 1, "dmg": "accent_dmg"},
    "hazard":    {"dmg": "hazard_dmg"},
    "gunmetal":  {},
    "darksteel": {},
    "steel":     {},
    "chrome":    {},
    "aluminum":  {},
    "brass":     {},
    "hose":      {},
    "motor":     {},
    "copper":    {},
    "rubber":    {},
    "vent":      {},
    "glow":      {"emit": 15},
    "visor":     {},
    "seat":      {},
    "screen":    {"emit": 12},
}


def _noise(img: Image.Image, amount: int, seed: int) -> None:
    rnd = random.Random(seed)
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            n = rnd.randint(-amount, amount)
            px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)), a)


def _flat(rgb, size=16, noise=4, seed=1, alpha=255) -> Image.Image:
    img = Image.new("RGBA", (size, size), (*rgb, alpha))
    if noise:
        _noise(img, noise, seed)
    return img


def _scratches(img: Image.Image, seed: int, color, count=7) -> Image.Image:
    img = img.copy()
    d = ImageDraw.Draw(img)
    rnd = random.Random(seed)
    w = img.width
    for _ in range(count):
        x0, y0 = rnd.randint(0, w - 1), rnd.randint(0, w - 1)
        x1, y1 = x0 + rnd.randint(-6, 6), y0 + rnd.randint(-3, 3)
        d.line((x0, y0, x1, y1), fill=color, width=1)
    return img


def _scorch(img: Image.Image, seed: int) -> Image.Image:
    img = img.copy()
    px = img.load()
    rnd = random.Random(seed)
    cx, cy = rnd.randint(4, 11), rnd.randint(4, 11)
    for y in range(16):
        for x in range(16):
            d = math.hypot(x - cx, y - cy)
            if d < 6:
                k = 1 - d / 6
                r, g, b, a = px[x, y]
                f = 1 - 0.55 * k
                px[x, y] = (int(r * f), int(g * f), int(b * f), a)
    return img


def _panel(rgb, seed, edge=-52, rivets=True) -> Image.Image:
    """Armor plate: a flat face with a darker rim and a rivet in each corner,
    so every face reads as a separate bolted plate."""
    img = _flat(rgb, noise=3, seed=seed)
    px = img.load()
    for i in range(16):
        for (x, y) in ((i, 0), (i, 15), (0, i), (15, i)):
            r, g, b, a = px[x, y]
            px[x, y] = (max(0, r + edge), max(0, g + edge), max(0, b + edge), a)
    if rivets:
        for (x, y) in ((2, 2), (13, 2), (2, 13), (13, 13)):
            px[x, y] = tuple(max(0, c - 70) for c in px[x, y][:3]) + (255,)
            px[x - 1, y - 1] = (255, 255, 255, 255)
    return img


def make_textures() -> dict[str, Image.Image]:
    t: dict[str, Image.Image] = {}
    # Armor and accent are near white so the tint sets the color.
    t["armor"] = _panel((232, 232, 228), 2)
    t["armor_dmg"] = _scorch(_scratches(_panel((218, 218, 214), 3), 4, (120, 120, 120, 255), 6), 5)
    t["accent"] = _flat((240, 240, 240), noise=2, seed=6)
    t["accent_dmg"] = _scratches(_flat((222, 222, 222), noise=4, seed=7), 8, (140, 140, 140, 255), 5)

    hz = Image.new("RGBA", (16, 16), (24, 24, 24, 255))
    d = ImageDraw.Draw(hz)
    for k in range(-16, 32, 8):                         # diagonal warning stripes
        d.polygon([(k, 16), (k + 4, 16), (k + 20, 0), (k + 16, 0)], fill=(236, 186, 22, 255))
    _noise(hz, 4, 8)
    t["hazard"] = hz
    t["hazard_dmg"] = _scorch(_scratches(hz, 9, (90, 80, 60, 255), 6), 10)

    t["gunmetal"] = _flat((58, 62, 70), noise=5, seed=11)
    t["darksteel"] = _flat((40, 42, 46), noise=5, seed=12)
    t["steel"] = _flat((150, 153, 158), noise=6, seed=13)

    chrome = _flat((226, 230, 236), noise=3, seed=14)
    px = chrome.load()
    for x in range(16):
        for y in (9, 10, 11):
            r, g, b, a = px[x, y]
            px[x, y] = (r - 70, g - 66, b - 60, a)
        px[x, 3] = (255, 255, 255, 255)
    t["chrome"] = chrome

    alu = _flat((176, 182, 190), noise=0)
    d = ImageDraw.Draw(alu)
    rnd = random.Random(15)
    for y in range(16):                                 # brushed streaks
        c = 170 + rnd.randint(-14, 16)
        d.line((0, y, 15, y), fill=(c, c + 5, c + 12, 255))
    t["aluminum"] = alu

    t["brass"] = _flat((186, 146, 62), noise=8, seed=16)
    hose = _flat((30, 30, 33), noise=3, seed=17)
    d = ImageDraw.Draw(hose)
    for k in range(-16, 16, 4):                         # braid
        d.line((k, 0, k + 16, 16), fill=(52, 52, 56, 255))
        d.line((k + 16, 0, k, 16), fill=(44, 44, 48, 255))
    t["hose"] = hose

    motor = _flat((44, 47, 53), noise=3, seed=18)
    d = ImageDraw.Draw(motor)
    for x in range(1, 16, 3):                           # cooling fins
        d.line((x, 0, x, 15), fill=(84, 88, 96, 255))
    t["motor"] = motor

    cu = _flat((176, 92, 46), noise=6, seed=19)
    d = ImageDraw.Draw(cu)
    for y in range(0, 16, 2):                           # windings
        d.line((0, y, 15, y), fill=(132, 64, 30, 255))
    t["copper"] = cu

    tread = Image.new("RGBA", (16, 16), (30, 30, 32, 255))
    d = ImageDraw.Draw(tread)
    for y in range(0, 16, 4):
        off = 2 if (y // 4) % 2 else 0
        for x in range(off, 16, 5):
            d.rectangle((x, y, x + 2, y + 2), fill=(50, 50, 52, 255))
    t["rubber"] = tread

    vent = Image.new("RGBA", (16, 16), (18, 18, 20, 255))
    d = ImageDraw.Draw(vent)
    for y in range(1, 16, 3):
        d.line((1, y, 14, y), fill=(70, 72, 78, 255))
    t["vent"] = vent

    glow = _flat((90, 230, 255), noise=3, seed=20)
    ImageDraw.Draw(glow).rectangle((5, 5, 10, 10), fill=(220, 252, 255, 255))
    t["glow"] = glow

    visor = _flat((16, 34, 52), noise=2, seed=21)       # dark tinted viewport
    d = ImageDraw.Draw(visor)
    d.line((0, 4, 15, 4), fill=(70, 130, 170, 255))
    d.line((3, 10, 9, 10), fill=(40, 90, 125, 255))
    t["visor"] = visor

    seat = _flat((34, 35, 40), noise=4, seed=22)         # padded seat, quilted, with a red stripe
    d = ImageDraw.Draw(seat)
    for y in (4, 8, 12):
        d.line((0, y, 15, y), fill=(24, 25, 29, 255))
    d.line((7, 0, 7, 15), fill=(170, 30, 30, 255), width=2)
    t["seat"] = seat

    scr = Image.new("RGBA", (16, 16), (8, 22, 30, 255))  # display: frame, grid and readouts
    d = ImageDraw.Draw(scr)
    d.rectangle((0, 0, 15, 15), outline=(40, 46, 52, 255))
    for k in (5, 10):
        d.line((1, k, 14, k), fill=(20, 70, 80, 255))
        d.line((k, 1, k, 14), fill=(20, 70, 80, 255))
    d.line((2, 12, 5, 8, 8, 9, 11, 4, 13, 6), fill=(90, 235, 255, 255))
    d.rectangle((2, 2, 4, 3), fill=(240, 180, 40, 255))
    t["screen"] = scr
    return t


# ---------------------------------------------------------------------------
# Geometry: axis-aligned boxes in part-local meters, each with an optional
# Euler XYZ rotation (degrees, Minecraft's rotationZYX order) about an origin.
# ---------------------------------------------------------------------------

FACES = ("north", "south", "east", "west", "up", "down")


@dataclass
class Elem:
    a: tuple
    b: tuple
    mat: str
    rot: tuple | None = None
    origin: tuple | None = None
    faces: tuple = FACES
    dent: bool = True


@dataclass
class Part:
    id: str
    label: str
    group: str
    parent: str | None
    segment: str                   # which rigid segment carries it (pelvis, thigh, shin, foot)
    pivot: tuple                   # leg frame meters, at rest
    mass: float
    hp: int
    on_break: str                  # "detach" or "fail"
    effect: str
    rest: tuple = (0.0, 0.0, 0.0)
    anim: str = "fixed"
    shield: list = field(default_factory=list)
    links: dict = field(default_factory=dict)
    elems: list = field(default_factory=list)
    damaged: bool = True


def box(a, b, mat, **kw) -> Elem:
    return Elem(tuple(min(p, q) for p, q in zip(a, b)), tuple(max(p, q) for p, q in zip(a, b)), mat, **kw)


def plate(center, size, mat, rot, **kw) -> Elem:
    """Box of `size` centered on `center`, rotated about its own center."""
    h = [s / 2 for s in size]
    a = tuple(c - s for c, s in zip(center, h))
    b = tuple(c + s for c, s in zip(center, h))
    return Elem(a, b, mat, rot=rot, origin=tuple(center), **kw)


def beam(p, q, w, h, mat, **kw) -> Elem:
    """Box from point p to point q with a w (x) by h (y) cross section."""
    d = [qi - pi for pi, qi in zip(p, q)]
    length = math.sqrt(sum(c * c for c in d))
    mid = tuple((pi + qi) / 2 for pi, qi in zip(p, q))
    yaw = math.degrees(math.atan2(d[0], d[2]))
    pitch = -math.degrees(math.asin(max(-1.0, min(1.0, d[1] / length))))
    return plate(mid, (w, h, length), mat, (round(pitch, 3), round(yaw, 3), 0.0), **kw)


def prism(center, axis, radius, length, sides, mat, faces_end=True, start=0.0, **kw) -> list[Elem]:
    """Regular `sides`-gon prism along a local axis, made of sides/2 rotated boxes."""
    apo = radius * math.cos(math.pi / sides)
    side = 2 * apo * math.tan(math.pi / sides)
    out = []
    ax = "xyz".index(axis)
    for k in range(sides // 2):
        ang = start + k * 360.0 / sides
        size = [0.0, 0.0, 0.0]
        size[ax] = length
        u, v = [i for i in range(3) if i != ax]
        size[u] = side
        size[v] = 2 * apo
        rot = [0.0, 0.0, 0.0]
        rot[ax] = round(ang, 3)
        side_faces = {"x": ("east", "west"), "y": ("up", "down"), "z": ("north", "south")}[axis]
        radial = {0: ("east", "west"), 1: ("up", "down"), 2: ("north", "south")}[v]
        faces = list(radial) + (list(side_faces) if faces_end else [])
        out.append(plate(center, size, mat, tuple(rot), faces=tuple(faces), **kw))
    return out


def ring_x(center, r_in, r_out, width, segs, mat, a0=0.0, a1=360.0, **kw) -> list[Elem]:
    """Arc of boxes around the X axis through `center`, from angle a0 to a1
    (degrees, 0 = +Z, 90 = +Y), r_in..r_out thick and `width` wide in X."""
    out = []
    rm = (r_in + r_out) / 2
    for k in range(segs):
        t0 = math.radians(a0 + (a1 - a0) * k / segs)
        t1 = math.radians(a0 + (a1 - a0) * (k + 1) / segs)
        p = (center[0], center[1] + rm * math.sin(t0), center[2] + rm * math.cos(t0))
        q = (center[0], center[1] + rm * math.sin(t1), center[2] + rm * math.cos(t1))
        # stretch each piece a little so neighbours close the seam
        mid = [(a + b) / 2 for a, b in zip(p, q)]
        d = [(b - a) * 0.56 for a, b in zip(p, q)]
        out.append(beam([m - x for m, x in zip(mid, d)], [m + x for m, x in zip(mid, d)], width, r_out - r_in, mat, **kw))
    return out


def to_local(elems: list[Elem], pivot) -> list[Elem]:
    out = []
    for e in elems:
        sh = lambda p: tuple(pi - qi for pi, qi in zip(p, pivot))
        out.append(Elem(sh(e.a), sh(e.b), e.mat, e.rot, sh(e.origin) if e.origin else None, e.faces, e.dent))
    return out


def mirror_x(elems: list[Elem]) -> list[Elem]:
    """Mirror elements left to right (x -> -x)."""
    out = []
    for e in elems:
        a = (-e.b[0], e.a[1], e.a[2])
        b = (-e.a[0], e.b[1], e.b[2])
        rot = (e.rot[0], -e.rot[1], -e.rot[2]) if e.rot else None
        origin = (-e.origin[0], e.origin[1], e.origin[2]) if e.origin else None
        faces = tuple({"east": "west", "west": "east"}.get(f, f) for f in e.faces)
        out.append(Elem(a, b, e.mat, rot, origin, faces, e.dent))
    return out


def scale_part(p: Part, k: float) -> None:
    """Scales a part about the frame origin by k: its elements, pivot and
    mount points. Rotations and joint angles do not change."""
    sc = lambda v: tuple(round(c * k, 5) for c in v)
    p.elems = [Elem(sc(e.a), sc(e.b), e.mat, e.rot, sc(e.origin) if e.origin else None, e.faces, e.dent)
               for e in p.elems]
    p.pivot = sc(p.pivot)
    if p.links:
        p.links = dict(p.links)
        if "to" in p.links:
            p.links["to"] = [round(c * k, 4) for c in p.links["to"]]
        if "rest_length" in p.links:
            p.links["rest_length"] = round(p.links["rest_length"] * k, 4)


def no_dent(elems: list[Elem]) -> list[Elem]:
    for e in elems:
        e.dent = False
    return elems


# ---------------------------------------------------------------------------
# Writers.
# ---------------------------------------------------------------------------

def u(v: float) -> float:
    return round(8 + v * UNITS_PER_M, 4)


def elem_json(e: Elem, dent_rng: random.Random | None) -> dict:
    a, b = list(e.a), list(e.b)
    rot = list(e.rot) if e.rot else [0.0, 0.0, 0.0]
    origin = list(e.origin) if e.origin else [(ai + bi) / 2 for ai, bi in zip(a, b)]
    mat = e.mat
    if dent_rng is not None:
        mat = MATERIALS[mat].get("dmg", mat)
        if e.dent:
            rot = [r + dent_rng.uniform(-6, 6) for r in rot]
            shift = [dent_rng.uniform(-0.015, 0.015) for _ in range(3)]
            a = [ai + si for ai, si in zip(a, shift)]
            b = [bi + si for bi, si in zip(b, shift)]
            origin = [oi + si for oi, si in zip(origin, shift)]
    out = {"from": [u(c) for c in a], "to": [u(c) for c in b]}
    for c in out["from"] + out["to"]:
        if c < -16 or c > 32:
            raise ValueError(f"element outside the model limit: {out}")
    if any(abs(r) > 1e-6 for r in rot):
        out["rotation"] = {"origin": [u(c) for c in origin], "x": round(rot[0], 3), "y": round(rot[1], 3),
                           "z": round(rot[2], 3)}
    meta = MATERIALS[e.mat]
    faces = {}
    for f in e.faces:
        face = {"uv": [0, 0, 16, 16], "texture": f"#{mat}"}
        if "tint" in meta:
            face["tintindex"] = meta["tint"]
        faces[f] = face
    out["faces"] = faces
    if meta.get("emit"):
        out["light_emission"] = meta["emit"]
    return out


def model_json(elems: list[Elem], damaged: bool, seed: int, folder: str) -> dict:
    rng = random.Random(seed) if damaged else None
    els = [elem_json(e, rng) for e in elems]
    mats = sorted({f["texture"][1:] for el in els for f in el["faces"].values()})
    tex = {m: f"{NS}:item/mech/{m}" for m in mats}
    tex["particle"] = tex[mats[0]]
    return {"textures": tex, "elements": els}


TINTS = [
    {"type": "minecraft:custom_model_data", "index": 0, "default": 0x8A9099},   # armor paint
    {"type": "minecraft:custom_model_data", "index": 1, "default": 0xE0761C},   # accent
]

# Item display rendering in 26.3 is: entity * matrix * rotateY(180) * translate(-0.5) * this.
# This undoes the 180 degree turn and scales the half-size model back up about
# its center, so the model's pivot lands on the display's origin.
S = 1 / MODEL_SCALE
UPSCALE = {"translation": [0.5 + 0.5 * S, 0.5 - 0.5 * S, 0.5 + 0.5 * S], "left_rotation": [0, 1, 0, 0],
           "scale": [S] * 3, "right_rotation": [0, 0, 0, 1]}


def item_json(folder: str, name: str, has_damaged: bool, tints: list | None = None) -> dict:
    """An item definition; `tints` are the default paint and accent colors (default TINTS')."""
    tl = TINTS if tints is None else [dict(t, default=c) for t, c in zip(TINTS, tints)]
    base = {"type": "minecraft:model", "model": f"{NS}:item/{folder}/{name}", "transformation": UPSCALE,
            "tints": tl}
    if not has_damaged:
        return {"model": base}
    dmg = dict(base, model=f"{NS}:item/{folder}/{name}_damaged")
    return {"model": {"type": "minecraft:select", "property": "minecraft:custom_model_data", "index": 0,
                      "cases": [{"when": "damaged", "model": dmg}], "fallback": base}}


def hitbox(elems: list[Elem]) -> list:
    """Local AABB (meters) around every element corner after its rotation."""
    pts = []
    for e in elems:
        corners = [(x, y, z) for x in (e.a[0], e.b[0]) for y in (e.a[1], e.b[1]) for z in (e.a[2], e.b[2])]
        if e.rot:
            rx, ry, rz = (math.radians(r) for r in e.rot)
            o = e.origin

            def R(p):
                x, y, z = (p[i] - o[i] for i in range(3))
                y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
                x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
                x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)
                return (x + o[0], y + o[1], z + o[2])
            corners = [R(c) for c in corners]
        pts += corners
    lo = [round(min(p[i] for p in pts), 3) for i in range(3)]
    hi = [round(max(p[i] for p in pts), 3) for i in range(3)]
    return [lo, hi]


def write_textures(used: set[str]) -> dict[str, str]:
    """Writes the textures the models use; returns them as data URLs for the viewer."""
    tdir = ASSETS / "textures/item/mech"
    tdir.mkdir(parents=True, exist_ok=True)
    for old in tdir.glob("*"):
        old.unlink()
    out = {}
    for name, img in make_textures().items():
        if name not in used:
            continue
        img.save(tdir / f"{name}.png", optimize=True)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        out[name] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    missing = used - set(out)
    if missing:
        raise SystemExit(f"textures missing: {missing}")
    return out


def write_models(folder: str, parts: list[Part], tints: list | None = None) -> dict[str, dict]:
    """Writes each part's model (and _damaged variant) and item definition
    under `folder`; returns every model for the viewer."""
    mdir = ASSETS / f"models/item/{folder}"
    idir = ASSETS / f"items/{folder}"
    for d in (mdir, idir):
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("*.json"):
            old.unlink()
    models = {}
    for i, p in enumerate(parts):
        m = model_json(p.elems, False, 0, folder)
        (mdir / f"{p.id}.json").write_text(json.dumps(m, indent=1) + "\n")
        models[p.id] = m
        if p.damaged:
            md = model_json(p.elems, True, 1000 + i, folder)
            (mdir / f"{p.id}_damaged.json").write_text(json.dumps(md, indent=1) + "\n")
            models[p.id + "_damaged"] = md
        (idir / f"{p.id}.json").write_text(json.dumps(item_json(folder, p.id, p.damaged, tints), indent=1) + "\n")
    return models
