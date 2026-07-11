"""Headless test of the Completed Maps shelf.

Run:  blender.exe -b --factory-startup --python tests/test_completed_area.py
"""
import os
import sys
import json
import shutil
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import bpy  # noqa: E402
import snaked_map_builder as mb  # noqa: E402
import snaked_tools as st  # noqa: E402

TMP = tempfile.mkdtemp(prefix="snaked_completed_test_")
FAILURES = []


def check(name, cond, detail=""):
    status = "ok" if cond else "FAIL"
    print("[TEST] %-58s %s %s" % (name, status, detail))
    if not cond:
        FAILURES.append(name)


def shelf_objs():
    coll = bpy.data.collections.get(st.COMPLETED_COLLECTION)
    return list(coll.objects) if coll else []


def shelf_empties():
    return [o for o in shelf_objs() if o.type == 'EMPTY']


# ---------------------------------------------------------------------------
# 1. Author and save two small levels (into a temp project root).
mb.rebuild()

st.place_component("BLOCK", 5, 5, 0)
st.place_component("BUTTON", 5, 5, 0, name_id="A")
st.place_component("RAMP", 6, 5, 0, rotation=90)
st.save_level(1, 1, name="First", root=TMP)

st.clear_components()
st.place_component("WALL", 2, 2, 0)
st.place_component("FLOOR", 3, 2, 0)
st.save_level(1, 2, name="Second", root=TMP)

# ---------------------------------------------------------------------------
# 2. Empty shelf when nothing is complete.
check("shelf is empty before anything is complete",
      st.build_completed_area(root=TMP) == 0 and len(shelf_objs()) == 0)

# 3. Mark level 1 complete and shelve it.
meta = st.set_level_status(1, 1, "complete", root=TMP)
check("status written to level.json", meta["status"] == "complete")
with open(os.path.join(TMP, "ai_data", "all_levels.json"),
          encoding="utf-8") as fh:
    idx = {e["id"]: e for e in json.load(fh)["levels"]}
check("status written to the index",
      idx["world_01_level_001"]["status"] == "complete")

shown = st.build_completed_area(root=TMP)
check("one map shelved", shown == 1 and len(shelf_empties()) == 1)
empty = shelf_empties()[0]
proto = empty.instance_collection
check("shelved map is a collection instance of its proto",
      proto is not None and proto.name == "Level_Proto_world_01_level_001")
check("proto holds the level's 3 components", len(proto.objects) == 3)
x0, y0, _, _ = st._completed_slot_bounds(0)
check("instance anchored so grid coords land in the slot",
      empty.location.x == x0 - 1 and empty.location.y == y0 - 1)
btn = next(o for o in proto.objects if o.name.startswith("LvlProto_Button"))
check("proto button rides its block's top face",
      abs(btn.location.z - 0.575) < 1e-6)
guide = next((o for o in shelf_objs() if o.type == 'MESH'), None)
check("shelf guide mesh exists with baked labels",
      guide is not None and any(m.name.startswith("Workshop_Label_")
                                for m in guide.data.materials))

# 4. Second map stacks into the next slot up.
st.set_level_status(1, 2, "complete", root=TMP)
shown = st.build_completed_area(root=TMP)
check("two maps shelved after second completion", shown == 2
      and len(shelf_empties()) == 2)
ys = sorted(int(o.location.y) for o in shelf_empties())
stride = st.GRID_HEIGHT + st.COMPLETED_GAP
check("slots stack upward by grid height + gap", ys[1] - ys[0] == stride,
      ys)

# 5. Rebuild is idempotent; marking draft unshelves.
st.build_completed_area(root=TMP)
check("rebuild does not duplicate shelf objects",
      len(shelf_empties()) == 2)

st.set_level_status(1, 1, "draft", root=TMP)
shown = st.build_completed_area(root=TMP)
check("draft map removed from shelf", shown == 1
      and len(shelf_empties()) == 1
      and shelf_empties()[0].name.endswith("world_01_level_002"))
check("stale proto collection cleaned up",
      bpy.data.collections.get("Level_Proto_world_01_level_001") is None)
check("remaining map moved down into slot 0",
      int(shelf_empties()[0].location.y) == st.COMPLETED_ORIGIN_Y - 1)

# 6. Status survives a normal re-save (save_level preserves metadata).
st.load_level(1, 2, root=TMP)
st.save_level(1, 2, root=TMP)
with open(st._level_json_path(TMP, 1, 2), encoding="utf-8") as fh:
    check("re-saving a complete level keeps its status",
          json.load(fh)["status"] == "complete")

# ---------------------------------------------------------------------------
shutil.rmtree(TMP, ignore_errors=True)
if FAILURES:
    print("[TEST] FAILED: %s" % ", ".join(FAILURES))
    sys.exit(1)
print("[TEST] all checks passed")
