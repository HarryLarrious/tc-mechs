#!/usr/bin/env python3
"""Generate the mech parts: one resource-pack model per part, plus the part spec.

    python3 pack/src/mech_parts.py

So far this is one leg of the two-legged mech: a digitigrade (reverse-knee)
leg driven by three electric motors (hip, knee, ankle) and three air pistons
(hip, knee, ankle), under bolted armor plates.

Writes:
  pack/assets/mech/models/item/leg/<part>.json   cuboid models (intact, and _damaged)
  pack/assets/mech/items/leg/<part>.json         item definitions (tints, damage state)
  pack/assets/mech/textures/item/mech/<mat>.png  material textures
  mech/leg_parts.json                            the part spec for the game code
  mech/LEG_PARTS.md                              the part table
  tools/viewer/leg_data.js                       the same data for the 3D viewer

Leg frame (meters, 1 m = 1 block): +X left (outboard, for the left leg), +Y
up, +Z forward. Origin on the ground under the hip joint. The right leg will
be the same parts mirrored in X.

The leg is four rigid segments joined by three hinges about X:

  pelvis --hip--> thigh --knee--> shin --ankle--> foot

Every part rides one segment. A part's display matrix is

  mech * segment(pose) * translate(pivot) * rotate(rest)

where segment(pose) = R(hip) for the thigh, R(hip) R(knee) for the shin and
R(hip) R(knee) R(ankle) for the foot, each R a turn about X through that
joint's rest position. Pistons are two parts each, a cylinder and a rod, that
aim at each other ("aim" anim): the cylinder sits on its mount on one
segment and points its +Y at the rod's mount on the next segment, and the rod
does the reverse, so the rod slides in the barrel as the joint turns.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mech_lib import (MODEL_SCALE, NS, ROOT, TINTS, Elem, Part, beam, box, hitbox, no_dent, plate,  # noqa: E402
                      prism, ring_x, to_local, write_models, write_textures)

FOLDER = "leg"

# ---------------------------------------------------------------------------
# Leg geometry (leg frame, meters).
# ---------------------------------------------------------------------------

HIP = (0.0, 3.00, 0.00)
KNEE = (0.0, 1.95, 0.55)
ANKLE = (0.0, 0.62, -0.30)
FOOT_HUB = (0.0, 0.24, 0.02)

SEGMENTS = ("pelvis", "thigh", "shin", "foot")
JOINTS = {"hip": (HIP, "pelvis", "thigh"), "knee": (KNEE, "thigh", "shin"), "ankle": (ANKLE, "shin", "foot")}


def add(p, *terms):
    """p + sum of (vector, scale) terms."""
    out = list(p)
    for v, s in terms:
        for i in range(3):
            out[i] += v[i] * s
    return tuple(out)


def sub(p, q):
    return tuple(a - b for a, b in zip(p, q))


def norm(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def lerp(p, q, t):
    return tuple(a + (b - a) * t for a, b in zip(p, q))


X = (1.0, 0.0, 0.0)
Y = (0.0, 1.0, 0.0)
Z = (0.0, 0.0, 1.0)

L_TH = math.dist(HIP, KNEE)
T_TH = norm(sub(KNEE, HIP))                  # along the thigh, hip to knee
F_TH = (0.0, T_TH[2], -T_TH[1])              # thigh front (forward and up)
L_SH = math.dist(KNEE, ANKLE)
T_SH = norm(sub(ANKLE, KNEE))                # along the shin, knee to ankle
F_SH = (0.0, T_SH[2], -T_SH[1])              # shin front (forward and down)


def th(s, off=0.0, x=0.0):
    """Point on the thigh: s along it from the hip, off toward its front, x sideways."""
    return add(HIP, (T_TH, s), (F_TH, off), (X, x))


def sh(s, off=0.0, x=0.0):
    """Point on the shin: s along it from the knee, off toward its front, x sideways."""
    return add(KNEE, (T_SH, s), (F_SH, off), (X, x))


# Piston mounts: (cylinder end, its segment), (rod end, its segment).
PISTONS = {
    "hip":   (((0.0, 3.30, -0.60), "pelvis"), (th(0.53, -0.22), "thigh")),
    "knee":  ((th(0.45, 0.21, 0.30), "thigh"), (sh(0.48, 0.26, 0.30), "shin")),
    "ankle": ((sh(0.40, -0.20), "shin"), ((0.0, 0.95, -0.62), "foot")),
}
BARREL = 0.6      # barrel length / rest length
ROD = 0.6         # rod length / rest length
EYE = 0.14        # from the cylinder's eye to the bottom of its bore

PARTS: list[Part] = []


def part(p: Part, elems: list[Elem]) -> Part:
    p.pivot = tuple(round(c, 4) for c in p.pivot)
    p.elems = to_local(elems, p.pivot)
    PARTS.append(p)
    return p


def pin(center, length, r=0.03):
    """Joint pin along X with a nut on each end."""
    e = prism(center, "x", r, length, 8, "steel")
    for s in (1, -1):
        e += prism(add(center, (X, s * (length / 2 + 0.012))), "x", r * 1.5, 0.024, 6, "darksteel")
    return e


def clevis(center, toward, depth, gap=0.065, mat="darksteel"):
    """Two cheek plates either side of an eye at `center`, reaching `depth`
    back along `toward` (a unit vector into the part that carries them)."""
    e = []
    for s in (1, -1):
        c = add(center, (X, s * gap))
        e.append(beam(add(c, (toward, -0.07)), add(c, (toward, depth)), 0.03, 0.15, mat))
        e += prism(c, "x", 0.075, 0.03, 8, mat)
    return e


def motor(center, side, radius, length, fins, sides=16):
    """Electric servo motor on the joint axis through `center`, sticking out
    toward `side` (+1 outboard, -1 inboard): reduction ring, finned housing,
    hazard end ring, hub and status light."""
    s = side
    cx = center[0]
    e = []
    x = lambda d: (cx + s * d, center[1], center[2])
    e += prism(x(0.015), "x", radius * 0.9, 0.03, sides, "darksteel")              # reduction ring
    e += prism(x(0.03 + length / 2), "x", radius, length, sides, "motor")           # housing
    for k in range(fins):
        e += prism(x(0.05 + k * (length - 0.04) / max(1, fins - 1)), "x", radius * 1.11, 0.014, sides, "darksteel")
    e += prism(x(0.03 + length - 0.03), "x", radius * 1.01, 0.05, sides, "hazard")  # warning band
    e += prism(x(0.03 + length + 0.015), "x", radius * 0.85, 0.03, sides, "gunmetal")  # end plate
    e += prism(x(0.03 + length + 0.035), "x", radius * 0.5, 0.03, 12, "darksteel")  # end cap
    e += prism(x(0.03 + length + 0.055), "x", radius * 0.22, 0.02, 8, "steel")      # shaft nut
    lx = cx + s * (0.03 + length + 0.031)
    for a in (45, 135, 225, 315):                                                    # status lights
        r = radius * 0.68
        cy, cz = center[1] + r * math.sin(math.radians(a)), center[2] + r * math.cos(math.radians(a))
        e.append(box((lx - 0.004, cy - 0.018, cz - 0.018), (lx + 0.004, cy + 0.018, cz + 0.018), "glow", dent=False))
    return no_dent(e)


# ---------------------------------------------------------------- pelvis
def hip_mount():
    e = [box((-0.30, 3.40, -0.30), (0.30, 3.50, 0.30), "steel", dent=False)]        # mounting flange
    for bx in (-0.24, 0.24):
        for bz in (-0.24, 0.24):
            e += prism((bx, 3.515, bz), "y", 0.03, 0.03, 6, "darksteel", dent=False)  # flange bolts
    for s in (1, -1):
        x0, x1 = sorted((s * 0.18, s * 0.26))
        e.append(box((x0, 3.0, -0.21), (x1, 3.42, 0.21), "gunmetal", dent=False))   # yoke cheek
        e += prism((s * 0.22, HIP[1], HIP[2]), "x", 0.21, 0.08, 12, "gunmetal", dent=False)
    e += prism((-0.30, HIP[1], HIP[2]), "x", 0.15, 0.08, 12, "darksteel", dent=False)  # inboard bearing cap
    e += prism((-0.35, HIP[1], HIP[2]), "x", 0.07, 0.03, 8, "steel", dent=False)
    a, _ = PISTONS["hip"]
    A = a[0]
    e.append(beam((0.0, 3.45, -0.20), add(A, (Y, 0.06), (Z, 0.04)), 0.18, 0.09, "gunmetal", dent=False))  # rear arm
    e += clevis(A, norm(sub((0.0, 3.45, -0.20), A)), 0.16)
    e += pin(A, 0.18)
    part(Part("hip_mount", "Hip mount (flange, yoke, piston anchor)", "structure", None, "pelvis", HIP,
              120, 400, "fail", "Cracks: the whole leg sags and the hip motor loses torque; at 0 the leg is lost",
              damaged=False), e)


def hip_motor():
    e = motor(HIP, 1, 0.30, 0.22, 4)
    # junction box on top
    e.append(box((0.32, 3.28, -0.10), (0.46, 3.38, 0.08), "darksteel", dent=False))
    e.append(beam((0.36, 3.36, -0.06), (0.26, 3.44, -0.06), 0.04, 0.04, "hose", dent=False))
    part(Part("hip_motor", "Hip motor (servo, 4-fin housing)", "actuator", "hip_mount", "pelvis", HIP,
              85, 160, "fail", "Loses torque with HP: slower, shorter strides; at 0 the hip only moves on its piston",
              shield=["hip_guard"], damaged=False), e)


def hip_guard():
    e = [plate((0.14, 3.30, 0.40), (0.80, 0.30, 0.05), "armor", (-12.0, 0.0, 0.0)),   # upper tasset
         plate((0.16, 3.04, 0.45), (0.76, 0.30, 0.05), "armor", (-18.0, 0.0, 0.0)),   # lower tasset
         plate((0.16, 2.897, 0.496), (0.76, 0.04, 0.06), "accent", (-18.0, 0.0, 0.0)),  # trim
         plate((0.42, 3.44, 0.02), (0.36, 0.05, 0.66), "armor", (0.0, 0.0, -16.0)),   # shoulder over the motor
         plate((0.42, 3.474, 0.02), (0.08, 0.012, 0.60), "accent", (0.0, 0.0, -16.0))]  # shoulder stripe
    for x in (-0.18, 0.46):
        e.append(plate((x, 3.38, 0.43), (0.04, 0.04, 0.03), "steel", (-12.0, 0.0, 0.0)))  # bolts
    part(Part("hip_guard", "Hip armor (tasset and motor cap)", "armor", "hip_mount", "pelvis", HIP,
              40, 140, "detach", "Torn off: the hip motor takes hits directly"), e)


def air_tank():
    c = (0.0, 3.585, -0.42)
    e = [box((-0.20, 3.44, -0.50), (0.20, 3.47, -0.30), "darksteel", dent=False)]   # saddle
    e += prism(c, "x", 0.12, 0.50, 12, "accent")                                     # tank
    for s in (1, -1):
        e += prism(add(c, (X, s * 0.27)), "x", 0.085, 0.04, 12, "accent")           # domed ends
        e += prism(add(c, (X, s * 0.14)), "x", 0.128, 0.03, 12, "darksteel", dent=False)  # straps
    e.append(box((-0.05, 3.70, -0.47), (0.07, 3.77, -0.37), "brass", dent=False))    # valve block
    e.append(box((0.10, 3.70, -0.44), (0.15, 3.735, -0.39), "glow", dent=False))     # pressure light
    # air line down to the hip piston's inlet
    a, b = PISTONS["hip"]
    d = norm(sub(b[0], a[0]))
    inlet = add(a[0], (d, 0.17), (X, 0.17))
    pts = [(0.03, 3.70, -0.49), (0.10, 3.62, -0.58), (0.17, 3.50, -0.62), inlet]
    e += [beam(pts[i], pts[i + 1], 0.035, 0.035, "hose", dent=False) for i in range(len(pts) - 1)]
    part(Part("air_tank", "Air tank and valve block", "air", "hip_mount", "pelvis", HIP,
              30, 60, "detach", "Ruptures: every piston loses pressure and the leg can only use its motors",
              shield=["hip_mount"]), e)


# ---------------------------------------------------------------- thigh
def thigh():
    e = prism(HIP, "x", 0.20, 0.34, 12, "darksteel")                                 # hip hub
    e += [beam(th(0.12), th(L_TH - 0.10), 0.24, 0.26, "gunmetal")]                   # core
    for s in (1, -1):
        e.append(beam(th(0.05, 0, s * 0.16), th(L_TH - 0.05, 0, s * 0.16), 0.06, 0.20, "steel"))  # rails
        e += prism(add(KNEE, (X, s * 0.16)), "x", 0.17, 0.08, 12, "darksteel")      # knee clevis
    e.append(beam(th(0.25, -0.15), th(0.85, -0.15), 0.12, 0.04, "darksteel"))        # rear spine
    # hip piston rod mount (rear)
    _, b = PISTONS["hip"]
    e += clevis(b[0], F_TH, 0.16)
    e += pin(b[0], 0.18)
    # knee piston cylinder mount (outboard, front)
    a, _ = PISTONS["knee"]
    s_a = 0.45
    e.append(beam(th(s_a, 0.04, 0.22), th(s_a, 0.25, 0.22), 0.08, 0.12, "darksteel"))  # gusset
    e += pin(a[0], 0.20)
    # power conduit down the inboard side to the knee motor
    e.append(beam(th(0.15, 0.04, -0.20), th(L_TH - 0.22, 0.04, -0.20), 0.05, 0.05, "hose"))
    e.append(beam(th(L_TH - 0.22, 0.04, -0.20), add(KNEE, (Y, 0.22), (X, -0.30)), 0.05, 0.05, "hose"))
    part(Part("thigh", "Thigh frame", "structure", "hip_mount", "thigh", HIP,
              260, 320, "fail", "Bends: the knee runs out of line and the stride shortens; at 0 the leg collapses",
              shield=["thigh_armor"]), e)


def thigh_armor():
    e = [beam(th(0.20, 0.19), th(0.72, 0.19), 0.38, 0.05, "armor"),                 # upper plate
         beam(th(0.64, 0.165), th(1.06, 0.165), 0.34, 0.05, "armor"),               # lower plate
         beam(th(0.24, 0.222), th(1.00, 0.20), 0.07, 0.025, "accent")]              # stripe
    for s in (1, -1):
        e.append(beam(th(0.28, -0.02, s * 0.205), th(0.98, -0.02, s * 0.205), 0.03, 0.24, "armor"))  # side plates
    e.append(beam(th(0.30, 0.218, -0.12), th(0.42, 0.218, -0.12), 0.10, 0.01, "hazard"))  # warning plate
    for s_ in (0.26, 0.66):
        for x in (-0.15, 0.15):
            e += prism(th(s_, 0.218, x), "y", 0.018, 0.012, 6, "steel", dent=False)  # bolt heads (approx)
    part(Part("thigh_armor", "Thigh armor", "armor", "thigh", "thigh", HIP,
              70, 200, "detach", "Torn off: the thigh frame and its knee piston mount take hits directly"), e)


def knee_motor():
    e = motor(KNEE, -1, 0.19, 0.18, 4, sides=12)
    e.append(box((-0.38, KNEE[1] + 0.17, KNEE[2] - 0.08), (-0.25, KNEE[1] + 0.25, KNEE[2] + 0.05), "darksteel",
                 dent=False))                                                        # junction box
    part(Part("knee_motor", "Knee motor (servo)", "actuator", "thigh", "thigh", KNEE,
              55, 130, "fail", "Loses torque with HP; at 0 the knee only moves on its piston"), e)


# ---------------------------------------------------------------- shin
def shin():
    e = prism(KNEE, "x", 0.15, 0.24, 12, "darksteel")                                # knee hub
    e += [beam(sh(0.10), sh(L_SH - 0.10), 0.22, 0.24, "gunmetal")]                   # core
    for s in (1, -1):
        e.append(beam(sh(0.08, 0, s * 0.145), sh(L_SH - 0.06, 0, s * 0.145), 0.05, 0.18, "steel"))  # rails
        e += prism(add(ANKLE, (X, s * 0.155)), "x", 0.14, 0.07, 12, "darksteel")    # ankle clevis
    e.append(beam(sh(0.50, 0.0, 0.0), sh(1.25, 0.0, 0.0), 0.235, 0.16, "vent"))     # vented core panel
    # knee piston rod mount (outboard, front)
    _, b = PISTONS["knee"]
    e.append(beam(sh(0.48, 0.06, 0.22), sh(0.48, 0.30, 0.22), 0.08, 0.12, "darksteel"))  # gusset
    e += pin(b[0], 0.22)
    # ankle piston cylinder mount (rear)
    a, _ = PISTONS["ankle"]
    e += clevis(a[0], F_SH, 0.16)
    e += pin(a[0], 0.18)
    e.append(beam(sh(0.55, -0.13, -0.10), sh(1.35, -0.13, -0.10), 0.04, 0.04, "hose"))  # power line
    part(Part("shin", "Shin frame", "structure", "thigh", "shin", KNEE,
              210, 300, "fail", "Bends: the foot lands out of line; at 0 the leg collapses",
              shield=["shin_armor", "knee_guard"]), e)


def knee_guard():
    e = ring_x(KNEE, 0.20, 0.25, 0.40, 6, "armor", a0=-55, a1=75)                   # rounded knee cap
    e += ring_x(KNEE, 0.25, 0.28, 0.08, 4, "accent", a0=-35, a1=60)                  # center ridge
    for s in (1, -1):
        e += ring_x(add(KNEE, (X, s * 0.185)), 0.16, 0.25, 0.03, 3, "armor", a0=-40, a1=60)  # side lips
    part(Part("knee_guard", "Knee armor", "armor", "shin", "shin", KNEE,
              30, 160, "detach", "Torn off: the knee hub and motor take hits directly"), e)


def shin_armor():
    e = [beam(sh(0.30, 0.17), sh(0.95, 0.17), 0.36, 0.05, "armor"),                # upper greave
         beam(sh(0.88, 0.155), sh(1.42, 0.155), 0.34, 0.05, "armor"),               # lower greave
         beam(sh(0.32, 0.205), sh(1.38, 0.19), 0.06, 0.03, "accent"),               # center ridge
         beam(sh(0.36, 0.197, -0.10), sh(0.52, 0.197, -0.10), 0.10, 0.012, "hazard")]  # warning plate
    for s in (1, -1):
        e.append(beam(sh(0.66, 0.08, s * 0.19), sh(1.28, 0.08, s * 0.19), 0.03, 0.17, "armor"))  # side wings
    part(Part("shin_armor", "Shin armor (greave)", "armor", "shin", "shin", KNEE,
              60, 200, "detach", "Torn off: the shin frame takes hits directly"), e)


def ankle_motor():
    e = motor(ANKLE, -1, 0.14, 0.12, 3, sides=12)
    part(Part("ankle_motor", "Ankle motor (servo)", "actuator", "shin", "shin", ANKLE,
              30, 100, "fail", "Loses torque with HP: the foot slaps down; at 0 the ankle only moves on its piston"), e)


# ---------------------------------------------------------------- foot
TOES = {"c": (0.0, 0.09, 0.84), "l": (0.40, 0.09, 0.66), "r": (-0.40, 0.09, 0.66)}
HEEL = (0.0, 0.08, -0.54)


def toe_root(tip):
    return (tip[0] * 0.30, 0.22, 0.20)


def toe_knuckle(root, tip):
    return add(lerp(root, tip, 0.5), (Y, 0.035))


def foot():
    e = prism(ANKLE, "x", 0.13, 0.24, 12, "darksteel")                              # ankle hub
    e.append(beam(ANKLE, FOOT_HUB, 0.24, 0.22, "gunmetal"))                         # tarsus
    e.append(box((-0.22, 0.12, -0.20), (0.22, 0.32, 0.28), "gunmetal"))             # foot block
    e.append(box((-0.16, 0.32, -0.12), (0.16, 0.36, 0.20), "vent"))                 # top vent
    # heel horn for the ankle piston
    _, b = PISTONS["ankle"]
    B = b[0]
    e.append(beam(ANKLE, lerp(ANKLE, B, 0.70), 0.12, 0.12, "darksteel"))
    e += clevis(B, norm(sub(ANKLE, B)), 0.20)
    e += pin(B, 0.18)
    for tip in TOES.values():
        root = toe_root(tip)
        k = toe_knuckle(root, tip)
        d = norm(sub(tip, root))
        yaw = math.degrees(math.atan2(d[0], d[2]))
        e.append(beam(root, k, 0.17, 0.16, "darksteel"))                            # proximal
        e.append(beam(k, tip, 0.15, 0.14, "darksteel"))                             # distal
        e.append(plate(k, (0.20, 0.13, 0.13), "steel", (0.0, round(yaw, 3), 0.0)))  # knuckle
        e.append(beam(add(tip, (d, -0.05)), add(tip, (d, 0.13), (Y, -0.07)), 0.11, 0.08, "steel"))  # claw
        e.append(plate(add(tip, (d, -0.07), (Y, -0.065)), (0.17, 0.05, 0.24), "rubber",
                       (0.0, round(yaw, 3), 0.0)))                                   # pad
    e.append(beam((0.0, 0.22, -0.16), HEEL, 0.15, 0.13, "darksteel"))               # heel spur
    e.append(beam(add(HEEL, (Z, 0.04)), add(HEEL, (Z, -0.10), (Y, -0.05)), 0.10, 0.07, "steel"))  # heel claw
    e.append(box((-0.09, 0.0, -0.56), (-0.09 + 0.18, 0.05, -0.34), "rubber"))       # heel pad
    e.append(box((-0.20, 0.0, -0.14), (0.20, 0.12, 0.26), "rubber"))                # center pad
    part(Part("foot", "Foot (three toes and a heel spur)", "structure", "shin", "foot", ANKLE,
              150, 260, "fail", "Damaged toes cost grip and balance; at 0 the mech stumbles on every step",
              shield=["foot_armor"]), e)


def foot_armor():
    e = []
    for name, tip in TOES.items():
        root = toe_root(tip)
        k = toe_knuckle(root, tip)
        d = norm(sub(tip, root))
        e.append(beam(add(lerp(root, k, 0.25), (Y, 0.10)), add(k, (Y, 0.10)), 0.21, 0.045, "armor"))   # rear cap
        e.append(beam(add(k, (Y, 0.095), (d, -0.02)), add(tip, (Y, 0.085)), 0.19, 0.045, "armor"))     # front cap
        e.append(beam(add(tip, (Y, 0.085), (d, -0.03)), add(tip, (d, 0.09), (Y, 0.0)), 0.17, 0.04, "armor"))  # nose
        if name == "c":
            e.append(beam(add(lerp(root, k, 0.35), (Y, 0.128)), add(k, (Y, 0.128)), 0.05, 0.02, "accent"))
            e.append(beam(add(k, (Y, 0.122)), add(tip, (Y, 0.112)), 0.05, 0.02, "accent"))
    # instep plate over the front of the tarsus
    t = norm(sub(FOOT_HUB, ANKLE))
    n = (0.0, t[2], -t[1])
    if n[2] < 0:
        n = tuple(-c for c in n)
    e.append(beam(add(ANKLE, (t, 0.08), (n, 0.135)), add(FOOT_HUB, (n, 0.14), (Y, 0.08)), 0.30, 0.04, "armor"))
    e.append(box((-0.24, 0.30, 0.10), (0.24, 0.34, 0.30), "armor"))                 # toe-box cap
    part(Part("foot_armor", "Foot armor (toe caps, instep)", "armor", "foot", "foot", ANKLE,
              35, 150, "detach", "Torn off: the toes take hits directly"), e)


# ---------------------------------------------------------------- pistons
def piston_cyl(L):
    """Air cylinder, local +Y from its eye toward the rod's mount."""
    lc = BARREL * L
    top = 0.09 + lc
    e = prism((0, 0, 0), "x", 0.06, 0.08, 8, "darksteel")                           # eye
    e.append(box((-0.035, 0.0, -0.035), (0.035, 0.10, 0.035), "darksteel"))        # neck
    e += prism((0, 0.115, 0), "y", 0.095, 0.05, 12, "darksteel")                    # base cap
    e += prism((0, (0.14 + top - 0.05) / 2, 0), "y", 0.075, top - 0.05 - 0.14, 12, "aluminum")  # barrel
    e += prism((0, top - 0.025, 0), "y", 0.095, 0.05, 12, "darksteel")              # head cap
    e += prism((0, top + 0.015, 0), "y", 0.045, 0.03, 8, "steel")                  # rod gland
    e += prism((0, top - 0.11, 0), "y", 0.078, 0.04, 12, "hazard")                 # band
    for sx in (-0.072, 0.072):
        for sz in (-0.072, 0.072):
            e.append(beam((sx, 0.10, sz), (sx, top - 0.01, sz), 0.014, 0.014, "steel"))  # tie rods
    e.append(box((0.07, 0.15, -0.025), (0.12, 0.20, 0.025), "brass"))               # inlet port
    e.append(box((0.07, top - 0.08, -0.025), (0.12, top - 0.03, 0.025), "brass"))   # outlet port
    e.append(beam((0.115, top - 0.055, 0.0), (0.115, 0.175, 0.0), 0.03, 0.03, "hose"))  # return line
    e.append(beam((0.12, 0.175, 0.0), (0.17, 0.17, 0.0), 0.035, 0.035, "hose"))     # inlet stub
    return no_dent(e)


def piston_rod(L):
    """Piston rod, local +Y from its eye toward the cylinder's mount."""
    lr = ROD * L
    e = prism((0, 0, 0), "x", 0.055, 0.08, 8, "darksteel")                          # eye
    e.append(box((-0.032, 0.0, -0.032), (0.032, 0.10, 0.032), "steel"))            # rod end
    e += prism((0, 0.11, 0), "y", 0.042, 0.03, 8, "darksteel")                      # wiper collar
    e += prism((0, (0.12 + lr) / 2, 0), "y", 0.03, lr - 0.12, 8, "chrome")          # rod
    return no_dent(e)


def aim_rest(a, b):
    """Rest rotation (about X) that turns local +Y from a toward b."""
    d = sub(b, a)
    return (round(math.degrees(math.atan2(d[2], d[1])), 3), 0.0, 0.0)


def pistons():
    info = {
        "hip": ("hip_mount", "thigh", 22, 90, "Hip piston", "pelvis to thigh"),
        "knee": ("thigh", "shin", 18, 80, "Knee piston", "thigh to shin, outboard"),
        "ankle": ("shin", "foot", 14, 70, "Ankle piston", "shin to heel"),
    }
    for name, ((A, seg_a), (B, seg_b)) in PISTONS.items():
        holder_a, holder_b, mass, hp, label, where = info[name]
        L = math.dist(A, B)
        cyl = f"{name}_piston_cyl"
        part(Part(cyl, f"{label} cylinder ({where})", "actuator", holder_a, seg_a, A, mass, hp, "detach",
                  "Leaks: the joint loses its air assist and moves on its motor alone; broken off with its rod",
                  rest=aim_rest(A, B), anim="aim",
                  links={"to": [round(c, 4) for c in B], "to_segment": seg_b, "rest_length": round(L, 4)}),
             to_local_inv(piston_cyl(L), A))
        part(Part(f"{name}_piston_rod", f"{label} rod", "actuator", cyl, seg_b, B, mass * 0.4, hp, "detach",
                  "Bends: the piston binds and the joint turns slower",
                  rest=aim_rest(B, A), anim="aim", damaged=False,
                  links={"to": [round(c, 4) for c in A], "to_segment": seg_a, "rest_length": round(L, 4)}),
             to_local_inv(piston_rod(L), B))


def to_local_inv(local, pivot):
    """`part()` takes leg-frame elements; these are already local, so shift
    them out to the pivot first (part() shifts them back)."""
    return to_local(local, tuple(-c for c in pivot))


# ---------------------------------------------------------------------------
# Pose math (the viewer and the game do the same).
# ---------------------------------------------------------------------------

def rot_x_about(p, c, deg):
    a = math.radians(deg)
    y, z = p[1] - c[1], p[2] - c[2]
    return (p[0], c[1] + y * math.cos(a) - z * math.sin(a), c[2] + y * math.sin(a) + z * math.cos(a))


def posed(p, seg, pose):
    """Leg-frame point p on segment `seg`, moved to pose {joint: degrees}."""
    order = SEGMENTS.index(seg)
    for j, (piv, _, child) in reversed(list(JOINTS.items())):
        if order >= SEGMENTS.index(child):
            p = rot_x_about(p, piv, pose.get(j, 0.0))
    return p


def piston_ok(name, pose):
    (A, sa), (B, sb) = PISTONS[name]
    L = math.dist(A, B)
    Lp = math.dist(posed(A, sa, pose), posed(B, sb, pose))
    # rod tip must stay between the bottom of the bore and the gland
    return BARREL * L + 0.10 >= Lp - ROD * L >= EYE


def joint_ranges():
    out = {}
    for j, (_, _, child) in JOINTS.items():
        names = [n for n, ((_, sa), (_, sb)) in PISTONS.items() if {sa, sb} == {JOINTS[j][1], JOINTS[j][2]}]
        lo = hi = 0
        while lo > -45 and all(piston_ok(n, {j: lo - 1}) for n in names):
            lo -= 1
        while hi < 45 and all(piston_ok(n, {j: hi + 1}) for n in names):
            hi += 1
        out[j] = [lo, hi]
    return out


# ---------------------------------------------------------------------------
# Build.
# ---------------------------------------------------------------------------

def build():
    hip_mount(); hip_motor(); hip_guard(); air_tank()
    thigh(); thigh_armor(); knee_motor()
    shin(); knee_guard(); shin_armor(); ankle_motor()
    foot(); foot_armor()
    pistons()


def write_table(spec):
    lines = ["# Leg parts", "",
             "Generated by `pack/src/mech_parts.py` from the same data as the models. Do not edit.", "",
             f"{len(spec['parts'])} parts, {spec['total_mass']} kg in total (one leg).", "",
             "| Part | Group | Parent | Segment | Mass (kg) | HP | Breaks | Moves | Shielded by | Effect |",
             "| --- | --- | --- | --- | ---: | ---: | --- | --- | --- | --- |"]
    for p in spec["parts"]:
        lines.append(f"| `{p['id']}` | {p['group']} | {p['parent'] or '-'} | {p['segment']} | {p['mass']:g} | "
                     f"{p['hp']} | {'off' if p['on_break'] == 'detach' else 'in place'} | {p['anim']} | "
                     f"{', '.join(p['shield']) or '-'} | {p['effect']} |")
    (ROOT / "mech/LEG_PARTS.md").write_text("\n".join(lines) + "\n")


def main():
    build()
    ids = {p.id for p in PARTS}
    for p in PARTS:
        if p.parent and p.parent not in ids:
            raise SystemExit(f"{p.id}: unknown parent {p.parent}")
        for s in p.shield:
            if s not in ids:
                raise SystemExit(f"{p.id}: unknown shield {s}")
    used = set()
    from mech_lib import MATERIALS
    for p in PARTS:
        for e in p.elems:
            used.add(e.mat)
            if p.damaged:
                used.add(MATERIALS[e.mat].get("dmg", e.mat))
    textures = write_textures(used)
    models = write_models(FOLDER, PARTS)
    ranges = joint_ranges()
    spec = {
        "frame": "+X left (outboard), +Y up, +Z forward; meters; origin on the ground under the hip",
        "model_scale": MODEL_SCALE,
        "placement": "item display at the mech origin; matrix = mech * segment(pose) * translate(pivot) * "
                     "rotate_xyz(rest). aim parts instead sit at their posed pivot with local +Y turned toward "
                     "their posed links.to point. The pack scales the half-size models back to 1:1.",
        "segments": list(SEGMENTS),
        "joints": {j: {"pivot": list(piv), "axis": "x", "parent": pa, "child": ch, "range": ranges[j]}
                   for j, (piv, pa, ch) in JOINTS.items()},
        "anims": {"fixed": "rigid with its segment",
                  "aim": "at its pivot on its segment, local +Y aimed at links.to on links.to_segment (pistons)"},
        "tints": {"0": "armor paint", "1": "accent (stripes, trims, air tank)"},
        "tint_defaults": ["#%06x" % t["default"] for t in TINTS],
        "damage_state": "custom_model_data string 0 = \"damaged\" swaps to the _damaged model",
        "total_mass": round(sum(p.mass for p in PARTS), 1),
        "parts": [{
            "id": p.id, "label": p.label, "group": p.group, "parent": p.parent, "segment": p.segment,
            "item_model": f"{NS}:{FOLDER}/{p.id}", "pivot": list(p.pivot), "rest": list(p.rest), "anim": p.anim,
            "mass": p.mass, "hp": p.hp, "on_break": p.on_break, "effect": p.effect, "shield": p.shield,
            "damaged_model": p.damaged, "hitbox": hitbox(p.elems), "links": p.links,
            "elements": len(p.elems),
        } for p in PARTS],
    }
    (ROOT / "mech").mkdir(exist_ok=True)
    (ROOT / "mech/leg_parts.json").write_text(json.dumps(spec, indent=1) + "\n")
    write_table(spec)
    viewer = ROOT / "tools/viewer"
    viewer.mkdir(parents=True, exist_ok=True)
    (viewer / "leg_data.js").write_text("// Generated by pack/src/mech_parts.py. Do not edit.\nwindow.MECH = "
                                        + json.dumps({"spec": spec, "models": models, "textures": textures}) + ";\n")
    n_el = sum(len(p.elems) for p in PARTS)
    print(f"{len(PARTS)} parts, {n_el} elements, {len(textures)} textures, {spec['total_mass']} kg")
    for name, ((A, _), (B, _)) in PISTONS.items():
        print(f"  {name} piston: rest length {math.dist(A, B):.3f} m")
    for j, r in ranges.items():
        print(f"  {j}: {r[0]}..{r[1]} deg")


if __name__ == "__main__":
    main()
