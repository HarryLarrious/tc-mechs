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
a second: from standing beside the kneeling mech's front (right) leg, a jump
up to grab the head of its knee piston, a pull-up onto the piston, up onto
the knee guard, up the torso front onto the roof, back along the roof outside
the right light gun, onto the hatch's side rim, down into the cabin, turn to
face ahead and slide forward into the chair. Its last sample is the seated
pose (hands on the joysticks). Getting out plays it backwards. The walk from
the player to the front foot is done live.

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
HIP_H = 12 * PX        # hips above the soles, standing
SHOULDER_H = 10 * PX   # shoulder pivots above the hips

# The climb up the front (right) leg of the kneeling mech: holds measured off
# the kneeling model in the viewer (raycasts), as heights above the ground
# and x, z in the mech frame (m).
PISTON = (-2.21, 3.67, 2.31)   # the knee piston's head (cylinder end), on the leg's outboard side
PISTON_TOP = 3.92              # top of the cylinder near its head
JUMP_FROM = (-2.95, 2.35)      # where the jump starts (x, z), facing the piston (+X)
KNEE_SIDE_X = -2.00            # the knee guard's and thigh's outboard face
LANE = -1.50                   # x of the knee top, the torso front climb and the walk's start
KNEE = (5.10, 2.28)            # top of the knee guard: a ledge
FRONT_Z = 2.06                 # the torso's front face above it
ROOF_EDGE_Z = 1.95             # where the roof starts at the front
WALK_X = -1.55                 # along the roof, outside the right light gun


def board_timeline(g: dict, seat, recline, hips_z, grips) -> list[list[float]]:
    """The boarding timeline: per sample [hips x y z, lean (degrees, + forward),
    yaw (degrees, 0 faces +Z, 90 faces +X), left foot, right foot, left hand,
    right hand], all in the mech frame at rest (real meters). g: the geometry
    (real meters): ground under the kneeling mech, roof top, the hatch hole's
    z range and half width, and the cabin floor."""
    G = g["ground"]

    def P(x, h, z):
        """A point `h` above the kneeling mech's ground."""
        return (x, G + h, z)

    def at(c, yaw, k, h, fwd=0.0):
        """A point k to the body's left and fwd ahead of c (x, z), at height h."""
        r = math.radians(yaw)
        lx, lz = math.cos(r), -math.sin(r)
        fx, fz = math.sin(r), math.cos(r)
        return (c[0] + lx * k + fx * fwd, h, c[1] + lz * k + fz * fwd)

    def stand(x, z, h, yaw, lean=0.0, step=0.0, swing=0.0):
        """Standing on height h at (x, z): feet `step` apart along the walk,
        hands hanging (swinging `swing` m)."""
        c = (x, z)
        hip = (x, G + h + HIP_H, z)
        return [*hip, lean, yaw,
                *at(c, yaw, 0.12, G + h, step / 2), *at(c, yaw, -0.12, G + h, -step / 2),
                *at(c, yaw, 0.33, hip[1] + SHOULDER_H - 0.6, -swing), *at(c, yaw, -0.33, hip[1] + SHOULDER_H - 0.6, swing)]

    def frame(hip, lean, yaw, fl, fr, hl, hr):
        return [*hip, lean, yaw, *fl, *fr, *hl, *hr]

    keys = []                                          # (seconds to get here, frame)
    face = 180.0                                       # facing the mech's front: toward -Z
    side_ = 90.0                                       # facing the leg's outboard side: toward +X
    jx, jz = JUMP_FROM
    px_, ph, pz = PISTON
    # facing +X the body's left is -Z
    keys.append((0.0, stand(jx, jz, 0.0, side_)))
    # crouch, arms back
    keys.append((0.3, frame(P(jx - 0.05, HIP_H - 0.28, jz), 20, side_, P(jx + 0.05, 0.0, jz - 0.12), P(jx + 0.05, 0.0, jz + 0.12),
                            P(jx - 0.35, 0.55, jz - 0.3), P(jx - 0.35, 0.55, jz + 0.3))))
    # jump: up and in, arms reaching for the piston head
    keys.append((0.25, frame(P(jx + 0.15, 1.75, jz), 5, side_, P(jx + 0.05, 1.0, jz - 0.12), P(jx + 0.1, 1.15, jz + 0.12),
                             P(px_ - 0.3, 3.35, pz - 0.18), P(px_ - 0.3, 3.35, pz + 0.18))))
    # catch it: hands over the top of the cylinder head
    hang_x = px_ - 0.55
    grip_l, grip_r = P(px_ - 0.12, PISTON_TOP, pz - 0.16), P(px_ - 0.12, PISTON_TOP, pz + 0.16)
    keys.append((0.15, frame(P(hang_x, PISTON_TOP - 1.25, pz), 0, side_, P(hang_x - 0.05, PISTON_TOP - 1.9, pz - 0.12),
                             P(hang_x + 0.05, PISTON_TOP - 1.85, pz + 0.12), grip_l, grip_r)))
    # hang, legs swinging under
    keys.append((0.35, frame(P(hang_x + 0.05, PISTON_TOP - 1.3, pz), -5, side_, P(hang_x + 0.15, PISTON_TOP - 1.95, pz - 0.12),
                             P(hang_x + 0.1, PISTON_TOP - 1.95, pz + 0.12), grip_l, grip_r)))
    keys.append((0.3, frame(P(hang_x, PISTON_TOP - 1.3, pz), 0, side_, P(hang_x - 0.1, PISTON_TOP - 1.95, pz - 0.12),
                            P(hang_x - 0.05, PISTON_TOP - 1.95, pz + 0.12), grip_l, grip_r)))
    # pull up, feet walking up the cylinder's side
    keys.append((0.5, frame(P(hang_x + 0.05, PISTON_TOP - 0.45, pz), 15, side_, P(px_ - 0.3, PISTON_TOP - 0.6, pz - 0.12),
                            P(hang_x, PISTON_TOP - 1.0, pz + 0.12), grip_l, grip_r)))
    # mantle: lean over it, a foot onto the top
    keys.append((0.5, frame(P(px_ - 0.25, PISTON_TOP + 0.35, pz), 35, side_, P(px_ - 0.05, PISTON_TOP, pz - 0.12),
                            P(px_ - 0.3, PISTON_TOP - 0.5, pz + 0.12), P(px_ + 0.08, PISTON_TOP, pz - 0.2), P(px_ + 0.08, PISTON_TOP, pz + 0.2))))
    # stand on the piston, hands on the knee guard
    keys.append((0.45, frame(P(px_ - 0.08, PISTON_TOP + HIP_H, pz), 0, side_, P(px_ - 0.05, PISTON_TOP, pz - 0.12),
                             P(px_ - 0.05, PISTON_TOP, pz + 0.12), P(KNEE_SIDE_X - 0.03, KNEE[0] - 0.35, pz - 0.22),
                             P(KNEE_SIDE_X - 0.03, KNEE[0] - 0.2, pz + 0.22))))
    # reach up to the top of the knee guard
    keys.append((0.35, frame(P(px_ - 0.08, PISTON_TOP + HIP_H, pz), 0, side_, P(px_ - 0.05, PISTON_TOP, pz - 0.12),
                             P(px_ - 0.05, PISTON_TOP, pz + 0.12), P(KNEE_SIDE_X + 0.15, KNEE[0], KNEE[1] - 0.15),
                             P(KNEE_SIDE_X + 0.15, KNEE[0], KNEE[1] + 0.15))))
    # pull up, a foot on the thigh armor's side
    keys.append((0.5, frame(P(KNEE_SIDE_X - 0.28, KNEE[0] - 0.3, KNEE[1]), 15, side_, P(KNEE_SIDE_X - 0.06, KNEE[0] - 0.45, KNEE[1] - 0.12),
                            P(px_ - 0.05, PISTON_TOP + 0.1, KNEE[1] + 0.12), P(KNEE_SIDE_X + 0.15, KNEE[0], KNEE[1] - 0.15),
                            P(KNEE_SIDE_X + 0.15, KNEE[0], KNEE[1] + 0.15))))
    # over the edge onto the knee guard
    keys.append((0.5, frame(P(KNEE_SIDE_X + 0.1, KNEE[0] + 0.4, KNEE[1]), 35, side_, P(KNEE_SIDE_X + 0.25, KNEE[0], KNEE[1] - 0.12),
                            P(KNEE_SIDE_X - 0.05, KNEE[0] - 0.4, KNEE[1] + 0.12), P(LANE + 0.2, KNEE[0], KNEE[1] - 0.15),
                            P(LANE + 0.2, KNEE[0], KNEE[1] + 0.15))))
    # stand up on it, turning to face the torso front
    x = LANE
    keys.append((0.5, frame(P(x, KNEE[0] + HIP_H, KNEE[1] + 0.05), 0, face, P(x - 0.12, KNEE[0], KNEE[1]),
                            P(x + 0.12, KNEE[0], KNEE[1]), P(x - 0.33, KNEE[0] + HIP_H + SHOULDER_H - 0.6, KNEE[1] + 0.05),
                            P(x + 0.33, KNEE[0] + HIP_H + SHOULDER_H - 0.6, KNEE[1] + 0.05))))
    # up the torso front onto the roof
    roof = g["roof"] - G
    keys.append((0.4, frame(P(x, KNEE[0] + HIP_H, KNEE[1] + 0.05), 0, face, P(x - 0.12, KNEE[0], KNEE[1]),
                            P(x + 0.12, KNEE[0], KNEE[1]), P(x - 0.2, roof, ROOF_EDGE_Z - 0.05), P(x + 0.2, roof, ROOF_EDGE_Z - 0.05))))
    keys.append((0.5, frame(P(x, roof - 0.35, FRONT_Z + 0.28), 0, face, P(x - 0.12, KNEE[0] + 0.6, FRONT_Z + 0.06),
                            P(x + 0.12, KNEE[0], KNEE[1]), P(x - 0.2, roof, ROOF_EDGE_Z - 0.05), P(x + 0.2, roof, ROOF_EDGE_Z - 0.05))))
    keys.append((0.5, frame(P(x, roof + 0.42, ROOF_EDGE_Z + 0.02), 35, face, P(x - 0.12, roof, ROOF_EDGE_Z - 0.2),
                            P(x + 0.12, roof - 0.5, FRONT_Z + 0.06), P(x - 0.25, roof, ROOF_EDGE_Z - 0.5),
                            P(x + 0.25, roof, ROOF_EDGE_Z - 0.5))))
    z0 = ROOF_EDGE_Z - 0.35
    keys.append((0.45, stand(WALK_X, z0, roof, face)))
    # back along the roof, outside the light gun, to beside the hatch
    h0z, h1z = g["hole"]
    hz = (h0z + h1z) / 2
    walk = [z0 + (hz - z0) * k / 5 for k in range(1, 6)]
    for k, z in enumerate(walk):
        last = k == len(walk) - 1
        sgn = 1 if k % 2 == 0 else -1
        keys.append((0.32, stand(WALK_X, z, roof, face, step=0 if last else 0.45 * sgn, swing=0 if last else 0.15 * sgn)))
    # turn to the hatch and step to its right rim
    keys.append((0.4, stand(WALK_X, hz, roof, 90.0)))
    hx = g["hole_x"]
    keys.append((0.4, stand(-hx - 0.45, hz, roof, 90.0, step=0.3, swing=0.1)))
    keys.append((0.3, stand(-hx - 0.4, hz, roof, 90.0)))
    # sit on the rim, legs in the hole, hands on the roof
    keys.append((0.5, frame(P(-hx - 0.16, roof + 0.07, hz), -10, 90.0, P(-0.05, roof - 0.55, hz - 0.12), P(-0.05, roof - 0.55, hz + 0.12),
                            P(-hx - 0.2, roof, hz - 0.38), P(-hx - 0.2, roof, hz + 0.38))))
    # down onto the cabin floor, holding the rim, and turn to face ahead
    floor = g["floor"] - G
    keys.append((0.7, frame(P(-0.05, floor + HIP_H, hz), 0, 90.0, P(0.0, floor, hz - 0.12), P(0.0, floor, hz + 0.12),
                            P(-hx - 0.1, roof, hz - 0.35), P(-hx - 0.1, roof, hz + 0.35))))
    keys.append((0.5, frame(P(0.0, floor + HIP_H, hz + 0.05), 0, 0.0, P(0.12, floor, hz + 0.1), P(-0.12, floor, hz + 0.1),
                            P(0.3, roof, h1z + 0.05), P(-0.3, roof, h1z + 0.05))))
    # crouch and slide forward under the roof into the chair
    parts, neck, up_t, head_center = pose(seat, recline, hips_z, grips)
    hip = add(seat, (0.0, 0.06, hips_z))
    fl_ = G + floor
    hz2 = (h1z + hip[2]) / 2
    keys.append((0.6, frame((0, fl_ + 0.38, hz2), -30, 0.0, (0.14, fl_ + 0.04, hip[2] - 0.35), (-0.14, fl_ + 0.04, hip[2] - 0.35),
                            (0.3, fl_ + 0.70, hz2 + 0.2), (-0.3, fl_ + 0.70, hz2 + 0.2))))
    feet = []
    for s_ in (1, -1):
        piv = add(hip, (s_ * 2 * PX, 0.0, 0.0))
        lf, sp = math.radians(LEG_LIFT), math.radians(LEG_SPLAY)
        d = (s_ * math.sin(sp), math.sin(lf), math.cos(lf) * math.cos(sp))
        feet.append(add(piv, mul(norm(d), 12 * PX)))
    keys.append((0.6, frame(hip, -recline, 0.0, feet[0], feet[1], grips[0], grips[1])))

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


def write_pilot(timeline: list[list[float]]) -> None:
    first = timeline[0]
    start = ((first[5] + first[8]) / 2, (first[6] + first[9]) / 2, (first[7] + first[10]) / 2)
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
        "/** Where the walk from the player ends (the soles' center in front of the\n"
        " * kneeling mech's front foot, on the ground), and the way the body faces\n"
        " * there (yaw in the mech frame: 0 faces +Z, 90 faces +X). */\n"
        f"function pilotClimbStart(): vec {{\n    return vec({', '.join(fmt(c) for c in start)});\n}}\n\n"
        f"function pilotClimbYaw(): num {{\n    return {fmt(first[4])};\n}}\n\n"
        "/** Boarding, sample by sample: \"hips x y z, lean (degrees, + forward), yaw,\n"
        " * left foot x y z, right foot, left hand, right hand\". The last is seated. */\n"
        f"function pilotBoardPath(): list {{\n    return [\n        {rows}\n    ];\n}}\n"
    )
    (ROOT / "tc/pilot_data.tc").write_text(tc)
