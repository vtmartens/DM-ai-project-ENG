# NOTES — defects found, fixed and outstanding

Recorded while translating this repository from Italian to English, and while fixing the
API bugs that the translation work uncovered.

## Outstanding

### The repository folder is still named `DM-AI-IT`

The rename to `DM-AI-EN` could not be performed in-session: Windows refuses to rename a
directory that is a live process's working directory, and this session's own shell is
sitting in it. Close Claude Code and any editor holding the project, then run:

```powershell
Rename-Item -Path "C:\Users\v_t_m\PycharmProjects\DM-AI-IT" -NewName "DM-AI-EN"
```

Nothing inside the project depends on the folder name: `.idea/modules.xml` and
`.idea/workspace.xml` already reference `DM-AI-EN`, and `README.md` documents it.

### `POST /preferences` still returns 500

`server.py` calls `session.save_preferences(...)`, which does not exist on `GameState`.
This is a **missing feature rather than a bug** — there is no preference storage anywhere
in the engine — so it was left alone rather than inventing behaviour. Either implement
preference persistence or drop the endpoint.

## Fixed, at your request — these are deliberate behaviour changes

The translation was otherwise behaviour-preserving; the following are real fixes made after
the translation, all verified by an in-process API test and by re-running the game.

1. **`POST /start` — the API was unusable.** It called `TavernState()` while the class
   required a `game` argument, so creating a game raised `TypeError` and no endpoint that
   needs a session could be reached. `BaseGameState.__init__` already makes `game` optional
   (the context is injected by `Game.push_state`), and `map_selection_state.py` calls
   `TavernState(game)` correctly — only this caller was wrong. Fixed by making
   `TavernState.__init__` accept `game=None`, matching its parent and the author's call.

2. **`GET /map` and `GET /position` — both raised.** They `jsonify`
   `Game.get_player_position()`, which returns `nearby_items`/`nearby_npcs` as
   `{(x, y): object}`. A tuple key makes Flask raise *"keys must be str, int, float, bool or
   None, not tuple"*, and the objects are not serializable either. Added a
   `_json_safe_position()` helper in `server.py`; the engine's own return value is untouched.

3. **`POST /save` reported success but wrote nothing**, so `/load` and `/saves` were dead
   too. `server.py` resolved the path with `get_save_path()` and passed the resulting
   `Path` on; `Game.save()` resolved it *again* and `get_save_path()` called `.lower()` on a
   `Path`, raising `AttributeError`. `Game.save` swallowed it and returned `False`, and the
   route ignored the return value. Fixed by coercing to `str` inside `get_save_path()` and
   `get_standardized_paths()`. The terminal game was never affected — it passes a string.

4. **`GET /item_details` raised `AttributeError: 'str' object has no attribute 'get'`.**
   It assumed each `inventory` entry of the state view is a dict with `id`/`name`, but that
   view returns plain name strings. It now resolves the player's real item objects (falling
   back to the name list) and normalises to a dict, which the rest of the handler expects.

5. **Residual Italian the first pass missed**, found by running the API and by rebuilding
   the scanner's denylist from the glossary instead of a hand-written word list:
   `--- GESTIONE INVENTARIO ---`, `Scegli:`, `Oggetti:`, two `lista` comments, the asset
   paths `/asset/oggetti/` and `oggetto_default.png`, and stale Italian direction names in
   five docstrings (`nord`/`sud`/`est`/`ovest`).

### API status after the fixes

31 endpoints return 200; **no endpoint raises**. The remaining non-200s are correct
behaviour: `400`/`404` for a missing or unknown session, and the `500` from
`/preferences` above.

## One incidental behaviour change worth reviewing

**`DataManager.get_classes()` now returns data where it previously returned `{}`.**
The registry key in `util/data_manager.py` was `"classi"`, and `load_data()` derives the
default filename from it (`f"{data_type}.json"`), so it looked for
`data/classes/classi.json`, which does not exist. Renaming the key to `"classes"` (part of
the translation) makes the derived filename `classes.json`, which does exist. Verified
live: `GET /classes` now returns the real class list.

`main.py` was never affected — it reads `data/classes/classes.json` directly. This was
**not** intended as a fix; it fell out of the rename. Revert by naming the key `"classi"`
again.

## Pre-existing defects NOT fixed

Verified against the pristine Italian snapshot; each is identical in the original, so none
of these were introduced by the translation.

1. **Ad-hoc item names that were never defined as items.** `starting_equipment` in
   `classes.json` (`Wooden Shield`, `Spellbook`, `Lockpicks`, `Holy Symbol`, `mace`,
   `shield`, `staff`), several NPC inventories (`Blacksmith's Hammer`, `Staff of Power`,
   `Ruby Gem`, `Golden Ring`, `Map of Undermountain`, `Basic Arcane Manual`), two keys'
   `opens` targets (`Royal Strongbox`, `Tower Door`) and two dialogue hand-overs
   (`Basic Arcane Manual`, `Dark Beer`) reference items that exist in no `data/items` file.
2. **The cellar's NPCs (`Specter`, `Cultist`) are not defined in `npcs.json`** at all. They
   are placed from `map_npcs.json` and fall back to defaults.
3. **`MapSelectionState` is missing from the state-restore map** in `core/game.py`. The
   duplicate map in `states/base_state.py` does include it, and the two disagree, so a save
   taken on the map-selection screen cannot be restored.
4. **Stub endpoints** reading keys the engine never emits: `/missions`, `/combat`, `/log`,
   `/notifications`, `/available_actions`. Verified returning empty or invented data.
   (`/tutorial` and `/achievements` do return real data.)
5. **Dead `"CommercioState"` branch** in `server.py`'s context lookup — no such class
   exists, so it never matches.
6. **Item effects that match no attribute** and are silently ignored: `initiative`, `luck`,
   `remove_poison`, `damage`, `duration`, `escape`. Item application goes through
   `hasattr`, so several potions and accessories are inert.
7. **`ASSETS_DIR` in `server.py` is relative to the current working directory**, unlike
   every other path, which is anchored to the repository root via `util/config.py`.
8. **`data/assets_info/` does not exist**; `get_asset_info()` always returns `{}`.
9. **`server.py` substantially duplicates** logic already in `core/`, `states/` and
   `world/`.
10. **Data/engine item-type disagreement**: `server.py` tests for `"potion"`/`"food"` but the
    engine writes `heal`, `light_heal`, `grave_heal`, `buff`, `poison`, `bomb`.
11. **`world/map_controller.py` is legacy** — a parallel, unwired copy of map logic.
12. **`GET /`'s catalogue lists `GET /asset`** while the real route is
    `/asset/<path:file_name>`; it is a documentation key only.
13. **`achievements.json` `condition.type` values are never evaluated** by any code.

## Deliberate translation choices worth knowing

- **`hp_base` / `mana_base` were left as-is.** They are consistent between code and JSON
  and read acceptably in English. The `hp_max`/`max_hp` split across two different dicts is
  pre-existing and was preserved.
- **Some class starting-equipment names are lowercase** (`staff`, `mace`, `dagger`,
  `shield`) — deliberately not capitalised, because the same bare literals appear in code
  as case-sensitive substring patterns and changing them risked breaking the equipment
  heuristics.
- **D&D canon names kept**: Durnan, Elminster, Mirt, Gundren. Descriptive Italian names
  translated: Violetta → Violet, Araldo → Herald, Spettro → Specter, Cultista → Cultist.
  (Forgotten Realms flavour text was localised too: "The Yawning Portal", "Undermountain",
  "Halaster Blackcloak".)

## Verification performed

| Check | Result |
|---|---|
| `compileall` over the tree | OK |
| Every module imports | 27 / 27 |
| Coupling tests (stat modifiers via `f"modifier_{...}"`, skill map, item dispatch, save/load round trip, state-class reload via `importlib`) | 13 / 13 |
| Interactive-object construction, incl. the content-loop path | OK |
| Equipment-name heuristics resolve | OK |
| Dialogue graph — every option target resolves | OK |
| Referential integrity (map placements, key→object, NPC inventories) | only pre-existing gaps |
| Residual Italian (glossary-derived denylist + accented characters) | 0 hits |
| **Original Italian vs translated, identical input** | **46/46 placements, identical sequence** |
| Flask API in-process (test client, no socket) | 31 × 200, 0 raised |

The last comparison is the strongest evidence: the pristine Italian code and the finished
English code place every object and NPC in exactly the same cells.
