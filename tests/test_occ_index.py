"""Headless smoke test for the _ComponentIndex occupancy optimization.

Run:  blender.exe -b --factory-startup --python test_occ_index.py
Verifies placement/erase semantics are unchanged and the bulk fills work
off a shared index, then benchmarks per-placement cost with/without it.
"""
import sys
import time

import os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import bpy  # noqa: E402
import puzzle_piece_workshop as ws  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    status = "ok" if cond else "FAIL"
    print("[TEST] %-58s %s %s" % (name, status, detail))
    if not cond:
        FAILURES.append(name)


def comps_coll():
    return bpy.data.collections.get(ws.WORKSHOP_COMPONENTS_COLLECTION)


def comps_at(x, y, layer):
    coll = comps_coll()
    if coll is None:
        return []
    return [o for o in coll.objects
            if o.get("snaked_x") == x and o.get("snaked_y") == y
            and o.get("snaked_z") == layer]


# ---------------------------------------------------------------------------
# Build the blank workshop (no file scaffold, no panel needed).
ws.build_blender_workshop()

# ---------------------------------------------------------------------------
# 1. Single-placement semantics, no occ passed (old call signature).
zx0, zy0, _, _ = ws._zone_bounds(0)

b = ws.place_workshop_component("BLOCK", zx0, zy0, 0)
check("block placed at zone origin", len(comps_at(zx0, zy0, 0)) == 1)
check("block z centred on layer", abs(b.location.z - 0.0) < 1e-6)

btn = ws.place_workshop_component("BUTTON", zx0, zy0, 0, name_id="A")
expect_top = ws.WS_BUTTON_HEIGHT / 2.0 + ws.WS_TILE_TOP
check("button on solid sits on tile top",
      abs(btn.location.z - expect_top) < 1e-6, "z=%.3f" % btn.location.z)
check("button kept the block underneath", len(comps_at(zx0, zy0, 0)) == 2)

w = ws.place_workshop_component("WALL", zx0, zy0, 0)
cell = comps_at(zx0, zy0, 0)
kinds = sorted(o["snaked_component"] for o in cell)
check("wall replaced block, kept button", kinds == ["BUTTON", "WALL"], kinds)

# Button placed on an EMPTY cell sits flush, then lifts when a solid arrives.
btn2 = ws.place_workshop_component("BUTTON", zx0 + 1, zy0, 0, name_id="B")
check("button on empty cell sits flush",
      abs(btn2.location.z - ws.WS_BUTTON_HEIGHT / 2.0) < 1e-6)
ws.place_workshop_component("BLOCK", zx0 + 1, zy0, 0)
check("existing button lifted onto new solid",
      abs(btn2.location.z - expect_top) < 1e-6, "z=%.3f" % btn2.location.z)

n = ws.erase_workshop_component(zx0, zy0, 0)
check("erase removes everything at the cell",
      n == 2 and len(comps_at(zx0, zy0, 0)) == 0, "removed=%d" % n)

# ---------------------------------------------------------------------------
# 2. Author two ramp puzzles, then run both bulk fills.
def author(shape, layout):
    idx = ws.RAMP_PUZZLES.index(shape)
    x0, y0, _, _ = ws._ramp_puzzle_bounds(idx)
    for kind, dx, dy, layer, rot, nid in layout:
        ws.place_workshop_component(kind, x0 + dx, y0 + dy, layer,
                                    rotation=rot, name_id=nid)

author("Cube", [
    ("BLOCK", 2, 2, 0, 0, ""), ("BLOCK", 3, 2, 0, 0, ""),
    ("BLOCK", 3, 2, 1, 0, ""),                      # stacked layer 1
    ("RAMP", 2, 3, 0, 90, ""), ("RAMP", 4, 2, 0, 270, ""),
    ("BUTTON", 5, 5, 0, 0, "C"),                     # excluded from wall fill
])
author("L", [
    ("BLOCK", 1, 1, 0, 0, ""), ("BLOCK", 1, 2, 0, 0, ""),
    ("RAMP", 2, 1, 0, 0, ""),
])

before = len(comps_coll().objects)

t0 = time.perf_counter()
filled, skipped = ws.fill_ramp_wall_cells_from_ramps()
t_fill = time.perf_counter() - t0

cube_cells = ws._ramp_wall_variation_count("Cube")
l_cells = ws._ramp_wall_variation_count("L")
check("filled every Cube+L lettered cell",
      filled == cube_cells + l_cells, "filled=%d" % filled)
check("unauthored shapes skipped",
      len(skipped) == len(ws.RAMP_PUZZLES) - 2, skipped[:3])
# Cube contributes 5 ramps/blocks per cell, L contributes 3 (buttons excluded).
expected_new = cube_cells * 5 + l_cells * 3
added = len(comps_coll().objects) - before
check("ramps+walls fill placed the expected count",
      added == expected_new, "added=%d expected=%d" % (added, expected_new))

# Spot-check one filled cell: components landed inside its bounds.
idx_a = next(i for i, (s, l, _c, _r) in enumerate(ws.RAMP_WALL_CELLS)
             if (s, l) == ("Cube", "a"))
x0, y0, x1, y1 = ws._ramp_wall_bounds(idx_a)
in_cell = [o for o in comps_coll().objects
           if x0 <= o.get("snaked_x", -99) <= x1
           and y0 <= o.get("snaked_y", -99) <= y1]
check("'Cube a' cell holds its 5 components inside bounds", len(in_cell) == 5)

before = len(comps_coll().objects)
t0 = time.perf_counter()
bfilled, bempty = ws.fill_ramp_wall_button_cells_from_ramp_walls()
t_bfill = time.perf_counter() - t0

expected_bcells = (cube_cells + l_cells) * ws.RAMP_WALL_BUTTON_VARIATIONS
check("filled every numbered button cell with a source",
      bfilled == expected_bcells, "filled=%d" % bfilled)
expected_new = (cube_cells * 5 + l_cells * 3) * ws.RAMP_WALL_BUTTON_VARIATIONS
added = len(comps_coll().objects) - before
check("button-cell fill placed the expected count",
      added == expected_new, "added=%d expected=%d" % (added, expected_new))

total = len(comps_coll().objects)
print("[TEST] bulk fills: ramps+walls %.2fs, button cells %.2fs, "
      "%d components in scene" % (t_fill, t_bfill, total))

# Re-running the ramps+walls fill overwrites in place (no duplicates).
before = len(comps_coll().objects)
ws.fill_ramp_wall_cells_from_ramps()
check("re-running a fill does not duplicate components",
      len(comps_coll().objects) == before)

# ---------------------------------------------------------------------------
# 3. Benchmark: per-placement cost, fresh scan vs shared index.
N = 60
t0 = time.perf_counter()
for i in range(N):
    ws.place_workshop_component("BLOCK", 1000 + i, 0, 0)
t_no_occ = time.perf_counter() - t0

occ = ws._ComponentIndex()
t0 = time.perf_counter()
for i in range(N):
    ws.place_workshop_component("BLOCK", 2000 + i, 0, 0, occ=occ)
t_occ = time.perf_counter() - t0
print("[TEST] %d placements among %d objects: %.3fs fresh-scan, "
      "%.3fs shared index (%.1fx)"
      % (N, total, t_no_occ, t_occ, t_no_occ / max(t_occ, 1e-9)))

# ---------------------------------------------------------------------------
if FAILURES:
    print("[TEST] FAILED: %s" % ", ".join(FAILURES))
    sys.exit(1)
print("[TEST] all checks passed")
