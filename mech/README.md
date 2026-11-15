# Mech design

A two-legged mech: an armored turret torso that turns on a pelvis, carried by
two digitigrade (reverse-knee) legs. It has no head and no arms. Its weapons
are two heavy rotary cannons on the sides of the torso and two light machine
guns on the roof, and each gun is its own set of parts.

It stands about 10.4 m tall to the roof of the turret, and a player sits
inside the turret's cabin (see [Cockpit](#cockpit)).

It has 63 parts (6 in the pelvis, 19 in each leg, 9 in the torso, 10 in the
guns). [PARTS.md](PARTS.md) lists every part. The masses (6446 kg in total)
are still the ones set for the original small design. Physics will need them
scaled up.

## Scale

The parts are designed at a small size (hips 3.0 m up, 0.75 m either side of
the centerline). `MECH_SCALE` in `mech_lib.py` (2.1) then scales everything
about the origin as the models and data are written. This scales the elements,
pivots, piston mounts and joint pivots. Angles and joint ranges stay the same.
Every size below is at the design size, so multiply it by 2.1 for the real one.
In real size, the hips are 6.3 m up and 1.575 m either side of the
centerline. The cockpit fittings are the exception: they are sized in real
meters, to fit a player.

## Frame and placement

Mech frame: **+X left, +Y up, +Z forward**, in meters. The origin is on the
ground midway between the hips.

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
stays in the barrel. The leg joints are also capped short of what the
pistons allow: the hip to 90°, the knee to 75°.

The models are 1/5 size (`MODEL_SCALE` 0.2, where the rally car's are half
size), so a part can reach 7.5 m from its pivot inside Minecraft's -16..32
element limit. The item definitions scale them back up by 5. Custom model data string 0 `damaged` changes a part to its
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
bustle, at the design size) on a base disc that sits on the waist ring's
turntable. It can turn all the way round.

### Cockpit

The hull is hollow. Its floor, walls and ceiling are plates whose inner faces
show from inside, so the cabin is a snug room for one pilot. At real size it
has 1.43 m of headroom over the floor grating. The `cockpit` part fits it out
with:

- a low pilot's chair, fighter style: the seat pan is 0.22 m up and tilted
  front-up, and the backrest, headrest and side bolsters lean back 25°
  (`RECLINE`),
- a joystick on the front of each armrest, with a lit fire button,
- three screens: one on a stand under the viewport, and one angled in from
  each front corner.

The pilot leans back with the chair. Their eyes are 1.03 m from the hips
along the back, so 0.93 m above the seat and 1.15 m above the floor. The top
of the head is about 1.42 m up, just under the ceiling. The viewport is a slit
across the front wall from 0.92 to 1.34 m, which puts those eyes in it. A
tunnel through the glacis leads to the visor. The visor model has only its
outside face, so from inside it is see-through and from outside it is dark
glass.

`parts.json` gives `cockpit_seat` (the seat's top center), `cockpit_eye`
(where the pilot's eyes go) and `cockpit_recline`. The viewer seats a
reclined player there for scale. In game the pilot is a drawn body that
reclines with the chair (see [Pilot model](#pilot-model)).

The roof hatch (`hatch`, at the back of the cabin) is a separate part on a
hinge along its rear edge. It turns about its own X axis (anim `hinge_x`):
0° is shut, -110° is open, with the lid standing up behind the hole so the
pilot can get in over its side. The ceiling and roof plates have a matching
square hole.

| Part | What it is |
| --- | --- |
| `torso_frame` | Hollow hull (floor, walls, ceiling, front wall with the viewport opening), base disc and collar, belly plate, and the hardpoints for the side and roof guns |
| `cockpit` | Reclined pilot's chair, two joysticks, three screens |
| `torso_front` | Lower and upper glacis that meet in a beak around the viewport, angled cheeks, accent stripes |
| `torso_top` | Roof with raised panels, a hatch hole in a warning ring, and edge chamfers |
| `hatch` | The roof hatch: armored lid with a handle and hinge knuckles, opens backward on its hinge |
| `torso_side_l`, `torso_side_r` | Sloped side slabs (top leaning in) and lower skirts. Each comes off on its own |
| `sensors` | Viewport visor with a running light under it, and a twin-lens camera pod and rangefinder on the roof |
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

The hip is 3.0 m above the ground (6.3 m at real size). The knee points forward, and the ankle is
behind the hip, above a broad, flat foot: a sole frame with a hinged toe plate
and heel plate, each sprung by a pair of dampers on the outside of the foot,
on split rubber tread pads.

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
- a toe cap with a striped nose, a heel guard, side plates and an instep plate.

Armor parts break off (`detach`). Each one shields the part under it.

## Procedural walk

The mech has no animation clips. Each tick it works out its own steps from
where its body is going: `tc/gait.tc` on the plot, the same code in the
viewer, and `tools/gait_check.py` as the reference with its checks. All three
read their numbers from `GAIT` in `pack/src/mech_lib.py`, through
`parts.json` and `mechGait()` in `tc/mech_data.tc`, so tuning happens in one
place.

- **Body:** it moves and turns at a commanded speed and turn rate, which ease
  in and out. The fastest is 3.8 m/s forward, half that backward, and 40°/s.
  It is crouched 0.42 m, which keeps the legs from straightening and lets them
  reach further, and it rises 0.1 m as each foot passes mid-swing.
- **Steps:** a planted foot stays where it is in the world. A foot steps when
  it lags more than 0.63 m (0.13 m when standing) behind its home spot, and
  only while the other foot is planted, so the feet alternate. The home spot
  is under its hip, moved half a step ahead at speed. The swing takes 0.6 s.
  It goes from where the foot is to where its home will be when it lands,
  eased in and out, lifting 0.53 m at mid-swing with the toes pitched down
  12°.
- **Legs:** inverse kinematics. Each leg turns only about X, so it works in
  its own plane. The hip and knee angles come from the hip-knee-ankle
  triangle, with the knee always bending the way it does at rest. The ankle
  keeps the foot level. Each angle is clamped to its joint's range, and the
  pistons follow because they aim at their mounts. `tools/gait_check.py`
  checks that the IK lands the ankle exactly where it was asked. It also
  checks that walking at every speed and turn rate keeps every joint in range
  and every foothold within reach.
- **Stride:** at a steady speed the feet step back to back, so the stride is
  speed × 2 × swing time: 4.5 m at full speed. The joints' range sets the
  limit. At full speed the legs use up to 93% of their reach, with every
  joint at least 6° inside its range.
- **Torso:** it faces where it was facing and turns toward its aim at 30°/s.
  So it trails the body's turns and then swings back to face ahead. When the
  mech follows a player, the torso and the guns aim at them.

A mech's legs only hinge about X (no hip yaw), so when it turns, a planted
foot slides sideways a little until it steps.

### Blocks

The walk reads the blocks around it (`tc/terrain.tc`). There is no ground
smoothing, as there is for the rally car's wheels. A walking foot plants flat
on whatever block tops are under it.

- **Footholds:** the ground under a foot is the highest block top under its
  heel, middle, toe and both sides. It is found by a raycast down from 3.7 m
  above the foot to 3.2 m below it, cached per column for two seconds. A
  block at the top of that reach is a wall, not ground. The middle of the
  foot must be on the top too, so a foot never perches on an edge by its heel
  or toe.
- **Choosing a step:** the foot tries the planned landing spot, then longer
  steps, then shorter ones. A longer step gets the whole foot onto a step,
  and it brings the trailing foot up a tall step that the body is waiting
  at. It takes the first spot that meets every test:
  - it has ground,
  - it is within 3.2 m (three blocks) above or below the other foot,
  - the foot's sweep from heel to toe crosses nothing higher than both ends,
    checked every half block,
  - the leg can reach it at some body height between the two feet, with
    every joint at least 1° inside its range and the leg under 97% of its
    length.

  A step up or down lifts the foot higher, by 0.6 × the height difference.
  The mech climbs steps of up to three blocks, and a 4-block ledge is a wall
  to it. A drop deeper than three blocks is walked off (see Gravity).
- **Body height:** it follows the feet at 2.1 m/s, with a swinging foot
  counted where it will land, so the body is already moving up or down a
  tall step as the foot gets there. It stops short of any height where a
  planted leg would go out of reach (a leg already out of reach never stops a
  move that helps it), or where a probe would hit a block.
- **Hitbox:** 32 collision probe points (`PROBES` in `mech_lib.py`) on the
  hips, knees, shins, turret hull and heavy guns. The body probes turn with
  the heading, and the hull and gun probes turn with the torso. A move or turn
  that would put any probe in a solid block is tried along one axis only, so
  the mech slides along a wall. If neither axis works, it stops. The torso
  will not turn its guns into a wall. The body also never moves so far that a
  planted leg would overstretch, so a mech whose feet can't go on stops and
  waits.

### Gravity

- **Lost ground:** every tick a planted foot checks the block top under it.
  If its ground is gone or lower, or a block has been placed into it, the
  foot steps at once to the best landing spot it can find.
- **Walking off a drop:** walking toward a drop deeper than three blocks, the
  foot steps out level over it. It then has no ground, so the mech falls. It
  falls from any height.
- **Falling:** if no spot works, or both feet lose their ground, the mech
  falls. Gravity is 15 m/s², heavier-feeling than a player's, up to 40 m/s.
  The feet swing to hang under the hips. It lands when a foot meets a block
  top below it; a foot still resting on an edge does not hold it up. If
  falling would put a probe or a foot inside a block, the whole mech is
  pushed clear (forward first, then back, then sideways, up to 3 m), so it
  slides off an edge rather than through it. If nothing clears, it comes to
  rest where it is. A mech spawned in the air falls too.
- **Landing:** every landing reports its impact speed to `mechLanded(m,
  speed)` in `tc/gait.tc`. For now it only stores it, in `gImpact`; the
  damage model will hurt the mech there when it lands too hard. For scale, a
  12-block drop lands at about 19 m/s and a 30-block drop at 30 m/s. On a
  hard landing the body sinks up to 0.32 m into its legs and comes back up at
  1 m/s.
- **Idle mechs:** a mech that has stood still with nothing to do for a second
  stops being walked and redrawn. Its feet are still checked every half
  second, and it wakes up as soon as one loses its ground.

`tools/gait_check.py` walks the reference model over test courses:

- climbing 1-, 2- and 3-block steps (at full and half speed) and a
  staircase, and stepping back down,
- stopping at a 4-block ledge, a 4-block wall one block thick, a 4-block
  cliff, and a bar at turret height,
- walking off 12-, 14- and 30-block cliffs, falling and landing (checking the
  landing speed),
- turning on the spot beside a tall wall,
- falling: spawned 8 m up, standing on a platform that is removed, and a pit
  opening under one foot (it steps aside instead of falling).

It checks that no probe ever ends up inside a block and that every joint
stays in range. The viewer's "Course" menu builds the same kinds of
obstacles, including a 4-block platform. "Remove blocks under it" knocks a
hole under the mech to watch it fall.

## Parked kneel

A mech without a pilot and with nothing to do goes down on its left knee
(`KNEEL_POSE` in `pack/src/mech_lib.py`, `mechKneelPose()` in game). It first
stops and lets its feet settle. Then over `kneel_time` (1.5 s) the leg
joints blend from the walk's inverse kinematics into the kneel pose and the
body drops `kneel_drop` (1.57 m). The right foot stays flat on the ground
ahead and the left knee guard rests just above the ground. `@walk`, `@turn`
and `@follow` make it stand up first, the same way back. A new mech spawns
kneeling.

The pose was found by a search over the joint ranges, which is why the hip
can now swing to -105°.

## Piloting

`@board` starts boarding the nearest free mech within 30 blocks
(`tc/pilot.tc`). It is a sequence:

1. Your pilot body appears where you stand and the real you is hidden. You
   walk to the front of the mech's front (right) foot while the mech kneels,
   turns its turret ahead, levels its guns and opens its hatch.
2. You climb (11 s): onto the toe and the top of the foot, hand over hand up
   the shin to the knee guard, up the torso front onto the roof, back along
   the roof outside the right light gun, onto the hatch's side rim, down onto
   the cabin floor, turn to face ahead, and slide forward into the chair.
3. The hatch shuts.
4. The mech stands up, and you have the controls.

Getting out (F or `@exit`) runs it backwards: the mech kneels, opens up, and
you climb out and down the front leg. Your real body comes back in front of
the foot, and the mech stays parked.

The climb is a timeline baked by `pack/src/mech_pilot.py`
(`board_timeline`): 10 samples a second of the figure's hips, lean, yaw, feet
and hands, in the mech frame with the mech kneeling. The holds on the leg and
the torso front were measured off the kneeling model in the viewer. On the
shin each limb holds for half a cycle and then moves up 0.6 m, a foot with
the opposite hand. The rest is keyframes. The last sample is the seated pose.
The game plays it through the torso's transform, and the viewer's "Board"
and "Get out" buttons play the same timeline.

| Control | What it does |
| --- | --- |
| W / S | Walk forward (full speed) / back (half speed) |
| A / D | Turn left / right on the legs |
| Look around | The turret turns toward where you look, at 60°/s, and all four guns tilt to your pitch |
| F | Get out (`@exit` too) |
| Shift | Nothing: dismounting is cancelled, so you can't fall out by accident |

The walk, the terrain and gravity all apply as before. The legs carry the
body where you steer, and the turret aims on its own, so you can walk one way
while watching another. A piloted mech never goes idle. The action bar shows
speed, heading, how far the turret lags behind your aim, the last landing's
impact speed, and plot CPU.

### Pilot model

The pilot is your own skin on six item displays, ported from the rally game's
driver model (`pack/src/mech_pilot.py`). Each display holds your player head.
The pack's core shader (`pack/assets/minecraft/shaders/core/entity.*`) draws
a head as another body part when the display's brightness marks it (sky
light 0, block light = part id: 1 head, 2 torso, 3 and 4 right and left arm,
5 and 6 right and left leg).

Every part holds the same item (`mech:pilot/unit`, a head as a 1 x 1 x 1
box) and is posed every tick from a figure pose: the hips, the body's lean,
and where the feet and hands are. Each limb is a straight Minecraft limb
from its hip or shoulder to its end point, stretched a little to reach, with
its front turned the least way from hanging straight down. Seated, the body
reclines with the chair and the hands are on the joysticks. The head looks
where you look, within what a neck allows. The walk to the mech is posed
live, with the legs and arms swinging.

You ride the mech's seat entity, placed every tick so your eye is at the
model head's center (`tc/pilot_data.tc` gives the timeline). The shader drops the
head when the camera is inside it, so in first person you see your arms on
the sticks. The real player is hidden from the others (Set Entity Hidden),
from yourself in third person (invisibility), and your hand item draws
nothing (`mech:empty`).

## Viewer

`tools/viewer/` has a slider for every joint: the six leg joints, the waist
and the four gun elevations. "Walk" runs the procedural walk: W and S walk
forward and back, A and D turn, and the camera follows the mech. "Feet level"
keeps the ankles flat. "Turret sweep" swings the torso and aims the guns, and
"Spin barrels" turns the heavy barrel clusters. "Parked (kneel)" blends the
mech down on one knee and back, "Hatch open" opens the roof hatch, and a
posed pilot figure sits in the chair. "Board" and "Get out" play the climb.

## Not done yet

- Collision limits: the joint ranges keep the pistons working but do not stop
  parts from passing through each other.
- Game code: firing and damage. `tc/` can spawn, pose, walk over blocks
  (with gravity), be piloted and remove mechs so far.
- Not loaded in game yet; the models have only been checked in the viewer.

## Plot code

`tc/mech_data.tc` is generated with the models. It holds the segments
(`mechSegData`: parent, joint, axis, pivot, range) and the parts
(`mechPartData`: item model, segment, anim, pivot, rest rotation columns,
aim target). `tc/mech.tc` spawns one item display per part on the mech
origin. It computes each segment's posed transform from the joint angles,
then sets each display's matrix to
`heading * segment * translate(pivot) * rotate(rest)`. Pistons are aimed at
their posed targets and the heavy barrels get their spin angle. This is the
same math as the viewer.

The displays do not stand on the origin itself, which is often inside the
ground (crouched or kneeling). They stand on an anchor 1 m above the ground,
and their matrices add the origin's offset from it. Their culling box (15 m
wide, 12 m tall) covers the whole mech. Occlusion culling mods (Entity
Culling, Sodium) hide an entity whose position is out of sight, so with the
displays on the buried origin the whole mech could vanish. The pilot body is
anchored the same way, just above its soles.
