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

Boarding is an animation in mech/animations/board.json (keyframes of figure
poses in the mech frame at rest, with the mech kneeling and the turret
ahead; edited with tools/animator), baked here into a timeline of
BOARD_RATE samples a second: from standing beside the kneeling mech's front
(right) leg, a jump up to grab the head of its knee piston, a pull-up onto
the piston, up onto the knee guard, up the torso front onto the roof, back
along the roof, onto the hatch's side rim, down into the cabin, turn to face
ahead and slide forward into the chair. Its last key is the seated pose
(hands on the joysticks). Getting out plays it backwards. The walk from the
player to the start is done live.

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


BOARD_RATE = 20        # timeline samples per second: every tick
HIP_H = 12 * PX        # hips above the soles, standing
SHOULDER_H = 10 * PX   # shoulder pivots above the hips

ANIMS = ROOT / "mech/animations"


def seated_frame(seat, recline, hips_z, grips) -> list[float]:
    """The seated pose as a timeline frame: hips on the seat, leaning back with
    the chair, legs along the seat pan, hands on the joysticks."""
    hip = add(seat, (0.0, 0.06, hips_z))
    feet = []
    for s_ in (1, -1):
        piv = add(hip, (s_ * 2 * PX, 0.0, 0.0))
        lf, sp = math.radians(LEG_LIFT), math.radians(LEG_SPLAY)
        d = (s_ * math.sin(sp), math.sin(lf), math.cos(lf) * math.cos(sp))
        feet.append(add(piv, mul(norm(d), 12 * PX)))
    return [*hip, -recline, 0.0, *feet[0], *feet[1], *grips[0], *grips[1]]


# Limbs, as the editor and the game pose them: rigid, from their joint (the
# shoulder 2 px under the top of the arm, the top of the leg; moved off its
# socket by an offset in the body frame if the animation says so) along a
# direction, ARM_LEN or LEG_LEN to the hand or the sole, twisted by a roll
# (degrees) about their length.
#
# A timeline row (what the game plays): hips x y z, lean, yaw, then per limb
# in LIMB_ORDER its joint x y z, its end x y z and its roll: 5 + 4 * 7 numbers.
ARM_LEN = 10 * PX
LEG_LEN = 12 * PX
LIMB_ORDER = ("leg_l", "leg_r", "arm_l", "arm_r")
LIMB_LEN = {"leg_l": LEG_LEN, "leg_r": LEG_LEN, "arm_l": ARM_LEN, "arm_r": ARM_LEN}
POINT_FIELDS = {"leg_l": "foot_l", "leg_r": "foot_r", "arm_l": "hand_l", "arm_r": "hand_r"}


def body_axes(lean: float, yaw: float):
    """The body's (left, up, forward) in the mech frame: leaning forward by
    `lean` about its left, turned by `yaw` about Y (0 faces +Z, 90 faces +X)."""
    a, y = math.radians(lean), math.radians(yaw)
    cy, sy, ca, sa = math.cos(y), math.sin(y), math.cos(a), math.sin(a)
    return (cy, 0.0, -sy), (sa * sy, ca, sa * cy), (ca * sy, -sa, ca * cy)


def limb_sockets(hips, tl, tu) -> dict:
    """Where each limb's joint is with no offset."""
    sh = add(hips, mul(tu, 10 * PX))
    return {"arm_l": add(sh, mul(tl, 6 * PX)), "arm_r": add(sh, mul(tl, -6 * PX)),
            "leg_l": add(hips, mul(tl, 2 * PX)), "leg_r": add(hips, mul(tl, -2 * PX))}


def in_body(v, axes):
    """A body-frame vector in the mech frame."""
    tl, tu, tf = axes
    return add(add(mul(tl, v[0]), mul(tu, v[1])), mul(tf, v[2]))


def rig_to_row(k: dict) -> list[float]:
    """A rig pose (limb directions, offsets and rolls in the body frame) as a
    timeline row."""
    axes = body_axes(k["lean"], k["yaw"])
    sockets = limb_sockets(k["hips"], axes[0], axes[1])
    row = [*k["hips"], k["lean"], k["yaw"]]
    for n in LIMB_ORDER:
        joint = add(sockets[n], in_body(k.get("off", {}).get(n, (0, 0, 0)), axes))
        end = add(joint, mul(norm(in_body(norm(k[n]), axes)), LIMB_LEN[n]))
        row += [*joint, *end, k.get("roll", {}).get(n, 0.0)]
    return row


def points_to_row(f) -> list[float]:
    """A frame of hand and foot points (hips, lean, yaw, left foot, right foot,
    left hand, right hand) as a timeline row: limbs in their sockets."""
    axes = body_axes(f[3], f[4])
    sockets = limb_sockets(f[0:3], axes[0], axes[1])
    ends = {"leg_l": f[5:8], "leg_r": f[8:11], "arm_l": f[11:14], "arm_r": f[14:17]}
    row = list(f[0:5])
    for n in LIMB_ORDER:
        row += [*sockets[n], *ends[n], 0.0]
    return row


def points_to_rig(f) -> dict:
    """A frame of hand and foot points as a rig pose (each limb pointing at its
    point from its socket)."""
    tl, tu, tf = body_axes(f[3], f[4])
    sockets = limb_sockets(f[0:3], tl, tu)
    ends = {"leg_l": f[5:8], "leg_r": f[8:11], "arm_l": f[11:14], "arm_r": f[14:17]}
    k = {"hips": list(f[0:3]), "lean": f[3], "yaw": f[4]}
    for n in LIMB_ORDER:
        d = norm(sub(ends[n], sockets[n]))
        k[n] = [dot(d, tl), dot(d, tu), dot(d, tf)]
    return k


def slerp(a, b, u):
    """Between unit vectors a and b, u of the way along the arc."""
    c = max(-1.0, min(1.0, dot(a, b)))
    th = math.acos(c)
    if th < 1e-4:
        return norm(add(a, mul(sub(b, a), u)))
    s = math.sin(th)
    return norm(add(mul(a, math.sin((1 - u) * th) / s), mul(b, math.sin(u * th) / s)))


def load_keys(name: str, seat, recline, hips_z, grips) -> tuple[str, list]:
    """The keys of animation `name` (mech/animations/<name>.json, made with
    tools/animator): ("rig", [(dt, pose)]) when the limbs are directions (the
    editor's format), else ("points", [(dt, row)]) for hand and foot points.
    A key marked "seated" takes the seated pose from the cockpit's geometry,
    so it stays right if the chair moves."""
    doc = json.loads((ANIMS / f"{name}.json").read_text())
    rig = any("arm_l" in k for k in doc["keys"])
    keys = []
    for k in doc["keys"]:
        if k.get("seated"):
            f = seated_frame(seat, recline, hips_z, grips)
            keys.append((k["dt"], points_to_rig(f) if rig else points_to_row(f)))
        elif rig:
            keys.append((k["dt"], {n: k[n] for n in ("hips", "lean", "yaw", "arm_l", "arm_r", "leg_l", "leg_r", "off", "roll")
                                   if n in k}))
        else:
            keys.append((k["dt"], points_to_row([*k["hips"], k["lean"], k["yaw"],
                                                 *[c for n in LIMB_ORDER for c in k[POINT_FIELDS[n]]]])))
    return ("rig" if rig else "points"), keys


def timeline(name: str, seat, recline, hips_z, grips) -> list[list[float]]:
    """Animation `name` (mech/animations/<name>.json) sampled at BOARD_RATE, as
    timeline rows (see LIMB_ORDER), in the mech frame at rest (real meters)
    with the mech kneeling."""
    kind, keys = load_keys(name, seat, recline, hips_z, grips)
    return sample_rig(keys) if kind == "rig" else sample_rows(keys)


def key_spans(keys):
    """Per sample time: (index of the key before, eased fraction to the next)."""
    times = [0.0]
    for dt, _ in keys[1:]:
        times.append(times[-1] + dt)
    total = times[-1]
    for i in range(round(total * BOARD_RATE) + 1):
        t = min(total, i / BOARD_RATE)
        j = max(k for k in range(len(times)) if times[k] <= t + 1e-9)
        if j >= len(keys) - 1:
            yield len(keys) - 1, 0.0
            continue
        u = (t - times[j]) / (times[j + 1] - times[j])
        yield j, u * u * (3 - 2 * u)


def sample_rows(keys) -> list[list[float]]:
    """Samples row keys [(seconds to get here, row)] at BOARD_RATE, eased
    (smoothstep) between each pair."""
    out = []
    for j, u in key_spans(keys):
        if j >= len(keys) - 1:
            out.append(keys[-1][1])
            continue
        a, b = keys[j][1], keys[j + 1][1]
        out.append([p + (q - p) * u for p, q in zip(a, b)])
    if out[-1] != keys[-1][1]:
        out.append(keys[-1][1])
    return [[round(v, 3) for v in row] for row in out]


def sample_rig(keys) -> list[list[float]]:
    """Samples rig keys at BOARD_RATE, eased between each pair: the hips, lean,
    yaw, offsets and rolls move straight, each limb turns along the arc
    between its directions. Returns timeline rows."""
    zero = (0.0, 0.0, 0.0)
    out = []
    for j, u in key_spans(keys):
        if j >= len(keys) - 1:
            out.append(rig_to_row(keys[-1][1]))
            continue
        a, b = keys[j][1], keys[j + 1][1]
        k = {"hips": [p + (q - p) * u for p, q in zip(a["hips"], b["hips"])],
             "lean": a["lean"] + (b["lean"] - a["lean"]) * u, "yaw": a["yaw"] + (b["yaw"] - a["yaw"]) * u,
             "off": {}, "roll": {}}
        for n in LIMB_ORDER:
            k[n] = slerp(norm(a[n]), norm(b[n]), u)
            oa, ob = a.get("off", {}).get(n, zero), b.get("off", {}).get(n, zero)
            k["off"][n] = [p + (q - p) * u for p, q in zip(oa, ob)]
            ra, rb = a.get("roll", {}).get(n, 0.0), b.get("roll", {}).get(n, 0.0)
            k["roll"][n] = ra + (rb - ra) * u
        out.append(rig_to_row(k))
    last = rig_to_row(keys[-1][1])
    if out[-1] != last:
        out.append(last)
    return [[round(v, 3) for v in row] for row in out]


def fmt(x: float) -> str:
    s = f"{x:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def soles(row) -> tuple:
    """The soles' center in a timeline row (the legs' ends, see LIMB_ORDER)."""
    return tuple((row[8 + i] + row[15 + i]) / 2 for i in range(3))


def write_pilot(board: list[list[float]], exit_: list[list[float]]) -> None:
    def rows(path):
        return ",\n        ".join('"' + " ".join(fmt(v) for v in row) + '"' for row in path)

    start, end = soles(board[0]), soles(exit_[-1])
    items = ITEMS / "pilot"
    items.mkdir(parents=True, exist_ok=True)
    for old in items.glob("*.json"):
        old.unlink()
    (items / "unit.json").write_text(json.dumps(head_item(item_transform(diag(1, 1, 1))), indent=1) + "\n")
    (ITEMS / "empty.json").write_text(json.dumps({"model": {"type": "minecraft:empty"}}, indent=1) + "\n")
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
        "/** Where the walk from the player ends (the soles' center in front of the\n"
        " * kneeling mech's front foot, on the ground), and the way the body faces\n"
        " * there (yaw in the mech frame: 0 faces +Z, 90 faces +X). */\n"
        f"function pilotClimbStart(): vec {{\n    return vec({', '.join(fmt(c) for c in start)});\n}}\n\n"
        f"function pilotClimbYaw(): num {{\n    return {fmt(board[0][4])};\n}}\n\n"
        "/** Where getting out ends (the soles' center, on the ground under the kneeling\n"
        " * mech), and the way the body faces there. */\n"
        f"function pilotExitSpot(): vec {{\n    return vec({', '.join(fmt(c) for c in end)});\n}}\n\n"
        f"function pilotExitYaw(): num {{\n    return {fmt(exit_[-1][4])};\n}}\n\n"
        "/** Boarding (mech/animations/board.json), sample by sample: \"hips x y z, lean\n"
        " * (degrees, + forward), yaw, then per limb (left leg, right leg, left arm,\n"
        " * right arm) its joint x y z, its end x y z (sole or hand) and its roll\n"
        " * (degrees)\". The last is seated. */\n"
        f"function pilotBoardPath(): list {{\n    return [\n        {rows(board)}\n    ];\n}}\n\n"
        "/** Getting out (mech/animations/exit.json), the same way. The first is seated. */\n"
        f"function pilotExitPath(): list {{\n    return [\n        {rows(exit_)}\n    ];\n}}\n"
    )
    (ROOT / "tc/pilot_data.tc").write_text(tc)
