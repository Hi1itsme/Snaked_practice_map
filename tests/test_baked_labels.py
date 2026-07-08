"""Headless test of baked-label guide meshes (optimization #2).

Run:  blender.exe -b --factory-startup --python test_baked_labels.py
"""
import sys
import time
import shutil
import tempfile

import os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import bpy  # noqa: E402
import puzzle_piece_workshop as ws  # noqa: E402

TMP = tempfile.mkdtemp(prefix="snaked_labels_test_")
FAILURES = []


def check(name, cond, detail=""):
    status = "ok" if cond else "FAIL"
    print("[TEST] %-58s %s %s" % (name, status, detail))
    if not cond:
        FAILURES.append(name)


def objs(coll_name):
    coll = bpy.data.collections.get(coll_name)
    return list(coll.objects) if coll else []


# ---------------------------------------------------------------------------
# 1. The blank workshop: 4 merged guide meshes, no font objects at all.
t0 = time.perf_counter()
ws.build_blender_workshop()
t_build = time.perf_counter() - t0

guides = objs(ws.COLLECTION_NAME)
check("workshop holds exactly 4 guide objects", len(guides) == 4,
      "n=%d" % len(guides))
check("no FONT objects remain in the workshop",
      all(o.type == 'MESH' for o in guides))
check("no temp label objects leaked",
      not any(o.name.startswith("WS_TmpLabel") for o in bpy.data.objects))

zones = bpy.data.objects.get("WS_Guide_WorkbenchZones")
label_slots = [m for m in zones.data.materials
               if m.name.startswith("Workshop_Label_")]
check("zone guide mesh contains baked label geometry",
      len(label_slots) >= 4 and len(zones.data.vertices) > 500,
      "%d label mats, %d verts" % (len(label_slots), len(zones.data.vertices)))
check("labels keep distinct accent colours",
      len({tuple(round(c, 3) for c in m.diffuse_color[:3])
           for m in label_slots}) == len(label_slots))

# Some label faces sit at the signage height (z = 0.05).
zs = {round(v.co.z, 3) for v in zones.data.vertices}
check("label faces sit just above the floor", 0.05 in zs, sorted(zs))

# Rebuild is idempotent: still 4 objects, and the label cache kicks in.
t0 = time.perf_counter()
ws.build_blender_workshop()
t_rebuild = time.perf_counter() - t0
check("rebuild stays at 4 guide objects",
      len(objs(ws.COLLECTION_NAME)) == 4)
print("[TEST] build %.2fs, cached rebuild %.2fs" % (t_build, t_rebuild))

# ---------------------------------------------------------------------------
# 2. Orientations: labels merge into the per-shape guide; banner is the only
#    font object left anywhere.
x0, y0, _, _ = ws._ramp_puzzle_bounds(ws.RAMP_PUZZLES.index("Cube"))
ws.place_workshop_component("BLOCK", x0 + 2, y0 + 2, 0)
ws.place_workshop_component("RAMP", x0 + 2, y0 + 3, 0, rotation=90)

comps = ws._capture_ramp_puzzle(ws.RAMP_PUZZLES.index("Cube"))
n = ws.generate_ramp_puzzle_orientations("Cube", comps, TMP)
check("generated Cube's 4 orientations", n == 4)

orient_objs = objs(ws.WORKSHOP_ORIENTATIONS_COLLECTION)
fonts = [o for o in orient_objs if o.type == 'FONT']
check("banner is the only font object in orientations",
      len(fonts) == 1 and fonts[0].name == "OrientLabel_RAMP_ORIENTATIONS")
guide = next((o for o in orient_objs
              if o.name.startswith("WS_OrientGuide_Cube")), None)
check("orientation row guide exists with baked labels",
      guide is not None
      and any(m.name.startswith("Workshop_Label_")
              for m in guide.data.materials))

# Regenerating the same shape rebuilds its row without duplicates.
before = len(objs(ws.WORKSHOP_ORIENTATIONS_COLLECTION))
ws.generate_ramp_puzzle_orientations("Cube", comps, TMP)
check("regenerating a shape does not duplicate objects",
      len(objs(ws.WORKSHOP_ORIENTATIONS_COLLECTION)) == before)

# ---------------------------------------------------------------------------
shutil.rmtree(TMP, ignore_errors=True)
if FAILURES:
    print("[TEST] FAILED: %s" % ", ".join(FAILURES))
    sys.exit(1)
print("[TEST] all checks passed")
