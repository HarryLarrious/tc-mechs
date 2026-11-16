"""The spider: a four-legged mech with a long rail cannon.

A long, angular fuselage like a jet's cockpit section (about 4 m nose to
tail, the pilot under a canopy), slung between four long legs whose knees
rise well above it, each leg ending in a blade-like shin and a dark foot pad.
No turret: the rail cannon rides the spine and the whole mech turns to aim.
White armor with magenta trim (the paint and accent tints), dark blades.

Built in real meters (SCALE 1), mech frame +X left, +Y up, +Z forward,
origin on the ground under the middle of the body.

Each leg is designed once, in its own frame, pointing outward along +X from
its root on the body: a yaw joint at the root (about Y: swings the leg
forward and back), a femur joint (about Z: raises and lowers the femur) and
a tibia joint at the knee (about Z). The legs are placed at the body's four
corners; the right ones are mirrored in X (their Z joints run the other
way). At rest every leg points straight out sideways; the gait turns them to
their feet. Leg ids end in _lf, _lh, _rf, _rh (left front, left hind, ...).

The cabin, the canopy (its hatch), the cockpit and the gun use the same part
ids as the two-legged types (torso_frame, hatch, cockpit, heavy_gun_c, ...),
so the damage model and the pilot code drive them unchanged.
"""

from __future__ import annotations

import copy
import math

import mech_parts as W
import mech_sprinter as SP
from mech_lib import Elem, Part, beam, box, mirror_x, no_dent, plate, prism, to_local

add, sub, norm, lerp = W.add, W.sub, W.norm, W.lerp
X, Y, Z = W.X, W.Y, W.Z
facet, ridge, oplate2, cross, dot = SP.facet, SP.ridge, SP.oplate2, SP.cross, SP.dot

SCALE = 1.0

# ---------------------------------------------------------------------------
# Legs (leg frame: the root at the origin, the leg along +X).
# ---------------------------------------------------------------------------

ROOT_Y = 1.2                                  # the leg roots' height (the body's middle)
DY = ROOT_Y - 3.0                             # the body's heights below are written for roots 3 m up
ROOTS = {"lf": (0.95, 0.70), "lh": (0.95, -1.10), "rf": (-0.95, 0.70), "rh": (-0.95, -1.10)}   # along the fuselage's sides
COXA = (0.75, 0.05, 0.0)                      # the femur joint
KNEE = (3.0, 2.3, 0.0)                        # the knee, high above the body
FOOT = (5.0, -ROOT_Y, 0.0)                    # the claw's tip, on the ground at rest
HOME_YAW = 40.0                               # the feet stand this far forward or back of straight out...
HOME_REACH = 4.2                              # ...this far out from the root
YAW_RANGE = [-75, 75]
FEM_RANGE = [-55, 70]                         # left legs; the right ones' Z joints are mirrored
TIB_RANGE = [-80, 75]

L1 = math.dist(COXA, KNEE)
L2 = math.dist(KNEE, FOOT)
T_FEM = norm(sub(KNEE, COXA))
U_FEM = (-T_FEM[1], T_FEM[0], 0.0)            # the femur's top (up and in)
T_TIB = norm(sub(FOOT, KNEE))
U_TIB = (-T_TIB[1], T_TIB[0], 0.0)            # the tibia's outer edge (out and up)


def fem(s, off=0.0, z=0.0):
    return add(COXA, (T_FEM, s), (U_FEM, off), (Z, z))


def tib(s, off=0.0, z=0.0):
    return add(KNEE, (T_TIB, s), (U_TIB, off), (Z, z))


LEG: list[Part] = []
ARMOR_HP, PART_HP, MASS = 0.8, 0.9, 0.7


def part(p: Part, elems: list[Elem]) -> Part:
    p.pivot = tuple(round(c, 4) for c in p.pivot)
    p.elems = to_local(elems, p.pivot)
    p.hp = round(p.hp * (ARMOR_HP if p.group == "armor" else PART_HP))
    p.mass = round(p.mass * MASS, 1)
    LEG.append(p)
    return p


def coxa():
    """The hip: a turntable on the body's leg housing, an arm out to the femur
    joint and the femur's drive motor."""
    e = prism((0.0, 0.40, 0.0), "y", 0.36, 0.10, 8, "steel")                       # turntable
    e += prism((0.0, 0.47, 0.0), "y", 0.22, 0.04, 8, "accent")
    e.append(box((0.05, -0.30, -0.30), (0.95, 0.34, 0.30), "gunmetal"))              # arm
    e.append(facet((0.05, 0.34, -0.30), (0.05, 0.34, 0.30), (0.80, 0.42, -0.30), 0.05, "armor", out=(0.0, 1.0, 0.0)))
    for s_ in (1, -1):
        e.append(facet((0.05, -0.30, s_ * 0.30), (0.95, -0.30, s_ * 0.30), (0.05, 0.34, s_ * 0.30), 0.04, "armor",
                       out=(0.0, 0.0, s_ * 1.0)))
    e += prism(COXA, "z", 0.30, 0.72, 8, "motor")                                    # femur drive
    for zz in (-0.30, 0.30):
        e += prism(add(COXA, (Z, zz)), "z", 0.32, 0.05, 8, "darksteel")
    e += prism(add(COXA, (Z, 0.39)), "z", 0.20, 0.06, 8, "accent")
    e += prism(add(COXA, (Z, -0.39)), "z", 0.20, 0.06, 8, "accent")
    no_dent(e)
    part(Part("coxa", "Hip (yaw turntable and femur drive)", "actuator", None, "coxa", (0.0, 0.0, 0.0),
              140, 220, "fail", "Loses torque with HP: the leg turns and lifts slower; at 0 the leg drags"), e)


def femur():
    e = [beam(fem(0.20), fem(L1 - 0.15), 0.40, 0.42, "gunmetal")]                   # core
    for zz in (-0.24, 0.24):
        e.append(beam(fem(0.30, 0.0, zz), fem(L1 - 0.30, 0.0, zz), 0.06, 0.30, "steel"))  # side rails
    e.append(beam(fem(0.40, -0.25), fem(L1 - 0.50, -0.25), 0.18, 0.08, "hose"))       # power line underneath
    part(Part("femur", "Femur (upper leg frame)", "structure", "coxa", "femur", COXA,
              260, 300, "fail", "Bends: the leg's reach shortens; at 0 the leg is lost"), e)


def femur_armor():
    """A broad white blade over the femur, deepest in the middle so the upper
    leg reads as a curved fin, with a ridged top."""
    e = []
    prof = [(0.25, 0.22, -0.22), (L1 * 0.5, 0.52, -0.40), (L1 - 0.35, 0.26, -0.22)]   # (along, top, bottom)
    for (a0, t0, b0), (a1, t1, b1) in zip(prof, prof[1:]):
        for s_ in (1, -1):
            e += quad(fem(a0, b0, s_ * 0.29), fem(a0, t0, s_ * 0.29), fem(a1, b1, s_ * 0.29), fem(a1, t1, s_ * 0.29),
                         0.04, "armor", (0.0, 0.0, s_ * 1.0))                                   # side blades
        e += ridge(fem(a0, t0), fem(a1, t1), U_FEM, Z, 0.30, 0.05, 32, "armor")             # ridged top
    for s_ in (1, -1):
        e.append(beam(fem(0.55, 0.05, s_ * 0.315), fem(L1 * 0.5, 0.30, s_ * 0.315), 0.012, 0.06, "accent"))
        e.append(beam(fem(L1 * 0.5, 0.30, s_ * 0.315), fem(L1 - 0.6, 0.08, s_ * 0.315), 0.012, 0.06, "accent"))
    e.append(beam(fem(L1 - 0.55, 0.29), fem(L1 - 0.30, 0.27), 0.36, 0.06, "accent"))      # magenta band at the knee
    part(Part("femur_armor", "Femur armor (curved blade)", "armor", "femur", "femur", COXA,
              80, 220, "detach", "Torn off: the femur and its power line take hits directly"), e)


def knee_motor():
    e = prism(KNEE, "z", 0.32, 0.70, 8, "motor")
    for zz in (-0.36, 0.36):
        e += prism(add(KNEE, (Z, zz)), "z", 0.24, 0.05, 8, "accent")
    e += prism(add(KNEE, (Z, 0.40)), "z", 0.12, 0.04, 6, "steel")
    e += prism(add(KNEE, (Z, -0.40)), "z", 0.12, 0.04, 6, "steel")
    part(Part("knee_motor", "Knee motor", "actuator", "femur", "femur", KNEE,
              70, 160, "fail", "Loses torque with HP: the leg steps slower; at 0 the knee locks"), no_dent(e))


def tibia():
    """The long, dark, blade-like lower leg, narrowing to the claw."""
    e = [beam(tib(0.15), tib(0.35 * L2), 0.40, 0.44, "gunmetal"),
         beam(tib(0.35 * L2), tib(0.72 * L2), 0.30, 0.32, "darksteel"),
         beam(tib(0.72 * L2), tib(0.93 * L2), 0.20, 0.22, "darksteel")]
    e.append(beam(tib(0.30 * L2, 0.27), tib(0.90 * L2, 0.14), 0.05, 0.16, "darksteel"))   # blade fin on the outer edge
    e.append(beam(tib(0.20 * L2, -0.23), tib(0.65 * L2, -0.17), 0.08, 0.06, "hose"))
    for k in (0.42, 0.58):
        e.append(beam(tib(k * L2, 0.0, 0.0), tib(k * L2 + 0.08, 0.0, 0.0), 0.33, 0.35, "steel"))  # clamp bands
    part(Part("tibia", "Tibia (blade)", "structure", "femur", "tibia", KNEE,
              220, 280, "fail", "Cracks: the foot lands short; at 0 the leg is lost"), e)


def tibia_armor():
    e = ridge(tib(0.20, 0.25), tib(0.36 * L2, 0.21), U_TIB, Z, 0.24, 0.05, 30, "armor")
    for s_ in (1, -1):
        e.append(facet(tib(0.25, -0.20, s_ * 0.235), tib(0.34 * L2, -0.17, s_ * 0.18), tib(0.25, 0.20, s_ * 0.235),
                       0.04, "armor", out=(0.0, 0.0, s_ * 1.0)))
    e.append(beam(tib(0.36 * L2 - 0.15, 0.24), tib(0.36 * L2, 0.21), 0.30, 0.05, "accent"))
    part(Part("tibia_armor", "Tibia armor (upper shell)", "armor", "tibia", "tibia", KNEE,
              60, 180, "detach", "Torn off: the tibia takes hits directly"), e)


def claw():
    """The foot: an ankle knuckle at the shin's end and a chunky, dark pad."""
    tip = FOOT
    ank = add(tip, (Y, 0.42), (X, -0.06))
    e = [beam(tib(0.90 * L2), ank, 0.20, 0.22, "darksteel")]
    e += prism(ank, "z", 0.17, 0.40, 8, "steel")                                            # ankle knuckle
    e += prism(ank, "z", 0.10, 0.46, 8, "accent")
    e.append(box(add(tip, (X, -0.36), (Y, 0.10), (Z, -0.24)), add(tip, (X, 0.26), (Y, 0.30), (Z, 0.24)), "darksteel"))  # pad body
    e.append(facet(add(tip, (X, -0.36), (Y, 0.30), (Z, -0.24)), add(tip, (X, -0.36), (Y, 0.30), (Z, 0.24)),
                   add(tip, (X, -0.10), (Y, 0.40), (Z, -0.24)), 0.04, "gunmetal", out=(0.0, 1.0, 0.0)))
    e.append(facet(add(tip, (X, 0.26), (Y, 0.30), (Z, -0.24)), add(tip, (X, 0.26), (Y, 0.30), (Z, 0.24)),
                   add(tip, (X, 0.02), (Y, 0.40), (Z, -0.24)), 0.04, "gunmetal", out=(0.0, 1.0, 0.0)))
    e.append(box(add(tip, (X, -0.40), (Y, 0.0), (Z, -0.27)), add(tip, (X, 0.30), (Y, 0.10), (Z, 0.27)), "rubber"))  # sole
    e.append(box(add(tip, (X, 0.26), (Y, 0.14), (Z, -0.10)), add(tip, (X, 0.29), (Y, 0.24), (Z, 0.10)), "accent"))  # toe mark
    part(Part("claw", "Foot (ankle and pad)", "structure", "tibia", "tibia", KNEE,
              40, 120, "fail", "Cracked: the foot slips; at 0 the mech stumbles on every step"), no_dent(e))


def build_leg() -> list[Part]:
    LEG.clear()
    coxa(); femur(); femur_armor(); knee_motor(); tibia(); tibia_armor(); claw()
    return LEG


def leg_point(t: str, p) -> tuple:
    """A leg-frame point of leg t in the mech frame (at rest)."""
    rx, rz = ROOTS[t]
    s = 1 if rx > 0 else -1
    return (rx + s * p[0], ROOT_Y + p[1], rz + p[2])


def place_legs(leg: list[Part]) -> list[Part]:
    out = []
    for t, (rx, rz) in ROOTS.items():
        s = 1 if rx > 0 else -1
        side = {"lf": "left front", "lh": "left hind", "rf": "right front", "rh": "right hind"}[t]
        for p in leg:
            q = copy.deepcopy(p)
            q.id = f"{p.id}_{t}"
            q.label = f"{p.label} ({side})"
            q.parent = f"{p.parent}_{t}" if p.parent else "pelvis"
            q.segment = f"{p.segment}_{t}"
            q.pivot = tuple(round(c, 4) for c in leg_point(t, p.pivot))
            q.shield = [f"{x}_{t}" for x in p.shield]
            if s < 0:
                q.elems = mirror_x(p.elems)
            out.append(q)
    return out


def leg_joints():
    segments, joints = [], {}
    for t, (rx, rz) in ROOTS.items():
        s = 1 if rx > 0 else -1
        segments += [f"coxa_{t}", f"femur_{t}", f"tibia_{t}"]
        z = (lambda r: r) if s > 0 else (lambda r: [-r[1], -r[0]])
        name = t.upper()
        joints[f"yaw_{t}"] = {"pivot": list(leg_point(t, (0, 0, 0))), "axis": "y", "parent": "pelvis",
                              "child": f"coxa_{t}", "range": YAW_RANGE, "label": f"Hip {name}"}
        joints[f"fem_{t}"] = {"pivot": [round(c, 4) for c in leg_point(t, COXA)], "axis": "z", "parent": f"coxa_{t}",
                              "child": f"femur_{t}", "range": z(FEM_RANGE), "label": f"Femur {name}"}
        joints[f"tib_{t}"] = {"pivot": [round(c, 4) for c in leg_point(t, KNEE)], "axis": "z", "parent": f"femur_{t}",
                              "child": f"tibia_{t}", "range": z(TIB_RANGE), "label": f"Knee {name}"}
    return segments, joints


def legs_data() -> list:
    """For the game: per leg (name, side, its three joints, the claw's tip and its
    home spot on the ground, mech frame at rest)."""
    out = []
    for t, (rx, rz) in ROOTS.items():
        s = 1 if rx > 0 else -1
        f = 1 if rz > 0 else -1
        a = math.radians(HOME_YAW)
        home = (rx + s * HOME_REACH * math.cos(a), rz + f * HOME_REACH * math.sin(a))
        out.append((t, s, f"yaw_{t}", f"fem_{t}", f"tib_{t}", leg_point(t, FOOT), home))
    return out


# ---------------------------------------------------------------------------
# The fuselage: one long, angular, fixed body like a jet's cockpit section,
# about 4 m nose to tail. The pilot lies back under a faceted canopy (the
# hatch); behind it the hull rises above the canopy, with the rail cannon on
# top. The canopy, that raised rear hull and the cannon are one lid, hinged
# across the tail, that lifts open with the hatch. The legs hang off its sides.
# Everything is rigid: the cabin parts sit on a "torso" segment whose waist
# joint is locked straight ahead (the pilot code rides that segment).
# ---------------------------------------------------------------------------

NOSE_Z, TAIL_Z = 3.40, -2.50                  # nose tip and tail end
HALF_W = 0.62                                 # cabin half width (inside)
FLOOR_Y = 2.62 + DY                                # cabin floor (top of the grating)
DECK_Y = 3.36 + DY                                 # the top deck, the canopy's rim
CANOPY_Y = 3.90 + DY                               # the canopy's flat top
BELLY_Y = 2.42 + DY
SIDE_W = 0.80                                 # the fuselage's half width at its chines
CHINE_Y = 2.95 + DY
CAN_FRONT, CAN_TOP_F, CAN_TOP_R, CAN_REAR = 1.00, 0.00, -1.20, -1.20
CAN_TW = 0.42                                 # the canopy's half width at its top
REAR_RISE = 0.36                              # the rear hull's top climbs this much from the canopy to the tail
LID_PIVOT = (0.0, DECK_Y, TAIL_Z)             # the lid (canopy, rear hull, cannon mount) hinges across the tail...
LID_OPEN = -50                                # ...and lifts this far with the hatch   # canopy z: windscreen foot, top front/rear, rear foot
RECLINE, SEAT_TOP, HIPS_Z = 40.0, 0.18, -0.11
STICK_X, STICK_Z, GRIP_UP = 0.33, 0.15, 0.415
SEAT = (0.0, FLOOR_Y + SEAT_TOP, -0.10)
_r = math.radians(RECLINE)
EYE = (0.0, SEAT[1] + 1.03 * math.cos(_r), SEAT[2] + HIPS_Z - 1.03 * math.sin(_r))
# the rail cannon's trunnion: on a short pylon on top of the rear hull
RG = (0.0, round(CANOPY_Y + REAR_RISE * (CAN_REAR + 1.95) / (CAN_REAR - TAIL_Z) + 0.50, 3), -1.95)
RG_MUZZLE = (RG[0], RG[1], 5.10)
LG = (0.36, BELLY_Y - 0.20, 0.55)             # the left belly gun's trunnion (the right one is mirrored)
LG_MUZZLE = (LG[0], LG[1], LG[2] + 1.42)
LG_TRAVERSE, LG_RANGE = [-30, 30], [-10, 15]  # elevation: negative = muzzle up (the nose is just above)
CAMERA_EYE = (0.0, 2.95 + DY, NOSE_Z + 0.08)       # the nose camera
WAIST = (0.0, ROOT_Y, 0.0)                    # the locked joint the cabin parts ride
PIVOT = (0.0, ROOT_Y, 0.0)
HATCH_Z = (CAN_FRONT + CAN_REAR) / 2


def pilot_grips():
    return [(s * STICK_X, SEAT[1] + GRIP_UP, SEAT[2] + STICK_Z + 0.0275) for s in (1, -1)]


def _add(out, p: Part, elems, pivot=PIVOT):
    p.pivot = tuple(round(c, 4) for c in pivot)
    p.elems = to_local(elems, p.pivot)
    p.hp = round(p.hp * (ARMOR_HP if p.group == "armor" else PART_HP))
    p.mass = round(p.mass * MASS, 1)
    out.append(p)
    return p


# The fuselage's cross sections, tail to nose: z, then (half width, height) of
# the belly edge, the chine and the deck edge. Between two stations each panel
# is a flat 4-sided facet; a tapering one is built as strips (Minecraft only
# has boxes), which reads as a stepped, angular taper.
# the rear hull up to the deck (the lid above it is rear_lid()), squared off
REAR = ((0.54, BELLY_Y), (SIDE_W + 0.10, CHINE_Y), (0.76, DECK_Y))
STATIONS = [(TAIL_Z, *REAR),
            (CAN_REAR, (0.50, BELLY_Y), (SIDE_W, CHINE_Y), (0.70, DECK_Y)),
            (CAN_REAR, (0.50, BELLY_Y), (SIDE_W, CHINE_Y), (HALF_W + 0.06, DECK_Y)),
            (CAN_FRONT, (0.50, BELLY_Y), (SIDE_W, CHINE_Y), (HALF_W + 0.06, DECK_Y)),
            (2.45, (0.30, 2.54 + DY), (0.50, 2.91 + DY), (0.36, 3.16 + DY)),
            (NOSE_Z, (0.03, 2.80 + DY), (0.05, 2.88 + DY), (0.03, 2.96 + DY))]


def _lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def quad(p0, p1, q0, q1, t, mat, out, n=None, **kw) -> list[Elem]:
    """A flat 4-sided panel, its edge p0-p1 at one end and q0-q1 at the other,
    as `n` strips across (by default as many as its taper needs)."""
    wa, wb = math.dist(p0, p1), math.dist(q0, q1)
    if n is None:
        n = 1 if abs(wa - wb) < 0.06 else max(2, min(7, round(abs(wa - wb) / 0.12)))
    ma, mb = _lerp(p0, p1, 0.5), _lerp(q0, q1, 0.5)
    e = []
    for i in range(n):
        s_ = (i + 0.5) / n
        L, R = _lerp(p0, q0, s_), _lerp(p1, q1, s_)
        if math.dist(L, R) < 0.03:
            continue
        d = sub(_lerp(ma, mb, (i + 1) / n), _lerp(ma, mb, i / n))
        h = tuple(c / 2 for c in d)
        e.append(facet(sub(L, h), sub(R, h), add(L, (h, 1.0)), t, mat, out=out, **kw))
    return e


def rear_top(z):
    """The rear hull's top at z (behind the canopy)."""
    return CANOPY_Y + REAR_RISE * (CAN_REAR - z) / (CAN_REAR - TAIL_Z)


def station_y(z, k):
    """The height of edge k (0 belly, 1 chine, 2 deck) at z."""
    for a, b in zip(STATIONS, STATIONS[1:]):
        if a[0] <= z <= b[0]:
            return _lerp(a[k + 1], b[k + 1], (z - a[0]) / (b[0] - a[0]))[1]
    return STATIONS[-1][k + 1][1]


def loft(panels):
    """The fuselage's skin panels named in `panels` (bottom, lower, upper, top),
    over every pair of stations (top only over the nose and tail: the cabin
    opening and the spine are the deck's)."""
    e = []
    for a, b in zip(STATIONS, STATIONS[1:]):
        za, zb = a[0], b[0]
        if zb - za < 0.01:
            continue
        fwd = 0.0 if a[1] == b[1] else (0.4 if zb > 0 else -0.4)
        pt = lambda st, k, sx: (sx * st[k + 1][0], st[k + 1][1], st[0])
        if "bottom" in panels:
            e += quad(pt(a, 0, 1), pt(a, 0, -1), pt(b, 0, 1), pt(b, 0, -1), 0.04, "armor", (0.0, -1.0, fwd))
        for s_ in (1, -1):
            if "lower" in panels:
                e += quad(pt(a, 0, s_), pt(a, 1, s_), pt(b, 0, s_), pt(b, 1, s_), 0.04, "armor", (s_, -0.6, fwd))
            if "upper" in panels:
                e += quad(pt(a, 1, s_), pt(a, 2, s_), pt(b, 1, s_), pt(b, 2, s_), 0.04, "armor", (s_, 0.6, fwd))
            if "chine" in panels and b is not STATIONS[-1]:
                e.append(beam(add(pt(a, 1, s_), ((s_ * 0.025, 0.0, 0.0), 1.0)),
                              add(pt(b, 1, s_), ((s_ * 0.025, 0.0, 0.0), 1.0)), 0.035, 0.035, "accent"))
        if "top" in panels and (zb <= CAN_REAR or za >= CAN_FRONT):      # not over the cabin
            e += quad(pt(a, 2, 1), pt(a, 2, -1), pt(b, 2, 1), pt(b, 2, -1), 0.04, "armor", (0.0, 1.0, fwd))
    return e


def chassis():
    """The frame: a keel along the belly, the cabin tub's walls, spars out to the
    four leg housings."""
    e = [box((-0.45, BELLY_Y + 0.04, -1.40), (0.45, FLOOR_Y - 0.08, CAN_FRONT), "gunmetal")]   # keel
    for s_ in (1, -1):
        x0, x1 = sorted((s_ * HALF_W, s_ * (HALF_W + 0.05)))
        e.append(box((x0, FLOOR_Y - 0.08, CAN_REAR), (x1, DECK_Y, CAN_FRONT), "gunmetal"))         # tub walls
    e.append(box((-HALF_W, FLOOR_Y - 0.08, CAN_REAR - 0.05), (HALF_W, DECK_Y, CAN_REAR), "gunmetal"))
    e.append(box((-HALF_W, FLOOR_Y - 0.08, CAN_FRONT), (HALF_W, DECK_Y - 0.10, CAN_FRONT + 0.05), "gunmetal"))
    e.append(box((-HALF_W, FLOOR_Y - 0.10, CAN_REAR), (HALF_W, FLOOR_Y - 0.05, CAN_FRONT), "gunmetal"))  # floor
    for t, (rx, rz) in ROOTS.items():
        e += prism((rx, ROOT_Y, rz), "y", 0.36, 0.70, 8, "darksteel")                       # leg housings
        e += prism((rx, ROOT_Y - 0.38, rz), "y", 0.26, 0.08, 8, "steel")
        x0, x1 = sorted((0.0, rx))
        e.append(box((x0, ROOT_Y - 0.22, rz - 0.24), (x1, ROOT_Y + 0.22, rz + 0.24), "gunmetal"))   # spars
    return no_dent(e)


def skin():
    """The outer armor: the belly and the chined sides, from the tapering tail
    to the pointed nose, every face a flat facet."""
    e = loft(("bottom", "lower", "upper", "chine"))
    (bw, by), (cw, cy), (dw, dy) = REAR
    z = TAIL_Z
    e += quad((bw, by, z), (-bw, by, z), (cw, cy, z), (-cw, cy, z), 0.04, "armor", (0.0, 0.0, -1.0))    # back plate
    e += quad((cw, cy, z), (-cw, cy, z), (dw, dy, z), (-dw, dy, z), 0.04, "armor", (0.0, 0.0, -1.0))
    for s_ in (1, -1):
        e.append(box((s_ * (cw - 0.20) - 0.08, cy - 0.06, z - 0.03), (s_ * (cw - 0.20) + 0.08, cy + 0.06, z), "lamp"))  # tail lights
        e.append(beam((s_ * (cw - 0.06), cy - 0.10, z - 0.02), (s_ * (dw - 0.04), dy - 0.06, z - 0.02), 0.04, 0.02, "accent"))
    e.append(box((-0.30, BELLY_Y - 0.010, -0.40), (0.30, BELLY_Y + 0.004, 0.30), "hazard", faces=("down",)))
    return e


def deck():
    """The top deck: the nose's top, the spine and tail behind the canopy, and
    the sills along the cabin opening."""
    w = HALF_W + 0.06
    e = loft(("top",))
    for s_ in (1, -1):
        x0, x1 = sorted((s_ * HALF_W, s_ * w))
        e.append(box((x0, DECK_Y - 0.04, CAN_REAR), (x1, DECK_Y, CAN_FRONT), "armor"))      # canopy sills
        e.append(box((x0, DECK_Y, CAN_REAR + 0.05), (x1, DECK_Y + 0.012, CAN_FRONT - 0.05), "hazard"))
    z1 = NOSE_Z - 0.55
    e.append(beam((0.0, DECK_Y + 0.02, CAN_FRONT + 0.05), (0.0, station_y(z1, 2) + 0.02, z1), 0.10, 0.012, "accent"))
    return e


def canopy():
    """The canopy: faceted glass in a frame, narrower at the top, its top
    running straight back into the rear hull's lid; it lifts with the lid. The
    glass has only its outer faces, so it is clear from inside."""
    w, tw, y0, y1 = HALF_W + 0.02, CAN_TW, DECK_Y, CANOPY_Y
    f, tf, r = CAN_FRONT, CAN_TOP_F, CAN_REAR
    e = quad((w, y0, f), (-w, y0, f), (tw, y1, tf), (-tw, y1, tf), 0.02, "visor", (0.0, 0.6, 1.0))        # windscreen
    e += quad((tw, y1, tf), (-tw, y1, tf), (tw, y1, r), (-tw, y1, r), 0.02, "visor", (0.0, 1.0, 0.0))    # top
    for s_ in (1, -1):
        e += quad((s_ * w, y0, r), (s_ * w, y0, f), (s_ * tw, y1, r), (s_ * tw, y1, tf), 0.02, "visor",
                  (s_ * 1.0, 0.3, 0.0))                                                                   # side glass
        e.append(beam((s_ * w, y0 + 0.01, f), (s_ * tw, y1, tf), 0.04, 0.04, "armor"))                   # frame
        e.append(beam((s_ * tw, y1 + 0.01, tf), (s_ * tw, y1 + 0.01, r), 0.04, 0.04, "armor"))
        e.append(beam((s_ * tw, y1, r + 0.02), (s_ * w, y0 + 0.01, r + 0.02), 0.05, 0.05, "armor"))
        e.append(beam((s_ * w, y0 + 0.02, r), (s_ * w, y0 + 0.02, f), 0.04, 0.04, "armor"))
    e.append(beam((0.0, y1 + 0.02, tf), (0.0, y1 + 0.02, r), 0.05, 0.03, "accent"))                  # spine strip
    for el in e:
        el.dent = False
    return e


def cockpit():
    """The cabin: a reclined seat, the joysticks and an instrument panel under
    the windscreen."""
    z0 = SEAT[2]

    def P(x, y, z):
        return (x, FLOOR_Y + y, z0 + z)

    def B(a, b, mat, **kw):
        return box(P(*a), P(*b), mat, **kw)

    def L(c, size, mat, rot, **kw):
        return plate(P(*c), size, mat, rot, **kw)

    def M(p, q, w, h, mat, **kw):
        return beam(P(*p), P(*q), w, h, mat, **kw)

    st = SEAT_TOP
    e = [box((-HALF_W, FLOOR_Y - 0.05, CAN_REAR), (HALF_W, FLOOR_Y, CAN_FRONT), "vent", faces=("up",))]
    e.append(B((-0.22, 0.0, -0.22), (0.22, 0.04, 0.22), "steel"))
    e.append(B((-0.05, 0.04, -0.05), (0.05, st - 0.10, 0.05), "darksteel"))
    e.append(L((0.0, st - 0.05, 0.0), (0.50, 0.10, 0.48), "seat", (-12.0, 0.0, 0.0)))

    def back(y, z):
        r = math.radians(-RECLINE)
        return (y * math.cos(r) - z * math.sin(r) + st, y * math.sin(r) + z * math.cos(r) - 0.24)

    rec = (-RECLINE, 0.0, 0.0)
    for (by, bz), size, mat in (((0.40, -0.05), (0.48, 0.80, 0.10), "seat"), ((1.00, -0.16), (0.28, 0.22, 0.10), "seat"),
                                ((0.40, -0.12), (0.44, 0.72, 0.04), "darksteel")):
        y, z = back(by, bz)
        e.append(L((0.0, y, z), size, mat, rec))
    for s in (1, -1):
        x0, x1 = sorted((s * 0.27, s * 0.35))
        e.append(B((x0, st + 0.10, -0.22), (x1, st + 0.16, 0.22), "gunmetal"))
        jx, jz = s * STICK_X, STICK_Z
        e += prism(P(jx, st + 0.20, jz), "y", 0.04, 0.04, 8, "darksteel")
        e.append(M((jx, st + 0.20, jz), (jx, st + 0.36, jz + 0.03), 0.025, 0.025, "steel"))
        e.append(B((jx - 0.025, st + 0.36, jz - 0.005), (jx + 0.025, st + 0.47, jz + 0.06), "accent"))
        e.append(B((jx - 0.012, st + 0.44, jz + 0.06), (jx + 0.012, st + 0.46, jz + 0.068), "glow"))
    panel = CAN_FRONT - 0.12 - z0
    e.append(L((0.0, 0.60, panel), (0.80, 0.30, 0.06), "darksteel", (-35.0, 0.0, 0.0)))                # instrument panel
    e.append(L((0.0, 0.615, panel - 0.035), (0.70, 0.22, 0.01), "screen", (-35.0, 0.0, 0.0), faces=("north",)))
    return no_dent(e)


def sensors():
    """The nose camera (its pod at the tip), red sensor eyes on the nose's
    flanks and a sensor strip under the nose."""
    cx, cy, cz = CAMERA_EYE
    e = [box((cx - 0.10, cy - 0.09, cz - 0.30), (cx + 0.10, cy + 0.07, cz - 0.04), "darksteel")]
    for x in (-0.045, 0.045):
        e += prism((cx + x, cy, cz - 0.03), "z", 0.035, 0.02, 6, "steel")
        e += prism((cx + x, cy, cz - 0.015), "z", 0.024, 0.01, 6, "lamp")
    z = CAN_FRONT + 0.30
    hw = SIDE_W + (STATIONS[-2][2][0] - SIDE_W) * (z - CAN_FRONT) / (STATIONS[-2][0] - CAN_FRONT)   # the chine's half width there
    for s_ in (1, -1):
        x = s_ * (hw - 0.16)
        y = CHINE_Y + 0.10
        e.append(box((x - 0.07, y - 0.07, z - 0.10), (x + 0.07, y + 0.07, z + 0.10), "darksteel"))   # eye housing
        e += prism((x, y, z + 0.11), "z", 0.05, 0.03, 8, "lamp")                                     # red eye
    e.append(box((-0.14, BELLY_Y - 0.012, 0.78), (0.14, BELLY_Y + 0.004, 0.97), "glow"))    # flush on the flat belly
    return no_dent(e)


def capacitors():
    """A capacitor bank in the tail behind the cabin, feeding the cannon, and
    the tail's exhaust vent."""
    e = [box((-0.32, 2.66 + DY, TAIL_Z + 0.10), (0.32, 3.14 + DY, CAN_REAR - 0.06), "gunmetal")]
    for k in range(3):
        e += prism((-0.20 + 0.20 * k, 3.02 + DY, (TAIL_Z + 0.10 + CAN_REAR) / 2), "z", 0.07, 0.55, 8, "copper")
    e.append(box((-0.40, CHINE_Y + 0.24, TAIL_Z - 0.04), (0.40, CHINE_Y + 0.28, TAIL_Z), "glow"))
    return e


def power():
    """The power pack, in the nose ahead of the cabin."""
    return [box((-0.28, BELLY_Y + 0.10, CAN_FRONT + 0.08), (0.28, CHINE_Y + 0.15, 1.50), "gunmetal"),
            box((-0.20, CHINE_Y + 0.15, CAN_FRONT + 0.15), (0.20, CHINE_Y + 0.22, 1.30), "copper")]


def antenna():
    base = (0.36, rear_top(TAIL_Z + 0.45), TAIL_Z + 0.45)
    e = [box(add(base, (X, -0.04), (Z, -0.04)), add(base, (X, 0.04), (Y, 0.05), (Z, 0.04)), "darksteel"),
         beam(add(base, (Y, 0.04)), add(base, (Y, 0.75), (Z, -0.35)), 0.018, 0.018, "steel"),
         box(add(base, (Y, 0.73), (Z, -0.37), (X, -0.018)), add(base, (Y, 0.77), (Z, -0.33), (X, 0.018)), "glow")]
    return no_dent(e)


def rear_lid():
    """The raised rear hull above the deck: its sloped sides, its top climbing
    from the canopy to the tail, the upper back plate and the bulkhead behind
    the pilot. It is the lid's frame: hinged across the tail at deck level, it
    lifts the canopy and the cannon mount with it."""
    y1, yt = CANOPY_Y, rear_top(TAIL_Z)
    r, t = CAN_REAR, TAIL_Z
    e = quad((CAN_TW, y1, r), (-CAN_TW, y1, r), (0.52, yt, t), (-0.52, yt, t), 0.04, "armor", (0.0, 1.0, 0.0))   # top
    for s_ in (1, -1):
        e += quad((s_ * 0.70, DECK_Y, r), (s_ * CAN_TW, y1, r), (s_ * 0.76, DECK_Y, t), (s_ * 0.52, yt, t), 0.04,
                  "armor", (s_ * 1.0, 0.6, 0.0))                                                    # sloped sides
        e.append(beam((s_ * 0.72, DECK_Y + 0.08, r - 0.05), (s_ * 0.775, DECK_Y + 0.08, t + 0.05), 0.03, 0.03, "accent"))
        e.append(box((s_ * 0.74 - 0.03, DECK_Y, t + 0.10), (s_ * 0.74 + 0.03, DECK_Y + 0.03, r - 0.05), "hazard"))
    e += quad((0.76, DECK_Y, t), (-0.76, DECK_Y, t), (0.52, yt, t), (-0.52, yt, t), 0.04, "armor", (0.0, 0.0, -1.0))  # back
    w = HALF_W + 0.06
    e += quad((w, DECK_Y, r), (-w, DECK_Y, r), (CAN_TW, y1, r), (-CAN_TW, y1, r), 0.04, "armor", (0.0, 0.0, 1.0))  # bulkhead
    e.append(beam((0.0, y1 + 0.02, r - 0.05), (0.0, yt + 0.02, t + 0.10), 0.12, 0.012, "accent"))     # top stripe
    for x in (-0.45, 0.45):
        e += prism((x, DECK_Y, t - 0.02), "x", 0.06, 0.22, 8, "steel")                              # tail hinge knuckles
    return e


def air_kit():
    """A compressed-air pack slung on the back below the lid: two magenta
    tanks on a frame, the compressor under them and hoses into the hull."""
    z = TAIL_Z
    e = []
    for x in (-0.52, 0.52):
        e.append(box((x - 0.035, BELLY_Y + 0.10, z - 0.12), (x + 0.035, DECK_Y - 0.06, z), "darksteel"))   # frame rails
    for y in (BELLY_Y + 0.12, DECK_Y - 0.10):
        e.append(box((-0.56, y - 0.03, z - 0.10), (0.56, y + 0.03, z - 0.02), "darksteel"))                 # cross bars
    tz = z - 0.28
    for y in (CHINE_Y - 0.06, CHINE_Y + 0.26):
        e += prism((0.0, y, tz), "x", 0.14, 0.86, 8, "accent")                                             # tanks
        for x in (-0.47, 0.47):
            e += prism((x, y, tz), "x", 0.10, 0.06, 8, "accent")                                           # end caps
        for x in (-0.28, 0.28):
            e += prism((x, y, tz), "x", 0.15, 0.04, 8, "darksteel")                                        # straps
            e.append(box((x - 0.02, y - 0.03, tz + 0.10), (x + 0.02, y + 0.03, z - 0.08), "darksteel"))
        e.append(box((0.38, y + 0.10, tz - 0.04), (0.46, y + 0.17, tz + 0.04), "brass"))                   # valve
    cy = BELLY_Y + 0.22
    e += prism((-0.12, cy, z - 0.24), "x", 0.11, 0.34, 10, "motor")                                        # compressor motor
    for x in (-0.25, -0.15, -0.05):
        e += prism((x, cy, z - 0.24), "x", 0.125, 0.014, 10, "darksteel")
    e += prism((-0.31, cy, z - 0.24), "x", 0.08, 0.03, 10, "hazard")
    e.append(box((0.08, cy - 0.10, z - 0.38), (0.32, cy + 0.12, z - 0.12), "aluminum"))                  # pump head
    for k in range(4):
        e.append(box((0.07, cy - 0.08 + 0.05 * k, z - 0.40), (0.33, cy - 0.065 + 0.05 * k, z - 0.10), "darksteel"))
    e.append(box((0.33, cy - 0.02, z - 0.30), (0.35, cy + 0.03, z - 0.22), "glow"))                      # running light
    # hoses: pump to the tanks, tanks into the hull
    pts = [(0.20, cy + 0.12, z - 0.30), (0.20, CHINE_Y - 0.20, tz - 0.12), (0.10, CHINE_Y - 0.14, tz - 0.10)]
    e += [beam(pts[i], pts[i + 1], 0.035, 0.035, "hose") for i in range(len(pts) - 1)]
    for y, x in ((CHINE_Y - 0.06, -0.40), (CHINE_Y + 0.26, -0.40)):
        e.append(beam((x, y, tz + 0.10), (x, y, z), 0.035, 0.035, "hose"))
    return no_dent(e)


def belly_mount(s_):
    """A belly gun's mount: a turntable under the fuselage and a short armored
    hanger down to the gun's trunnion (s_ 1 left, -1 right)."""
    x, y, z = s_ * LG[0], LG[1], LG[2]
    e = [box((x - 0.14, BELLY_Y - 0.06, z - 0.20), (x + 0.14, BELLY_Y - 0.02, z + 0.20), "darksteel")]   # base plate
    e += prism((x, BELLY_Y - 0.08, z), "y", 0.12, 0.04, 8, "steel")                                    # turntable
    e += prism((x, BELLY_Y - 0.105, z), "y", 0.08, 0.01, 8, "accent")
    for k in (1, -1):
        x0, x1 = sorted((x + k * 0.085, x + k * 0.11))
        e.append(box((x0, y - 0.04, z - 0.10), (x1, BELLY_Y - 0.10, z + 0.10), "gunmetal"))         # yoke arms
    e += prism((x - s_ * 0.13, y, z), "x", 0.045, 0.04, 8, "motor")                                   # elevation motor
    return no_dent(e)


def belly_gun(s_):
    """A belly machine gun: an angular armored receiver, a vented cooling
    jacket and a long barrel, an ammo box on its outer side."""
    x, y, z = s_ * LG[0], LG[1], LG[2]
    e = prism((x, y, z), "x", 0.02, 0.17, 8, "steel")                                                # trunnion pin
    e.append(box((x - 0.075, y - 0.08, z - 0.32), (x + 0.075, y + 0.05, z + 0.28), "gunmetal"))      # receiver
    for k in (1, -1):
        e.append(facet((x + k * 0.075, y - 0.08, z - 0.30), (x + k * 0.075, y - 0.08, z + 0.26),
                       (x + k * 0.09, y + 0.04, z - 0.30), 0.03, "armor", out=(k * 1.0, 0.0, 0.0)))   # side armor
    e.append(facet((x - 0.08, y - 0.08, z + 0.28), (x + 0.08, y - 0.08, z + 0.28), (x - 0.08, y + 0.05, z + 0.22),
                   0.03, "armor", out=(0.0, 0.0, 1.0)))                                                # sloped front
    e.append(beam((x + s_ * 0.105, y - 0.02, z - 0.24), (x + s_ * 0.105, y - 0.02, z + 0.20), 0.012, 0.04, "accent"))
    e += prism((x, y - 0.015, z + 0.62), "z", 0.04, 0.62, 8, "vent")                                 # cooling jacket
    e += prism((x, y - 0.015, z + 1.15), "z", 0.018, 0.48, 8, "darksteel")                           # barrel
    e += prism((x, y - 0.015, z + 1.39), "z", 0.032, 0.07, 8, "steel")                               # muzzle
    e.append(box((x + s_ * 0.085 - 0.05, y - 0.10, z - 0.22), (x + s_ * 0.085 + 0.05, y + 0.02, z + 0.08), "accent"))  # ammo box
    e.append(box((x - 0.02, y - 0.12, z + 0.05), (x + 0.02, y - 0.08, z + 0.16), "darksteel"))       # sight
    e.append(box((x - 0.012, y - 0.11, z + 0.16), (x + 0.012, y - 0.09, z + 0.162), "lamp", faces=("south",)))
    return e


def rail_mount():
    """The cannon's mount: a base on the rear hull's top, an armored pylon up
    to the trunnion and the elevation drives either side."""
    x, y, z = RG
    top = rear_top(z)
    e = [box((x - 0.32, top - 0.02, z - 0.50), (x + 0.32, top + 0.08, z + 0.50), "darksteel")]           # base ring plate
    e += prism((x, top + 0.10, z), "y", 0.30, 0.05, 8, "accent")
    e.append(box((x - 0.17, top + 0.08, z - 0.32), (x + 0.17, y - 0.12, z + 0.32), "gunmetal"))           # pylon
    for s_ in (1, -1):
        e.append(facet((x + s_ * 0.26, top + 0.08, z - 0.36), (x + s_ * 0.26, top + 0.08, z + 0.36),
                       (x + s_ * 0.19, y - 0.14, z - 0.30), 0.04, "armor", out=(s_ * 1.0, 0.2, 0.0)))     # pylon armor
        x0, x1 = sorted((x + s_ * 0.20, x + s_ * 0.27))
        e.append(box((x0, y - 0.30, z - 0.22), (x1, y + 0.14, z + 0.22), "gunmetal"))                     # yokes
        e += prism((x + s_ * 0.30, y, z), "x", 0.15, 0.07, 8, "motor")
        e += prism((x + s_ * 0.345, y, z), "x", 0.09, 0.02, 8, "accent")
    return no_dent(e)


def rail_gun():
    x, y, z = RG
    e = prism(RG, "x", 0.09, 0.40, 8, "steel")
    e.append(box((x - 0.17, y - 0.17, z - 0.75), (x + 0.17, y + 0.19, z + 0.85), "gunmetal"))
    e.append(facet((x - 0.20, y + 0.19, z - 0.75), (x + 0.20, y + 0.19, z - 0.75), (x - 0.20, y + 0.27, z + 0.20), 0.04,
                   "armor", out=(0.0, 1.0, 0.0)))
    for s_ in (1, -1):
        e.append(facet((x + s_ * 0.17, y - 0.17, z - 0.75), (x + s_ * 0.17, y - 0.17, z + 0.85),
                       (x + s_ * 0.21, y + 0.19, z - 0.75), 0.04, "armor", out=(s_ * 1.0, 0.0, 0.0)))
        e.append(beam((x + s_ * 0.215, y + 0.04, z - 0.60), (x + s_ * 0.215, y + 0.04, z + 0.70), 0.012, 0.05, "accent"))
    for k in range(5):
        e += prism((x, y, z + 0.95 + 0.14 * k), "z", 0.16, 0.07, 8, "copper")
    # the scope on top of the breech
    sy = y + 0.40
    e.append(box((x - 0.04, y + 0.25, z + 0.05), (x + 0.04, sy - 0.04, z + 0.15), "darksteel"))
    e.append(box((x - 0.04, y + 0.25, z + 0.55), (x + 0.04, sy - 0.04, z + 0.65), "darksteel"))
    e += prism((x, sy, z + 0.35), "z", 0.07, 0.95, 8, "darksteel")
    e += prism((x, sy, z + 0.85), "z", 0.09, 0.12, 8, "gunmetal")
    e += prism((x, sy, z + 0.915), "z", 0.06, 0.01, 8, "visor")
    return e


def rail_barrel():
    """The long barrel: rails either side of the bore, magenta field rings, a
    laser under it and a muzzle brake at its end."""
    x, y, z = RG
    z0, z1 = z + 1.70, RG_MUZZLE[2]
    e = [box((x - 0.06, y - 0.06, z0), (x + 0.06, y + 0.06, z1 - 0.40), "darksteel")]
    for yy in (0.10, -0.10):
        e.append(box((x - 0.08, y + yy - 0.03, z0 - 0.20), (x + 0.08, y + yy + 0.03, z1 - 0.45), "steel"))
    for k in range(4):
        zz = z0 + 0.4 + k * (z1 - z0 - 1.3) / 3
        e.append(box((x - 0.11, y - 0.15, zz), (x + 0.11, y + 0.15, zz + 0.12), "accent"))
    # muzzle brake: a wider block with side ports
    e.append(box((x - 0.12, y - 0.10, z1 - 0.42), (x + 0.12, y + 0.10, z1), "gunmetal"))
    for k in range(3):
        zz = z1 - 0.36 + 0.11 * k
        e.append(box((x - 0.125, y - 0.06, zz), (x + 0.125, y + 0.06, zz + 0.05), "vent", faces=("east", "west")))
    e.append(box((x - 0.13, y - 0.11, z1 - 0.04), (x + 0.13, y + 0.11, z1 + 0.02), "darksteel"))
    # laser module under the barrel
    lz = z0 + 0.9
    e.append(box((x - 0.03, y - 0.16, lz + 0.05), (x + 0.03, y - 0.09, lz + 0.15), "darksteel"))
    e.append(box((x - 0.06, y - 0.27, lz - 0.05), (x + 0.06, y - 0.16, lz + 0.30), "darksteel"))
    e += prism((x, y - 0.215, lz + 0.31), "z", 0.035, 0.02, 6, "lamp")
    return no_dent(e)


def body() -> list[Part]:
    """The pelvis segment: the fuselage's frame, skin and power pack."""
    out = []
    _add(out, Part("pelvis", "Fuselage frame (keel, cabin tub, leg spars)", "structure", None, "pelvis", PIVOT, 900, 600,
                   "fail", "Cracks: every leg weakens; at 0 the mech is wrecked", shield=["pelvis_armor"], damaged=False),
         chassis())
    _add(out, Part("pelvis_armor", "Fuselage armor (chined sides, nose, tail)", "armor", "pelvis", "pelvis", PIVOT, 180, 380,
                   "detach", "Torn off: the frame takes hits directly"), skin())
    _add(out, Part("power_pack", "Power pack (in the nose)", "power", "pelvis", "pelvis", PIVOT, 280, 200, "fail",
                   "Loses charge with HP: every leg weakens; at 0 the legs barely move", shield=["pelvis_armor"]), power())
    return out


def cabin():
    """The parts on the locked torso segment: the cabin, canopy, deck, sensors
    and the cannon."""
    out = []
    _add(out, Part("torso_frame", "Cabin frame", "structure", "pelvis", "torso", PIVOT, 300, 480, "fail",
                   "Cracks: the cannon's mount shakes loose and aim wanders; at 0 the mech is wrecked",
                   shield=["torso_top"], damaged=False), [box((-0.40, FLOOR_Y - 0.08, CAN_REAR + 0.05), (0.40, FLOOR_Y - 0.05, CAN_FRONT - 0.05), "darksteel")])
    _add(out, Part("torso_top", "Top deck (nose top, spine, sills)", "armor", "torso_frame", "torso", PIVOT, 120, 300,
                   "detach", "Torn off: the cabin and the cannon mount take hits from above"), deck())
    _add(out, Part("hatch", "Canopy (lifts with the rear hull's lid)", "armor", "rear_lid", "lid", LID_PIVOT, 30, 140,
                   "detach", "Shot off: the cabin is open to the sky"), canopy(), LID_PIVOT)
    _add(out, Part("rear_lid", "Rear hull lid (hinged at the tail, lifts the canopy and the cannon)", "armor", "torso_top",
                   "lid", LID_PIVOT, 150, 340, "detach", "Torn off: the cannon mount and the bay under it take hits directly"),
         rear_lid(), LID_PIVOT)
    _add(out, Part("air_kit", "Air kit (compressor and tanks on the back)", "air", "pelvis", "pelvis", PIVOT, 70, 150,
                   "fail", "Ruptures: the legs lose their air assist and step slower"), air_kit())
    side = _add(out, Part("torso_side_l", "Leg spar armor (left)", "armor", "torso_frame", "torso", PIVOT, 60, 220,
                          "detach", "Torn off: the left leg spars take hits directly"),
                [facet((ROOTS["lf"][0] - 0.30, ROOT_Y + 0.26, ROOTS["lh"][1] + 0.30), (ROOTS["lf"][0] - 0.30, ROOT_Y + 0.26, ROOTS["lf"][1] - 0.30),
                       (SIDE_W + 0.05, CHINE_Y + 0.10, ROOTS["lh"][1] + 0.30), 0.04, "armor", out=(1.0, 1.0, 0.0))])
    right = copy.deepcopy(side)
    right.id, right.label = "torso_side_r", side.label.replace("(left)", "(right)")
    right.pivot = (-side.pivot[0], side.pivot[1], side.pivot[2])
    right.elems = mirror_x(side.elems)
    out.append(right)
    _add(out, Part("cockpit", "Cockpit (reclined seat, joysticks, panel)", "interior", "torso_frame", "torso", PIVOT, 60, 120,
                   "fail", "Damaged: the panel flickers; at 0 the pilot flies blind", shield=["hatch", "torso_top"],
                   damaged=False), cockpit())
    _add(out, Part("sensors", "Sensors (nose camera, sensor strip)", "sensor", "torso_frame", "torso", PIVOT, 25, 60, "fail",
                   "Damaged: aim gets sloppy; at 0 no camera", damaged=False), sensors())
    _add(out, Part("ammo_bustle", "Capacitor bank (in the tail, feeds the rail cannon)", "ammo", "torso_frame", "torso", PIVOT, 240, 200,
                   "fail", "Leaks charge with damage: the cannon misfires; at 0 it discharges and the cannon is dead"),
         capacitors())
    _add(out, Part("antenna", "Antenna mast", "sensor", "rear_lid", "lid", PIVOT, 4, 20, "detach",
                   "Shot off: no radio or radar", damaged=False), antenna())
    guns = []
    _add(guns, Part("heavy_mount_c", "Rail cannon mount", "actuator", "torso_frame", "hyaw_c", RG, 90, 220, "fail",
                    "Elevation drives weaken: the cannon lifts slower; at 0 it stays put", damaged=False), rail_mount(), RG)
    _add(guns, Part("heavy_gun_c", "Rail cannon breech", "weapon", "heavy_mount_c", "hgun_c", RG, 260, 240, "detach",
                    "Damaged: slower to charge; shot off with its barrel"), rail_gun(), RG)
    _add(guns, Part("heavy_barrels_c", "Rail cannon barrel", "weapon", "heavy_gun_c", "hgun_c", RG, 180, 160, "detach",
                    "Bent: shots spread; shot off: the cannon cannot fire", damaged=False), rail_barrel(), RG)
    for s_, t in ((1, "l"), (-1, "r")):
        side = "left" if s_ > 0 else "right"
        piv = (s_ * LG[0], LG[1], LG[2])
        _add(guns, Part(f"light_mount_{t}", f"Belly gun mount ({side})", "actuator", "pelvis", f"lyaw_{t}", piv, 25, 80,
                        "detach", "Torn off with its gun", damaged=False), belly_mount(s_), piv)
        _add(guns, Part(f"light_gun_{t}", f"Belly machine gun ({side})", "weapon", f"light_mount_{t}", f"lgun_{t}", piv,
                        45, 100, "detach", "Damaged: jams now and then; shot off: one gun fewer"), belly_gun(s_), piv)
    segments = ["torso", "lid", "hyaw_c", "hgun_c", "lyaw_l", "lyaw_r", "lgun_l", "lgun_r"]
    joints = {"waist": {"pivot": list(WAIST), "axis": "y", "parent": "pelvis", "child": "torso", "range": [0, 0],
                        "label": "Waist (locked)"},
              "lid": {"pivot": list(LID_PIVOT), "axis": "x", "parent": "torso", "child": "lid", "range": [LID_OPEN, 0],
                      "label": "Lid (opens with the hatch)"},
              "trav_hc": {"pivot": list(RG), "axis": "y", "parent": "lid", "child": "hyaw_c", "range": [-20, 20],
                          "label": "Cannon turn"},
              "elev_hc": {"pivot": list(RG), "axis": "x", "parent": "hyaw_c", "child": "hgun_c", "range": [-25, 8],
                          "label": "Cannon"}}
    for s_, t in ((1, "l"), (-1, "r")):
        side = "L" if s_ > 0 else "R"
        piv = [s_ * LG[0], LG[1], LG[2]]
        joints[f"trav_l{t}"] = {"pivot": piv, "axis": "y", "parent": "torso", "child": f"lyaw_{t}",
                                "range": LG_TRAVERSE, "label": f"Belly gun {side} turn"}
        joints[f"elev_l{t}"] = {"pivot": piv, "axis": "x", "parent": f"lyaw_{t}", "child": f"lgun_{t}",
                                "range": LG_RANGE, "label": f"Belly gun {side}"}
    muz = [("heavy", "elev_hc", RG_MUZZLE)] + [("light", f"elev_l{t}", (s_ * LG_MUZZLE[0], LG_MUZZLE[1], LG_MUZZLE[2]))
                                             for s_, t in ((1, "l"), (-1, "r"))]
    return out, guns, segments, joints, muz


# ---------------------------------------------------------------------------
# The walk (real meters) and the collision probes.
# ---------------------------------------------------------------------------

GAIT = dict(W.GAIT)
GAIT.update({
    "legs": 4,
    # the fastest mech: double the sprinter's top speed, quick to turn to the pilot's look
    "crouch": 0.0, "swing": 0.30, "lift": 0.8, "bob": 0.0, "step": 0.90, "settle": 0.30, "lead": 0.5,
    "max_speed": 12.6, "accel": 10.0, "max_turn": 240.0, "turn_accel": 1000.0, "aim_rate": 200.0,
    "pilot_aim_rate": 200.0,
    # the surface under the body and the feet is looked for from probe_up above it to probe_down below;
    # a foot lands at most max_rise off it
    "toe": 0.0, "max_rise": 2.6, "probe_up": 2.2, "probe_down": 2.6, "climb_rate": 3.0,
    "foot_heel": 0.0, "foot_mid": 0.0, "foot_toe": 0.0, "foot_side": 0.0,
    "land_dip": 0.25, "dip_rate": 1.5, "fall_drift": 6.0,
    "kneel_drop": 0.25, "kneel_time": 0.8, "kneel_lift_l": 0.0, "kneel_lift_r": 0.0,
    # piloting: strafes on A/D, jumps high (about 8 m) and pressurizes again
    "agile": 1.0, "strafe": 0.75, "jump_speed": 15.5, "jump_cooldown": 3.0,
    # on a wall it runs at this share of its speed; it tilts its nose toward the pilot's look by this
    # share of the look's elevation, at most tilt_max degrees
    "climb": 0.7, "tilt": 0.4, "tilt_max": 15.0,
    # the legs: long, quick strides (a foot flies at 2.5 times the top speed)
    "trigger_rest": 0.35, "trigger_move": 1.6, "comfort": 3.0, "leg_speed": 31.5, "look_ahead": 0.6,
    "cool_cross": 1.0, "cool_same": 1.0, "uncomfortable": 0.3,
    # its body pitches and rolls toward where its feet stand, at most this far (degrees)
    "lean_max": 25.0,
})

PROBES = (
    [("body", x, y, z) for x in (SIDE_W, -SIDE_W) for y in (BELLY_Y + 0.1, DECK_Y) for z in (TAIL_Z + 0.5, 0.0, NOSE_Z - 0.9)]
    + [("body", 0.0, CHINE_Y, NOSE_Z), ("body", 0.0, CHINE_Y, TAIL_Z), ("body", 0.0, CANOPY_Y, CAN_TOP_F)]
    + [("torso", RG[0], RG[1], z) for z in (1.0, 2.6, RG_MUZZLE[2])]
)


def spider() -> dict:
    leg = build_leg()
    legs = place_legs(leg)
    tparts, guns, tsegs, tjoints, muz = cabin()
    lsegs, ljoints = leg_joints()
    return {
        "name": "spider", "label": "Spider", "folder": "spider/", "spec_dir": "mech/spider", "anims": "spider/",
        "about": "The spider: a long, angular fuselage like a jet's cockpit section on four long legs with high "
                 "knees and blade shins, a rail cannon on its spine.",
        "scale": SCALE, "hip_x": ROOTS["lf"][0], "legs": 4,
        "folders": [("pelvis", body()), ("leg", legs), ("torso", tparts), ("guns", guns)],
        "segments": ["pelvis"] + lsegs + tsegs, "joints": {**ljoints, **tjoints},
        "seat": SEAT, "eye": EYE, "recline": RECLINE, "hips_z": HIPS_Z, "grips": pilot_grips(),
        "gait": GAIT, "gait_lengths": W.GAIT_LENGTHS, "kneel_pose": {}, "probes": PROBES,
        "hatch": (DECK_Y, HATCH_Z), "muzzles": muz, "camera_eye": CAMERA_EYE,
        "tints": [0xE8E8EA, 0xB5185E], "pistons": {}, "ranges": {},
        "spider_legs": legs_data(),
    }
