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
| [tools/build_pack.py](tools/build_pack.py) | Validates, zips and publishes the pack to the `pack-dist` branch, and points `tc/pack.tc` at it |
| [tc/](tc/) | Terracotta code for the plot: spawning and posing mechs (`mech.tc`), commands, the pack; `mech_data.tc` is generated |

## Build the mech

```bash
python3 pack/src/mech_parts.py
```

Needs Pillow. Then open the viewer:

```bash
python3 -m http.server 8766 --directory tools/viewer
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

In game (play mode):

| Command | What it does |
| --- | --- |
| `@mech [turn]` | Spawns a mech 20 blocks in front of you, facing you (or turned by `turn` degrees) |
| `@pose JOINT DEGREES` | Moves a joint on the nearest mech: `hip_l`, `knee_l`, `ankle_l`, `hip_r`, `knee_r`, `ankle_r`, `waist`, `elev_hl`, `elev_hr`, `elev_ll`, `elev_lr` |
| `@pose reset` | Puts the nearest mech back in its rest pose |
| `@clearmechs` | Removes every mech |
| `@pack` | Sends the resource pack again |

