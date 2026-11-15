"""The mech's pelvis: the root of the lower body, between the two hip mounts.

Built in the mech frame (+X left, +Y up, +Z forward, origin on the ground
midway between the hips). The hips sit at x = +/-HIP_X, y = HIP_Y. Each leg's
hip mount bolts up under one end of the pelvis crossbeam (its flange top is at
y = 3.50, x = +/-(HIP_X - 0.30 .. HIP_X + 0.30), z = -0.30 .. 0.30).

Parts (all on the "pelvis" segment, which is the mech body itself):

  pelvis        crossbeam over both hip flanges, a keel between the legs
  waist_ring    slewing ring and drive motor on top, for the torso to turn on
  pelvis_armor  front plates (a V-shaped codpiece) and top plates over the flanges
  power_pack    battery pack behind the keel, with cables to both hip motors
  compressor    air compressor under the power pack, feeding both legs' air tanks
  rear_armor    the cover over the power pack
"""

from __future__ import annotations

import math

from mech_lib import Elem, Part, beam, box, no_dent, plate, prism, to_local

PIVOT = (0.0, 3.60, 0.0)


def _rx(p, deg):
    a = math.radians(deg)
    return (p[0], p[1] * math.cos(a) - p[2] * math.sin(a), p[1] * math.sin(a) + p[2] * math.cos(a))


def on_plate(center, rot_x, local):
    """A point given in the frame of a plate turned rot_x degrees about X."""
    r = _rx(local, rot_x)
    return tuple(c + d for c, d in zip(center, r))


def pelvis_parts(hip_x: float) -> list[Part]:
    out: list[Part] = []

    def part(p: Part, elems: list[Elem]):
        p.pivot = PIVOT
        p.elems = to_local(elems, PIVOT)
        out.append(p)

    X0, X1 = hip_x - 0.30, hip_x + 0.30   # each hip flange's span in x (outboard side positive)

    # ------------------------------------------------------------ frame
    e = [box((-X1, 3.52, -0.26), (X1, 3.70, 0.26), "gunmetal", dent=False)]          # crossbeam
    for z, r in ((0.26, 45.0), (-0.26, -45.0)):
        e.append(plate((0.0, 3.70, z), (2 * X1, 0.06, 0.06), "darksteel", (r, 0.0, 0.0), dent=False))  # top edges
    for s in (1, -1):
        x0, x1 = sorted((s * (X0 - 0.02), s * (X1 + 0.02)))
        e.append(box((x0, 3.50, -0.30), (x1, 3.54, 0.30), "steel", dent=False))      # flange adapter
        x0, x1 = sorted((s * X1, s * (X1 + 0.05)))
        e.append(box((x0, 3.50, -0.28), (x1, 3.72, 0.28), "steel", dent=False))      # end cap
        for z in (-0.18, 0.0, 0.18):
            e += prism((s * (X1 + 0.06), 3.61, z), "x", 0.025, 0.02, 6, "darksteel", dent=False)  # end bolts
    e.append(box((-0.28, 3.05, -0.24), (0.28, 3.52, 0.24), "gunmetal", dent=False))   # keel
    e.append(box((-0.22, 2.98, -0.18), (0.22, 3.05, 0.18), "darksteel", dent=False))  # keel foot
    for s in (1, -1):
        x0, x1 = sorted((s * 0.28, s * 0.30))
        e.append(box((x0, 3.12, -0.16), (x1, 3.44, 0.16), "vent", dent=False))       # keel side vents
    part(Part("pelvis", "Pelvis frame (crossbeam and keel)", "structure", None, "pelvis", PIVOT,
              420, 500, "fail", "Cracks: both hips sag and lose torque; at 0 the mech collapses",
              shield=["pelvis_armor"], damaged=False), e)

    # ------------------------------------------------------------ waist ring
    c = (0.0, 3.70, 0.0)
    e = prism((0.0, 3.74, 0.0), "y", 0.50, 0.08, 16, "darksteel")                    # base race
    e += prism((0.0, 3.81, 0.0), "y", 0.455, 0.06, 16, "steel")                      # gear ring
    for k in range(24):                                                               # gear teeth
        a = 2 * math.pi * k / 24
        e.append(plate((0.47 * math.sin(a), 3.81, 0.47 * math.cos(a)), (0.035, 0.05, 0.04), "darksteel",
                       (0.0, round(math.degrees(a), 3), 0.0)))
    e += prism((0.0, 3.865, 0.0), "y", 0.42, 0.05, 16, "gunmetal")                  # turntable
    for k in range(8):                                                                # turntable bolts
        a = 2 * math.pi * (k + 0.5) / 8
        e += prism((0.34 * math.sin(a), 3.90, 0.34 * math.cos(a)), "y", 0.025, 0.02, 6, "steel")
    e += prism((0.0, 3.90, 0.0), "y", 0.14, 0.02, 12, "hazard")                      # center hatch
    for k in range(4):                                                                # status lights on the race
        a = 2 * math.pi * (k + 0.5) / 4
        e.append(plate((0.505 * math.sin(a), 3.74, 0.505 * math.cos(a)), (0.05, 0.03, 0.008), "glow",
                       (0.0, round(math.degrees(a), 3), 0.0)))
    m = (0.0, 3.86, -0.60)                                                            # drive motor (vertical)
    e += prism((m[0], 3.745, m[2]), "y", 0.10, 0.03, 12, "darksteel")
    e += prism((m[0], 3.86, m[2]), "y", 0.11, 0.20, 12, "motor")
    for y in (3.79, 3.86, 3.93):
        e += prism((m[0], y, m[2]), "y", 0.125, 0.014, 12, "darksteel")
    e += prism((m[0], 3.97, m[2]), "y", 0.10, 0.03, 12, "hazard")
    e += prism((m[0], 3.995, m[2]), "y", 0.05, 0.02, 8, "steel")
    e.append(box((-0.02, 3.985, m[2] + 0.06), (0.02, 3.995, m[2] + 0.09), "glow"))
    e.append(box((-0.06, 3.77, -0.50), (0.06, 3.85, -0.44), "darksteel"))            # pinion housing
    no_dent(e)
    part(Part("waist_ring", "Waist slewing ring and drive motor", "actuator", "pelvis", "pelvis", PIVOT,
              140, 220, "fail", "Jams with damage: the torso turns slower; at 0 it locks facing where it was",
              shield=["rear_armor"], damaged=False), e)

    # ------------------------------------------------------------ front and top armor
    up_c, up_r = (0.0, 3.40, 0.40), -15.0
    lo_c, lo_r = (0.0, 3.07, 0.36), 10.0
    e = [plate(up_c, (0.86, 0.46, 0.06), "armor", (up_r, 0.0, 0.0)),                # upper front plate
         plate(lo_c, (0.52, 0.34, 0.06), "armor", (lo_r, 0.0, 0.0))]                # codpiece
    for s in (1, -1):                                                                 # accent chevron
        p0 = on_plate(up_c, up_r, (s * 0.02, 0.10, 0.035))
        p1 = on_plate(up_c, up_r, (s * 0.34, 0.20, 0.035))
        e.append(beam(p0, p1, 0.012, 0.06, "accent"))
    e.append(plate(on_plate(up_c, up_r, (0.0, -0.10, 0.032)), (0.22, 0.08, 0.01), "hazard", (up_r, 0.0, 0.0)))
    for s in (1, -1):
        for y in (0.18, -0.18):
            e += [plate(on_plate(up_c, up_r, (s * 0.38, y, 0.035)), (0.035, 0.035, 0.012), "steel",
                        (up_r, 0.0, 0.0))]                                            # bolts
        cx = s * hip_x
        e.append(plate((cx, 3.745, 0.0), (0.62, 0.05, 0.60), "armor", (0.0, 0.0, -s * 7.0)))   # top plates
        e.append(plate((cx, 3.772, 0.0), (0.62, 0.012, 0.08), "accent", (0.0, 0.0, -s * 7.0)))  # stripe
    part(Part("pelvis_armor", "Pelvis armor (front plates, flange covers)", "armor", "pelvis", "pelvis", PIVOT,
              90, 260, "detach", "Torn off: the pelvis frame and keel take hits directly"), e)

    # ------------------------------------------------------------ power pack
    e = [box((-0.36, 3.20, -0.74), (0.36, 3.72, -0.28), "gunmetal")]                 # battery case
    e.append(box((-0.30, 3.28, -0.745), (0.30, 3.52, -0.74), "vent", faces=("north",)))  # rear vents
    e.append(box((-0.32, 3.56, -0.752), (0.32, 3.585, -0.74), "glow", dent=False))    # charge bar
    for s in (1, -1):
        for z in (-0.36, -0.46, -0.56, -0.66):
            x0, x1 = sorted((s * 0.36, s * 0.40))
            e.append(box((x0, 3.24, z - 0.015), (x1, 3.68, z + 0.015), "darksteel"))  # cooling fins
        # power cable to the hip motor's junction box
        hx = hip_x + 0.39
        pts = [(s * 0.40, 3.25, -0.36), (s * (hx - 0.03), 3.25, -0.36), (s * hx, 3.29, -0.24),
               (s * hx, 3.33, -0.12)]
        e += [beam(pts[i], pts[i + 1], 0.045, 0.045, "hose") for i in range(len(pts) - 1)]
        e.append(box(tuple(v - 0.035 for v in pts[0]), tuple(v + 0.035 for v in pts[0]), "brass"))  # plug
    part(Part("power_pack", "Power pack (battery and cables)", "power", "pelvis", "pelvis", PIVOT,
              260, 180, "fail", "Loses charge with HP: every motor weakens; at 0 only the air pistons move the legs",
              shield=["rear_armor"]), e)

    # ------------------------------------------------------------ compressor
    e = [box((-0.20, 3.10, -0.36), (0.20, 3.20, -0.24), "darksteel")]                # bracket to the keel
    e += prism((-0.10, 3.06, -0.47), "x", 0.11, 0.30, 12, "motor")                   # motor
    for x in (-0.20, -0.12, -0.04):
        e += prism((x, 3.06, -0.47), "x", 0.125, 0.014, 12, "darksteel")
    e += prism((-0.265, 3.06, -0.47), "x", 0.09, 0.03, 12, "hazard")
    e.append(box((0.05, 2.95, -0.60), (0.26, 3.18, -0.35), "aluminum"))              # pump head
    for y in (2.99, 3.04, 3.09, 3.14):
        e.append(box((0.04, y, -0.62), (0.27, y + 0.015, -0.33), "darksteel"))        # head fins
    e.append(box((-0.07, 3.17, -0.52), (0.07, 3.20, -0.40), "brass"))                 # manifold
    e.append(box((0.27, 3.05, -0.50), (0.29, 3.09, -0.44), "glow"))                   # running light
    for s in (1, -1):                                                                  # hoses up to the tanks
        pts = [(s * 0.05, 3.19, -0.46), (s * 0.30, 3.17, -0.46), (s * 0.48, 3.30, -0.46),
               (s * (hip_x - 0.27), 3.48, -0.42)]
        e += [beam(pts[i], pts[i + 1], 0.035, 0.035, "hose") for i in range(len(pts) - 1)]
    no_dent(e)
    part(Part("compressor", "Air compressor (feeds both leg tanks)", "air", "power_pack", "pelvis", PIVOT,
              45, 90, "fail", "Stops pumping: the leg tanks run down as the pistons work",
              shield=["power_pack"], damaged=False), e)

    # ------------------------------------------------------------ rear armor
    rc, rr = (0.0, 3.68, -0.80), 25.0
    e = [plate(rc, (0.90, 0.20, 0.05), "armor", (rr, 0.0, 0.0)),                    # rear cowl
         plate(on_plate(rc, rr, (0.0, 0.0, -0.03)), (0.10, 0.18, 0.012), "accent", (rr, 0.0, 0.0))]
    for s in (1, -1):
        x0, x1 = sorted((s * 0.40, s * 0.43))
        e.append(box((x0, 3.30, -0.76), (x1, 3.72, -0.30), "armor"))                  # side plates
        x0, x1 = sorted((s * 0.395, s * 0.435))
        e.append(box((x0, 3.30, -0.76), (x1, 3.33, -0.30), "accent"))                 # side trim
    part(Part("rear_armor", "Rear armor (power pack cover)", "armor", "pelvis", "pelvis", PIVOT,
              45, 180, "detach", "Torn off: the power pack and waist motor take hits directly"), e)
    return out
