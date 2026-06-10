"""
Wall.py

Build a 1x1x1 "wall" cube that reads clearly as IMPASSABLE: a solid block with
a bold square panel-frame stamped on every side (the "you can't cross here"
marker) and a hex nut / bolt at each corner of that frame, so it looks built and
riveted together rather than a plain box.

Convention (shared with cube.py / snaked_tools.py masters)
----------------------------------------------------------
- The wall is a true 1x1x1 (1 Blender unit == 1 tile) centred on the origin, so
  it drops straight onto a tile centre like the grid's centred boxes.
- The four vertical side faces (+X, -X, +Y, -Y) get the frame + bolts, since
  those are the directions a player would try to cross. Top/bottom stay plain.

Run from Blender's Text Editor (Alt+P) or via the command line:
    blender --python Wall.py
"""

import bpy
from math import radians

# ---------------------------------------------------------------------------
# Dimensions (all in tile units; the body is a centred 1x1x1 cube)
# ---------------------------------------------------------------------------

HALF = 0.5            # half the cube -> each face sits at +-0.5 along its normal

FRAME_HALF = 0.33     # half-size of the square frame stamped on each face
FRAME_BAR = 0.07      # thickness (width) of each frame bar
FRAME_DEPTH = 0.05    # how far the frame stands proud of the face
BOLT_RADIUS = 0.055   # corner bolt / nut radius
BOLT_DEPTH = 0.07     # corner bolt / nut height (sticks out past the frame)

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


MAT_BODY = ("Wall_Body", (0.20, 0.22, 0.25))    # dark slate -- the solid block
MAT_TRIM = ("Wall_Trim", (0.46, 0.48, 0.52))    # steel -- the square frame
MAT_BOLT = ("Wall_Bolt", (0.58, 0.54, 0.46))    # warm metal -- the nuts/bolts


def _apply(obj, mat_spec):
    obj.data.materials.clear()
    obj.data.materials.append(_material(*mat_spec))


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


def _bolt(name, location, rotation):
    """Add a 6-sided prism (a hex nut / bolt head) at `location` with `rotation`."""
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=6, radius=BOLT_RADIUS, depth=BOLT_DEPTH, location=location,
    )
    obj = bpy.context.active_object
    obj.name = name
    obj.rotation_euler = rotation
    _apply(obj, MAT_BOLT)
    _parts.append(obj)
    return obj


def _build_face(axis, sign):
    """Stamp the square frame + four corner bolts onto one side face.

    `axis` is 'X', 'Y' or 'Z'; `sign` is +1 or -1 (which of the two faces on
    that axis). The frame is a square outline; the bolts sit at its four corners.
    """
    s, t, d = FRAME_HALF, FRAME_BAR, FRAME_DEPTH
    span = 2.0 * s + t                       # bar length so corners overlap
    frame_c = sign * (HALF + d / 2.0)        # frame centre, standing proud
    bolt_c = sign * (HALF + BOLT_DEPTH / 2.0)  # bolts stick out a touch further
    tag = "%s%s" % (axis, "p" if sign > 0 else "n")

    if axis == "X":
        # In-plane axes are Y (horizontal) and Z (vertical); depth runs along X.
        _box("Frame_%s_top" % tag, (frame_c, 0.0, +s), (d, span, t), MAT_TRIM)
        _box("Frame_%s_bot" % tag, (frame_c, 0.0, -s), (d, span, t), MAT_TRIM)
        _box("Frame_%s_rgt" % tag, (frame_c, +s, 0.0), (d, t, span), MAT_TRIM)
        _box("Frame_%s_lft" % tag, (frame_c, -s, 0.0), (d, t, span), MAT_TRIM)
        bolt_rot = (0.0, radians(90), 0.0)   # cylinder axis Z -> X
        for sy in (+s, -s):
            for sz in (+s, -s):
                _bolt("Bolt_%s_%+d%+d" % (tag, sy > 0, sz > 0),
                      (bolt_c, sy, sz), bolt_rot)
    elif axis == "Y":
        # In-plane axes are X (horizontal) and Z (vertical); depth runs along Y.
        _box("Frame_%s_top" % tag, (0.0, frame_c, +s), (span, d, t), MAT_TRIM)
        _box("Frame_%s_bot" % tag, (0.0, frame_c, -s), (span, d, t), MAT_TRIM)
        _box("Frame_%s_rgt" % tag, (+s, frame_c, 0.0), (t, d, span), MAT_TRIM)
        _box("Frame_%s_lft" % tag, (-s, frame_c, 0.0), (t, d, span), MAT_TRIM)
        bolt_rot = (radians(90), 0.0, 0.0)   # cylinder axis Z -> Y
        for sx in (+s, -s):
            for sz in (+s, -s):
                _bolt("Bolt_%s_%+d%+d" % (tag, sx > 0, sz > 0),
                      (sx, bolt_c, sz), bolt_rot)
    else:  # axis == "Z" (top / bottom face)
        # In-plane axes are X and Y; depth runs along Z. Bolts keep their
        # default Z axis, so no rotation is needed.
        _box("Frame_%s_top" % tag, (0.0, +s, frame_c), (span, t, d), MAT_TRIM)
        _box("Frame_%s_bot" % tag, (0.0, -s, frame_c), (span, t, d), MAT_TRIM)
        _box("Frame_%s_rgt" % tag, (+s, 0.0, frame_c), (t, span, d), MAT_TRIM)
        _box("Frame_%s_lft" % tag, (-s, 0.0, frame_c), (t, span, d), MAT_TRIM)
        bolt_rot = (0.0, 0.0, 0.0)           # cylinder axis already Z
        for sx in (+s, -s):
            for sy in (+s, -s):
                _bolt("Bolt_%s_%+d%+d" % (tag, sx > 0, sy > 0),
                      (sx, sy, bolt_c), bolt_rot)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

# Clear scene (matches button.py / the other asset scripts).
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# The solid block, centred on the origin.
body = _box("Wall_Body", (0.0, 0.0, 0.0), (1.0, 1.0, 1.0), MAT_BODY)

# Stamp the "no-cross" frame + corner bolts on all four vertical faces...
for axis in ("X", "Y"):
    for sign in (+1, -1):
        _build_face(axis, sign)
# ...and on the top face too.
_build_face("Z", +1)

# Join everything into a single "Wall" object (transforms bake into the mesh).
bpy.ops.object.select_all(action='DESELECT')
for obj in _parts:
    obj.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.ops.object.join()

wall = bpy.context.active_object
wall.name = "Wall"

# Recalculate normals so every face points outward.
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT')

print("Wall created -- 1x1x1 impassable block with a square frame and "
      "corner bolts on all four sides.")
