"""The pilot model: the player's own skin, reclined in the mech's cockpit.

Ported from tc-rally_game's driver model (pack/src/driver.py there). Every
body part is an item display holding the pilot's player head; the core shader
in pack/assets/minecraft/shaders/core/entity.* draws a head as another part
(torso, arm, leg) when the display's brightness override marks it (sky 0,
block = part id), so a part is just a head scaled to the part's size.

Torso, arms and legs never move relative to the torso segment (the hands rest
on the joysticks), so their pose is baked into their item models, posed in
the mech frame at rest; their displays take the torso segment's matrix. The
head is posed by tc/pilot.tc every tick: it looks where the player looks. The
player's camera sits at the head's center (the shader drops a head with the
camera inside it).

Writes (called from mech_parts.py):
  pack/assets/mech/items/pilot/unit.json    the head as a 1 x 1 x 1 box at the origin
  pack/assets/mech/items/pilot/<part>.json  torso, arms and legs, posed in the mech frame
  pack/assets/mech/items/empty.json         an item that draws nothing (held while piloting)
  tc/pilot_data.tc                          the pose for the game code
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


def fmt(x: float) -> str:
    s = f"{x:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def write_pilot(seat, recline, hips_z, grips) -> None:
    parts, neck, up_t, head_center = pose(seat, recline, hips_z, grips)
    items = ITEMS / "pilot"
    items.mkdir(parents=True, exist_ok=True)
    for old in items.glob("*.json"):
        old.unlink()
    (items / "unit.json").write_text(json.dumps(head_item(item_transform(diag(1, 1, 1))), indent=1) + "\n")
    for name, (l, u, f, size, c) in parts.items():
        (items / f"{name}.json").write_text(json.dumps(head_item(item_transform(placement(l, u, f, size, c))),
                                                       indent=1) + "\n")
    (ITEMS / "empty.json").write_text(json.dumps({"model": {"type": "minecraft:empty"}}, indent=1) + "\n")

    def v(name, p):
        return f"    global {name} = vec({fmt(p[0])}, {fmt(p[1])}, {fmt(p[2])});\n"

    rigid = ", ".join(f'"mech:pilot/{n} {PART_IDS[n]}"' for n in ("torso", "arm_r", "arm_l", "leg_r", "leg_l"))
    tc = (
        "// Generated by pack/src/mech_pilot.py: do not edit.\n"
        "// The pilot model's pose in the mech frame at rest (+X left, +Y up, +Z forward, m);\n"
        "// it turns with the torso segment.\n\n"
        "/** One skin pixel (m); the neck, the torso's up axis, and the head's center\n"
        " * (where the pilot's camera goes). */\n"
        "declare global pPx: num;\n"
        "declare global pNeck: vec;\n"
        "declare global pTorsoUp: vec;\n"
        "declare global pHead: vec;\n\n"
        "function loadPilotPose {\n"
        f"    global pPx = {fmt(PX)};\n"
        + v("pNeck", neck) + v("pTorsoUp", up_t) + v("pHead", head_center)
        + "}\n\n"
        "/** Item model and part id (the shader's mark) of each rigid part. */\n"
        f"function pilotRigidParts(): list {{\n    return [{rigid}];\n}}\n"
    )
    (ROOT / "tc/pilot_data.tc").write_text(tc)
