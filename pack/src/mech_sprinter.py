"""The sprinter: a light, fast two-legged mech.

Like the walker (mech_parts.py) it is a turret on two digitigrade legs with
no head and no arms, built from the same kinds of parts with the same ids, so
the game's gait, damage model and pilot code drive it unchanged. It differs:

* smaller (built at SCALE 1.5 against the walker's 2.1, with a cabin sized in
  real meters for the pilot) and lighter: thinner armor with fewer hit points
* angular: faceted, chined armor (ridged thigh and shin plates, a pointed
  knee, a chisel beak under a wide visor, a wedge turret)
* longer legs for its size, hips set wider apart (a wider stance) and a
  longer, quicker stride (GAIT)
* running feet: long, narrow, one width from heel to toe, shaped like a shoe
  (heel counter, sloped vamp, a sole with toe spring), no hinged plates
* one gun on the roof (a machine gun on a pintle in the middle) besides the
  two side cannons

The pelvis frame, waist ring, power pack and compressor, and the guns, are
the walker's parts moved into place (their models are scaled with the rest);
everything else is built here. Frames as in mech_parts.py: design units, mech
frame +X left, +Y up, +Z forward, origin on the ground midway between the
hips; the leg is designed as the left leg in its own frame.
"""

from __future__ import annotations

import copy
import math

import mech_parts as W
from mech_lib import Elem, Part, beam, box, mirror_x, no_dent, plate, prism, to_local
from mech_pelvis import pelvis_parts
from mech_torso import torso_parts

add, sub, norm, lerp = W.add, W.sub, W.norm, W.lerp
X, Y, Z = W.X, W.Y, W.Z

SCALE = 1.5
HIP_X = 1.05            # wider apart than the walker's 0.75 (design units): a wider stance
ARMOR_HP = 0.55         # lighter armor: hit points of the walker's armor parts times this
PART_HP = 0.75          # every other part
MASS = 0.45

# ---------------------------------------------------------------------------
# Leg geometry (leg frame).
# ---------------------------------------------------------------------------

HIP = (0.0, 3.30, 0.00)
KNEE = (0.0, 2.12, 0.66)
ANKLE = (0.0, 0.58, -0.42)
SEGMENTS = W.SEGMENTS
JOINTS = {"hip": (HIP, "pelvis", "thigh"), "knee": (KNEE, "thigh", "shin"), "ankle": (ANKLE, "shin", "foot")}
JOINT_CAP = {"hip": 110, "knee": 80, "ankle": 80}

L_TH = math.dist(HIP, KNEE)
T_TH = norm(sub(KNEE, HIP))
F_TH = (0.0, T_TH[2], -T_TH[1])              # thigh front (forward and up)
L_SH = math.dist(KNEE, ANKLE)
T_SH = norm(sub(ANKLE, KNEE))
F_SH = (0.0, T_SH[2], -T_SH[1])              # shin front (forward and down)

HEEL_Z, TOE_Z = -0.72, 0.70                  # the sole's flat part; the toe springs up to TIP_Z
TIP_Z = 0.92
FOOT_W = 0.17                                # half width, heel to toe


def th(s, off=0.0, x=0.0):
    return add(HIP, (T_TH, s), (F_TH, off), (X, x))


def sh(s, off=0.0, x=0.0):
    return add(KNEE, (T_SH, s), (F_SH, off), (X, x))


PISTONS = {
    "hip":   (((0.0, 3.76, -0.62), "pelvis"), (th(0.50, -0.19), "thigh")),
    "knee":  ((th(0.40, 0.18, 0.25), "thigh"), (sh(0.50, 0.22, 0.25), "shin")),
    "ankle": ((sh(0.42, -0.17), "shin"), ((0.0, 0.98, -0.78), "foot")),
}


# ---------------------------------------------------------------------------
# Faceted plates.
# ---------------------------------------------------------------------------

def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def oplate(center, size, xa, ya, za, mat, **kw) -> Elem:
    """A box of `size` (along xa, ya, za: orthonormal) centered on `center`."""
    if dot(cross(xa, ya), za) < 0:
        ya = tuple(-c for c in ya)
    # R = Rz(c) Ry(b) Rx(a) with columns xa, ya, za
    if abs(xa[2]) > 0.99999:                  # gimbal lock: take c = 0
        b, c = -math.copysign(math.pi / 2, xa[2]), 0.0
        a = math.atan2(-za[1], ya[1])
    else:
        b = -math.asin(xa[2])
        a = math.atan2(ya[2], za[2])
        c = math.atan2(xa[1], xa[0])
    rot = tuple(round(math.degrees(v), 3) for v in (a, b, c))
    return plate(center, size, mat, rot, **kw)


def oplate2(center, size, xa, up, mat, **kw) -> Elem:
    """A box of `size` (along xa, along `up` made square to xa, thickness)
    centered on `center`."""
    xa = norm(xa)
    ya = norm(sub(up, tuple(c * dot(up, xa) for c in xa)))
    return oplate(center, size, xa, ya, cross(xa, ya), mat, **kw)


def facet(p, q, r, t, mat, out=None, **kw) -> Elem:
    """A flat plate `t` thick with one corner at p and edges p->q and p->r
    (r is moved square to p->q), its back face on the p-q-r plane (with `out`,
    a direction outward: its outer face on the plane, the plate behind it)."""
    u = sub(q, p)
    lu = math.sqrt(dot(u, u))
    xa = tuple(c / lu for c in u)
    v = sub(r, p)
    v = sub(v, tuple(c * dot(v, xa) for c in xa))
    lv = math.sqrt(dot(v, v))
    za = tuple(c / lv for c in v)
    ya = cross(za, xa)
    if out is not None:
        n = ya if dot(ya, out) > 0 else tuple(-c for c in ya)
        t = -abs(t) if n is ya else abs(t)
    c = add(p, (u, 0.5), (v, 0.5), (ya, t / 2))
    return oplate(c, (lu, abs(t), lv), xa, ya, za, mat, **kw)


def ridge(p, q, front, side, w, t, angle, mat, **kw) -> list[Elem]:
    """Two plates along p->q meeting in a ridge on the line, each `w` wide,
    sloping back from it by `angle` degrees either side: a V of armor whose
    point faces `front` (unit, at right angles to p->q; `side` is the third axis)."""
    L = math.dist(p, q)
    za = norm(sub(q, p))
    a = math.radians(angle)
    out = []
    for k in (1, -1):
        xa = norm(add((0.0, 0.0, 0.0), (side, k * math.cos(a)), (front, -math.sin(a))))
        xa = norm(sub(xa, tuple(c * dot(xa, za) for c in za)))
        ya = norm(cross(za, xa))
        if dot(ya, front) < 0:
            ya = tuple(-c for c in ya)
        mid = lerp(p, q, 0.5)
        c = add(mid, (xa, w / 2), (ya, -t / 2))
        out.append(oplate(c, (w, t, L), xa, ya, za, mat, **kw))
    return out


# ---------------------------------------------------------------------------
# Leg parts.
# ---------------------------------------------------------------------------

LEG: list[Part] = []


def part(p: Part, elems: list[Elem]) -> Part:
    p.pivot = tuple(round(c, 4) for c in p.pivot)
    p.elems = to_local(elems, p.pivot)
    p.hp = round(p.hp * (ARMOR_HP if p.group == "armor" else PART_HP))
    p.mass = round(p.mass * MASS, 1)
    LEG.append(p)
    return p


def hip_mount():
    y = HIP[1]
    e = [box((-0.26, y + 0.40, -0.26), (0.26, y + 0.50, 0.26), "steel", dent=False)]  # mounting flange
    for bx in (-0.20, 0.20):
        for bz in (-0.20, 0.20):
            e += prism((bx, y + 0.515, bz), "y", 0.026, 0.03, 6, "darksteel", dent=False)
    for s in (1, -1):
        x0, x1 = sorted((s * 0.15, s * 0.22))
        e.append(box((x0, y, -0.18), (x1, y + 0.42, 0.18), "gunmetal", dent=False))   # yoke cheeks
        e += prism((s * 0.185, y, 0.0), "x", 0.18, 0.07, 6, "gunmetal", dent=False)    # hexagonal bosses
    e += prism((-0.26, y, 0.0), "x", 0.13, 0.08, 6, "darksteel", dent=False)          # inboard bearing cap
    a, _ = PISTONS["hip"]
    A = a[0]
    e.append(beam((0.0, y + 0.44, -0.18), add(A, (Y, 0.05), (Z, 0.04)), 0.16, 0.08, "gunmetal", dent=False))
    e += W.clevis(A, norm(sub((0.0, y + 0.44, -0.18), A)), 0.14, gap=0.06)
    e += W.pin(A, 0.16)
    part(Part("hip_mount", "Hip mount (flange, yoke, piston anchor)", "structure", None, "pelvis", HIP,
              120, 400, "fail", "Cracks: the whole leg sags and the hip motor loses torque; at 0 the leg is lost",
              damaged=False), e)


def hip_motor():
    e = W.motor(HIP, 1, 0.24, 0.18, 3, sides=12)
    e.append(box((0.30, HIP[1] + 0.22, -0.10), (0.42, HIP[1] + 0.32, 0.06), "darksteel", dent=False))  # junction box
    part(Part("hip_motor", "Hip motor (servo)", "actuator", "hip_mount", "pelvis", HIP,
              85, 160, "fail", "Loses torque with HP: slower, shorter strides; at 0 the hip only moves on its piston",
              shield=["hip_guard"], damaged=False), e)


def hip_guard():
    y = HIP[1]
    e = []
    # a faceted tasset: two plates breaking forward along a vertical crease
    for k in (1, -1):
        xa = (k * 0.85, 0.0, -0.53)
        e.append(oplate2(add((0.10, y + 0.16, 0.40), (norm(xa), 0.17)), (0.34, 0.52, 0.045), xa, (0.0, 0.96, -0.28),
                         "armor"))
    e.append(plate((0.10, y - 0.09, 0.42), (0.04, 0.30, 0.03), "accent", (-16.0, 0.0, 0.0)))    # crease trim
    e.append(plate((0.38, y + 0.40, 0.0), (0.30, 0.045, 0.58), "armor", (0.0, 0.0, -28.0)))    # shoulder over the motor
    e.append(plate((0.50, y + 0.30, 0.0), (0.12, 0.04, 0.52), "armor", (0.0, 0.0, -62.0)))     # its outer bevel
    e.append(plate((0.37, y + 0.43, 0.0), (0.06, 0.01, 0.50), "accent", (0.0, 0.0, -28.0)))    # stripe
    part(Part("hip_guard", "Hip armor (faceted tasset and motor cap)", "armor", "hip_mount", "pelvis", HIP,
              40, 140, "detach", "Torn off: the hip motor takes hits directly"), e)


def air_tank():
    c = (0.0, HIP[1] + 0.565, -0.40)
    e = [box((-0.16, HIP[1] + 0.44, -0.48), (0.16, HIP[1] + 0.47, -0.32), "darksteel", dent=False)]
    e += prism(c, "x", 0.095, 0.40, 8, "accent")                                     # octagonal tank
    for s in (1, -1):
        e += prism(add(c, (X, s * 0.22)), "x", 0.065, 0.04, 8, "accent")
        e += prism(add(c, (X, s * 0.11)), "x", 0.10, 0.025, 8, "darksteel", dent=False)
    e.append(box((-0.04, c[1] + 0.09, -0.45), (0.06, c[1] + 0.15, -0.37), "brass", dent=False))
    e.append(box((0.08, c[1] + 0.09, -0.42), (0.12, c[1] + 0.12, -0.38), "glow", dent=False))
    a, b = PISTONS["hip"]
    d = norm(sub(b[0], a[0]))
    inlet = add(a[0], (d, 0.15), (X, 0.15))
    pts = [(0.02, c[1] + 0.09, -0.47), (0.08, c[1] + 0.02, -0.56), (0.15, HIP[1] + 0.40, -0.60), inlet]
    e += [beam(pts[i], pts[i + 1], 0.03, 0.03, "hose", dent=False) for i in range(len(pts) - 1)]
    part(Part("air_tank", "Air tank and valve block", "air", "hip_mount", "pelvis", HIP,
              30, 60, "detach", "Ruptures: every piston loses pressure and the leg can only use its motors",
              shield=["hip_mount"]), e)


def thigh():
    e = prism(HIP, "x", 0.17, 0.30, 8, "darksteel")                                   # hip hub
    e.append(beam(th(0.10), th(L_TH - 0.08), 0.20, 0.22, "gunmetal"))                 # core
    for s in (1, -1):
        e.append(beam(th(0.05, 0, s * 0.13), th(L_TH - 0.05, 0, s * 0.13), 0.05, 0.17, "steel"))  # rails
        e += prism(add(KNEE, (X, s * 0.13)), "x", 0.14, 0.07, 8, "darksteel")        # knee clevis
    e.append(beam(th(0.25, -0.13), th(0.90, -0.13), 0.10, 0.04, "darksteel"))        # rear spine
    _, b = PISTONS["hip"]
    e += W.clevis(b[0], F_TH, 0.14, gap=0.06)
    e += W.pin(b[0], 0.16)
    a, _ = PISTONS["knee"]
    e.append(beam(th(0.40, 0.03, 0.18), th(0.40, 0.22, 0.18), 0.07, 0.10, "darksteel"))  # gusset
    e += W.pin(a[0], 0.18)
    e.append(beam(th(0.15, 0.03, -0.17), th(L_TH - 0.20, 0.03, -0.17), 0.04, 0.04, "hose"))
    e.append(beam(th(L_TH - 0.20, 0.03, -0.17), add(KNEE, (Y, 0.18), (X, -0.25)), 0.04, 0.04, "hose"))
    part(Part("thigh", "Thigh frame", "structure", "hip_mount", "thigh", HIP,
              260, 320, "fail", "Bends: the knee runs out of line and the stride shortens; at 0 the leg collapses",
              shield=["thigh_armor"]), e)


def thigh_armor():
    e = ridge(th(0.16, 0.20), th(L_TH - 0.22, 0.17), F_TH, X, 0.17, 0.04, 34, "armor")   # ridged front plate
    for s in (1, -1):                                                                     # chamfered side plates
        e.append(beam(th(0.24, -0.02, s * 0.175), th(L_TH - 0.28, -0.02, s * 0.165), 0.025, 0.20, "armor"))
    e.append(beam(th(0.24, 0.205, 0.0), th(L_TH - 0.30, 0.18, 0.0), 0.035, 0.03, "accent"))  # ridge trim
    e.append(beam(th(0.30, 0.16, 0.11), th(0.44, 0.16, 0.11), 0.06, 0.012, "hazard"))
    part(Part("thigh_armor", "Thigh armor (ridged)", "armor", "thigh", "thigh", HIP,
              70, 200, "detach", "Torn off: the thigh frame and its knee piston mount take hits directly"), e)


def knee_motor():
    e = W.motor(KNEE, -1, 0.16, 0.15, 3, sides=8)
    part(Part("knee_motor", "Knee motor (servo)", "actuator", "thigh", "thigh", KNEE,
              55, 130, "fail", "Loses torque with HP; at 0 the knee only moves on its piston"), e)


def shin():
    e = prism(KNEE, "x", 0.13, 0.22, 8, "darksteel")                                  # knee hub
    e.append(beam(sh(0.10), sh(L_SH - 0.10), 0.18, 0.20, "gunmetal"))                 # core
    for s in (1, -1):
        e.append(beam(sh(0.08, 0, s * 0.12), sh(L_SH - 0.06, 0, s * 0.12), 0.04, 0.15, "steel"))
        e += prism(add(ANKLE, (X, s * 0.13)), "x", 0.12, 0.06, 8, "darksteel")       # ankle clevis
    e.append(beam(sh(0.55), sh(1.35), 0.195, 0.14, "vent"))
    _, b = PISTONS["knee"]
    e.append(beam(sh(0.50, 0.04, 0.18), sh(0.50, 0.26, 0.18), 0.07, 0.10, "darksteel"))
    e += W.pin(b[0], 0.20)
    a, _ = PISTONS["ankle"]
    e += W.clevis(a[0], F_SH, 0.14, gap=0.06)
    e += W.pin(a[0], 0.16)
    e.append(beam(sh(0.55, -0.11, -0.09), sh(1.45, -0.11, -0.09), 0.035, 0.035, "hose"))
    part(Part("shin", "Shin frame", "structure", "thigh", "shin", KNEE,
              210, 300, "fail", "Bends: the foot lands out of line; at 0 the leg collapses",
              shield=["shin_armor", "knee_guard"]), e)


def knee_guard():
    """A pointed knee: two ridged plates meeting at a point ahead of the knee."""
    tip = add(KNEE, (Z, 0.27), (Y, 0.02))
    top = add(KNEE, (F_TH, 0.16), (T_TH, -0.30))
    bot = add(KNEE, (F_SH, 0.15), (T_SH, 0.30))
    e = ridge(top, tip, norm(add(F_TH, (Z, 0.4))), X, 0.15, 0.04, 30, "armor")
    e += ridge(tip, bot, norm(add(F_SH, (Z, 0.4))), X, 0.15, 0.04, 30, "armor")
    e.append(beam(add(tip, (Y, 0.10), (Z, -0.025)), add(tip, (Y, -0.10), (Z, -0.025)), 0.05, 0.03, "accent"))  # point trim
    for s in (1, -1):
        e.append(facet(add(KNEE, (X, s * 0.16), (Y, -0.14), (Z, 0.02)), add(KNEE, (X, s * 0.16), (Y, -0.14), (Z, 0.24)),
                       add(KNEE, (X, s * 0.16), (Y, 0.14), (Z, 0.02)), 0.025, "armor"))     # side cheeks
    part(Part("knee_guard", "Knee armor (pointed)", "armor", "shin", "shin", KNEE,
              30, 160, "detach", "Torn off: the knee hub and motor take hits directly"), e)


def shin_armor():
    e = ridge(sh(0.32, 0.16), sh(1.00, 0.165), F_SH, X, 0.16, 0.04, 32, "armor")      # upper greave
    e += ridge(sh(0.96, 0.165), sh(1.52, 0.14), F_SH, X, 0.15, 0.04, 38, "armor")     # lower greave
    e.append(beam(sh(0.36, 0.20), sh(1.48, 0.175), 0.03, 0.03, "accent"))            # ridge trim
    e.append(beam(sh(0.40, 0.155, -0.12), sh(0.56, 0.155, -0.12), 0.07, 0.012, "hazard"))
    for s in (1, -1):
        e.append(beam(sh(0.70, 0.05, s * 0.165), sh(1.34, 0.05, s * 0.15), 0.025, 0.14, "armor"))  # side wings
    part(Part("shin_armor", "Shin armor (ridged greave)", "armor", "shin", "shin", KNEE,
              60, 200, "detach", "Torn off: the shin frame takes hits directly"), e)


def ankle_motor():
    e = W.motor(ANKLE, -1, 0.12, 0.10, 2, sides=8)
    part(Part("ankle_motor", "Ankle motor (servo)", "actuator", "shin", "shin", ANKLE,
              30, 100, "fail", "Loses torque with HP: the foot slaps down; at 0 the ankle only moves on its piston"), e)


# The foot: a long, narrow, one-width mechanical foot in three pieces on
# one frame (it moves as one): a heel block down and back from the ankle, a
# long metatarsal down to a low mid-foot hub, and a toe block on to the tip,
# each with its own pad, under angular cowls, with sprung dampers.
MID = (0.0, 0.17, 0.28)                       # the mid-foot hub
HEEL = (0.0, 0.14, -0.66)                     # the heel block's end
TIP = (0.0, 0.07, 0.92)                       # the toe's tip


def hub(c, r, w, cap=True):
    """A round hub across the foot, with brass bearing caps on both ends."""
    e = prism(c, "x", r, w, 8, "darksteel")
    if cap:
        for s_ in (1, -1):
            e += prism(add(c, (X, s_ * (w / 2 + 0.01))), "x", r * 0.55, 0.02, 8, "brass")
            e += prism(add(c, (X, s_ * (w / 2 + 0.025))), "x", r * 0.25, 0.012, 6, "steel")
    return e


def spring(a, b, r, mat="brass", coils=6):
    """A coil spring round a damper rod from a to b."""
    e = [beam(a, b, 0.025, 0.025, "chrome")]
    for k in range(coils):
        c = lerp(a, b, (k + 0.5) / coils)
        d = norm(sub(b, a))
        e.append(beam(add(c, (d, -0.012)), add(c, (d, 0.012)), 2 * r, 2 * r, mat))
    return e


def foot():
    """The foot's frame: ankle hub, heel block, metatarsal, mid-foot hub, toe
    block, pads, and dampers (springs either side of the heel, one on top of
    the toe)."""
    w = FOOT_W
    e = hub(ANKLE, 0.13, 0.28)
    e.append(beam(ANKLE, HEEL, 0.20, 0.16, "gunmetal"))                                 # heel block
    e.append(beam(ANKLE, MID, 0.17, 0.17, "gunmetal"))                                  # metatarsal
    e += hub(MID, 0.09, 0.24)
    e.append(beam(MID, TIP, 0.22, 0.12, "darksteel"))                                   # toe block
    # pads: heel, under the mid hub, toe
    e.append(box((-w + 0.03, 0.0, HEEL_Z - 0.06), (w - 0.03, 0.07, -0.52), "rubber"))
    e.append(box((-w + 0.03, 0.0, 0.16), (w - 0.03, 0.07, 0.40), "rubber"))
    e.append(box((-w + 0.03, 0.0, 0.48), (w - 0.03, 0.06, TIP[2] - 0.04), "rubber"))
    e.append(beam((0.0, 0.04, TIP[2] - 0.08), (0.0, 0.0, TIP[2] + 0.02), 2 * w - 0.06, 0.05, "rubber"))   # toe grip
    # the ankle piston's heel horn
    _, b = PISTONS["ankle"]
    B = b[0]
    e.append(beam(ANKLE, lerp(ANKLE, B, 0.72), 0.10, 0.10, "darksteel"))
    e += W.clevis(B, norm(sub(ANKLE, B)), 0.18, gap=0.055)
    e += W.pin(B, 0.16)
    # sprung dampers: either side of the heel, and over the toe
    for s_ in (1, -1):
        x = s_ * (w + 0.03)
        e.append(beam((x, ANKLE[1] - 0.02, ANKLE[2] + 0.06), (x, 0.42, -0.36), 0.06, 0.06, "darksteel"))
        e += spring((x, 0.40, -0.40), (x, 0.17, -0.60), 0.045)
        x0, x1 = sorted((s_ * (w - 0.02), s_ * (w + 0.06)))
        e.append(box((x0, 0.10, -0.66), (x1, 0.18, -0.56), "steel"))
    e += spring((0.0, 0.40, -0.10), (0.0, 0.25, 0.40), 0.04)
    e.append(box((-0.05, 0.22, 0.38), (0.05, 0.30, 0.46), "steel"))
    e.append(box((-0.07, 0.15, TIP[2] - 0.10), (0.07, 0.17, TIP[2] - 0.04), "glow", faces=("up", "south")))
    part(Part("foot", "Foot (heel block, metatarsal, toe block, sprung dampers)", "structure", "shin", "foot", ANKLE,
              150, 260, "fail", "Damaged dampers and pads cost grip and balance; at 0 the mech stumbles on every step",
              shield=["foot_armor"]), e)


def foot_armor():
    """Angular cowls: a ridged instep over the metatarsal with two swept fins,
    a ridged toe cap that hooks down to the tip, a heel spur, and side plates."""
    up = lambda a, b: norm(tuple(-c for c in cross(norm(sub(b, a)), X)) if cross(norm(sub(b, a)), X)[1] < 0
                           else cross(norm(sub(b, a)), X))
    a, b = add(ANKLE, (Y, 0.15), (Z, 0.05)), add(MID, (Y, 0.15), (Z, 0.02))
    e = ridge(a, b, up(a, b), X, 0.15, 0.04, 28, "armor")                               # instep cowl
    e.append(beam(add(a, (Y, 0.02)), add(b, (Y, 0.02)), 0.03, 0.03, "accent"))
    for s_ in (1, -1):                                                                  # swept fins
        root = lerp(a, b, 0.55)
        base = add(root, (X, s_ * 0.10), (Y, -0.04))
        e.append(beam(base, add(base, (Y, 0.20), (Z, -0.16), (X, s_ * 0.04)), 0.04, 0.10, "armor"))
        e.append(beam(add(base, (Y, 0.02)), add(base, (Y, 0.18), (Z, -0.14), (X, s_ * 0.04)), 0.045, 0.02, "accent"))
    c, d = add(MID, (Y, 0.12), (Z, -0.04)), add(TIP, (Y, 0.11), (Z, -0.10))
    e += ridge(c, d, up(c, d), X, 0.14, 0.04, 26, "armor")                              # toe cap
    e.append(facet((-0.15, d[1] + 0.02, d[2] - 0.02), (0.15, d[1] + 0.02, d[2] - 0.02), (-0.15, 0.02, TIP[2] + 0.04),
                   0.04, "armor", out=(0.0, 0.2, 1.0)))                                 # hooked tip
    e.append(beam(add(c, (Y, 0.02)), add(d, (Y, 0.02)), 0.03, 0.03, "accent"))
    # heel spur: a cowl from over the ankle down past the heel, ending in a point
    h0, h1 = add(ANKLE, (Y, 0.12), (Z, -0.10)), (0.0, 0.10, HEEL_Z - 0.10)
    e += ridge(h0, h1, norm((0.0, 0.5, -1.0)), X, 0.13, 0.04, 30, "armor")
    for s_ in (1, -1):                                                                  # side plates
        x = s_ * (FOOT_W + 0.005)
        e.append(facet((x, 0.24, -0.28), (x, 0.15, 0.14), (x, 0.36, -0.25), 0.03, "armor", out=(s_ * 1.0, 0.0, 0.0)))
        e.append(beam((x + s_ * 0.002, 0.10, 0.48), (x + s_ * 0.002, 0.16, 0.80), 0.01, 0.04, "hazard"))
    part(Part("foot_armor", "Foot armor (instep cowl and fins, toe cap, heel spur)", "armor", "foot", "foot", ANKLE,
              45, 170, "detach", "Torn off: the foot's frame, hubs and dampers take hits directly"), e)


def build_leg() -> list[Part]:
    LEG.clear()
    hip_mount(); hip_motor(); hip_guard(); air_tank()
    thigh(); thigh_armor(); knee_motor()
    shin(); knee_guard(); shin_armor(); ankle_motor()
    foot(); foot_armor()
    W.pistons(PISTONS, part, mass_k=1.0, hp_k=1.0)
    return LEG


# ---------------------------------------------------------------------------
# Pelvis: the walker's frame, ring, power pack and compressor moved up to
# these hips, with angular armor of its own.
# ---------------------------------------------------------------------------

PELVIS_UP = HIP[1] - W.HIP[1]                 # the walker's pelvis is built over hips at 3.0


def moved(p: Part, d, **kw) -> Part:
    """A copy of part p moved by d (its elements are local to its pivot)."""
    q = copy.deepcopy(p)
    q.pivot = tuple(round(a + b, 4) for a, b in zip(p.pivot, d))
    if q.links and "to" in q.links:
        q.links = dict(q.links, to=[round(a + b, 4) for a, b in zip(q.links["to"], d)])
    for k, v in kw.items():
        setattr(q, k, v)
    return q


def lighten(p: Part) -> Part:
    p.hp = round(p.hp * (ARMOR_HP if p.group == "armor" else PART_HP))
    p.mass = round(p.mass * MASS, 1)
    return p


def pelvis() -> list[Part]:
    keep = {q.id: q for q in pelvis_parts(HIP_X)}
    d = (0.0, PELVIS_UP, 0.0)
    out = [lighten(moved(keep[i], d)) for i in ("pelvis", "waist_ring", "power_pack", "compressor")]
    piv = add(keep["pelvis"].pivot, (Y, PELVIS_UP))
    y = HIP[1]
    x1 = HIP_X + 0.30
    # front: a V-shaped prow of two plates, and faceted covers over the hip flanges
    e = []
    for k in (1, -1):
        xa = norm((k * 0.80, 0.0, -0.60))
        e.append(oplate2(add((0.0, y + 0.30, 0.44), (xa, 0.24)), (0.48, 0.56, 0.045), xa, (0.0, 1.0, -0.22), "armor"))
        e.append(plate((k * HIP_X, y + 0.72, 0.0), (0.64, 0.045, 0.58), "armor", (0.0, 0.0, -k * 14.0)))
        e.append(plate((k * (x1 + 0.02), y + 0.60, 0.0), (0.045, 0.22, 0.58), "armor", (0.0, 0.0, k * 30.0)))
        e.append(plate((k * HIP_X, y + 0.75, 0.0), (0.64, 0.01, 0.06), "accent", (0.0, 0.0, -k * 14.0)))
    e.append(beam((0.0, y + 0.06, 0.52), (0.0, y + 0.54, 0.42), 0.05, 0.03, "accent"))  # prow trim
    out.append(lighten(Part("pelvis_armor", "Pelvis armor (prow, flange covers)", "armor", "pelvis", "pelvis", piv,
                            90, 260, "detach", "Torn off: the pelvis frame and keel take hits directly")))
    out[-1].elems = to_local(e, piv)
    # rear: a wedge cowl over the power pack
    e = [facet((-0.44, y + 0.44, -0.80), (0.44, y + 0.44, -0.80), (-0.44, y + 0.12, -0.70), 0.045, "armor"),
         facet((-0.44, y + 0.44, -0.80), (0.44, y + 0.44, -0.80), (-0.44, y + 0.44, -0.30), -0.045, "armor")]
    for k in (1, -1):
        x0, x1_ = sorted((k * 0.40, k * 0.44))
        e.append(box((x0, y + 0.0, -0.78), (x1_, y + 0.44, -0.30), "armor"))
        e.append(beam((k * 0.445, y + 0.40, -0.76), (k * 0.445, y + 0.06, -0.66), 0.01, 0.04, "accent"))
    out.append(lighten(Part("rear_armor", "Rear armor (power pack cowl)", "armor", "pelvis", "pelvis", piv,
                            45, 180, "detach", "Torn off: the power pack and waist motor take hits directly")))
    out[-1].elems = to_local(e, piv)
    return out


# ---------------------------------------------------------------------------
# Torso: a wedge turret with a chisel beak under a wide visor.
# ---------------------------------------------------------------------------

WAIST = (0.0, HIP[1] + 0.90, 0.0)             # the waist ring's top (the torso turns about Y here)
PIVOT = (0.0, 4.80, 0.0)
FLOOR_Y = 4.36                                # cabin floor (top of the grating)
CEIL_Y = FLOOR_Y + 1.38 / SCALE               # 1.38 m of headroom
ROOF_Y = CEIL_Y + 0.09                        # top of the roof plates
HALF_W = 0.62                                 # cabin half width (inside)
FRONT_Z, REAR_Z = 0.72, -1.12                 # cabin front and rear (inside)
VIEW_X = 0.56
VIEW_Y = (FLOOR_Y + 0.84 / SCALE, FLOOR_Y + 1.22 / SCALE)
VISOR_Z = FRONT_Z + 0.12                      # the visor's face
SEAT_TOP = 0.18                               # real m above the floor
RECLINE = 30.0
HIPS_Z = -0.11
STICK_X, STICK_Z, GRIP_UP = 0.33, 0.15, 0.415
SEAT = (0.0, FLOOR_Y + SEAT_TOP / SCALE, FRONT_Z - 1.0 / SCALE)
_r = math.radians(RECLINE)
EYE = (0.0, SEAT[1] + 1.03 * math.cos(_r) / SCALE, SEAT[2] + (HIPS_Z - 1.03 * math.sin(_r)) / SCALE)
HATCH_Z, HATCH_HALF = -0.80, 0.26
BEAK = (0.50, 4.52, 1.22)                     # the nose's ridge: half width, height, how far forward
CHINE = (0.76, 4.74)                          # the side chine: half width, height
SHOULDER = (0.70, 5.10)                       # where the side meets the roof chamfer
HGUN = (1.17, 4.80, 0.05)                     # left cannon trunnion
LGUN = (0.0, ROOF_Y + 0.20, 0.25)             # roof gun trunnion
CAMERA_EYE = (-0.36, ROOF_Y + 0.08, 0.70)
H_RANGE, L_RANGE = [-35, 12], [-35, 8]
H_TRAVERSE, L_TRAVERSE = [-15, 15], [-60, 60]


def pilot_grips():
    return [(s * STICK_X / SCALE, SEAT[1] + GRIP_UP / SCALE, SEAT[2] + (STICK_Z + 0.0275) / SCALE) for s in (1, -1)]


def hatch_hole(x0, x1, y0, y1, z0, z1, mat):
    hz, h = HATCH_Z, HATCH_HALF
    return [box((x0, y0, hz + h), (x1, y1, z1), mat), box((x0, y0, z0), (x1, y1, hz - h), mat),
            box((x0, y0, hz - h), (-h, y1, hz + h), mat), box((h, y0, hz - h), (x1, y1, hz + h), mat)]


def frame():
    w, f, r = HALF_W, FRONT_Z, REAR_Z
    e = prism((0.0, WAIST[1] + 0.04, 0.0), "y", 0.40, 0.06, 8, "darksteel")          # base on the turntable
    e += prism((0.0, WAIST[1] + 0.10, 0.0), "y", 0.34, 0.06, 8, "gunmetal")
    e.append(box((-w - 0.04, FLOOR_Y - 0.06, r - 0.04), (w + 0.04, FLOOR_Y - 0.02, f + 0.04), "gunmetal"))  # floor
    e += hatch_hole(-w - 0.04, w + 0.04, CEIL_Y, CEIL_Y + 0.04, r - 0.04, f + 0.04, "gunmetal")         # ceiling
    for s in (1, -1):
        x0, x1 = sorted((s * w, s * (w + 0.04)))
        e.append(box((x0, FLOOR_Y - 0.02, r), (x1, CEIL_Y, f), "gunmetal"))           # side walls
        x0, x1 = sorted((s * VIEW_X, s * w))
        e.append(box((x0, VIEW_Y[0], f), (x1, VIEW_Y[1], f + 0.04), "gunmetal"))     # beside the viewport
    e.append(box((-w, FLOOR_Y - 0.02, r - 0.04), (w, CEIL_Y, r), "gunmetal"))         # rear wall
    e.append(box((-w, FLOOR_Y - 0.02, f), (w, VIEW_Y[0], f + 0.04), "gunmetal"))      # front wall below
    e.append(box((-w, VIEW_Y[1], f), (w, CEIL_Y, f + 0.04), "gunmetal"))              # front wall above
    e.append(box((-w + 0.04, FLOOR_Y - 0.10, r + 0.04), (w - 0.04, FLOOR_Y - 0.06, f - 0.04), "darksteel"))  # belly
    for s in (1, -1):
        x0, x1 = sorted((s * (w + 0.04), s * 0.80))
        e.append(box((x0, HGUN[1] - 0.16, -0.16), (x1, HGUN[1] + 0.16, 0.24), "darksteel"))  # cannon hardpoints
    e.append(box((-0.14, ROOF_Y - 0.06, 0.05), (0.14, ROOF_Y, 0.40), "darksteel"))   # roof gun hardpoint
    return no_dent(e)


def front():
    """A chisel nose under the visor: a lower and an upper glacis meeting in a
    ridge, a facet at each end of it back to the chines; the viewport
    tunnel, and the brow over it."""
    rw, ry, rz = BEAK
    y0, y1 = VIEW_Y
    sill_y, sill_z = y0 - 0.03, VISOR_Z + 0.02
    belly_y, belly_z = FLOOR_Y - 0.10, FRONT_Z + 0.06
    e = [facet((-rw, ry, rz), (rw, ry, rz), (-rw, sill_y, sill_z), 0.05, "armor", out=(0.0, 1.0, 0.8)),     # upper glacis
         facet((-rw, ry, rz), (rw, ry, rz), (-rw, belly_y, belly_z), 0.05, "armor", out=(0.0, -1.0, 0.5)),  # lower glacis
         beam((-rw, ry, rz), (rw, ry, rz), 0.035, 0.035, "darksteel")]                                    # ridge
    for s_ in (1, -1):
        end, chine = (s_ * rw, ry, rz), (s_ * (CHINE[0] - 0.01), CHINE[1], FRONT_Z + 0.04)
        e.append(facet(end, chine, (s_ * rw, sill_y, sill_z), 0.05, "armor", out=(s_ * 0.6, 1.0, 0.6)))
        e.append(facet(end, chine, (s_ * rw, belly_y, belly_z), 0.05, "armor", out=(s_ * 0.6, -1.0, 0.5)))
        e.append(beam(end, chine, 0.03, 0.03, "darksteel"))
        e.append(beam((s_ * 0.24, ry + 0.03, rz - 0.04), (s_ * 0.24, sill_y - 0.02, sill_z + 0.06), 0.07, 0.012, "accent"))
    e.append(facet((-0.14, belly_y + 0.05, belly_z + 0.10), (0.14, belly_y + 0.05, belly_z + 0.10), (-0.14, ry - 0.05, rz - 0.12),
                   0.006, "hazard", out=(0.0, -1.0, 0.5)))
    # the viewport tunnel, and the brow over it sloping back to the roof
    e.append(box((-VIEW_X - 0.04, y0 - 0.03, FRONT_Z), (VIEW_X + 0.04, y0, VISOR_Z + 0.01), "darksteel"))
    e.append(box((-VIEW_X - 0.04, y1, FRONT_Z), (VIEW_X + 0.04, y1 + 0.03, VISOR_Z + 0.01), "darksteel"))
    for s_ in (1, -1):
        x0, x1 = sorted((s_ * VIEW_X, s_ * (VIEW_X + 0.04)))
        e.append(box((x0, y0, FRONT_Z), (x1, y1, VISOR_Z + 0.01), "darksteel"))
        x0, x1 = sorted((s_ * (VIEW_X + 0.04), s_ * (HALF_W + 0.06)))
        e.append(box((x0, y0 - 0.03, FRONT_Z + 0.04), (x1, y1 + 0.03, VISOR_Z + 0.03), "armor"))   # beside the visor
    e.append(facet((-HALF_W - 0.06, y1 + 0.03, VISOR_Z + 0.03), (HALF_W + 0.06, y1 + 0.03, VISOR_Z + 0.03),
                   (-HALF_W - 0.06, ROOF_Y, FRONT_Z - 0.10), 0.05, "armor", out=(0.0, 1.0, 1.0)))  # brow
    return e


def top():
    w = HALF_W
    e = hatch_hole(-w, w, CEIL_Y + 0.04, ROOF_Y, REAR_Z - 0.04, FRONT_Z - 0.06, "armor")
    hz, h = HATCH_Z, HATCH_HALF
    for a, b in (((-h - 0.04, hz + h), (h + 0.04, hz + h + 0.04)), ((-h - 0.04, hz - h - 0.04), (h + 0.04, hz - h)),
                 ((-h - 0.04, hz - h), (-h, hz + h)), ((h, hz - h), (h + 0.04, hz + h))):
        e.append(box((a[0], ROOF_Y, a[1]), (b[0], ROOF_Y + 0.012, b[1]), "hazard"))   # hatch rim
    for s in (1, -1):
        # chamfers down from the roof edge to the chine, and a raised spine either side
        e.append(facet((s * SHOULDER[0], SHOULDER[1], REAR_Z - 0.06), (s * SHOULDER[0], SHOULDER[1], FRONT_Z - 0.02),
                       (s * (w - 0.02), ROOF_Y, REAR_Z - 0.06), 0.04 * s, "armor"))
        e.append(box((s * 0.40 - 0.03, ROOF_Y, REAR_Z + 0.04), (s * 0.40 + 0.03, ROOF_Y + 0.03, 0.55), "armor"))
        e.append(box((s * 0.40 - 0.012, ROOF_Y + 0.03, REAR_Z + 0.08), (s * 0.40 + 0.012, ROOF_Y + 0.036, 0.50),
                     "accent"))
    return e


def hatch():
    hz, h, y = HATCH_Z, HATCH_HALF, ROOF_Y
    e = [box((-h + 0.01, y - 0.02, hz - h + 0.01), (h - 0.01, y + 0.02, hz + h - 0.01), "armor"),
         facet((-h + 0.05, y + 0.02, hz - h + 0.05), (h - 0.05, y + 0.02, hz - h + 0.05), (-h + 0.05, y + 0.05, hz + h - 0.08),
               -0.012, "accent"),
         box((-0.07, y + 0.02, hz + h - 0.07), (0.07, y + 0.05, hz + h - 0.04), "steel"),
         box((-h + 0.03, y - 0.04, hz - h + 0.03), (h - 0.03, y - 0.02, hz + h - 0.03), "darksteel")]
    for x in (-0.13, 0.13):
        e += prism((x, y, hz - h), "x", 0.018, 0.07, 6, "steel")
    return e


def side_l():
    """The left side: two plates meeting in a sharp chine, lower one leaning
    out, upper one leaning in, from the cheek back to the bustle."""
    cx, cy = CHINE
    z0, z1 = REAR_Z - 0.06, FRONT_Z + 0.02
    e = [facet((HALF_W + 0.04, FLOOR_Y - 0.10, z0), (HALF_W + 0.04, FLOOR_Y - 0.10, z1), (cx, cy, z0), 0.04, "armor"),
         facet((cx, cy, z0), (cx, cy, z1), (SHOULDER[0], SHOULDER[1], z0), 0.04, "armor")]
    e.append(beam((cx + 0.01, cy, z0 + 0.02), (cx + 0.01, cy, z1 - 0.02), 0.03, 0.03, "accent"))   # chine trim
    e.append(facet((cx - 0.02, cy - 0.30, -0.95), (cx - 0.02, cy - 0.30, -0.55), (cx + 0.02, cy - 0.12, -0.95), 0.012,
                   "hazard"))
    return e


def side_r_mirror(p: Part) -> Part:
    q = copy.deepcopy(p)
    q.id, q.label = "torso_side_r", p.label.replace("(left)", "(right)")
    q.pivot = (-p.pivot[0], p.pivot[1], p.pivot[2])
    q.elems = mirror_x(p.elems)
    return q


def sensors():
    e = [box((-VIEW_X, VIEW_Y[0], VISOR_Z - 0.005), (VIEW_X, VIEW_Y[1], VISOR_Z), "visor", faces=("south",)),
         box((-VIEW_X, VIEW_Y[0] - 0.02, VISOR_Z), (VIEW_X, VIEW_Y[0] - 0.01, VISOR_Z + 0.005), "glow", faces=("south",))]
    cx, cy, cz = CAMERA_EYE
    e.append(facet((cx - 0.13, ROOF_Y, cz - 0.30), (cx + 0.13, ROOF_Y, cz - 0.30), (cx - 0.13, cy + 0.06, cz - 0.08),
                   -0.10, "darksteel"))                                                       # camera pod (wedge)
    e.append(box((cx - 0.13, ROOF_Y, cz - 0.10), (cx + 0.13, cy + 0.05, cz - 0.04), "darksteel"))
    for x in (-0.06, 0.06):
        e += prism((cx + x, cy, cz - 0.035), "z", 0.035, 0.02, 6, "steel")
        e += prism((cx + x, cy, cz - 0.02), "z", 0.024, 0.01, 6, "visor")
    e.append(box((cx - 0.015, cy + 0.05, cz - 0.20), (cx + 0.015, cy + 0.06, cz - 0.10), "glow"))
    return no_dent(e)


def cockpit():
    """The cabin fittings in real meters: a reclined racing chair with a
    joystick on each armrest, and three screens."""
    k = SCALE
    z0 = SEAT[2]

    def P(x, y, z):
        return (x / k, FLOOR_Y + y / k, z0 + z / k)

    def B(a, b, mat, **kw):
        return box(P(*a), P(*b), mat, **kw)

    def L(c, size, mat, rot, **kw):
        return plate(P(*c), tuple(v / k for v in size), mat, rot, **kw)

    def M(p, q, w, h, mat, **kw):
        return beam(P(*p), P(*q), w / k, h / k, mat, **kw)

    st = SEAT_TOP
    e = [box((-HALF_W, FLOOR_Y - 0.02, REAR_Z), (HALF_W, FLOOR_Y, FRONT_Z), "vent", faces=("up",))]
    e.append(B((-0.24, 0.0, -0.24), (0.24, 0.04, 0.24), "steel"))
    e.append(B((-0.05, 0.04, -0.05), (0.05, st - 0.10, 0.05), "darksteel"))
    e.append(L((0.0, st - 0.05, 0.0), (0.52, 0.10, 0.50), "seat", (-10.0, 0.0, 0.0)))

    def back(y, z):
        r = math.radians(-RECLINE)
        return (y * math.cos(r) - z * math.sin(r) + st, y * math.sin(r) + z * math.cos(r) - 0.24)

    rec = (-RECLINE, 0.0, 0.0)
    for (by, bz), size, mat in (((0.40, -0.05), (0.50, 0.80, 0.10), "seat"), ((1.00, -0.16), (0.30, 0.22, 0.10), "seat"),
                                ((0.84, -0.11), (0.10, 0.20, 0.06), "darksteel"), ((0.40, -0.12), (0.46, 0.72, 0.04), "darksteel"),
                                ((0.0, -0.06), (0.38, 0.10, 0.12), "darksteel")):
        y, z = back(by, bz)
        e.append(L((0.0, y, z), size, mat, rec))
    for s in (1, -1):
        x0, x1 = sorted((s * 0.27, s * 0.35))
        e.append(B((x0, st + 0.10, -0.22), (x1, st + 0.16, 0.22), "gunmetal"))
        e.append(B((x0 + 0.02, st - 0.10, -0.16), (x1 - 0.02, st + 0.10, -0.10), "darksteel"))
        y, z = back(0.30, 0.03)
        e.append(L((s * 0.25, y, z), (0.07, 0.62, 0.16), "seat", rec))                  # racing bolsters
        jx, jz = s * STICK_X, STICK_Z
        e += prism(P(jx, st + 0.20, jz), "y", 0.04 / k, 0.04 / k, 8, "darksteel")
        e.append(M((jx, st + 0.20, jz), (jx, st + 0.36, jz + 0.03), 0.025, 0.025, "steel"))
        e.append(B((jx - 0.025, st + 0.36, jz - 0.005), (jx + 0.025, st + 0.47, jz + 0.06), "accent"))
        e.append(B((jx - 0.012, st + 0.44, jz + 0.06), (jx + 0.012, st + 0.46, jz + 0.068), "glow"))
    wall = (FRONT_Z - z0) * k
    e.append(L((0.0, 0.60, wall - 0.05), (0.60, 0.34, 0.04), "darksteel", (-14.0, 0.0, 0.0)))
    e.append(L((0.0, 0.60, wall - 0.075), (0.54, 0.28, 0.01), "screen", (-14.0, 0.0, 0.0), faces=("north",)))
    e.append(B((-0.05, 0.0, wall - 0.10), (0.05, 0.43, wall - 0.02), "darksteel"))
    for s in (1, -1):
        c = (s * 0.70, 0.62, wall - 0.36)
        yaw = s * 38.0
        e.append(L(c, (0.38, 0.26, 0.04), "darksteel", (-10.0, yaw, 0.0)))
        off = (-s * 0.025 * math.sin(math.radians(38.0)), 0.0, -0.025 * math.cos(math.radians(38.0)))
        e.append(L(add(c, (off, 1.0)), (0.32, 0.20, 0.01), "screen", (-10.0, yaw, 0.0), faces=("north",)))
        e.append(B((c[0] - 0.04, 0.0, c[2] - 0.04), (c[0] + 0.04, c[1] - 0.13, c[2] + 0.04), "darksteel"))
    return no_dent(e)


def bustle():
    """A wedge-shaped ammo bustle behind the cabin, with feed chutes to the cannons."""
    z0, z1 = REAR_Z - 0.04, REAR_Z - 0.46
    yb, yt = FLOOR_Y - 0.04, CEIL_Y - 0.06
    e = [box((-0.50, yb, z1 + 0.04), (0.50, yt - 0.10, z0), "gunmetal"),                     # magazine
         facet((-0.54, yt, z0), (0.54, yt, z0), (-0.54, yt - 0.24, z1), -0.04, "armor"),       # sloped lid
         facet((-0.54, yt - 0.24, z1), (0.54, yt - 0.24, z1), (-0.54, yb + 0.06, z1 + 0.10), -0.04, "armor"),  # rear plate
         box((-0.36, yt - 0.10, z0 - 0.30), (0.36, yt - 0.02, z0 - 0.08), "vent", faces=("up",)),
         facet((-0.20, yb + 0.20, z1 + 0.035), (0.20, yb + 0.20, z1 + 0.035), (-0.20, yb + 0.28, z1 + 0.02), -0.008, "hazard")]
    for s in (1, -1):
        x0, x1 = sorted((s * 0.50, s * 0.54))
        e.append(box((x0, yb, z1 + 0.06), (x1, yt, z0), "armor"))
        pts = [(s * 0.54, HGUN[1] - 0.04, z0 - 0.22), (s * 0.70, HGUN[1] - 0.04, z0 - 0.06),
               (s * 0.80, HGUN[1] - 0.06, -0.62), (s * 0.85, HGUN[1] - 0.06, -0.30)]
        for i in range(len(pts) - 1):
            e.append(beam(pts[i], pts[i + 1], 0.08, 0.06, "darksteel"))
            e.append(box(tuple(v - 0.035 for v in pts[i + 1]), tuple(v + 0.035 for v in pts[i + 1]), "brass"))
    return e


def antenna():
    base = (0.36, CEIL_Y - 0.10, REAR_Z - 0.36)
    e = [box((base[0] - 0.05, base[1] - 0.02, base[2] - 0.05), (base[0] + 0.05, base[1] + 0.05, base[2] + 0.05), "darksteel")]
    e.append(beam(add(base, (Y, 0.05)), add(base, (Y, 0.75), (Z, -0.22)), 0.018, 0.018, "steel"))   # raked mast
    e.append(box(add(base, (Y, 0.73), (Z, -0.24), (X, -0.018)), add(base, (Y, 0.77), (Z, -0.20), (X, 0.018)), "glow"))
    e.append(beam(add(base, (Y, 0.05), (X, -0.08)), add(base, (Y, 0.40), (Z, -0.16), (X, -0.09)), 0.012, 0.012, "darksteel"))
    return no_dent(e)


def torso() -> tuple[list[Part], list[Part], list, dict]:
    out: list[Part] = []

    def add_part(p: Part, elems, pivot=PIVOT):
        p.pivot = tuple(round(c, 4) for c in pivot)
        p.elems = to_local(elems, p.pivot)
        out.append(lighten(p))
        return p

    add_part(Part("torso_frame", "Torso frame (hull core, hardpoints)", "structure", "waist_ring", "torso", PIVOT,
                  650, 520, "fail", "Cracks: every gun mount shakes loose and aim wanders; at 0 the mech is wrecked",
                  shield=["torso_front", "torso_top"], damaged=False), frame())
    add_part(Part("torso_front", "Torso front armor (beak, brow, cheeks)", "armor", "torso_frame", "torso", PIVOT,
                  220, 420, "detach", "Torn off: the sensors and hull core take front hits directly"), front())
    add_part(Part("torso_top", "Torso roof armor (hatch, chamfers)", "armor", "torso_frame", "torso", PIVOT,
                  140, 300, "detach", "Torn off: the hull core and roof gun mount take hits from above"), top())
    hinge = (0.0, ROOF_Y, HATCH_Z - HATCH_HALF)
    add_part(Part("hatch", "Roof hatch (hinged lid over the cabin)", "armor", "torso_top", "torso", hinge,
                  20, 120, "detach", "Torn off: the cabin is open to the sky", anim="hinge_x"), hatch(), hinge)
    left = add_part(Part("torso_side_l", "Torso side armor (left)", "armor", "torso_frame", "torso", PIVOT,
                         120, 320, "detach", "Torn off: the hull and the cannon's hardpoint take side hits directly"),
                    side_l())
    out.append(side_r_mirror(left))
    add_part(Part("cockpit", "Cockpit (racing chair, joysticks, screens)", "interior", "torso_frame", "torso", PIVOT,
                  60, 120, "fail", "Damaged: screens flicker and controls lag; at 0 the pilot flies blind",
                  shield=["torso_front", "torso_top"], damaged=False), cockpit())
    add_part(Part("sensors", "Sensors (visor, camera pod)", "sensor", "torso_frame", "torso", PIVOT, 25, 60, "fail",
                  "Damaged: aim gets sloppy; at 0 the guns fire without the rangefinder",
                  shield=["torso_front"], damaged=False), sensors())
    add_part(Part("ammo_bustle", "Ammo bustle (magazine and feed chutes)", "ammo", "torso_frame", "torso", PIVOT,
                  300, 220, "fail", "Feed jams with damage; at 0 the magazine cooks off and the cannons run dry"),
             bustle())
    add_part(Part("antenna", "Antenna mast", "sensor", "ammo_bustle", "torso", PIVOT, 4, 20, "detach",
                  "Shot off: no radio or radar", damaged=False), antenna())

    # the guns: the walker's, moved to this hull's hardpoints; one roof gun in the middle
    wt, wg, _, _ = torso_parts()
    by = {p.id: p for p in wg}
    dh = sub(HGUN, (1.30, 4.40, 0.05))
    dl = sub(LGUN, (0.45, 5.08, 0.05))
    guns = []
    for s, t in ((1, "l"), (-1, "r")):
        d = (s * dh[0], dh[1], dh[2])
        for n in ("heavy_mount", "heavy_gun", "heavy_barrels"):
            guns.append(lighten(moved(by[f"{n}_{t}"], d)))
    guns.append(lighten(moved(by["light_mount_l"], dl, id="light_mount_c", label="Roof gun pintle", segment="lyaw_c")))
    guns.append(lighten(moved(by["light_gun_l"], dl, id="light_gun_c", label="Roof machine gun", segment="lgun_c",
                              parent="light_mount_c")))
    hb = add(HGUN, (Z, 0.65))
    segments = ["torso", "hyaw_l", "hyaw_r", "lyaw_c", "hgun_l", "hgun_r", "lgun_c"]
    joints = {"waist": {"pivot": list(WAIST), "axis": "y", "parent": "pelvis", "child": "torso",
                        "range": [-180, 180], "label": "Waist"}}
    for t, s in (("l", 1), ("r", -1)):
        side = t.upper()
        piv = [s * HGUN[0], HGUN[1], HGUN[2]]
        joints[f"trav_h{t}"] = {"pivot": piv, "axis": "y", "parent": "torso", "child": f"hyaw_{t}",
                                "range": H_TRAVERSE, "label": f"Heavy {side} turn"}
        joints[f"elev_h{t}"] = {"pivot": piv, "axis": "x", "parent": f"hyaw_{t}", "child": f"hgun_{t}",
                                "range": H_RANGE, "label": f"Heavy {side}"}
    joints["trav_lc"] = {"pivot": list(LGUN), "axis": "y", "parent": "torso", "child": "lyaw_c",
                         "range": L_TRAVERSE, "label": "Roof gun turn"}
    joints["elev_lc"] = {"pivot": list(LGUN), "axis": "x", "parent": "lyaw_c", "child": "lgun_c",
                         "range": L_RANGE, "label": "Roof gun"}
    muz = [("heavy", "elev_hl", (hb[0], hb[1], hb[2] + 1.85)), ("heavy", "elev_hr", (-hb[0], hb[1], hb[2] + 1.85)),
           ("light", "elev_lc", (LGUN[0], LGUN[1], 1.08 + dl[2]))]
    return out, guns, segments, joints, muz


# ---------------------------------------------------------------------------
# The walk, the kneel and the collision probes (design units).
# ---------------------------------------------------------------------------

GAIT = dict(W.GAIT)
GAIT.update({
    "crouch": 0.24,      # a deeper runner's crouch
    "swing": 0.42,       # quick steps...
    "lift": 0.34,
    "bob": 0.08,
    "step": 0.34,
    "lead": 0.55,
    "max_speed": 4.2,    # ...and long ones: stride = speed x 2 x swing = 3.5 (5.3 m), at 6.3 m/s
    "accel": 2.2,
    "max_turn": 65.0,
    "turn_accel": 150.0,
    "aim_rate": 45.0,
    "pilot_aim_rate": 80.0,
    "toe": 22.0,         # pushes off its toes
    "max_rise": 1.40,    # 2.1 m: two blocks
    "probe_up": 1.60,
    "probe_down": 1.45,  # deeper than max_rise, so a foot half over a two-block drop still finds its ground
    "climb_rate": 1.6,
    "foot_heel": -0.26,  # samples along the long, narrow foot
    "foot_mid": 0.42,
    "foot_toe": 1.22,
    "foot_side": 0.12,
    "land_dip": 0.18,
    "dip_rate": 0.7,
    "fall_drift": 3.0,
    "kneel_drop": 1.73,
    "kneel_time": 1.1,
    "agile": 1.0,        # steers where the pilot looks, strafes, kneels on Shift, jumps on Space
    "strafe": 0.55,
    "jump_min": 6.5,     # 1.4 m up...
    "jump_max": 11.5,    # ...to 4.4 m, landing under the 12 m/s that hurts
    "charge_time": 1.2,
})
KNEEL_POSE = {"hip_l": 49.0, "knee_l": 35.0, "ankle_l": 19.6, "hip_r": -102.0, "knee_r": 57.8, "ankle_r": 44.2}  # solved offline

PROBES = (
    [("body", x, y, z) for x in (HIP_X + 0.30, -HIP_X - 0.30) for y in (3.30, 3.90) for z in (0.30, -0.30)]
    + [("body", x, KNEE[1], KNEE[2] + 0.20) for x in (HIP_X, -HIP_X)]
    + [("body", x, y, z) for x in (HIP_X, -HIP_X) for y, z in ((1.40, 0.15), (0.95, -0.15))]
    + [("torso", x, y, z) for x in (CHINE[0], -CHINE[0]) for y in (4.45, 5.20) for z in (-1.50, -0.40, 0.75)]
    + [("torso", x, BEAK[1], BEAK[2]) for x in (BEAK[0], 0.0, -BEAK[0])]
    + [("torso", x, HGUN[1], z) for x in (HGUN[0], -HGUN[0]) for z in (-0.5, 1.2, 2.4)]
)


def sprinter() -> dict:
    leg = build_leg()
    torso_p, guns, torso_segs, torso_joints, muz = torso()
    ranges = W.joint_ranges(PISTONS, JOINTS, JOINT_CAP)
    segments, joints = W.leg_joints(ranges, HIP_X, JOINTS)
    tints = [0xD9D4C7, 0xC8232C]                       # bone white, racing red
    return {
        "name": "sprinter", "label": "Sprinter", "folder": "sprinter/", "spec_dir": "mech/sprinter",
        "anims": "sprinter/",
        "about": "The sprinter: a light, fast, angular mech on long legs with running feet, a wide stance and a "
                 "long stride; two side cannons and one roof machine gun.",
        "scale": SCALE, "hip_x": HIP_X,
        "folders": [("pelvis", pelvis()), ("leg", W.place_leg("l", leg, HIP_X) + W.place_leg("r", leg, HIP_X)),
                    ("torso", torso_p), ("guns", guns)],
        "segments": segments + torso_segs, "joints": {**joints, **torso_joints},
        "seat": SEAT, "eye": EYE, "recline": RECLINE, "hips_z": HIPS_Z, "grips": pilot_grips(),
        "gait": GAIT, "gait_lengths": W.GAIT_LENGTHS, "kneel_pose": KNEEL_POSE, "probes": PROBES,
        "hatch": (ROOF_Y, HATCH_Z), "muzzles": muz, "camera_eye": CAMERA_EYE,
        "tints": tints, "pistons": PISTONS, "ranges": ranges,
    }
