# Mech design: the sprinter

A light, fast two-legged mech, built in `pack/src/mech_sprinter.py`. Like the
[walker](../README.md), it is a turret on two digitigrade legs with no head
and no arms. It has the same kinds of parts with the same ids, so the game's
gait, damage model and pilot code drive it without changes. [PARTS.md](PARTS.md)
lists its parts.

## How it differs from the walker

| | Walker | Sprinter |
| --- | --- | --- |
| Scale (design to real) | 2.1 | 1.5 |
| Roof of the turret | 10.4 m | 8.1 m |
| Hips | 6.3 m up, 1.58 m from the middle | 4.95 m up, 1.58 m from the middle (wider for its size) |
| Mass | 6466 kg | about 2900 kg |
| Armor | full | 55% of the walker's hit points (other parts 75%) |
| Top speed, stride | 3.8 m/s, 4.5 m | 6.3 m/s, 5.3 m (a step every 0.42 s) |
| Climbs | 3 blocks | 2 blocks |
| Guns | 2 side cannons, 2 roof machine guns | 2 side cannons, 1 roof machine gun in the middle |
| Turning | A/D | where the pilot looks, with A/D strafing |

## Look

Every armor piece is faceted. The thigh and shin plates are V ridges, and the
knee guard comes to a point. The pelvis has a V prow. The turret is a wedge
with chined sides. Its nose is a chisel: a lower and an upper glacis meet in a
ridge, with a facet at each end back to the chines. A wide visor sits over the
nose, under a sloped brow. The paint is bone white with racing-red trim.

The feet are long, narrow and one width from heel to toe. Each foot is one
rigid piece in three sections. A heel block goes down and back from a large
ankle hub. A long metatarsal goes down to a low mid-foot hub. A toe block goes
on to the tip. Each section has its own rubber pad. Sprung dampers sit either
side of the heel and over the toe. Angular cowls cover the foot: a ridged
instep with two swept fins, a ridged toe cap that hooks down at the tip, and a
pointed heel spur.

## Cockpit

The cabin is sized in real meters for the pilot: 1.38 m of headroom and
1.86 m wide. The chair is a racing seat that leans back 30°. The hatch is on
the roof behind the chair, and the roof gun is in front of it.

## Legs that roll

The sprinter's legs have two more joints than the walker's (`JOINTS` in
`mech_sprinter.py`). The hip rolls the whole leg out (up to 28°) or in (up
to 12°) about the front-to-back axis, on a yoke (`hip_yoke`) that turns on
two roll bearings under the hip mount. The ankle rolls the foot back level.
The gait solves each leg in its tilted plane: a foot off to the side swings
the leg out to it. So the feet step sideways when it strafes, and they reach
where the steps put them when it turns or runs. The right leg's roll joints
are mirrored (`hip_roll_r` runs -28..12).

## Walk and kneel

The walk is the walker's algorithm with the sprinter's numbers (`GAIT` in
`mech_sprinter.py`): a deeper crouch, quicker and longer steps, more toe
push-off, faster turns. The ground under a foot is looked for down to 2.2 m,
deeper than the 2.1 m it climbs. A foot half over a two-block drop must still
find its own ground. `python3 tools/gait_check.py sprinter` passes every check.

The parked kneel (`KNEEL_POSE`) was solved from the part geometry: the right
foot flat on the ground ahead, the left knee guard 3 cm off the ground, and
the left foot behind on its toes. The body sinks 2.6 m. Going down and coming
up, the ankles arc 1.1 m (left) and 0.4 m (right) clear of the ground, so no
part goes through it on the way.

## Piloting

The sprinter is an agile type (`agile` in its gait):

- The body turns toward where the pilot looks. W/S run, and A/D strafe at up
  to 55% of top speed.
- The turret faces ahead with the body. The guns still turn on their own
  mounts toward the aim. While it kneels, the turret turns freely toward
  where the pilot looks. It only swings back to face ahead for getting out.
- Shift kneels or stands up. It does nothing while the mech is still going
  down or getting up, and a held Shift counts as one press.
- Space jumps at 11.5 m/s up (4.4 m), carrying the mech's speed plus a
  little more forward. Then it pressurizes again for 3 s (`jump_cooldown`),
  counted in the air too, with a hiss when it is ready. Space while it
  pressurizes only sputters. Damaged legs jump lower. A jump flies as a fall,
  carries on until something is in the way, and lands running.

## Getting in and out

The animations are in `mech/animations/sprinter/`. To get in, the pilot
dashes at the raised right foot and hops onto its toe cap and instep. Then
the pilot leaps and catches the knee guard, swings, and hauls up and across
onto the nose. From there the pilot climbs past the visor and over the brow
(between the roof gun and the camera pod), takes two strides back to the
hatch, and drops in. To get out, the pilot goes up through the hatch, runs to
the front edge, drops onto the nose and leaps clear to the ground.
