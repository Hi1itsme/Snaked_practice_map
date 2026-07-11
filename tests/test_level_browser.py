"""Headless test of the level catalog + Browse dropdown.

Run:  blender.exe -b --factory-startup --python tests/test_level_browser.py
"""
import os
import sys
import shutil
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import bpy  # noqa: E402
import snaked_map_builder as mb  # noqa: E402
import snaked_tools as st  # noqa: E402

TMP = tempfile.mkdtemp(prefix="snaked_browser_test_")
FAILURES = []


def check(name, cond, detail=""):
    status = "ok" if cond else "FAIL"
    print("[TEST] %-58s %s %s" % (name, status, detail))
    if not cond:
        FAILURES.append(name)


# ---------------------------------------------------------------------------
# 1. Save two levels into a temp root, build the catalog from it.
mb.rebuild()
st.place_component("BLOCK", 5, 5, 0)
st.save_level(1, 1, name="Alpha", root=TMP)
st.clear_components()
st.place_component("WALL", 2, 2, 0)
st.save_level(2, 5, name="Beta", root=TMP)

catalog = st.load_level_catalog(root=TMP)
check("catalog keys are level ids",
      set(catalog) == {"world_01_level_001", "world_02_level_005"})
check("catalog entries carry names",
      catalog["world_01_level_001"]["name"] == "Alpha")

n = st._refresh_level_catalog(root=TMP)
check("refresh reports the level count", n == 2)
labels = [item[1] for item in st._level_enum_items]
check("dropdown labels read W#-L#  Name",
      labels == ["W1-L1  Alpha", "W2-L5  Beta"], labels)

# Completion status shows up in the label after refresh.
st.set_level_status(2, 5, "complete", root=TMP)
st._refresh_level_catalog(root=TMP)
labels = [item[1] for item in st._level_enum_items]
check("complete levels are tagged in the dropdown",
      labels[1] == "W2-L5  Beta  [complete]", labels[1])

# 2. Picking from the dropdown drives the World/Level/Name fields.
st.register()
try:
    p = bpy.context.scene.snaked_tools
    p.saved_level = "world_02_level_005"
    check("picking a level sets World/Level/Name",
          p.world == 2 and p.level == 5 and p.level_name == "Beta",
          "(%d, %d, %r)" % (p.world, p.level, p.level_name))
    p.saved_level = "world_01_level_001"
    check("picking another level re-points the fields",
          p.world == 1 and p.level == 1 and p.level_name == "Alpha")
finally:
    st.unregister()

# 3. Empty index gives the friendly placeholder, and picking it is a no-op.
st._refresh_level_catalog(root=tempfile.mkdtemp(prefix="snaked_empty_"))
check("empty index shows a placeholder entry",
      st._level_enum_items[0][0] == "NONE")

# ---------------------------------------------------------------------------
shutil.rmtree(TMP, ignore_errors=True)
if FAILURES:
    print("[TEST] FAILED: %s" % ", ".join(FAILURES))
    sys.exit(1)
print("[TEST] all checks passed")
