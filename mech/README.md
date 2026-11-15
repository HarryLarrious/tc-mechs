# Mech design

A two-legged mech: an armored turret torso that turns on a pelvis, carried by
two digitigrade (reverse-knee) legs. It has no head and no arms. Its weapons
are two heavy rotary cannons on the sides of the torso and two light machine
guns on the roof, and each gun is its own set of parts.

It has 62 parts (6 in the pelvis, 19 in each leg, 8 in the torso, 10 in the
guns) and weighs 6366 kg. [PARTS.md](PARTS.md) lists every part.

## Frame and placement

Mech frame: **+X left, +Y up, +Z forward**, in meters. The origin is on the
ground midway between the hips. The hips are 3.0 m up at x = ±0.75
(`HIP_X`).

The leg is designed once, as the left leg, in its own leg frame (the origin
on the ground under the hip, +X outboard). The right leg is the same parts with
every model mirrored in X (`place_leg` in `mech_parts.py`). Leg part ids end
in `_l` or `_r`.

The parts ride rigid segments joined by joints. Each leg has three segments
on hinges about X, the torso turns about Y on the waist ring, and each gun
elevates about X on its mount:

```
pelvis --hip_l--> thigh_l --knee_l--> shin_l --ankle_l--> foot_l
       --hip_r--> thigh_r --knee_r--> shin_r --ankle_r--> foot_r
       --waist (Y)--> torso --elev_hl--> hgun_l    --elev_ll--> lgun_l
                            --elev_hr--> hgun_r    --elev_lr--> lgun_r
```

Every part rides one segment. The game puts each display at the mech position
and sets its matrix to:

```
mech * segment(pose) * translate(pivot) * rotate(rest)
```

`segment(pose)` turns about each joint's axis through its pivot, up the chain.
On the leg joints, positive angles swing the part below the joint backward. On
the gun joints, negative angles raise the muzzle. Piston parts (`aim`) are placed at
their posed pivot instead, with local +Y pointing at their posed `links.to`
point. Spin parts (`spin_z`, the heavy barrel clusters) take one more turn
about their own Z axis. `parts.json` gives each joint its axis, pivot and
range. Inside that range the rod
stays in the barrel (capped at ±45°).

The models are half size, as in the rally car, and the item definitions scale
them back up. Custom model data string 0 `damaged` changes a part to its
dented, scorched `_damaged` model. Tint 0 is the armor paint and tint 1 the
accent.

## Pelvis

The root part. Each leg's hip mount bolts up under one end of it.

| Part | What it is |
| --- | --- |
| `pelvis` | Crossbeam over both hip flanges, with end caps and a vented keel that hangs between the legs |
| `waist_ring` | A slewing ring on top (gear teeth, turntable, status lights) with a vertical drive motor behind it. The torso will turn on it |
| `pelvis_armor` | V-shaped front plates with an accent chevron, and plates over both hip flanges |
| `power_pack` | Battery case behind the keel, with vents, a charge light bar, cooling fins and a cable to each hip motor |
| `compressor` | Air compressor under the power pack, with hoses up to both legs' air tanks |
| `rear_armor` | Cowl and side plates over the power pack |

## Torso

The torso is a low, wide turret hull (1.6 m wide, 2.5 m long with the
bustle) on a base disc that sits on the waist ring's turntable. It can turn all
the way round.

| Part | What it is |
| --- | --- |
| `torso_frame` | Hull core, base disc and collar, belly plate, and the hardpoints for the side and roof guns |
| `torso_front` | Lower and upper glacis that meet in a beak around the viewport, angled cheeks, accent stripes |
| `torso_top` | Roof with raised panels, a hatch in a warning ring, and edge chamfers |
| `torso_side_l`, `torso_side_r` | Sloped side slabs (top leaning in) and lower skirts. Each comes off on its own |
| `sensors` | Viewport slit with a running light, and a twin-lens camera pod and rangefinder on the roof |
| `ammo_bustle` | Armored magazine behind the hull, with feed chutes running to both heavy gun mounts |
| `antenna` | Mast with a tip light, and a whip, on the bustle |

## Guns

Every gun is separate from the torso, and the parts in each gun are separate
from each other, so a gun can be swapped or shot off on its own. The
right-hand guns are the left-hand ones mirrored.

| Part | What it is |
| --- | --- |
| `heavy_mount_l/r` | Base plate bolted to the side armor, with a finned elevation motor, gussets and the feed port. Elevation is +35° up to 12° down |
| `heavy_gun_l/r` | Six-barrel rotary cannon: armored receiver, barrel drive housing with a light ring, a vented heat shield to a front barrel clamp, a recoil buffer and a feed inlet |
| `heavy_barrels_l/r` | The barrel cluster (six barrels on a spindle, two clamps, a muzzle ring). It spins about its own axis (`spin_z`) |
| `light_mount_l/r` | Pintle on the roof: base ring, turntable, yoke and a small elevation motor |
| `light_gun_l/r` | Light machine gun: receiver with an armored cover, a gun shield, a cooling jacket, an ammo can and a sight. Elevation is +35° up to 8° down |

## Leg

The hip is 3.0 m above the ground. The knee points forward, and the ankle is
behind the hip, above a three-toed foot with a heel spur.

Each joint has both an electric motor and an air piston:

| Joint | Motor | Air piston |
| --- | --- | --- |
| Hip | Large servo with four fins, on the outboard side, under an armored cap | Behind the hip, from an anchor arm on the hip mount to the back of the thigh |
| Knee | Servo on the inboard side | Outboard, across the front of the knee, from the thigh to the shin |
| Ankle | Small servo on the inboard side | Behind the shin, from the shin to the heel horn |

Each piston is two parts: an aluminum cylinder (with tie rods, brass ports, a
return line and a warning band) and a chrome rod. They aim at each other, so
the rod slides in the barrel as the joint turns. Each leg's air tank and valve
block sit behind its hip mount, filled by the compressor in the pelvis. A hose
runs from the tank to the hip piston.

The armor is bolted plates with accent stripes and warning plates:

- a hip tasset and a cap over the hip motor,
- thigh plates (front, sides),
- a rounded knee cap,
- a two-piece greave with side wings,
- toe caps and an instep plate.

Armor parts break off (`detach`). Each one shields the part under it.

## Viewer

`tools/viewer/` has a slider for every joint: the six leg joints, the waist
and the four gun elevations. It has a walk cycle, with the legs half a stride
apart and the body raised or lowered so the lower foot stays on the ground,
and a "keep feet level" option that sets the ankles. "Turret sweep" swings the
torso and aims the guns, and "Spin barrels" turns the heavy barrel clusters.

## Not done yet

- Collision limits: the joint ranges keep the pistons working but do not stop
  parts from passing through each other.
- Game code (`tc/`): spawning, posing, walking, aiming, firing and damage.
- Not loaded in game yet; the models have only been checked in the viewer.
