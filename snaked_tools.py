


"""
snaked_tools.py

A simplified map-editor sidebar panel for the game "Snaked".

This sits *next to* snaked_map_builder.py (which draws the 22x40x4 grid) and
never touches the grid. It adds a "Snaked Tools" panel to the 3D viewport
sidebar (press N) that lets you drop and erase a small set of gameplay
components on the grid.

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

import bpy
import bmesh

# ---------------------------------------------------------------------------
# Configuration  (must match snaked_map_builder.py)
# ---------------------------------------------------------------------------

GRID_WIDTH = 22      # tiles along X
GRID_HEIGHT = 40     # tiles along Y
NUM_LAYERS = 4       # 1 floor + 3 obstacle layers
LAYER_HEIGHT = 1.0   # Z distance between layers (1 unit == 1 tile)

COMPONENTS_COLLECTION = "Snaked_Components"
LIBRARY_COLLECTION = "Snaked_Asset_Library"

# Master-asset object names, one per component kind.
MASTER_NAMES = {
    "BLOCK": "Master_Block",
    "BUTTON": "Master_Button",
    "RAMP": "Master_Ramp",
}


# ---------------------------------------------------------------------------
# Collection helpers
# ---------------------------------------------------------------------------

def _get_or_create_collection(name, hide_viewport=False):
    """Return a scene collection with the given name, creating it if needed."""
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    coll.hide_viewport = hide_viewport
    return coll


# ---------------------------------------------------------------------------
# Material helper
# ---------------------------------------------------------------------------

def _get_material(name, color):
    """Return a flat-shaded material with the given name, creating it if needed."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = False
    mat.diffuse_color = (color[0], color[1], color[2], 1.0)
    return mat


def _apply_material(obj, name, color):
    """Apply a single flat-shaded material to an object.

    Same convention as snaked_map_builder._apply_material.
    """
    mat = _get_material(name, color)
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def _link_to_collection(obj, coll):
    """Unlink an object from every collection it is in, then link it to `coll`.

    Mirrors snaked_map_builder._link_to_map.
    """
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)


# ---------------------------------------------------------------------------
# Master / placeholder asset geometry
# ---------------------------------------------------------------------------
# Placement convention matches snaked_map_builder.py: like the grid's boxes,
# every master is modelled *centred on its origin* (x = y = 0, and centred in
# z too). A tile at layer L occupies the cell centred on z = L, so a placed
# block/ramp fills z in [L-0.5, L+0.5] exactly like a grid box centred at z = L.
# Buttons follow the original button.py and rest on the tile's top face.

BUTTON_RADIUS = 0.3
BUTTON_HEIGHT = 0.15
TILE_TOP = 0.5   # half a tile above the centre — the tile's top face (button.py)


def _build_block_master(name):
    """Solid 1x1x1 cube centred on the tile (matches the grid's centred boxes)."""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.0))
    obj = bpy.context.active_object
    obj.name = name
    _apply_material(obj, "Snaked_BlockMat", (0.30, 0.55, 0.85))   # blue
    return obj


def _build_button_master(name):
    """Small flat cylinder; origin at its centre so it can rest on a tile top."""
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=24, radius=BUTTON_RADIUS, depth=BUTTON_HEIGHT,
        location=(0.0, 0.0, 0.0),
    )
    obj = bpy.context.active_object
    obj.name = name
    _apply_material(obj, "Snaked_ButtonMat", (0.90, 0.20, 0.20))   # red
    return obj


def _build_ramp_master(name):
    """Sloped wedge filling one tile (+-0.5 on every axis), rising toward +Y.

    With rotation 0 the high (vertical) wall faces +Y so the direction reads
    clearly. Built with bmesh (Blender has no primitive wedge) but kept centred
    on the origin to match the grid's centred-box convention.
    """
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
    mesh = bpy.data.meshes.new("Snaked_RampMesh")
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
    _apply_material(obj, "Snaked_RampMat", (0.95, 0.75, 0.15))   # amber
    return obj


_MASTER_BUILDERS = {
    "BLOCK": _build_block_master,
    "BUTTON": _build_button_master,
    "RAMP": _build_ramp_master,
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


def _placement_z(kind, layer):
    """World Z for a placed component's origin.

    Z equals the layer number (the grid plane at z = layer). Blocks and ramps
    are centred on that plane like the grid's boxes; buttons sit on the tile's
    top face, exactly as the original button.py raised the button by CUBE_TOP.
    """
    z = layer * LAYER_HEIGHT
    if kind == "BUTTON":
        z += TILE_TOP + BUTTON_HEIGHT / 2.0
    return z


# ---------------------------------------------------------------------------
# Placement / erase
# ---------------------------------------------------------------------------

def _component_name(kind, x, y, layer, rotation, name_id):
    """Build the canonical object name for a placed component."""
    if kind == "BLOCK":
        return "Block_x%d_y%d_z%d" % (x, y, layer)
    if kind == "RAMP":
        return "Ramp_x%d_y%d_z%d_rot%d" % (x, y, layer, rotation)
    if kind == "BUTTON":
        return "Button_%s_x%d_y%d_z%d" % (name_id, x, y, layer)
    raise ValueError("Unknown kind %r" % kind)


def _iter_components_at(x, y, layer):
    """Yield placed component objects sitting at the given grid cell."""
    coll = bpy.data.collections.get(COMPONENTS_COLLECTION)
    if coll is None:
        return
    for obj in list(coll.objects):
        if (obj.get("snaked_x") == x
                and obj.get("snaked_y") == y
                and obj.get("snaked_z") == layer):
            yield obj


def erase_component(x, y, layer):
    """Remove any placed component(s) at the cell. Grid and masters are never
    touched because we only ever look inside the Snaked_Components collection
    and only remove objects tagged as placed components."""
    removed = 0
    for obj in _iter_components_at(x, y, layer):
        if "snaked_component" not in obj:
            continue  # safety: never remove anything we did not place
        mesh = obj.data if obj.type == 'MESH' else None
        bpy.data.objects.remove(obj, do_unlink=True)
        # Mesh data is shared with the master, so it will normally survive;
        # only remove it if it has become an orphan.
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        removed += 1
    return removed


def place_component(kind, x, y, layer, rotation=0, name_id=""):
    """Place a component as a linked-duplicate of its master asset.

    Any existing component already at the same cell is erased first so that
    placement overwrites cleanly.
    """
    import math

    erase_component(x, y, layer)

    master = _ensure_master(kind)
    obj = bpy.data.objects.new(
        _component_name(kind, x, y, layer, rotation, name_id),
        master.data,                 # shares the master mesh (linked duplicate)
    )

    obj.location = (float(x), float(y), _placement_z(kind, layer))
    obj.rotation_euler = (0.0, 0.0, math.radians(rotation))

    # Tag the placement so erase can find it and never confuse it with a
    # grid object or a master asset.
    obj["snaked_component"] = kind
    obj["snaked_x"] = x
    obj["snaked_y"] = y
    obj["snaked_z"] = layer
    if kind == "BUTTON":
        obj["snaked_id"] = name_id

    components = _get_or_create_collection(COMPONENTS_COLLECTION)
    components.objects.link(obj)
    return obj


# ---------------------------------------------------------------------------
# UI: properties, operator, panel
# ---------------------------------------------------------------------------

class SnakedToolsProps(bpy.types.PropertyGroup):
    component: bpy.props.EnumProperty(
        name="Component",
        description="What to place (or Erase to remove)",
        items=[
            ("RAMP", "Ramp", "Sloped wedge showing direction"),
            ("BUTTON", "Button", "Small flat button on top of a tile"),
            ("BLOCK", "Block", "Solid cube that fills one tile"),
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


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_classes = (
    SnakedToolsProps,
    SNAKED_OT_apply,
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
