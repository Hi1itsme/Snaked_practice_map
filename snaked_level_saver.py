"""
snaked_level_saver.py


Blank foundation for SAVING and ORGANISING levels in the "Snaked" project.

This script is the level-side counterpart to puzzle_piece_workshop.py. It does
NOT generate level layouts, and it is NOT an AI level generator. It only lays
down the clean folder + file structure that levels will be saved into, plus a
single helper -- create_blank_level() -- for stamping out a new, empty level.

It is SAFE TO RUN MULTIPLE TIMES:

  1. Creates the on-disk level scaffold (folders + blank JSON files). Existing
     files are never overwritten -- missing folders/files are filled in,
     nothing is destroyed.

  2. Inside Blender, creates an empty top-level collection called
     "Snaked_Levels" to hold every per-level collection.

It NEVER touches the existing "Snaked_Map" collection, the existing
"Puzzle_Piece_Workshop" collection, or any puzzle-piece files those scripts
own. It only ever creates the levels/ tree, ai_data/all_levels.json, and the
"Snaked_Levels" collection.

On-disk layout this script builds (under the shared Snaked_Project root)
----------------------------------------------------------------------------
    Snaked_Project/
        levels/
            level_metadata_template.json   <- blank template for one level
            world_01/ ... world_08/        <- one folder per world
        ai_data/
            all_levels.json                <- combined index of every level

Each saved level eventually looks like:

    levels/
        world_01/
            level_001/
                level.json     <- this level's metadata (from the template)
                level.blend    <- (you save this from Blender; not made here)
                preview.png    <- (you render this later; not made here)

Conventions (shared with the other Snaked scripts)
----------------------------------------------------------------------------
- 1 Blender unit == 1 tile.
- Worlds are numbered 1..8 and stored zero-padded: world_01 .. world_08.
- Levels are zero-padded to three digits: level_001, level_002, ...
- A level's id and its Blender collection name are derived from those numbers,
  e.g. world 1 / level 1  ->  id "world_01_level_001",
                              collection "WORLD_01_LEVEL_001".

===========================================================================
HOW TO RUN
===========================================================================

  Option A (Blender Text Editor):
    - Open Blender, switch an area to the "Text Editor".
    - Open this file (Text > Open), then press  Alt+P  (Text > Run Script).

  Option B (command line):
    - blender --python snaked_level_saver.py

  Option C (VS Code with a Blender-connect add-on, e.g. "Blender Development"):
    - Command Palette > "Blender: Run Script" while connected to Blender.

Running the script builds the scaffold and the empty "Snaked_Levels"
collection. To stamp out a new blank level afterwards, call:

    create_blank_level(1, 1, "First Steps")

either from the same script, from another script, or from Blender's Python
console.
"""

import os
import sys
import json


def _ensure_repo_on_path():
    """Put this repo's folder on sys.path so `import snaked_common` works no
    matter how the script is run (module import, blender --python, plain
    python, or the Text Editor's Alt+P on a saved file)."""
    dirs = []
    try:
        dirs.append(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        pass
    try:
        import bpy
        dirs.extend(
            os.path.dirname(os.path.abspath(bpy.path.abspath(t.filepath)))
            for t in bpy.data.texts if t.filepath)
        if bpy.data.filepath:
            dirs.append(os.path.dirname(bpy.data.filepath))
    except Exception:
        pass
    dirs.append(os.getcwd())
    for d in dirs:
        if os.path.isfile(os.path.join(d, "snaked_common.py")):
            if d not in sys.path:
                sys.path.insert(0, d)
            return


_ensure_repo_on_path()

import snaked_common as sc

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_DIR_NAME = sc.PROJECT_DIR_NAME   # shared root folder name

LEVELS_COLLECTION = "Snaked_Levels"     # top-level Blender collection for all levels

# Collections we must NEVER touch -- listed here only for clarity / safety.
MAIN_MAP_COLLECTION = "Snaked_Map"
WORKSHOP_COLLECTION = "Puzzle_Piece_Workshop"

NUM_WORLDS = 8                          # world_01 .. world_08

# Blank metadata template for a single level. This is written to disk as
# levels/level_metadata_template.json and is also the starting point for every
# level.json that create_blank_level() stamps out.
_LEVEL_METADATA_TEMPLATE = {
    "id": "",
    "name": "",
    "world": 0,
    "level_number": 0,
    "difficulty": 0,
    "grid_size": [0, 0, 0],
    "pieces_used": [],
    "start_position": [0, 0, 0],
    "start_direction": "",
    "goal_position": [0, 0, 0],
    "required_mechanics": [],
    "introduced_mechanics": [],
    "tags": [],
    "notes": "",
    "status": "draft",
}

# Blank starter contents for the combined level index that a local AI will
# later read to understand every level at once.
_ALL_LEVELS_TEMPLATE = {
    "version": "0.1",
    "levels": [],
}


# ===========================================================================
# Shared project-root resolution (see snaked_common)
# ===========================================================================

resolve_project_root = sc.resolve_project_root


# ===========================================================================
# PART 1 -- On-disk level scaffold (pure Python; runs anywhere)
# ===========================================================================

def _levels_dir(root):
    """Absolute path of the levels/ folder under the project root."""
    return os.path.join(root, "levels")


def _ai_data_dir(root):
    """Absolute path of the ai_data/ folder under the project root."""
    return os.path.join(root, "ai_data")


# Naming conventions are shared with snaked_tools' level saver (snaked_common).
_world_folder_name = sc.world_folder_name
_level_folder_name = sc.level_folder_name
_level_id = sc.level_id
_level_collection_name = sc.level_collection_name


def _write_json_if_missing(path, contents):
    """Write `contents` as pretty JSON to `path`, but only if it doesn't exist.

    Returns True if a new file was written, False if an existing one was kept.
    """
    if os.path.exists(path):
        print("[Levels] Kept existing %s" % path)
        return False
    sc.save_json(path, contents)
    print("[Levels] Created %s" % path)
    return True


def setup_level_files():
    """Create the levels/ tree and ai_data/all_levels.json if (and only if)
    they are missing.

    Returns the resolved project-root path. Existing files are left untouched,
    so this is safe to run repeatedly and will never clobber your data.
    """
    root = resolve_project_root()
    os.makedirs(root, exist_ok=True)

    # levels/ and one folder per world (world_01 .. world_08).
    levels_dir = _levels_dir(root)
    os.makedirs(levels_dir, exist_ok=True)
    for world_number in range(1, NUM_WORLDS + 1):
        os.makedirs(os.path.join(levels_dir, _world_folder_name(world_number)),
                    exist_ok=True)

    # ai_data/ holds the combined index that a local AI will read later.
    ai_dir = _ai_data_dir(root)
    os.makedirs(ai_dir, exist_ok=True)

    # Blank JSON files -- only written when absent.
    _write_json_if_missing(
        os.path.join(levels_dir, "level_metadata_template.json"),
        _LEVEL_METADATA_TEMPLATE,
    )
    _write_json_if_missing(
        os.path.join(ai_dir, "all_levels.json"),
        _ALL_LEVELS_TEMPLATE,
    )

    print("[Levels] Level scaffold ready at: %s" % root)
    return root


# ---------------------------------------------------------------------------
# The combined level index (ai_data/all_levels.json)
# ---------------------------------------------------------------------------

def _all_levels_path(root):
    return os.path.join(_ai_data_dir(root), "all_levels.json")


def _load_all_levels(root):
    """Load the combined index, falling back to the blank template if missing
    or unreadable (so a corrupt/empty file never blocks a save)."""
    path = _all_levels_path(root)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            # Be tolerant of a hand-edited file that's missing keys.
            data.setdefault("version", _ALL_LEVELS_TEMPLATE["version"])
            data.setdefault("levels", [])
            return data
        except (ValueError, OSError):
            print("[Levels] WARNING: could not read %s -- starting a fresh "
                  "index in memory (existing file left in place)." % path)
    return dict(_ALL_LEVELS_TEMPLATE, levels=[])


def _save_all_levels(root, data):
    """Write the combined index back to disk as pretty JSON."""
    sc.save_json(_all_levels_path(root), data)


def _register_level_in_index(root, entry):
    """Add `entry` to ai_data/all_levels.json if its id isn't already listed.

    Returns True if the level was added, False if it was already present.
    Matching is by the level's id, so re-running create_blank_level() for the
    same world/level never creates a duplicate index entry.
    """
    data = _load_all_levels(root)
    if any(existing.get("id") == entry["id"] for existing in data["levels"]):
        print("[Levels] Index already lists %s -- not adding again."
              % entry["id"])
        return False
    data["levels"].append(entry)
    _save_all_levels(root, data)
    print("[Levels] Added %s to %s" % (entry["id"], _all_levels_path(root)))
    return True


# ===========================================================================
# PART 2 -- "Snaked_Levels" Blender collection (requires bpy)
# ===========================================================================

def get_levels_collection():
    """Return the top-level "Snaked_Levels" collection, creating and linking it
    if needed. Never touches Snaked_Map or Puzzle_Piece_Workshop."""
    import bpy
    coll = bpy.data.collections.get(LEVELS_COLLECTION)
    if coll is None:
        coll = bpy.data.collections.new(LEVELS_COLLECTION)
        bpy.context.scene.collection.children.link(coll)
        print("[Levels] Created Blender collection '%s'." % LEVELS_COLLECTION)
    return coll


def get_level_collection(world_number, level_number):
    """Return the per-level collection (e.g. "WORLD_01_LEVEL_001"), creating it
    and nesting it inside "Snaked_Levels" if needed.

    Idempotent: if the collection already exists we reuse it, and we make sure
    it is linked under "Snaked_Levels" exactly once.
    """
    import bpy
    parent = get_levels_collection()
    name = _level_collection_name(world_number, level_number)

    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)

    # Ensure the level collection sits inside Snaked_Levels (and only there,
    # among collections we manage). We don't unlink it from elsewhere in case
    # you've intentionally linked it somewhere too -- we just guarantee the
    # parent link exists.
    if coll.name not in parent.children:
        parent.children.link(coll)

    return coll


# ===========================================================================
# PART 3 -- Create one blank level
# ===========================================================================

def create_blank_level(world_number, level_number, level_name):
    """Create the folder + files + Blender collection for ONE blank level.

    This does NOT generate any layout -- it only stamps out the empty
    structure so a level is ready to be authored and saved into.

    Steps:
      1. Make levels/world_NN/level_MMM/ (creating parents as needed).
      2. Write level.json there from the metadata template, filling in the
         id / name / world / level_number (only if level.json doesn't exist).
      3. Add the level to ai_data/all_levels.json if it isn't already listed.
      4. Inside Blender, create a collection WORLD_NN_LEVEL_MMM nested under
         "Snaked_Levels".

    Args:
        world_number:  world index, 1-based (1 -> world_01).
        level_number:  level index within the world, 1-based (1 -> level_001).
        level_name:    human-readable name, e.g. "First Steps".

    Returns the level's id string (e.g. "world_01_level_001").

    Safe to run multiple times for the same world/level: existing files are
    kept and the index is not duplicated.
    """
    # Make sure the base scaffold exists first (idempotent).
    root = setup_level_files()

    level_id = _level_id(world_number, level_number)
    world_folder = _world_folder_name(world_number)
    level_folder = _level_folder_name(level_number)

    # 1. levels/world_NN/level_MMM/
    level_dir = os.path.join(_levels_dir(root), world_folder, level_folder)
    os.makedirs(level_dir, exist_ok=True)

    # 2. level.json from the template, with this level's identity filled in.
    #    (level.blend and preview.png are produced by you later, not here.)
    metadata = dict(_LEVEL_METADATA_TEMPLATE)   # shallow copy of the template
    metadata["id"] = level_id
    metadata["name"] = level_name
    metadata["world"] = int(world_number)
    metadata["level_number"] = int(level_number)
    _write_json_if_missing(os.path.join(level_dir, "level.json"), metadata)

    # 3. Register the level in the combined index (relative path so the project
    #    folder stays portable between machines).
    rel_dir = os.path.join("levels", world_folder, level_folder).replace(os.sep, "/")
    index_entry = {
        "id": level_id,
        "name": level_name,
        "world": int(world_number),
        "level_number": int(level_number),
        "path": rel_dir,
        "status": "draft",
    }
    _register_level_in_index(root, index_entry)

    # 4. Blender collection WORLD_NN_LEVEL_MMM nested under Snaked_Levels.
    #    Skipped silently when running outside Blender (no bpy available).
    try:
        import bpy  # noqa: F401  -- only present inside Blender
    except ImportError:
        print("[Levels] bpy not available -- created files only for %s. "
              "Run inside Blender to also create its collection." % level_id)
        return level_id

    coll = get_level_collection(world_number, level_number)
    print("[Levels] Ready: %s (folder %s, collection '%s')."
          % (level_id, rel_dir, coll.name))
    return level_id


# ===========================================================================
# Entry point
# ===========================================================================

def build():
    """Create the on-disk level scaffold, then (inside Blender) the empty
    "Snaked_Levels" collection.

    No levels are created here -- call create_blank_level() to stamp one out.
    """
    setup_level_files()
    try:
        import bpy  # noqa: F401  -- only present inside Blender
    except ImportError:
        print("[Levels] bpy not available -- created level files only. "
              "Run inside Blender to also create the 'Snaked_Levels' collection.")
        return
    get_levels_collection()
    print("[Levels] Foundation ready. Call create_blank_level(world, level, "
          "name) to add a blank level.")


if __name__ == "__main__":
    build()
