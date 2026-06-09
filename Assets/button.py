import bpy
import math

# Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

SCALE = .65   # compensates for Blender FBX 0.01 export scale → correct size in Unity

# The button shares its origin with the 1x1x1 cube (both load at the grid center).
# The cube's center is at that origin, so its top face is half a unit above it.
# Raise the button by that amount so it rests on top of the cube instead of
# overlapping it.
CUBE_TOP = 0.5   # half the cube's height

# ── Dimensions ──────────────────────────────────────────────────────────────────
RADIUS    = 0.5  * SCALE   # button radius
HEIGHT    = 0.2  * SCALE   # button body height (flat bottom rests on the cube top)
RING_MINR = 0.04 * SCALE   # thickness of the ring tube
RING_Z    = CUBE_TOP + HEIGHT * 0.5   # ring sits around the middle of the side
SEGMENTS  = 48

# ── Button body (cylinder, flat bottom on the cube's top face) ───────────────────
bpy.ops.mesh.primitive_cylinder_add(
    vertices=SEGMENTS,
    radius=RADIUS,
    depth=HEIGHT,
    location=(0, 0, CUBE_TOP + HEIGHT / 2.0),   # base flat on the cube top
)
body = bpy.context.active_object
body.name = "Button_Body"

# ── Ring around the side (torus hugging the outer wall) ──────────────────────────
bpy.ops.mesh.primitive_torus_add(
    major_radius=RADIUS,        # centered on the side wall
    minor_radius=RING_MINR,
    major_segments=SEGMENTS,
    minor_segments=16,
    location=(0, 0, RING_Z),
)
ring = bpy.context.active_object
ring.name = "Button_Ring"

# ── Join into a single Button object ────────────────────────────────────────────
bpy.ops.object.select_all(action='DESELECT')
body.select_set(True)
ring.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.ops.object.join()

button = bpy.context.active_object
button.name = "Button"

# Recalculate normals to point outward
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT')

print("Button created — flat bottom cylinder with a ring around the side.")
