# tc-mechs

Walking mechs for DiamondFire, written in
[Terracotta](https://github.com/Owlfroggy/terracotta). They use the same build
style as the cars in tc-rally_game: every part is its own resource-pack model
on its own item display, so any part can move, take damage or break off.

The first mech walks on two legs and carries a turret torso with two heavy side guns and two light roof guns.

## Layout

| Path | Contents |
| --- | --- |
| [mech/](mech/) | Mech design: [README](mech/README.md), [part list](mech/PARTS.md), `parts.json` for the game code |
| [pack/](pack/) | Resource pack (Minecraft 26.3, format 97.1), namespace `mech` |
| [pack/src/mech_parts.py](pack/src/mech_parts.py) | The leg design and the build: mirrors the leg, adds the pelvis, writes models, textures and part data |
| [pack/src/mech_pelvis.py](pack/src/mech_pelvis.py) | The pelvis design |
| [pack/src/mech_torso.py](pack/src/mech_torso.py) | The turret torso and its guns |
| [pack/src/mech_lib.py](pack/src/mech_lib.py) | Shared code: materials, textures, cuboid helpers, model and item writers |
| [tools/viewer/](tools/viewer/) | 3D viewer: pose the joints, play a walk cycle, explode or break parts |
| [tools/animator/](tools/animator/) | Animation editor: pose the pilot on the kneeling mech key by key, play it, save drafts |
| [mech/animations/](mech/animations/) | The pilot's animations (getting in and getting out), baked into the game by `mech_pilot.py` |
| [tools/build_pack.py](tools/build_pack.py) | Validates, zips and publishes the pack to the `pack-dist` branch, and points `tc/pack.tc` at it |
| [tc/](tc/) | Terracotta code for the plot: spawning, drawing and posing mechs (`mech.tc`), the procedural walk (`gait.tc`) over blocks (`terrain.tc`), piloting (`pilot.tc`), firing (`weapons.tc`), damage (`damage.tc`), commands, the pack; `mech_data.tc` is generated |
| [tools/gait_check.py](tools/gait_check.py) | The reference model of the procedural walk, with its checks (IK round trip, joint ranges at every speed and turn rate, test courses of steps, walls and drops) |

## Build the mech

```bash
python3 pack/src/mech_parts.py
```

Needs Pillow. Then open the viewer:

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
| `@mech [turn]` | Spawns a mech 20 blocks in front of you, facing you (or turned by `turn` degrees) |
| `@walk [m/s] [deg/s]` | The nearest mech walks forward (3 m/s by default, up to 3.8; negative walks back) and turns (+ right) |
| `@turn [deg/s]` | The nearest mech turns on the spot (30°/s by default, up to 40; + right) |
| `@stop` | The nearest mech stops; its feet settle under it and it kneels (parked) |
| `@follow` | The nearest mech walks after you and aims its torso and guns at you; `@follow` again or `@stop` ends it |
| `@board` | Boards the nearest free mech within 30 blocks: you sprint to it while it kneels and opens its hatch, leap to its knee piston, scramble up onto the roof and drop in through the hatch, then it stands up. W/S walk, A/D turn, look to aim the turret and guns, hold right click for the cannons, left click for the machine guns, F gets out |
| `@exit` | Gets out of the mech you pilot (same as F): it kneels, and you spring out of the hatch, sprint along the roof and jump down off its knee |
| `@pose JOINT DEGREES` | Moves a joint on the nearest mech: `hip_l`, `knee_l`, `ankle_l`, `hip_r`, `knee_r`, `ankle_r`, `waist`, `elev_hl`, `elev_hr`, `elev_ll`, `elev_lr` |
| `@pose reset` | Puts the nearest mech back in its rest pose |
| `@status` | The nearest mech's damage: integrity, walking and turret speed, every damaged part |
| `@damage PART AMOUNT` | Damages a part of the nearest mech (a test tool; `@damage all AMOUNT` for every part) |
| `@repair` | Puts the nearest mech back together |
| `@clearmechs` | Removes every mech |
| `@pack` | Sends the resource pack again |

