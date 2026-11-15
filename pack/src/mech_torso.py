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
+Z). The heavy barrel cluster spins about its own Z axis ("spin_z" anim). The
roof hatch turns about its own X axis at its rear hinge ("hinge_x" anim;
negative opens it).
"""

from __future__ import annotations

import copy
import math

from mech_lib import MECH_SCALE, Elem, Part, beam, box, mirror_x, no_dent, plate, prism, to_local

WAIST = (0.0, 3.90, 0.0)              # torso yaw axis (vertical line through this point)
PIVOT = (0.0, 4.40, 0.0)              # pivot the hull parts are built around
HGUN = (1.30, 4.40, 0.05)             # left heavy gun trunnion (elevation axis, along X)
HBARREL = (1.30, 4.40, 0.70)          # left heavy barrel cluster: spin axis start (along Z)
LGUN = (0.45, 5.08, 0.05)             # left light gun trunnion
VIEW_X = 0.62                         # viewport half width
FLOOR_Y = 4.078                       # cabin floor (top of the grating)
# The pilot's chair is low and leans back RECLINE degrees, fighter style. A
# seated player's eyes are 1.03 m from the hips along the back, so reclined
# they are 1.03 cos(RECLINE) = 0.93 m above the seat, 1.15 m above the floor
# with the seat 0.22 m up; the head's top is about 1.38 m up, under the 1.43 m
# ceiling. The viewport spans 0.92..1.34 m.
SEAT_TOP = 0.22                       # real meters above the floor
RECLINE = 25.0                        # degrees the backrest (and the pilot) lean back
VIEW_Y = (FLOOR_Y + 0.92 / MECH_SCALE, FLOOR_Y + 1.34 / MECH_SCALE)  # viewport bottom and top
SEAT = (0.0, FLOOR_Y + SEAT_TOP / MECH_SCALE, 0.66 - 1.15 / MECH_SCALE)  # seat top center (design units)
_r = math.radians(RECLINE)
HIPS_Z = -0.11                        # the pilot's hips, real meters behind the seat's center
STICK_X, STICK_Z = 0.33, 0.15         # joysticks: out to each side and ahead of the seat's center (real m)
GRIP_UP = 0.415                       # grip center above the seat top (real m)


def pilot_grips():
    """The joystick grips' centers (design units, mech frame): [left, right]."""
    out = []
    for s in (1, -1):
        out.append((s * STICK_X / MECH_SCALE, SEAT[1] + GRIP_UP / MECH_SCALE, SEAT[2] + (STICK_Z + 0.0275) / MECH_SCALE))
    return out
EYE = (0.0, SEAT[1] + 1.03 * math.cos(_r) / MECH_SCALE,
       SEAT[2] + (HIPS_Z - 1.03 * math.sin(_r)) / MECH_SCALE)                       # pilot's eyes (design units)
ROOF_Y = 4.88                         # top of the roof plates
HATCH_Z = -0.68                       # roof hatch, over the ladder
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
    # The hull is a hollow cabin: floor, walls and ceiling are plates whose
    # inner faces show from inside. The front wall has the viewport opening.
    e.append(box((-0.80, 4.03, -0.95), (0.80, 4.07, 0.70), "gunmetal"))              # floor
    e += _with_hatch_hole(-0.80, 0.80, 4.76, 4.80, -0.95, 0.70, "gunmetal")          # ceiling
    for s in (1, -1):
        x0, x1 = sorted((s * 0.76, s * 0.80))
        e.append(box((x0, 4.07, -0.95), (x1, 4.76, 0.70), "gunmetal"))               # side walls
        x0, x1 = sorted((s * VIEW_X, s * 0.76))
        e.append(box((x0, VIEW_Y[0], 0.66), (x1, VIEW_Y[1], 0.70), "gunmetal"))     # beside the viewport
    e.append(box((-0.76, 4.07, -0.95), (0.76, 4.76, -0.91), "gunmetal"))             # rear wall
    e.append(box((-0.76, 4.07, 0.66), (0.76, VIEW_Y[0], 0.70), "gunmetal"))          # front wall, below
    e.append(box((-0.76, VIEW_Y[1], 0.66), (0.76, 4.76, 0.70), "gunmetal"))          # front wall, above
    e.append(box((-0.72, 4.00, -0.88), (0.72, 4.04, 0.62), "darksteel"))             # belly plate
    for s in (1, -1):                                                                 # hardpoint blocks
        x0, x1 = sorted((s * 0.80, s * 0.90))
        e.append(box((x0, 4.24, -0.16), (x1, 4.56, 0.26), "darksteel"))
        x0, x1 = sorted((s * 0.42, s * 0.48))
        e.append(box((x0 - 0.0, 4.80, -0.10), (x1, 4.88, 0.20), "darksteel"))       # roof hardpoints
    return no_dent(e)


def _front():
    y0, y1 = VIEW_Y
    e = [beam((0.0, 4.05, 0.70), (0.0, y0 - 0.03, 0.98), 1.56, 0.07, "armor"),      # lower glacis
         beam((0.0, y1 + 0.03, 0.98), (0.0, 4.87, 0.60), 1.56, 0.07, "armor")]       # upper glacis
    # the viewport tunnel from the cabin's front wall out to the visor
    e.append(box((-VIEW_X - 0.04, y0 - 0.03, 0.70), (VIEW_X + 0.04, y0, 0.99), "darksteel"))  # sill
    e.append(box((-VIEW_X - 0.04, y1, 0.70), (VIEW_X + 0.04, y1 + 0.03, 0.99), "darksteel"))  # lintel
    for s in (1, -1):
        x0, x1 = sorted((s * VIEW_X, s * (VIEW_X + 0.04)))
        e.append(box((x0, y0, 0.70), (x1, y1, 0.99), "darksteel"))                    # jambs
    up = norm2((0.98 - 0.60, 4.87 - (y1 + 0.03)))                                     # upper glacis outward normal (y, z)
    lo = norm2((-(0.98 - 0.70), (y0 - 0.03) - 4.05))                                  # lower glacis outward normal (y, z)
    for s in (1, -1):
        p0 = (s * 0.52, y1 + 0.05 + up[0] * 0.04, 0.95 + up[1] * 0.04)
        p1 = (s * 0.52, 4.85 + up[0] * 0.04, 0.65 + up[1] * 0.04)
        e.append(beam(p0, p1, 0.07, 0.012, "accent"))                                # stripes
        e.append(plate((s * 0.80, 4.45, 0.78), (0.06, 0.82, 0.44), "armor", (0.0, -s * 25.0, 0.0)))  # cheeks
        for y in (4.15, 4.36):
            z = _glacis_z(y)
            e += prism((s * 0.62, y + lo[0] * 0.04, z + lo[1] * 0.04), "z", 0.025, 0.02, 6, "steel")  # bolts
    a, b = 4.13, 4.29
    e.append(beam((0.0, a + lo[0] * 0.04, _glacis_z(a) + lo[1] * 0.04), (0.0, b + lo[0] * 0.04, _glacis_z(b) + lo[1] * 0.04),
                  0.30, 0.012, "hazard"))                                             # warning plate
    return e


def norm2(v):
    n = math.hypot(*v)
    return (v[0] / n, v[1] / n)


def _glacis_z(y):
    """z of the lower glacis's center plane at height y."""
    y0 = VIEW_Y[0] - 0.03
    return 0.70 + (0.98 - 0.70) * (y - 4.05) / (y0 - 4.05)


HATCH_HALF = 0.22                     # the hatch is a square this far either side of its center


def _with_hatch_hole(x0, x1, y0, y1, z0, z1, mat):
    """A flat slab with a square hole where the hatch is."""
    hz, h = HATCH_Z, HATCH_HALF
    return [box((x0, y0, hz + h), (x1, y1, z1), mat),           # in front of the hole
            box((x0, y0, z0), (x1, y1, hz - h), mat),           # behind it
            box((x0, y0, hz - h), (-h, y1, hz + h), mat),       # to its right
            box((h, y0, hz - h), (x1, y1, hz + h), mat)]        # to its left


def _hatch():
    """The roof hatch, a square armored lid over the cabin, hinged at its front
    edge (the part's pivot); it opens forward by turning about X, so the way in
    from the back stays clear."""
    hz, h = HATCH_Z, HATCH_HALF
    e = [box((-h + 0.01, 4.86, hz - h + 0.01), (h - 0.01, 4.90, hz + h - 0.01), "armor"),   # lid
         box((-h + 0.05, 4.90, hz - h + 0.05), (h - 0.05, 4.91, hz + h - 0.05), "accent"),  # raised panel
         box((-0.08, 4.91, hz + 0.02), (0.08, 4.94, hz + 0.06), "steel"),                     # handle
         box((-h + 0.03, 4.84, hz - h + 0.03), (h - 0.03, 4.86, hz + h - 0.03), "darksteel")]  # underside
    for x in (-0.15, 0.15):
        e += prism((x, 4.88, hz + h), "x", 0.02, 0.08, 6, "steel")                          # hinge knuckles
    return e


def _top():
    e = _with_hatch_hole(-0.78, 0.78, 4.80, 4.86, -0.95, 0.62, "armor")              # roof (hatch hole)
    e += [
         box((-0.70, 4.86, -0.90), (-0.28, 4.88, -0.20), "armor"),                   # raised panels
         box((0.28, 4.86, -0.90), (0.70, 4.88, -0.20), "armor")]
    hz, h = HATCH_Z, HATCH_HALF
    for a, b in (((-h - 0.05, hz + h), (h + 0.05, hz + h + 0.05)), ((-h - 0.05, hz - h - 0.05), (h + 0.05, hz - h)),
                 ((-h - 0.05, hz - h), (-h, hz + h)), ((h, hz - h), (h + 0.05, hz + h))):
        e.append(box((a[0], 4.86, a[1]), (b[0], 4.875, b[1]), "hazard"))           # hatch rim
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
    # The visor only has its outer face, so from inside the cabin it is see-through.
    e = [box((-VIEW_X, VIEW_Y[0], 0.985), (VIEW_X, VIEW_Y[1], 0.99), "visor", faces=("south",)),
         box((-VIEW_X, VIEW_Y[0] - 0.02, 0.99), (VIEW_X, VIEW_Y[0] - 0.01, 0.995), "glow", faces=("south",))]
    e.append(box((-0.16, 4.86, 0.30), (0.16, 5.00, 0.55), "darksteel"))             # camera pod
    for x in (-0.08, 0.08):
        e += prism((x, 4.93, 0.565), "z", 0.045, 0.03, 8, "steel")
        e += prism((x, 4.93, 0.58), "z", 0.03, 0.01, 8, "visor")
    e.append(box((-0.02, 4.995, 0.40), (0.02, 5.01, 0.52), "glow"))                 # rangefinder light
    e.append(box((-0.05, 5.00, 0.32), (0.05, 5.06, 0.46), "gunmetal"))               # rangefinder
    return no_dent(e)


def _cockpit():
    """The cabin fittings, sized in real meters (they do not grow with the
    mech): a pilot's chair with a joystick on each armrest, and three screens,
    one under the viewport and one angled in from each front corner."""
    k = MECH_SCALE
    z0 = SEAT[2]

    def P(x, y, z):
        """Real meters, from the floor under the seat's center, to design units."""
        return (x / k, FLOOR_Y + y / k, z0 + z / k)

    def B(a, b, mat, **kw):
        return box(P(*a), P(*b), mat, **kw)

    def L(c, size, mat, rot, **kw):
        return plate(P(*c), tuple(v / k for v in size), mat, rot, **kw)

    def M(p, q, w, h, mat, **kw):
        return beam(P(*p), P(*q), w / k, h / k, mat, **kw)

    st = SEAT_TOP
    e = [box((-0.74, 4.07, -0.89), (0.74, FLOOR_Y, 0.64), "vent", faces=("up",))]    # floor grating
    # chair
    e.append(B((-0.26, 0.0, -0.26), (0.26, 0.04, 0.26), "steel"))                      # base plate
    e.append(B((-0.06, 0.04, -0.06), (0.06, st - 0.12, 0.06), "darksteel"))            # post
    e.append(L((0.0, st - 0.06, 0.0), (0.56, 0.12, 0.50), "seat", (-8.0, 0.0, 0.0)))   # seat pan, front up

    def back(y, z):
        """A point on the reclined back: y up it and z out of it, from the hinge
        at the rear of the seat."""
        r = math.radians(-RECLINE)
        return (y * math.cos(r) - z * math.sin(r) + st, y * math.sin(r) + z * math.cos(r) - 0.24)

    rec = (-RECLINE, 0.0, 0.0)
    y, z = back(0.40, -0.05)
    e.append(L((0.0, y, z), (0.54, 0.80, 0.10), "seat", rec))                           # backrest
    y, z = back(1.00, -0.18)
    e.append(L((0.0, y, z), (0.32, 0.24, 0.10), "seat", rec))                           # headrest (behind the head)
    y, z = back(0.84, -0.12)
    e.append(L((0.0, y, z), (0.10, 0.20, 0.06), "darksteel", rec))                      # headrest mount
    y, z = back(0.40, -0.12)
    e.append(L((0.0, y, z), (0.48, 0.72, 0.04), "darksteel", rec))                      # back shell
    y, z = back(0.0, -0.06)
    e.append(L((0.0, y, z), (0.40, 0.10, 0.12), "darksteel", rec))                      # hinge
    for s in (1, -1):
        x0, x1 = sorted((s * 0.29, s * 0.37))
        e.append(B((x0, st + 0.12, -0.22), (x1, st + 0.18, 0.22), "gunmetal"))           # armrest
        e.append(B((x0 + 0.02, st - 0.12, -0.16), (x1 - 0.02, st + 0.12, -0.10), "darksteel"))  # armrest support
        y, z = back(0.30, 0.02)
        e.append(L((s * 0.27, y, z), (0.06, 0.60, 0.14), "seat", rec))                  # side bolster
        # joystick at the front of the armrest
        jx, jz = s * STICK_X, STICK_Z
        e += prism(P(jx, st + 0.20, jz), "y", 0.04 / k, 0.04 / k, 8, "darksteel")          # boot
        e.append(M((jx, st + 0.20, jz), (jx, st + 0.36, jz + 0.03), 0.025, 0.025, "steel"))  # stick
        e.append(B((jx - 0.025, st + 0.36, jz - 0.005), (jx + 0.025, st + 0.47, jz + 0.06), "accent"))  # grip
        e.append(B((jx - 0.012, st + 0.44, jz + 0.06), (jx + 0.012, st + 0.46, jz + 0.068), "glow"))  # fire button
    # screens
    wall = 0.66 * k - z0 * k                                                            # front wall, from the seat
    e.append(L((0.0, 0.66, wall - 0.05), (0.62, 0.40, 0.04), "darksteel", (-12.0, 0.0, 0.0)))   # center bezel
    e.append(L((0.0, 0.66, wall - 0.075), (0.56, 0.34, 0.01), "screen", (-12.0, 0.0, 0.0), faces=("north",)))
    e.append(B((-0.05, 0.0, wall - 0.10), (0.05, 0.46, wall - 0.02), "darksteel"))     # center stand
    for s in (1, -1):
        c = (s * 0.78, 0.66, wall - 0.40)
        yaw = s * 35.0
        e.append(L(c, (0.44, 0.30, 0.04), "darksteel", (-10.0, yaw, 0.0)))              # side bezel
        off = (-s * 0.025 * math.sin(math.radians(35.0)), 0.0, -0.025 * math.cos(math.radians(35.0)))
        e.append(L(tuple(a + b for a, b in zip(c, off)), (0.38, 0.24, 0.01), "screen", (-10.0, yaw, 0.0),
                   faces=("north",)))
        e.append(B((c[0] - 0.04, 0.0, c[2] - 0.04), (c[0] + 0.04, c[1] - 0.15, c[2] + 0.04), "darksteel"))  # stand
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


# The boarding ladder, on the back of the ammo bustle (design units). Its rungs
# sit LADDER_STEP real meters apart, counted up from the ground under a
# kneeling mech (GROUND_K, the mech frame at rest), so the climb in
# mech_pilot.py can put hands and feet on them. The upper section is fixed to
# the bustle's rear plate and ends in grab handles over the lid; the drop
# section hangs below it and slides out of a tray under the bustle when the
# mech kneels (anim "extend_y": scaled down from its top).
LADDER_Z = -1.581                     # the rungs' plane, just behind the leaning rear plate
LADDER_X = 0.13                       # upper rails, either side of the centerline
DROP_X = 0.11                         # drop section rails (inside the upper ones)
LADDER_TOP = 4.06                     # where the drop section hangs from
LADDER_STEP = 0.30                    # real meters between rungs


def ladder_rungs(y0: float, y1: float, ground: float) -> list[float]:
    """Rung heights (design units) between y0 and y1 on the grid counted up
    from `ground` (design units)."""
    step = LADDER_STEP / MECH_SCALE
    k = math.ceil((y0 - ground) / step - 1e-6)
    out = []
    while ground + k * step <= y1 + 1e-6:
        if k >= 1:
            out.append(ground + k * step)
        k += 1
    return out


def _ladder(ground: float):
    """The fixed upper section: rails on standoffs, rungs, grab handles that
    curve over the lid, and the tray the drop section stows in."""
    z, w = LADDER_Z, LADDER_X
    e = []
    for x in (-w, w):
        e.append(box((x - 0.01, 4.04, z - 0.01), (x + 0.01, 4.95, z + 0.01), "steel"))        # rail
        e.append(box((x - 0.01, 4.94, z), (x + 0.01, 4.96, -1.40), "steel"))                 # handle, over the lid
        e.append(box((x - 0.01, 4.76, -1.41), (x + 0.01, 4.95, -1.39), "steel"))             # handle foot
        for y, zp in ((4.15, -1.462), (4.65, -1.535)):
            e.append(box((x - 0.008, y - 0.008, z + 0.01), (x + 0.008, y + 0.008, zp), "darksteel"))  # standoff
    for y in ladder_rungs(4.10, 4.90, ground):
        e.append(box((-w, y - 0.006, z - 0.006), (w, y + 0.006, z + 0.006), "darksteel"))     # rung
    e.append(box((-0.16, 3.98, z - 0.04), (0.16, 4.08, z + 0.04), "gunmetal"))               # tray
    e.append(box((-0.17, 3.975, z - 0.045), (0.17, 3.985, z + 0.045), "hazard"))
    return e


def _ladder_drop(ground: float):
    """The drop section, deployed: rails from the tray down to just above the
    ground under a kneeling mech, with rungs and two feet."""
    z, w = LADDER_Z, DROP_X
    bottom = ground + 0.10 / MECH_SCALE
    e = []
    for x in (-w, w):
        e.append(box((x - 0.009, bottom, z - 0.009), (x + 0.009, LADDER_TOP, z + 0.009), "steel"))
        e.append(box((x - 0.02, bottom - 0.01, z - 0.03), (x + 0.02, bottom, z + 0.03), "rubber"))  # foot
    for y in ladder_rungs(bottom, LADDER_TOP - 0.02, ground):
        e.append(box((-w, y - 0.006, z - 0.006), (w, y + 0.006, z + 0.006), "darksteel"))
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


def torso_parts(ground_k: float = 0.0):
    """Returns (torso parts, gun parts, segments, joints). ground_k: the ground
    under a kneeling mech, in the mech frame at rest (design units), which the
    boarding ladder reaches down to."""
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
    hinge = (0.0, 4.88, HATCH_Z + HATCH_HALF)
    _part(torso, Part("hatch", "Roof hatch (hinged lid over the cabin)", "armor", "torso_top", "torso", hinge,
                      20, 120, "detach", "Torn off: the cabin is open to the sky", anim="hinge_x"), _hatch(), hinge)
    left = Part("torso_side_l", "Torso side armor (left)", "armor", "torso_frame", "torso", PIVOT,
                120, 320, "detach", "Torn off: the hull and the heavy gun's hardpoint take side hits directly")
    _part(torso, left, _side_l(), PIVOT)
    torso.append(_mirror(left))
    _part(torso, Part("cockpit", "Cockpit (pilot's chair, joysticks, screens)", "interior", "torso_frame", "torso",
                      PIVOT, 60, 120, "fail", "Damaged: screens flicker and controls lag; at 0 the pilot flies blind",
                      shield=["torso_front", "torso_top"], damaged=False), _cockpit(), PIVOT)
    _part(torso, Part("sensors", "Sensors (viewport, camera pod, rangefinder)", "sensor", "torso_frame", "torso",
                      PIVOT, 25, 60, "fail", "Damaged: aim gets sloppy; at 0 the guns fire without the rangefinder",
                      shield=["torso_front"], damaged=False), _sensors(), PIVOT)
    _part(torso, Part("ammo_bustle", "Ammo bustle (magazine and feed chutes)", "ammo", "torso_frame", "torso",
                      PIVOT, 300, 220, "fail", "Feed jams with damage; at 0 the magazine cooks off and the heavy guns run dry"),
          _bustle(), PIVOT)
    _part(torso, Part("ladder", "Boarding ladder (upper section, handles, tray)", "structure", "ammo_bustle", "torso",
                      PIVOT, 25, 60, "detach", "Shot off: no way up while kneeling", damaged=False),
          _ladder(ground_k), PIVOT)
    drop = (0.0, LADDER_TOP, LADDER_Z)
    _part(torso, Part("ladder_drop", "Boarding ladder (drop section)", "structure", "ladder", "torso", drop,
                      20, 40, "detach", "Shot off: no way up while kneeling", anim="extend_y", damaged=False),
          _ladder_drop(ground_k), drop)
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
