"""The mech's torso: an armored turret that turns on the pelvis's waist ring,
with its guns as separate parts.

Built in the mech frame (+X left, +Y up, +Z forward, origin on the ground
midway between the hips). There is no head and no arms. The torso is a low,
wide hull with a sloped glacis and a viewport slit. Weapons hang off it:

  heavy guns  one on each side, on an elevation mount bolted to the side armor:
              a six-barrel rotary cannon (receiver, then a barrel cluster that spins)
  light guns  two on the roof, each on its own small pintle mount

Every gun is its own parts (mount, gun, and for the heavy guns the barrel
cluster), so each can be swapped, posed, damaged or shot off by itself. The
right-hand guns are the left-hand ones mirrored in X.

Segments and joints added here:

  pelvis --waist (Y)--> torso --elev_hl/elev_hr (X)--> hgun_l / hgun_r
                              --elev_ll/elev_lr (X)--> lgun_l / lgun_r

Negative elevation raises the muzzle (it is a turn about X, and the guns point
+Z). The heavy barrel cluster spins about its own Z axis ("spin_z" anim).
"""

from __future__ import annotations

import copy
import math

from mech_lib import Elem, Part, beam, box, mirror_x, no_dent, plate, prism, to_local

WAIST = (0.0, 3.90, 0.0)              # torso yaw axis (vertical line through this point)
PIVOT = (0.0, 4.40, 0.0)              # pivot the hull parts are built around
HGUN = (1.30, 4.40, 0.05)             # left heavy gun trunnion (elevation axis, along X)
HBARREL = (1.30, 4.40, 0.70)          # left heavy barrel cluster: spin axis start (along Z)
LGUN = (0.45, 5.08, 0.05)             # left light gun trunnion
H_RANGE = [-35, 12]                   # elevation, degrees (negative = muzzle up)
L_RANGE = [-35, 8]


def _part(out, p: Part, elems: list[Elem], pivot):
    p.pivot = tuple(round(c, 4) for c in pivot)
    p.elems = to_local(elems, p.pivot)
    out.append(p)


def _mirror(p: Part) -> Part:
    """The right-hand copy of a left-hand part (x -> -x)."""
    q = copy.deepcopy(p)
    sw = lambda s: s[:-2] + "_r" if s and s.endswith("_l") else s
    q.id, q.parent, q.segment = sw(p.id), sw(p.parent), sw(p.segment)
    q.label = p.label.replace("(left)", "(right)")
    q.shield = [sw(x) for x in p.shield]
    q.pivot = (-p.pivot[0], p.pivot[1], p.pivot[2])
    q.elems = mirror_x(p.elems)
    return q


def _rz(p, deg):
    a = math.radians(deg)
    return (p[0] * math.cos(a) - p[1] * math.sin(a), p[0] * math.sin(a) + p[1] * math.cos(a), p[2])


# ---------------------------------------------------------------- hull
def _frame():
    e = prism((0.0, 3.95, 0.0), "y", 0.42, 0.06, 16, "darksteel")                   # base disc on the turntable
    e += prism((0.0, 4.01, 0.0), "y", 0.36, 0.06, 16, "gunmetal")                    # collar
    e.append(box((-0.80, 4.03, -0.95), (0.80, 4.80, 0.70), "gunmetal"))              # hull core
    e.append(box((-0.72, 4.00, -0.88), (0.72, 4.04, 0.62), "darksteel"))             # belly plate
    for s in (1, -1):                                                                 # hardpoint blocks
        x0, x1 = sorted((s * 0.80, s * 0.90))
        e.append(box((x0, 4.24, -0.16), (x1, 4.56, 0.26), "darksteel"))
        x0, x1 = sorted((s * 0.42, s * 0.48))
        e.append(box((x0 - 0.0, 4.80, -0.10), (x1, 4.88, 0.20), "darksteel"))       # roof hardpoints
    return no_dent(e)


def _front():
    e = [beam((0.0, 4.05, 0.70), (0.0, 4.40, 0.98), 1.56, 0.07, "armor"),           # lower glacis
         box((-0.78, 4.40, 0.90), (0.78, 4.53, 0.99), "darksteel"),                  # viewport frame
         beam((0.0, 4.53, 0.98), (0.0, 4.87, 0.60), 1.56, 0.07, "armor")]            # upper glacis
    up = (0.0, 0.745, 0.667)                                                          # upper glacis outward normal
    for s in (1, -1):
        p0 = (s * 0.52, 4.56 + up[1] * 0.04, 0.95 + up[2] * 0.04)
        p1 = (s * 0.52, 4.84 + up[1] * 0.04, 0.64 + up[2] * 0.04)
        e.append(beam(p0, p1, 0.07, 0.012, "accent"))                                # stripes
        e.append(plate((s * 0.80, 4.45, 0.78), (0.06, 0.82, 0.44), "armor", (0.0, -s * 25.0, 0.0)))  # cheeks
        for y, z in ((4.15, 0.80), (4.33, 0.93)):
            e += prism((s * 0.62, y, z + 0.04), "z", 0.025, 0.02, 6, "steel")        # bolts
    e.append(beam((0.0, 4.12, 0.79), (0.0, 4.26, 0.89), 0.30, 0.075, "hazard"))      # warning plate
    return e


def _top():
    e = [box((-0.78, 4.80, -0.95), (0.78, 4.86, 0.62), "armor"),                    # roof
         box((-0.70, 4.86, -0.90), (-0.12, 4.88, -0.20), "armor"),                   # raised panels
         box((0.12, 4.86, -0.90), (0.70, 4.88, -0.20), "armor")]
    e += prism((0.0, 4.875, -0.55), "y", 0.25, 0.03, 12, "hazard")                   # hatch ring
    e += prism((0.0, 4.895, -0.55), "y", 0.21, 0.03, 12, "armor")                    # hatch
    e.append(box((-0.08, 4.91, -0.57), (0.08, 4.94, -0.53), "steel"))               # handle
    for s in (1, -1):
        e.append(plate((s * 0.80, 4.81, -0.16), (0.10, 0.05, 1.58), "armor", (0.0, 0.0, s * 40.0)))  # edge chamfer
        e.append(box((s * 0.41 - 0.02, 4.88, -0.88), (s * 0.41 + 0.02, 4.885, -0.24), "accent"))
    return e


def _side_l():
    c, r = (0.85, 4.42, -0.15), 12.0
    e = [plate(c, (0.07, 0.80, 1.70), "armor", (0.0, 0.0, r)),                      # side slab (top leans in)
         plate((0.86, 4.08, -0.15), (0.06, 0.20, 1.60), "armor", (0.0, 0.0, -20.0))]  # lower skirt
    sc = tuple(a + b for a, b in zip(c, _rz((0.04, 0.27, 0.0), r)))
    e.append(plate(sc, (0.012, 0.06, 1.60), "accent", (0.0, 0.0, r)))               # stripe
    hz = tuple(a + b for a, b in zip(c, _rz((0.038, -0.22, -0.62), r)))
    e.append(plate(hz, (0.01, 0.12, 0.26), "hazard", (0.0, 0.0, r)))                # warning plate
    for z in (-0.85, 0.55):
        for y in (-0.28, 0.28):
            e.append(plate(tuple(a + b for a, b in zip(c, _rz((0.04, y, z), r))), (0.02, 0.04, 0.04), "steel",
                           (0.0, 0.0, r)))                                           # bolts
    return e


def _sensors():
    e = [box((-0.62, 4.42, 0.99), (0.62, 4.51, 1.0), "visor", faces=("south",)),   # viewport
         box((-0.60, 4.405, 0.99), (0.60, 4.415, 1.002), "glow")]                    # running light
    e.append(box((-0.16, 4.86, 0.30), (0.16, 5.00, 0.55), "darksteel"))             # camera pod
    for x in (-0.08, 0.08):
        e += prism((x, 4.93, 0.565), "z", 0.045, 0.03, 8, "steel")
        e += prism((x, 4.93, 0.58), "z", 0.03, 0.01, 8, "visor")
    e.append(box((-0.02, 4.995, 0.40), (0.02, 5.01, 0.52), "glow"))                 # rangefinder light
    e.append(box((-0.05, 5.00, 0.32), (0.05, 5.06, 0.46), "gunmetal"))               # rangefinder
    return no_dent(e)


def _bustle():
    e = [box((-0.70, 4.08, -1.45), (0.70, 4.72, -0.95), "gunmetal"),                # magazine
         plate((0.0, 4.40, -1.47), (1.44, 0.66, 0.06), "armor", (-8.0, 0.0, 0.0)),  # rear plate
         box((-0.72, 4.72, -1.48), (0.72, 4.76, -0.95), "armor"),                    # lid
         box((-0.55, 4.76, -1.40), (0.55, 4.78, -1.02), "vent", faces=("up",)),      # lid vents
         plate((0.0, 4.18, -1.505), (0.50, 0.10, 0.01), "hazard", (-8.0, 0.0, 0.0))]
    for s in (1, -1):                                                                 # ammo feed chutes to the heavy mounts
        x0, x1 = sorted((s * 0.70, s * 0.73))
        e.append(box((x0, 4.12, -1.44), (x1, 4.70, -0.96), "armor"))                  # side plates
        pts = [(s * 0.72, 4.42, -1.18), (s * 0.90, 4.42, -1.08), (s * 0.99, 4.40, -0.70), (s * 1.02, 4.37, -0.34)]
        for i in range(len(pts) - 1):
            e.append(beam(pts[i], pts[i + 1], 0.10, 0.07, "darksteel"))
            e.append(box(tuple(v - 0.04 for v in pts[i + 1]), tuple(v + 0.04 for v in pts[i + 1]), "brass"))
    return e


def _antenna():
    base = (-0.55, 4.78, -1.30)
    e = [box((base[0] - 0.06, 4.76, base[2] - 0.06), (base[0] + 0.06, 4.84, base[2] + 0.06), "darksteel")]
    e.append(beam((base[0], 4.84, base[2]), (base[0], 5.75, base[2] - 0.05), 0.02, 0.02, "steel"))  # mast
    e.append(box((base[0] - 0.02, 5.74, base[2] - 0.07), (base[0] + 0.02, 5.78, base[2] - 0.03), "glow"))
    e.append(beam((base[0] + 0.10, 4.84, base[2]), (base[0] + 0.12, 5.30, base[2] - 0.08), 0.014, 0.014, "darksteel"))
    return no_dent(e)


# ---------------------------------------------------------------- heavy guns (left)
def _heavy_mount():
    x0 = 0.89
    e = [box((x0, 4.18, -0.30), (0.97, 4.62, 0.36), "darksteel")]                   # base plate
    for y in (4.22, 4.58):
        for z in (-0.26, 0.32):
            e += prism((0.975, y, z), "x", 0.022, 0.015, 6, "steel")                 # bolts
    e += prism((1.04, 4.40, 0.05), "x", 0.17, 0.14, 12, "motor")                     # elevation motor
    for x in (0.99, 1.04, 1.09):
        e += prism((x, 4.40, 0.05), "x", 0.19, 0.014, 12, "darksteel")
    e += prism((1.10, 4.40, 0.05), "x", 0.172, 0.02, 12, "hazard")
    e.append(box((0.97, 4.56, -0.12), (1.10, 4.60, 0.22), "gunmetal"))              # gussets
    e.append(box((0.97, 4.20, -0.12), (1.10, 4.24, 0.22), "gunmetal"))
    e.append(box((0.97, 4.28, -0.36), (1.09, 4.46, -0.20), "darksteel"))             # feed port
    e.append(box((1.0, 4.46, -0.33), (1.06, 4.475, -0.23), "brass"))
    e.append(box((1.02, 4.585, 0.10), (1.06, 4.605, 0.14), "glow"))                  # status light
    return no_dent(e)


def _heavy_gun():
    e = prism((1.13, 4.40, 0.05), "x", 0.12, 0.04, 12, "steel")                      # trunnion boss
    e.append(box((1.13, 4.20, -0.55), (1.47, 4.60, 0.40), "gunmetal"))               # receiver
    e.append(box((1.11, 4.60, -0.58), (1.49, 4.65, 0.38), "armor"))                  # top shroud
    e.append(box((1.47, 4.18, -0.58), (1.52, 4.62, 0.38), "armor"))                  # outboard shroud
    e.append(plate((1.30, 4.66, 0.45), (0.38, 0.05, 0.16), "armor", (25.0, 0.0, 0.0)))  # front chamfer
    e.append(box((1.52, 4.48, -0.50), (1.525, 4.54, 0.30), "accent"))                # stripe
    e.append(box((1.18, 4.65, -0.48), (1.42, 4.66, -0.30), "hazard"))                # warning plate
    e += prism((1.30, 4.40, 0.55), "z", 0.17, 0.30, 12, "darksteel")                 # barrel drive housing
    e += prism((1.30, 4.40, 0.69), "z", 0.175, 0.02, 12, "glow")                     # drive ring light
    e.append(beam((1.30, 4.58, 0.70), (1.30, 4.56, 1.98), 0.20, 0.03, "vent"))       # heat shield
    e += prism((1.30, 4.40, 1.98), "z", 0.165, 0.06, 12, "steel", faces_end=False)   # barrel clamp
    e.append(box((1.28, 4.545, 1.93), (1.32, 4.58, 2.03), "steel"))                  # clamp to shield
    e += prism((1.30, 4.15, 0.12), "z", 0.045, 0.60, 8, "steel")                     # recoil buffer
    e.append(beam((1.13, 4.37, -0.30), (1.09, 4.37, -0.30), 0.12, 0.10, "darksteel"))  # feed inlet
    e.append(box((1.24, 4.44, -0.555), (1.36, 4.50, -0.55), "glow", faces=("north",)))  # ready light
    return e


def _heavy_barrels():
    """Local: spin axis along +Z from the drive housing."""
    e = prism((0, 0, 0.925), "z", 0.03, 1.85, 8, "darksteel")                        # spindle
    for k in range(6):
        a = 2 * math.pi * k / 6
        e += prism((0.085 * math.cos(a), 0.085 * math.sin(a), 0.925), "z", 0.032, 1.85, 8, "gunmetal")
    for z in (0.35, 1.05):
        e += prism((0, 0, z), "z", 0.135, 0.05, 12, "steel")                          # clamps
    e += prism((0, 0, 1.80), "z", 0.13, 0.08, 12, "darksteel", faces_end=False)      # muzzle ring
    return no_dent(e)


# ---------------------------------------------------------------- light guns (left)
def _light_mount():
    x = LGUN[0]
    e = prism((x, 4.885, 0.05), "y", 0.16, 0.05, 12, "darksteel")                   # base ring
    e += prism((x, 4.925, 0.05), "y", 0.13, 0.03, 12, "steel")                      # turntable
    for yx in (x - 0.11, x + 0.11):
        e.append(box((yx - 0.015, 4.94, -0.04), (yx + 0.015, 5.13, 0.14), "gunmetal"))  # yoke
    e += prism((x + 0.15, 5.08, 0.05), "x", 0.06, 0.06, 10, "motor")                # elevation motor
    e += prism((x + 0.19, 5.08, 0.05), "x", 0.05, 0.02, 10, "hazard")
    e.append(box((x + 0.20, 5.07, 0.04), (x + 0.205, 5.09, 0.06), "glow"))
    return no_dent(e)


def _light_gun():
    x, y = LGUN[0], LGUN[1]
    e = prism(LGUN, "x", 0.025, 0.25, 8, "steel")                                    # trunnion pin
    e.append(box((x - 0.08, 5.01, -0.35), (x + 0.08, 5.15, 0.20), "gunmetal"))       # receiver
    e.append(box((x - 0.085, 5.15, -0.30), (x + 0.085, 5.18, 0.18), "armor"))        # top cover
    e.append(box((x - 0.12, 4.98, 0.20), (x + 0.12, 5.20, 0.23), "armor"))           # gun shield
    e.append(box((x - 0.12, 5.18, 0.20), (x + 0.12, 5.20, 0.232), "accent"))
    e += prism((x, y, 0.46), "z", 0.045, 0.46, 8, "vent")                            # cooling jacket
    e += prism((x, y, 0.86), "z", 0.02, 0.34, 8, "darksteel")                        # barrel
    e += prism((x, y, 1.05), "z", 0.035, 0.06, 8, "steel")                           # muzzle
    e.append(box((x - 0.05, 5.18, -0.28), (x + 0.05, 5.26, -0.05), "accent"))        # ammo can
    e.append(box((x - 0.02, 5.18, 0.05), (x + 0.02, 5.24, 0.15), "darksteel"))       # sight
    e.append(box((x - 0.015, 5.205, 0.15), (x + 0.015, 5.225, 0.152), "glow", faces=("south",)))
    return e


def torso_parts():
    """Returns (torso parts, gun parts, segments, joints)."""
    torso: list[Part] = []
    _part(torso, Part("torso_frame", "Torso frame (hull core, hardpoints)", "structure", "waist_ring", "torso",
                      PIVOT, 650, 520, "fail", "Cracks: every gun mount shakes loose and aim wanders; at 0 the mech is wrecked",
                      shield=["torso_front", "torso_top"], damaged=False), _frame(), PIVOT)
    _part(torso, Part("torso_front", "Torso front armor (glacis, cheeks)", "armor", "torso_frame", "torso", PIVOT,
                      220, 420, "detach", "Torn off: the sensors and hull core take front hits directly"),
          _front(), PIVOT)
    _part(torso, Part("torso_top", "Torso roof armor (hatch)", "armor", "torso_frame", "torso", PIVOT,
                      140, 300, "detach", "Torn off: the hull core and light gun mounts take hits from above"),
          _top(), PIVOT)
    left = Part("torso_side_l", "Torso side armor (left)", "armor", "torso_frame", "torso", PIVOT,
                120, 320, "detach", "Torn off: the hull and the heavy gun's hardpoint take side hits directly")
    _part(torso, left, _side_l(), PIVOT)
    torso.append(_mirror(left))
    _part(torso, Part("sensors", "Sensors (viewport, camera pod, rangefinder)", "sensor", "torso_frame", "torso",
                      PIVOT, 25, 60, "fail", "Damaged: aim gets sloppy; at 0 the guns fire without the rangefinder",
                      shield=["torso_front"], damaged=False), _sensors(), PIVOT)
    _part(torso, Part("ammo_bustle", "Ammo bustle (magazine and feed chutes)", "ammo", "torso_frame", "torso",
                      PIVOT, 300, 220, "fail", "Feed jams with damage; at 0 the magazine cooks off and the heavy guns run dry"),
          _bustle(), PIVOT)
    _part(torso, Part("antenna", "Antenna mast", "sensor", "ammo_bustle", "torso", PIVOT, 4, 20, "detach",
                      "Shot off: no radio or radar", damaged=False), _antenna(), PIVOT)

    guns: list[Part] = []
    left = []
    _part(left, Part("heavy_mount_l", "Heavy gun mount (left)", "actuator", "torso_frame", "torso", HGUN,
                     70, 200, "fail", "Elevation motor weakens: the gun lifts slower; at 0 it stays where it was",
                     shield=["heavy_gun_l"], damaged=False), _heavy_mount(), HGUN)
    _part(left, Part("heavy_gun_l", "Heavy rotary cannon (left)", "weapon", "heavy_mount_l", "hgun_l", HGUN,
                     380, 260, "detach", "Damaged: slower fire; shot off with its barrels"), _heavy_gun(), HGUN)
    _part(left, Part("heavy_barrels_l", "Heavy cannon barrel cluster (left)", "weapon", "heavy_gun_l", "hgun_l",
                     HBARREL, 140, 160, "detach", "Bent: shots spread; shot off: the cannon cannot fire",
                     anim="spin_z", damaged=False), to_local(_heavy_barrels(), tuple(-c for c in HBARREL)), HBARREL)
    _part(left, Part("light_mount_l", "Light gun pintle (left)", "actuator", "torso_top", "torso", LGUN,
                     18, 80, "detach", "Torn off with its gun", damaged=False), _light_mount(), LGUN)
    _part(left, Part("light_gun_l", "Light machine gun (left)", "weapon", "light_mount_l", "lgun_l", LGUN,
                     35, 90, "detach", "Damaged: jams now and then; shot off: one gun fewer"), _light_gun(), LGUN)
    for p in left:
        guns.append(p)
    for p in left:
        guns.append(_mirror(p))

    segments = ["torso", "hgun_l", "hgun_r", "lgun_l", "lgun_r"]
    joints = {"waist": {"pivot": list(WAIST), "axis": "y", "parent": "pelvis", "child": "torso",
                        "range": [-180, 180], "label": "Waist"}}
    for t, s in (("l", 1), ("r", -1)):
        side = "L" if s > 0 else "R"
        joints[f"elev_h{t}"] = {"pivot": [s * HGUN[0], HGUN[1], HGUN[2]], "axis": "x", "parent": "torso",
                                "child": f"hgun_{t}", "range": H_RANGE, "label": f"Heavy {side}"}
        joints[f"elev_l{t}"] = {"pivot": [s * LGUN[0], LGUN[1], LGUN[2]], "axis": "x", "parent": "torso",
                                "child": f"lgun_{t}", "range": L_RANGE, "label": f"Light {side}"}
    return torso, guns, segments, joints
