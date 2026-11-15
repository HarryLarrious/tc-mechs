# tc-mechs

Walking mechs for DiamondFire, written in
[Terracotta](https://github.com/Owlfroggy/terracotta). They use the same build
style as the cars in tc-rally_game: every part is its own resource-pack model
on its own item display, so any part can move, take damage or break off.

So far there is one leg for a two-legged mech.

## Layout

| Path | Contents |
| --- | --- |
| [mech/](mech/) | Mech design: [README](mech/README.md), [leg part list](mech/LEG_PARTS.md), `leg_parts.json` for the game code |
| [pack/](pack/) | Resource pack (Minecraft 26.3, format 97.1), namespace `mech` |
| [pack/src/mech_parts.py](pack/src/mech_parts.py) | The leg design: makes its models, textures and part data |
| [pack/src/mech_lib.py](pack/src/mech_lib.py) | Shared code: materials, textures, cuboid helpers, model and item writers |
| [tools/viewer/](tools/viewer/) | 3D viewer: pose the joints, play a walk cycle, explode or break parts |

## Build the leg

```bash
python3 pack/src/mech_parts.py
```

Needs Pillow. Then open the viewer:

```bash
python3 -m http.server 8766 --directory tools/viewer
```
