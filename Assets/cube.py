"""
cube.py

Add a 1x1x1 cube at the world origin.

Run this from Blender's Text Editor (Alt+P) or via the command line:
    blender --python cube.py
"""

import bpy

# size=1 gives a 1x1x1 cube (Blender's default cube is size=2).
bpy.ops.mesh.primitive_cube_add(size=1, location=(0.5, 0.5, 0.5))
bpy.context.active_object.name = "Cube_1x1"
