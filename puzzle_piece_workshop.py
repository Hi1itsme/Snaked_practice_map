"""
puzzle_piece_workshop.py


Blank foundation for the "Snaked" reusable puzzle-piece workshop.

This script does two things and is SAFE TO RUN MULTIPLE TIMES:

  1. Creates the on-disk project scaffold (folders + empty JSON files) for a
     future visual-editor + local-AI pipeline. Existing files are never
     overwritten -- missing folders/files are filled in, nothing is destroyed.

  2. Inside Blender, builds a blank "Puzzle_Piece_Workshop" area off to the
     side of the main level (around X = 40). It draws four labelled, EMPTY
     zones (floor guide + border + text header) so you have a tidy place to
     start authoring pieces. It deliberately places NO example components.

  3. Inside Blender, registers a "Snaked Workshop" sidebar panel that lets you
     drop floor / block / wall / ramp / button components into a chosen zone
     with point-and-click, the same way snaked_tools.py works for the main grid.

It never touches the existing "Snaked_Map" collection. Re-running only ever
clears and rebuilds the "Puzzle_Piece_Workshop" collection. Components you place
live in their own "Puzzle_Workshop_Components" collection and are NEVER deleted
by a rebuild.

Conventions (shared with snaked_map_builder.py)
-----------------------------------------------
- 1 Blender unit == 1 tile.
- X and Y are the grid directions; tile centres sit on integer world coords.
- Z is height; the floor guide sits at z = 0.

===========================================================================
HOW TO ACTIVATE  (the placement panel)
===========================================================================

Step 1 -- Run this script ONCE to build the zones and register the panel:

  Option A (Blender Text Editor):
    - Open Blender, switch an area to the "Text Editor".
    - Open this file (Text > Open), then press  Alt+P  (Text > Run Script).

  Option B (command line):
    - blender --python puzzle_piece_workshop.py

  Option C (VS Code with a Blender-connect add-on, e.g. "Blender Development"):
    - Command Palette > "Blender: Run Script" while connected to Blender.

Step 2 -- Open the panel:
    - Hover the 3D viewport and press  N  to open the right-hand sidebar.
    - Click the vertical  "Snaked Workshop"  tab.

Step 3 -- Place components:
    - Pick an Area:
        * "Workbench Zones" -- the four general zones; place any component.
        * "Ramp Puzzles"    -- the ramp-puzzle area; Place drops a Ramp into the
                               named puzzle cell you choose (Cube, L, Rectangle,
                               U, Indent, Tabletop, Plus, Short Top, Double Top,
                               Big Square, Fortress, Fortress 2, Overhang, Fish).
                               Blocks are fundamental, so picking "Block" places
                               a block here too; Erase works anywhere.
        * "Ramps + Walls"   -- a second area with lettered variation cells for
                               each ramp shape (Cube a..w, L a..d, Rectangle a/b,
                               and at least a/b for every other shape). Unlike the
                               ramp area it is NOT forced, so you place Ramps or
                               Walls (or any component) into each variation cell.
    - Pick the Zone / Puzzle, then a Col / Row inside it, and a Layer (height).
    - For a Workbench Zone, also pick a Component (Floor / Block / Wall / Ramp /
      Button / Erase).
    - Click  "Place"  --  OR  point the 3D cursor in the viewport (Shift+Right
      click) and click  "Place at 3D Cursor"  for the fastest workflow.
    - Buttons need an "ID / Name"; Ramp direction uses the Rotation buttons.
    - Choose "Erase" + Place to remove the component at that cell.

Re-running the script (Alt+P again) safely reloads the panel and rebuilds the
empty zones; your placed components are kept. Placed components also remember
which area square they live in, so if an area is relocated (its *_ORIGIN_X/Y
constants changed), re-running moves every piece along with its square.
"""

import os
import json
import copy

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_DIR_NAME = "Snaked_Project"   # root folder created on disk

COLLECTION_NAME = "Puzzle_Piece_Workshop"
MAIN_MAP_COLLECTION = "Snaked_Map"    # never modified -- listed only for clarity

# Place the workshop well clear of the main level grid (X 0.5..22.5).
WORKSHOP_ORIGIN_X = 40   # left-most tile column of the workshop

# Each labelled zone is a flat ZONE_WIDTH x ZONE_HEIGHT floor area. Zones are
# stacked along +Y with a gap that leaves room for each zone's text header.
ZONE_WIDTH = 10    # tiles along X
ZONE_HEIGHT = 8    # tiles along Y
ZONE_GAP = 4       # empty tiles (and header space) between stacked zones

# The four workbench zones, bottom (low Y) to top (high Y).
ZONES = [
    "Single Components",
    "Small Puzzle Pieces",
    "Finished Reusable Tactics",
    "Export Staging Area",
]

# A readable accent colour per zone (RGB 0..1), reused for its border frame.
ZONE_ACCENTS = [
    (0.30, 0.55, 0.85),   # blue
    (0.35, 0.75, 0.45),   # green
    (0.90, 0.65, 0.20),   # amber
    (0.75, 0.40, 0.80),   # violet
]

# ---------------------------------------------------------------------------
# Ramp-only puzzle area
# ---------------------------------------------------------------------------
# A separate region, further out in X than the workbench, holding one labelled
# cell per named ramp puzzle. These are meant for authoring ramp shapes only;
# the placement panel can target them directly (and forces the Ramp component).

# Each named ramp puzzle gets its own square cell, laid out in a grid.
RAMP_AREA_ORIGIN_X = 60   # left-most tile column of the ramp-puzzle area
RAMP_AREA_ORIGIN_Y = 1    # bottom row of the ramp-puzzle area
RAMP_CELL = 8             # tiles per side of each ramp puzzle cell
RAMP_CELL_GAP = 4         # empty tiles (and header space) between cells
RAMP_AREA_COLS = 5        # cells per row before wrapping to the next row up

# The amber ramp accent, reused for every ramp-puzzle border (signals "ramps").
RAMP_ACCENT = (0.95, 0.75, 0.15)

# The named ramp puzzles, in layout order (left->right, bottom->top).
RAMP_PUZZLES = [
    "Cube",
    "L",
    "Rectangle",
    "U",
    "Indent",
    "Tabletop",
    "Plus",
    "Short Top",
    "Double Top",
    "Big Square",
    "Fortress",
    "Fortress 2",
    "Overhang",
    "Fish",
]

# ---------------------------------------------------------------------------
# Ramps + Walls puzzle area
# ---------------------------------------------------------------------------
# A SECOND labelled area, further out in X than the ramp-only area, holding
# lettered *variation* cells for each ramp shape so you can author ramp- AND
# wall-based variants side by side. Every shape gets its own row; that shape's
# variations (a, b, c, ...) run left->right across the row. Unlike the ramp-only
# area, this area never forces a component -- you place Ramps OR Walls freely.

RAMP_WALL_AREA_ORIGIN_X = 130  # left-most tile column of the ramps+walls area
RAMP_WALL_AREA_ORIGIN_Y = 1    # bottom row of the ramps+walls area
# Ramps+walls cells are one tile larger than the ramp-puzzle cells so an
# authored ramp puzzle can be filled into the centre with room left over for
# the walls you add per variation. (Gap is still reused: RAMP_CELL_GAP.)
RAMP_WALL_CELL = RAMP_CELL + 1   # tiles per side of each ramps+walls cell

# Per-cell size overrides for individual ramps+walls cells, keyed by
# (shape, letter). A listed cell is drawn this many tiles per side instead of
# RAMP_WALL_CELL. The cell's bottom-left corner is unchanged (column stride still
# uses RAMP_WALL_CELL), so an oversized cell just grows up/right into the
# surrounding RAMP_CELL_GAP -- keep the override small enough to stay clear of
# its neighbours (gap is RAMP_CELL_GAP tiles).
RAMP_WALL_CELL_OVERRIDES = {
    ("Fortress 2", "b"): RAMP_WALL_CELL + 1,
}


def _ramp_wall_cell_size(shape, letter):
    """Tiles-per-side for a given ramps+walls cell (honouring any override)."""
    return RAMP_WALL_CELL_OVERRIDES.get((shape, letter), RAMP_WALL_CELL)

# A cool-blue accent for every ramps+walls border (distinct from amber ramps).
RAMP_WALL_ACCENT = (0.45, 0.70, 0.95)

# How many lettered variations each shape gets in the ramps+walls area. Any
# shape not listed here gets RAMP_WALL_DEFAULT_VARIATIONS ("at least a, b").
RAMP_WALL_VARIATION_COUNTS = {
    "Cube": 23,       # a .. w
    "L": 4,           # a .. d
    "Rectangle": 2,   # a, b
    "Indent": 2,      # a, b
    "Plus": 2,        # a, b
    "Double Top": 2,  # a, b
}
RAMP_WALL_DEFAULT_VARIATIONS = 2   # every other ramp shape: at least a, b


def _ramp_wall_variation_count(shape):
    """How many lettered variation cells a given shape gets."""
    return RAMP_WALL_VARIATION_COUNTS.get(shape, RAMP_WALL_DEFAULT_VARIATIONS)


def _build_ramp_wall_cells():
    """Flat, ordered list of (shape, letter, col, row) variation cells.

    One row per shape (taken from RAMP_PUZZLES order, bottom->top); each shape's
    lettered variations run left->right across its row (col 0 == 'a').
    """
    cells = []
    for row, shape in enumerate(RAMP_PUZZLES):
        for col in range(_ramp_wall_variation_count(shape)):
            letter = chr(ord('a') + col)
            cells.append((shape, letter, col, row))
    return cells


# Every ramps+walls variation cell, in layout / dropdown order.
RAMP_WALL_CELLS = _build_ramp_wall_cells()


# ---------------------------------------------------------------------------
# Ramps + Walls + Buttons puzzle area
# ---------------------------------------------------------------------------
# A THIRD labelled area that imports every authored ramps+walls piece and gives
# each one a few NUMBERED variation cells -- room to add buttons per variation.
# Layout mirrors the ramps+walls area: one row per ramps+walls (shape, letter)
# piece, with that piece's numbered variations running left->right across the
# row. Like the ramps+walls area it never forces a component, so you freely add
# Buttons (and Ramps / Walls) into each cell. Keep the count small -- every cell
# draws its own floor grid + border + label, so more cells = slower rebuilds.

RAMP_WALL_BUTTON_AREA_ORIGIN_X = 600  # left-most tile column of this area
RAMP_WALL_BUTTON_AREA_ORIGIN_Y = 1    # bottom row of this area
RAMP_WALL_BUTTON_VARIATIONS = 4       # numbered cells per ramps+walls piece (1..N)

# Ramps+walls+buttons cells are 2 tiles bigger per side than the ramps+walls
# cells they import, leaving extra room around the piece to add buttons.
RAMP_WALL_BUTTON_CELL = RAMP_WALL_CELL + 2

# A warm red accent for every ramps+walls+buttons border (signals "buttons").
RAMP_WALL_BUTTON_ACCENT = (0.95, 0.45, 0.45)


def _ramp_wall_button_cell_size(shape, letter):
    """Tiles-per-side for a ramps+walls+buttons cell: 2 bigger than its source
    ramps+walls cell (honouring any per-cell override on that source)."""
    return _ramp_wall_cell_size(shape, letter) + 2


def _build_ramp_wall_button_cells():
    """Flat, ordered list of (shape, letter, number, col, row) numbered cells.

    One row per ramps+walls piece (same order as RAMP_WALL_CELLS); each piece's
    numbered variations (1..RAMP_WALL_BUTTON_VARIATIONS) run left->right.
    """
    cells = []
    for row, (shape, letter, _col, _row) in enumerate(RAMP_WALL_CELLS):
        for col in range(RAMP_WALL_BUTTON_VARIATIONS):
            cells.append((shape, letter, col + 1, col, row))
    return cells


# Every ramps+walls+buttons numbered cell, in layout / dropdown order.
RAMP_WALL_BUTTON_CELLS = _build_ramp_wall_button_cells()

# (shape, letter) -> its index in RAMP_WALL_CELLS, for importing the source piece.
_RAMP_WALL_INDEX_BY_KEY = {
    (shape, letter): i
    for i, (shape, letter, _col, _row) in enumerate(RAMP_WALL_CELLS)
}


# ---------------------------------------------------------------------------
# Ramp-puzzle orientation generation (config + pure transforms)
# ---------------------------------------------------------------------------
# For each authored ramp puzzle we can auto-generate its rotated / mirrored
# orientations. Rotations are flat (about the vertical Z axis); a mirror flips
# the piece left<->right (across X). The first entry of every set is always
# (0, False) -- the base piece. Curated sets per shape:
#
#   * L, Indent, Overhang, Fish                -> all 8 (4 rotations + mirrors)
#   * Cube, U, Tabletop, Plus, Short Top,
#     Double Top, Fortress, Fortress 2         -> 4 rotations only
#   * Rectangle                                -> base + 90 deg
#   * Big Square                               -> base + 180 deg
#
# Generated orientations are laid out in their own area (X = below) and saved
# as one piece JSON per orientation under snaked_assets/puzzle_pieces/.

WORKSHOP_ORIENTATIONS_COLLECTION = "Puzzle_Workshop_Orientations"
RAMP_ORIENT_AREA_ORIGIN_X = 450   # left-most tile column of the orientations area
RAMP_ORIENT_AREA_ORIGIN_Y = 1     # bottom row of the orientations area


def _rot4():
    """Base + the three flat rotations, no mirror (4 orientations)."""
    return [(0, False), (90, False), (180, False), (270, False)]


def _rot4_mirrored():
    """All four rotations plus a mirrored copy of each (8 orientations)."""
    return _rot4() + [(0, True), (90, True), (180, True), (270, True)]


# Per-shape orientation sets (see table above). An orientation is a
# (rotation_degrees, mirrored) pair.
RAMP_PUZZLE_ORIENTATIONS = {
    "L": _rot4_mirrored(),
    "Indent": _rot4_mirrored(),
    "Overhang": _rot4_mirrored(),
    "Fish": _rot4_mirrored(),
    "Cube": _rot4(),
    "U": _rot4(),
    "Tabletop": _rot4(),
    "Plus": _rot4(),
    "Short Top": _rot4(),
    "Double Top": _rot4(),
    "Fortress": _rot4(),
    "Fortress 2": _rot4(),
    "Rectangle": [(0, False), (90, False)],
    "Big Square": [(0, False), (180, False)],
}


def _orientations_for(shape):
    """Curated orientation set for a shape (defaults to 4 rotations)."""
    return RAMP_PUZZLE_ORIENTATIONS.get(shape, _rot4())


def _orientation_tag(rotation, mirrored):
    """Short, filename-safe tag, e.g. (90, True) -> 'r90_m'."""
    return "r%d%s" % (rotation, "_m" if mirrored else "")


def _orientation_meta(rotation, mirrored, index):
    """Descriptive metadata for one orientation (label / type / notes / base)."""
    is_base = (rotation == 0 and not mirrored)
    if is_base:
        vtype, notes = "base", "Base orientation as authored."
    elif mirrored and rotation:
        vtype, notes = "mirror", "Mirrored, then rotated %d deg." % rotation
    elif mirrored:
        vtype, notes = "mirror", "Mirrored (left-right)."
    else:
        vtype, notes = "rotate", "Rotated %d deg." % rotation
    return {
        "tag": _orientation_tag(rotation, mirrored),
        "label": "%d%s" % (rotation, " M" if mirrored else ""),
        "vtype": vtype,
        "notes": notes,
        "is_base": is_base,
        "index": index,
    }


def _xform_cell(cx, cy, rotation, mirrored):
    """Transform a relative cell: mirror across X first, then rotate CCW."""
    if mirrored:
        cx = -cx
    for _ in range((rotation // 90) % 4):
        cx, cy = -cy, cx
    return cx, cy


def _xform_ramp_rotation(rrot, rotation, mirrored):
    """Transform a ramp's facing to match a mirror-then-rotate of the piece.

    A left<->right mirror sends facing r -> (360 - r); a flat CCW rotation by
    `rotation` degrees adds that much. (Derived from the +Y-facing master at
    r = 0: mirroring keeps +Y, while +X<->-X swap, i.e. r -> -r.)
    """
    if mirrored:
        rrot = (360 - rrot) % 360
    return (rrot + rotation) % 360


def _transform_piece(components, rotation, mirrored):
    """Return a new component list for one orientation, re-packed to (0, 0)."""
    out = []
    for c in components:
        nx, ny = _xform_cell(c["x"], c["y"], rotation, mirrored)
        nc = dict(c)
        nc["x"], nc["y"] = nx, ny
        if c.get("kind") == "RAMP":
            nc["rotation"] = _xform_ramp_rotation(
                c.get("rotation", 0), rotation, mirrored)
        else:
            nc["rotation"] = 0
        out.append(nc)
    if out:
        minx = min(c["x"] for c in out)
        miny = min(c["y"] for c in out)
        for c in out:
            c["x"] -= minx
            c["y"] -= miny
    return out


def _piece_grid_size(components):
    """[width, height, layers] bounding box of a relative-coord component list."""
    if not components:
        return [0, 0, 0]
    w = max(c["x"] for c in components) + 1
    h = max(c["y"] for c in components) + 1
    layers = max(c.get("layer", 0) for c in components) + 1
    return [w, h, layers]


# ---- piece / family JSON builders + writers (pure Python) -----------------

def _pieces_dir(root):
    """Absolute path of the puzzle_pieces/ folder under the project root."""
    return os.path.join(root, "snaked_assets", "puzzle_pieces")


def _family_id_for(shape):
    """Canonical family id for a ramp puzzle, e.g. 'Big Square' -> 'ramp_big_square'."""
    return "ramp_" + shape.lower().replace(" ", "_")


def _build_piece_dict(pid, fid, shape, meta, components, base_id):
    """Fill a copy of the metadata template for one orientation."""
    piece = copy.deepcopy(_METADATA_TEMPLATE)
    piece["id"] = pid
    piece["family_id"] = fid
    piece["base_piece_id"] = "" if meta["is_base"] else base_id
    piece["variation_type"] = meta["vtype"]
    piece["variation_index"] = meta["index"]
    piece["is_base_piece"] = meta["is_base"]
    piece["name"] = "%s (%s)" % (shape, meta["label"])
    piece["category"] = "ramp_puzzle"
    piece["grid_size"] = _piece_grid_size(components)
    piece["components"] = [
        {
            "type": c.get("kind", "").lower(),
            "x": c["x"],
            "y": c["y"],
            "layer": c.get("layer", 0),
            "rotation": c.get("rotation", 0),
            "id": c.get("id", ""),
        }
        for c in components
    ]
    piece["tags"] = ["ramp", shape.lower().replace(" ", "_"), meta["vtype"]]
    piece["variation_notes"] = meta["notes"]
    return piece


def _build_family_dict(fid, shape, base_id, variation_ids):
    """Fill a copy of the family template for a ramp-puzzle family."""
    fam = copy.deepcopy(_FAMILY_TEMPLATE)
    fam["family_id"] = fid
    fam["family_name"] = shape
    fam["core_idea"] = "Ramp puzzle '%s' and its generated orientations." % shape
    fam["main_mechanics"] = ["ramp"]
    fam["base_piece_id"] = base_id
    fam["variation_ids"] = variation_ids
    fam["tags"] = ["ramp", shape.lower().replace(" ", "_")]
    return fam


def _write_family_files(root, fid, family, pieces):
    """Write family.json + one piece_<tag>.json per orientation for a family."""
    family_dir = os.path.join(_pieces_dir(root), fid)
    os.makedirs(family_dir, exist_ok=True)
    with open(os.path.join(family_dir, "family.json"), "w", encoding="utf-8") as fh:
        json.dump(family, fh, indent=2)
        fh.write("\n")
    for piece in pieces:
        tag = piece["id"][len(fid) + 1:]   # "<fid>_<tag>" -> "<tag>"
        path = os.path.join(family_dir, "piece_%s.json" % tag)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(piece, fh, indent=2)
            fh.write("\n")


def _register_pieces_in_index(root, family, pieces):
    """Refresh ai_data/all_puzzle_pieces.json for one family (replace, not dupe)."""
    path = os.path.join(root, "ai_data", "all_puzzle_pieces.json")
    data = {"version": "0.1", "families": [], "pieces": []}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (ValueError, OSError):
            data = {"version": "0.1", "families": [], "pieces": []}
    data.setdefault("version", "0.1")
    data.setdefault("families", [])
    data.setdefault("pieces", [])

    fid = family["family_id"]
    # Drop any prior entries for this family, then add the fresh ones.
    data["families"] = [f for f in data["families"]
                        if f.get("family_id") != fid] + [family]
    data["pieces"] = [p for p in data["pieces"]
                      if p.get("family_id") != fid] + list(pieces)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


# ===========================================================================
# PART 1 -- On-disk project scaffold (pure Python; runs anywhere)
# ===========================================================================

# Folder tree (relative to the project root) to ensure exists.
_FOLDERS = [
    "blender",
    "blender/main_levels",
    "snaked_assets",
    "snaked_assets/components/floor",
    "snaked_assets/components/wall",
    "snaked_assets/components/ramp",
    "snaked_assets/components/button",
    "snaked_assets/components/block",
    "snaked_assets/puzzle_pieces",
    "ai_data",
]

# Blank metadata template for a single future puzzle piece.
#
# Variation support: a piece can be a "base" piece or a variation of one.
# Variations share a `family_id` and point back to their `base_piece_id`, so
# the family's explanation lives once (in the family file) and is never
# duplicated per variation -- each variation only records what makes it differ
# (variation_type / variation_index / variation_notes).
_METADATA_TEMPLATE = {
    "id": "",
    "family_id": "",          # which piece family this belongs to
    "base_piece_id": "",      # the base piece this is a variation of ("" if base)
    "variation_type": "",     # e.g. "easy", "hard", "reversed", "taller", "themed"
    "variation_index": 0,     # ordering within the family's variations
    "is_base_piece": False,   # True for the family's canonical base piece
    "name": "",
    "category": "",
    "difficulty": 0,
    "grid_size": [0, 0, 0],
    "components": [],
    "entry_points": [],
    "exit_points": [],
    "tags": [],
    "requirements": [],
    "effects": [],
    "constraints": [],
    "variation_notes": "",    # what makes THIS variation differ from the base
    "notes": "",
}

# Blank template for a piece *family* -- the shared idea behind a base piece and
# all of its variations. The explanation lives here once; variations reference
# the family by `family_id` instead of repeating it.
_FAMILY_TEMPLATE = {
    "family_id": "",
    "family_name": "",
    "core_idea": "",
    "main_mechanics": [],
    "base_piece_id": "",
    "variation_ids": [],
    "difficulty_range": [0, 0],
    "tags": [],
    "notes": "",
}

# Blank starter contents for the AI-readable data files.
# Maps a path (relative to the project root) -> default JSON contents.
_JSON_FILES = {
    "snaked_assets/puzzle_piece_metadata_template.json": _METADATA_TEMPLATE,
    "snaked_assets/puzzle_piece_family_template.json": _FAMILY_TEMPLATE,
    "ai_data/all_puzzle_pieces.json": {"version": "0.1", "families": [], "pieces": []},
    "ai_data/training_examples.json": {"version": "0.1", "examples": []},
}


def _base_dir():
    """Best-effort folder to anchor the project root in.

    Order of preference:
      1. The saved .blend file's folder (when running inside Blender).
      2. This script file's folder (saved .py / VS Code).
      3. The current working directory.
    """
    try:
        import bpy
        if bpy.data.filepath:
            return os.path.dirname(bpy.data.filepath)
    except Exception:
        pass
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()


def resolve_project_root():
    """Return the absolute path of the Snaked_Project root.

    If we're already running from somewhere inside an existing Snaked_Project
    tree, reuse that root instead of nesting a second one.
    """
    base = os.path.normpath(_base_dir())
    parts = base.split(os.sep)
    if PROJECT_DIR_NAME in parts:
        idx = len(parts) - 1 - parts[::-1].index(PROJECT_DIR_NAME)
        return os.sep.join(parts[: idx + 1])
    return os.path.join(base, PROJECT_DIR_NAME)


def setup_project_files():
    """Create folders and blank JSON files if (and only if) they are missing.

    Returns the resolved project-root path. Existing files are left untouched
    so this is safe to run repeatedly and will never clobber your data.
    """
    root = resolve_project_root()
    os.makedirs(root, exist_ok=True)

    # Folders -- exist_ok keeps this idempotent.
    for rel in _FOLDERS:
        os.makedirs(os.path.join(root, *rel.split("/")), exist_ok=True)

    # JSON files -- only written when absent.
    for rel, contents in _JSON_FILES.items():
        path = os.path.join(root, *rel.split("/"))
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(contents, fh, indent=2)
                fh.write("\n")
            print("[Workshop] Created %s" % path)
        else:
            print("[Workshop] Kept existing %s" % path)

    print("[Workshop] Project scaffold ready at: %s" % root)
    return root


# ===========================================================================
# PART 2 -- Blank Blender workshop (requires bpy / runs inside Blender)
# ===========================================================================

def _get_material(name, color):
    """Return a flat-shaded material with the given name, creating it if needed."""
    import bpy
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = False
    mat.diffuse_color = (color[0], color[1], color[2], 1.0)
    return mat


def _apply_material(obj, name, color):
    mat = _get_material(name, color)
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def get_workshop_collection():
    """Return the dedicated workshop collection, creating and linking it if needed."""
    import bpy
    coll = bpy.data.collections.get(COLLECTION_NAME)
    if coll is None:
        coll = bpy.data.collections.new(COLLECTION_NAME)
        bpy.context.scene.collection.children.link(coll)
    return coll


def clear_workshop():
    """Remove everything previously generated *inside the workshop only*.

    The main map collection ("Snaked_Map") and every other collection are
    never inspected or modified.
    """
    import bpy
    coll = bpy.data.collections.get(COLLECTION_NAME)
    if coll is None:
        return
    for obj in list(coll.objects):
        data = obj.data if obj.type in {'MESH', 'FONT'} else None
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Curve):
                bpy.data.curves.remove(data)


def _link_to_workshop(obj):
    """Unlink an object from any other collection and place it in the workshop."""
    import bpy
    coll = get_workshop_collection()
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)


class _GuideMeshBuilder:
    """Accumulates axis-aligned boxes and emits them all as ONE mesh object.

    Guide scenery (grid lines, borders) used to be one object -- with its own
    mesh datablock, created via a bpy.ops call -- per line segment, which meant
    thousands of objects, a huge .blend and a laggy viewport. Boxes added here
    become faces of a single shared mesh instead; colours are kept via one
    material slot per (name, colour) and per-face material indices.
    """

    # Standard cube faces over the 8 corner verts emitted by add_box.
    _FACES = (
        (0, 3, 2, 1), (4, 5, 6, 7),   # bottom, top
        (0, 1, 5, 4), (1, 2, 6, 5),   # -Y, +X
        (2, 3, 7, 6), (3, 0, 4, 7),   # +Y, -X
    )

    def __init__(self, name):
        self.name = name
        self.verts = []
        self.faces = []
        self.face_mats = []
        self.mats = []           # (mat_name, color) in material-slot order
        self._slot_by_name = {}

    def _mat_slot(self, name, color):
        slot = self._slot_by_name.get(name)
        if slot is None:
            slot = len(self.mats)
            self._slot_by_name[name] = slot
            self.mats.append((name, color))
        return slot

    def add_box(self, location, size, mat_name, color):
        """Append a box with explicit per-axis dimensions, centred on location."""
        cx, cy, cz = location
        hx, hy, hz = size[0] / 2.0, size[1] / 2.0, size[2] / 2.0
        base = len(self.verts)
        self.verts.extend((
            (cx - hx, cy - hy, cz - hz), (cx + hx, cy - hy, cz - hz),
            (cx + hx, cy + hy, cz - hz), (cx - hx, cy + hy, cz - hz),
            (cx - hx, cy - hy, cz + hz), (cx + hx, cy - hy, cz + hz),
            (cx + hx, cy + hy, cz + hz), (cx - hx, cy + hy, cz + hz),
        ))
        slot = self._mat_slot(mat_name, color)
        for f in self._FACES:
            self.faces.append((base + f[0], base + f[1],
                               base + f[2], base + f[3]))
            self.face_mats.append(slot)

    def build(self):
        """Create and return the merged mesh object (not linked anywhere yet)."""
        import bpy
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(self.verts, [], self.faces)
        for name, color in self.mats:
            mesh.materials.append(_get_material(name, color))
        mesh.polygons.foreach_set("material_index", self.face_mats)
        mesh.update()
        return bpy.data.objects.new(self.name, mesh)


def _link_guide(builder):
    """Build a guide builder's merged mesh object and link it into the workshop."""
    obj = builder.build()
    # Guide geometry is scenery, not pieces -- keep it from getting in the way.
    obj.hide_select = True
    _link_to_workshop(obj)
    return obj


def _add_label(text, x, y, color, size=1.4):
    """Add a flat text label lying on the floor (readable from the top view)."""
    import bpy
    curve = bpy.data.curves.new(type='FONT', name=text + "_Font")
    curve.body = text
    curve.size = size
    curve.align_x = 'LEFT'
    curve.align_y = 'BOTTOM'
    # Signage only needs to be readable -- a low curve resolution keeps a few
    # hundred labels from weighing on every viewport redraw.
    curve.resolution_u = 3

    obj = bpy.data.objects.new("Label_" + text.replace(" ", "_"), curve)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = (float(x), float(y), 0.05)   # just above the floor; no z-fight
    _link_to_workshop(obj)
    _apply_material(obj, "Workshop_LabelMat", color)
    obj.hide_select = True   # signage, not a draggable piece
    return obj


def _zone_bounds(index):
    """Inclusive tile bounds (x0, y0, x1, y1) for the zone at the given index."""
    x0 = WORKSHOP_ORIGIN_X
    x1 = WORKSHOP_ORIGIN_X + ZONE_WIDTH - 1
    y0 = 1 + index * (ZONE_HEIGHT + ZONE_GAP)
    y1 = y0 + ZONE_HEIGHT - 1
    return x0, y0, x1, y1


def _ramp_puzzle_bounds(index):
    """Inclusive tile bounds (x0, y0, x1, y1) for the ramp puzzle at `index`.

    Cells are laid out in a grid RAMP_AREA_COLS wide, filling left->right then
    bottom->top, each a RAMP_CELL square with RAMP_CELL_GAP between them.
    """
    col = index % RAMP_AREA_COLS
    row = index // RAMP_AREA_COLS
    stride = RAMP_CELL + RAMP_CELL_GAP
    x0 = RAMP_AREA_ORIGIN_X + col * stride
    y0 = RAMP_AREA_ORIGIN_Y + row * stride
    x1 = x0 + RAMP_CELL - 1
    y1 = y0 + RAMP_CELL - 1
    return x0, y0, x1, y1


def _ramp_wall_bounds(index):
    """Inclusive tile bounds (x0, y0, x1, y1) for the ramps+walls cell at `index`.

    One row per shape; each shape's lettered variations run left->right. Cells
    are RAMP_CELL squares spaced by RAMP_CELL_GAP, same sizing as the ramp area.
    """
    shape, letter, col, row = RAMP_WALL_CELLS[index]
    stride = RAMP_WALL_CELL + RAMP_CELL_GAP
    x0 = RAMP_WALL_AREA_ORIGIN_X + col * stride
    y0 = RAMP_WALL_AREA_ORIGIN_Y + row * stride
    size = _ramp_wall_cell_size(shape, letter)
    x1 = x0 + size - 1
    y1 = y0 + size - 1
    return x0, y0, x1, y1


def _draw_floor(builder, x0, y0, x1, y1):
    """Add a flat grid floor over tile cells x0..x1, y0..y1 (inclusive).

    Cells are centred on integer coords, so grid lines run along the
    half-integers from x0-0.5 to x1+0.5 (same scheme as snaked_map_builder).
    """
    line_thickness = 0.02
    mat_name, color = "Workshop_GridFloor", (0.30, 0.31, 0.29)

    x_lo, x_hi = x0 - 0.5, x1 + 0.5
    y_lo, y_hi = y0 - 0.5, y1 + 0.5
    x_span = x_hi - x_lo
    y_span = y_hi - y_lo
    x_center = (x_lo + x_hi) / 2.0
    y_center = (y_lo + y_hi) / 2.0

    # Lines parallel to Y (varying X).
    for i in range(int(round(x_span)) + 1):
        builder.add_box((x_lo + i, y_center, 0.0),
                        (line_thickness, y_span, line_thickness),
                        mat_name, color)
    # Lines parallel to X (varying Y).
    for j in range(int(round(y_span)) + 1):
        builder.add_box((x_center, y_lo + j, 0.0),
                        (x_span, line_thickness, line_thickness),
                        mat_name, color)


def _draw_border(builder, x0, y0, x1, y1, mat_name, color):
    """Add a coloured frame around a zone so empty zones stay easy to read."""
    t = 0.08          # border thickness
    z = 0.04          # sits just above the floor lines
    x_lo, x_hi = x0 - 0.5, x1 + 0.5
    y_lo, y_hi = y0 - 0.5, y1 + 0.5
    x_span = (x_hi - x_lo) + t
    y_span = (y_hi - y_lo) + t
    x_center = (x_lo + x_hi) / 2.0
    y_center = (y_lo + y_hi) / 2.0

    edges = (
        ((x_center, y_lo, z), (x_span, t, t)),   # bottom
        ((x_center, y_hi, z), (x_span, t, t)),   # top
        ((x_lo, y_center, z), (t, y_span, t)),   # left
        ((x_hi, y_center, z), (t, y_span, t)),   # right
    )
    for loc, size in edges:
        builder.add_box(loc, size, mat_name, color)


def _build_zone(builder, index, title):
    """Draw one blank, labelled zone: floor grid + coloured border + header."""
    x0, y0, x1, y1 = _zone_bounds(index)
    accent = ZONE_ACCENTS[index % len(ZONE_ACCENTS)]
    _draw_floor(builder, x0, y0, x1, y1)
    _draw_border(builder, x0, y0, x1, y1, "Workshop_Border_Zone%d" % index, accent)
    # Header sits in the gap just above the zone's far (high-Y) edge.
    _add_label(title, x0 - 0.5, y1 + 1.0, accent)


def _build_ramp_puzzle(builder, index, name):
    """Draw one blank, labelled ramp-puzzle cell: floor + amber border + header."""
    x0, y0, x1, y1 = _ramp_puzzle_bounds(index)
    _draw_floor(builder, x0, y0, x1, y1)
    _draw_border(builder, x0, y0, x1, y1, "Workshop_Border_RampPuzzles",
                 RAMP_ACCENT)
    # Header sits in the gap just above the cell's far (high-Y) edge.
    _add_label(name, x0 - 0.5, y1 + 0.6, RAMP_ACCENT, size=1.1)


def build_ramp_puzzle_area():
    """Draw the ramps-only puzzle area: one labelled cell per RAMP_PUZZLES name."""
    builder = _GuideMeshBuilder("WS_Guide_RampPuzzles")
    for index, name in enumerate(RAMP_PUZZLES):
        _build_ramp_puzzle(builder, index, name)
    _link_guide(builder)
    # A big banner above the whole area so it reads as "ramps only".
    _, _, _, top_y = _ramp_puzzle_bounds(len(RAMP_PUZZLES) - 1)
    _add_label("RAMP PUZZLES (ramps only)",
               RAMP_AREA_ORIGIN_X - 0.5, top_y + 3.0, RAMP_ACCENT, size=2.2)


def _build_ramp_wall_puzzle(builder, index):
    """Draw one blank, labelled ramps+walls variation cell: floor + border + tag."""
    shape, letter, _col, _row = RAMP_WALL_CELLS[index]
    x0, y0, x1, y1 = _ramp_wall_bounds(index)
    _draw_floor(builder, x0, y0, x1, y1)
    _draw_border(builder, x0, y0, x1, y1, "Workshop_Border_RampWalls",
                 RAMP_WALL_ACCENT)
    # Header sits in the gap just above the cell's far (high-Y) edge.
    _add_label("%s %s" % (shape, letter),
               x0 - 0.5, y1 + 0.6, RAMP_WALL_ACCENT, size=1.1)


def build_ramp_wall_area():
    """Draw the ramps+walls area: lettered variation cells per ramp shape."""
    builder = _GuideMeshBuilder("WS_Guide_RampWalls")
    for index in range(len(RAMP_WALL_CELLS)):
        _build_ramp_wall_puzzle(builder, index)
    _link_guide(builder)
    # A big banner above the whole area so it reads as "ramps + walls".
    _, _, _, top_y = _ramp_wall_bounds(len(RAMP_WALL_CELLS) - 1)
    _add_label("RAMPS + WALLS (lettered variations)",
               RAMP_WALL_AREA_ORIGIN_X - 0.5, top_y + 3.0,
               RAMP_WALL_ACCENT, size=2.2)


def _ramp_wall_button_bounds(index):
    """Inclusive tile bounds (x0, y0, x1, y1) for the ramps+walls+buttons cell.

    One row per ramps+walls (shape, letter) piece; each row's numbered
    variations run left->right. Cells match the source ramps+walls cell size
    (honouring any per-cell override) and are spaced by RAMP_CELL_GAP.
    """
    shape, letter, _number, col, row = RAMP_WALL_BUTTON_CELLS[index]
    stride = RAMP_WALL_BUTTON_CELL + RAMP_CELL_GAP
    x0 = RAMP_WALL_BUTTON_AREA_ORIGIN_X + col * stride
    y0 = RAMP_WALL_BUTTON_AREA_ORIGIN_Y + row * stride
    size = _ramp_wall_button_cell_size(shape, letter)
    x1 = x0 + size - 1
    y1 = y0 + size - 1
    return x0, y0, x1, y1


def _build_ramp_wall_button_puzzle(builder, index):
    """Draw one blank, labelled ramps+walls+buttons numbered cell."""
    shape, letter, number, _col, _row = RAMP_WALL_BUTTON_CELLS[index]
    x0, y0, x1, y1 = _ramp_wall_button_bounds(index)
    _draw_floor(builder, x0, y0, x1, y1)
    _draw_border(builder, x0, y0, x1, y1, "Workshop_Border_RampWallButtons",
                 RAMP_WALL_BUTTON_ACCENT)
    # Header sits in the gap just above the cell's far (high-Y) edge.
    _add_label("%s %s %d" % (shape, letter, number),
               x0 - 0.5, y1 + 0.6, RAMP_WALL_BUTTON_ACCENT, size=1.0)


def build_ramp_wall_button_area():
    """Draw the ramps+walls+buttons area: numbered cells per ramps+walls piece."""
    builder = _GuideMeshBuilder("WS_Guide_RampWallButtons")
    for index in range(len(RAMP_WALL_BUTTON_CELLS)):
        _build_ramp_wall_button_puzzle(builder, index)
    _link_guide(builder)
    # A big banner above the whole area so it reads as "ramps + walls + buttons".
    _, _, _, top_y = _ramp_wall_button_bounds(len(RAMP_WALL_BUTTON_CELLS) - 1)
    _add_label("RAMPS + WALLS + BUTTONS (numbered 1-%d)"
               % RAMP_WALL_BUTTON_VARIATIONS,
               RAMP_WALL_BUTTON_AREA_ORIGIN_X - 0.5, top_y + 3.0,
               RAMP_WALL_BUTTON_ACCENT, size=2.2)


def build_blender_workshop():
    """Clear and rebuild the blank workshop: workbench zones + ramp area +
    ramps+walls area.

    No example pieces are placed -- only the empty, labelled guide areas.
    """
    clear_workshop()
    get_workshop_collection()
    zones_builder = _GuideMeshBuilder("WS_Guide_WorkbenchZones")
    for index, title in enumerate(ZONES):
        _build_zone(zones_builder, index, title)
    _link_guide(zones_builder)
    build_ramp_puzzle_area()
    build_ramp_wall_area()
    build_ramp_wall_button_area()
    print("[Workshop] Built blank '%s': %d workbench zones (X=%d) + "
          "%d ramp puzzles (X=%d) + %d ramps+walls cells (X=%d) + "
          "%d ramps+walls+buttons cells (X=%d)." % (
              COLLECTION_NAME, len(ZONES), WORKSHOP_ORIGIN_X,
              len(RAMP_PUZZLES), RAMP_AREA_ORIGIN_X,
              len(RAMP_WALL_CELLS), RAMP_WALL_AREA_ORIGIN_X,
              len(RAMP_WALL_BUTTON_CELLS), RAMP_WALL_BUTTON_AREA_ORIGIN_X))

    # Pieces follow their squares: adopt any pre-home-tag pieces where they
    # stand, then pull every tagged piece onto its square's current location
    # (a no-op unless an area was relocated since the last run).
    tagged = tag_untagged_components()
    moved = sync_components_to_layout()
    if tagged or moved:
        print("[Workshop] Home tags: %d piece(s) newly tagged, %d moved to "
              "their square's current location." % (tagged, moved))


# ===========================================================================
# PART 3 -- Easy component placement panel (mirrors snaked_tools.py)
# ===========================================================================
#
# Adds a "Snaked Workshop" tab to the 3D viewport sidebar (press N) so you can
# drop floor / block / wall / ramp / button components straight into a chosen
# workbench zone -- no guessing absolute coords out at X=40. You pick a zone and
# a col/row inside it (or just click "Place at 3D Cursor"), exactly the kind of
# point-and-click flow snaked_tools.py gives the main grid.
#
# Placed components live in their OWN collection (Puzzle_Workshop_Components),
# so re-running this script to rebuild the guide zones never deletes them.

WORKSHOP_COMPONENTS_COLLECTION = "Puzzle_Workshop_Components"
WORKSHOP_LIBRARY_COLLECTION = "Puzzle_Workshop_Library"

# Master-asset object names, one per component kind (kept distinct from
# snaked_tools' masters so the two scripts never collide).
WS_MASTER_NAMES = {
    "FLOOR": "WS_Master_Floor",
    "BLOCK": "WS_Master_Block",
    "WALL": "WS_Master_Wall",
    "RAMP": "WS_Master_Ramp",
    "BUTTON": "WS_Master_Button",
}

# Button geometry (matches snaked_tools / button.py).
WS_BUTTON_RADIUS = 0.3
WS_BUTTON_HEIGHT = 0.15
WS_TILE_TOP = 0.5   # half a tile above centre -- the tile's top face


# ---------------------------------------------------------------------------
# Placement collections
# ---------------------------------------------------------------------------

def _get_or_create_collection(name, hide_viewport=False):
    """Return a scene collection with the given name, creating it if needed."""
    import bpy
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    coll.hide_viewport = hide_viewport
    return coll


def _link_to_collection(obj, coll):
    """Unlink an object from every collection it is in, then link it to `coll`."""
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)


# ---------------------------------------------------------------------------
# Master / placeholder geometry (built once, hidden in the asset library)
# ---------------------------------------------------------------------------

def _ws_build_floor_master(name):
    """Thin 1x1 plate centred on the tile -- a flat floor marker."""
    import bpy
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.0))
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (1.0, 1.0, 0.1)
    _apply_material(obj, "WS_FloorMat", (0.45, 0.47, 0.50))   # grey
    return obj


def _ws_build_block_master(name):
    """Solid 1x1x1 cube centred on the tile (matches the grid's centred boxes)."""
    import bpy
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.0))
    obj = bpy.context.active_object
    obj.name = name
    _apply_material(obj, "WS_BlockMat", (0.30, 0.55, 0.85))   # blue
    return obj


def _ws_build_wall_master(name):
    """Solid 1x1x1 cube, darker than a block, to read as an impassable wall."""
    import bpy
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.0))
    obj = bpy.context.active_object
    obj.name = name
    _apply_material(obj, "WS_WallMat", (0.22, 0.24, 0.28))   # dark slate
    return obj


def _ws_build_button_master(name):
    """Small flat cylinder; origin at its centre so it can rest on a tile top."""
    import bpy
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=24, radius=WS_BUTTON_RADIUS, depth=WS_BUTTON_HEIGHT,
        location=(0.0, 0.0, 0.0),
    )
    obj = bpy.context.active_object
    obj.name = name
    _apply_material(obj, "WS_ButtonMat", (0.90, 0.20, 0.20))   # red
    return obj


def _ws_build_ramp_master(name):
    """Sloped wedge filling one tile (+-0.5 on every axis), rising toward +Y.

    Built with bmesh (Blender has no primitive wedge), centred on the origin to
    match the centred-box convention. Identical shape to snaked_tools' ramp.
    """
    import bpy
    import bmesh
    h = 0.5
    verts = [
        (-h, -h, -h),  # 0 low edge, -X
        ( h, -h, -h),  # 1 low edge, +X
        ( h,  h, -h),  # 2 high edge base, +X
        (-h,  h, -h),  # 3 high edge base, -X
        ( h,  h,  h),  # 4 high edge top, +X
        (-h,  h,  h),  # 5 high edge top, -X
    ]
    faces = [
        (0, 1, 2, 3),  # bottom
        (2, 4, 5, 3),  # vertical wall (+Y)
        (0, 3, 5),     # left triangle (-X)
        (1, 4, 2),     # right triangle (+X)
        (0, 5, 4, 1),  # sloped top surface
    ]
    mesh = bpy.data.meshes.new("WS_RampMesh")
    bm = bmesh.new()
    bverts = [bm.verts.new(v) for v in verts]
    for f in faces:
        bm.faces.new([bverts[i] for i in f])
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    _apply_material(obj, "WS_RampMat", (0.95, 0.75, 0.15))   # amber
    return obj


_WS_MASTER_BUILDERS = {
    "FLOOR": _ws_build_floor_master,
    "BLOCK": _ws_build_block_master,
    "WALL": _ws_build_wall_master,
    "RAMP": _ws_build_ramp_master,
    "BUTTON": _ws_build_button_master,
}


def _ensure_workshop_master(kind):
    """Return the master object for a kind, building a hidden placeholder once."""
    import bpy
    name = WS_MASTER_NAMES[kind]
    master = bpy.data.objects.get(name)
    if master is None:
        master = _WS_MASTER_BUILDERS[kind](name)
        library = _get_or_create_collection(WORKSHOP_LIBRARY_COLLECTION,
                                            hide_viewport=True)
        _link_to_collection(master, library)
    return master


def _workshop_placement_z(kind, layer, on_solid=False):
    """World Z for a placed component's origin.

    Buttons are overlays: when a tile-filling solid (block/wall/ramp) occupies
    the cell the button rests on that tile's top face (`on_solid`); otherwise it
    sits flush on the layer's floor (so a layer-0 button is level with the
    ground, not floating at cube-top height).
    """
    z = float(layer)
    if kind == "BUTTON":
        z += WS_BUTTON_HEIGHT / 2.0
        if on_solid:
            z += WS_TILE_TOP
    return z


# ---------------------------------------------------------------------------
# Place / erase (only ever touch the components collection)
# ---------------------------------------------------------------------------

def _ws_component_name(kind, x, y, layer, rotation, name_id):
    """Build the canonical object name for a placed component."""
    if kind == "BUTTON":
        return "WS_Button_%s_x%d_y%d_z%d" % (name_id or "A", x, y, layer)
    if kind == "RAMP":
        return "WS_Ramp_x%d_y%d_z%d_rot%d" % (x, y, layer, rotation)
    return "WS_%s_x%d_y%d_z%d" % (kind.title(), x, y, layer)


def _iter_workshop_components_at(x, y, layer):
    """Yield placed component objects sitting at the given grid cell."""
    import bpy
    coll = bpy.data.collections.get(WORKSHOP_COMPONENTS_COLLECTION)
    if coll is None:
        return
    for obj in list(coll.objects):
        if (obj.get("snaked_x") == x
                and obj.get("snaked_y") == y
                and obj.get("snaked_z") == layer):
            yield obj


# Tile-filling solids: a button placed on such a cell rests on the tile's top.
_SOLID_KINDS = {"BLOCK", "WALL", "RAMP"}


def _solid_at(x, y, layer):
    """True if a tile-filling solid (block/wall/ramp) occupies the cell."""
    for obj in _iter_workshop_components_at(x, y, layer):
        if obj.get("snaked_component") in _SOLID_KINDS:
            return True
    return False


def erase_workshop_component(x, y, layer, only_kinds=None):
    """Remove placed component(s) at the cell. Guide zones and masters are never
    touched -- we only look inside the components collection and only remove
    objects tagged as placed components.

    With `only_kinds` given, removes just components of those kinds, so a button
    overlay and the solid beneath it can be replaced independently. With no
    filter (the Erase tool) every component at the cell is removed.
    """
    import bpy
    removed = 0
    for obj in _iter_workshop_components_at(x, y, layer):
        if "snaked_component" not in obj:
            continue   # safety: never remove anything we did not place
        if only_kinds is not None and obj["snaked_component"] not in only_kinds:
            continue
        mesh = obj.data if obj.type == 'MESH' else None
        bpy.data.objects.remove(obj, do_unlink=True)
        # Mesh data is shared with the master, so it normally survives; only
        # remove it if it has become an orphan.
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        removed += 1
    return removed


def place_workshop_component(kind, x, y, layer, rotation=0, name_id=""):
    """Place a component as a linked-duplicate of its master asset.

    Any existing component at the same cell is erased first so placement
    overwrites cleanly (same behaviour as snaked_tools).
    """
    import bpy
    import math

    if kind == "BUTTON":
        # Buttons are overlays -- only replace an existing button, never the
        # solid/floor they sit on (so a button on a square keeps the square).
        erase_workshop_component(x, y, layer, only_kinds={"BUTTON"})
    else:
        # Tile-filling components are mutually exclusive; replace any other
        # solid/floor but keep a button overlay sitting on this cell.
        erase_workshop_component(
            x, y, layer, only_kinds={"FLOOR", "BLOCK", "WALL", "RAMP"})

    master = _ensure_workshop_master(kind)
    obj = bpy.data.objects.new(
        _ws_component_name(kind, x, y, layer, rotation, name_id),
        master.data,                 # shares the master mesh (linked duplicate)
    )
    obj.location = (float(x), float(y),
                    _workshop_placement_z(kind, layer,
                                          on_solid=_solid_at(x, y, layer)))
    obj.rotation_euler = (0.0, 0.0, math.radians(rotation))

    # Tag so erase can find it and never confuse it with a guide or a master.
    obj["snaked_component"] = kind
    obj["snaked_x"] = x
    obj["snaked_y"] = y
    obj["snaked_z"] = layer
    # Home tag: which area square this piece lives in (and where inside it),
    # so the piece follows its square if that area is ever relocated.
    _tag_home(obj, x, y)
    # Ramps carry a facing; record it so a captured piece can be rotated/mirrored
    # later without having to read it back off rotation_euler.
    if kind == "RAMP":
        obj["snaked_rot"] = rotation
    if kind == "BUTTON":
        obj["snaked_id"] = name_id

    coll = _get_or_create_collection(WORKSHOP_COMPONENTS_COLLECTION)
    coll.objects.link(obj)

    # If we just placed a solid beneath an existing button overlay, lift that
    # button onto the new tile's top so it isn't left buried inside the solid.
    if kind in _SOLID_KINDS:
        for b in _iter_workshop_components_at(x, y, layer):
            if b is not obj and b.get("snaked_component") == "BUTTON":
                b.location.z = _workshop_placement_z(
                    "BUTTON", layer, on_solid=True)

    return obj


def _area_cell_to_world(area, zone_index, ramp_index, ramp_wall_index, col, row,
                        ramp_wall_button_index=0):
    """Map an (area, target, col, row) address to absolute grid (x, y).

    `area` is "RAMP" (a named ramp-puzzle cell), "RAMPWALL" (a lettered
    ramps+walls variation cell), "RAMPWALLBUTTON" (a numbered ramps+walls+buttons
    cell), or anything else (a workbench zone). col runs along +X, row along +Y,
    both clamped into the chosen cell so you can never place outside its border.
    """
    if area == "RAMP":
        x0, y0, x1, y1 = _ramp_puzzle_bounds(ramp_index)
    elif area == "RAMPWALL":
        x0, y0, x1, y1 = _ramp_wall_bounds(ramp_wall_index)
    elif area == "RAMPWALLBUTTON":
        x0, y0, x1, y1 = _ramp_wall_button_bounds(ramp_wall_button_index)
    else:
        x0, y0, x1, y1 = _zone_bounds(zone_index)
    x = min(max(x0 + col, x0), x1)
    y = min(max(y0 + row, y0), y1)
    return x, y


# ---------------------------------------------------------------------------
# Home cells: pieces follow their square when an area is relocated
# ---------------------------------------------------------------------------
# Every placed component is stamped with a "home" -- which area, which cell in
# it, and where inside that cell it sits. Positions are then derived, so if an
# area's ORIGIN constants change, re-running the script (rebuild) moves every
# piece along with its square via sync_components_to_layout(). Pieces placed
# outside any square get no home and never move.

# Area id -> (cell bounds function, cell count function).
_AREA_BOUNDS = {
    "WORKBENCH": (_zone_bounds, lambda: len(ZONES)),
    "RAMP": (_ramp_puzzle_bounds, lambda: len(RAMP_PUZZLES)),
    "RAMPWALL": (_ramp_wall_bounds, lambda: len(RAMP_WALL_CELLS)),
    "RAMPWALLBUTTON": (_ramp_wall_button_bounds,
                       lambda: len(RAMP_WALL_BUTTON_CELLS)),
}


def _locate_cell(x, y):
    """(area, cell_index, dx, dy) of the cell containing tile (x, y), or None.

    dx/dy are the tile's offset from the cell's low (bottom-left) corner. Only
    meaningful while the layout matches the pieces on the ground -- i.e. tag at
    placement time (or once, before any area is moved), never after a move.
    """
    for area, (bounds_fn, count_fn) in _AREA_BOUNDS.items():
        for index in range(count_fn()):
            x0, y0, x1, y1 = bounds_fn(index)
            if x0 <= x <= x1 and y0 <= y <= y1:
                return area, index, x - x0, y - y0
    return None


def _tag_home(obj, x, y):
    """Stamp a component with the area square it sits in (no-op outside all)."""
    home = _locate_cell(x, y)
    if home is None:
        return False
    obj["snaked_area"], obj["snaked_cell"] = home[0], home[1]
    obj["snaked_dx"], obj["snaked_dy"] = home[2], home[3]
    return True


def tag_untagged_components():
    """Give every placed component that lacks one a home tag, from where it
    currently sits. Returns the number of components newly tagged.

    Pieces placed before home tags existed are adopted here -- which is only
    correct while their positions still match the current layout, so this runs
    on every rebuild: BEFORE an area is moved everything gets tagged; after a
    move, everything already has its tag and this is a no-op.
    """
    import bpy
    coll = bpy.data.collections.get(WORKSHOP_COMPONENTS_COLLECTION)
    tagged = 0
    if coll is None:
        return tagged
    for obj in coll.objects:
        if "snaked_component" not in obj or "snaked_area" in obj:
            continue
        x, y = obj.get("snaked_x"), obj.get("snaked_y")
        if x is None or y is None:
            continue
        if _tag_home(obj, x, y):
            tagged += 1
    return tagged


def sync_components_to_layout():
    """Move every home-tagged component to its square's CURRENT location.

    A pure origin move translates the whole square's contents intact; if a
    cell also shrank, offsets are clamped inside its new bounds. Layer (Z) is
    untouched. Returns the number of components moved.
    """
    import bpy
    coll = bpy.data.collections.get(WORKSHOP_COMPONENTS_COLLECTION)
    moved = 0
    if coll is None:
        return moved
    for obj in coll.objects:
        if "snaked_component" not in obj or "snaked_area" not in obj:
            continue
        entry = _AREA_BOUNDS.get(obj["snaked_area"])
        if entry is None:
            continue
        bounds_fn, count_fn = entry
        index = int(obj.get("snaked_cell", 0))
        if not (0 <= index < count_fn()):
            continue
        x0, y0, x1, y1 = bounds_fn(index)
        x = min(x0 + int(obj.get("snaked_dx", 0)), x1)
        y = min(y0 + int(obj.get("snaked_dy", 0)), y1)
        if x == obj.get("snaked_x") and y == obj.get("snaked_y"):
            continue
        obj["snaked_x"], obj["snaked_y"] = x, y
        obj.location.x, obj.location.y = float(x), float(y)
        moved += 1
    return moved


# ===========================================================================
# PART 3b -- Hidden interior-face culling (delete faces where pieces meet)
# ===========================================================================
#
# Placed components are linked duplicates that all SHARE their master mesh, and
# the masters are full cubes / wedges. So wherever two pieces sit flush against
# each other the touching faces still exist -- they are just hidden inside the
# join. This pass deletes those interior faces ("makes them null") so a finished
# piece has no buried geometry.
#
# Two pieces only count as "fitting together" on a side when the NEIGHBOUR fully
# covers that side with a flat square face. Full-cover faces are:
#   * BLOCK / WALL  -- all six sides (they fill the whole tile cube).
#   * RAMP          -- its flat bottom (-Z) and its single vertical back wall.
# A ramp's two sloped/triangular sides are NOT full covers, so a face is only
# removed when we are certain it is completely buried. Floors and buttons are
# thin/small and never fill a tile, so they take no part (neither hide nor are
# hidden). Because instances share the master mesh, each affected object's mesh
# is made single-user first, so the shared master is never altered.

# The six axis-aligned grid directions (unit steps) a face can point along.
_AXIS_DIRS = (
    (1, 0, 0), (-1, 0, 0),
    (0, 1, 0), (0, -1, 0),
    (0, 0, 1), (0, 0, -1),
)

# Component kinds that have buried faces worth removing when they fit together.
_CULLABLE_KINDS = {"BLOCK", "WALL", "RAMP"}


def _snap_axis(vec):
    """Snap a (world-space) vector to the grid axis it points along.

    Returns one of `_AXIS_DIRS`, or None if `vec` is not clearly axis-aligned
    (e.g. a ramp's sloped top, whose normal is diagonal) so such faces are never
    mistaken for a flat side and are left in place.
    """
    if vec.length == 0.0:
        return None
    vec = vec.normalized()
    best, best_dot = None, 0.9   # require a near-exact axis match
    for d in _AXIS_DIRS:
        dot = vec.x * d[0] + vec.y * d[1] + vec.z * d[2]
        if dot > best_dot:
            best, best_dot = d, dot
    return best


def _full_cover_world_dirs(obj):
    """World directions in which `obj` presents a full, flat square face.

    These are the directions in which the component can completely hide a
    neighbour's facing side (and have its own side hidden in return).
    """
    import mathutils
    kind = obj.get("snaked_component")
    if kind in {"BLOCK", "WALL"}:
        return set(_AXIS_DIRS)
    if kind == "RAMP":
        # The wedge's only flat square faces are its bottom (-Z) and its
        # vertical back wall (local +Y, rotated into world by the ramp facing).
        dirs = {(0, 0, -1)}
        rot = obj.matrix_world.to_3x3()
        wall = _snap_axis(rot @ mathutils.Vector((0.0, 1.0, 0.0)))
        if wall is not None:
            dirs.add(wall)
        return dirs
    return set()


def _occupancy_map():
    """Map (x, y, layer) -> placed component object, for the components area.

    Only ever reads the workshop COMPONENTS collection and only objects we
    tagged on placement, so guide geometry and masters are never considered.
    """
    import bpy
    occ = {}
    coll = bpy.data.collections.get(WORKSHOP_COMPONENTS_COLLECTION)
    if coll is None:
        return occ
    for obj in coll.objects:
        if "snaked_component" not in obj:
            continue
        if obj["snaked_component"] == "BUTTON":
            continue   # overlays never hide a face nor are hidden -- skip them
        key = (obj.get("snaked_x"), obj.get("snaked_y"), obj.get("snaked_z"))
        if None in key:
            continue
        occ[key] = obj
    return occ


def cull_hidden_faces():
    """Delete buried faces wherever placed blocks/walls/ramps fit together.

    Returns (components_changed, faces_removed). Safe to re-run: a second pass
    finds nothing new. Use restore_full_faces() to put the geometry back.
    """
    import bmesh
    occ = _occupancy_map()
    # Pre-compute each cell's full-cover directions once.
    cover = {key: _full_cover_world_dirs(obj) for key, obj in occ.items()}

    changed, removed = 0, 0
    for (x, y, z), obj in occ.items():
        if obj.get("snaked_component") not in _CULLABLE_KINDS:
            continue
        if obj.type != 'MESH':
            continue

        # Which of this cell's six sides are fully covered by a neighbour?
        culled_dirs = set()
        for d in _AXIS_DIRS:
            ncover = cover.get((x + d[0], y + d[1], z + d[2]))
            if ncover and (-d[0], -d[1], -d[2]) in ncover:
                culled_dirs.add(d)
        if not culled_dirs:
            continue

        # Make the mesh single-user so we never edit the shared master.
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        me = obj.data
        rot = obj.matrix_world.to_3x3()

        bm = bmesh.new()
        bm.from_mesh(me)
        to_del = [f for f in bm.faces
                  if _snap_axis(rot @ f.normal) in culled_dirs]
        if to_del:
            bmesh.ops.delete(bm, geom=to_del, context='FACES')
            removed += len(to_del)
            changed += 1
        bm.to_mesh(me)
        bm.free()
        me.update()

    return changed, removed


def restore_full_faces():
    """Re-link placed blocks/walls/ramps back to their full master meshes.

    Reverses cull_hidden_faces(): every culled component shares the intact
    master mesh again and its orphaned trimmed mesh is freed. Returns the number
    of components restored.
    """
    import bpy
    restored = 0
    for obj in _occupancy_map().values():
        kind = obj.get("snaked_component")
        if kind not in _CULLABLE_KINDS or obj.type != 'MESH':
            continue
        master = bpy.data.objects.get(WS_MASTER_NAMES.get(kind, ""))
        if master is None or master.data is obj.data:
            continue   # no master, or already on the full mesh
        old = obj.data
        obj.data = master.data
        if old.users == 0:
            bpy.data.meshes.remove(old)
        restored += 1
    return restored


# ===========================================================================
# PART 4 -- Ramp-puzzle orientation generator (Blender capture + layout)
# ===========================================================================
#
# Captures an authored ramp puzzle, generates its curated orientations, lays
# them out in the "RAMP ORIENTATIONS" area, and saves a piece JSON each.
# Layout objects live in their own collection (Puzzle_Workshop_Orientations) so
# regenerating only ever rebuilds that area -- the authored source puzzles in
# Puzzle_Workshop_Components are never touched.


def _capture_cell_components(x0, y0, x1, y1):
    """Capture tagged components whose tile falls in [x0,x1]x[y0,y1].

    Reads the components we placed (snaked_x/y/z), returning them with (x, y)
    made relative to the cell's low corner so they can be transformed and
    re-stamped anywhere.
    """
    import bpy
    import math
    coll = bpy.data.collections.get(WORKSHOP_COMPONENTS_COLLECTION)
    comps = []
    if coll is None:
        return comps
    for obj in coll.objects:
        if "snaked_component" not in obj:
            continue
        ox = obj.get("snaked_x")
        oy = obj.get("snaked_y")
        oz = obj.get("snaked_z")
        if ox is None or oy is None:
            continue
        if not (x0 <= ox <= x1 and y0 <= oy <= y1):
            continue
        rrot = obj.get("snaked_rot")
        if rrot is None:   # older placements: read facing back off the object
            rrot = int(round(math.degrees(obj.rotation_euler.z)))
        comps.append({
            "kind": obj["snaked_component"],
            "x": int(ox - x0),
            "y": int(oy - y0),
            "layer": int(oz) if oz is not None else 0,
            "rotation": int(rrot) % 360,
            "id": obj.get("snaked_id", ""),
        })
    return comps


def _capture_ramp_puzzle(index):
    """Capture the components inside a ramp-puzzle cell as cell-relative dicts."""
    x0, y0, x1, y1 = _ramp_puzzle_bounds(index)
    return _capture_cell_components(x0, y0, x1, y1)


def _capture_ramp_wall_cell(index):
    """Capture the components inside a ramps+walls cell as cell-relative dicts."""
    x0, y0, x1, y1 = _ramp_wall_bounds(index)
    return _capture_cell_components(x0, y0, x1, y1)


def clear_orientations(shape=None):
    """Remove generated orientation objects (all, or just one shape's row).

    Stamped components share the hidden master meshes (users > 0) so those
    survive; only the per-cell guide/label data we created is freed.
    """
    import bpy
    coll = bpy.data.collections.get(WORKSHOP_ORIENTATIONS_COLLECTION)
    if coll is None:
        return
    for obj in list(coll.objects):
        if shape is not None and obj.get("snaked_orient_shape") != shape:
            continue
        data = obj.data if obj.type in {'MESH', 'FONT'} else None
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Curve):
                bpy.data.curves.remove(data)


def _orient_border(builder, x0, y0, x1, y1):
    """Add an amber frame around one orientation cell to the guide builder."""
    t, z = 0.08, 0.04
    x_lo, x_hi = x0 - 0.5, x1 + 0.5
    y_lo, y_hi = y0 - 0.5, y1 + 0.5
    x_span = (x_hi - x_lo) + t
    y_span = (y_hi - y_lo) + t
    xc = (x_lo + x_hi) / 2.0
    yc = (y_lo + y_hi) / 2.0
    edges = (
        ((xc, y_lo, z), (x_span, t, t)),
        ((xc, y_hi, z), (x_span, t, t)),
        ((x_lo, yc, z), (t, y_span, t)),
        ((x_hi, yc, z), (t, y_span, t)),
    )
    for loc, size in edges:
        builder.add_box(loc, size, "Workshop_OrientBorder", RAMP_ACCENT)


def _orient_label(coll, shape, text, x, y, size=1.0):
    """A flat floor label linked to the orientations collection."""
    import bpy
    curve = bpy.data.curves.new(type='FONT', name="OrientFont")
    curve.body = text
    curve.size = size
    curve.align_x = 'LEFT'
    curve.align_y = 'BOTTOM'
    curve.resolution_u = 3   # signage: readable at a fraction of the geometry
    obj = bpy.data.objects.new("OrientLabel_" + text.replace(" ", "_"), curve)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = (float(x), float(y), 0.05)
    _link_to_collection(obj, coll)
    _apply_material(obj, "Workshop_LabelMat", RAMP_ACCENT)
    obj.hide_select = True
    obj["snaked_orient_shape"] = shape
    return obj


def _orient_stamp(coll, shape, kind, x, y, layer, rotation, name_id,
                  on_solid=False):
    """Stamp one component (linked dup of its master) into the orientations area."""
    import bpy
    import math
    master = _ensure_workshop_master(kind)
    obj = bpy.data.objects.new(
        "WS_Orient_%s_%s_x%d_y%d_z%d_r%d"
        % (shape.replace(" ", "_"), kind.title(), x, y, layer, rotation),
        master.data,
    )
    obj.location = (float(x), float(y),
                    _workshop_placement_z(kind, layer, on_solid=on_solid))
    obj.rotation_euler = (0.0, 0.0, math.radians(rotation))
    obj["snaked_orient_shape"] = shape
    obj["snaked_orientation"] = kind
    if kind == "BUTTON" and name_id:
        obj["snaked_id"] = name_id
    coll.objects.link(obj)
    return obj


def _ensure_orient_banner(coll):
    """Create the one-time area banner above the orientations grid (idempotent)."""
    import bpy
    name = "OrientLabel_RAMP_ORIENTATIONS"
    if bpy.data.objects.get(name) is not None:
        return
    stride = RAMP_CELL + RAMP_CELL_GAP
    top_y = RAMP_ORIENT_AREA_ORIGIN_Y + len(RAMP_PUZZLES) * stride + 1
    obj = _orient_label(coll, "__banner__", "RAMP ORIENTATIONS (generated)",
                        RAMP_ORIENT_AREA_ORIGIN_X - 0.5, top_y, size=2.2)
    obj.name = name


def generate_ramp_puzzle_orientations(shape, components, root):
    """Lay out + save every curated orientation for one ramp puzzle.

    `components` is the cell-relative capture from _capture_ramp_puzzle. Each
    shape keeps a stable row (its index in RAMP_PUZZLES); orientations run
    left->right across that row. Returns the number of orientations produced.
    """
    coll = _get_or_create_collection(WORKSHOP_ORIENTATIONS_COLLECTION)
    clear_orientations(shape)          # rebuild just this shape's row
    _ensure_orient_banner(coll)

    row = RAMP_PUZZLES.index(shape)
    orients = _orientations_for(shape)
    fid = _family_id_for(shape)
    base_meta = _orientation_meta(orients[0][0], orients[0][1], 0)
    base_id = "%s_%s" % (fid, base_meta["tag"])

    stride = RAMP_CELL + RAMP_CELL_GAP
    y0 = RAMP_ORIENT_AREA_ORIGIN_Y + row * stride

    # Shape name to the left of its row of orientation cells.
    _orient_label(coll, shape, shape,
                  RAMP_ORIENT_AREA_ORIGIN_X - 6.0, y0 + 0.5, size=1.3)

    # All of this row's cell borders merge into ONE guide mesh object, tagged
    # with the shape so clear_orientations(shape) still removes just this row.
    guide = _GuideMeshBuilder(
        "WS_OrientGuide_%s" % shape.replace(" ", "_"))

    pieces = []
    for col, (rotation, mirrored) in enumerate(orients):
        meta = _orientation_meta(rotation, mirrored, col)
        variant = _transform_piece(components, rotation, mirrored)

        x0 = RAMP_ORIENT_AREA_ORIGIN_X + col * stride
        x1, y1 = x0 + RAMP_CELL - 1, y0 + RAMP_CELL - 1
        _orient_border(guide, x0, y0, x1, y1)
        _orient_label(coll, shape, "%s %s" % (shape, meta["label"]),
                      x0 - 0.5, y1 + 0.6, size=1.0)

        # Cells filled by a solid, so any button stamped there rests on top.
        solid_cells = {(c["x"], c["y"], c.get("layer", 0)) for c in variant
                       if c["kind"] in _SOLID_KINDS}
        for c in variant:
            on_solid = (c["x"], c["y"], c.get("layer", 0)) in solid_cells
            _orient_stamp(coll, shape, c["kind"],
                          x0 + c["x"], y0 + c["y"], c.get("layer", 0),
                          c.get("rotation", 0), c.get("id", ""),
                          on_solid=on_solid)

        pid = "%s_%s" % (fid, meta["tag"])
        pieces.append(_build_piece_dict(pid, fid, shape, meta, variant, base_id))

    guide_obj = guide.build()
    guide_obj.hide_select = True
    guide_obj["snaked_orient_shape"] = shape
    _link_to_collection(guide_obj, coll)

    variation_ids = [p["id"] for p in pieces if not p["is_base_piece"]]
    family = _build_family_dict(fid, shape, base_id, variation_ids)
    _write_family_files(root, fid, family, pieces)
    _register_pieces_in_index(root, family, pieces)
    return len(pieces)


# ---------------------------------------------------------------------------
# Seed the Ramps+Walls variation cells from the authored ramp puzzles
# ---------------------------------------------------------------------------
# Each lettered ramps+walls cell (e.g. "Fish a", "Cube b") is pre-filled in its
# centre with that shape's authored ramp puzzle -- ramps and blocks only, in the
# original orientation -- so you only have to add the walls per variation. The
# filled components are placed as normal, tagged workshop components, so the
# regular Place / Erase tools can edit them afterwards.

# Component kinds the fill copies from a ramp puzzle (you add the rest by hand).
_FILL_KINDS = {"RAMP", "BLOCK"}


def _ramps_and_blocks(components):
    """Keep only the ramp/block components from a captured piece."""
    return [c for c in components if c.get("kind") in _FILL_KINDS]


def fill_ramp_wall_cell(index, components):
    """Place `components` inside the ramps+walls cell at `index`.

    `components` are cell-relative ramp/block dicts (from a ramp-puzzle capture).
    They are normalised to their own bounding box and centred horizontally in the
    cell, then placed as standard, editable workshop components. Standard cells
    centre the piece vertically too; oversized (overridden) cells anchor it to the
    bottom instead, so the cell's extra height becomes clear rows on top -- room
    to add walls above the piece. Returns the count placed.
    """
    base = _transform_piece(components, 0, False)   # normalise, original facing
    if not base:
        return 0
    shape, letter, _col, _row = RAMP_WALL_CELLS[index]
    x0, y0, _x1, _y1 = _ramp_wall_bounds(index)
    size = _ramp_wall_cell_size(shape, letter)
    w, h, _layers = _piece_grid_size(base)
    ox = max(0, (size - w) // 2)
    # Oversized cells: anchor to the bottom so the spare rows land on top.
    is_oversized = (shape, letter) in RAMP_WALL_CELL_OVERRIDES
    oy = 0 if is_oversized else max(0, (size - h) // 2)
    for c in base:
        place_workshop_component(
            c["kind"], x0 + ox + c["x"], y0 + oy + c["y"], c.get("layer", 0),
            rotation=c.get("rotation", 0), name_id=c.get("id", ""),
        )
    return len(base)


def fill_ramp_wall_cells_from_ramps():
    """Seed every ramps+walls cell with its shape's authored ramp puzzle.

    Captures each ramp puzzle once (ramps + blocks, original orientation) and
    stamps it into the centre of every lettered cell for that shape. Returns
    (cells_filled, [shapes_skipped]) -- a shape is skipped when its ramp puzzle
    has not been authored yet.
    """
    cache = {}
    filled = 0
    skipped = set()
    for index, (shape, _letter, _col, _row) in enumerate(RAMP_WALL_CELLS):
        if shape not in cache:
            cache[shape] = _ramps_and_blocks(
                _capture_ramp_puzzle(RAMP_PUZZLES.index(shape)))
        comps = cache[shape]
        if not comps:
            skipped.add(shape)
            continue
        fill_ramp_wall_cell(index, comps)
        filled += 1
    return filled, sorted(skipped)


def fill_ramp_wall_button_cell(index, components):
    """Place `components` inside the ramps+walls+buttons cell at `index`.

    Mirrors fill_ramp_wall_cell: normalise to the piece bbox, centre it in the
    cell (oversized cells anchor to the bottom so spare rows land on top), and
    place as standard, editable workshop components. Returns the count placed.
    """
    base = _transform_piece(components, 0, False)   # normalise, original facing
    if not base:
        return 0
    shape, letter, _number, _col, _row = RAMP_WALL_BUTTON_CELLS[index]
    x0, y0, _x1, _y1 = _ramp_wall_button_bounds(index)
    size = _ramp_wall_button_cell_size(shape, letter)
    w, h, _layers = _piece_grid_size(base)
    ox = max(0, (size - w) // 2)
    is_oversized = (shape, letter) in RAMP_WALL_CELL_OVERRIDES
    oy = 0 if is_oversized else max(0, (size - h) // 2)
    for c in base:
        place_workshop_component(
            c["kind"], x0 + ox + c["x"], y0 + oy + c["y"], c.get("layer", 0),
            rotation=c.get("rotation", 0), name_id=c.get("id", ""),
        )
    return len(base)


def fill_ramp_wall_button_cells_from_ramp_walls():
    """Import every ramps+walls piece into its numbered button cells.

    Captures each ramps+walls cell once (all components, original orientation)
    and stamps it into all RAMP_WALL_BUTTON_VARIATIONS numbered cells for that
    (shape, letter). Empty sources are left blank so you can delete the empties
    later. Returns (cells_filled, [(shape, letter), ...] for empty sources).
    """
    cache = {}
    filled = 0
    empty = set()
    for index, (shape, letter, _num, _col, _row) in enumerate(RAMP_WALL_BUTTON_CELLS):
        key = (shape, letter)
        if key not in cache:
            cache[key] = _capture_ramp_wall_cell(_RAMP_WALL_INDEX_BY_KEY[key])
        comps = cache[key]
        if not comps:
            empty.add(key)
            continue
        fill_ramp_wall_button_cell(index, comps)
        filled += 1
    return filled, sorted(empty)


# ---------------------------------------------------------------------------
# UI: properties, operators, panel (only defined when bpy is importable)
# ---------------------------------------------------------------------------

try:
    import bpy as _bpy
except Exception:   # pragma: no cover -- running outside Blender
    _bpy = None


if _bpy is not None:

    _ZONE_ITEMS = [
        (str(i), title, "Place into the '%s' zone" % title)
        for i, title in enumerate(ZONES)
    ]

    _RAMP_PUZZLE_ITEMS = [
        (str(i), name, "Place into the '%s' ramp puzzle" % name)
        for i, name in enumerate(RAMP_PUZZLES)
    ]

    _RAMP_WALL_ITEMS = [
        (str(i), "%s %s" % (shape, letter),
         "Place into the '%s %s' ramps+walls variation" % (shape, letter))
        for i, (shape, letter, _col, _row) in enumerate(RAMP_WALL_CELLS)
    ]

    _RAMP_WALL_BUTTON_ITEMS = [
        (str(i), "%s %s %d" % (shape, letter, number),
         "Place into the '%s %s %d' ramps+walls+buttons variation"
         % (shape, letter, number))
        for i, (shape, letter, number, _col, _row)
        in enumerate(RAMP_WALL_BUTTON_CELLS)
    ]

    class PuzzleWorkshopToolsProps(_bpy.types.PropertyGroup):
        area: _bpy.props.EnumProperty(
            name="Area",
            description="Where to place: the workbench zones or the ramp puzzles",
            items=[
                ("WORKBENCH", "Workbench Zones",
                 "The four general authoring zones (any component)"),
                ("RAMP", "Ramp Puzzles",
                 "The ramps-only puzzle area (always places Ramps)"),
                ("RAMPWALL", "Ramps + Walls",
                 "The ramps+walls variation area (places Ramps or Walls)"),
                ("RAMPWALLBUTTON", "Ramps + Walls + Buttons",
                 "The numbered ramps+walls+buttons area (add Buttons per "
                 "variation)"),
            ],
            default="WORKBENCH",
        )
        zone: _bpy.props.EnumProperty(
            name="Zone",
            description="Which workbench zone to place into",
            items=_ZONE_ITEMS,
            default="0",
        )
        ramp_puzzle: _bpy.props.EnumProperty(
            name="Puzzle",
            description="Which named ramp puzzle to place into",
            items=_RAMP_PUZZLE_ITEMS,
            default="0",
        )
        ramp_wall_puzzle: _bpy.props.EnumProperty(
            name="Variation",
            description="Which ramps+walls variation cell to place into",
            items=_RAMP_WALL_ITEMS,
            default="0",
        )
        ramp_wall_button_puzzle: _bpy.props.EnumProperty(
            name="Numbered",
            description="Which ramps+walls+buttons numbered cell to place into",
            items=_RAMP_WALL_BUTTON_ITEMS,
            default="0",
        )
        component: _bpy.props.EnumProperty(
            name="Component",
            description="What to place (or Erase to remove)",
            items=[
                ("FLOOR", "Floor", "Flat floor tile"),
                ("BLOCK", "Block", "Solid cube that fills one tile"),
                ("WALL", "Wall", "Impassable wall cube"),
                ("RAMP", "Ramp", "Sloped wedge showing direction"),
                ("BUTTON", "Button", "Small flat button on top of a tile"),
                ("ERASE", "Erase", "Remove a placed component at the cell"),
            ],
            default="FLOOR",
        )
        col: _bpy.props.IntProperty(
            name="Col", description="Column within the zone (along X)",
            default=0, min=0, max=ZONE_WIDTH - 1,
        )
        row: _bpy.props.IntProperty(
            name="Row", description="Row within the zone (along Y)",
            default=0, min=0, max=ZONE_HEIGHT - 1,
        )
        layer: _bpy.props.IntProperty(
            name="Layer", description="Layer number (Z height)",
            default=0, min=0, max=8,
        )
        rotation: _bpy.props.EnumProperty(
            name="Rotation",
            description="Z rotation in degrees (used by Ramp direction)",
            items=[("0", "0", ""), ("90", "90", ""),
                   ("180", "180", ""), ("270", "270", "")],
            default="0",
        )
        name_id: _bpy.props.StringProperty(
            name="ID / Name",
            description="ID for buttons and linked objects",
            default="A",
        )
        orient_shape: _bpy.props.EnumProperty(
            name="Ramp Puzzle",
            description="Which authored ramp puzzle to generate orientations for",
            items=_RAMP_PUZZLE_ITEMS,
            default="0",
        )
        orient_all: _bpy.props.BoolProperty(
            name="All ramp puzzles",
            description="Generate orientations for every authored ramp puzzle",
            default=False,
        )

    def _do_place(self, context, x, y, force_kind=None):
        p = context.scene.puzzle_workshop_tools
        layer = p.layer
        rotation = int(p.rotation)

        if p.component == "ERASE":
            removed = erase_workshop_component(x, y, layer)
            if removed:
                self.report({'INFO'}, "Erased %d component(s) at (%d, %d, L%d)."
                            % (removed, x, y, layer))
            else:
                self.report({'WARNING'}, "Nothing to erase at (%d, %d, L%d)."
                            % (x, y, layer))
            return {'FINISHED'}

        # The ramp area forces ramps for most picks; Blocks (fundamental) and
        # Erase pass through unforced so they can be placed anywhere.
        kind = force_kind if force_kind else p.component

        if kind == "BUTTON" and not p.name_id.strip():
            self.report({'ERROR'}, "Buttons need an ID / Name.")
            return {'CANCELLED'}

        obj = place_workshop_component(
            kind, x, y, layer,
            rotation=rotation, name_id=p.name_id.strip(),
        )
        self.report({'INFO'}, "Placed %s." % obj.name)
        return {'FINISHED'}

    class PUZZLE_OT_place(_bpy.types.Operator):
        """Place (or erase) at the chosen workbench-zone or ramp-puzzle cell."""
        bl_idname = "puzzle_workshop.place"
        bl_label = "Place"
        bl_options = {'REGISTER', 'UNDO'}

        def execute(self, context):
            p = context.scene.puzzle_workshop_tools
            x, y = _area_cell_to_world(
                p.area, int(p.zone), int(p.ramp_puzzle),
                int(p.ramp_wall_puzzle), p.col, p.row,
                ramp_wall_button_index=int(p.ramp_wall_button_puzzle))
            # The ramp area defaults to ramps, but Blocks are fundamental and
            # may go anywhere, so they (and Erase) are never forced to a ramp.
            force = ("RAMP" if p.area == "RAMP"
                     and p.component not in {"BLOCK", "ERASE"} else None)
            return _do_place(self, context, x, y, force_kind=force)

    class PUZZLE_OT_place_cursor(_bpy.types.Operator):
        """Place the selected component at the nearest tile under the 3D cursor.

        The quickest flow: point the 3D cursor in the viewport, then click here.
        """
        bl_idname = "puzzle_workshop.place_cursor"
        bl_label = "Place at 3D Cursor"
        bl_options = {'REGISTER', 'UNDO'}

        def execute(self, context):
            cur = context.scene.cursor.location
            x, y = int(round(cur.x)), int(round(cur.y))
            # Snap the layer too, then sync the panel so the values are visible.
            layer = max(0, int(round(cur.z)))
            context.scene.puzzle_workshop_tools.layer = layer
            return _do_place(self, context, x, y)

    class PUZZLE_OT_generate_orientations(_bpy.types.Operator):
        """Generate curated rotated/mirrored orientations for ramp puzzles.

        Captures each chosen ramp puzzle's authored cell, lays its orientations
        out in the "RAMP ORIENTATIONS" area, and saves a piece JSON per
        orientation under snaked_assets/puzzle_pieces/.
        """
        bl_idname = "puzzle_workshop.generate_orientations"
        bl_label = "Generate Orientations"
        bl_options = {'REGISTER', 'UNDO'}

        def execute(self, context):
            p = context.scene.puzzle_workshop_tools
            root = resolve_project_root()
            if p.orient_all:
                shapes = list(RAMP_PUZZLES)
            else:
                shapes = [RAMP_PUZZLES[int(p.orient_shape)]]

            total, done, empty = 0, 0, []
            for shape in shapes:
                comps = _capture_ramp_puzzle(RAMP_PUZZLES.index(shape))
                if not comps:
                    empty.append(shape)
                    continue
                total += generate_ramp_puzzle_orientations(shape, comps, root)
                done += 1

            if done == 0:
                self.report({'WARNING'},
                            "No components found in the selected ramp puzzle(s). "
                            "Author a ramp puzzle first (Area > Ramp Puzzles), "
                            "then generate.")
                return {'CANCELLED'}
            msg = ("Generated %d orientation(s) across %d ramp puzzle(s) at X=%d."
                   % (total, done, RAMP_ORIENT_AREA_ORIGIN_X))
            if empty:
                msg += " Skipped (empty): %s." % ", ".join(empty)
            self.report({'INFO'}, msg)
            return {'FINISHED'}

    class PUZZLE_OT_fill_variations(_bpy.types.Operator):
        """Seed every Ramps+Walls cell with its shape's authored ramp puzzle.

        Centres each ramp puzzle (ramps + blocks, original orientation) inside
        every lettered variation cell for that shape, so you only need to add
        the walls per variation afterwards.
        """
        bl_idname = "puzzle_workshop.fill_variations"
        bl_label = "Fill Variation Centres"
        bl_options = {'REGISTER', 'UNDO'}

        def execute(self, context):
            filled, skipped = fill_ramp_wall_cells_from_ramps()
            if filled == 0:
                self.report({'WARNING'},
                            "No authored ramp puzzles to fill from. Author them "
                            "in the Ramp Puzzles area first, then fill.")
                return {'CANCELLED'}
            msg = ("Filled %d ramps+walls cell(s) from ramp puzzles "
                   "(ramps + blocks, original orientation)." % filled)
            if skipped:
                msg += " No source yet for: %s." % ", ".join(skipped)
            self.report({'INFO'}, msg)
            return {'FINISHED'}

    class PUZZLE_OT_fill_button_variations(_bpy.types.Operator):
        """Import every Ramps+Walls piece into its numbered button cells.

        Captures each ramps+walls cell (all components, original orientation)
        and stamps it into every numbered cell for that piece, so you only
        need to add the buttons per numbered variation afterwards. Empty
        ramps+walls sources are left blank (delete the empties later).
        """
        bl_idname = "puzzle_workshop.fill_button_variations"
        bl_label = "Import Ramps+Walls (x%d)" % RAMP_WALL_BUTTON_VARIATIONS
        bl_options = {'REGISTER', 'UNDO'}

        def execute(self, context):
            filled, empty = fill_ramp_wall_button_cells_from_ramp_walls()
            if filled == 0:
                self.report({'WARNING'},
                            "No authored ramps+walls pieces to import from. "
                            "Fill the Ramps+Walls area first, then import.")
                return {'CANCELLED'}
            msg = ("Imported %d ramps+walls+buttons cell(s) from ramps+walls "
                   "pieces (numbered 1-%d per piece)."
                   % (filled, RAMP_WALL_BUTTON_VARIATIONS))
            if empty:
                msg += " Empty source (left blank): %s." % ", ".join(
                    "%s %s" % (s, l) for s, l in empty)
            self.report({'INFO'}, msg)
            return {'FINISHED'}

    class PUZZLE_OT_cull_hidden(_bpy.types.Operator):
        """Delete buried faces where placed blocks/walls/ramps fit together.

        Hidden interior faces (the ones you can't see because a neighbouring
        piece sits flush against them) are removed. Only touches placed
        components; the shared master meshes are never altered.
        """
        bl_idname = "puzzle_workshop.cull_hidden"
        bl_label = "Cull Hidden Faces"
        bl_options = {'REGISTER', 'UNDO'}

        def execute(self, context):
            changed, removed = cull_hidden_faces()
            if changed == 0:
                self.report({'INFO'},
                            "No hidden interior faces to cull (nothing fits "
                            "flush yet, or already culled).")
            else:
                self.report({'INFO'},
                            "Culled %d hidden face(s) across %d component(s)."
                            % (removed, changed))
            return {'FINISHED'}

    class PUZZLE_OT_restore_faces(_bpy.types.Operator):
        """Restore full geometry on placed blocks/walls/ramps (undo culling)."""
        bl_idname = "puzzle_workshop.restore_faces"
        bl_label = "Restore Full Faces"
        bl_options = {'REGISTER', 'UNDO'}

        def execute(self, context):
            n = restore_full_faces()
            self.report({'INFO'},
                        "Restored full faces on %d component(s)." % n)
            return {'FINISHED'}

    class PUZZLE_PT_tools(_bpy.types.Panel):
        bl_label = "Snaked Workshop"
        bl_idname = "PUZZLE_PT_tools"
        bl_space_type = 'VIEW_3D'
        bl_region_type = 'UI'
        bl_category = "Snaked Workshop"

        def draw(self, context):
            layout = self.layout
            p = context.scene.puzzle_workshop_tools

            layout.prop(p, "area")

            is_ramp_area = p.area == "RAMP"
            is_ramp_wall_area = p.area == "RAMPWALL"
            is_ramp_wall_button_area = p.area == "RAMPWALLBUTTON"
            if is_ramp_area:
                layout.prop(p, "ramp_puzzle")
                # Ramp area: Blocks (fundamental) and Erase pass through; any
                # other pick is placed as a Ramp. Keep the picker usable.
                layout.prop(p, "component")
                layout.label(text="Blocks/Erase anywhere; else places a Ramp.",
                             icon='INFO')
            elif is_ramp_wall_area:
                layout.prop(p, "ramp_wall_puzzle")
                # Ramps+walls area: never forced -- the component picker decides,
                # so Ramps and Walls can sit side by side in the same variation.
                layout.prop(p, "component")
                layout.label(text="Places the chosen component (Ramp or Wall).",
                             icon='INFO')
            elif is_ramp_wall_button_area:
                layout.prop(p, "ramp_wall_button_puzzle")
                # Ramps+walls+buttons area: never forced -- typically you add
                # Buttons here on top of the imported ramps+walls piece.
                layout.prop(p, "component")
                layout.label(text="Places the chosen component (usually Button).",
                             icon='INFO')
            else:
                layout.prop(p, "zone")
                layout.prop(p, "component")

            col = layout.column(align=True)
            col.prop(p, "col")
            col.prop(p, "row")
            col.prop(p, "layer")

            is_erase = p.component == "ERASE"
            # Rotation matters for ramps (always, in the ramp area) and for a
            # ramp component elsewhere.
            row = layout.row()
            row.enabled = is_ramp_area or (p.component == "RAMP")
            row.prop(p, "rotation", expand=True)

            row = layout.row()
            row.enabled = (not is_ramp_area) and p.component == "BUTTON"
            row.prop(p, "name_id")

            if is_erase:
                label = "Erase"
            elif is_ramp_area and p.component == "BLOCK":
                label = "Place Block"
            elif is_ramp_area:
                label = "Place Ramp"
            else:
                label = "Place %s" % p.component.title()
            layout.operator(PUZZLE_OT_place.bl_idname, text=label,
                            icon='X' if is_erase else 'ADD')
            layout.operator(PUZZLE_OT_place_cursor.bl_idname, icon='CURSOR')

            # --- Ramp-puzzle orientation generator -----------------------
            layout.separator()
            box = layout.box()
            box.label(text="Ramp Puzzle Orientations", icon='MOD_MIRROR')
            box.prop(p, "orient_all")
            sub = box.row()
            sub.enabled = not p.orient_all
            sub.prop(p, "orient_shape")
            box.operator(PUZZLE_OT_generate_orientations.bl_idname,
                         icon='FILE_REFRESH')

            # --- Seed Ramps+Walls cells from the ramp puzzles ------------
            box2 = layout.box()
            box2.label(text="Fill Variation Cells", icon='PASTEDOWN')
            box2.label(text="Centres each Ramps+Walls cell with its ramp "
                            "puzzle (ramps + blocks).", icon='INFO')
            box2.operator(PUZZLE_OT_fill_variations.bl_idname, icon='PASTEDOWN')

            # --- Import Ramps+Walls pieces into the numbered button cells ---
            box2b = layout.box()
            box2b.label(text="Fill Button Variation Cells", icon='PASTEDOWN')
            box2b.label(text="Imports each Ramps+Walls piece into its %d "
                             "numbered button cells."
                             % RAMP_WALL_BUTTON_VARIATIONS, icon='INFO')
            box2b.operator(PUZZLE_OT_fill_button_variations.bl_idname,
                           icon='PASTEDOWN')

            # --- Optimise geometry: delete buried interior faces ----------
            box3 = layout.box()
            box3.label(text="Optimise Geometry", icon='MOD_DECIM')
            box3.label(text="Delete hidden faces where blocks/walls/ramps "
                            "fit together.", icon='INFO')
            box3.operator(PUZZLE_OT_cull_hidden.bl_idname, icon='MESH_DATA')
            box3.operator(PUZZLE_OT_restore_faces.bl_idname, icon='FILE_REFRESH')

    _tool_classes = (
        PuzzleWorkshopToolsProps,
        PUZZLE_OT_place,
        PUZZLE_OT_place_cursor,
        PUZZLE_OT_generate_orientations,
        PUZZLE_OT_fill_variations,
        PUZZLE_OT_fill_button_variations,
        PUZZLE_OT_cull_hidden,
        PUZZLE_OT_restore_faces,
        PUZZLE_PT_tools,
    )

    def register_tools():
        """Register the placement panel (idempotent: clears a prior load first)."""
        try:
            unregister_tools()
        except Exception:
            pass
        for cls in _tool_classes:
            _bpy.utils.register_class(cls)
        _bpy.types.Scene.puzzle_workshop_tools = _bpy.props.PointerProperty(
            type=PuzzleWorkshopToolsProps)

    def unregister_tools():
        if hasattr(_bpy.types.Scene, "puzzle_workshop_tools"):
            del _bpy.types.Scene.puzzle_workshop_tools
        for cls in reversed(_tool_classes):
            try:
                _bpy.utils.unregister_class(cls)
            except Exception:
                pass

else:   # outside Blender: PART 1 (scaffold) still works; tools are a no-op.
    def register_tools():
        pass

    def unregister_tools():
        pass


# ===========================================================================
# Entry point
# ===========================================================================

def build():
    """Create the on-disk scaffold, then (inside Blender) the blank workshop
    and the 'Snaked Workshop' placement panel."""
    setup_project_files()
    try:
        import bpy  # noqa: F401  -- only present inside Blender
    except ImportError:
        print("[Workshop] bpy not available -- created project files only. "
              "Run inside Blender to also build the 3D workshop.")
        return
    build_blender_workshop()
    register_tools()
    print("[Workshop] 'Snaked Workshop' placement panel registered "
          "(3D viewport sidebar > Snaked Workshop).")


if __name__ == "__main__":
    # Re-running in the Text Editor: clear a previous panel load first.
    try:
        unregister_tools()
    except Exception:
        pass
    build()
