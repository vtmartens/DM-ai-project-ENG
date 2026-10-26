# NOTES — defects found, fixed and outstanding

Recorded while translating this repository from Italian to English, and while fixing the
API bugs that the translation work uncovered.

## Outstanding

No outstanding blockers from the translation. The repository folder has since been renamed
to `DM-AI-EN`, so the earlier rename note no longer applies. Known engine/content gaps are
listed under **Pre-existing defects NOT fixed** below.

## Fixed in the test/API foundation pass (2026-10-26)

A pytest suite, `requirements.txt` / `requirements-dev.txt` and a CI workflow were added.
The pass also fixed the following, each covered by a regression test:

1. **Saving on the map-selection screen could not be restored.** `MapSelectionState` was
   absent from the restore map in `core/game.py`, although the duplicate map in
   `states/base_state.py` included it. Added the mapping.
   (`tests/test_save_load.py::test_map_selection_state_survives_a_save_load`)

2. **`POST /preferences` returned 500.** `GameState` now stores per-session preferences
   (`save_preferences` / `get_preferences`), exposes them in `/state`, and rejects a
   non-mapping payload with `400`. Preferences survive session pickling.
   (`tests/test_api.py::test_preferences_are_stored_on_the_session`)

3. **Several potions were inert.** `Item.use` handled only `heal` / `light_heal` /
   `grave_heal`, while `data/items/potions.json` also defines `buff`, `poison` and `bomb`.
   - `buff` applies its stat bonuses and consumes the item. There is still no timed-effect
     system, so the bonus does not expire; the descriptions calling these "temporary"
     remain aspirational.
   - `poison` damages the current opponent in combat and is refused (and kept) outside it.
   - `bomb` calls `CombatState._attempt_escape` with a `+5` bonus; that method now accepts
     a roll modifier.
   (`tests/test_items.py`, plus the item-type check in `tests/test_data_integrity.py`)

4. **Stub endpoints now read real engine data.**
   - `/missions` returns the player's active/completed/in-progress quests.
   - `/combat` and `/combat_action` build their response from the actual `CombatState`.
   - `/log` returns a rolling event log maintained by `GameState.process_command`.
   - `/available_actions` derives actions from the current state and targets from the
     player's real nearby items/NPCs and walkable directions; the dead `CommercioState`
     branch was replaced with `MarketState`.
   - `/npcs` returns the NPCs placed on the current map.
   `/notifications` was already backed by a real in-memory store. A sweep test asserts that
   every hit endpoint returns below 500.

5. **`/item_details` advertised `potion`/`food` types the engine never emits.** It now
   recognises `heal` / `light_heal` / `grave_heal` / `buff` / `poison` / `bomb` and
   armour/accessories.

## AI Dungeon Master vertical slice (2026-10-26)

The first AI feature is narration only. The engine remains authoritative: `ai/io.py`'s
`NarratingIO` decorator forwards every engine message immediately and unchanged, batches the
turn's narrative events, and *appends* one short DM paragraph before the next prompt. Because
nothing is replaced, menus, numbers and outcomes cannot be broken by the model. If the
feature is disabled, credentials are absent, the call times out, or the model refuses, no
paragraph is added and play continues normally.

- **Providers:** two interchangeable implementations behind `ai/narrator.py`'s protocol,
  sharing the prompt in `ai/prompts.py`:
  - `ai/claude_narrator.py` — official `anthropic` SDK, default model `claude-opus-5-5`,
    `max_tokens=1024`, `output_config.effort="low"`, server-side refusal fallback
    (`server-side-fallback-2026-06-01`, fallback `claude-opus-4-8`). `stop_reason`
    `refusal`/`max_tokens` yields no narration.
  - `ai/openai_narrator.py` — official `openai` SDK against any OpenAI-compatible endpoint
    (OpenAI, Ollama, LM Studio, vLLM, OpenRouter, Groq, local gateways). Default model
    `gpt-4o-mini`; set `DM_AI_MODEL` for local servers. `finish_reason` `length` or
    `content_filter` yields no narration.
- **Opt-in:** `DM_AI_NARRATION=1`; `DM_AI_PROVIDER=claude` (default) or
  `openai`/`openai-compatible`. OpenAI-compatible endpoints read `DM_AI_BASE_URL` (or
  `OPENAI_BASE_URL`) and `DM_AI_API_KEY` (or `OPENAI_API_KEY`). Also optional:
  `DM_AI_MODEL`, `DM_AI_MAX_TOKENS`, `DM_AI_TIMEOUT`. No flag means no wrapper and no API
  imports.
- **Context sent:** player name/class/HP, map and position, active state name, and nearby
  item/NPC names (`ai/context.py`). Inventory is deliberately excluded to keep requests small.
- **Web sessions:** `NarratingIO` drops its client from the pickle and rebuilds the narrator
  from the environment on load, so `sessions/*.pickle` stay serializable.
- **Tests:** `tests/test_narrating_io.py`, `tests/test_claude_narrator.py`,
  `tests/test_openai_narrator.py`, `tests/test_ai_factory.py`. All model calls are faked;
  the suite makes no network calls. The Claude beta request shape (`betas`, `fallbacks`,
  `output_config`) was checked against the installed `anthropic` 1.17.0 SDK.
- **Live check (local gateway):** the OpenAI-compatible adapter produced a narrated tavern
  turn in 2.2s against `deepseek-v4.1-flash:cloud` at `http://127.0.0.1:11434/v1`. The
  gateway does not serve Claude models, so the default Claude path was not live-tested
  here; that attempt confirmed the failure path (engine text only, no crash). Local
  `Qwen2.5-Coder:7b` and `:32B` also narrated correctly but took 15s and 58s per turn.

Deliberate non-goals for this slice: natural-language command parsing, AI decisions, and
conversation memory across turns. The narrator has no authority over game state.

## API contract + web client (2026-10-26)

- Added `docs/API.md` (the endpoint/session/state contract) and a dependency-free SPA in
  `frontend/` served by Flask at `/app`. No Node/bundler is required.
- The client supports character creation, resume, live log (with `narration` styled
  separately), quick actions, inventory/item details, saves (load/delete), and a
  light/dark theme persisted through `/preferences`.
- Contract fixes:
  - `/start` and `/load` now return the structured `output` and a `player` summary.
  - `/load` can create a session when none is supplied (load from the start screen).
  - `/save` returns `409` when the engine refuses to save (combat/dialogue/market).
  - `/abilities` returns real class abilities, skills and mana; `/use_ability` is an
    explicit `501` instead of pretending a command ran.
  - `/explore` and `/dialogue` return real nearby targets and dialogue options.
  - `/achievements` copies the cached catalogue before annotating it (no cross-session
    leakage).
  - `/assets_info` has a stable, empty catalogue (`data/assets_info/assets.json`);
    `ASSETS_DIR` is anchored to the repository root.
  - Import/export save filenames are sanitized and imports get unique names.
  - AI prose is tagged `{"type": "narration"}` so clients can style it separately.
- `/app` redirects to `/app/` so the client's relative `styles.css`/`app.js` load.
- Fixed the web session's off-by-one command pacing. `WebGameIO` now supplies each command
  once and raises `NeedsInput` when a state must wait for the next one;
  `GameState.process_command` runs the state until that point. A menu choice is processed
  in the same request instead of one command late (previously the first choice produced
  "I don't understand what you want to do with ''"). `TavernState` also avoids re-rendering
  the opening menu, and the client collapses repeated menu blocks.
- Fixed the log's auto-scroll. Command output was appended below the fold while the log
  stayed at the top, so a valid command such as "talk to Durnan" looked like it did
  nothing. The client now scrolls to the bottom after each batch and collapses consecutive
  duplicate prompts.
- Verified live: `/app`, `/app/styles.css`, `/app/app.js`, `/start`, `/state`,
  `/abilities`, `/inventory`, `/available_actions`, `/command`, `/save`, `/list_saves` and
  a session-less `/load` all returned the expected data. With AI narration enabled,
  `/start` emitted exactly one `{"type": "narration"}` message containing real prose.
- Verified in a real headless browser (Selenium): class selection, start, talk list,
  Durnan's dialogue options, inventory item details, and AI narration all worked with no
  empty-command errors.

## Web flow hardening (2026-10-26)

- `press_enter` is now non-blocking when `GameIO.pause_for_confirmation` is false.
  `WebGameIO` returns false (and `NarratingIO` delegates to its base), so the map-selection
  travel flow no longer stalls after "You head toward Cellar…". Terminals still pause.
- Added `GET /map_view` (ASCII grid with `P`), plus `combat` and `dialogue` snapshots in
  `/state`. The client now has a map modal, a combat card with enemy HP, and clickable
  dialogue options.
- Fixed `NPC.get_conversation` mutating the `DataManager` cached conversation. The first
  call converted options to tuples; the second call skipped them and wrote an empty list,
  so dialogue options disappeared. It now copies the node and accepts list/tuple/object
  option formats.
- Verified in a real headless browser: map modal on the tavern and cellar, travel
  (tavern → cellar), Durnan's dialogue options and clicking through to `info_tavern`,
  and a combat round with the enemy HP updating (75 → 69). 150 tests pass.

## Map tokens and legend (2026-10-26)

- Multi-character tokens (`or`, `and`, `to`) broke ASCII row widths: each cell could emit
  two or three characters. Normalized all `interactive_objects.json` and `npcs.json` tokens
  to one character, changed the code defaults to `?`, and `Map.display_token` now
  defensively falls back to the first letter of the name.
- `/map_view` returns a `legend` mapping each token to its name(s)/type(s), including
  per-name `members`; the modal and in-log legends label characters `(NPC)` so players can
  see who is interactable (D = Durnan (NPC), E = Elminster (NPC), M = Mirt (NPC), ...).
- Duplicate-placement warnings are gone: `transfer_items_from_state` keeps an existing
  object/NPC placed from JSON when the names match (case/underscore tolerant), and missing
  positions are logged at debug level.
- Added tests for single-character tokens, map-object references, row widths and legend
  entries. 152 tests pass.

## Dialogue exit and press-enter prompts (2026-10-26)

- `DialogueState` (and `AbilityCheckState` / `InventoryManagementState`) called
  `io.request_input("Press Enter to continue...")` directly before `pop_state()` or another
  state change. Under the web runner that pause raised `NeedsInput` and aborted the run
  *before* the state change, so Durnan's final `info_dungeon` option looped on the same
  node; pressing Enter produced "Please enter a valid number".
- All direct press-enter prompts now use `press_enter(game, message)`, which is
  non-blocking when `GameIO.pause_for_confirmation` is false. Choosing the final dialogue
  option now exits to the tavern immediately (no Enter step) on the web.
- Client assets now carry a `?v=6` query so a reload picks up the current JS/CSS (including
  the dialogue card, map rendering and NPC legend labels) instead of a stale cached copy.
- Added a regression test for the `info_dungeon` exit path. 155 tests pass.
- The in-game “9. Display map” view now emits a `map` message type, rendered in the log with
  the same monospace font and `white-space: pre` as the modal (the proportional log font
  made periods and letters different widths). The block also expands to all rows; an
  `overflow-x: auto` scroll container had clipped it to a single line. The in-log legend is
  generated from the real map tokens (`S = Chair`, `T = Table`, ...) instead of the old
  generic token list.

## Natural-language targeting + browser CI (2026-10-26)

- `TavernState` now parses targeted free-text commands: `talk/speak/chat/converse`, `attack/fight/hit/kill/challenge`, `use/drink/quaff/consume`, `equip/wield/wear`, `go/travel/walk/head`, `examine/inspect/look at/check`, and `interact with/open/pull/push`.
- Targets are resolved deterministically against the state's NPCs, the current map's NPCs, the player's inventory, map names, and map objects. Matching is case/article tolerant and tries exact, prefix, then substring.
- `talk to Durnan` starts his dialogue directly; `attack Durnan` starts combat; `use Healing Potion` consumes it; `go to the market` changes map; `examine chair` prints its description; `interact with barrel` requires adjacency and calls its interaction.
- Unknown targets print a message and fall back to the normal menu (talk list, inventory, map selection, etc.). No AI is involved; the engine stays authoritative.
- Added `tests/test_web_browser.py`: starts the Flask app on a random port in a thread and drives the client with headless Chrome (CI) or Edge (local), checking start, `talk to Durnan`, the dialogue card, and the map modal. `requirements-dev.txt` now includes `selenium`.
- Added API tests for talk/travel/use/attack/examine and the unknown-target fallback.
- Map movement is now phase-based (`main_menu` / `move` / `interact`) instead of nested
  `request_input` calls, so the web runner can consume the movement menu correctly. The map
  redraws after each move with the new `P`; direction words (`south`, `move east`) work from
  the map menu. `TavernState`/`MarketState` always push a fresh `MapState` with the right
  initial phase (their old `open`/`move`/`interact` lookups did not exist). Web sessions skip
  the terminal y/n prompt when walking through a door.
- The targeting parser/resolver now lives in `states/commands.py` and is shared by
  `TavernState` and `MapState`, so “talk to Durnan” works from the map screen too. Unknown
  targets stay on the map menu.
- Added direct approach to NPCs/objects: `go/walk/move/approach to <name>` runs a BFS from the
  player to any free adjacent cell, respecting walls, items, NPCs and doors, then moves the
  player there in one command. It works from the tavern hub, the map menu and the movement
  submenu; the map redraws at the new position. Already-adjacent targets report rather than
  move.
- Added movement/targeting/approach regression tests. 169 tests pass.

## Character stats and mana (2026-10-26)

- The sidebar displayed effective modifiers (`INT 4`) while the class preview displayed base
  scores (`INT 16`), which looked like a mismatch. `/state` now also exposes
  `strength_base`…`charisma_base`; the client shows the base score with the effective
  modifier, e.g. `INT 16 (+4)`. The parenthetical can include equipped gear.
- `Player.__init__` read `mana_base` from `base_stats`, where it does not exist, so wizards
  and clerics started with 0 mana while the class preview showed 20/10. It now reads the
  top-level `mana_base` from the class data. `Player.from_dict` also restores saved
  `mana`/`mana_max` (previously they were serialized but not loaded).
- Added API and save/load tests for base stats, modifiers and mana. 171 tests pass.

## Narration ordering (2026-10-26)

- `NarratingIO` used to forward each engine message immediately and append the DM paragraph
  at the next prompt, so the DM prose appeared *after* the NPC dialog and options list. It
  now buffers the turn's narrative messages and, at flush, emits the DM paragraph first,
  followed by the engine text unchanged. System/error messages flush the same way. If the
  narrator is unavailable, the engine messages are emitted unchanged.
- The play area is ordered Adventure log (with the DM narration first) → NPC
  dialogue/options card → combat card → item panel. When a dialogue is active, the log
  scrolls to the latest DM paragraph; focusing the command input uses `preventScroll` so the
  layout does not jump. Client assets are at `?v=11`.
- Updated the narration-order tests and API docs. 171 tests pass.

## Map exits (2026-10-26)

- Map-only doors were invisible: the ASCII renderer ignored `map.doors`, and a door placed
  on a wall cell was unreachable because the wall check ran before the door check. The map
  now renders `>` for a map door without an interactive object, and the legend adds
  `> = Exit to <map>`. `MapManager.move_player` checks doors before walls.
- Fixed two broken destinations: tavern→market now lands at `(12, 2)` (previously `(12, 1)`,
  which is occupied by the market's tavern-door object), and market→tavern lands at
  `(12, 13)` (previously `(12, 15)`, outside the tavern's 15-row grid). The
  cellar↔market doors were already valid.
- On web, passing a door now enters `MarketState` / `TavernState` directly (the cellar has
  no dedicated state, so it stays in `MapState`). `MarketState` preserves a valid arrival
  position instead of resetting to its start tile, so the tavern exit lands at `(12, 2)`
  with the market menu shown.
- Added `go to exit` / `leave`: pathfinds to the nearest map door, steps through it, and
  enters the destination state (market/tavern; cellar stays in MapState). This makes leaving
  the tavern one command instead of walking the grid manually.
- Added tests for the visible exit, walking through it, the state transition, and the
  `go to exit` / `leave` commands. 177 tests pass.

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
6. **`Personaggi:` in the map's “Show nearby elements” list** (`states/map_state.py`) was
   still Italian. The earlier scanner had the singular `Personaggio` but not the plural.
   Changed to `Characters:` and covered by a regression test.

### API status after the fixes

Every endpoint returns below 500 under the test suite's sweep; the remaining non-200s are
correct behaviour (`400`/`404` for a missing or unknown session). The former `500` from
`/preferences` is fixed — see the foundation-pass section above.

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
3. ~~**`MapSelectionState` is missing from the state-restore map** in `core/game.py`.~~
   Fixed in the foundation pass above.
4. ~~**Stub endpoints** reading keys the engine never emits: `/missions`, `/combat`, `/log`,
   `/notifications`, `/available_actions`.~~ Implemented in the foundation pass above.
5. ~~**Dead `"CommercioState"` branch** in `server.py`'s context lookup.~~ Replaced with
   `MarketState` in the foundation pass.
6. **Some item effect keys still match no attribute**: `initiative`, `luck`,
   `remove_poison`, and poison `duration` (poison damage and bomb escape now work). Item
   application goes through `hasattr`, so those specific effects remain inert.
7. ~~**`ASSETS_DIR` in `server.py` is relative to the current working directory.~~ Anchored
   to `BASE_DIR` in the API contract pass.
8. ~~**`data/assets_info/` does not exist**; `get_asset_info()` always returns `{}`.~~
   Added a stable empty catalogue and a typed lookup.
9. **`server.py` substantially duplicates** logic already in `core/`, `states/` and
   `world/`. Still open; the API contract pass only removed the worst fabricated data.
10. ~~**Data/engine item-type disagreement**: `server.py` tests for `"potion"`/`"food"`.~~
    Fixed in the foundation/contract passes.
11. **`world/map_controller.py` is legacy** — a parallel, unwired copy of map logic.
12. ~~**`GET /`'s catalogue lists `GET /asset`** while the real route is
    `/asset/<path:file_name>`.~~ Fixed in the foundation pass.
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
| `pytest` suite (imports, state stack, save/load, items, data integrity, API, AI narration, web client routes, browser smoke) | 177 passed |
| Live smoke test (Flask server, `/app`, start/state/abilities/inventory/actions/command/save/load) | passed |

The last comparison is the strongest evidence: the pristine Italian code and the finished
English code place every object and NPC in exactly the same cells.
