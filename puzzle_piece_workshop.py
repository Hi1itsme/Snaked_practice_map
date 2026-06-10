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
    - Pick the Zone / Puzzle, then a Col / Row inside it, and a Layer (height).
    - For a Workbench Zone, also pick a Component (Floor / Block / Wall / Ramp /
      Button / Erase).
    - Click  "Place"  --  OR  point the 3D cursor in the viewport (Shift+Right
      click) and click  "Place at 3D Cursor"  for the fastest workflow.
    - Buttons need an "ID / Name"; Ramp direction uses the Rotation buttons.
    - Choose "Erase" + Place to remove the component at that cell.

Re-running the script (Alt+P again) safely reloads the panel and rebuilds the
empty zones; your placed components are kept.
"""

import os
import json

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


def _add_box(name, location, size, mat_name, color):
    """Create a box (cube) mesh with explicit per-axis dimensions, in the workshop."""
    import bpy
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size[0], size[1], size[2])
    _link_to_workshop(obj)
    _apply_material(obj, mat_name, color)
    # Guide geometry is scenery, not pieces -- keep it from getting in the way.
    obj.hide_select = True
    return obj


def _add_label(text, x, y, color, size=1.4):
    """Add a flat text label lying on the floor (readable from the top view)."""
    import bpy
    curve = bpy.data.curves.new(type='FONT', name=text + "_Font")
    curve.body = text
    curve.size = size
    curve.align_x = 'LEFT'
    curve.align_y = 'BOTTOM'

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


def _draw_floor(x0, y0, x1, y1, prefix):
    """Draw a flat grid floor over tile cells x0..x1, y0..y1 (inclusive).

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
        _add_box(
            "%s_LineY_%02d" % (prefix, i),
            location=(x_lo + i, y_center, 0.0),
            size=(line_thickness, y_span, line_thickness),
            mat_name=mat_name, color=color,
        )
    # Lines parallel to X (varying Y).
    for j in range(int(round(y_span)) + 1):
        _add_box(
            "%s_LineX_%02d" % (prefix, j),
            location=(x_center, y_lo + j, 0.0),
            size=(x_span, line_thickness, line_thickness),
            mat_name=mat_name, color=color,
        )


def _draw_border(x0, y0, x1, y1, prefix, color):
    """Draw a coloured frame around a zone so empty zones stay easy to read."""
    t = 0.08          # border thickness
    z = 0.04          # sits just above the floor lines
    x_lo, x_hi = x0 - 0.5, x1 + 0.5
    y_lo, y_hi = y0 - 0.5, y1 + 0.5
    x_span = (x_hi - x_lo) + t
    y_span = (y_hi - y_lo) + t
    x_center = (x_lo + x_hi) / 2.0
    y_center = (y_lo + y_hi) / 2.0
    mat_name = "Workshop_Border_%s" % prefix

    edges = {
        "S": ((x_center, y_lo, z), (x_span, t, t)),   # bottom
        "N": ((x_center, y_hi, z), (x_span, t, t)),   # top
        "W": ((x_lo, y_center, z), (t, y_span, t)),   # left
        "E": ((x_hi, y_center, z), (t, y_span, t)),   # right
    }
    for tag, (loc, size) in edges.items():
        _add_box("%s_Border_%s" % (prefix, tag), loc, size, mat_name, color)


def _build_zone(index, title):
    """Draw one blank, labelled zone: floor grid + coloured border + header."""
    x0, y0, x1, y1 = _zone_bounds(index)
    prefix = "Zone%d_%s" % (index, title.replace(" ", "_"))
    accent = ZONE_ACCENTS[index % len(ZONE_ACCENTS)]
    _draw_floor(x0, y0, x1, y1, prefix)
    _draw_border(x0, y0, x1, y1, prefix, accent)
    # Header sits in the gap just above the zone's far (high-Y) edge.
    _add_label(title, x0 - 0.5, y1 + 1.0, accent)


def _build_ramp_puzzle(index, name):
    """Draw one blank, labelled ramp-puzzle cell: floor + amber border + header."""
    x0, y0, x1, y1 = _ramp_puzzle_bounds(index)
    prefix = "RampPuzzle%02d_%s" % (index, name.replace(" ", "_"))
    _draw_floor(x0, y0, x1, y1, prefix)
    _draw_border(x0, y0, x1, y1, prefix, RAMP_ACCENT)
    # Header sits in the gap just above the cell's far (high-Y) edge.
    _add_label(name, x0 - 0.5, y1 + 0.6, RAMP_ACCENT, size=1.1)


def build_ramp_puzzle_area():
    """Draw the ramps-only puzzle area: one labelled cell per RAMP_PUZZLES name."""
    for index, name in enumerate(RAMP_PUZZLES):
        _build_ramp_puzzle(index, name)
    # A big banner above the whole area so it reads as "ramps only".
    _, _, _, top_y = _ramp_puzzle_bounds(len(RAMP_PUZZLES) - 1)
    _add_label("RAMP PUZZLES (ramps only)",
               RAMP_AREA_ORIGIN_X - 0.5, top_y + 3.0, RAMP_ACCENT, size=2.2)


def build_blender_workshop():
    """Clear and rebuild the blank workshop: workbench zones + ramp puzzle area.

    No example pieces are placed -- only the empty, labelled guide areas.
    """
    clear_workshop()
    get_workshop_collection()
    for index, title in enumerate(ZONES):
        _build_zone(index, title)
    build_ramp_puzzle_area()
    print("[Workshop] Built blank '%s': %d workbench zones (X=%d) + "
          "%d ramp puzzles (X=%d)." % (
              COLLECTION_NAME, len(ZONES), WORKSHOP_ORIGIN_X,
              len(RAMP_PUZZLES), RAMP_AREA_ORIGIN_X))


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


def _workshop_placement_z(kind, layer):
    """World Z for a placed component's origin (buttons sit on the tile top)."""
    z = float(layer)
    if kind == "BUTTON":
        z += WS_TILE_TOP + WS_BUTTON_HEIGHT / 2.0
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


def erase_workshop_component(x, y, layer):
    """Remove any component(s) we placed at the cell. Guide zones and masters
    are never touched -- we only look inside the components collection and only
    remove objects tagged as placed components."""
    import bpy
    removed = 0
    for obj in _iter_workshop_components_at(x, y, layer):
        if "snaked_component" not in obj:
            continue   # safety: never remove anything we did not place
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

    erase_workshop_component(x, y, layer)

    master = _ensure_workshop_master(kind)
    obj = bpy.data.objects.new(
        _ws_component_name(kind, x, y, layer, rotation, name_id),
        master.data,                 # shares the master mesh (linked duplicate)
    )
    obj.location = (float(x), float(y), _workshop_placement_z(kind, layer))
    obj.rotation_euler = (0.0, 0.0, math.radians(rotation))

    # Tag so erase can find it and never confuse it with a guide or a master.
    obj["snaked_component"] = kind
    obj["snaked_x"] = x
    obj["snaked_y"] = y
    obj["snaked_z"] = layer
    if kind == "BUTTON":
        obj["snaked_id"] = name_id

    coll = _get_or_create_collection(WORKSHOP_COMPONENTS_COLLECTION)
    coll.objects.link(obj)
    return obj


def _area_cell_to_world(area, zone_index, ramp_index, col, row):
    """Map an (area, target, col, row) address to absolute grid (x, y).

    `area` is "RAMP" (a named ramp-puzzle cell) or anything else (a workbench
    zone). col runs along +X, row along +Y, both clamped into the chosen cell so
    you can never place outside its border.
    """
    if area == "RAMP":
        x0, y0, x1, y1 = _ramp_puzzle_bounds(ramp_index)
    else:
        x0, y0, x1, y1 = _zone_bounds(zone_index)
    x = min(max(x0 + col, x0), x1)
    y = min(max(y0 + row, y0), y1)
    return x, y


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

    class PuzzleWorkshopToolsProps(_bpy.types.PropertyGroup):
        area: _bpy.props.EnumProperty(
            name="Area",
            description="Where to place: the workbench zones or the ramp puzzles",
            items=[
                ("WORKBENCH", "Workbench Zones",
                 "The four general authoring zones (any component)"),
                ("RAMP", "Ramp Puzzles",
                 "The ramps-only puzzle area (always places Ramps)"),
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
                p.area, int(p.zone), int(p.ramp_puzzle), p.col, p.row)
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
            if is_ramp_area:
                layout.prop(p, "ramp_puzzle")
                # Ramp area: Blocks (fundamental) and Erase pass through; any
                # other pick is placed as a Ramp. Keep the picker usable.
                layout.prop(p, "component")
                layout.label(text="Blocks/Erase anywhere; else places a Ramp.",
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

    _tool_classes = (
        PuzzleWorkshopToolsProps,
        PUZZLE_OT_place,
        PUZZLE_OT_place_cursor,
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
