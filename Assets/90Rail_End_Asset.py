import bpy
import bmesh

# Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

mesh = bpy.data.meshes.new("Rail_End_Half")
obj  = bpy.data.objects.new("Rail_End_Half", mesh)
bpy.context.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)

bm = bmesh.new()

  # compensates for Blender FBX 0.01 export scale → correct size in Unity

bw = 0.12  
bh = 0.06  
wt = 0.025 
wh = 0.12  
hw = 0.06  
hh = 0.04  
L  = 0.5   

# ── Vertices ──────────────────────────────────────────────────────────────────
# Entry (Y=0) — full I-beam
e0  = bm.verts.new((-bw, 0, 0          ))
e1  = bm.verts.new(( bw, 0, 0          ))
e2  = bm.verts.new(( bw, 0, bh         ))
e3  = bm.verts.new(( wt, 0, bh         ))
e4  = bm.verts.new(( wt, 0, bh+wh      ))
e5  = bm.verts.new(( hw, 0, bh+wh      ))
e6  = bm.verts.new(( hw, 0, bh+wh+hh   ))
e7  = bm.verts.new((-hw, 0, bh+wh+hh   ))
e8  = bm.verts.new((-hw, 0, bh+wh      ))
e9  = bm.verts.new((-wt, 0, bh+wh      ))
e10 = bm.verts.new((-wt, 0, bh         ))
e11 = bm.verts.new((-bw, 0, bh         ))

# Exit (Y=L) — base height only; inner verts where sloped surfaces land
x0  = bm.verts.new((-bw, L, 0  ))
x1  = bm.verts.new(( bw, L, 0  ))
x2  = bm.verts.new(( bw, L, bh ))
x3  = bm.verts.new(( wt, L, bh ))   # right inner shoulder
x4  = bm.verts.new(( hw, L, bh ))   # right head junction
x5  = bm.verts.new((-hw, L, bh ))   # left  head junction
x6  = bm.verts.new((-wt, L, bh ))   # left  inner shoulder
x7  = bm.verts.new((-bw, L, bh ))

def f(*v):
    bm.faces.new(v)

# ── Bottom ─────────────────────────────────────────────────────────────────────
f(e0, x0, x1, e1)

# ── Outer side walls ───────────────────────────────────────────────────────────
f(e1, x1, x2, e2)          # right (x=+bw)
f(e0, e11, x7, x0)         # left  (x=−bw)

# ── Base-top shoulders (flat, z=bh) ───────────────────────────────────────────
f(e2, e3, x3, x2)          # right shoulder
f(e10, e11, x7, x6)        # left  shoulder

# ── Sloped web inner walls (triangle — collapses to base top at exit) ─────────
f(e3, e4, x3)              # right
f(e9, e10, x6)             # left

# ── Sloped head-web shoulders ─────────────────────────────────────────────────
f(e4, e5, x4, x3)          # right
f(e8, e9, x6, x5)          # left

# ── Sloped head outer walls (triangle) ────────────────────────────────────────
f(e5, e6, x4)              # right
f(e7, e8, x5)              # left

# ── Sloped head top ───────────────────────────────────────────────────────────
f(e6, e7, x5, x4)

# ── Entry cap (Y=0) — full I-beam, same triangulation as all other pieces ─────
f(e0,  e1,  e2,  e11)      # base
f(e2,  e3,  e10, e11)      # base-web filler
f(e3,  e4,  e9,  e10)      # web
f(e4,  e5,  e8,  e9 )      # web-head filler
f(e5,  e6,  e7,  e8 )      # head

# ── Exit cap (Y=L) — base rectangle, fanned to include all top-edge verts ─────
f(x0, x1, x2)
f(x0, x2, x3)
f(x0, x3, x4)
f(x0, x4, x5)
f(x0, x5, x6)
f(x0, x6, x7)

# ── Fix all normals ────────────────────────────────────────────────────────────
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

bm.to_mesh(mesh)
bm.free()
mesh.update()

print("Rail end slope created — explicit faces, fully manifold, normals correct.")
