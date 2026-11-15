# Mech design

The lower body of a two-legged mech: a pelvis and two digitigrade
(reverse-knee) legs. It has 44 parts (6 in the pelvis, 19 in each leg) and
weighs 3501 kg. [PARTS.md](PARTS.md) lists every part.

## Frame and placement

Mech frame: **+X left, +Y up, +Z forward**, in meters. The origin is on the
ground midway between the hips. The hips are 3.0 m up at x = ±0.75
(`HIP_X`).

The leg is designed once, as the left leg, in its own leg frame (the origin
on the ground under the hip, +X outboard). The right leg is the same parts with
every model mirrored in X (`place_leg` in `mech_parts.py`). Leg part ids end
in `_l` or `_r`.

Each leg has three rigid segments, hung from the pelvis by three hinges about X:

```
pelvis --hip_l--> thigh_l --knee_l--> shin_l --ankle_l--> foot_l
       --hip_r--> thigh_r --knee_r--> shin_r --ankle_r--> foot_r
```

Every part rides one segment. The game puts each display at the mech position
and sets its matrix to:

```
mech * segment(pose) * translate(pivot) * rotate(rest)
```

`segment(pose)` turns about X through each joint up the chain. Positive angles
swing the part below the joint backward. Piston parts (`aim`) are placed at
their posed pivot instead, with local +Y pointing at their posed `links.to`
point. `parts.json` gives each joint its range. Inside that range the rod
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

`tools/viewer/` has sliders for all six joints. It also has a walk cycle, with
the legs half a stride apart and the body raised or lowered so the lower foot
stays on the ground, and a "keep foot level" option that sets the ankles.

## Not done yet

- The torso (it will sit on the waist ring), arms and cockpit.
- Game code (`tc/`): spawning, posing, walking and damage.
- Not loaded in game yet; the models have only been checked in the viewer.
