import bpy
import bmesh
import math

# Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

mesh = bpy.data.meshes.new("Rail_90")
obj  = bpy.data.objects.new("Rail_90", mesh)
bpy.context.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)

bm = bmesh.new()

# ── Same profile as the straight rail ────────────────────────────────────────
SCALE = 100   # compensates for Blender FBX 0.01 export scale → correct size in Unity

bw = 0.12  * SCALE
bh = 0.06  * SCALE
wt = 0.025 * SCALE
wh = 0.12  * SCALE
hw = 0.06  * SCALE
hh = 0.04  * SCALE

profile = [
    (-bw, 0.0),           # 0  base outer-left
    ( bw, 0.0),           # 1  base outer-right
    ( bw, bh),            # 2  base inner-right
    ( wt, bh),            # 3  web bottom-right
    ( wt, bh + wh),       # 4  web top-right
    ( hw, bh + wh),       # 5  head inner-right
    ( hw, bh + wh + hh),  # 6  head outer-right
    (-hw, bh + wh + hh),  # 7  head outer-left
    (-hw, bh + wh),       # 8  head inner-left
    (-wt, bh + wh),       # 9  web top-left
    (-wt, bh),            # 10 web bottom-left
    (-bw, bh),            # 11 base inner-left
]

# ── Quarter-circle arc ────────────────────────────────────────────────────────
# Tile: X −0.5→0.5, Y 0→1  (same footprint as the straight rail)
#
# Arc center: (0.5, 0),  radius: 0.5
#   s=0 → position (0,   0  ), tangent (0, +1) — south face CENTER, matches straight rail
#   s=1 → position (0.5, 0.5), tangent (+1, 0) — east  face CENTER, modular connection ✓
#
# pos(s)     = (0.5 − 0.5·cos(s·π/2),  0.5·sin(s·π/2))
# tangent(s) = (sin(s·π/2),             cos(s·π/2))
# right(s)   = (cos(s·π/2),            −sin(s·π/2))

SEGMENTS = 32  # smoothness

def arc_frame(s):
    """Returns (cx, cy, right_x, right_y) at arc parameter s ∈ [0,1]."""
    a  = s * math.pi / 2
    cx = (0.5 - 0.5 * math.cos(a)) * SCALE
    cy = (0.5 * math.sin(a))       * SCALE
    rx =  math.cos(a)   # right x
    ry = -math.sin(a)   # right y
    return cx, cy, rx, ry

# ── Build vertex rings along the arc ─────────────────────────────────────────
all_rings = []
for i in range(SEGMENTS + 1):
    s = i / SEGMENTS
    cx, cy, rx, ry = arc_frame(s)
    ring = []
    for px, pz in profile:
        wx = cx + px * rx
        wy = cy + px * ry
        wz = pz
        # mirror x → right turn
        vx = 0.5 * SCALE - wy
        vy = 0.5 * SCALE - wx
        ring.append(bm.verts.new((vx, vy, wz)))
    all_rings.append(ring)

# ── Side faces between adjacent rings ────────────────────────────────────────
n = len(profile)
for i in range(SEGMENTS):
    r0 = all_rings[i]
    r1 = all_rings[i + 1]
    for j in range(n):
        k = (j + 1) % n
        bm.faces.new([r0[j], r0[k], r1[k], r1[j]])

# ── End caps — single N-gon per cap, no zero-area filler faces ───────────────
def cap_faces(ring, reverse=False):
    r = list(reversed(ring)) if reverse else ring
    bm.faces.new(r)

cap_faces(all_rings[0],  reverse=True)   # entry end
cap_faces(all_rings[-1], reverse=False)  # exit end

bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

bm.to_mesh(mesh)
bm.free()
mesh.update()

print("90-degree rail turn created. Fits 1×1 unit tile.")
