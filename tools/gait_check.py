#!/usr/bin/env python3
"""Reference model of the mech's procedural walk over blocks, and its checks.

    python3 tools/gait_check.py [walker|sprinter]     (default walker)

The viewer (tools/viewer/index.html) and the plot code (tc/gait.tc) run the
same algorithm; this file is the reference they were written from. All three
read their numbers from GAIT and PROBES in pack/src/mech_lib.py (through
mech/parts.json here).

  * Leg IK: each leg turns only about X, so it works in its own YZ plane.
    Given where the ankle should be, the hip and knee angles come from the
    triangle hip-knee-ankle (the knee always bends the way it does at rest),
    and the ankle angle keeps the foot level (-(hip + knee)) plus a toe pitch
    while the foot swings.
  * Footholds: the ground under a foot is the block top under its middle
    (one block to stand on), found by looking down from probe_up above the
    foot to probe_down below it (a block at the top of that reach is a wall,
    not ground). A planted foot tilts to the slope between the blocks under
    its heel and toe.
  * Steps: a planted foot stays where it is in the world. When it lags too far
    behind its home spot under the hip (moved ahead by half a step) and the
    other foot is planted, it swings to where its home will be when it lands,
    or a longer or shorter step if that spot is no good: no ground there, more than
    max_rise above or below the other foot, or a leg would come within margin
    degrees of a joint limit or stretch past max_reach. The swing eases over,
    lifting higher for a step up or down.
  * Body: it moves and turns at the commanded speed and turn rate, unless the
    move would put a collision probe in a solid block (it slides along the
    wall if one axis is free) or put a planted leg out of reach or past a
    joint limit when it is inside them now (it waits for the feet; a leg
    already out of reach never stops a move that helps it). Its height
    follows the feet (a swinging foot by where it will land) by the same
    rules; it is crouched a little and rises at mid-swing.
  * Torso: it turns toward its aim at aim_rate, unless that would put its
    probes (the hull and the heavy guns) in a block.
  * Gravity: each tick a planted foot checks the block top under it. A foot
    whose ground is gone (or has a block grown into it) steps at once; with
    no step to take, or both feet gone, the mech falls (gravity, capped at
    max_fall) with its legs held, lands when a foot meets a block top, and
    sinks land_dip into its legs on a hard landing. Walking toward a drop
    deeper than max_rise, a foot steps out over it and the mech falls; every
    landing records its impact speed, for the damage model.

Checks: the IK puts the ankle exactly where it was asked; a walk at every
speed and turn rate on flat ground keeps every joint in range and every
foothold within reach; and on test courses (steps of one and two blocks, a
wall too high to climb, a bar at turret height) the mech climbs what it can,
stops at what it cannot, never has a probe inside a block, and never leaves a
joint's range.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TYPE = sys.argv[1] if len(sys.argv) > 1 else "walker"
SPEC = json.loads((ROOT / ("mech/parts.json" if TYPE == "walker" else f"mech/{TYPE}/parts.json")).read_text())
J = SPEC["joints"]
K = SPEC["scale"]
G = SPEC["gait"]
PROBES = SPEC["probes"]

# Leg geometry, mech frame (left leg; the right is x mirrored).
HIP = J["hip_l"]["pivot"]
KNEE = J["knee_l"]["pivot"]
ANKLE = J["ankle_l"]["pivot"]

CROUCH, SWING, LIFT, BOB = G["crouch"], G["swing"], G["lift"], G["bob"]
STEP, SETTLE, LEAD = G["step"], G["settle"], G["lead"]
MAX_SPEED, MAX_TURN, TOE = G["max_speed"], G["max_turn"], G["toe"]
MAX_RISE, UP, DOWN, CLIMB = G["max_rise"], G["probe_up"], G["probe_down"], G["climb_rate"]
MARGIN, MAX_REACH = G["margin"], G["max_reach"]
GRAVITY, MAX_FALL, LAND_DIP, DIP_RATE = G["gravity"], G["max_fall"], G["land_dip"], G["dip_rate"]
FALL_DRIFT = G["fall_drift"]
# Body heights a landing is judged at, as shares from the lower foot to the
# higher: halfway first, then lower and higher (a tall step needs the body
# near one end).
BODY_MIXES = (0.5, 0.25, 0.75, 0.0, 1.0)
# Landing spots tried, as shares of the planned step: the plan, longer steps
# (to get a whole foot onto a step instead of perching on its edge, and to
# bring the trailing foot up a tall step the body is waiting at), shorter ones.
STEP_FRACTIONS = (1.0, 1.3, 1.6, 2.0, 0.7, 0.45, 0.2)
FOOT_SAMPLES = [(0.0, G["foot_heel"]), (0.0, G["foot_mid"]), (0.0, G["foot_toe"]),
                (G["foot_side"], G["foot_mid"]), (-G["foot_side"], G["foot_mid"])]


def ang(y, z):
    """Angle of a vector in the YZ plane, increasing as a turn about +X turns it."""
    return math.atan2(z, y)


def wrap(a):
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


T0 = (KNEE[1] - HIP[1], KNEE[2] - HIP[2])        # thigh at rest (y, z)
S0 = (ANKLE[1] - KNEE[1], ANKLE[2] - KNEE[2])    # shin at rest
L1 = math.hypot(*T0)
L2 = math.hypot(*S0)
PHI0 = wrap(ang(*S0) - ang(*T0))                 # knee bend at rest (signed)
BEND = 1 if PHI0 > 0 else -1
REACH = [0.0]   # the most the walk has asked of a leg, as a share of its full length


def leg_ik(dy, dz):
    """Hip and knee angles (degrees) that put the ankle at (dy, dz) from the hip."""
    d = math.hypot(dy, dz)
    REACH[0] = max(REACH[0], d / (L1 + L2))
    d = min(max(d, abs(L1 - L2) + 0.01), L1 + L2 - 0.01)
    gamma = math.acos((L1 * L1 + L2 * L2 - d * d) / (2 * L1 * L2))    # inner knee angle
    alpha = math.acos((L1 * L1 + d * d - L2 * L2) / (2 * L1 * d))     # thigh off the hip-ankle line
    phi = BEND * (math.pi - gamma)                                     # thigh-to-shin turn
    thigh = ang(dy, dz) - BEND * alpha
    hip = wrap(thigh - ang(*T0))
    knee = wrap(phi - PHI0)
    return math.degrees(hip), math.degrees(knee)


def leg_fk(hip, knee):
    """Ankle (dy, dz) from the hip for hip and knee angles (degrees)."""
    a1 = ang(*T0) + math.radians(hip)
    a2 = a1 + PHI0 + math.radians(knee)
    return (L1 * math.cos(a1) + L2 * math.cos(a2), L1 * math.sin(a1) + L2 * math.sin(a2))


def leg_ok(dy, dz):
    """Whether a leg can put its ankle at (dy, dz) from the hip with every joint
    margin inside its range and without stretching past max_reach."""
    if math.hypot(dy, dz) > MAX_REACH * (L1 + L2):
        return False
    hip, knee = leg_ik(dy, dz)
    ankle = -(hip + knee)
    for j, v in (("hip_l", hip), ("knee_l", knee), ("ankle_l", ankle)):
        lo, hi = J[j]["range"]
        if v < lo + MARGIN or v > hi - MARGIN:
            return False
    return True


class World:
    """Blocks: a height per column (block tops, default 0) plus loose blocks."""

    def __init__(self):
        self.tops = {}
        self.blocks = set()

    def solid(self, x, y, z):
        ix, iy, iz = math.floor(x), math.floor(y), math.floor(z)
        return iy < self.tops.get((ix, iz), 0) or (ix, iy, iz) in self.blocks

    def col_top(self, x, z, start, length):
        """Like a raycast straight down from (x, start, z) for `length`: the top
        of the first solid block, `start` if it starts inside one, or None."""
        y = math.floor(start)
        if self.solid(x, start, z):
            return start
        while y >= start - length - 1:
            if self.solid(x, y + 0.5, z):
                top = y + 1
                return top if top >= start - length else None
            y -= 1
        return None


def fwd(yaw):
    # Minecraft-style: yaw 0 faces +Z; + yaw turns right; mech left is +X at yaw 0.
    return (-math.sin(yaw), math.cos(yaw))


def left(yaw):
    f = fwd(yaw)
    return (f[1], -f[0])


class Walker:
    """The gait state of one mech."""

    def __init__(self, world, x=0.0, z=0.0, yaw=0.0, y=0.0):
        self.world = world
        self.pos = [x, y, z]             # x, ground level, z
        self.yaw = yaw
        self.aim = yaw                   # where the torso faces
        self.speed = self.want_speed = 0.0
        self.turn = self.want_turn = 0.0
        self.body_y = -CROUCH
        self.vy = 0.0                    # falling speed (m/s, negative down)
        self.falling = False
        self.dip = 0.0                   # how far the body has sunk after a landing
        self.feet = {}
        for s in ("l", "r"):
            h = self.home(s, 0.0)
            g = self.ground(h[0], h[1], yaw, y, stand=False)
            if g is None:                # nothing under it: it falls
                self.falling = True
            self.feet[s] = [h[0], y if g is None else g, h[1]]
        if not self.falling:
            self.pos[1] = (self.feet["l"][1] + self.feet["r"][1]) / 2
        self.swing = {"l": None, "r": None}   # (t, start, end) while swinging
        self.blocked = 0
        self.falls = 0
        self.forced = 0
        self.stepped_off = 0
        self.impacts = []                # landing speeds (m/s), for the damage model

    def home(self, side, lead, x=None, z=None, yaw=None):
        """Where a foot (ankle x, z) rests under its hip, `lead` meters ahead."""
        x = self.pos[0] if x is None else x
        z = self.pos[2] if z is None else z
        yaw = self.yaw if yaw is None else yaw
        s = 1 if side == "l" else -1
        f, l = fwd(yaw), left(yaw)
        hx, hz = s * HIP[0], ANKLE[2] + lead
        return (x + l[0] * hx + f[0] * hz, z + l[1] * hx + f[1] * hz)

    def ground(self, x, z, yaw, near, stand=True):
        """Ground height under a foot whose ankle is at (x, z), facing yaw,
        looked for around height `near`: the block top under the middle of
        the foot (the one block it stands on); None if there is none or it is
        a wall. (`stand` is not used any more.)"""
        f = fwd(yaw)
        t = self.world.col_top(x + f[0] * G["foot_mid"], z + f[1] * G["foot_mid"], near + UP, UP + DOWN)
        if t is None or t >= near + UP - 0.01:
            return None
        return t

    def toe_jammed(self, x, y, z, yaw):
        """Whether a foot standing at (x, y, z) facing yaw has a block under its
        toe more than half a block higher than where it stands."""
        f = fwd(yaw)
        t = self.world.col_top(x + f[0] * G["foot_toe"], z + f[1] * G["foot_toe"], y + UP, UP + DOWN)
        return t is not None and t > y + 0.5

    def tilt(self, s):
        """How far planted foot s tilts to the ground under its heel and toe
        (degrees, + toe up): their slope, each within 1 m of the foot's
        height (none counts as level), at most 30."""
        foot, f = self.feet[s], fwd(self.yaw)
        hs = []
        for sz in (G["foot_heel"], G["foot_toe"]):
            t = self.world.col_top(foot[0] + f[0] * sz, foot[2] + f[1] * sz, foot[1] + UP, UP + DOWN)
            hs.append(0.0 if t is None else max(-1.0, min(1.0, t - foot[1])))
        a = math.degrees(math.atan2(hs[1] - hs[0], G["foot_toe"] - G["foot_heel"]))
        return max(-30.0, min(30.0, a))

    def foot_ok(self, foot, x, z, yaw, gy):
        """Whether a foot at `foot` (x, y, z) suits a body at (x, gy, z) facing yaw."""
        f = fwd(yaw)
        mz = (foot[0] - x) * f[0] + (foot[2] - z) * f[1]
        my = ANKLE[1] + foot[1] - gy - (-CROUCH)
        return leg_ok(my - HIP[1], mz - HIP[2])

    def legs_allow(self, x, z, yaw, gy):
        """Whether the body may stand at (x, gy, z) facing yaw: no planted leg
        that suits the body now would stop suiting it there (a leg that is
        already out of reach may stay so, so the body can move to fix it)."""
        for s in ("l", "r"):
            if self.swing[s] is None and not self.foot_ok(self.feet[s], x, z, yaw, gy) and \
                    self.foot_ok(self.feet[s], self.pos[0], self.pos[2], self.yaw, self.pos[1]):
                return False
        return True

    def path_clear(self, a, b, yaw):
        """Whether a swing from a to b passes over nothing higher than both ends:
        the ground under the middle of the foot along its way, every half block."""
        top = max(a[1], b[1])
        f = fwd(yaw)
        p0 = (a[0] + f[0] * G["foot_mid"], a[2] + f[1] * G["foot_mid"])
        p1 = (b[0] + f[0] * G["foot_mid"], b[2] + f[1] * G["foot_mid"])
        n = max(1, math.ceil(math.dist(p0, p1) / 0.5))
        for i in range(n + 1):
            x, z = p0[0] + (p1[0] - p0[0]) * i / n, p0[1] + (p1[1] - p0[1]) * i / n
            t = self.world.col_top(x, z, top + UP, UP + DOWN)
            if t is not None and t > top + 0.01:
                return False
        return True

    def probes_clear(self, x, z, yaw, aim, gy, body_y):
        for frame, px, py, pz in PROBES:
            y_ = yaw if frame == "body" else aim
            f, l = fwd(y_), left(y_)
            wx, wz = x + l[0] * px + f[0] * pz, z + l[1] * px + f[1] * pz
            if self.world.solid(wx, gy + body_y + py, wz):
                return False
        return True

    def plan_step(self, s, lead, lx, lz, lyaw, may_step_off=True):
        """Starts a swing of foot s to the first good landing spot near its home
        spot for a body landing at (lx, lz) facing lyaw. If there is none
        because the planned spot is a drop deeper than MAX_RISE (or has no
        ground at all), the foot steps out level over it, and the mech falls
        once it is there (unless may_step_off is False). False if neither."""
        o = "r" if s == "l" else "l"
        tx, tz = self.home(s, lead, lx, lz, lyaw)
        a = self.feet[s]
        # first a spot whose toe is not jammed against a higher block, then any
        for frac, fussy in [(fr, True) for fr in STEP_FRACTIONS] + [(fr, False) for fr in STEP_FRACTIONS]:
            ex, ez = a[0] + (tx - a[0]) * frac, a[2] + (tz - a[2]) * frac
            ey = self.ground(ex, ez, lyaw, a[1])
            if ey is None or abs(ey - self.feet[o][1]) > MAX_RISE:
                continue
            if fussy and self.toe_jammed(ex, ey, ez, lyaw):
                continue
            if not self.path_clear(a, (ex, ey, ez), lyaw):
                continue
            # the body moves toward the feet's heights while the foot swings;
            # the landing must suit some body height between them
            oy = self.feet[o][1]
            lo_, hi_ = min(ey, oy), max(ey, oy)
            if any(self.foot_ok((ex, ey, ez), lx, lz, lyaw, lo_ + (hi_ - lo_) * k_) for k_ in BODY_MIXES):
                self.swing[s] = (0.0, list(a), [ex, ey, ez])
                return True
        if may_step_off:
            g = self.ground(tx, tz, lyaw, a[1], stand=False)
            if g is None or g < a[1] - MAX_RISE:
                end = (tx, a[1], tz)
                if self.path_clear(a, end, lyaw) and self.foot_ok(end, lx, lz, lyaw, self.pos[1]):
                    self.swing[s] = (0.0, list(a), list(end))
                    self.stepped_off += 1
                    return True
        return False

    def supported(self, s):
        """Whether foot s still has its ground: the block top under it is where
        it stands (not gone, not lower, not a block grown into it)."""
        f = self.feet[s]
        g = self.ground(f[0], f[2], self.yaw, f[1], stand=False)
        return g is not None and abs(g - f[1]) <= 0.05

    def fall_clear(self, x, z, d):
        """Whether the mech, moved to (x, z) and dropped by d, has no probe and
        no foot (its ankle point and middle) inside a block."""
        if not self.probes_clear(x, z, self.yaw, self.aim, self.pos[1] + d, self.body_y):
            return False
        f = fwd(self.yaw)
        for s in ("l", "r"):
            ft = self.feet[s]
            for along in (0.0, G["foot_mid"]):
                if self.world.solid(ft[0] + x - self.pos[0] + f[0] * along, ft[1] + d + 0.05,
                                    ft[2] + z - self.pos[2] + f[1] * along):
                    return False
        return True

    def fall(self, dt):
        """One tick of falling: everything drops together, the feet swinging to
        hang under the hips (off any edge they stood on), until a foot meets a
        block top below it; then it lands with its legs as they were, records
        the impact speed and sinks a little."""
        self.vy = max(self.vy - GRAVITY * dt, -MAX_FALL)
        dy = self.vy * dt
        for s in ("l", "r"):
            f = self.feet[s]
            hx, hz = self.home(s, 0.0)
            ddx, ddz = hx - f[0], hz - f[2]
            dd = math.hypot(ddx, ddz)
            step = FALL_DRIFT * dt
            if dd > step:
                ddx, ddz = ddx * step / dd, ddz * step / dd
            f[0] += ddx
            f[2] += ddz
        land = None
        for s in ("l", "r"):
            f = self.feet[s]
            g = self.ground(f[0], f[2], self.yaw, f[1], stand=False)
            # only ground below the foot counts (a foot still on an edge does not hold the mech up)
            if g is not None and g < f[1] - 0.001 and g >= f[1] + dy:
                land = g - f[1] if land is None else max(land, g - f[1])
        d = dy if land is None else land
        # the mech falls clear of whatever it would drop into: its probes, and
        # its feet (a foot still standing on an edge slides off it). It is
        # pushed away (forward first, then back, then sideways) up to 3 m; if
        # nothing clears, it comes to rest where it is
        if not self.fall_clear(self.pos[0], self.pos[2], d):
            f, l = fwd(self.yaw), left(self.yaw)
            moved = False
            for r in (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0):
                for vx, vz in ((f[0], f[1]), (-f[0], -f[1]), (l[0], l[1]), (-l[0], -l[1])):
                    nx, nz = self.pos[0] + vx * r, self.pos[2] + vz * r
                    if self.fall_clear(nx, nz, d):
                        for s in ("l", "r"):
                            self.feet[s][0] += nx - self.pos[0]
                            self.feet[s][2] += nz - self.pos[2]
                        self.pos[0], self.pos[2] = nx, nz
                        moved = True
                        break
                if moved:
                    break
            if not moved:
                d = 0.0
                land = 0.0
        for s in ("l", "r"):
            self.feet[s][1] += d
        self.pos[1] += d
        if land is not None:
            self.falling = False
            self.impacts.append(-self.vy)
            self.dip = LAND_DIP * min(1.0, -self.vy / 10.0)
            self.vy = 0.0

    def tick(self, dt, aim_at=None):
        approach = lambda v, t, s: min(t, v + s) if v < t else max(t, v - s)
        self.speed = approach(self.speed, self.want_speed, G["accel"] * dt)
        self.turn = approach(self.turn, self.want_turn, G["turn_accel"] * dt)

        # gravity: a planted foot that lost its ground steps at once; with no
        # step to take, or both feet gone, the mech falls
        if not self.falling:
            planted = [s for s in ("l", "r") if self.swing[s] is None]
            lost = [s for s in planted if not self.supported(s)]
            if lost and (len(lost) == 2 or len(planted) == 1):
                self.falling = True
            elif lost:
                s = lost[0]
                self.forced += 1
                if not self.plan_step(s, 0.0, self.pos[0], self.pos[2], self.yaw, may_step_off=False):
                    self.falling = True
            if self.falling:
                self.falls += 1
                self.vy = 0.0
                self.swing = {"l": None, "r": None}
        if self.falling:
            self.speed = 0.0
            self.turn = 0.0
            self.fall(dt)
            return self.legs({"l": 0.0, "r": 0.0}, {"l": 0.0, "r": 0.0}, {s: self.feet[s][1] for s in "lr"})
        gy = self.pos[1]

        # body: move unless a probe would hit a block or a planted leg would
        # be stretched too far; slide along a wall when one axis is free
        yaw2 = self.yaw + math.radians(self.turn) * dt
        f2 = fwd(yaw2)
        dx, dz = f2[0] * self.speed * dt, f2[1] * self.speed * dt
        planted = [s for s in ("l", "r") if self.swing[s] is None]
        moved = False
        tries = ((yaw2, dx, dz), (yaw2, dx, 0.0), (yaw2, 0.0, dz), (yaw2, 0.0, 0.0),
                 (self.yaw, dx, dz), (self.yaw, dx, 0.0), (self.yaw, 0.0, dz))
        for n, (cy, cdx, cdz) in enumerate(tries):
            if n > 0 and cdx == 0 and cdz == 0 and cy == self.yaw:
                continue
            nx, nz = self.pos[0] + cdx, self.pos[2] + cdz
            if not self.probes_clear(nx, nz, cy, self.aim, gy, self.body_y):
                continue
            if self.legs_allow(nx, nz, cy, gy):
                if (cdx, cdz) != (dx, dz):
                    self.speed = math.hypot(cdx, cdz) / dt * (1 if self.speed >= 0 else -1)
                if cy != yaw2:
                    self.turn = 0.0
                self.pos[0], self.pos[2], self.yaw = nx, nz, cy
                moved = n == 0 or (dx == 0 and dz == 0 and self.turn == 0)
                break
        if not moved and (abs(self.want_speed) > 0.01 or abs(self.want_turn) > 0.5):
            self.blocked += 1
        if not moved:
            self.speed = 0.0 if not (dx == 0 and dz == 0) else self.speed
        f = fwd(self.yaw)

        # torso: toward its aim, unless its probes would hit
        target = self.yaw if aim_at is None else aim_at
        step = math.radians(G["aim_rate"]) * dt
        aim2 = self.aim + max(-step, min(step, wrap(target - self.aim)))
        if self.probes_clear(self.pos[0], self.pos[2], self.yaw, aim2, gy, self.body_y):
            self.aim = aim2

        # steps
        lead = self.speed * SWING * LEAD
        moving = abs(self.speed) > 0.01 or abs(self.turn) > 0.5
        for s in ("l", "r"):
            o = "r" if s == "l" else "l"
            if self.swing[s] is not None or self.swing[o] is not None:
                continue
            want = self.home(s, lead)
            off = math.dist((self.feet[s][0], self.feet[s][2]), want)
            other = math.dist((self.feet[o][0], self.feet[o][2]), self.home(o, lead))
            if off > (STEP if moving else SETTLE) and off >= other:
                lx, lz = self.pos[0] + f[0] * self.speed * SWING, self.pos[2] + f[1] * self.speed * SWING
                self.plan_step(s, lead, lx, lz, self.yaw + math.radians(self.turn) * SWING)

        # swing
        lift = {"l": 0.0, "r": 0.0}
        arcs = {"l": 0.0, "r": 0.0}
        rise = 0.0
        foot_y = {s: self.feet[s][1] for s in ("l", "r")}
        for s in ("l", "r"):
            if self.swing[s] is None:
                continue
            t, a, b = self.swing[s]
            t = min(1.0, t + dt / SWING)
            e = t * t * (3 - 2 * t)
            self.feet[s] = [a[0] + (b[0] - a[0]) * e, a[1] + (b[1] - a[1]) * e, a[2] + (b[2] - a[2]) * e]
            arc = math.sin(math.pi * t)
            lift[s] = (LIFT + 0.6 * abs(b[1] - a[1])) * arc
            arcs[s] = arc
            rise = max(rise, arc)
            foot_y[s] = self.feet[s][1]
            self.swing[s] = None if t >= 1.0 else (t, a, b)

        # body height follows the feet (a swinging foot by where it will land),
        # but never so far that a planted leg would be stretched out of reach
        target_y = sum(self.swing[s][2][1] if self.swing[s] is not None else foot_y[s] for s in "lr") / 2
        y2 = approach(self.pos[1], target_y, CLIMB * dt)
        # the bob and the landing dip settle first, so the height is checked with them
        dip2 = approach(self.dip, 0.0, DIP_RATE * dt)
        body2 = -CROUCH + BOB * rise - dip2
        if self.legs_allow(self.pos[0], self.pos[2], self.yaw, y2) and \
                self.probes_clear(self.pos[0], self.pos[2], self.yaw, self.aim, y2, body2):
            self.pos[1] = y2
        if self.probes_clear(self.pos[0], self.pos[2], self.yaw, self.aim, self.pos[1], body2):
            self.dip, self.body_y = dip2, body2
        return self.legs(lift, arcs, foot_y)

    def legs(self, lift, arcs, foot_y):
        """Joint angles for both legs (IK to each foot)."""
        f = fwd(self.yaw)
        pose = {}
        for s in ("l", "r"):
            mz = (self.feet[s][0] - self.pos[0]) * f[0] + (self.feet[s][2] - self.pos[2]) * f[1]
            base = ANKLE[1] + foot_y[s] - self.pos[1] - self.body_y
            # a swinging foot lifts less if the full lift would fold the leg too far
            for k_ in (1.0, 0.6, 0.3, 0.0):
                my = base + lift[s] * k_
                if k_ == 0.0 or leg_ok(my - HIP[1], mz - HIP[2]):
                    break
            hip, knee = leg_ik(my - HIP[1], mz - HIP[2])
            pose[f"hip_{s}"] = hip
            pose[f"knee_{s}"] = knee
            lo, hi = J["ankle_l"]["range"]       # the toe pitch is cosmetic: clamp it like the game does
            tilt = self.tilt(s) if self.swing[s] is None else 0.0   # planted: tilted to the ground
            pose[f"ankle_{s}"] = min(hi, max(lo, -(hip + knee) - TOE * arcs[s] - tilt))
        return pose


def out_of_range(pose):
    # 2.5 degrees of slack: walking off an edge, the trailing foot stays on the
    # last block with its toe over the drop and the body's bob can stretch that
    # leg a degree or two past its range for a moment; the game and the viewer
    # clamp every joint, so that foot just sits a little off its spot
    bad = []
    for k_, v in pose.items():
        lo, hi = J[k_]["range"]
        if v < lo - 2.5 or v > hi + 2.5:
            bad.append(f"{k_}={v:.0f}")
    return bad


def course(name, build, speed, ticks=500, expect=None, turn=0.0, start_y=0.0):
    w = World()
    build(w)
    m = Walker(w, y=start_y)
    m.want_speed = speed
    m.want_turn = turn
    worst, inside, ylo, yhi = [], 0, 1e9, -1e9
    for _ in range(ticks):
        pose = m.tick(0.05)
        worst += out_of_range(pose)
        if not m.probes_clear(m.pos[0], m.pos[2], m.yaw, m.aim, m.pos[1], m.body_y):
            inside += 1
        ylo, yhi = min(ylo, m.pos[1]), max(yhi, m.pos[1])
    ok = not worst and not inside
    verdict = ""
    if expect is not None:
        good = expect(m)
        ok &= good
        verdict = "as expected" if good else "NOT AS EXPECTED"
    hit = f", landed at {max(m.impacts):.1f} m/s" if m.impacts else ""
    print(f"{name:34s} ended at z {m.pos[2]:6.1f}, ground {ylo:.1f}..{yhi:.1f}, blocked {m.blocked:3d} ticks, "
          f"probe hits {inside}, joints {'ok' if not worst else 'OUT ' + str(worst[:3])}{hit} {verdict}")
    return ok


def gravity_checks():
    ok = True
    # spawned in the air: falls and lands on the ground
    m = Walker(World(), y=8.0)
    worst = []
    for _ in range(200):
        worst += out_of_range(m.tick(0.05))
    good = not m.falling and abs(m.pos[1]) < 0.01 and not worst and len(m.impacts) == 1
    print(f"{'spawned 8 m up':34s} ended at ground {m.pos[1]:.2f}, landed at {m.impacts[0] if m.impacts else 0:.1f} m/s, joints "
          f"{'ok' if not worst else 'OUT'} {'as expected' if good else 'NOT AS EXPECTED'}")
    ok &= good

    # standing on a platform that is removed: falls to the ground below
    w = World()
    for x in range(-12, 13):
        for z in range(-12, 13):
            w.tops[(x, z)] = 4
    m = Walker(w, y=4.0)
    for _ in range(20):
        m.tick(0.05)
    w.tops.clear()
    worst = []
    for _ in range(200):
        worst += out_of_range(m.tick(0.05))
    good = not m.falling and abs(m.pos[1]) < 0.01 and not worst and m.falls == 1
    print(f"{'platform removed (4 blocks)':34s} ended at ground {m.pos[1]:.2f}, falls {m.falls}, joints "
          f"{'ok' if not worst else 'OUT'} {'as expected' if good else 'NOT AS EXPECTED'}")
    ok &= good

    # a pit opens under one foot: that foot steps instead of the mech falling
    w = World()
    for x in range(-12, 13):
        for z in range(-12, 13):
            w.tops[(x, z)] = 1
    m = Walker(w, y=1.0)
    for _ in range(20):
        m.tick(0.05)
    fx, fz = m.feet["l"][0], m.feet["l"][2]
    for x in range(math.floor(fx) - 1, math.floor(fx) + 2):
        for z in range(math.floor(fz) - 1, math.floor(fz) + 3):
            w.tops[(x, z)] = 0
    worst = []
    for _ in range(100):
        worst += out_of_range(m.tick(0.05))
    good = not m.falling and m.falls == 0 and m.forced >= 1 and not worst and m.supported("l") and m.supported("r")
    print(f"{'pit under one foot':34s} feet at {m.feet['l'][1]:.0f}/{m.feet['r'][1]:.0f}, forced steps {m.forced}, "
          f"falls {m.falls}, joints {'ok' if not worst else 'OUT'} {'as expected' if good else 'NOT AS EXPECTED'}")
    ok &= good
    return ok


def main():
    # IK round trip over the leg's reach
    worst = 0.0
    for i in range(41):
        for j in range(41):
            hip, knee = -40 + 2 * i, -40 + 2 * j
            p = leg_fk(hip, knee)
            h2, k2 = leg_ik(*p)
            q = leg_fk(h2, k2)
            worst = max(worst, math.dist(p, q), abs(h2 - hip) + abs(k2 - knee))
    print(f"IK round trip: worst error {worst:.2e}")
    print(f"rest pose IK: {leg_ik(ANKLE[1] - HIP[1], ANKLE[2] - HIP[2])} (should be 0, 0)")

    # flat ground: every speed and turn rate keeps every joint in range
    ok = True
    REACH[0] = 0.0
    for speed in (0.0, 0.5 * MAX_SPEED, MAX_SPEED, -0.5 * MAX_SPEED):
        for turn in (0.0, MAX_TURN, -MAX_TURN):
            w = Walker(World())
            w.want_speed, w.want_turn = speed, turn
            lo, hi = {}, {}
            for _ in range(400):
                pose = w.tick(0.05)
                for k_, v in pose.items():
                    lo[k_] = min(lo.get(k_, 0), v)
                    hi[k_] = max(hi.get(k_, 0), v)
            bad = [f"{k_} {lo[k_]:.0f}..{hi[k_]:.0f} (range {J[k_]['range']})" for k_ in lo
                   if lo[k_] < J[k_]["range"][0] - 0.5 or hi[k_] > J[k_]["range"][1] + 0.5]
            span = " ".join(f"{k_}={lo[k_]:.0f}..{hi[k_]:.0f}" for k_ in ("hip_l", "knee_l", "ankle_l"))
            print(f"flat, speed {speed:5.2f} m/s turn {turn:5.1f} deg/s: {span}" + (f"  OUT: {bad}" if bad else ""))
            ok &= not bad
    print(f"stride at full speed: {MAX_SPEED * 2 * SWING:.2f} m ({MAX_SPEED:.2f} m/s, a step every {SWING} s)")
    print(f"longest reach asked of a leg on flat ground: {REACH[0]:.0%} of its length")
    if REACH[0] > MAX_REACH + 0.005:
        print("A FOOTHOLD IS OUT OF REACH")
        ok = False

    # courses: the mech starts at z 0 and walks toward +z
    def platform(h, z0=12, z1=40):
        def build(w):
            for x in range(-20, 21):
                for z in range(z0, z1):
                    w.tops[(x, z)] = h
        return build

    def wall(w):      # one block thick: too high to step over
        for x in range(-20, 21):
            w.tops[(x, 14)] = 4

    def cliff(w):     # four blocks up: too high to climb
        for x in range(-20, 21):
            for z in range(14, 40):
                w.tops[(x, z)] = 4

    # what this type should manage: steps up to max_rise, and a bar where its turret is
    climb = int(MAX_RISE + 1e-6)
    top = max(y for f, x, y, z in PROBES if f == "torso")
    bar_y = (math.floor(top) - 1, math.floor(top))

    def bar(w):   # a beam at turret height, open underneath
        for x in range(-20, 21):
            for y in bar_y:
                w.blocks.add((x, y, 16))

    print(f"\n{SPEC.get('label', TYPE)}: climbs {climb} blocks, turret up to {top:.1f} m")
    ok &= course("one-block step up and down", platform(1, 12, 30), MAX_SPEED,
                 expect=lambda m: m.pos[2] > 32)
    ok &= course("two-block step up and down", platform(2, 12, 30), 0.5 * MAX_SPEED,
                 expect=lambda m: m.pos[2] > 32)
    if climb >= 3:
        ok &= course("three-block step up and down", platform(3, 12, 30), MAX_SPEED,
                     expect=lambda m: m.pos[2] > 31)
        ok &= course("three-block step, walking slowly", platform(3, 12, 30), 0.5 * MAX_SPEED,
                     expect=lambda m: m.pos[2] > 31, ticks=700)
    else:
        ok &= course("three-block ledge (too high)", platform(3, 12, 30), MAX_SPEED,
                     expect=lambda m: m.pos[2] < 13 and m.blocked > 50)
    ok &= course("four-block ledge (too high)", platform(4, 12, 30), MAX_SPEED,
                 expect=lambda m: m.pos[2] < 13 and m.blocked > 50)
    ok &= course("one-block step down", lambda w: [w.tops.__setitem__((x, z), 1 if z < 12 else 0)
                                                   for x in range(-20, 21) for z in range(-10, 40)],
                 MAX_SPEED, expect=lambda m: m.pos[2] > 30)
    ok &= course("four-block wall (too high)", wall, MAX_SPEED,
                 expect=lambda m: m.pos[2] < 14 and m.blocked > 50 and max(m.feet["l"][2], m.feet["r"][2]) < 14)
    ok &= course("four-block cliff (too high)", cliff, MAX_SPEED,
                 expect=lambda m: m.pos[2] < 14 and m.blocked > 50)
    ok &= course("bar at turret height", bar, MAX_SPEED,
                 expect=lambda m: m.pos[2] < 16 and m.blocked > 50)
    ok &= course("three-block step down", lambda w: [w.tops.__setitem__((x, z), 3 if z < 12 else 0)
                                                     for x in range(-20, 21) for z in range(-10, 60)],
                 MAX_SPEED, expect=lambda m: m.pos[2] > 30 and (m.falls == 0 or climb < 3), start_y=3.0)
    for top, edge in ((12, 12), (14, 14), (30, 9)):
        ok &= course(f"walking off a {top}-block cliff", lambda w, top=top, edge=edge: [
            w.tops.__setitem__((x, z), top if z < edge else 0) for x in range(-20, 21) for z in range(-12, 60)],
            MAX_SPEED, expect=lambda m: m.falls == 1 and len(m.impacts) == 1 and m.impacts[0] > 15
            and abs(m.pos[1]) < 0.01, start_y=float(top))

    def side_wall(w):   # a tall wall just right of the mech, along its path
        for z in range(-10, 40):
            for y in range(0, 14):
                w.blocks.add((-4, y, z))
    ok &= course("turning on the spot beside a wall", side_wall, 0.0, turn=-MAX_TURN,
                 expect=lambda m: True)
    ok &= gravity_checks()
    ok &= course("stairs up (1 block every 3)", lambda w: [w.tops.__setitem__((x, z), min(10, max(0, (z - 9) // 3)))
                                                          for x in range(-20, 21) for z in range(9, 120)],
                 MAX_SPEED, expect=lambda m: m.pos[1] > 9)
    print()
    print("all checks pass" if ok else "SOME CHECKS FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
