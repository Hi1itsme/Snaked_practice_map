"""Headless test of instanced fills (collection instancing, optimization #1).

Run:  blender.exe -b --factory-startup --python test_instanced_fills.py
"""
import os
import sys
import shutil
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import bpy  # noqa: E402
import puzzle_piece_workshop as ws  # noqa: E402

TMP = tempfile.mkdtemp(prefix="snaked_instfill_test_")
FAILURES = []


def check(name, cond, detail=""):
    status = "ok" if cond else "FAIL"
    print("[TEST] %-58s %s %s" % (name, status, detail))
    if not cond:
        FAILURES.append(name)


def comps_coll():
    return bpy.data.collections.get(ws.WORKSHOP_COMPONENTS_COLLECTION)


def loose_comps():
    return [o for o in comps_coll().objects if "snaked_component" in o]


def instance_empties():
    return [o for o in comps_coll().objects if "snaked_instance" in o]


def loose_in(x0, y0, x1, y1):
    return [o for o in loose_comps()
            if x0 <= o.get("snaked_x", -9) <= x1
            and y0 <= o.get("snaked_y", -9) <= y1]


def empties_in(x0, y0, x1, y1):
    return [o for o in instance_empties()
            if x0 <= o.get("snaked_x", -9) <= x1
            and y0 <= o.get("snaked_y", -9) <= y1]


# ---------------------------------------------------------------------------
# 1. Author two ramp puzzles (same layouts as the earlier tests).
ws.build_blender_workshop()


def author(shape, layout):
    x0, y0, _, _ = ws._ramp_puzzle_bounds(ws.RAMP_PUZZLES.index(shape))
    for kind, dx, dy, layer, rot, nid in layout:
        ws.place_workshop_component(kind, x0 + dx, y0 + dy, layer,
                                    rotation=rot, name_id=nid)


author("Cube", [
    ("BLOCK", 2, 2, 0, 0, ""), ("BLOCK", 3, 2, 0, 0, ""),
    ("BLOCK", 3, 2, 1, 0, ""),
    ("RAMP", 2, 3, 0, 90, ""), ("RAMP", 4, 2, 0, 270, ""),
    ("BUTTON", 5, 5, 0, 0, "C"),
])
author("L", [
    ("BLOCK", 1, 1, 0, 0, ""), ("BLOCK", 1, 2, 0, 0, ""),
    ("RAMP", 2, 1, 0, 0, ""),
])
authored_loose = len(loose_comps())   # 9

# ---------------------------------------------------------------------------
# 2. Instanced ramps+walls fill: one empty per cell, protos hold the geometry.
filled, skipped = ws.fill_ramp_wall_cells_from_ramps(instanced=True)
check("filled 27 cells instanced", filled == 27, "filled=%d" % filled)
check("one instance empty per filled cell", len(instance_empties()) == 27)
check("no loose components were added",
      len(loose_comps()) == authored_loose)

proto_cube = bpy.data.collections.get("WS_PieceProto_rw_src_cube")
proto_l = bpy.data.collections.get("WS_PieceProto_rw_src_l")
check("protos hold the piece geometry (5 + 3, buttons excluded)",
      proto_cube is not None and len(proto_cube.objects) == 5
      and proto_l is not None and len(proto_l.objects) == 3)
check("proto collections stay out of the scene",
      proto_cube.name not in bpy.context.scene.collection.children)

loose_would_be = 23 * 5 + 4 * 3
inst_actual = 27 + 5 + 3
print("[TEST] ramps+walls fill objects: %d loose -> %d instanced"
      % (loose_would_be, inst_actual))

# ---------------------------------------------------------------------------
# 3. Capture reads through the instance; loose additions combine with it.
ca_x0, ca_y0, ca_x1, ca_y1 = ws._ramp_wall_bounds(0)   # "Cube a"
cap = ws._capture_cell_components(ca_x0, ca_y0, ca_x1, ca_y1)
check("capture sees the instanced piece", len(cap) == 5,
      "n=%d" % len(cap))
check("captured kinds match the source",
      sorted(c["kind"] for c in cap) == ["BLOCK", "BLOCK", "BLOCK",
                                         "RAMP", "RAMP"])
ws.place_workshop_component("WALL", ca_x1, ca_y1, 0)   # user adds a wall
cap = ws._capture_cell_components(ca_x0, ca_y0, ca_x1, ca_y1)
check("capture combines instance + loose wall", len(cap) == 6)

# A button dropped on an INSTANCED block must still ride its top face.
cb_x0, cb_y0, _, _ = ws._ramp_wall_bounds(1)   # "Cube b"
btn = ws.place_workshop_component("BUTTON", cb_x0 + 3, cb_y0 + 3, 0,
                                  name_id="T")
check("button on instanced block sits on tile top",
      abs(btn.location.z - 0.575) < 1e-6, "z=%.3f" % btn.location.z)
ws.erase_workshop_component(cb_x0 + 3, cb_y0 + 3, 0)   # tidy up again

# Erase cannot eat part of an instance (explode first) -- documented.
removed = ws.erase_workshop_component(ca_x0 + 3, ca_y0 + 3, 0)
check("erase leaves instanced contents alone", removed == 0
      and len(empties_in(ca_x0, ca_y0, ca_x1, ca_y1)) == 1)

# ---------------------------------------------------------------------------
# 4. Instanced button-cell import (captures through the rw instances).
before_empties = len(instance_empties())
bfilled, bempty = ws.fill_ramp_wall_button_cells_from_ramp_walls(
    instanced=True)
check("imported 108 button cells instanced", bfilled == 108,
      "filled=%d" % bfilled)
check("one empty per button cell",
      len(instance_empties()) - before_empties == 108)
proto_ca = bpy.data.collections.get("WS_PieceProto_rwb_src_cube_a")
check("button-cell proto includes the added wall",
      proto_ca is not None and len(proto_ca.objects) == 6)

# ---------------------------------------------------------------------------
# 5. Make Cell Editable: explode "Cube a" (ramps+walls) back to loose comps.
exploded, placed = ws.make_cell_editable("RAMPWALL", rw_i=0)
check("explode replaced 1 instance with 5 components",
      exploded == 1 and placed == 5, "(%d, %d)" % (exploded, placed))
check("cell is loose again (5 + the wall)",
      len(loose_in(ca_x0, ca_y0, ca_x1, ca_y1)) == 6
      and len(empties_in(ca_x0, ca_y0, ca_x1, ca_y1)) == 0)
check("exploded block landed on its fill anchor",
      any(o.get("snaked_component") == "BLOCK"
          and o.get("snaked_x") == ca_x0 + 3 and o.get("snaked_y") == ca_y0 + 3
          for o in loose_in(ca_x0, ca_y0, ca_x1, ca_y1)))
check("explode on a cell with no instance is a no-op",
      ws.make_cell_editable("RAMPWALL", rw_i=0) == (0, 0))

# ---------------------------------------------------------------------------
# 6. Re-filling overwrites the exploded seed but keeps the user's wall.
ws.fill_ramp_wall_cells_from_ramps(instanced=True)
check("re-fill re-instanced the exploded cell",
      len(empties_in(ca_x0, ca_y0, ca_x1, ca_y1)) == 1)
in_cell = loose_in(ca_x0, ca_y0, ca_x1, ca_y1)
check("re-fill erased the seed, kept the user's wall",
      len(in_cell) == 1
      and in_cell[0].get("snaked_component") == "WALL")
cap = ws._capture_cell_components(ca_x0, ca_y0, ca_x1, ca_y1)
check("capture after re-fill still sees 6 components", len(cap) == 6)

# ---------------------------------------------------------------------------
# 7. Rebuild survival + piece save from an instanced cell.
n_empties = len(instance_empties())
ws.build_blender_workshop()   # re-run: guides rebuilt, components kept
check("instances survive a workshop rebuild",
      len(instance_empties()) == n_empties)

pid, n = ws.save_cell_as_piece("RAMPWALLBUTTON", rwb_i=0, root=TMP)
check("save piece from an instanced button cell",
      pid == "rwb_cube_a_1_base" and n == 6, "%s n=%s" % (pid, n))

total = len(comps_coll().objects)
print("[TEST] components collection now holds %d objects "
      "(9 authored + 1 wall + %d instance empties)" % (total, n_empties))

# ---------------------------------------------------------------------------
shutil.rmtree(TMP, ignore_errors=True)
if FAILURES:
    print("[TEST] FAILED: %s" % ", ".join(FAILURES))
    sys.exit(1)
print("[TEST] all checks passed")
