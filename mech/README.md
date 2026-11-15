# Mech design

## The leg

A digitigrade (reverse-knee) leg for a two-legged mech. The hip is 3.0 m above
the ground. The knee points forward and the ankle is behind the hip, above a
three-toed foot with a heel spur. It has 19 parts and weighs 1251 kg.
[LEG_PARTS.md](LEG_PARTS.md) lists every part.

Each joint has both an electric motor and an air piston:

| Joint | Motor | Air piston |
| --- | --- | --- |
| Hip | Large servo with four fins, on the outboard side, under an armored cap | Behind the hip, from an anchor arm on the hip mount to the back of the thigh |
| Knee | Servo on the inboard side | Outboard, across the front of the knee, from the thigh to the shin |
| Ankle | Small servo on the inboard side | Behind the shin, from the shin to the heel horn |

Each piston is two parts: an aluminum cylinder (with tie rods, brass ports, a
return line and a warning band) and a chrome rod. They aim at each other, so
the rod slides in the barrel as the joint turns. The air tank and valve block
sit behind the hip mount, and a hose runs from the tank to the hip piston.

The armor is bolted plates in the armor paint (tint 0), with accent stripes
(tint 1) and warning plates:

- a hip tasset and a cap over the hip motor,
- thigh plates (front, sides),
- a rounded knee cap,
- a two-piece greave with side wings,
- toe caps and an instep plate.

Armor parts break off (`detach`). Each one shields the frame part under it.

## Frame and placement

Leg frame: **+X left (outboard for the left leg), +Y up, +Z forward**, in meters.
The origin is on the ground under the hip. The right leg will use the same
parts mirrored in X (`mirror_x` in `mech_lib.py`).

The leg has four rigid segments joined by three hinges about X:

```
pelvis --hip--> thigh --knee--> shin --ankle--> foot
```

Every part rides one segment. The game puts each display at the mech position
and sets its matrix to:

```
mech * segment(pose) * translate(pivot) * rotate(rest)
```

`segment(pose)` turns about X through each joint up the chain. Positive angles
swing the part below the joint backward. Piston parts (`aim`) are placed at
their posed pivot instead, with local +Y pointing at their posed `links.to`
point. `leg_parts.json` gives each joint its range. Inside that range the rod
stays in the barrel (capped at ±45°).

The models are half size, as in the rally car, and the item definitions scale
them back up. Custom model data string 0 `damaged` changes a part to its
dented, scorched `_damaged` model.

## Not done yet

- The right leg (mirrored models), the pelvis and the body.
- Game code (`tc/`): spawning, posing and damage.
- Not loaded in game yet; the models have only been checked in the viewer.
