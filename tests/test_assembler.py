"""Headless end-to-end test of the level assembler.

Run:  blender.exe -b --factory-startup --python test_assembler.py
Workshop: author a cell -> save_cell_as_piece -> JSON.
Main grid: place_piece (rotated) -> save_level -> clear -> load_level ->
re-serialize and compare. All JSON goes to a temp root.
"""
import os
import sys
import json
import shutil
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import bpy  # noqa: E402
import puzzle_piece_workshop as ws  # noqa: E402
import snaked_map_builder as mb  # noqa: E402
import snaked_tools as st  # noqa: E402

TMP = tempfile.mkdtemp(prefix="snaked_assembler_test_")
FAILURES = []


def check(name, cond, detail=""):
    status = "ok" if cond else "FAIL"
    print("[TEST] %-58s %s %s" % (name, status, detail))
    if not cond:
        FAILURES.append(name)


def grid_comps():
    coll = bpy.data.collections.get(st.COMPONENTS_COLLECTION)
    if coll is None:
        return []
    return [o for o in coll.objects if "snaked_component" in o]


def comp_at(x, y, layer, kind):
    for o in grid_comps():
        if (o.get("snaked_x") == x and o.get("snaked_y") == y
                and o.get("snaked_z") == layer
                and o.get("snaked_component") == kind):
            return o
    return None


# ---------------------------------------------------------------------------
# 1. Workshop: author one ramps+walls cell and one workbench zone, save both.
ws.build_blender_workshop()

rw_x0, rw_y0, _, _ = ws._ramp_wall_bounds(0)   # "Cube a"
ws.place_workshop_component("BLOCK", rw_x0, rw_y0, 0)
ws.place_workshop_component("BUTTON", rw_x0, rw_y0, 0, name_id="B1")
ws.place_workshop_component("RAMP", rw_x0 + 1, rw_y0, 0, rotation=0)
ws.place_workshop_component("WALL", rw_x0, rw_y0 + 1, 0)

pid1, n1 = ws.save_cell_as_piece("RAMPWALL", rw_i=0, root=TMP)
check("saved ramps+walls cell as piece", pid1 == "rw_cube_a_base" and n1 == 4,
      "%s n=%s" % (pid1, n1))
fam_dir = os.path.join(TMP, "snaked_assets", "puzzle_pieces", "rw_cube_a")
check("family.json + piece_base.json written",
      os.path.exists(os.path.join(fam_dir, "family.json"))
      and os.path.exists(os.path.join(fam_dir, "piece_base.json")))

zx0, zy0, _, _ = ws._zone_bounds(0)
ws.place_workshop_component("FLOOR", zx0, zy0, 0)
ws.place_workshop_component("FLOOR", zx0 + 1, zy0, 0)
pid2, n2 = ws.save_cell_as_piece("WORKBENCH", zone_i=0,
                                 custom_id="Test Floor Strip", root=TMP)
check("saved workbench cell with custom id",
      pid2 == "test_floor_strip_base" and n2 == 2, "%s n=%s" % (pid2, n2))

with open(os.path.join(TMP, "ai_data", "all_puzzle_pieces.json"),
          encoding="utf-8") as fh:
    idx = json.load(fh)
check("piece index lists both pieces",
      {p["id"] for p in idx["pieces"]} == {pid1, pid2})

# Empty cell refuses to save.
pid3, n3 = ws.save_cell_as_piece("RAMPWALL", rw_i=1, root=TMP)
check("empty cell returns (None, 0)", pid3 is None and n3 == 0)

# ---------------------------------------------------------------------------
# 2. Main grid: build it, load the catalog, stamp the piece rotated 90.
mb.rebuild()
catalog = st.load_piece_catalog(root=TMP)
check("assembler catalog sees both pieces", set(catalog) == {pid1, pid2})

placed, err = st.place_piece(catalog[pid1], 5, 5, layer=0, rotation=90)
check("piece placed rotated 90", placed == 4 and err is None,
      "placed=%s err=%s" % (placed, err))

# Authored rel coords: block(0,0)+button(0,0), ramp(1,0) r0, wall(0,1).
# Rotate 90 CCW + re-pack: wall(0,0), block(1,0), button(1,0), ramp(1,1) r90.
check("wall landed at (5, 5)", comp_at(5, 5, 0, "WALL") is not None)
check("block landed at (6, 5)", comp_at(6, 5, 0, "BLOCK") is not None)
ramp = comp_at(6, 6, 0, "RAMP")
check("ramp landed at (6, 6) with facing 90",
      ramp is not None and ramp.get("snaked_rot") == 90)
btn = comp_at(6, 5, 0, "BUTTON")
check("button rode its block (top-face z)",
      btn is not None and abs(btn.location.z - 0.575) < 1e-6,
      "z=%s" % (btn and btn.location.z))
check("components carry the piece tag",
      all(o.get("snaked_piece") == pid1 for o in grid_comps()))

# All-or-nothing bounds check: at (22, 40) the piece pokes past the grid.
before = len(grid_comps())
placed, err = st.place_piece(catalog[pid1], 22, 40)
check("out-of-bounds placement rejected", placed == 0 and err is not None,
      err)
check("rejected placement placed nothing", len(grid_comps()) == before)

# Floor piece: thin mesh (the master bakes 0.1 thinness into the mesh).
placed, err = st.place_piece(catalog[pid2], 1, 1)
check("floor piece placed", placed == 2 and err is None)
fl = comp_at(1, 1, 0, "FLOOR")
zs = [v.co.z for v in fl.data.vertices]
check("placed floor shares a genuinely thin mesh",
      abs((max(zs) - min(zs)) - 0.1) < 1e-6, "dz=%.3f" % (max(zs) - min(zs)))

# ---------------------------------------------------------------------------
# 3. Level round trip: save -> clear -> load -> compare serializations.
path, n = st.save_level(1, 2, name="Round Trip", root=TMP)
check("save_level wrote 6 components", n == 6 and os.path.exists(path))

with open(path, encoding="utf-8") as fh:
    saved = json.load(fh)
check("level.json identity + grid size",
      saved["id"] == "world_01_level_002"
      and saved["grid_size"] == [22, 40, 4])
check("pieces_used tracked", set(saved["pieces_used"]) == {pid1, pid2})

with open(os.path.join(TMP, "ai_data", "all_levels.json"),
          encoding="utf-8") as fh:
    lidx = json.load(fh)
check("level registered in all_levels.json",
      [e["id"] for e in lidx["levels"]] == ["world_01_level_002"])

removed = st.clear_components()
check("clear_components emptied the grid",
      removed == 6 and len(grid_comps()) == 0)

placed, err = st.load_level(1, 2, root=TMP)
check("load_level rebuilt the grid", placed == 6 and err is None,
      "placed=%s err=%s" % (placed, err))
btn = comp_at(6, 5, 0, "BUTTON")
check("loaded button back on its block top",
      btn is not None and abs(btn.location.z - 0.575) < 1e-6)

comps2, pieces2 = st._serialize_components()
check("re-serialization is lossless",
      comps2 == saved["components"] and pieces2 == saved["pieces_used"])

# Re-saving does not duplicate the index entry, and keeps the name.
st.save_level(1, 2, root=TMP)
with open(os.path.join(TMP, "ai_data", "all_levels.json"),
          encoding="utf-8") as fh:
    lidx = json.load(fh)
check("re-save keeps one index entry + name",
      len(lidx["levels"]) == 1 and lidx["levels"][0]["name"] == "Round Trip")

# Loading a level that doesn't exist reports an error.
placed, err = st.load_level(3, 9, root=TMP)
check("missing level load fails cleanly", placed == 0 and err is not None)

# ---------------------------------------------------------------------------
shutil.rmtree(TMP, ignore_errors=True)
if FAILURES:
    print("[TEST] FAILED: %s" % ", ".join(FAILURES))
    sys.exit(1)
print("[TEST] all checks passed")
