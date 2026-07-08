"""
snaked_solver.py

Headless solvability checker / validator for saved Snaked levels.

Reads a level.json produced by snaked_tools.py (save_level) and answers:
can the snake get from start_position to goal_position, which buttons are
reachable, and how long is the shortest route -- plus difficulty signals a
future AI level generator can train on. Pure Python: runs with plain
`python snaked_solver.py`, no Blender required (but works there too).

===========================================================================
MOVEMENT MODEL (v0) -- assumptions, since the game rules are not final
===========================================================================
This is a REACHABILITY solver for the snake's head, not a full snake-body
simulation. Body mechanics (growth, tail collision, gravity on the body) are
not defined anywhere in the project yet, so this checks the necessary
condition for solvability -- a route exists -- and reports signals about it.
The rules below are deliberately explicit so they can be tuned as the game
firms up:

  * The head occupies one cell (x, y, layer); the grid is 1-based in X/Y,
    layers 0..N-1 (same conventions as every other Snaked script).
  * BLOCK and WALL fill their cell: the head can never share it.
  * Support: at layer 0 the ground carries you; above that you need a solid
    (block, or wall if WALLS_SUPPORT) in the cell below.
  * Flat movement: 4-directional, to a free supported cell on the same layer.
  * RAMPS connect layers. A ramp's facing (rotation 0 = rises toward +Y,
    CCW) points at its high wall. You may:
      - enter the ramp on its own layer from the LOW side (moving toward the
        high wall), stand on it,
      - continue forward off the top onto a supported cell one layer up,
      - or the mirror of both to descend.
    Sloped ramp tops do NOT support standing from other directions, and
    ramp-to-ramp chains are not modelled (v0).
  * BUTTONS are overlays and never block. A button is "reached" when the
    head visits the cell it physically sits in (on top of a solid: one layer
    up; on the floor: its own cell).
  * start_direction in level.json is ignored (BFS explores all directions).

===========================================================================
HOW TO RUN
===========================================================================
  python snaked_solver.py                validate every level in the index
  python snaked_solver.py 1 2            validate world 1, level 2
  python snaked_solver.py --annotate     also write each report into its
                                         level.json under "validation"

Or from Python / Blender:
    import snaked_solver
    report = snaked_solver.validate_level_file(root, world, level)
"""

import os
import sys
import json
from collections import deque


def _ensure_repo_on_path():
    """Put this repo's folder on sys.path so `import snaked_common` works no
    matter how the script is run (module import, blender --python, plain
    python, or the Text Editor's Alt+P on a saved file)."""
    dirs = []
    try:
        dirs.append(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        pass
    try:
        import bpy
        dirs.extend(
            os.path.dirname(os.path.abspath(bpy.path.abspath(t.filepath)))
            for t in bpy.data.texts if t.filepath)
        if bpy.data.filepath:
            dirs.append(os.path.dirname(bpy.data.filepath))
    except Exception:
        pass
    dirs.append(os.getcwd())
    for d in dirs:
        if os.path.isfile(os.path.join(d, "snaked_common.py")):
            if d not in sys.path:
                sys.path.insert(0, d)
            return


_ensure_repo_on_path()

import snaked_common as sc

# ---------------------------------------------------------------------------
# Movement-rule switches (see the module docstring)
# ---------------------------------------------------------------------------

WALLS_SUPPORT = True   # the head may stand ON TOP of a wall (it is a solid)

# Ramp facing rotation -> (dx, dy) of its HIGH wall. The master rises toward
# +Y at rotation 0; rotations are CCW, matching snaked_common.xform_cell.
RAMP_DIR = {0: (0, 1), 90: (-1, 0), 180: (0, -1), 270: (1, 0)}

_FLAT_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


# ---------------------------------------------------------------------------
# Level occupancy (pure data, no bpy)
# ---------------------------------------------------------------------------

class LevelGrid:
    """Occupancy view of one level's serialized components."""

    def __init__(self, meta):
        gs = meta.get("grid_size") or []
        self.width = int(gs[0]) if len(gs) > 0 and gs[0] else sc.GRID_WIDTH
        self.height = int(gs[1]) if len(gs) > 1 and gs[1] else sc.GRID_HEIGHT
        self.layers = int(gs[2]) if len(gs) > 2 and gs[2] else sc.NUM_LAYERS

        self.solids = {}    # (x, y, layer) -> "BLOCK" | "WALL"
        self.ramps = {}     # (x, y, layer) -> (dx, dy) of the high wall
        self.buttons = {}   # (x, y, layer) -> button id
        self.kinds = set()  # every component type present (mechanics signal)

        for c in meta.get("components", []):
            kind = (c.get("type") or "").upper()
            key = (int(c.get("x", 0)), int(c.get("y", 0)),
                   int(c.get("layer", 0)))
            self.kinds.add(kind.lower())
            if kind in {"BLOCK", "WALL"}:
                self.solids[key] = kind
            elif kind == "RAMP":
                self.ramps[key] = RAMP_DIR.get(
                    int(c.get("rotation", 0)) % 360, (0, 1))
            elif kind == "BUTTON":
                self.buttons[key] = c.get("id", "")

    # -- cell queries -------------------------------------------------------

    def in_grid(self, x, y, layer):
        return (1 <= x <= self.width and 1 <= y <= self.height
                and 0 <= layer < self.layers)

    def blocked(self, x, y, layer):
        """A solid or a ramp occupies the cell (ramps are entered specially)."""
        return (x, y, layer) in self.solids or (x, y, layer) in self.ramps

    def standable(self, x, y, layer):
        """Free cell the head can rest in: in-grid, empty, and supported."""
        if not self.in_grid(x, y, layer) or self.blocked(x, y, layer):
            return False
        if layer == 0:
            return True   # the ground carries you
        below = self.solids.get((x, y, layer - 1))
        if below == "WALL":
            return WALLS_SUPPORT
        return below is not None

    def valid_state(self, state):
        """A place the head may BE: standable, or standing on a ramp."""
        x, y, layer = state
        return self.standable(x, y, layer) or (x, y, layer) in self.ramps

    # -- movement ------------------------------------------------------------

    def moves(self, state):
        """All states reachable in one step from `state` (see rules above)."""
        x, y, layer = state

        # Standing ON a ramp: forward off the top (one layer up) or back down
        # the low side. Nothing else -- the sloped sides are not walkable.
        ramp_dir = self.ramps.get((x, y, layer))
        if ramp_dir is not None:
            dx, dy = ramp_dir
            out = []
            if self.standable(x + dx, y + dy, layer + 1):
                out.append((x + dx, y + dy, layer + 1))
            if self.standable(x - dx, y - dy, layer):
                out.append((x - dx, y - dy, layer))
            return out

        out = []
        for dx, dy in _FLAT_DIRS:
            nx, ny = x + dx, y + dy
            # Flat step on the same layer.
            if self.standable(nx, ny, layer):
                out.append((nx, ny, layer))
                continue
            # Step onto a ramp on this layer from its LOW side (moving toward
            # the high wall).
            if (self.in_grid(nx, ny, layer)
                    and self.ramps.get((nx, ny, layer)) == (dx, dy)):
                out.append((nx, ny, layer))
                continue
            # Step DOWN over a ramp's high wall onto the ramp one layer below.
            if layer > 0 and self.ramps.get((nx, ny, layer - 1)) == (-dx, -dy):
                out.append((nx, ny, layer - 1))
        return out

    def button_touch_states(self, key):
        """Head states that count as touching the button at `key`.

        A button placed on a solid physically sits on its top face, so the
        head touches it while standing on that solid (one layer up). A button
        on a ramp is touched from the ramp itself or from above; a button on
        open floor is touched in its own cell.
        """
        x, y, layer = key
        if key in self.solids:
            return {(x, y, layer + 1)}
        if key in self.ramps:
            return {(x, y, layer), (x, y, layer + 1)}
        return {(x, y, layer)}


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def explore(grid, start):
    """BFS from `start` over grid.moves. Returns {state: parent_state}."""
    start = tuple(start)
    seen = {start: None}
    queue = deque([start])
    while queue:
        s = queue.popleft()
        for t in grid.moves(s):
            if t not in seen:
                seen[t] = s
                queue.append(t)
    return seen


def _path_to(seen, state):
    """Reconstruct the BFS path to `state` (inclusive), or None."""
    if state not in seen:
        return None
    path = [state]
    while seen[path[-1]] is not None:
        path.append(seen[path[-1]])
    path.reverse()
    return path


def _position_or_none(value):
    """A [x, y, layer] triple from level.json, or None when unset.

    The blank template stores [0, 0, 0]; grid X/Y are 1-based, so an X or Y
    of 0 means "never filled in".
    """
    if (not isinstance(value, (list, tuple)) or len(value) < 3
            or int(value[0]) < 1 or int(value[1]) < 1):
        return None
    return (int(value[0]), int(value[1]), int(value[2]))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_level(meta):
    """Validate one level dict (parsed level.json). Returns a report dict.

    The report is JSON-ready and self-describing; `solvable` is the headline
    answer, `issues` lists everything that stops (or would stop) a player.
    """
    grid = LevelGrid(meta)
    issues = []

    start = _position_or_none(meta.get("start_position"))
    goal = _position_or_none(meta.get("goal_position"))
    if start is None:
        issues.append("start_position is not set")
    elif not grid.valid_state(start):
        issues.append("start_position %r is not a standable cell"
                      % (list(start),))
        start = None
    if goal is None:
        issues.append("goal_position is not set")
    elif not grid.valid_state(goal):
        issues.append("goal_position %r is not a standable cell"
                      % (list(goal),))
        goal = None

    report = {
        "level_id": meta.get("id", ""),
        "rules": "reachability-v0",
        "solvable": False,
        "shortest_path": None,
        "path_uses_ramp": False,
        "reachable_cells": 0,
        "buttons_total": len(grid.buttons),
        "buttons_reachable": [],
        "buttons_unreachable": sorted(grid.buttons.values()),
        "mechanics_present": sorted(grid.kinds),
        "issues": issues,
    }
    if start is None:
        return report

    seen = explore(grid, start)
    report["reachable_cells"] = len(seen)

    # Buttons: reached when any of their touch states was visited.
    reachable, unreachable = [], []
    for key, bid in grid.buttons.items():
        touched = any(s in seen for s in grid.button_touch_states(key))
        (reachable if touched else unreachable).append(bid or "?")
    report["buttons_reachable"] = sorted(reachable)
    report["buttons_unreachable"] = sorted(unreachable)
    if unreachable:
        issues.append("unreachable button(s): %s" % ", ".join(sorted(unreachable)))

    if goal is not None:
        path = _path_to(seen, goal)
        if path is None:
            issues.append("goal is unreachable from start")
        else:
            report["shortest_path"] = len(path) - 1
            report["path_uses_ramp"] = any(
                (x, y, l) in grid.ramps for x, y, l in path)
            report["solvable"] = not unreachable

    return report


def _level_json_path(root, world, level):
    return os.path.join(root, "levels", sc.world_folder_name(world),
                        sc.level_folder_name(level), "level.json")


def validate_level_file(root, world, level, annotate=False):
    """Validate levels/world_NN/level_MMM/level.json. Returns the report.

    With `annotate` True the report is also written back into the file under
    a "validation" key (everything else in the file is preserved).
    """
    path = _level_json_path(root, world, level)
    with open(path, "r", encoding="utf-8") as fh:
        meta = json.load(fh)
    report = validate_level(meta)
    if annotate:
        meta["validation"] = report
        sc.save_json(path, meta)
    return report


def validate_all(root, annotate=False):
    """Validate every level listed in ai_data/all_levels.json.

    Returns a list of (world, level, report_or_error_string).
    """
    index_path = os.path.join(root, "ai_data", "all_levels.json")
    try:
        with open(index_path, "r", encoding="utf-8") as fh:
            entries = json.load(fh).get("levels", [])
    except (OSError, ValueError):
        return []
    results = []
    for e in entries:
        world, level = e.get("world"), e.get("level_number")
        try:
            results.append((world, level,
                            validate_level_file(root, world, level,
                                                annotate=annotate)))
        except (OSError, ValueError) as exc:
            results.append((world, level, "could not read level.json (%s)" % exc))
    return results


def _print_report(world, level, report):
    if isinstance(report, str):
        print("  world %s level %s: ERROR -- %s" % (world, level, report))
        return
    verdict = "SOLVABLE" if report["solvable"] else "NOT SOLVABLE"
    extras = []
    if report["shortest_path"] is not None:
        extras.append("shortest path %d" % report["shortest_path"])
    if report["path_uses_ramp"]:
        extras.append("uses ramps")
    if report["buttons_total"]:
        extras.append("buttons %d/%d reachable"
                      % (len(report["buttons_reachable"]),
                         report["buttons_total"]))
    print("  %s: %s%s" % (report["level_id"] or
                          ("world %s level %s" % (world, level)),
                          verdict,
                          (" (%s)" % ", ".join(extras)) if extras else ""))
    for issue in report["issues"]:
        print("      - %s" % issue)


def main(argv):
    annotate = "--annotate" in argv
    args = [a for a in argv if not a.startswith("--")]
    root = sc.resolve_project_root()

    if len(args) >= 2:
        world, level = int(args[0]), int(args[1])
        print("[Solver] Validating world %d level %d (root: %s)"
              % (world, level, root))
        report = validate_level_file(root, world, level, annotate=annotate)
        _print_report(world, level, report)
        return 0 if report["solvable"] else 1

    print("[Solver] Validating every level in the index (root: %s)" % root)
    results = validate_all(root, annotate=annotate)
    if not results:
        print("  (no levels in ai_data/all_levels.json yet)")
        return 0
    for world, level, report in results:
        _print_report(world, level, report)
    bad = sum(1 for _, _, r in results
              if isinstance(r, str) or not r["solvable"])
    print("[Solver] %d level(s) checked, %d with problems."
          % (len(results), bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
