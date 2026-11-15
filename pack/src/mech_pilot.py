"""The pilot model: the player's own skin, reclined in the mech's cockpit.

Ported from tc-rally_game's driver model (pack/src/driver.py there). Every
body part is an item display holding the pilot's player head; the core shader
in pack/assets/minecraft/shaders/core/entity.* draws a head as another part
(torso, arm, leg) when the display's brightness override marks it (sky 0,
block = part id), so a part is just a head scaled to the part's size.

Every part is the same unit item (a head as a 1 x 1 x 1 box) and is posed
live by tc/pilot.tc from a figure pose: the hips' center, the body's lean, and
where the feet and hands are. Limbs are straight Minecraft limbs from the hip
or shoulder to their end point. The head looks where the player looks, and the
player's camera sits at its center (the shader drops a head with the camera
inside it).

Boarding is baked here as a timeline of figure poses in the mech frame at
rest (with the mech kneeling and the turret facing ahead), BOARD_RATE samples
a second: from standing at the foot of the boarding ladder, hand over hand up
its rungs, over the grab handles onto the ammo bustle, a few steps to the
roof hatch, sit on its rim, lower in and slide forward into the chair. Its
last sample is the seated pose (hands on the joysticks). Getting out plays it
backwards. The walk from the player to the ladder is done live.

Writes (called from mech_parts.py):
  pack/assets/mech/items/pilot/unit.json    the head as a 1 x 1 x 1 box at the origin
  pack/assets/mech/items/empty.json         an item that draws nothing (held while piloting)
  tc/pilot_data.tc                          the timeline and sizes for the game code
"""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ITEMS = ROOT / "pack/assets/mech/items"

PX = 0.05625          # one skin pixel in meters: a real Minecraft player (32 px = 1.8 m)
PART_IDS = {"head": 1, "torso": 2, "arm_r": 3, "arm_l": 4, "leg_r": 5, "leg_l": 6}
LEG_LIFT = 8.0        # legs point forward along the seat pan, this much up (degrees)
LEG_SPLAY = 4.0       # and this much outward


def add(a, b): return tuple(x + y for x, y in zip(a, b))
def sub(a, b): return tuple(x - y for x, y in zip(a, b))
def mul(a, k): return tuple(x * k for x in a)
def dot(a, b): return sum(x * y for x, y in zip(a, b))
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def norm(a): return mul(a, 1 / math.sqrt(dot(a, a)))


def matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def translate(t):
    return [[1, 0, 0, t[0]], [0, 1, 0, t[1]], [0, 0, 1, t[2]], [0, 0, 0, 1]]


def diag(x, y, z):
    return [[x, 0, 0, 0], [0, y, 0, 0], [0, 0, z, 0], [0, 0, 0, 1]]


def columns(cx, cy, cz, t):
    return [[cx[0], cy[0], cz[0], t[0]], [cx[1], cy[1], cz[1], t[1]], [cx[2], cy[2], cz[2], t[2]], [0, 0, 0, 1]]


def swing(d):
    """Axes (left, up, forward) of a limb hanging along d: the standing frame
    turned by the smallest rotation that takes straight down to d."""
    d = norm(d)
    a = (0.0, -1.0, 0.0)
    k = cross(a, d)
    c = dot(a, d)
    f = (0.0, 0.0, 1.0)
    kf = cross(k, f)
    fwd = norm(add(add(f, kf), mul(cross(k, kf), 1 / (1 + c))))
    up = mul(d, -1)
    return cross(up, fwd), up, fwd


# The unit head: skull model space to a 1 x 1 x 1 box centered at the origin
# with the face to -Z and the player's left to -X, as seen after the item
# renderer's -0.5 shift and the display's 180 degree turn about Y (as in the
# rally driver).
RY180 = diag(-1, 1, -1)
Q = matmul(translate((0, -0.5, 0)), diag(-2, -2, 2))


def item_transform(placement):
    return matmul(matmul(translate((0.5, 0.5, 0.5)), RY180), matmul(placement, Q))


def placement(l, u, f, size, center):
    sx, sy, sz = (n * PX for n in size)
    return columns(mul(l, -sx), mul(u, sy), mul(f, -sz), center)


def head_item(matrix):
    flat = [round(matrix[i][j], 6) + 0.0 for i in range(4) for j in range(4)]
    return {"model": {"type": "minecraft:special", "base": "minecraft:item/template_skull",
                      "model": {"type": "minecraft:player_head"}, "transformation": flat}}


def pose(seat, recline, hips_z, grips):
    """Parts posed in the mech frame (real meters): seat top center, the
    recline (degrees), the hips' offset behind the seat center, and the
    joystick grips [left, right]."""
    hip = add(seat, (0.0, 0.06, hips_z))
    r = math.radians(recline)
    up_t = (0.0, math.cos(r), -math.sin(r))
    fwd_t = (0.0, math.sin(r), math.cos(r))
    left = (1.0, 0.0, 0.0)
    neck = add(hip, mul(up_t, 12 * PX))
    parts = {"torso": (left, up_t, fwd_t, (8, 12, 4), add(hip, mul(up_t, 6 * PX)))}
    for name, s in (("leg_l", 1), ("leg_r", -1)):
        piv = add(hip, mul(left, s * 2 * PX))
        lf, sp = math.radians(LEG_LIFT), math.radians(LEG_SPLAY)
        d = (s * math.sin(sp), math.sin(lf), math.cos(lf) * math.cos(sp))
        l, u, f = swing(d)
        parts[name] = (l, u, f, (4, 12, 4), add(piv, mul(norm(d), 6 * PX)))
    shoulders = {"arm_l": add(sub(neck, mul(up_t, 2 * PX)), mul(left, 6 * PX)),
                 "arm_r": add(sub(neck, mul(up_t, 2 * PX)), mul(left, -6 * PX))}
    for name, grip in (("arm_l", grips[0]), ("arm_r", grips[1])):
        s0 = shoulders[name]
        d = sub(grip, s0)
        length = math.sqrt(dot(d, d))
        k = min(max(length / (10 * PX), 0.85), 1.2)     # stretch a little to reach (as the rally arms)
        l, u, f = swing(d)
        parts[name] = (l, u, f, (4, 12 * k, 4), add(s0, mul(norm(d), 4 * PX * k)))
    head_center = add(neck, mul(up_t, 4 * PX))
    return parts, neck, up_t, head_center


BOARD_RATE = 10        # timeline samples per second
CLIMB_SPEED = 1.6      # m/s up the ladder
HIP_H = 12 * PX        # hips above the soles, standing
SHOULDER_H = 10 * PX   # shoulder pivots above the hips


def board_timeline(g: dict, seat, recline, hips_z, grips) -> list[list[float]]:
    """The boarding timeline: per sample [hips x y z, lean (degrees, + forward),
    left foot, right foot, left hand, right hand], all in the mech frame at rest
    (real meters). g: the geometry (real meters): ground under the kneeling
    mech, the rungs' plane z and spacing, the bustle lid top, the handles'
    top, roof top, the roof's back edge z, the hatch hole's z range and the
    cabin floor."""
    G, ZR, step = g["ground"], g["rung_z"], g["rung_step"]
    hip_z = ZR - 0.30          # hips hang behind the rungs
    foot_z = ZR - 0.08         # soles on the rungs
    hand_z = ZR - 0.03

    def hang(h, x):
        """A hand hanging at the side of hips h."""
        return (x, h[1] + SHOULDER_H - 0.62, h[2])

    def frame(h, lean, fl, fr, hl, hr):
        return [*h, lean, *fl, *fr, *hl, *hr]

    keys = []                                          # (seconds to get here, frame)
    h0 = (0.0, G + HIP_H, hip_z)
    keys.append((0.0, frame(h0, 0, (0.12, G, hip_z), (-0.12, G, hip_z), hang(h0, 0.33), hang(h0, -0.33))))

    # the climb: each limb holds a rung for half a cycle, then moves up two;
    # a foot and the opposite hand move together
    def limb(c, base, phase):
        x = c - G + phase
        n = math.floor(x / (2 * step))
        f = x / (2 * step) - n
        level = base + n * 2 * step - phase + step
        if f < 0.5:
            return level, 0.0
        u = (f - 0.5) * 2
        return level + 2 * step * (u * u * (3 - 2 * u)), math.sin(math.pi * u)

    def climb(c):
        h = (0.0, c + HIP_H, hip_z)
        out = []
        for x, base, phase, z in ((0.12, G, step, foot_z), (-0.12, G, 0.0, foot_z),
                                  (0.20, G + 1.2, 0.0, hand_z), (-0.20, G + 1.2, step, hand_z)):
            y, lift = limb(c, base, phase)
            out.append((x, y, z - 0.12 * lift))
        return frame(h, 0, *out)

    c_end = g["lid"] - 1.9
    n = max(2, round((c_end - G) / CLIMB_SPEED * BOARD_RATE))
    for i in range(n + 1):
        keys.append((0.3 if i == 0 else 1 / BOARD_RATE, climb(G + (c_end - G) * i / n)))

    lid, roof, top = g["lid"], g["roof"], g["handle_top"]
    back, h0z, h1z, floor = g["roof_back"], g["hole"][0], g["hole"][1], g["floor"]
    # over the handles onto the bustle lid
    keys.append((0.45, frame((0, lid - 0.05, hip_z), 0, (0.12, lid - 0.40, foot_z), (-0.12, lid - 0.70, foot_z),
                             (0.20, top, hand_z + 0.05), (-0.20, top, hand_z + 0.05))))
    keys.append((0.5, frame((0, lid + 0.55, ZR + 0.07), 35, (0.12, lid, ZR + 0.27), (-0.12, lid - 0.10, foot_z),
                            (0.25, lid, ZR + 0.62), (-0.25, lid, ZR + 0.62))))
    h = (0, lid + HIP_H, ZR + 0.47)
    keys.append((0.5, frame(h, 0, (0.12, lid, h[2]), (-0.12, lid, h[2]), hang(h, 0.33), hang(h, -0.33))))
    # two steps to the hatch
    h = (0, lid + HIP_H + 0.03, (ZR + 0.47 + back - 0.25) / 2)
    keys.append((0.35, frame(h, 0, (0.12, lid, h[2] + 0.22), (-0.12, lid, h[2] - 0.22),
                             (0.33, h[1] + SHOULDER_H - 0.6, h[2] - 0.15), (-0.33, h[1] + SHOULDER_H - 0.6, h[2] + 0.15))))
    h = (0, lid + HIP_H, back - 0.25)
    keys.append((0.35, frame(h, 0, (0.12, lid, h[2]), (-0.12, lid, h[2]), hang(h, 0.33), hang(h, -0.33))))
    # sit on the hatch rim, legs in the hole
    keys.append((0.5, frame((0, roof + 0.07, (back + h0z) / 2), -10, (0.12, roof - 0.45, (h0z + h1z) / 2 - 0.05),
                            (-0.12, roof - 0.45, (h0z + h1z) / 2 - 0.05), (0.55, roof, back + 0.02), (-0.55, roof, back + 0.02))))
    # down through it onto the cabin floor, holding the rim
    hz = (h0z + h1z) / 2 - 0.08
    keys.append((0.7, frame((0, floor + HIP_H, hz), 0, (0.12, floor, hz + 0.1), (-0.12, floor, hz + 0.1),
                            (0.5, roof, hz - 0.2), (-0.5, roof, hz - 0.2))))
    # crouch and slide forward under the roof into the chair
    parts, neck, up_t, head_center = pose(seat, recline, hips_z, grips)
    hip = add(seat, (0.0, 0.06, hips_z))
    hz2 = (h1z + hip[2]) / 2
    keys.append((0.6, frame((0, floor + 0.38, hz2), -30, (0.14, floor + 0.04, hip[2] - 0.35), (-0.14, floor + 0.04, hip[2] - 0.35),
                            (0.3, floor + 0.70, hz2 + 0.2), (-0.3, floor + 0.70, hz2 + 0.2))))
    feet = []
    for s_ in (1, -1):
        piv = add(hip, (s_ * 2 * PX, 0.0, 0.0))
        lf, sp = math.radians(LEG_LIFT), math.radians(LEG_SPLAY)
        d = (s_ * math.sin(sp), math.sin(lf), math.cos(lf) * math.cos(sp))
        feet.append(add(piv, mul(norm(d), 12 * PX)))
    keys.append((0.6, frame(hip, -recline, feet[0], feet[1], grips[0], grips[1])))

    # sample: eased between keys
    times = [0.0]
    for dt, _ in keys[1:]:
        times.append(times[-1] + dt)
    total = times[-1]
    out = []
    count = round(total * BOARD_RATE)
    for i in range(count + 1):
        t = min(total, i / BOARD_RATE)
        j = max(k for k in range(len(times)) if times[k] <= t + 1e-9)
        if j >= len(keys) - 1:
            out.append(keys[-1][1])
            continue
        u = (t - times[j]) / (times[j + 1] - times[j])
        if keys[j + 1][0] > 1.5 / BOARD_RATE:             # the climb is sampled already; ease the rest
            u = u * u * (3 - 2 * u)
        a, b = keys[j][1], keys[j + 1][1]
        out.append([p + (q - p) * u for p, q in zip(a, b)])
    if out[-1] != keys[-1][1]:
        out.append(keys[-1][1])
    return [[round(v, 3) for v in row] for row in out]


def fmt(x: float) -> str:
    s = f"{x:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def write_pilot(timeline: list[list[float]], ladder_foot) -> None:
    items = ITEMS / "pilot"
    items.mkdir(parents=True, exist_ok=True)
    for old in items.glob("*.json"):
        old.unlink()
    (items / "unit.json").write_text(json.dumps(head_item(item_transform(diag(1, 1, 1))), indent=1) + "\n")
    (ITEMS / "empty.json").write_text(json.dumps({"model": {"type": "minecraft:empty"}}, indent=1) + "\n")
    rows = ",\n        ".join('"' + " ".join(fmt(v) for v in row) + '"' for row in timeline)
    ids = ", ".join(str(PART_IDS[n]) for n in ("head", "torso", "arm_r", "arm_l", "leg_r", "leg_l"))
    tc = (
        "// Generated by pack/src/mech_pilot.py: do not edit.\n"
        "// The pilot model: sizes, and the boarding timeline in the mech frame at rest\n"
        "// (+X left, +Y up, +Z forward, m; the mech kneeling, the turret ahead).\n\n"
        "/** One skin pixel (m), and the timeline's samples per second. */\n"
        "declare global pPx: num;\n"
        "declare global pRate: num;\n\n"
        "function loadPilotPose {\n"
        f"    global pPx = {PX};\n"
        f"    global pRate = {BOARD_RATE};\n"
        "}\n\n"
        "/** The shader's part ids, in display order: head, torso, right arm, left\n"
        " * arm, right leg, left leg. */\n"
        f"function pilotPartIds(): list {{\n    return [{ids}];\n}}\n\n"
        "/** Where the walk from the player ends (the soles' center at the foot of\n"
        " * the ladder, on the ground under the kneeling mech). */\n"
        f"function pilotLadderFoot(): vec {{\n    return vec({', '.join(fmt(c) for c in ladder_foot)});\n}}\n\n"
        "/** Boarding, sample by sample: \"hips x y z, lean (degrees, + forward), left\n"
        " * foot x y z, right foot, left hand, right hand\". The last is seated. */\n"
        f"function pilotBoardPath(): list {{\n    return [\n        {rows}\n    ];\n}}\n"
    )
    (ROOT / "tc/pilot_data.tc").write_text(tc)
