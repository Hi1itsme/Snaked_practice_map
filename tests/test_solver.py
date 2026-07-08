"""Tests for snaked_solver.py (pure Python -- no Blender required).

Run:  python tests/test_solver.py
"""
import os
import sys
import json
import shutil
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import snaked_common as sc  # noqa: E402
import snaked_solver as sv  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    status = "ok" if cond else "FAIL"
    print("[TEST] %-58s %s %s" % (name, status, detail))
    if not cond:
        FAILURES.append(name)


def C(type_, x, y, layer=0, rotation=0, id_=""):
    return {"type": type_, "x": x, "y": y, "layer": layer,
            "rotation": rotation, "id": id_}


def level(components, start=None, goal=None, **extra):
    meta = {
        "id": "test_level",
        "grid_size": [10, 10, 4],
        "components": components,
        "start_position": list(start) if start else [0, 0, 0],
        "goal_position": list(goal) if goal else [0, 0, 0],
    }
    meta.update(extra)
    return meta


# ---------------------------------------------------------------------------
# 1. Flat movement.
r = sv.validate_level(level([], start=(1, 1, 0), goal=(5, 1, 0)))
check("flat corridor is solvable", r["solvable"] and not r["issues"])
check("flat shortest path is manhattan distance", r["shortest_path"] == 4)
check("flat level uses no ramps", r["path_uses_ramp"] is False)
check("reachable cells cover the open floor", r["reachable_cells"] == 100)

# 2. A wall bar cuts the floor in two.
walls = [C("wall", x, 3) for x in range(1, 11)]
r = sv.validate_level(level(walls, start=(1, 1, 0), goal=(5, 5, 0)))
check("wall bar makes the goal unreachable",
      not r["solvable"] and any("unreachable" in i for i in r["issues"]))

# 3. Ramp ascent: ramp faces +X (rotation 270), block beyond it.
climb = [C("ramp", 2, 1, rotation=270), C("block", 3, 1)]
r = sv.validate_level(level(climb, start=(1, 1, 0), goal=(3, 1, 1)))
check("ramp ascent reaches the block top",
      r["solvable"] and r["shortest_path"] == 2 and r["path_uses_ramp"])

r = sv.validate_level(level([C("block", 3, 1)],
                            start=(1, 1, 0), goal=(3, 1, 1)))
check("without the ramp the block top is unreachable", not r["solvable"])

# 4. Ramps only accept entry from their LOW side.
r = sv.validate_level(level([C("ramp", 2, 1, rotation=270)],
                            start=(2, 2, 0), goal=(2, 1, 0)))
check("side entry onto a ramp is forbidden (path detours to the low side)",
      r["solvable"] and r["shortest_path"] == 3, r["shortest_path"])

# 5. Descent: start on the block top, leave over the ramp.
r = sv.validate_level(level(climb, start=(3, 1, 1), goal=(1, 1, 0)))
check("ramp descent works (mirror of ascent)",
      r["solvable"] and r["shortest_path"] == 2)

# 6. Buttons: on top of a solid; unreachable buttons block solvability.
btns = climb + [C("button", 3, 1, id_="A"), C("button", 8, 8, id_="B")]
r = sv.validate_level(level(btns, start=(1, 1, 0), goal=(3, 1, 1)))
check("button on the block top is reachable",
      "A" in r["buttons_reachable"])
check("floor button across the map is also reachable",
      "B" not in r["buttons_unreachable"])
check("all buttons reachable -> solvable", r["solvable"])

sealed = btns + [C("wall", 7, 7), C("wall", 8, 7), C("wall", 9, 7),
                 C("wall", 7, 8), C("wall", 9, 8),
                 C("wall", 7, 9), C("wall", 8, 9), C("wall", 9, 9),
                 C("wall", 10, 7), C("wall", 10, 9)]
r = sv.validate_level(level(sealed, start=(1, 1, 0), goal=(3, 1, 1)))
check("sealed-off button is reported and blocks solvability",
      not r["solvable"] and r["buttons_unreachable"] == ["B"]
      and any("button" in i for i in r["issues"]))

# 7. Start / goal validity.
r = sv.validate_level(level([]))
check("unset start and goal are reported",
      not r["solvable"] and len(r["issues"]) == 2)

r = sv.validate_level(level([], start=(1, 1, 0), goal=(5, 5, 2)))
check("floating goal (no support) is rejected",
      any("goal_position" in i for i in r["issues"]))

r = sv.validate_level(level([C("wall", 1, 1)], start=(1, 1, 0),
                            goal=(5, 1, 0)))
check("start inside a wall is rejected",
      any("start_position" in i for i in r["issues"]))

# 8. Mechanics signal.
r = sv.validate_level(level(btns, start=(1, 1, 0), goal=(3, 1, 1)))
check("mechanics_present lists the component types",
      r["mechanics_present"] == ["block", "button", "ramp"])

# ---------------------------------------------------------------------------
# 9. File round trip: validate_level_file + --annotate + validate_all.
TMP = tempfile.mkdtemp(prefix="snaked_solver_test_")
meta = level(climb, start=(1, 1, 0), goal=(3, 1, 1),
             id="world_01_level_001", world=1, level_number=1)
path = os.path.join(TMP, "levels", "world_01", "level_001", "level.json")
sc.save_json(path, meta)
sc.save_json(os.path.join(TMP, "ai_data", "all_levels.json"),
             {"version": "0.1",
              "levels": [{"id": "world_01_level_001", "world": 1,
                          "level_number": 1}]})

r = sv.validate_level_file(TMP, 1, 1, annotate=True)
check("validate_level_file solves the saved level", r["solvable"])
with open(path, encoding="utf-8") as fh:
    saved = json.load(fh)
check("--annotate writes the report into level.json",
      saved.get("validation", {}).get("solvable") is True)
check("annotation preserves the level's own data",
      saved["components"] == meta["components"]
      and saved["start_position"] == [1, 1, 0])

results = sv.validate_all(TMP)
check("validate_all walks the index",
      len(results) == 1 and results[0][2]["solvable"])

shutil.rmtree(TMP, ignore_errors=True)

# ---------------------------------------------------------------------------
if FAILURES:
    print("[TEST] FAILED: %s" % ", ".join(FAILURES))
    sys.exit(1)
print("[TEST] all checks passed")
