#!/usr/bin/env python3
"""Generate the mech parts: one resource-pack model per part, plus the part spec.

    python3 pack/src/mech_parts.py

The two-legged mech: an armored turret torso with separate heavy and light
guns (mech_torso.py) that turns on the pelvis (mech_pelvis.py), on two
digitigrade (reverse-knee) legs. Each leg is driven
by three electric motors (hip, knee, ankle) and three air pistons (hip, knee,
ankle), under bolted armor plates. The leg is designed once, as the left leg,
in its own leg frame; the right leg is the same parts mirrored in X.

Writes:
  pack/assets/mech/models/item/<folder>/<part>.json       cuboid models (intact, and _damaged);
                                                          folders: leg, pelvis, torso, guns
  pack/assets/mech/items/<folder>/<part>.json             item definitions (tints, damage state)
  pack/assets/mech/textures/item/mech/<mat>.png           material textures
  mech/parts.json                                         the part spec for the game code
  mech/PARTS.md                                           the part table
  tools/viewer/mech_data.js                               the same data for the 3D viewer
  tc/mech_data.tc                                         segments, joints and parts for the plot code

Mech frame (meters, 1 m = 1 block): +X left, +Y up, +Z forward. Origin on the
ground midway between the hips. The hips are at x = +/-HIP_X.

Leg frame (where the leg below is drawn): the same axes, origin on the ground
under the hip, +X outboard. Left leg: mech = leg + HIP_X. Right leg: mech =
-(leg + HIP_X), with every model mirrored.

Each leg is three rigid segments hung off the pelvis by three hinges about X:

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

import copy
import hashlib
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mech_lib import (GAIT, GAIT_LENGTHS, MATERIALS, MODEL_SCALE, NS, ROOT, TINTS, Elem, Part, beam, box, hitbox,  # noqa: E402
                      KNEEL_POSE, MECH_SCALE, PROBES, gait_scaled, mirror_x, no_dent, plate, prism, ring_x, scale_part, to_local,
                      write_models, write_textures)
from mech_pelvis import pelvis_parts  # noqa: E402
from mech_torso import (CAMERA_EYE, EYE as PILOT_EYE, HATCH_Z, HIPS_Z, RECLINE, ROOF_Y, SEAT,  # noqa: E402
                        muzzles, pilot_grips, torso_parts)  # noqa: E402
from mech_pilot import timeline, write_pilot  # noqa: E402

HIP_X = 0.75      # hip joint offset from the centerline (mech frame, before MECH_SCALE)
SIDES = {"l": (1, "left"), "r": (-1, "right")}

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
JOINT_CAP = {"hip": 105, "knee": 75, "ankle": 75}  # leg joints never turn further than this (degrees),
                                                   # even where the pistons would (the hip to 105 for the kneel)
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
TOE_HINGE_Z = 0.30     # toe plate hinge line (across the foot)
HEEL_HINGE_Z = -0.42   # heel plate hinge line


def foot():
    """A broad, flat stomper: a sole frame with a hinged toe plate and heel
    plate, each sprung by a pair of dampers, on rubber tread pads."""
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
    # sole frame, toe plate and heel plate
    e.append(box((-0.30, 0.07, HEEL_HINGE_Z), (0.30, 0.15, TOE_HINGE_Z), "darksteel"))
    e.append(box((-0.32, 0.06, TOE_HINGE_Z + 0.02), (0.32, 0.17, 0.66), "darksteel"))
    e.append(box((-0.28, 0.06, -0.60), (0.28, 0.17, HEEL_HINGE_Z - 0.02), "darksteel"))
    for z, w in ((TOE_HINGE_Z, 0.70), (HEEL_HINGE_Z, 0.62)):
        e += prism((0.0, 0.12, z), "x", 0.055, w, 10, "steel")                       # hinge barrels
        for x in (-0.20, 0.0, 0.20):
            e += prism((x, 0.12, z), "x", 0.065, 0.08, 10, "darksteel")              # hinge knuckles
    for x0, x1 in ((-0.31, -0.02), (0.02, 0.31)):                                    # rubber tread pads
        e.append(box((x0, 0.0, TOE_HINGE_Z + 0.03), (x1, 0.06, 0.64), "rubber"))
        e.append(box((x0 + 0.02, 0.0, -0.40), (x1 - 0.02, 0.07, 0.28), "rubber"))
        e.append(box((x0 + 0.04, 0.0, -0.58), (x1 - 0.04, 0.06, HEEL_HINGE_Z - 0.03), "rubber"))
    # damper pairs from the foot block to the toe and heel plates
    for s in (1, -1):
        x = s * 0.37                                                                   # outside the armor
        for top, mid, bot in (((x, 0.33, 0.04), (x, 0.24, 0.30), (x, 0.13, 0.50)),
                              ((x, 0.31, -0.14), (x, 0.23, -0.36), (x, 0.13, -0.52))):
            e.append(beam(top, mid, 0.07, 0.07, "darksteel"))                        # damper body
            e.append(beam(mid, bot, 0.03, 0.03, "chrome"))                            # damper rod
            lx0, lx1 = sorted((s * 0.27, s * 0.41))
            e.append(box((lx0, bot[1] - 0.04, bot[2] - 0.04), (lx1, bot[1] + 0.03, bot[2] + 0.04), "steel"))  # lower lug
        x0, x1 = sorted((s * 0.22, s * 0.41))
        e.append(box((x0, 0.26, -0.18), (x1, 0.36, 0.08), "darksteel"))               # upper damper lugs
    e.append(box((-0.10, 0.19, 0.28), (0.10, 0.22, 0.285), "glow", faces=("south",)))  # foot light
    part(Part("foot", "Foot (sole, hinged toe and heel plates, dampers)", "structure", "shin", "foot", ANKLE,
              150, 260, "fail", "Damaged dampers and plates cost grip and balance; at 0 the mech stumbles on every step",
              shield=["foot_armor"]), e)


def foot_armor():
    e = [beam((0.0, 0.205, TOE_HINGE_Z + 0.02), (0.0, 0.17, 0.68), 0.68, 0.05, "armor"),   # toe cap
         beam((0.0, 0.19, 0.68), (0.0, 0.06, 0.745), 0.66, 0.05, "armor"),                 # toe nose
         beam((0.0, 0.20, HEEL_HINGE_Z - 0.01), (0.0, 0.15, -0.62), 0.58, 0.05, "armor"),  # heel guard
         beam((0.0, 0.15, -0.62), (0.0, 0.06, -0.66), 0.56, 0.05, "armor")]                # heel bevel
    for x in (-0.20, 0.20):
        e.append(beam((x, 0.233, TOE_HINGE_Z + 0.05), (x, 0.20, 0.66), 0.06, 0.012, "accent"))  # stripes
        for z in (0.40, 0.60):
            e.append(box((x + 0.07, 0.225 - (z - 0.32) * 0.1, z - 0.02), (x + 0.11, 0.24 - (z - 0.32) * 0.1, z + 0.02),
                         "steel"))                                                       # bolts
    n = norm((0.0, 0.065, 0.13))                                                         # toe nose outward normal
    e.append(beam(add((0.0, 0.165, 0.692), (n, 0.028)), add((0.0, 0.085, 0.732), (n, 0.028)), 0.40, 0.008, "hazard"))
    for s in (1, -1):
        x0, x1 = sorted((s * 0.22, s * 0.245))
        e.append(box((x0, 0.15, -0.20), (x1, 0.26, 0.26), "armor"))                     # side plates
    # instep plate over the front of the tarsus
    t = norm(sub(FOOT_HUB, ANKLE))
    n = (0.0, t[2], -t[1])
    if n[2] < 0:
        n = tuple(-c for c in n)
    e.append(beam(add(ANKLE, (t, 0.08), (n, 0.135)), add(FOOT_HUB, (n, 0.14), (Y, 0.08)), 0.30, 0.04, "armor"))
    e.append(box((-0.24, 0.30, 0.10), (0.24, 0.34, 0.30), "armor"))                 # foot block cap
    part(Part("foot_armor", "Foot armor (toe cap, heel guard, side plates)", "armor", "foot", "foot", ANKLE,
              45, 170, "detach", "Torn off: the toe and heel plates and the dampers take hits directly"), e)


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


def pistons(table=None, add_part=None, mass_k=1.0, hp_k=1.0):
    """The air pistons in `table` (default the walker's), each a cylinder and
    a rod, added with `add_part` (default part())."""
    table, add_part = table or PISTONS, add_part or part
    info = {
        "hip": ("hip_mount", "thigh", 22, 90, "Hip piston", "pelvis to thigh"),
        "knee": ("thigh", "shin", 18, 80, "Knee piston", "thigh to shin, outboard"),
        "ankle": ("shin", "foot", 14, 70, "Ankle piston", "shin to heel"),
    }
    for name, ((A, seg_a), (B, seg_b)) in table.items():
        holder_a, holder_b, mass, hp, label, where = info[name]
        mass, hp = round(mass * mass_k, 1), round(hp * hp_k)
        L = math.dist(A, B)
        cyl = f"{name}_piston_cyl"
        add_part(Part(cyl, f"{label} cylinder ({where})", "actuator", holder_a, seg_a, A, mass, hp, "detach",
                  "Leaks: the joint loses its air assist and moves on its motor alone; broken off with its rod",
                  rest=aim_rest(A, B), anim="aim",
                  links={"to": [round(c, 4) for c in B], "to_segment": seg_b, "rest_length": round(L, 4)}),
             to_local_inv(piston_cyl(L), A))
        add_part(Part(f"{name}_piston_rod", f"{label} rod", "actuator", cyl, seg_b, B, mass * 0.4, hp, "detach",
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


def rot_z_about(p, c, deg):
    a = math.radians(deg)
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + x * math.cos(a) - y * math.sin(a), c[1] + x * math.sin(a) + y * math.cos(a), p[2])


def posed(p, seg, pose, joints=None, segments=SEGMENTS):
    """Leg-frame point p on segment `seg`, moved to pose {joint: degrees}.
    A joint is (pivot, parent, child) turning about X, or (pivot, parent,
    child, "z") turning about Z; segments are in order from the pelvis."""
    joints = joints or JOINTS
    order = segments.index(seg)
    for j, v in reversed(list(joints.items())):
        piv, child = v[0], v[2]
        if order >= segments.index(child):
            rot = rot_z_about if len(v) > 3 and v[3] == "z" else rot_x_about
            p = rot(p, piv, pose.get(j, 0.0))
    return p


def piston_ok(name, pose, pistons=None, joints=None, segments=SEGMENTS):
    (A, sa), (B, sb) = (pistons or PISTONS)[name]
    L = math.dist(A, B)
    Lp = math.dist(posed(A, sa, pose, joints, segments), posed(B, sb, pose, joints, segments))
    # rod tip must stay between the bottom of the bore and the gland
    return BARREL * L + 0.10 >= Lp - ROD * L >= EYE


def joint_ranges(pistons=None, joints=None, caps=None, segments=SEGMENTS, piston_joint=None):
    """Each leg joint's range (degrees): as far as its pistons allow, within its
    cap. A piston works the joint between its two segments, or the one
    `piston_joint` names for it."""
    pistons, joints, caps = pistons or PISTONS, joints or JOINTS, caps or JOINT_CAP
    out = {}
    for j, v in joints.items():
        pa, ch = v[1], v[2]
        names = [n for n, ((_, sa), (_, sb)) in pistons.items()
                 if (piston_joint or {}).get(n, None) == j or (not piston_joint and {sa, sb} == {pa, ch})]
        ok = lambda a: all(piston_ok(n, {j: a}, pistons, joints, segments) for n in names)
        lo = hi = 0
        while lo > -caps[j] and ok(lo - 1):
            lo -= 1
        while hi < caps[j] and ok(hi + 1):
            hi += 1
        out[j] = [lo, hi]
    return out


# ---------------------------------------------------------------------------
# Build.
# ---------------------------------------------------------------------------

def build_leg():
    hip_mount(); hip_motor(); hip_guard(); air_tank()
    thigh(); thigh_armor(); knee_motor()
    shin(); knee_guard(); shin_armor(); ankle_motor()
    foot(); foot_armor()
    pistons()


def place_leg(tag: str, parts: list[Part] | None = None, hip_x: float = HIP_X) -> list[Part]:
    """The leg-frame parts (default the walker's) as the left or right leg in
    the mech frame, with the hips at x = +/-hip_x."""
    s, name = SIDES[tag]
    seg = lambda g: g if g == "pelvis" else f"{g}_{tag}"
    mx = lambda p: (s * (p[0] + hip_x), p[1], p[2])
    out = []
    for p in (PARTS if parts is None else parts):
        q = copy.deepcopy(p)
        q.id = f"{p.id}_{tag}"
        q.label = f"{p.label} ({name})"
        q.parent = f"{p.parent}_{tag}" if p.parent else "pelvis"
        q.segment = seg(p.segment)
        q.pivot = tuple(round(c, 4) for c in mx(p.pivot))
        q.shield = [f"{x}_{tag}" for x in p.shield]
        if p.links:
            q.links = dict(p.links, to=[round(c, 4) for c in mx(p.links["to"])], to_segment=seg(p.links["to_segment"]))
        if s < 0:
            q.elems = mirror_x(p.elems)
        out.append(q)
    return out


def leg_joints(ranges: dict, hip_x: float, joints: dict | None = None, seg_names=SEGMENTS) -> tuple[list, dict]:
    """The pelvis and both legs' segments, and their joints (mech frame). A
    joint about Z is mirrored on the right leg, so its range flips there (the
    same angle swings both legs outward)."""
    joints = joints or JOINTS
    segments = ["pelvis"]
    out = {}
    for tag, (s, _) in SIDES.items():
        segments += [f"{g}_{tag}" for g in seg_names[1:]]
        for j, v in joints.items():
            piv, pa, ch = v[:3]
            axis = v[3] if len(v) > 3 else "x"
            lo, hi = ranges[j]
            out[f"{j}_{tag}"] = {
                "pivot": [round(s * (piv[0] + hip_x), 4), piv[1], piv[2]], "axis": axis,
                "parent": pa if pa == "pelvis" else f"{pa}_{tag}", "child": f"{ch}_{tag}",
                "range": [lo, hi] if axis == "x" or s > 0 else [-hi, -lo],
                "label": f"{j.replace('_', ' ').capitalize()} {tag.upper()}"}
    return segments, out


def write_table(spec, path: Path, title: str):
    lines = [f"# {title} parts", "",
             "Generated by `pack/src/mech_parts.py` from the same data as the models. Do not edit.", "",
             f"{len(spec['parts'])} parts, {spec['total_mass']} kg in total.", "",
             "| Part | Group | Parent | Segment | Mass (kg) | HP | Breaks | Moves | Shielded by | Effect |",
             "| --- | --- | --- | --- | ---: | ---: | --- | --- | --- | --- |"]
    for p in spec["parts"]:
        lines.append(f"| `{p['id']}` | {p['group']} | {p['parent'] or '-'} | {p['segment']} | {p['mass']:g} | "
                     f"{p['hp']} | {'off' if p['on_break'] == 'detach' else 'in place'} | {p['anim']} | "
                     f"{', '.join(p['shield']) or '-'} | {p['effect']} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def tc_num(v: float) -> str:
    v = round(v, 3)
    if v == 0:
        return "0"
    return f"{v:g}"


def rest_cols(rest) -> list[float]:
    """Columns of rotate_xyz(rest) (Minecraft's Rz * Ry * Rx), flattened:
    x column, y column, z column."""
    rx, ry, rz = (math.radians(a) for a in rest)
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
    Ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    Rz = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]
    mul = lambda A, B: [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    R = mul(Rz, mul(Ry, Rx))
    return [R[i][j] for j in range(3) for i in range(3)]


# ---------------------------------------------------------------------------
# Mech types. Each type is built in its own modules and described by a dict
# (see walker()); everything after that is the same for every type.
# ---------------------------------------------------------------------------

def walker() -> dict:
    """The walker: the heavy two-legged mech (this file, mech_pelvis.py and
    mech_torso.py)."""
    build_leg()
    torso, guns, torso_segs, torso_joints = torso_parts()
    ranges = joint_ranges()
    segments, joints = leg_joints(ranges, HIP_X)
    return {
        "name": "walker", "label": "Walker", "folder": "", "spec_dir": "mech", "anims": "",
        "about": "The walker: a heavy turret on two digitigrade legs, two rotary cannons and two roof machine guns.",
        "scale": MECH_SCALE, "hip_x": HIP_X,
        "folders": [("pelvis", pelvis_parts(HIP_X)), ("leg", place_leg("l") + place_leg("r")), ("torso", torso),
                    ("guns", guns)],
        "segments": segments + torso_segs, "joints": {**joints, **torso_joints},
        "seat": SEAT, "eye": PILOT_EYE, "recline": RECLINE, "hips_z": HIPS_Z, "grips": pilot_grips(),
        "gait": GAIT, "gait_lengths": GAIT_LENGTHS, "kneel_pose": KNEEL_POSE, "probes": PROBES,
        "hatch": (ROOF_Y, HATCH_Z), "muzzles": muzzles(), "camera_eye": CAMERA_EYE,
        "tints": [t["default"] for t in TINTS], "pistons": PISTONS, "ranges": ranges,
    }


def all_types() -> list[dict]:
    """Every mech type, in game order (the game's type numbers start at 1)."""
    from mech_sprinter import sprinter
    from mech_spider import spider
    return [walker(), sprinter(), spider()]


def pilot_path(t: dict, name: str) -> list:
    """A pilot animation's timeline (mech_pilot.py, from mech/animations/<anims><name>.json)."""
    k = t["scale"]
    return timeline(t["anims"] + name, tuple(c * k for c in t["seat"]), t["recline"], t["hips_z"],
                    [tuple(c * k for c in g) for g in t["grips"]])


def guns_of(t: dict) -> list:
    """The guns as (kind, elevation joint, muzzle (design units), traverse joint, side)."""
    out = []
    for kind, joint, pt in t["muzzles"]:
        out.append((kind, joint, pt, joint.replace("elev_", "trav_"), joint[-1]))
    return out


def make_spec(t: dict, folder_of: dict) -> dict:
    """The part spec of type t (mech/parts.json for the walker)."""
    K = t["scale"]
    allp = [p for _, ps in t["folders"] for p in ps]
    joints = copy.deepcopy(t["joints"])
    for j in joints.values():
        j["pivot"] = [round(c * K, 4) for c in j["pivot"]]
    return {
        "type": t["name"], "label": t["label"], "about": t["about"],
        "frame": "+X left, +Y up, +Z forward; meters (scaled); origin on the ground midway between the hips",
        "model_scale": MODEL_SCALE,
        "placement": "item display at the mech origin; matrix = mech * segment(pose) * translate(pivot) * "
                     "rotate_xyz(rest). aim parts instead sit at their posed pivot with local +Y turned toward "
                     "their posed links.to point. The pack scales the half-size models back to 1:1.",
        "scale": K,
        "hip_x": round(t["hip_x"] * K, 4),
        "cockpit_seat": [round(c * K, 4) for c in t["seat"]],
        "cockpit_eye": [round(c * K, 4) for c in t["eye"]],
        "cockpit_recline": t["recline"],
        "gait": gait_scaled(t["gait"], K, t["gait_lengths"]),
        "kneel_pose": t["kneel_pose"],
        "board_path": pilot_path(t, "board"),
        "exit_path": pilot_path(t, "exit"),
        "probes": [[f, round(x * K, 4), round(y * K, 4), round(z * K, 4)] for f, x, y, z in t["probes"]],
        "hatch_center": [0, round(t["hatch"][0] * K, 4), round(t["hatch"][1] * K, 4)],
        "camera_eye": [round(c * K, 4) for c in t["camera_eye"]],
        "guns": [{"kind": k, "elevation": j, "traverse": tj, "side": sd, "muzzle": [round(c * K, 4) for c in pt]}
                 for k, j, pt, tj, sd in guns_of(t)],
        "legs": t.get("legs", 2),
        "spider_legs": [{"leg": n, "side": sd, "yaw": yj, "femur": fj, "tibia": tj, "foot": [round(c * K, 4) for c in ft],
                         "home": [round(c * K, 4) for c in hm]} for n, sd, yj, fj, tj, ft, hm in t.get("spider_legs", [])],
        "segments": t["segments"],
        "joints": joints,
        "anims": {"fixed": "rigid with its segment",
                  "aim": "at its pivot on its segment, local +Y aimed at links.to on links.to_segment (pistons)",
                  "spin_z": "rigid with its segment, then turned about its own local Z (heavy gun barrels)",
                  "hinge_x": "rigid with its segment, then turned about its own local X at its pivot (the "
                             "roof hatch, hinged at its rear edge; negative opens it)"},
        "tints": {"0": "armor paint", "1": "accent (stripes, trims, air tanks)"},
        "tint_defaults": ["#%06x" % c for c in t["tints"]],
        "damage_state": "custom_model_data string 0 = \"damaged\" swaps to the _damaged model",
        "total_mass": round(sum(p.mass for p in allp), 1),
        "parts": [{
            "id": p.id, "label": p.label, "group": p.group, "parent": p.parent, "segment": p.segment,
            "item_model": f"{NS}:{folder_of[p.id]}/{p.id}", "pivot": list(p.pivot), "rest": list(p.rest),
            "anim": p.anim, "mass": p.mass, "hp": p.hp, "on_break": p.on_break, "effect": p.effect,
            "shield": p.shield, "damaged_model": p.damaged, "hitbox": hitbox(p.elems), "links": p.links,
            "elements": len(p.elems),
        } for p in allp],
    }


def tc_type_funcs(n: str, spec: dict) -> str:
    """The data functions of one type for the plot code, named n + what they
    hold (walkerSegData, ...); mech_data.tc's mech* functions pick the
    current type's."""
    segs = spec["segments"]
    sidx = {s: i + 1 for i, s in enumerate(segs)}
    joint_of = {j["child"]: (name, j) for name, j in spec["joints"].items()}
    seg_rows = []
    for s in segs:
        if s not in joint_of:
            seg_rows.append(f'"{s} 0 - - 0 0 0 0 0"')
            continue
        name, j = joint_of[s]
        vals = " ".join(tc_num(v) for v in j["pivot"] + j["range"])
        seg_rows.append(f'"{s} {sidx[j["parent"]]} {name} {j["axis"]} {vals}"')
    part_rows = []
    for p in spec["parts"]:
        anim = p["anim"]
        nums = [*p["pivot"], *rest_cols(p["rest"])]
        to = p["links"].get("to") if anim == "aim" else None
        tseg = sidx[p["links"]["to_segment"]] if to else 0
        nums += to if to else [0, 0, 0]
        part_rows.append(f'"{p["id"]} {p["item_model"]} {sidx[p["segment"]]} {anim} '
                         + " ".join(tc_num(v) for v in nums[:12]) + f" {tseg} "
                         + " ".join(tc_num(v) for v in nums[12:]) + '"')
    pidx = {q["id"]: i + 1 for i, q in enumerate(spec["parts"])}
    dmg_rows = []
    for q in spec["parts"]:
        hb = q["hitbox"]
        dmg_rows.append(f'"{q["group"]} {q["hp"]} {1 if q["on_break"] == "detach" else 0} {1 if q["damaged_model"] else 0} '
                        f'{pidx.get(q["parent"], 0)} ' + " ".join(tc_num(v) for v in hb[0] + hb[1]) + '"')
    ind = ",\n        "
    v = lambda c: "vec(" + ", ".join(tc_num(x) for x in c) + ")"
    guns = ", ".join(f'["{g["kind"]}", "{g["elevation"]}", {v(g["muzzle"])}, "{g["traverse"]}", "{g["side"]}"]'
                     for g in spec["guns"])
    return (
        f"// ---------------------------------------------------------------- {spec['label']}\n\n"
        f"function {n}SegData(): list {{\n    return [\n        " + ind.join(seg_rows) + "\n    ];\n}\n\n"
        f"function {n}SegCount(): num {{\n    return {len(segs)};\n}}\n\n"
        f"function {n}PartData(): list {{\n    return [\n        " + ind.join(part_rows) + "\n    ];\n}\n\n"
        f"function {n}PartCount(): num {{\n    return {len(part_rows)};\n}}\n\n"
        f"function {n}PartDamage(): list {{\n    return [\n        " + ind.join(dmg_rows) + "\n    ];\n}\n\n"
        f"function {n}Scale(): num {{\n    return {tc_num(spec['scale'])};\n}}\n\n"
        f"function {n}Gait(): dict {{\n    return {{"
        + ", ".join(f"{k_}: {tc_num(x)}" for k_, x in spec["gait"].items()) + "};\n}\n\n"
        f"function {n}Probes(): list {{\n    return [\n        "
        + ind.join(f'"{f} {tc_num(x)} {tc_num(y)} {tc_num(z)}"' for f, x, y, z in spec["probes"])
        + "\n    ];\n}\n\n"
        f"function {n}KneelPose(): dict {{\n    return {{"
        + ", ".join(f"{k_}: {tc_num(x)}" for k_, x in spec["kneel_pose"].items()) + "};\n}\n\n"
        f"function {n}HatchCenter(): vec {{\n    return {v(spec['hatch_center'])};\n}}\n\n"
        f"function {n}Muzzles(): list {{\n    return [{guns}];\n}}\n\n"
        f"function {n}CameraEye(): vec {{\n    return {v(spec['camera_eye'])};\n}}\n\n"
        f"function {n}CockpitSeat(): vec {{\n    return {v(spec['cockpit_seat'])};\n}}\n\n"
        f"function {n}Legs(): list {{\n    return ["
        + ", ".join(f'"{l["leg"]} {l["side"]} {l["yaw"]} {l["femur"]} {l["tibia"]} ' + " ".join(tc_num(c) for c in l["foot"] + l["home"]) + '"'
                    for l in spec["spider_legs"]) + "];\n}\n\n"
        f"function {n}DefaultColors(): list {{\n    return ["
        + ", ".join(f"0x{c[1:].upper()}" for c in spec["tint_defaults"]) + "];\n}\n\n"
    )


# The data functions every type has: (name, type, what it holds).
TC_FUNCS = [
    ("SegData", "list", "The mech's segments in order (a parent always comes before its children),\n"
     " * each \"name parent joint axis px py pz lo hi\": the parent's index (0 for the\n"
     " * root), the joint that turns this segment on its parent, the joint axis (x\n"
     " * or y, in the mech frame) through the pivot (mech frame, meters), and the\n"
     " * joint range in degrees. The root row has \"-\" for joint and axis."),
    ("SegCount", "num", "Number of segments."),
    ("PartData", "list", "The mech's parts in spawn order, each \"id itemModel seg anim px py pz\n"
     " * xx xy xz yx yy yz zx zy zz tseg tx ty tz\": the segment index the part\n"
     " * rides, its anim (fixed, aim, spin_z, hinge_x), its pivot (mech frame at\n"
     " * rest), the columns of its rest rotation, and for aim parts the segment and\n"
     " * rest point its +Y aims at (tseg 0 otherwise)."),
    ("PartCount", "num", "Number of parts."),
    ("PartDamage", "list", "Each part's damage data, in mechPartData order: \"group hp detach damaged\n"
     " * parent minx miny minz maxx maxy maxz\": its group (armor, structure,\n"
     " * actuator, ...), its hit points, 1 if it breaks off at 0 (else it stays\n"
     " * and fails), 1 if it has a damaged model (custom model data string\n"
     " * \"damaged\"), its parent part's index (0 for none: a part breaking off\n"
     " * takes its children with it), and its hitbox in its own frame (m)."),
    ("Scale", "num", "The scale the mech was built at: sizes in the gait are given at the design\n"
     " * size and multiplied by this."),
    ("Gait", "dict", "The procedural walk's numbers (at real size): lengths in meters, speeds\n"
     " * in m/s, times in seconds, angles in degrees."),
    ("Probes", "list", "Collision probes, each \"frame x y z\" (mech frame, meters): points that\n"
     " * must stay out of solid blocks. Frame \"body\" turns with the heading,\n"
     " * \"torso\" with the torso."),
    ("KneelPose", "dict", "The parked kneel (degrees per leg joint): down on the left knee."),
    ("HatchCenter", "vec", "The roof hatch's center, on top of the roof, in the mech frame at rest (m)."),
    ("Muzzles", "list", "The guns: [kind (heavy or light), the elevation joint that aims it, its\n"
     " * muzzle in the mech frame at rest (m), the traverse joint that turns it,\n"
     " * its side (l, r, or c for one in the middle)]. Rounds leave along +Z of the\n"
     " * elevation joint's segment."),
    ("CameraEye", "vec", "Where the pilot's eye goes in camera view: just ahead of the roof camera's\n"
     " * lenses, in the mech frame at rest (m); it turns with the torso."),
    ("CockpitSeat", "vec", "The pilot's seat: the top center of the chair's seat in the mech frame at\n"
     " * rest (it turns with the torso)."),
    ("Legs", "list", "A four-legged type's legs (none for two legs), each \"leg side yaw femur tibia\n"
     " * fx fy fz hx hz\": its name, its side (1 left, -1 right), its three joints, the\n"
     " * claw's tip at rest and its home spot on the ground (mech frame, m)."),
    ("DefaultColors", "list", "Default armor paint and accent colors."),
]


def write_tc_data(specs: list[dict], stamp: str) -> None:
    """tc/mech_data.tc: every type's data for the plot code, and mech*
    functions that return the current type's (global curType, mech.tc)."""
    names = [s["type"] for s in specs]
    disp = []
    for f, typ, doc in TC_FUNCS:
        body = "".join(f"    if (global curType == {i + 1}) {{\n        return {n}{f}();\n    }}\n"
                       for i, n in enumerate(names) if i > 0)
        disp.append(f"/** {doc} */\nfunction mech{f}(): {typ} {{\n{body}    return {names[0]}{f}();\n}}\n")
    text = (
        "// Generated by pack/src/mech_parts.py from mech/parts.json and the other\n"
        "// types' specs. Do not edit.\n\n"
        "/** The mech types, in order (a mech's type is its number here). */\n"
        "function mechTypeNames(): list {\n    return [" + ", ".join(f'"{n}"' for n in names) + "];\n}\n\n"
        "/** Changes whenever any of the data below changes, so parsed copies of it\n"
        " * (which outlive a code update) are thrown away. */\n"
        f"function mechDataStamp(): str {{\n    return \"{stamp}\";\n}}\n\n"
        "// The current type's data (global curType; mech.tc's useType sets it).\n\n"
        + "\n".join(disp) + "\n"
        + "".join(tc_type_funcs(n, s) for n, s in zip(names, specs))
    )
    (ROOT / "tc").mkdir(exist_ok=True)
    (ROOT / "tc/mech_data.tc").write_text(text.rstrip() + "\n")


def main():
    types = all_types()
    for t in types:
        allp = [p for _, ps in t["folders"] for p in ps]
        for p in allp:
            scale_part(p, t["scale"])
        ids = [p.id for p in allp]
        if len(set(ids)) != len(ids):
            raise SystemExit(f"{t['name']}: duplicate part ids")
        for p in allp:
            if p.parent and p.parent not in ids:
                raise SystemExit(f"{t['name']}: {p.id}: unknown parent {p.parent}")
            for x in p.shield:
                if x not in ids:
                    raise SystemExit(f"{t['name']}: {p.id}: unknown shield {x}")
    if len({len(t["folders"]) for t in types}) < 1:
        raise SystemExit("no types")
    # the damage model and the gait look these parts and joints up by name
    need = (["pelvis", "waist_ring", "power_pack", "compressor", "torso_frame", "torso_top", "torso_side_l",
             "torso_side_r", "cockpit", "sensors", "ammo_bustle", "antenna"]
            + [f"{n}_{s}" for s in "lr" for n in ("hip_mount", "hip_motor", "air_tank", "thigh", "knee_motor", "shin",
                                                   "shin_armor", "ankle_motor", "foot", "foot_armor")]
            + [f"{j}_piston_{k}_{s}" for j in ("hip", "knee", "ankle") for k in ("cyl", "rod") for s in "lr"])
    spider_need = (["pelvis", "power_pack", "torso_frame", "torso_top", "torso_side_l", "torso_side_r",
                    "cockpit", "sensors", "ammo_bustle", "antenna", "hatch"]
                   + [f"{n}_{l}" for l in ("lf", "lh", "rf", "rh") for n in ("coxa", "femur", "knee_motor", "tibia", "claw")])
    for t in types:
        ids = {p.id for _, ps in t["folders"] for p in ps}
        missing = [x for x in (spider_need if t.get("legs", 2) == 4 else need) if x not in ids]
        for kind, joint, pt, tj, side in guns_of(t):
            pre = "heavy" if kind == "heavy" else "light"
            parts = [f"{pre}_gun_{side}", f"{pre}_mount_{side}"] + ([f"heavy_barrels_{side}"] if pre == "heavy" else [])
            missing += [x for x in parts if x not in ids]
            missing += [x for x in (joint, tj) if x not in t["joints"]]
        if missing:
            raise SystemExit(f"{t['name']}: missing {missing}")
    used = set()
    for t in types:
        for _, ps in t["folders"]:
            for p in ps:
                for e in p.elems:
                    used.add(e.mat)
                    if p.damaged:
                        used.add(MATERIALS[e.mat].get("dmg", e.mat))
    textures = write_textures(used)
    for old in ("mech/leg_parts.json", "mech/LEG_PARTS.md", "tools/viewer/leg_data.js"):
        (ROOT / old).unlink(missing_ok=True)
    specs, viewer = [], {}
    for t in types:
        models, folder_of = {}, {}
        for folder, parts in t["folders"]:
            path = t["folder"] + folder
            models.update(write_models(path, parts, t["tints"]))
            folder_of.update({p.id: path for p in parts})
        spec = make_spec(t, folder_of)
        specs.append(spec)
        d = ROOT / t["spec_dir"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "parts.json").write_text(json.dumps(spec, indent=1) + "\n")
        write_table(spec, d / "PARTS.md", t["label"])
        viewer[t["name"]] = {"spec": spec, "models": models}
        allp = [p for _, ps in t["folders"] for p in ps]
        n_el = sum(len(p.elems) for p in allp)
        hips = spec["joints"]["hip_l"]["pivot"][1] if "hip_l" in spec["joints"] else spec["joints"]["yaw_lf"]["pivot"][1]
        print(f"{t['name']}: {len(allp)} parts, {n_el} elements, {spec['total_mass']} kg, "
              f"{spec['scale']}x, hips {hips} m up, top speed {spec['gait']['max_speed']} m/s")
        for name, ((A, _), (B, _)) in t["pistons"].items():
            print(f"  {name} piston: rest length {math.dist(A, B):.3f}")
        for j, r in t["ranges"].items():
            print(f"  {j}: {r[0]}..{r[1]} deg")
    stamp = hashlib.sha1(json.dumps(specs, sort_keys=True).encode()).hexdigest()[:12]
    write_tc_data(specs, stamp)
    write_pilot([(s["type"], s["board_path"], s["exit_path"]) for s in specs])
    vdir = ROOT / "tools/viewer"
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "mech_data.js").write_text(
        "// Generated by pack/src/mech_parts.py. Do not edit.\n"
        "window.MECH_TEXTURES = " + json.dumps(textures) + ";\n"
        "window.MECHS = " + json.dumps(viewer) + ";\n")
    print(f"{len(textures)} textures, data stamp {stamp}")


if __name__ == "__main__":
    main()
