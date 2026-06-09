import bpy
import bmesh
import math

# Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

mesh = bpy.data.meshes.new("Rail")
obj  = bpy.data.objects.new("Rail", mesh)
bpy.context.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
obj.location = (0, 0, 0)
obj.rotation_euler = (0, 0, math.radians(270))

bm = bmesh.new()

# Real rail profile (simplified): base -> web -> head
# Centered on X=0, sitting on Z=0, 1 unit long on Y
#
#    [-head-]        z=0.18 - 0.22
#       |            z=0.06 - 0.18  (web)
#   [--base--]       z=0.00 - 0.06

SCALE = 100   # compensates for Blender FBX 0.01 export scale → correct size in Unity

bw = 0.12  * SCALE
bh = 0.06  * SCALE
wt = 0.025 * SCALE
wh = 0.12  * SCALE
hw = 0.06  * SCALE
hh = 0.04  * SCALE
L  = 1.0   * SCALE

# Profile vertices, counter-clockwise from bottom-left
profile = [
    (-bw, 0.0),           # 0  base outer-left   (z=0)
    ( bw, 0.0),           # 1  base outer-right  (z=0)
    ( bw, bh),            # 2  base inner-right  (z=bh)
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

# Build start (y=0) and end (y=L) vert rings
front = [bm.verts.new((x, 0, z)) for x, z in profile]
back  = [bm.verts.new((x, L, z)) for x, z in profile]

# End caps — triangulate the concave profile manually
# Split into three convex quads/tris: base, web, head
def cap_faces(ring, reverse=False):
    r = list(reversed(ring)) if reverse else ring
    bm.faces.new(r)

cap_faces(front, reverse=False)
cap_faces(back,  reverse=True)

# Side quads along the length
n = len(front)
for i in range(n):
    j = (i + 1) % n
    bm.faces.new([front[i], back[i], back[j], front[j]])

bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

bm.to_mesh(mesh)
bm.free()
mesh.update()

print("Single rail created.")
