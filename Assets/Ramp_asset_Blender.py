import bpy
import bmesh

# Remove default cube if present
bpy.ops.object.select_all(action='DESELECT')
for obj in bpy.data.objects:
    if obj.name == "Cube":
        obj.select_set(True)
        bpy.ops.object.delete()

# Create a new mesh and object
mesh = bpy.data.meshes.new("Ramp")
obj = bpy.data.objects.new("Ramp", mesh)
bpy.context.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)

bm = bmesh.new()

# 1x1x1 triangular ramp (right-angle prism)
# Vertices: two triangular faces (front and back) forming a wedge
# Base is on XY plane, ramp rises from front-bottom to back-top
#
#       4----5        <- top back edge  (z=1, y=1)
#      /|   /|
#     / |  / |
#    /  | /  |
#   2---3/   |        <- not used — prism has 6 verts total
#
# Simpler: 6 vertices (2 triangles connected)
#
#  Front face (y=0): bottom-left (0,0,0), bottom-right (1,0,0), top-right (1,0,1)
#  Back  face (y=1): bottom-left (0,1,0), bottom-right (1,1,0), top-right (1,1,1)
#
#  The ramp slopes from z=0 at the front to z=1 at the back (45 degrees)

verts = [
    bm.verts.new((0, 0, 0)),  # 0 front bottom left
    bm.verts.new((1, 0, 0)),  # 1 front bottom right
    bm.verts.new((1, 0, 1)),  # 2 front top right  (peak at front)
    bm.verts.new((0, 1, 0)),  # 3 back  bottom left
    bm.verts.new((1, 1, 0)),  # 4 back  bottom right
    bm.verts.new((1, 1, 1)),  # 5 back  top right  (peak at back)
]

# Faces
bm.faces.new([verts[0], verts[1], verts[2]])          # front triangle
bm.faces.new([verts[3], verts[5], verts[4]])          # back triangle  (flipped for normals)
bm.faces.new([verts[0], verts[3], verts[4], verts[1]])  # bottom quad
bm.faces.new([verts[1], verts[4], verts[5], verts[2]])  # right quad (vertical wall)
bm.faces.new([verts[0], verts[2], verts[5], verts[3]])  # ramp surface (slope)

bm.to_mesh(mesh)
bm.free()

mesh.update()

print("1x1x1 triangular ramp created successfully.")
