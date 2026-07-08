"""
snaked_common.py

Shared helpers for the Snaked scripts (snaked_map_builder.py, snaked_tools.py,
snaked_level_saver.py, puzzle_piece_workshop.py).

Everything here used to live as near-identical copies inside those scripts.
Most of it was harmless duplication, but two groups were genuinely dangerous
to keep in sync by hand:

  * the piece-transform maths (xform_cell / transform_piece): the workshop's
    orientation generator and the main grid's piece assembler MUST rotate a
    piece identically, or saved orientations and stamped pieces silently
    disagree;
  * the grid configuration: the tools panel assumes the grid the map builder
    draws.

Layout of this module
---------------------
- Pure-Python helpers first (paths, naming, JSON, transforms): these run
  anywhere, including outside Blender (the scaffold halves of the level saver
  and the workshop rely on that).
- bpy-dependent helpers after (materials, collections, mesh builders,
  occupancy index): they import bpy lazily inside each function/class, so
  merely importing this module never requires Blender.

Each script makes itself importable-safe with a tiny bootstrap that puts this
file's folder on sys.path before `import snaked_common` -- so running from
the Text Editor (Alt+P on a saved file), `blender --python`, or a plain
`import` all work.
"""

import os
import json

# ---------------------------------------------------------------------------
# Shared configuration
# ---------------------------------------------------------------------------

PROJECT_DIR_NAME = "Snaked_Project"   # on-disk project root folder name

# The main grid (drawn by snaked_map_builder, edited by snaked_tools).
GRID_WIDTH = 22      # tiles along X
GRID_HEIGHT = 40     # tiles along Y
NUM_LAYERS = 4       # 1 floor + 3 obstacle layers
LAYER_HEIGHT = 1.0   # Z distance between layers (1 unit == 1 tile)

# Button geometry (master asset + placement height maths).
BUTTON_RADIUS = 0.3
BUTTON_HEIGHT = 0.15
TILE_TOP = 0.5   # half a tile above the centre -- the tile's top face

# Tile-filling solids: a button placed on such a cell rests on the tile's top.
# (FLOOR is thin and never counts as solid.)
SOLID_KINDS = {"BLOCK", "WALL", "RAMP"}


# ---------------------------------------------------------------------------
# Project root resolution (pure Python)
# ---------------------------------------------------------------------------

def base_dir():
    """Best-effort folder to anchor the project root in.

    Order of preference:
      1. The saved .blend file's folder (when running inside Blender).
      2. This module file's folder (the repo checkout).
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
    base = os.path.normpath(base_dir())
    parts = base.split(os.sep)
    if PROJECT_DIR_NAME in parts:
        idx = len(parts) - 1 - parts[::-1].index(PROJECT_DIR_NAME)
        return os.sep.join(parts[: idx + 1])
    return os.path.join(base, PROJECT_DIR_NAME)


# ---------------------------------------------------------------------------
# Level / world naming conventions (pure Python)
# ---------------------------------------------------------------------------

def world_folder_name(world_number):
    """Zero-padded world folder name, e.g. 1 -> 'world_01'."""
    return "world_%02d" % int(world_number)


def level_folder_name(level_number):
    """Zero-padded level folder name, e.g. 1 -> 'level_001'."""
    return "level_%03d" % int(level_number)


def level_id(world_number, level_number):
    """Canonical level id, e.g. (1, 1) -> 'world_01_level_001'."""
    return "%s_%s" % (world_folder_name(world_number),
                      level_folder_name(level_number))


def level_collection_name(world_number, level_number):
    """Per-level Blender collection name, e.g. (1, 1) -> 'WORLD_01_LEVEL_001'."""
    return level_id(world_number, level_number).upper()


def slug(text):
    """Filename/id-safe slug: 'Fortress 2 b' -> 'fortress_2_b'."""
    out = "".join(ch if ch.isalnum() else "_" for ch in text.strip().lower())
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")


# ---------------------------------------------------------------------------
# JSON writing (pure Python)
# ---------------------------------------------------------------------------

def save_json(path, data):
    """Write pretty JSON (+ trailing newline), creating parent folders."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


# ---------------------------------------------------------------------------
# Piece transforms (pure Python)
# ---------------------------------------------------------------------------
# The single source of truth for rotating / mirroring a piece. Used by the
# workshop's orientation generator AND the main grid's piece assembler -- the
# two must agree exactly, which is the whole reason this lives here.

def xform_cell(cx, cy, rotation, mirrored=False):
    """Transform a relative cell: mirror across X first, then rotate CCW."""
    if mirrored:
        cx = -cx
    for _ in range((rotation // 90) % 4):
        cx, cy = -cy, cx
    return cx, cy


def xform_ramp_rotation(rrot, rotation, mirrored=False):
    """Transform a ramp's facing to match a mirror-then-rotate of the piece.

    A left<->right mirror sends facing r -> (360 - r); a flat CCW rotation by
    `rotation` degrees adds that much. (Derived from the +Y-facing master at
    r = 0: mirroring keeps +Y, while +X<->-X swap, i.e. r -> -r.)
    """
    if mirrored:
        rrot = (360 - rrot) % 360
    return (rrot + rotation) % 360


def transform_piece(components, rotation, mirrored=False):
    """Return a new component list for one orientation, re-packed to (0, 0)."""
    out = []
    for c in components:
        nx, ny = xform_cell(c["x"], c["y"], rotation, mirrored)
        nc = dict(c)
        nc["x"], nc["y"] = nx, ny
        if c.get("kind") == "RAMP":
            nc["rotation"] = xform_ramp_rotation(
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


def piece_grid_size(components):
    """[width, height, layers] bounding box of a relative-coord component list."""
    if not components:
        return [0, 0, 0]
    w = max(c["x"] for c in components) + 1
    h = max(c["y"] for c in components) + 1
    layers = max(c.get("layer", 0) for c in components) + 1
    return [w, h, layers]


def placement_z(kind, layer, on_solid=False, layer_height=LAYER_HEIGHT):
    """World Z for a placed component's origin.

    Z equals the layer number (the grid plane at z = layer). Solids are
    centred on that plane like the grid's boxes. Buttons are overlays: when a
    tile-filling solid occupies the cell the button rests on that tile's top
    face (`on_solid`); otherwise it sits flush on the layer's floor.
    """
    z = layer * layer_height
    if kind == "BUTTON":
        z += BUTTON_HEIGHT / 2.0
        if on_solid:
            z += TILE_TOP
    return z


# ===========================================================================
# bpy-dependent helpers (import bpy lazily; safe to import outside Blender)
# ===========================================================================

# ---------------------------------------------------------------------------
# Materials / collections / object cleanup
# ---------------------------------------------------------------------------

def get_material(name, color):
    """Return a flat-shaded material with the given name, creating it if needed."""
    import bpy
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = False
    mat.diffuse_color = (color[0], color[1], color[2], 1.0)
    return mat


def apply_material(obj, name, color):
    """Apply a single flat-shaded material to an object."""
    mat = get_material(name, color)
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def get_or_create_collection(name, hide_viewport=False):
    """Return a scene collection with the given name, creating it if needed."""
    import bpy
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    coll.hide_viewport = hide_viewport
    return coll


def link_to_collection(obj, coll):
    """Unlink an object from every collection it is in, then link it to `coll`."""
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)


def remove_object_with_orphan_data(obj):
    """Remove an object, freeing its mesh/curve data if that became orphaned.

    Data shared with a master (linked duplicates) normally survives; only
    data with no users left is removed.
    """
    import bpy
    data = obj.data if obj.type in {'MESH', 'FONT', 'CURVE'} else None
    bpy.data.objects.remove(obj, do_unlink=True)
    if data is not None and data.users == 0:
        if isinstance(data, bpy.types.Mesh):
            bpy.data.meshes.remove(data)
        elif isinstance(data, bpy.types.Curve):
            bpy.data.curves.remove(data)


# ---------------------------------------------------------------------------
# Merged guide meshes
# ---------------------------------------------------------------------------

class GuideMeshBuilder:
    """Accumulates axis-aligned boxes (and arbitrary flat geometry) and emits
    them all as ONE mesh object.

    Guide scenery (grid lines, borders, baked labels) used to be one object --
    with its own mesh datablock, created via a bpy.ops call -- per element,
    which meant thousands of objects, a huge .blend and a laggy viewport.
    Everything added here becomes faces of a single shared mesh instead;
    colours are kept via one material slot per (name, colour) and per-face
    material indices.
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

    def add_mesh(self, verts, faces, location, mat_name, color):
        """Append arbitrary geometry (e.g. tessellated label text) offset by
        `location`. Faces may be tris/quads/ngons."""
        ox, oy, oz = location
        base = len(self.verts)
        self.verts.extend((vx + ox, vy + oy, vz + oz) for vx, vy, vz in verts)
        slot = self._mat_slot(mat_name, color)
        for f in faces:
            self.faces.append(tuple(base + i for i in f))
            self.face_mats.append(slot)

    def build(self):
        """Create and return the merged mesh object (not linked anywhere yet)."""
        import bpy
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(self.verts, [], self.faces)
        for name, color in self.mats:
            mesh.materials.append(get_material(name, color))
        mesh.polygons.foreach_set("material_index", self.face_mats)
        mesh.update()
        return bpy.data.objects.new(self.name, mesh)


# ---------------------------------------------------------------------------
# Master / placeholder asset geometry
# ---------------------------------------------------------------------------
# Placement convention: every master is modelled centred on its origin so a
# linked duplicate dropped on a tile centre fills that tile exactly.

def build_cube_master(name, mat_name, color):
    """Solid 1x1x1 cube centred on the tile (blocks and walls)."""
    import bpy
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.0))
    obj = bpy.context.active_object
    obj.name = name
    apply_material(obj, mat_name, color)
    return obj


def build_floor_master(name, mat_name, color):
    """Thin 1x1 plate centred on the tile -- a flat floor marker.

    The thinness is baked into the MESH, not object scale: placed components
    are linked duplicates sharing this mesh, and object-level scale would not
    carry over to them.
    """
    import bpy
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.0))
    obj = bpy.context.active_object
    obj.name = name
    for v in obj.data.vertices:
        v.co.z *= 0.1
    apply_material(obj, mat_name, color)
    return obj


def build_button_master(name, mat_name, color):
    """Small flat cylinder; origin at its centre so it can rest on a tile top."""
    import bpy
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=24, radius=BUTTON_RADIUS, depth=BUTTON_HEIGHT,
        location=(0.0, 0.0, 0.0),
    )
    obj = bpy.context.active_object
    obj.name = name
    apply_material(obj, mat_name, color)
    return obj


def build_ramp_master(name, mat_name, color, mesh_name="Snaked_RampMesh"):
    """Sloped wedge filling one tile (+-0.5 on every axis), rising toward +Y.

    With rotation 0 the high (vertical) wall faces +Y so the direction reads
    clearly. Built with bmesh (Blender has no primitive wedge) but kept
    centred on the origin to match the centred-box convention.
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
    mesh = bpy.data.meshes.new(mesh_name)
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
    apply_material(obj, mat_name, color)
    return obj


# ---------------------------------------------------------------------------
# Occupancy index
# ---------------------------------------------------------------------------

class ComponentIndex:
    """Occupancy index of placed components, keyed by grid cell.

    Placement and erase used to rescan the whole components collection for
    every cell query (erase + solid check + button lift = three scans per
    placement), which made bulk operations quadratic in the number of placed
    components. Instead, build one index per operation -- or one per *batch*
    -- and keep it updated as components are added and removed. Within a
    single operation the collection only changes through the owning script's
    place/erase functions, so the index stays true.

    Instanced fills (collection-instance empties tagged "snaked_instance")
    are expanded into read-only solid occupancy: a button dropped on a cell
    whose block lives inside an instance still lands on the tile's top, but
    at()/erase never return parts of an instance.
    """

    def __init__(self, collection_name):
        import bpy
        self._cells = {}             # (x, y, layer) -> [obj, ...]
        self._instanced_solids = set()   # cells filled by an INSTANCE's solid
        coll = bpy.data.collections.get(collection_name)
        if coll is not None:
            for obj in coll.objects:
                self.add(obj)
                if "snaked_instance" in obj:
                    self.add_instance(obj)

    @staticmethod
    def _key_of(obj):
        """The object's cell key, or None for anything we did not place."""
        if "snaked_component" not in obj:
            return None   # safety: never index anything we did not tag
        key = (obj.get("snaked_x"), obj.get("snaked_y"), obj.get("snaked_z"))
        return None if None in key else key

    def add(self, obj):
        """Index a placed component (no-op for untagged objects)."""
        key = self._key_of(obj)
        if key is not None:
            self._cells.setdefault(key, []).append(obj)

    def add_instance(self, empty):
        """Register an instanced fill's SOLID cells for solid_at()."""
        ax, ay = empty.get("snaked_x"), empty.get("snaked_y")
        proto = empty.instance_collection
        if ax is None or ay is None or proto is None:
            return
        for src in proto.objects:
            if src.get("snaked_component") in SOLID_KINDS:
                self._instanced_solids.add(
                    (ax + src.get("snaked_x", 0),
                     ay + src.get("snaked_y", 0),
                     src.get("snaked_z", 0)))

    def discard(self, obj):
        """Drop a component from the index (call just before removing it)."""
        key = self._key_of(obj)
        objs = self._cells.get(key)
        if objs and obj in objs:
            objs.remove(obj)

    def at(self, x, y, layer):
        """Placed components at the cell (a copy, safe to erase while iterating)."""
        return list(self._cells.get((x, y, layer), ()))

    def solid_at(self, x, y, layer):
        """True if a tile-filling solid (block/wall/ramp) occupies the cell."""
        if (x, y, layer) in self._instanced_solids:
            return True
        return any(obj.get("snaked_component") in SOLID_KINDS
                   for obj in self._cells.get((x, y, layer), ()))
