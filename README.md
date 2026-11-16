# tc-mechs

Walking mechs for DiamondFire, written in
[Terracotta](https://github.com/Owlfroggy/terracotta). They use the same build
style as the cars in tc-rally_game: every part is its own resource-pack model
on its own item display, so any part can move, take damage or break off.

There are three mech types:

- **Walker**: a heavy turret on two legs, with two heavy side guns and two light roof guns
  ([design](mech/README.md)).
- **Sprinter**: smaller, lighter and angular, on long legs with running feet, a wide stance and a
  long stride. It has two side cannons and one roof gun. Its pilot steers it by looking, strafes,
  kneels and jumps ([design](mech/sprinter/README.md)).
- **Spider**: a long, angular fuselage like a jet's cockpit on four long legs, with a rail cannon
  on its raised back, two machine guns under its belly and an air kit on its back. It is the
  fastest mech, climbs walls and jumps high ([part list](mech/spider/PARTS.md)).

## Layout

| Path | Contents |
| --- | --- |
| [mech/](mech/) | The walker's design: [README](mech/README.md), [part list](mech/PARTS.md), `parts.json` for the game code |
| [mech/sprinter/](mech/sprinter/) | The sprinter's design: [README](mech/sprinter/README.md), [part list](mech/sprinter/PARTS.md), `parts.json` |
| [mech/spider/](mech/spider/) | The spider's [part list](mech/spider/PARTS.md) and `parts.json` |
| [pack/](pack/) | Resource pack (Minecraft 26.3, format 97.1), namespace `mech` |
| [pack/src/mech_parts.py](pack/src/mech_parts.py) | The walker's leg design and the build for every type: mirrors the legs, adds the pelvis, writes models, textures and part data |
| [pack/src/mech_sprinter.py](pack/src/mech_sprinter.py) | The sprinter: its legs and running feet, angular armor, wedge turret, walk and kneel |
| [pack/src/mech_spider.py](pack/src/mech_spider.py) | The spider: its four legs, fuselage and lid, guns, air kit and gait numbers |
| [pack/src/mech_pelvis.py](pack/src/mech_pelvis.py) | The pelvis design |
| [pack/src/mech_torso.py](pack/src/mech_torso.py) | The turret torso and its guns |
| [pack/src/mech_lib.py](pack/src/mech_lib.py) | Shared code: materials, textures, cuboid helpers, model and item writers |
| [tools/viewer/](tools/viewer/) | 3D viewer: pose the joints, play a walk cycle, explode or break parts |
| [tools/animator/](tools/animator/) | Animation editor: pose the pilot on the kneeling mech key by key, play it, save drafts |
| [mech/animations/](mech/animations/) | The pilot's animations (getting in and getting out), baked into the game by `mech_pilot.py`; the sprinter's are in `sprinter/` |
| [tools/build_pack.py](tools/build_pack.py) | Validates, zips and publishes the pack to the `pack-dist` branch, and points `tc/pack.tc` at it |
| [tc/](tc/) | Terracotta code for the plot: spawning, drawing and posing mechs (`mech.tc`), the procedural walk (`gait.tc`) over blocks (`terrain.tc`), the spider's walk and climbing (`spider.tc`), piloting (`pilot.tc`), firing (`weapons.tc`), damage (`damage.tc`), commands, the pack; `mech_data.tc` is generated |
| [tools/gait_check.py](tools/gait_check.py) | The reference model of the procedural walk, with its checks (IK round trip, joint ranges at every speed and turn rate, test courses of steps, walls and drops); `python3 tools/gait_check.py sprinter` checks the sprinter |

## Build the mech

```bash
python3 pack/src/mech_parts.py
```

Needs Pillow. This builds every type. Then open the viewer (pick the type at
the top, or open `?type=sprinter`):

```bash
python3 -m http.server 8766 --directory tools/viewer
```

To rough out a pilot animation, run the editor and open
<http://127.0.0.1:8767/tools/animator/>:

```bash
python3 tools/animator/serve.py
```

## Put it on the plot

1. Build the pack. This also points `packUrl()` in `tc/pack.tc` at the new zip:

   ```bash
   python3 tools/build_pack.py
   ```

2. Publish the pack to the `pack-dist` branch. Players load it from its raw
   GitHub URL:

   ```bash
   python3 tools/build_pack.py --publish --push
   ```

3. Compile `tc/` and send it to the plot with the Terracotta VS Code extension
   (`.vscode/launch.json`, plot size 300).

In game (play mode). Joining sets your third-person camera 15 blocks back (the `camera_distance` attribute), so a whole mech fits in view.

| Command | What it does |
| --- | --- |
| `@mech [walker\|sprinter\|spider] [turn]` | Spawns a mech (a walker unless you name the type) 20 blocks in front of you, facing you (or turned by `turn` degrees). `@sprinter [turn]`, `@walker [turn]` and `@spider [turn]` do the same |
| `@walk [m/s] [deg/s]` | The nearest mech walks forward (3 m/s by default, up to 3.8; negative walks back) and turns (+ right) |
| `@turn [deg/s]` | The nearest mech turns on the spot (30°/s by default, up to 40; + right) |
| `@stop` | The nearest mech stops; its feet settle under it and it kneels (parked) |
| `@follow` | The nearest mech walks after you and aims its torso and guns at you; `@follow` again or `@stop` ends it |
| `@board` | Boards the nearest free mech within 30 blocks: you sprint to it while it kneels and opens its hatch, leap to its knee piston, scramble up onto the roof and drop in through the hatch, then it stands up. W/S walk, A/D turn, look to aim the turret and guns, hold right click for the cannons, left click for the machine guns, Q for the roof camera, F gets out. In a sprinter you climb its raised foot, catch its knee and go up over the nose instead. Its controls differ: see below |
| `@exit` | Gets out of the mech you pilot (same as F): it kneels, and you spring out of the hatch, sprint along the roof and jump down off its knee |
| `@pose JOINT DEGREES` | Moves a joint on the nearest mech: `hip_l`, `knee_l`, `ankle_l`, `hip_r`, `knee_r`, `ankle_r`, `waist`, `elev_hl`, `elev_hr`, `elev_ll`, `elev_lr` |
| `@pose reset` | Puts the nearest mech back in its rest pose |
| `@status` | The nearest mech's damage: integrity, walking and turret speed, every damaged part |
| `@damage PART AMOUNT` | Damages a part of the nearest mech (a test tool; `@damage all AMOUNT` for every part) |
| `@repair` | Puts the nearest mech back together |
| `@clearmechs` | Removes every mech |
| `@selftest` | Tests the walk where you stand: drives each type in `selfTestKinds()` (now the spider) straight ahead at full speed, then up the highest ground within 60 blocks, and reports each run in chat (distance, rise, top speed, stalls; for the spider also its time on walls and a jump) |
| `@pack` | Sends the resource pack again |

### Piloting the sprinter

| Key | What it does |
| --- | --- |
| W/S | Runs forward (up to 6.3 m/s) or back |
| A/D | Strafes left or right |
| Look | Steers: the body turns toward where you look, with the turret facing ahead, and the guns turn on their own mounts to aim |
| Shift | Kneels, or stands up again. While it kneels, the turret turns freely toward where you look |
| Space | Jumps 4.4 m up, carrying its speed. Then it pressurizes again for 3 seconds before the next jump (the action bar shows PRESSURIZING, then JUMP READY) |
| Right click (hold), left click, Q, F | Cannons, roof machine gun, roof camera, get out (as in the walker) |

### Piloting the spider

| Key | What it does |
| --- | --- |
| W/S | Runs forward (up to 12.6 m/s, twice the sprinter) or back |
| A/D | Strafes left or right |
| Look | Steers: the body turns toward where you look, and tilts its nose up to 15° toward your look, so the guns reach further. The guns turn on their own mounts to aim |
| Run at a wall | It climbs onto the wall, runs up it (at 70% speed), goes over the top, and climbs down cliffs the same way. On a wall, look where you want to go. The air kit grips: without it (or with a leg gone) it cannot climb, and it lets go of a wall |
| Space | Jumps about 8 m up off whatever it stands on (off a wall: away from it), carrying its speed. In the air it grabs a wall it flies into. Then it pressurizes again for 3 seconds |
| Shift | Crouches, or stands up again |
| Right click (hold), left click, Q, F | Rail cannon, belly machine guns, nose camera, get out (on the ground only) |

