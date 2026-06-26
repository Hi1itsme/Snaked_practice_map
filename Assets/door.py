"""
door.py

Build a door that fits entirely inside the 1x1x1 cube/tile: a frame (two jambs,
a top lintel and a bottom sill) with a door leaf set into it, a mid-rail and a
knob on each face. Nothing pokes past the +-0.5 tile bounds, so it drops onto a
tile centre exactly like Wall.py / cube.py.

The scene is cleared first, so this leaves ONLY the door behind -- no leftover
default cube sitting in the same spot.

Convention (shared with cube.py / Wall.py / snaked_tools.py masters)
-------------------------------------------------------------------
- 1 Blender unit == 1 tile; the door is centred on the origin.
- The leaf faces +Y / -Y (the direction you'd walk through), so it reads as a
  door set into a wall that runs along X.

Run from Blender's Text Editor (Alt+P) or via the command line:
    blender --python door.py
"""

import bpy
from math import radians

# ---------------------------------------------------------------------------
# Dimensions (tile units; everything stays within the centred 1x1x1 cube)
# ---------------------------------------------------------------------------

HALF = 0.5            # tile half-extent -> every part must stay within +-0.5

FRAME_BAR = 0.10      # width of each frame member (jambs / lintel / sill)
FRAME_T = 0.18        # frame thickness along Y (stands proud of the leaf)
FRAME_INSET = 0.02    # keep the frame just inside the tile edge (no z-fighting)

DOOR_W = 0.62         # leaf width (along X), fits between the jambs
DOOR_T = 0.10         # leaf thickness (along Y), recessed inside the frame

# Derived placements -----------------------------------------------------------
JAMB_X = DOOR_W / 2.0 + FRAME_BAR / 2.0       # centre X of each vertical jamb
FRAME_OUTER_W = DOOR_W + 2.0 * FRAME_BAR      # full outer width of the frame
FRAME_TOP = HALF - FRAME_INSET                # top of the frame (z)
FRAME_BOT = -HALF + FRAME_INSET               # bottom of the frame (z)
FRAME_H = FRAME_TOP - FRAME_BOT               # full frame height
LINTEL_Z = FRAME_TOP - FRAME_BAR / 2.0        # centre Z of the top lintel
SILL_Z = FRAME_BOT + FRAME_BAR / 2.0          # centre Z of the bottom sill
DOOR_H = (LINTEL_Z - FRAME_BAR / 2.0) - (SILL_Z + FRAME_BAR / 2.0)  # opening height

# ---------------------------------------------------------------------------
# Materials (flat-shaded; simple diffuse colours that export cleanly)
# ---------------------------------------------------------------------------

def _material(name, color):
    """Return a flat-shaded material with the given name, creating it if needed."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = False
    mat.diffuse_color = (color[0], color[1], color[2], 1.0)
    return mat


def _emission_material(name, color, strength):
    """Return an EMISSIVE material (glows the given colour), creating it if needed.

    Uses an Emission shader so the leaf actually emits light/glows in Eevee &
    Cycles. The diffuse_color is set to match so it also reads correctly in the
    Solid viewport and in exporters that only look at diffuse_color.
    """
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emi = nt.nodes.new("ShaderNodeEmission")
    emi.inputs["Color"].default_value = (color[0], color[1], color[2], 1.0)
    emi.inputs["Strength"].default_value = strength
    nt.links.new(emi.outputs["Emission"], out.inputs["Surface"])
    mat.diffuse_color = (color[0], color[1], color[2], 1.0)
    return mat


MAT_FRAME = ("Door_Frame", (0.40, 0.42, 0.46))   # steel -- the surrounding frame
MAT_LEAF = ("Door_Leaf", (0.55, 0.38, 0.24))     # warm bronze/wood -- the leaf
MAT_KNOB = ("Door_Knob", (0.82, 0.68, 0.34))     # brass -- the knob

GREEN_GLOW = (0.05, 0.95, 0.25)   # the colour the door panel glows
# Emission strength. Keep this LOW: green only stays green up to a point -- crank
# it too high (e.g. 350) and the colour saturates all the way to white. ~3-8 is a
# bright green glow; bloom adds the halo on top.
GLOW_STRENGTH = 5.0


def _apply(obj, mat_spec):
    obj.data.materials.clear()
    obj.data.materials.append(_material(*mat_spec))


def _apply_glow(obj, name, color, strength):
    """Give `obj` an emissive (glowing) material."""
    obj.data.materials.clear()
    obj.data.materials.append(_emission_material(name, color, strength))


# ---------------------------------------------------------------------------
# Primitive helpers -- everything is collected, then joined into one object
# ---------------------------------------------------------------------------

_parts = []


def _box(name, location, size, mat_spec):
    """Add a cube scaled to `size` (X,Y,Z) at `location`; transforms bake on join."""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = size
    _apply(obj, mat_spec)
    _parts.append(obj)
    return obj


def _knob(name, location):
    """Add a small cylinder knob whose axis runs along Y (out of the leaf face)."""
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=20, radius=0.05, depth=0.06, location=location,
    )
    obj = bpy.context.active_object
    obj.name = name
    obj.rotation_euler = (radians(90), 0.0, 0.0)   # cylinder axis Z -> Y
    _apply(obj, MAT_KNOB)
    _parts.append(obj)
    return obj


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

# Clear scene so nothing else (e.g. a leftover default cube) shares this tile.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Frame: two vertical jambs, a top lintel and a bottom sill, all FRAME_T deep.
_box("Door_Jamb_L", (-JAMB_X, 0.0, (FRAME_TOP + FRAME_BOT) / 2.0),
     (FRAME_BAR, FRAME_T, FRAME_H), MAT_FRAME)
_box("Door_Jamb_R", (+JAMB_X, 0.0, (FRAME_TOP + FRAME_BOT) / 2.0),
     (FRAME_BAR, FRAME_T, FRAME_H), MAT_FRAME)
_box("Door_Lintel", (0.0, 0.0, LINTEL_Z),
     (FRAME_OUTER_W, FRAME_T, FRAME_BAR), MAT_FRAME)
_box("Door_Sill", (0.0, 0.0, SILL_Z),
     (FRAME_OUTER_W, FRAME_T, FRAME_BAR), MAT_FRAME)

# The door leaf, set into the opening (thinner than the frame so it reads inset).
# This is the part that glows green.
leaf = _box("Door_Leaf", (0.0, 0.0, 0.0), (DOOR_W, DOOR_T, DOOR_H), MAT_LEAF)
_apply_glow(leaf, "Door_Glow", GREEN_GLOW, GLOW_STRENGTH)

# A mid-rail across the leaf -> classic two-panel door look (stands slightly
# proud of the leaf on both faces). Glows with the leaf.
midrail = _box("Door_MidRail", (0.0, 0.0, 0.0), (DOOR_W, DOOR_T + 0.04, 0.06), MAT_LEAF)
_apply_glow(midrail, "Door_Glow", GREEN_GLOW, GLOW_STRENGTH)

# A green-glowing cap that sits just ON TOP of the frame so the glow is clearly
# visible from a top-down camera (the leaf faces sideways and is hidden from
# straight above). It is stacked ABOVE the frame with a hair of air gap and
# inset slightly, so none of its faces overlap the frame -> no z-fighting/glitch.
CAP_T = 0.015          # cap thickness (Z)
CAP_GAP = 0.005        # tiny gap above the frame so faces never become coplanar
CAP_INSET = 0.03       # shrink footprint so cap sides don't touch frame sides
top_glow = _box("Door_TopGlow",
                (0.0, 0.0, HALF - CAP_T / 2.0),   # rides at the very tile top
                (FRAME_OUTER_W - CAP_INSET, FRAME_T - CAP_INSET, CAP_T), MAT_LEAF)
_apply_glow(top_glow, "Door_Glow", GREEN_GLOW, GLOW_STRENGTH)

# A knob on each face, near the latch side (+X), at handle height.
_knob("Door_Knob_Front", (0.20, +(DOOR_T / 2.0 + 0.03), 0.0))
_knob("Door_Knob_Back", (0.20, -(DOOR_T / 2.0 + 0.03), 0.0))

# Join everything into a single "Door" object (transforms bake into the mesh).
bpy.ops.object.select_all(action='DESELECT')
for obj in _parts:
    obj.select_set(True)
bpy.context.view_layer.objects.active = _parts[0]
bpy.ops.object.join()

door = bpy.context.active_object
door.name = "Door"

# Recalculate normals so every face points outward.
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT')

# Turn on Eevee (legacy) bloom so the green emission actually blooms. Newer
# Eevee Next / Cycles don't expose this flag, so guard it and move on.
try:
    eevee = bpy.context.scene.eevee
    if hasattr(eevee, "use_bloom"):
        eevee.use_bloom = True
except Exception:
    pass

# IMPORTANT: emission/glow is INVISIBLE in 'Solid' viewport shading -- Solid mode
# only ever shows the flat diffuse colour, so changing GLOW_STRENGTH there does
# nothing. Force every 3D viewport to 'RENDERED' so the glow + bloom actually
# show. (Guarded: there is no screen/viewport in background `--python` runs.)
try:
    screen = bpy.context.screen
    if screen is not None:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = 'RENDERED'
except Exception:
    pass

print("Door created -- steel frame with a green-glowing leaf and a green-glowing "
      "top cap (visible from top-down), fits inside the 1x1x1 tile "
      "(scene cleared, no leftover cube). NOTE: glow only shows in Material "
      "Preview / Rendered shading, not Solid.")
