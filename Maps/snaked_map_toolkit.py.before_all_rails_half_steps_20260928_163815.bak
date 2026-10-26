"""Start every Snaked map-row tool from one embedded Blender text.

Run this text once with Alt+P after opening the blend file.
"""
import bpy

TOOLS = (
    'snaked_map_row.py',
    'snaked_exit_door.py',
    'snaked_rail_puzzles.py',
    'snaked_rail_placer.py',
    'snaked_component_placer.py',
)

for name in TOOLS:
    text = bpy.data.texts.get(name)
    if text is None:
        raise FileNotFoundError("Missing embedded Blender text: " + name)
    namespace = {'__name__': '__main__', '__file__': text.filepath or name}
    exec(compile(text.as_string(), name, 'exec'), namespace)

print('Snaked map toolkit ready: maps, puzzle pieces, exit door, components, and rails.')
