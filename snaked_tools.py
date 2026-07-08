


"""
snaked_tools.py

A simplified map-editor sidebar panel for the game "Snaked".

This sits *next to* snaked_map_builder.py (which draws the 22x40x4 grid) and
never touches the grid. It adds a "Snaked Tools" panel to the 3D viewport
sidebar (press N) that lets you drop and erase a small set of gameplay
components on the grid.

It is also the LEVEL ASSEMBLER: the panel's "Pieces" box stamps saved puzzle
pieces (JSON captured in the workshop) onto the grid, and the "Levels" box
saves / loads the whole grid to levels/world_NN/level_MMM/level.json. The main
grid holds ONE level at a time: Save serializes what is placed, Load clears
the grid and rebuilds it from the file.

Conventions (shared with snaked_map_builder.py)
-----------------------------------------------
- 1 Blender unit == 1 tile.
- X and Y are the grid position; tile centres sit on integer world coords
  (X: 1..22, Y: 1..40).
- Z (height) equals the layer number; layer L's grid plane is at z = L.

Collections
-----------
- Placed components go into "Snaked_Components".
- Master/placeholder assets live in "Snaked_Asset_Library" (hidden in the
  viewport). Placed components are linked-duplicates of these masters.
- The grid's own collection ("Snaked_Map") is never modified.

Usage
-----
Run this from Blender's Text Editor (Alt+P) or via the command line:
    blender --python snaked_tools.py
Then open the 3D viewport sidebar (N) and pick the "Snaked Tools" tab.
"""

import os
import sys
import json

import bpy


def _ensure_repo_on_path():
    """Put this repo's folder on sys.path so `import snaked_common` works no
    matter how the script is run (module import, blender --python, or the
    Text Editor's Alt+P on a saved file)."""
    dirs = []
    try:
        dirs.append(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        pass
    try:
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
# Configuration  (grid dimensions live in snaked_common -- shared with
# snaked_map_builder so the two can never drift apart)
# ---------------------------------------------------------------------------

GRID_WIDTH = sc.GRID_WIDTH       # tiles along X
GRID_HEIGHT = sc.GRID_HEIGHT     # tiles along Y
NUM_LAYERS = sc.NUM_LAYERS       # 1 floor + 3 obstacle layers
LAYER_HEIGHT = sc.LAYER_HEIGHT   # Z distance between layers (1 unit == 1 tile)

COMPONENTS_COLLECTION = "Snaked_Components"
LIBRARY_COLLECTION = "Snaked_Asset_Library"

# Master-asset object names, one per component kind. FLOOR and WALL exist so
# workshop-authored pieces (which may contain them) can be stamped onto the
# main grid; they follow the workshop's look.
MASTER_NAMES = {
    "FLOOR": "Master_Floor",
    "BLOCK": "Master_Block",
    "WALL": "Master_Wall",
    "BUTTON": "Master_Button",
    "RAMP": "Master_Ramp",
}


# ---------------------------------------------------------------------------
# Collection / material helpers (shared: see snaked_common)
# ---------------------------------------------------------------------------

_get_or_create_collection = sc.get_or_create_collection
_link_to_collection = sc.link_to_collection


# ---------------------------------------------------------------------------
# Master / placeholder asset geometry (shared builders: see snaked_common)
# ---------------------------------------------------------------------------
# Placement convention matches snaked_map_builder.py: like the grid's boxes,
# every master is modelled *centred on its origin* (x = y = 0, and centred in
# z too). A tile at layer L occupies the cell centred on z = L, so a placed
# block/ramp fills z in [L-0.5, L+0.5] exactly like a grid box centred at z = L.
# Buttons follow the original button.py and rest on the tile's top face.

BUTTON_RADIUS = sc.BUTTON_RADIUS
BUTTON_HEIGHT = sc.BUTTON_HEIGHT
TILE_TOP = sc.TILE_TOP   # half a tile above the centre -- the tile's top face

# Shared geometry, this script's material names/colours.
_MASTER_BUILDERS = {
    "FLOOR": lambda name: sc.build_floor_master(
        name, "Snaked_FloorMat", (0.45, 0.47, 0.50)),    # grey
    "BLOCK": lambda name: sc.build_cube_master(
        name, "Snaked_BlockMat", (0.30, 0.55, 0.85)),    # blue
    "WALL": lambda name: sc.build_cube_master(
        name, "Snaked_WallMat", (0.22, 0.24, 0.28)),     # dark slate
    "BUTTON": lambda name: sc.build_button_master(
        name, "Snaked_ButtonMat", (0.90, 0.20, 0.20)),   # red
    "RAMP": lambda name: sc.build_ramp_master(
        name, "Snaked_RampMat", (0.95, 0.75, 0.15),      # amber
        mesh_name="Snaked_RampMesh"),
}


def _ensure_master(kind):
    """Return the master object for a component kind, building a placeholder
    (geometry + material) in the hidden asset library if it does not exist yet."""
    name = MASTER_NAMES[kind]
    master = bpy.data.objects.get(name)
    if master is None:
        master = _MASTER_BUILDERS[kind](name)
        library = _get_or_create_collection(LIBRARY_COLLECTION, hide_viewport=True)
        _link_to_collection(master, library)
    return master


def _placement_z(kind, layer, on_solid=False):
    """World Z for a placed component's origin (see snaked_common.placement_z)."""
    return sc.placement_z(kind, layer, on_solid=on_solid,
                          layer_height=LAYER_HEIGHT)


# ---------------------------------------------------------------------------
# Placement / erase
# ---------------------------------------------------------------------------

def _component_name(kind, x, y, layer, rotation, name_id):
    """Build the canonical object name for a placed component."""
    if kind == "RAMP":
        return "Ramp_x%d_y%d_z%d_rot%d" % (x, y, layer, rotation)
    if kind == "BUTTON":
        return "Button_%s_x%d_y%d_z%d" % (name_id, x, y, layer)
    return "%s_x%d_y%d_z%d" % (kind.title(), x, y, layer)


# Tile-filling solids: a button placed on such a cell rests on the tile's top.
# (FLOOR is thin and never counts as solid, matching the workshop.)
_SOLID_KINDS = sc.SOLID_KINDS


class _ComponentIndex(sc.ComponentIndex):
    """Occupancy index over the main grid's components collection.

    See snaked_common.ComponentIndex: build one per operation (or one per
    batch, e.g. stamping a whole piece or loading a level) so each cell query
    is a dict lookup instead of a scan of the whole components collection.
    """

    def __init__(self):
        super().__init__(COMPONENTS_COLLECTION)


def erase_component(x, y, layer, only_kinds=None, occ=None):
    """Remove placed component(s) at the cell. Grid and masters are never
    touched -- the occupancy index only ever contains objects tagged as placed
    components, so nothing else can be removed.

    With `only_kinds` given, removes just components of those kinds, so a button
    overlay and the solid beneath it can be replaced independently. With no
    filter (the Erase tool) every component at the cell is removed.

    `occ` is an optional shared _ComponentIndex: batch callers build one index
    up front and pass it through so each erase is a dict lookup instead of a
    full collection scan. Without it a fresh index is built for this call.
    """
    if occ is None:
        occ = _ComponentIndex()
    removed = 0
    for obj in occ.at(x, y, layer):
        if only_kinds is not None and obj["snaked_component"] not in only_kinds:
            continue
        occ.discard(obj)
        # Mesh data shared with the master survives; orphans are freed.
        sc.remove_object_with_orphan_data(obj)
        removed += 1
    return removed


def place_component(kind, x, y, layer, rotation=0, name_id="", occ=None,
                    piece_tag=""):
    """Place a component as a linked-duplicate of its master asset.

    Any existing component already at the same cell is erased first so that
    placement overwrites cleanly.

    `occ` is an optional shared _ComponentIndex (see erase_component): batch
    callers pass one so every cell query here is a dict lookup; the index is
    kept up to date as this function erases and places. `piece_tag` records
    which saved puzzle piece stamped this component (kept through level
    save/load so pieces_used can be tracked).
    """
    import math

    if occ is None:
        occ = _ComponentIndex()

    if kind == "BUTTON":
        # Buttons are overlays -- only replace an existing button, never the
        # solid they sit on (so a button on a block keeps the block).
        erase_component(x, y, layer, only_kinds={"BUTTON"}, occ=occ)
    else:
        # Tile-filling components are mutually exclusive; replace any other
        # solid/floor but keep a button overlay sitting on this cell.
        erase_component(x, y, layer,
                        only_kinds={"FLOOR", "BLOCK", "WALL", "RAMP"}, occ=occ)

    master = _ensure_master(kind)
    obj = bpy.data.objects.new(
        _component_name(kind, x, y, layer, rotation, name_id),
        master.data,                 # shares the master mesh (linked duplicate)
    )

    obj.location = (float(x), float(y),
                    _placement_z(kind, layer, on_solid=occ.solid_at(x, y, layer)))
    obj.rotation_euler = (0.0, 0.0, math.radians(rotation))

    # Tag the placement so erase can find it and never confuse it with a
    # grid object or a master asset.
    obj["snaked_component"] = kind
    obj["snaked_x"] = x
    obj["snaked_y"] = y
    obj["snaked_z"] = layer
    if kind == "RAMP":
        obj["snaked_rot"] = rotation   # facing, for clean serialization
    if kind == "BUTTON":
        obj["snaked_id"] = name_id
    if piece_tag:
        obj["snaked_piece"] = piece_tag

    components = _get_or_create_collection(COMPONENTS_COLLECTION)
    components.objects.link(obj)
    occ.add(obj)   # after tagging: the index keys off the snaked_* properties

    # If we just placed a solid beneath an existing button overlay, lift that
    # button onto the new tile's top so it isn't left buried inside the solid.
    if kind in _SOLID_KINDS:
        for b in occ.at(x, y, layer):
            if b is not obj and b.get("snaked_component") == "BUTTON":
                b.location.z = _placement_z("BUTTON", layer, on_solid=True)

    return obj


# ---------------------------------------------------------------------------
# Project root / piece catalog
# ---------------------------------------------------------------------------
# Root resolution is shared (snaked_common), so every script agrees on where
# Snaked_Project lives.

resolve_project_root = sc.resolve_project_root


def load_piece_catalog(root=None):
    """{piece_id: piece dict} read from ai_data/all_puzzle_pieces.json.

    The index holds every saved piece in full (components included), so this
    one file is all the assembler needs. Returns {} when nothing is saved yet.
    """
    root = root or resolve_project_root()
    path = os.path.join(root, "ai_data", "all_puzzle_pieces.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {p["id"]: p for p in data.get("pieces", []) if p.get("id")}


# ---------------------------------------------------------------------------
# Piece placement (the assembler half of the workshop's orientation maths)
# ---------------------------------------------------------------------------
# The transform is snaked_common.transform_piece -- the SAME function the
# workshop's orientation generator uses, so a piece rotated here always
# matches the orientations the workshop generates.

_transform_piece = sc.transform_piece


def place_piece(piece, x, y, layer=0, rotation=0, occ=None):
    """Stamp a saved puzzle piece onto the main grid.

    `piece` is a piece dict from load_piece_catalog(). (x, y) is the grid cell
    the piece's bottom-left corner lands on after `rotation` (0/90/180/270);
    `layer` is added to every component's layer. Placement is all-or-nothing:
    if any component would fall outside the grid, nothing is placed.

    Returns (placed_count, error) -- error is None on success.
    """
    comps = [{
        "kind": (c.get("type") or "").upper(),
        "x": int(c.get("x", 0)),
        "y": int(c.get("y", 0)),
        "layer": int(c.get("layer", 0)),
        "rotation": int(c.get("rotation", 0)),
        "id": c.get("id", ""),
    } for c in piece.get("components", [])]
    comps = [c for c in comps if c["kind"] in MASTER_NAMES]
    if not comps:
        return 0, "piece has no placeable components"

    comps = _transform_piece(comps, rotation)
    for c in comps:
        gx, gy, gl = x + c["x"], y + c["y"], layer + c["layer"]
        if not (1 <= gx <= GRID_WIDTH and 1 <= gy <= GRID_HEIGHT
                and 0 <= gl < NUM_LAYERS):
            return 0, ("component would land outside the grid at "
                       "(%d, %d, L%d)" % (gx, gy, gl))

    if occ is None:
        occ = _ComponentIndex()
    # Solids first so a button is placed onto its supporting tile directly.
    comps.sort(key=lambda c: c["kind"] == "BUTTON")
    for c in comps:
        place_component(c["kind"], x + c["x"], y + c["y"], layer + c["layer"],
                        rotation=c["rotation"], name_id=c["id"], occ=occ,
                        piece_tag=piece.get("id", ""))
    return len(comps), None


# ---------------------------------------------------------------------------
# Level save / load  (level.json round-trip; the grid holds one level at a time)
# ---------------------------------------------------------------------------
# Folder + id conventions are shared with snaked_level_saver via snaked_common.

_world_folder_name = sc.world_folder_name
_level_folder_name = sc.level_folder_name
_level_id = sc.level_id


def _level_json_path(root, world_number, level_number):
    return os.path.join(root, "levels", _world_folder_name(world_number),
                        _level_folder_name(level_number), "level.json")


# Matches snaked_level_saver's template, plus the components list this script
# serializes into it.
_LEVEL_TEMPLATE = {
    "id": "",
    "name": "",
    "world": 0,
    "level_number": 0,
    "difficulty": 0,
    "grid_size": [0, 0, 0],
    "pieces_used": [],
    "start_position": [0, 0, 0],
    "start_direction": "",
    "goal_position": [0, 0, 0],
    "required_mechanics": [],
    "introduced_mechanics": [],
    "tags": [],
    "notes": "",
    "status": "draft",
    "components": [],
}


def _serialize_components():
    """The main grid's placed components as JSON-ready dicts.

    Returns (components, pieces_used). Components are sorted so a saved file
    diffs cleanly between edits.
    """
    import math
    coll = bpy.data.collections.get(COMPONENTS_COLLECTION)
    comps, pieces = [], set()
    if coll is None:
        return comps, []
    for obj in coll.objects:
        if "snaked_component" not in obj:
            continue
        x, y, z = obj.get("snaked_x"), obj.get("snaked_y"), obj.get("snaked_z")
        if None in (x, y, z):
            continue
        rot = obj.get("snaked_rot")
        if rot is None:   # older placements: read facing back off the object
            rot = int(round(math.degrees(obj.rotation_euler.z)))
        entry = {
            "type": obj["snaked_component"].lower(),
            "x": int(x), "y": int(y), "layer": int(z),
            "rotation": int(rot) % 360,
            "id": obj.get("snaked_id", ""),
        }
        piece = obj.get("snaked_piece", "")
        if piece:
            entry["piece"] = piece
            pieces.add(piece)
        comps.append(entry)
    comps.sort(key=lambda c: (c["layer"], c["y"], c["x"], c["type"]))
    return comps, sorted(pieces)


def _update_levels_index(root, meta):
    """Replace-or-add this level's entry in ai_data/all_levels.json."""
    path = os.path.join(root, "ai_data", "all_levels.json")
    data = {"version": "0.1", "levels": []}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            data = {"version": "0.1", "levels": []}
    data.setdefault("version", "0.1")
    data.setdefault("levels", [])
    entry = {
        "id": meta["id"],
        "name": meta.get("name", ""),
        "world": meta["world"],
        "level_number": meta["level_number"],
        "path": "levels/%s/%s" % (_world_folder_name(meta["world"]),
                                  _level_folder_name(meta["level_number"])),
        "status": meta.get("status", "draft"),
    }
    data["levels"] = [e for e in data["levels"]
                      if e.get("id") != meta["id"]] + [entry]
    sc.save_json(path, data)


def save_level(world, level, name=None, root=None):
    """Serialize the main grid into levels/world_NN/level_MMM/level.json.

    Unlike the scaffold scripts this OVERWRITES level.json -- it is a save
    operation -- but hand-edited metadata (difficulty, notes, tags, ...) in an
    existing file is preserved; only the identity, grid_size, components and
    pieces_used fields are refreshed. Also updates ai_data/all_levels.json.

    Returns (path, component_count).
    """
    root = root or resolve_project_root()
    path = _level_json_path(root, world, level)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    meta = dict(_LEVEL_TEMPLATE)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                meta.update(json.load(fh))
        except (OSError, ValueError):
            pass   # unreadable file: rebuild from the template

    comps, pieces_used = _serialize_components()
    meta["id"] = _level_id(world, level)
    if name:
        meta["name"] = name
    meta["world"] = int(world)
    meta["level_number"] = int(level)
    meta["grid_size"] = [GRID_WIDTH, GRID_HEIGHT, NUM_LAYERS]
    meta["components"] = comps
    meta["pieces_used"] = pieces_used

    sc.save_json(path, meta)
    _update_levels_index(root, meta)
    return path, len(comps)


def clear_components():
    """Remove every placed component from the main grid (grid guides stay)."""
    coll = bpy.data.collections.get(COMPONENTS_COLLECTION)
    removed = 0
    if coll is None:
        return removed
    for obj in list(coll.objects):
        if "snaked_component" not in obj:
            continue   # safety: never remove anything we did not place
        sc.remove_object_with_orphan_data(obj)
        removed += 1
    return removed


def load_level(world, level, root=None):
    """Clear the grid and rebuild it from level.json.

    Returns (placed_count, error) -- error is None on success.
    """
    root = root or resolve_project_root()
    path = _level_json_path(root, world, level)
    if not os.path.exists(path):
        return 0, "no level.json at %s" % path
    try:
        with open(path, "r", encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError) as exc:
        return 0, "could not read %s (%s)" % (path, exc)

    clear_components()
    occ = _ComponentIndex()
    placed = 0
    # Solids first so buttons land on their supporting tiles directly.
    comps = sorted(meta.get("components", []),
                   key=lambda c: c.get("type") == "button")
    for c in comps:
        kind = (c.get("type") or "").upper()
        if kind not in MASTER_NAMES:
            continue
        place_component(kind, int(c.get("x", 0)), int(c.get("y", 0)),
                        int(c.get("layer", 0)),
                        rotation=int(c.get("rotation", 0)),
                        name_id=c.get("id", ""), occ=occ,
                        piece_tag=c.get("piece", ""))
        placed += 1
    return placed, None


# ---------------------------------------------------------------------------
# UI: properties, operator, panel
# ---------------------------------------------------------------------------

# Piece-catalog cache for the panel's dropdown. Kept module-level on purpose:
# Blender enum callbacks must return strings that stay referenced, and the
# catalog only re-reads the JSON when Refresh is clicked (or on first use).
_piece_catalog = {}
_piece_enum_items = []


def _refresh_piece_catalog():
    """Re-read the saved-piece index; returns the number of pieces found."""
    global _piece_catalog, _piece_enum_items
    _piece_catalog = load_piece_catalog()
    _piece_enum_items = [
        (pid, p.get("name") or pid,
         p.get("category", "") or "Saved puzzle piece")
        for pid, p in sorted(_piece_catalog.items())
    ] or [("NONE", "<no pieces saved>",
           "Save pieces from the workshop first, then Refresh")]
    return len(_piece_catalog)


def _piece_items(self, context):
    if not _piece_enum_items:
        _refresh_piece_catalog()
    return _piece_enum_items


class SnakedToolsProps(bpy.types.PropertyGroup):
    component: bpy.props.EnumProperty(
        name="Component",
        description="What to place (or Erase to remove)",
        items=[
            ("FLOOR", "Floor", "Flat floor tile"),
            ("BLOCK", "Block", "Solid cube that fills one tile"),
            ("WALL", "Wall", "Impassable wall cube"),
            ("RAMP", "Ramp", "Sloped wedge showing direction"),
            ("BUTTON", "Button", "Small flat button on top of a tile"),
            ("ERASE", "Erase", "Remove a placed component at X/Y/Layer"),
        ],
        default="BLOCK",
    )
    x: bpy.props.IntProperty(
        name="X", description="Grid X position",
        default=1, min=1, max=GRID_WIDTH,
    )
    y: bpy.props.IntProperty(
        name="Y", description="Grid Y position",
        default=1, min=1, max=GRID_HEIGHT,
    )
    layer: bpy.props.IntProperty(
        name="Layer", description="Layer number (Z height)",
        default=0, min=0, max=NUM_LAYERS - 1,
    )
    rotation: bpy.props.EnumProperty(
        name="Rotation",
        description="Z rotation in degrees (used by Ramp direction)",
        items=[
            ("0", "0", ""),
            ("90", "90", ""),
            ("180", "180", ""),
            ("270", "270", ""),
        ],
        default="0",
    )
    name_id: bpy.props.StringProperty(
        name="ID / Name",
        description="ID for buttons and linked objects",
        default="A",
    )
    piece: bpy.props.EnumProperty(
        name="Piece",
        description="Saved puzzle piece to stamp onto the grid at X/Y/Layer",
        items=_piece_items,
    )
    world: bpy.props.IntProperty(
        name="World", description="World number (1-8)",
        default=1, min=1, max=8,
    )
    level: bpy.props.IntProperty(
        name="Level", description="Level number within the world",
        default=1, min=1, max=999,
    )
    level_name: bpy.props.StringProperty(
        name="Name",
        description="Human-readable level name (kept if left blank on re-save)",
        default="",
    )


class SNAKED_OT_apply(bpy.types.Operator):
    """Place the selected component (or erase) at the given grid cell."""
    bl_idname = "snaked.apply"
    bl_label = "Apply"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        p = context.scene.snaked_tools
        x, y, layer = p.x, p.y, p.layer
        rotation = int(p.rotation)

        if p.component == "ERASE":
            removed = erase_component(x, y, layer)
            if removed:
                self.report({'INFO'}, "Erased %d component(s) at (%d, %d, L%d)."
                            % (removed, x, y, layer))
            else:
                self.report({'WARNING'}, "Nothing to erase at (%d, %d, L%d)."
                            % (x, y, layer))
            return {'FINISHED'}

        if p.component == "BUTTON" and not p.name_id.strip():
            self.report({'ERROR'}, "Buttons need an ID / Name.")
            return {'CANCELLED'}

        obj = place_component(
            p.component, x, y, layer,
            rotation=rotation, name_id=p.name_id.strip(),
        )
        self.report({'INFO'}, "Placed %s." % obj.name)
        return {'FINISHED'}


class SNAKED_OT_refresh_pieces(bpy.types.Operator):
    """Re-read the saved-piece catalog (ai_data/all_puzzle_pieces.json)."""
    bl_idname = "snaked.refresh_pieces"
    bl_label = "Refresh Pieces"

    def execute(self, context):
        n = _refresh_piece_catalog()
        self.report({'INFO'}, "Piece catalog: %d piece(s)." % n)
        return {'FINISHED'}


class SNAKED_OT_place_piece(bpy.types.Operator):
    """Stamp the chosen saved piece onto the grid at X/Y/Layer.

    X/Y is the piece's bottom-left corner after rotation. All-or-nothing:
    nothing is placed if any part would fall outside the grid.
    """
    bl_idname = "snaked.place_piece"
    bl_label = "Place Piece"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        p = context.scene.snaked_tools
        piece = _piece_catalog.get(p.piece)
        if piece is None:
            self.report({'ERROR'}, "No piece selected -- save pieces in the "
                        "workshop, then Refresh.")
            return {'CANCELLED'}
        placed, err = place_piece(piece, p.x, p.y, p.layer,
                                  rotation=int(p.rotation))
        if err:
            self.report({'ERROR'}, "Not placed: %s." % err)
            return {'CANCELLED'}
        self.report({'INFO'}, "Placed piece '%s' (%d components) at (%d, %d, "
                    "L%d)." % (p.piece, placed, p.x, p.y, p.layer))
        return {'FINISHED'}


class SNAKED_OT_save_level(bpy.types.Operator):
    """Save the grid's placed components to this world/level's level.json."""
    bl_idname = "snaked.save_level"
    bl_label = "Save Level"

    def execute(self, context):
        p = context.scene.snaked_tools
        path, n = save_level(p.world, p.level,
                             name=p.level_name.strip() or None)
        self.report({'INFO'}, "Saved %d component(s) to %s" % (n, path))
        return {'FINISHED'}


class SNAKED_OT_load_level(bpy.types.Operator):
    """Clear the grid and rebuild it from this world/level's level.json."""
    bl_idname = "snaked.load_level"
    bl_label = "Load Level"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        p = context.scene.snaked_tools
        placed, err = load_level(p.world, p.level)
        if err:
            self.report({'ERROR'}, "Not loaded: %s" % err)
            return {'CANCELLED'}
        self.report({'INFO'}, "Loaded %s: %d component(s)."
                    % (_level_id(p.world, p.level), placed))
        return {'FINISHED'}


class SNAKED_OT_clear_grid(bpy.types.Operator):
    """Remove every placed component from the grid (grid guides stay)."""
    bl_idname = "snaked.clear_grid"
    bl_label = "Clear Grid"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = clear_components()
        self.report({'INFO'}, "Removed %d component(s)." % n)
        return {'FINISHED'}


class SNAKED_PT_tools(bpy.types.Panel):
    bl_label = "Snaked Tools"
    bl_idname = "SNAKED_PT_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Snaked Tools"

    def draw(self, context):
        layout = self.layout
        p = context.scene.snaked_tools

        layout.prop(p, "component")

        col = layout.column(align=True)
        col.prop(p, "x")
        col.prop(p, "y")
        col.prop(p, "layer")

        is_erase = p.component == "ERASE"
        row = layout.row()
        row.enabled = not is_erase
        row.prop(p, "rotation", expand=True)

        row = layout.row()
        row.enabled = p.component == "BUTTON"
        row.prop(p, "name_id")

        label = "Erase" if is_erase else "Place %s" % p.component.title()
        layout.operator(SNAKED_OT_apply.bl_idname, text=label,
                        icon='X' if is_erase else 'ADD')

        # --- Pieces: stamp saved workshop pieces onto the grid -----------
        layout.separator()
        box = layout.box()
        box.label(text="Pieces", icon='MOD_BUILD')
        box.prop(p, "piece")
        box.label(text="Places at X/Y/Layer above; Rotation applies.",
                  icon='INFO')
        row = box.row(align=True)
        row.operator(SNAKED_OT_place_piece.bl_idname, icon='ADD')
        row.operator(SNAKED_OT_refresh_pieces.bl_idname, text="",
                     icon='FILE_REFRESH')

        # --- Levels: save / load the grid as world_NN/level_MMM ----------
        box2 = layout.box()
        box2.label(text="Levels", icon='FILE')
        col = box2.column(align=True)
        col.prop(p, "world")
        col.prop(p, "level")
        box2.prop(p, "level_name")
        row = box2.row(align=True)
        row.operator(SNAKED_OT_save_level.bl_idname, icon='EXPORT')
        row.operator(SNAKED_OT_load_level.bl_idname, icon='IMPORT')
        box2.operator(SNAKED_OT_clear_grid.bl_idname, icon='TRASH')


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_classes = (
    SnakedToolsProps,
    SNAKED_OT_apply,
    SNAKED_OT_refresh_pieces,
    SNAKED_OT_place_piece,
    SNAKED_OT_save_level,
    SNAKED_OT_load_level,
    SNAKED_OT_clear_grid,
    SNAKED_PT_tools,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.snaked_tools = bpy.props.PointerProperty(type=SnakedToolsProps)


def unregister():
    del bpy.types.Scene.snaked_tools
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    # Re-running in the Text Editor: unregister a previous load first.
    try:
        unregister()
    except Exception:
        pass
    register()
    print("[Snaked] Snaked Tools panel registered (3D viewport sidebar > Snaked Tools).")
