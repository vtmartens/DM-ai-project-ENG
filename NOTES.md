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

1. **Some ad-hoc item names were never defined as items.** `starting_equipment` in
   `classes.json` (`Wooden Shield`, `Spellbook`, `Lockpicks`, `Holy Symbol`, `mace`,
   `shield`, `staff`), several NPC inventories (`Blacksmith's Hammer`, `Staff of Power`,
   `Ruby Gem`, `Gold Ring`, `Map of Undermountain`, `Basic Arcane Manual`), two keys'
   `opens` targets (`Royal Strongbox`, `Tower Door`) and two dialogue hand-overs
   (`Basic Arcane Manual`, `Dark Beer`) reference items that exist in no `data/items`
   file. The lock pass resolved the lock-related chain — Warehouse Door/Warehouse Key,
   Cellar Key/Cellar Door, Rusty Key/Treasure Chest — but the non-lock names above remain.
   The Sealed Vault chain (Vault Key, Sentinel Key, Sentinel's Edge) is defined as well.
2. ~~**The cellar's NPCs (`Specter`, `Cultist`) are not defined in `npcs.json`** at all.~~
   Fixed in the locks pass: both now have real definitions and stats.
3. ~~**`MapSelectionState` is missing from the state-restore map** in `core/game.py`.~~
   Fixed in the foundation pass above.
4. ~~**Stub endpoints** reading keys the engine never emits: `/missions`, `/combat`, `/log`,
   `/notifications`, `/available_actions`.~~ Implemented in the foundation pass above.
5. ~~**Dead `"CommercioState"` branch** in `server.py`'s context lookup.~~ Replaced with
   `MarketState` in the foundation pass.
6. **One item effect key still matches no attribute**: `luck`. `initiative`,
   `remove_poison` and poison `duration` were implemented in later passes (accessories
   recalculate initiative, antidotes clear poison, and poison carries a duration), so the
   earlier note listing them as inert is stale. Item application still goes through
   `hasattr`, so an unknown future key remains inert rather than crashing.
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
13. ~~**`achievements.json` `condition.type` values are never evaluated** by any code.~~
    Implemented — see the achievements section below.

## Achievements (2026-10-26)

`/achievements` previously always reported `unlocked: 0` because `GameState` never
emitted an `achievements` key. The feature is now backed by real tracking:

- `core/achievements.py` records gameplay events on the player and evaluates every
  condition type used by the catalogue (`movement`, `combat_victory`,
  `unique_items_collected`, `areas_visited`, `equip_item`, `coins`,
  `combat_without_damage`, `quest_without_combat`). Unknown types stay locked rather than
  raising, so future catalogue entries cannot break play.
- Events are emitted from the existing systems: map movement and transitions, combat
  victory/defeat and damage taken, item pickups and equips, gold gains, and quest
  completion. `Item` gained an optional `rarity` (default `common`) so `weapon_master` can
  be evaluated; `Dragonbane` is a new legendary weapon carried (and dropped) by Vargas.
- `Player` persists `achievements`, `achievement_timestamps` and `achievement_stats` in
  `to_dict`/`from_dict`, so both terminal saves and web session pickles keep progress.
  Older saves load with empty progress. Unlocks print once and are deduplicated.
- `diplomacy` needed a quest that can finish without fighting, so a small side quest,
  **A Word of Warning** (`violet_warning`), was added: accept it from Violet in the market
  and deliver her warning to Mirt in the tavern. A fight while the quest is active is
  counted per quest (`progress_quests[id]["combat_encounters"]`) and prevents the unlock.
- `test_data_integrity` now allows dialogue-completed quests to omit `target`.
- Fixed while wiring this up: `NPC.get_conversation` dropped the optional third element of
  each option (the visibility condition), so every quest-gated dialogue option was always
  shown. It now preserves conditions and `DialogueState.visible_options` filters correctly.
- Tests: `tests/test_achievements.py` covers each condition, deduplication, save/load,
  the `/achievements` API, and the Violet → Mirt dialogue route. 258 tests pass (including
  the headless-browser smoke test).
- Web client: the sidebar has an Achievements card driven by `GET /achievements`, showing
  the unlocked/total count, score, description and unlock date, with locked entries styled
  as goals. New unlocks also raise a toast. The browser smoke test asserts the panel
  renders and the count badge is populated.

## Utility spells (2026-10-26)

The ability engine previously only understood combat effects, so fighters, rogues and
wizards had no out-of-combat class abilities.

- `core/abilities.py` now also supports `knock`, `mage_hand` and `guidance`, and exposes
  `usable_in_combat` in `GET /abilities` (false for utility spells). Utility spells are
  refused inside combat and do not spend mana when there is no valid target.
- **Knock** (wizard, 5 mana): opens the nearest locked door or chest within two steps
  without consuming a key. `Chest.force_open` / `Door.force_open` temporarily bypass
  `requires_key` and reuse the normal `interact` path, so chest loot is still awarded and
  the lock remains locked for later interactions.
- **Mage Hand** (rogue, 2 mana): operates the nearest door, chest or lever within two
  steps. It cannot bypass a lock without a matching key.
- **Guidance** (cleric, 2 mana): stores `{"guidance": {"bonus": 2}}` in the player's
  persisted conditions. The next ability check (base, NPC or object mode) consumes it and
  adds the bonus to the roll; casting it again does not stack.
- `states/ability_check.py` now rolls through `_roll_with_guidance`, which consumes the
  bonus and prints it. This also fixed a pre-existing bug: all three check modes called
  `player.ability_modifier(name)` without the required `game` argument, so choosing a
  specific skill (Perception, Persuasion, ...) raised `TypeError`.
- Tests: `tests/test_abilities.py` covers each spell, range/target refusal, the lock
  bypass, Guidance consumption and the combat restriction; `tests/test_api.py` covers
  `usable_in_combat`, `POST /use_ability` with Guidance and Knock opening a chest through
  the API. 272 tests pass.

## Locked doors and routes (2026-10-26)

Keyed doors previously never blocked map travel: `MapManager.move_player` only read
`map.doors`, and direct travel (`go to <map>`, the map-selection menu) bypassed doors
entirely. The doors that existed were also misaligned with the map exits.

- `MapManager.move_player` now refuses to step onto a transition whose cell holds a
  `Door` with `requires_key` and a state other than `open`.
- `MapManager.prepare_map_entry` checks every physical route into a destination. If all
  routes are locked, a matching key in the player's inventory opens one and travel
  proceeds; otherwise the command is refused with a message. `change_player_map` and
  `MapSelectionState._change_map` both use it, so walking and fast travel share one rule.
- Content:
  - **Warehouse Door** at market `(20, 7)` (requires a key) and a **Warehouse Key**
    (`opens: ["Warehouse Door"]`). Violet hands over the key when her quest is accepted;
    the key is also added to old saves that already have the quest. Wizards can Knock the
    door open instead.
  - **Tavern cellar door** at `(22, 9)` now has a real transition to cellar `(18, 8)`;
    cellar `(18, 7)` leads back to tavern `(22, 8)`. The market↔cellar route `(14, 5)` /
    `(1, 7)` stays open, so the Cellar Key found in the cellar's hidden chest is the
    optional shortcut back into the tavern.
  - **Treasure Chest** at tavern `(2, 2)` with the Rusty Key (`opens: ["Treasure Chest"]`),
    giving the existing key a real target.
  - **Specter** and **Cultist** now have definitions in `npcs.json` (NOTES defect 2).
- Save/load fix: `Map.from_dict` used `InteractiveObject.from_dict` for every saved
  object, so doors, chests, levers and traps came back as plain objects without
  `requires_key`/`force_open`. It now dispatches to the correct subclass.
- `transfer_items_from_state` now points the state's `interactive_objects` entries at the
  map instances when a matching object is already placed, so menu interactions and map
  movement share one door/chest.
- Dialogue hand-overs (`add_item`) now give the NPC's actual item object. Passing the name
  meant non-potion items such as the Warehouse Key became raw strings in the inventory.
- Tavern/market/ability-check interactions now pass `game` to `interact`/`describe`, so
  lock, loot and state messages are shown.
- Tests: `tests/test_locks.py` covers blocked movement, Cellar Key, Knock, warehouse
  fast-travel gating, Violet's key hand-over, door save/load and the Rusty Key.
  `tests/test_quests.py` covers the end-to-end warehouse route. 285 tests pass.

## Accessibility and mobile pass (2026-10-26)

- **Modals** (`#load-modal`, `#map-modal`): opening one now captures the trigger, moves
  focus to the first control, traps Tab/Shift+Tab inside, marks the topbar, main content
  and skip links `inert`, and locks background scrolling. Closing (button, backdrop or
  Escape) restores focus to the trigger.
- **Navigation**: added “Skip to content” and “Skip to command input” links, a labelled
  `<main>`, sidebar and play-area landmarks, and an action-oriented `aria-label` on the
  theme toggle.
- **Contrast**: `--text-faint` failed WCAG AA in both themes (dark 4.05:1, light 3.75:1
  against cards). It is now `#7f8ea3` dark (4.98:1) and `#75675a` light (5.26:1). All text
  tokens were checked against every background token at 4.5:1 or better.
- **Mobile**: below 980px the play area now comes first, so the log and command input are
  visible without scrolling past the sidebar. Below 640px, buttons/inputs get 44px touch
  targets and modals use tighter padding. The layout has no horizontal page scroll at
  390×844.
- **Tests**: `tests/test_accessibility.py` checks the contrast ratios and static landmark,
  skip-link and dialog semantics; `tests/test_web_browser.py` adds a keyboard focus-trap
  test and a 390×844 mobile test (no horizontal scroll, command input above the fold,
  44px targets, theme label, modal bounds). 290 tests pass. Client assets are at `?v=20`.

## Dungeon Master hints (2026-10-26)

- `core/hints.py` builds a deterministic hint from the current state, in priority order:
  combat target (and low HP), active dialogue, quest ready to turn in, a locked door within
  two steps (naming a held key when possible), active quest objective, low HP with/without a
  healing item, a nearby NPC, a nearby object, then a generic exploration fallback.
- `ai/hints.py` optionally asks the narrator to rephrase the engine hint. `Narrator` gained a
  `hint` method; `NullNarrator` returns `None`. The Claude and OpenAI-compatible adapters
  share a `_complete` helper, use a dedicated hint system prompt, and cap hint output at 256
  tokens. Any error, refusal, `max_tokens`/`length` or empty response falls back to the
  engine hint.
- `POST /hint` returns `{"hint", "source": "engine"|"ai"}` and appends the hint to the
  session's event log (`type: "hint"`). It never changes game state. AI hints reuse the
  existing `DM_AI_NARRATION` narrator/provider configuration; without it the endpoint still
  works with engine wording.
- The web client gained a **Hint** button in the log actions and a blue `hint` log style.
- Tests: `tests/test_hints.py` covers quests, locked doors/keys, low HP, combat, dialogue,
  determinism, no state changes and AI fallbacks; provider tests cover the new `hint`
  request shape and failures; API tests cover engine/AI sources, logging and errors; the
  browser smoke test clicks Hint and asserts the log entry. 318 tests pass.

## Sealed Vault phase 1 (2026-10-26)

- New `vault` map beneath the warehouse, reached through a **Vault Door** at warehouse
  `(18, 2)` and returning via the **Vault Exit** to warehouse `(17, 2)`.
- **Warehouse Key** now also opens the **Sealed Strongbox** at warehouse `(16, 9)`, which
  holds the **Vault Key**. The old-save quest migration upgrades an existing Warehouse Key
  so the strongbox works without a new game; session loading runs the same migration for
  existing web sessions.
- Inside: the hostile **Iron Sentinel** at `(13, 5)` carries the **Sentinel Key**; the
  **Relic Chest** at `(16, 5)` needs that key and contains **Sentinel's Edge** (rare,
  strength +6) and a Greater Healing Potion. A **Rune Pillar** provides the in-world clue.
- **Reachability fix**: the old fast-travel check considered every route in the world, so
  the vault's open exit made the warehouse reachable from the tavern without any key.
  `MapManager.prepare_map_entry` now BFS-searches outward from the player's current map,
  treats a locked route as passable only when its key is carried, and opens the final keyed
  door when travel succeeds.
- Hints now cover locked chests as well as doors, so the strongbox names the Warehouse Key.
  NPCs also expose their `friendly` flag, so hints warn about a hostile guardian instead of
  suggesting a chat.
- Tests: `tests/test_vault.py` covers the map/guardian placement, blocked vault movement,
  the strongbox→Vault Key→Vault Door chain, direct travel, the vault-exit bypass regression,
  the guardian drop, relic loot and save/load. 330 tests pass.

## Sealed Vault phase 2 — the quest wrapper (2026-10-26)

- **The Sentinel's Sigil** (`sentinel_sigil`): Mirt asks for **Sentinel's Edge** from the
  vault. Rewards are 100 gold, 200 XP and the new **Vault Warden's Signet** accessory
  (defense +1, wisdom +1). The offer is shown when the Shadows quest is active, ready or
  completed, so the player has Violet's warehouse-key thread.
- Item-based progress: `core/quests.py` gained `record_item_acquired`, called from
  `Entity.add_item`. An active quest with a matching `target_item` becomes ready as soon as
  the item is picked up (including chest loot). `start_quest` also checks the inventory, so
  accepting the quest after recovering the relic marks it ready immediately.
- `complete_quest` now supports `reward.items`, building defined items from the data files
  and adding them through `player.add_item` (so achievements and item quests still fire).
- Mirt's dialogue has offer, reminder, ready turn-in and completed nodes, using the
  quest-conditioned options fixed earlier.
- Tests: item progress, out-of-order start, reward items, Mirt option visibility, save/load
  and the vault-chest integration; 336 tests pass. Phase 2's optional rune ability check
  and a dedicated achievement remain future work.

## Enemy abilities and encounter variety (2026-10-26)

- `data/monsters/abilities.json` now defines data-driven enemy abilities; monsters and
  NPCs reference them through an `abilities` id list. Effects support attack damage,
  poison, self-heal, a temporary guard, and pure healing, with an optional telegraph.
- `core/enemy_abilities.py` loads definitions and chooses the first useful off-cooldown
  ability (heals are skipped at full health).
- `CombatState` tracks per-enemy cooldowns and guard values, ticks cooldowns at the start of
  each enemy phase, falls back to a basic attack, and exposes the ability messages in the
  combat log. A guard absorbs the next physical hit; cooldowns/guards survive the combat
  state round trip and are cleared when the enemy falls.
- Assigned abilities: goblin *Poison Arrow*, orc and Iron Sentinel *Shield Bash*, wolf and
  troll *Savage Bite*, skeleton *Bone Volley*, cultists *Dark Bolt*, specter *Spectral
  Touch*, Vargas *Dirty Trick*, Iron Sentinel *Repair*.
- Tests: `tests/test_enemy_abilities.py` covers loading, damage/poison, cooldowns and
  fallback, Spectral Touch, Shield Bash guard, Repair selection, basic attacks, and the
  state round trip; data-integrity tests validate definitions and references. 348 tests
  pass. Encounter tuning remains playtest work.

## Curated encounters (2026-10-26)

- `data/monsters/encounters.json` defines named groups (Goblin Scouts, Orc Patrol, Bone
  Pack, Wolf Pack) with a title, description, difficulty, enemy specs and a completion
  reward. An enemy spec can reference a monster type or an NPC, so story encounters can use
  the same builder later.
- `core/encounters.py` validates/builds the live enemies. The tavern's fight menu gained
  option 8, “Fight a curated encounter”, which lists the catalogue and starts the selected
  group; the existing options (including the goblin pair) are unchanged.
- `CombatState` carries encounter metadata (without the enemy objects) and grants the
  reward exactly once when every enemy falls. The bonus is paid on top of enemy loot/XP;
  defeat and fleeing grant nothing. Encounter metadata and the rewarded flag survive the
  combat-state round trip.
- Balance guardrails in `tests/test_encounters.py` check group size, total HP, ability
  coverage and positive rewards; they are a safety net, not a substitute for playtesting.
- Tests: construction/metadata, victory reward, no reward on defeat, serialization, the
  tavern menu end to end and data integrity. 357 tests pass.

## Saving throws and advantage (2026-10-26)

- `util.dice.roll_d20(advantage, disadvantage)` rolls two d20s and keeps the high/low die;
  both flags cancel. Both dice are shown in the log.
- `Entity.ability_check` and `Entity.saving_throw` use the helper and read
  `advantage`/`disadvantage` (or `check_*`/`save_*`) from `player.conditions`; saving throws
  show the roll, ability modifier, DC and success/failure. `AbilityCheckState` uses the same
  roll helper, so Guidance and condition advantage compose.
- Enemy abilities gained optional `save` blocks: Poison Arrow CON 12, Shield Bash DEX 13,
  Dark Bolt WIS 12, Dirty Trick CON 12 and Bone Volley DEX 12. A successful save halves
  damage (`success: "negate"` is also supported) and prevents poison; the enemy's own
  self-heal/guard still applies.
- Data-integrity tests validate save ability/DC/success values; tests cover advantage/
  disadvantage, save DCs, poisoning on failure, half damage, guard interaction and ability
  checks. 366 tests pass. Attack rolls/AC and a general condition UI remain future work.

## Combat status UI (2026-10-27)

- `GET /state` now exposes `conditions` (poison, Guidance, advantage/disadvantage, etc.).
- `GET /combat` and command `state.combat` snapshots now include the player's `conditions`
  and, for each living enemy, its physical `guard` and active ability `cooldowns`
  (`id`, display `name`, `remaining` rounds). Dead enemies report empty status.
- The web client gained a Conditions card (colour-coded tags for poison duration/damage,
  Guidance, advantage and disadvantage) and status tags under each enemy's HP bar for guard
  and cooldowns. Both update after every action and use the existing live regions.
- Tests: API coverage for conditions, guard and cooldown serialization; a browser test that
  starts a goblin fight, waits for the Poison Arrow cooldown tag, formats conditions, and
  checks Guard/cooldown tags. 369 tests pass. Client assets are at `?v=22`.

## AI conversation memory (2026-10-27)

- `NarratingIO` keeps a bounded `memory` of recent engine events and non-numeric player
  actions. Menu options, prompts and combat/state stat lines are filtered out, entries are
  truncated to 240 chars, and the default limit is 8 (`DM_AI_MEMORY_TURNS`, clamped 0–20;
  `0` disables).
- `ai/context.py` adds `context.recent` for narration and hints. The narration and hint
  system prompts tell the model to use it for continuity without repeating or contradicting
  it. Hints receive the session IO's memory through `POST /hint`.
- Memory is added after a turn is narrated, so it contains prior turns while the current
  events are still sent separately. It survives web-session pickling; terminal runs keep it
  in process memory only.
- Tests: accumulation and prompt context, menu/state filtering, the cap, disabling memory,
  pickle round trip, and hint-memory propagation. 375 tests pass.

## Timed conditions (2026-10-27)

- `data/conditions/conditions.json` defines **burning** (3 damage per combat round, DEX 12
  save to end), **frightened** (disadvantage on checks/saves, WIS 12 save to end) and
  **weakened** (-2 weapon damage, CON 12 save to end).
- `core/conditions.py` applies/refreshes conditions, ticks damage/healing, makes save-to-end
  checks, expires them, and exposes their roll flags and damage modifiers. Poison remains
  handled by `CombatState` and is skipped by the generic tick, so it is never applied twice.
- `CombatState._phase_end_turn` ticks conditions each round. `_manage_attack` applies
  weakened's damage penalty, and `Entity.roll_flags` merges frightened's disadvantage.
  Conditions are applied by enemy abilities on a failed save (or on a hit for abilities
  without a save): Dark Bolt → frightened, Shield Bash → weakened, young dragon Flame
  Breath → burning.
- Conditions live in the existing `player.conditions` map, so they persist through saves and
  the Conditions panel renders them (`Burning · 3 turns`, `Frightened · 2 turns`,
  `Weakened · 2 turns`).
- Tests: apply/refresh, tick damage and expiry, save-to-end, disadvantage, weapon-damage
  reduction, ability application, end-of-turn ticking, persistence and data integrity.
  Non-combat duration ticking remains future work; the tavern rest now clears conditions.

## Tavern rest loop (2026-10-27)

- Tavern menu option 14, **Rest at the inn (10 gold)**, plus natural-language `rest`,
  `sleep`, `recover` and `nap`.
- `TavernState._rest` refuses without charging when HP and mana are full and there are no
  conditions. With less than 10 gold it refuses and reports the shortfall. Otherwise it
  charges 10 gold, restores HP and mana to maximum, and clears every entry in
  `player.conditions` — poison, Guidance, advantage/disadvantage and timed
  burning/frightened/weakened — naming what was cleared in the log.
- `GET /available_actions` now has a TavernState action list led by `rest`, so the web
  client renders a Rest quick action.
- Tests: full/partial recovery, mana restoration, condition clearing and labels, natural
  language, insufficient gold, already-rested, and the advertised action.

## Attack rolls and armor class (2026-10-27)

- Player, enemy and ally weapon attacks now roll `d20 + attack bonus` against AC. The
  combat log shows both dice when advantage/disadvantage applies, the bonus, total and
  target AC. A natural 20 is a critical hit (double damage); a natural 1 always misses.
- `Entity.armor_class` is `10 + Dexterity modifier + defense`. Player AC therefore includes
  base defense, armor and levels; monsters declare an explicit `stats.ac` in
  `data/monsters/monsters.json`. `defense` still reduces damage after a hit, preserving the
  existing armor behaviour.
- Enemy abilities that call for a save keep resolving through the save (and cannot crit).
  Non-save abilities such as Spectral Touch and Savage Bite use an attack roll. Class
  abilities and spells continue to resolve through their own effects.
- `GET /state` exposes `stats.ac` and `stats.attack_bonus`; `GET /combat` and `/state`
  include each enemy's `ac`. The web client's stats panel shows AC and Attack, enemy rows
  show AC, and combat output shows the roll line. Asset version bumped to `v=24`.
- Tests: AC calculation, player hit/miss, natural 20 criticals, natural 1 misses,
  advantage, enemy attacks against player AC, non-save enemy ability misses, API exposure,
  monster data integrity, and deterministic updates to the existing combat tests.

## Defeat and recovery (2026-10-27)

- Reaching 0 HP no longer leaves the player at 1 HP in the middle of the map. Combat ends,
  the state stack is replaced with a fresh `TavernState`, and the player is placed at the
  tavern's start position.
- Recovery restores half of maximum HP and mana (at least 1 HP), clears every condition,
  and charges up to 20 gold (`CombatState.DEFEAT_GOLD_LOSS`). With less gold, the loss is
  capped at the current purse. The log reports the defeat, the wake-up, the charge and the
  partial recovery; the normal tavern menu follows.
- Quest progress, opened routes, defeated NPCs and other map state are untouched, so the
  player can rest for full HP or return to the fight. The welcome message is suppressed for
  the recovery visit.
- `Game.reset_to_state` clears the old stack (avoiding a stale map or combat state below the
  tavern) and enters the replacement state. The API response reports `TavernState` and the
  new position immediately.
- Tests: unit recovery, gold capping, condition clearing, quest preservation, tavern
  position, and the API transition.

## Defend and Aim combat actions (2026-10-27)

- Added combat menu options **7. Defend** and **8. Aim**, plus natural-language
  `defend`/`dodge`/`block` and `aim`/`focus`. Option 6 remains target selection, so existing
  controls and tests keep their numbering.
- Defend sets a `defend` effect: incoming enemy attacks roll against +4 AC, and the attack
  log shows `(defending)`. The effect lasts through the enemy phase and is cleared at the end
  of the round.
- Aim sets an `aim` effect; the next player weapon attack is rolled with advantage (using
  two dice and the better result), then the effect is consumed. It does not affect class
  abilities.
- `/available_actions` now advertises `defend`, `aim`, abilities and equipment changes for
  combat. `GET /combat` and `/state` expose `effects.defending` and `effects.aiming`; the web
  combat card renders the active status tags. Asset version bumped to `v=25`.
- Tests: defend AC bonus and expiry, aimed advantage and consumption, API action exposure,
  and the browser status tags.

## Session recap (2026-10-27)

- `ai/recap.py` builds a deterministic recap from the player's name/class/level, map,
  HP/mana, gold, active and completed quests, conditions, defeat count and the freshest
  recent events. It filters menus, prompts, stat lines and prior recap/hint entries.
- `POST /recap` returns `{"recap", "source"}`. With narration enabled, the configured
  narrator is asked to rewrite the same facts; failures, refusals and missing narrators
  return the engine text with `source: "engine"`. Recaps never change game state and are
  appended to `/log` with `type: "recap"`.
- Added `Narrator.recap` to the protocol, `NullNarrator`, both providers, and a dedicated
  recap prompt. Added a `defeats` counter to `Player` (persisted and shown in the recap).
- The web client has a **Recap** button next to Hint and renders the result as a “Previously”
  log entry. Asset version bumped to `v=26`.
- Tests: deterministic state/quest/condition/defeat/recent summaries, AI rephrasing and
  failure fallback, empty recent history, endpoint behavior/logging, and provider request
  shapes.

## Equipment economy (2026-10-27)

- `data/items/shop_stock.json` lists the market's weapons, armor, accessories and potions.
  `core/shop.py` loads the stock, describes effects, buys at the listed value, and sells
  non-equipped inventory items for half value. Equipped items must be removed first.
- Market menu option 1 is now **Browse the shop**; the numbered list uses the same buy path
  as `buy <item>` and the web shop modal. The old buy-potion phase remains as a compatibility
  wrapper for a Healing Potion.
- Added `GET /shop`, `POST /shop/buy` and `POST /shop/sell`, all restricted to
  `MarketState`. Responses include engine output, updated state, success flags, messages and
  the refreshed stock/sell lists.
- The web client shows a **Shop** button in the market and a focus-trapped modal with Buy
  and Sell lists. Purchase/sale output goes to the adventure log; inventory and stats
  refresh immediately.
- Fixed equipment stat application: `Item.equip`/`remove` now apply and reverse every
  numeric effect, not only weapon Strength and armor Defense. Weapon/armor Dexterity,
  Intelligence and other bonuses therefore update AC, saves, initiative and attack
  calculations, and `Player._equipment_stat_bonus` preserves them across level-ups and
  save/load. The starting Healing Potion's value now matches the item catalogue (25 gold).
- Tests: stock integrity and pricing, buying/refusal, selling/equipped refusal, full
  equipment effects and AC/attack updates, save round trip, API buy/sell and market-only
  restrictions, direct buy commands, terminal sell flow, and the browser Shop modal.

## Road and wilderness encounters (2026-10-27)

- Added the `road` outdoor map east of the market: market `(33,7)` ↔ road `(23,7)`, with
  the player entering at `(2,7)`. The map loads through the normal JSON map pipeline, so
  `/map_view`, travel commands and the web map legend work without special cases.
- `core/wilderness.py` defines the road encounter chance (30%), a two-step grace period
  after entering the map, and a three-step cooldown after a fight. Encounter choice uses the
  existing curated encounter definitions; Orc Patrol is added at level 3+ while lower levels
  see Goblin Scouts and Wolf Pack.
- `MapState` rolls after a successful road step (not on other maps), pushes a
  `CombatState` with the encounter metadata and recruited allies, and persists the cooldown
  through save/load. `MapState` uses `encounter_cooldown` so existing maps are unaffected.
- Added `core/loot.py` and `data/monsters/loot_tables.json`. Road encounters carry
  `loot: true`; defeated enemies roll their table with `CombatState.dice_d100`, and dropped
  items are added to the inventory with a log message. Non-road encounters do not roll loot,
  so existing fight rewards and tests are unchanged.
- Added `core/item_catalogue.py` as the shared item-definition lookup used by both the shop
  and loot tables.
- Tests: map connection, deterministic encounter triggering, grace/cooldown sequencing,
  level-gated encounter tables, road-only loot, non-road no-loot behavior, API travel to the
  road, loot-table integrity and road encounter id integrity.

## The Broken Waystation (2026-10-27)

- Added the `waystation` map at the far end of the Trade Road (`road (21,7)` ↔
  `waystation (1,7)`), plus a `WaystationState` menu with confront, strongbox, campfire rest
  and leave actions. The state is included in save/load state restoration.
- Added the `Waystation Chief` and `Waystation Bandit` monsters, a `cheap_shot` bandit
  ability, and the fixed `waystation_chief` encounter (chief + two bandits). The encounter is
  marked `location: "waystation"`, so the tavern's curated encounter list excludes it.
- Victory marks `waystation` in `player.cleared_areas`; the cleared strongbox grants the
  unique **Wayfarer's Cloak** plus 50 gold once, tracked in `player.claimed_rewards`. The
  cleared campfire is a free full HP/mana/condition reset.
- Added Mirt's **Trouble on the Trade Road** quest. Dialogue visibility now supports
  `not_started`, and defeating the chief marks the quest ready for turn-in.
- Added 9 tests covering map/encounter data, boss victory and quest readiness, unique loot,
  campfire recovery, uncleared refusals, Mirt's dialogue options, leaving for the road,
  persistence, and the API fight flow.

## Bounty board (2026-10-27)

- Added three repeatable data-driven bounty quests to `data/quests/quests.json`: Goblin
  Toll (2 goblins), Wolf Cull (2 wolves) and The Waystation Contract (the Waystation Chief).
  They use `bounty: true`, `repeatable: true`, `target_type`, `target_count` and
  `turn_in: "Bounty Board"`; claiming one makes it available again and replaces the previous
  completion record.
- `core/bounties.py` lists contracts, enforces a two-active-bounty limit, accepts
  contracts through the quest system and claims ready ones through `complete_quest`.
- `core.quests.record_enemy_defeat` now receives the defeated enemy's monster type, tracks
  bounty progress safely (capped at the required count), prints progress, and marks the
  contract ready when complete. Existing named-target quests keep their old behavior.
- Tavern menu option 15 / `bounties` opens `BountyBoardState`, which lists available, active,
  ready and completed contracts with progress and rewards. Quick actions `accept`, `claim`
  and `leave` work; `claim N` handles a specific ready contract. Bounty quests appear in the
  normal quest log with their kill progress; ready contracts say “Ready to claim at the
  Bounty Board.” Asset version bumped to `v=28`.
- Added 7 tests covering contract data, progress counting/capping, combat integration, the
  active limit, readiness and repeatable claim rewards, the board API flow, and the tavern
  command.

## Progression achievements (2026-10-27)

- Extended the achievement stats with bounty claims, road victories, item/equipment purchases
  and defeated-enemy names. `area_cleared` reads the persistent `cleared_areas` list and
  `defeats` reads the player's defeat counter.
- Added six achievements: **Contractor** (3 bounty claims), **Roadwarden** (5 road encounter
  wins), **Waystation Liberator**, **Well Equipped** (3 equipment purchases), **Back on Your
  Feet** (first defeat recovery) and **Vaultbreaker** (defeat the Iron Sentinel).
- Added event hooks in bounty claims, shop purchases, road/area victory resolution and enemy
  defeats. Bounty repeats continue to count; road victories count only actual road
  encounters, not the Waystation boss. All new conditions are in `SUPPORTED_CONDITIONS`.
- Added four integration/condition tests; existing clean-streak, quest and save/load
  achievement behavior is unchanged. 468 tests pass.

## Weapon properties (2026-10-27)

- `Item.properties` now carries weapon metadata (`finesse`, `ranged`, `attack_stat`,
  `damage_bonus`) through `to_dict`/`from_dict`, shop stock, loot and saved equipment.
- `Entity.attack_ability()` selects Strength by default, Dexterity for ranged or the better
  of Strength/Dexterity for finesse, or an explicit `attack_stat`. `attack_bonus`,
  `attack_modifier` and `attack_damage_modifier` use that choice; the combat log labels the
  stat (`STR`/`DEX`/`INT`). Player and class weapon-damage abilities use the weapon damage
  modifier.
- Data: Short Sword and dagger are finesse; Short Bow is ranged/Dexterity with +4 damage;
  Mage Staff attacks with Intelligence. Starting class weapons receive the matching
  properties. Short Bow's old Strength effect was replaced with Dexterity.
- The shop API and web modal expose weapon properties and their readable summary; asset
  version bumped to `v=29`.
- Tests: ranged, finesse and melee stat selection; Intelligence attacks and log labels;
  damage; item/player round trips; shop property exposure; weapon data integrity. 475 tests
  pass.

## Enemy attack profiles (2026-10-27)

- `Enemy` now reads `attack_stat` and `damage_bonus` from monster stats, exposes them on
  save round trips, and uses them for basic attacks and non-save abilities through
  `Entity.attack_ability()` and `attack_damage_modifier`.
- Goblin archers, skeletons, wolves, spiders, bandits and smugglers use Dexterity; orcs,
  trolls, dragons and chiefs use Strength. Damage bonuses are data-driven and modest.
  Enemy attack logs now label `(STR)`/`(DEX)`.
- Tests cover profile selection, Dexterity-based basic damage and log labels, generic enemy
  round trips and monster attack-profile data integrity. 498 tests pass.

## Roadside events (2026-10-27)

- Added `data/road/road_events.json` and `core/road_events.py`. A triggered road event now
  chooses between an ambush and non-combat events using data weights, with one-time events
  filtered by `player.claimed_rewards`.
- Added `RoadEventState` for the traveling merchant (shop stock purchases), one-time healing
  shrine, stranded wagon (Investigation check), wounded traveler reward and leave flow.
  Ambush events continue through the existing road encounter system.
- `MapState` now routes triggered road steps through `start_road_event`; the existing grace
  period and three-step event cooldown are unchanged. Added a shared skill-check helper.
- Added state restore/quick-action handling and API documentation. Tests cover data
  integrity, event selection/filtering, merchant purchases, shrine recovery, wagon checks,
  traveler rewards and MapState event entry. 508 tests pass.

## Rune Pillar vault challenge (2026-10-27)

- Changed the vault Rune Pillar data type to `rune_pillar` and added a `RunePillar`
  interactive-object subclass. Object loading and `Map.from_dict` preserve the subclass, and
  adjacent-item interaction now receives the game context so objects can push states.
- `RunePillarState` offers `study` / `leave`. Studying makes a DC 15 Arcana check with
  Intelligence + Arcana proficiency, condition advantage/disadvantage and Guidance.
- Success grants the unique **Rune-Ward Amulet** and records
  `vault_rune_pillar` in `player.claimed_rewards`; repeated study is refused. Failure deals
  2 HP of damage and can be retried. The solved state and reward persist through save/load.
- Added `study`/`leave` available actions and state restore mappings. Tests cover object
  loading/map round trips, interaction, success/reward-once, failure/retry and Guidance
  consumption. 481 tests pass.

## The Underroad chapter (2026-10-27)

- Added the `underroad` dungeon map beneath the Waystation and an `UnderroadState` with
  confront/cache/leave actions. Access is offered after the Waystation is cleared; the map
  is hidden from the destination menu until then.
- The Waystation strongbox now also yields a Bandit Ledger and starts Mirt's
  `underroad_chapter` quest. The Underroad state ensures the quest starts for older saves.
- Added Smuggler and Smuggler Lord monsters, the fixed `underroad_boss` encounter and the
  unique Underroad Signet cache reward. Victory clears the area, readies the quest and
  unlocks the **Underroad Delver** achievement; Mirt provides the turn-in dialogue.
- Added state restore handling and server quick actions (`confront`, `cache`, `leave`).
  Tests cover map/encounter data, access gating, boss victory, quest readiness, cache
  once-only rewards, return travel, dialogue and the waystation ledger hook. 493 tests pass.

## Bounty Board web panel (2026-10-27)

- Added `GET /bounties`, `POST /bounties/accept` and `POST /bounties/claim`, available from
  `TavernState`/`BountyBoardState` and backed by the existing bounty service.
- Added a **Bounties** button in the tavern and a focus-trapped modal showing each contract's
  objective, description, status, progress and reward, with Accept/Claim actions.
- The modal refreshes the quest log, character gold and bounty list after each action.
  Asset version bumped to `v=30`.
- Added API and browser coverage for listing, accepting and claiming contracts. 494 tests
  pass.

## Hardening pass (2026-10-27)

- Removed the unused legacy `world/map_controller.py`; all live map/state navigation goes
  through `MapManager`, `MapState` and the registered game states.
- Added `states/registry.py` as the single source of truth for restoring state classes.
  Both `Game.load` and `BaseState.from_dict` now use it, so adding a state no longer
  requires updating two separate mappings. Registry tests import every registered class.
- Added `server.get_session_or_error` and routed endpoint session lookup through it. It
  handles the shared 400/404 responses and caches sessions loaded from disk consistently.
  A regression test covers disk loading and cache insertion.
- Full suite after the refactor: 485 tests pass.

## Stable map ordering (CI fix, 2026-10-27)

- `Path.glob()` order is filesystem-dependent. After the Road and Waystation maps were
  added, destination option 1 was no longer reliably Cellar, so
  `test_travel_moves_the_player_to_another_map` failed on the Python 3.13 CI runner.
- `MapLoader.list_available_maps` and `MapSelectionState` now sort map names, giving the
  destination menu a stable alphabetical order. The travel test resolves the Cellar option
  from that sorted list instead of assuming it is option 1.
- Full suite remains green: 468 tests pass.

## Combat maneuvers and expanded conditions (2026-10-27)

- Added `data/combat/maneuvers.json` and `core/maneuvers.py`. **Trip** and **Shove** are
  contested Athletics checks against the target's Acrobatics or Athletics; the data file
  defines their skill pair, condition and duration.
- Added the `prone` and `staggered` conditions. Prone gives the target's attacks
  disadvantage, gives attacks against it advantage, and costs its next action to stand up.
  Staggered gives disadvantage on attacks and blocks special abilities for a round.
- Conditions now tick on living enemies as well as the player, with entity-aware messages,
  and enemy conditions survive combat save/load. Incoming-condition roll flags are applied
  when resolving attacks against a prone target.
- Added menu options 9+, natural-language `trip`/`shove` commands and API quick actions.
  The combat snapshot exposes enemy conditions, and the web card renders them as status tags.
  Asset version bumped to `v=31`.
- Tests cover success/failure, prone stand-up, stagger ability blocking and expiry,
  incoming advantage, enemy/NPC-condition round trips, the command loop, API exposure and
  data integrity. 518 tests pass.

## Traps and environmental searches (2026-10-27)

- Added discovery state to every interactive object (`hidden`, `detected`, `detection_dc`).
  Undiscovered objects are omitted from the ASCII map, token legend, nearby lists and
  targeted command resolution until a search reveals them.
- Map menu option 6, the `search` command and the map quick actions roll Perception once
  against each hidden object within two cells. Successes reveal the object; the Cellar's
  hidden chest and floor trap, the Vault pit trap and the Underroad spike trap now use this
  flow.
- Modernised `Trap`: hidden traps can be detected, disarmed with an Investigation check, or
  triggered. Triggering calls for a data-driven saving throw, deals damage on failure and
  applies an optional condition. Failed disarms can spring the trap when configured.
- Added `disarm <trap>` targeted commands and interaction-based disarm attempts, with
  adjacent-cell checks. Trap and discovery state survive map/save round trips.
- Added a MapState quick-action context (`search` plus movement) and documented the search,
  disarm and hidden-object contract. Tests cover visibility, successful/failed searches,
  disarm success/failure, saves, one-use triggers and persistence. 530 tests pass.

## Stealth and surprise (2026-10-27)

- Added `core/stealth.py` and `Player.stealthed`. Sneak/hide (map option 7, `sneak`/`hide`
  or the map quick action) rolls Stealth against the highest passive Perception of NPCs
  within four cells; observer Perception prefers the NPC's data `wisdom`/`wisdom_base`.
- Moving while hidden re-checks Stealth through map-menu movement, `/move` and pathfinding.
  Failure names the observer and clears the hidden state. A long rest also clears stealth.
- Attacking from stealth clears it, shows a break-cover message and starts combat with
  `surprised=True`. The opening weapon attack uses the existing aim advantage, the fastest
  enemy cannot seize initiative, and enemies lose their first turn.
- Exposed `stealthed` in `/state` and `/start` summaries, and `surprised` at the top level and
  per living enemy in `/combat`. The client renders Hidden, Surprise round and Surprised
  tags; assets are at `v=32`.
- Tests cover successful/failed hiding, movement re-checks, the map command, stealth
  attacks, skipped initiative/actions, surprise advantage, round trips and API exposure.
  541 tests pass.

## The Sealed Sanctum capstone (2026-10-27)

- Added the `sanctum` map (hidden from destination selection), the `SanctumState` chapter and
  its registry/server quick-action support. The Underroad's cleared cache exposes the sealed
  door; the Underroad Signet opens it.
- Added the `sanctum_chapter` quest for Mirt. Dialogue conditions now support recursively
  nested `all`/`any` groups so the offer requires both a completed Underroad and an unstarted
  Sanctum quest.
- The chapter has a warded threshold: the Rune-Ward Amulet bypasses it, while forcing it
  calls for a DC 14 Constitution save, costs up to 8 HP and applies Weakened on failure. The
  ward state persists in `claimed_rewards`.
- Added the Rune Warden and Rune Sentinel monsters, three new abilities, the `sanctum_boss`
  encounter and the unique legendary Runeheart Amulet vault reward. Victory clears `sanctum`,
  readies the quest and unlocks the Sanctum Breaker achievement.
- Added Mirt's offer, reminder, turn-in and epilogue nodes. Tests cover map/encounter data,
  access gating, the ward paths, boss victory, reward-once behavior, dialogue visibility,
  quick actions and state round trips. 555 tests pass.

## Faction reputation and the Runeheart choice (2026-10-27)

- Added `data/factions/factions.json` and `core/factions.py` for Mirt's Network, Violet's
  Watch and the Underroad Smugglers. `Player.reputation` persists through save/load and is
  exposed in `/state` and `GET /reputation`.
- Quest definitions now carry optional `faction` and `reputation` values. Completing a
  quest adjusts standing; friendly-or-better standing adds the faction's `quest_bonus`
  percentage to the gold reward.
- Mirt's Network standing discounts market purchase prices (`shop_discount`), with the
  base and discounted prices exposed in `/shop`; the shop modal shows the active discount.
- Dialogue conditions now support reputation thresholds and nested `all`/`any` groups. Mirt
  and Violet each gain a friendly-standing dialogue option.
- The Runeheart vault now offers a choice: keep the legendary Runeheart Amulet, give it to
  Mirt (+12 Mirt's Network, +200 gold), or give it to Violet (+12 Violet's Watch,
  +100 gold). The chosen flag is persisted.
- Added a client Reputation panel and bumped assets to `v=33`. Tests cover thresholds,
  discounts, quest bonuses, dialogue gates, API exposure, the Runeheart outcomes and data
  integrity. 566 tests pass.

## Enemy maneuvers and player counterplay (2026-10-27)

- `Enemy` now carries data-driven `maneuvers` and `maneuver_chance` fields, serialized through
  save/load. Wolves Trip; bandits, smugglers, sentinels and the Smuggler Lord Shove; the Rune
  Warden has both.
- Enemy actions check for an appropriate off-cooldown maneuver before abilities or a basic
  attack. The d100 chance roll and a two-round maneuver cooldown limit repeated control. A
  maneuver is skipped when its condition is already on the player.
- Refactored the contested skill helper into a generic attacker/defender form. Enemy
  maneuvers roll Athletics against the player's Acrobatics/Athletics, with Guidance applying
  on whichever side is controlled by the player; the player-initiated wrapper keeps its old
  return shape.
- A prone player now gets a dynamic **Stand up** combat option, quick action and
  `/available_actions` entry. It costs the turn and clears Prone. Staggered now blocks player
  class abilities, matching the enemy rule.
- Added maneuver data integrity checks and tests for enemy Trip/Shove, failure, condition
  skipping, cooldowns, Stand Up, ability blocking and enemy round trips. 575 tests pass.

## Rune Trials post-campaign arena (2026-10-27)

- Added `data/trials/rune_trials.json` and `core/trials.py`: five data-driven waves built
  from existing monsters, three modifiers (Empowered/Warded/Frenzied) and three boons
  (Mend/Focus/Cleanse).
- Added `RuneTrialsState`, reachable from the cleared Sanctum. It tracks the current wave,
  boons, active combat and phase; combat victory advances to boon selection, flight or
  defeat ends the run, and a full clear grants the completion reward.
- Added `CombatState.outcome` (`victory`/`fled`/`defeat`) so enclosing states can distinguish
  the result after combat pops; it is serialized for completeness.
- Persisted `Player.rune_trials_best` and `rune_trials_runs`, exposed under `state.rune_trials`.
  Added Rune Trials Adept and Champion achievement conditions.
- Added phase-dependent quick actions (`begin`, boons, `restart`) and state registry/server
  support. Updated README, API docs, frontend notes and data integrity/tests.
- 587 tests pass.

## Level 10 class capstones (2026-10-27)

- Added one capstone per class to `data/classes/abilities.json` and level 10 progression in
  `data/classes/classes.json`: Fighter **Last Stand** (+5 attack/-5 incoming), Wizard
  **Meteor Swarm** (30 armor-ignoring damage), Rogue **Assassinate** (4x weapon damage) and
  Cleric **Divine Intervention** (40 HP heal).
- The existing ability engine already supports all four effects, so capstones use the same
  combat resolution, mana costs, UI progression rows and save/load path as earlier tiers.
- Added the **Legend** achievement for reaching level 10 and a `level` achievement condition.
  `Player._ascend_level` now records a `level_up` event so the achievement unlocks on the
  level-up itself.
- Tests cover lock/unlock at level 9/10, each capstone effect and the Legend achievement.
  593 tests pass.

## Cover and flanking (2026-10-27)

- Added **Take cover** as combat action 9. It grants +2 AC and advantage on Dexterity saves
  through the enemy phase, then expires. It is available only when the player is adjacent to
  a wall or an interactive object tagged `provides_cover`; otherwise it is refused. This is
  distinct from Defend's +4 AC.
- Added **Flanking**: while any living ally remains, the player's weapon attacks gain +2 to
  hit. The bonus is shown in the combat card through `effects.flanking`, and cover through
  `effects.covering`.
- Shifted maneuver menu numbers to 10+ and the dynamic Stand Up option accordingly; text
  commands and quick actions are unchanged in intent.
- Client asset version bumped to `v=34`. Tests cover cover proximity, AC and expiry,
  cover-enhanced Dexterity saves, flanking hit/miss comparisons and combat snapshot exposure.
- Full suite: 599 tests pass.

## AI Dungeon Master awareness (2026-10-27)

- Expanded the shared narrator context in `ai/context.py` with player level, conditions,
  active quests and completed count, faction standing/shop discount, campaign flags
  (Sanctum, Runeheart choice, completion), Rune Trials best/runs, and active combat details
  (round, target, enemies, allies, Cover, Flanking). The context remains compact and excludes
  the inventory, full stats and hidden map contents.
- Deterministic recaps now include faction standing, merchant discount, Runeheart choice,
  Sanctum completion, Rune Trials depth/runs and capstone status. Combat hints now warn when
  the player is Prone or Staggered.
- Narration, hint and recap prompts document the richer context while retaining the existing
  no-state-authority, no-hidden-information and fallback rules.
- Tests cover context fields, faction/campaign/trial recap text, combat condition hints and
  the existing no-AI fallback paths. 602 tests pass.

## Rune-forged crafting (2026-10-27)

- Added `Player.rune_shards`, awarded by every Rune Trial wave and the full-clear bonus.
  Shards persist through save/load and are exposed in `/state`, the player summary and AI
  context/recap.
- Added `data/crafting/recipes.json` and `core/crafting.py`: repeatable Rune Draught plus
  unique Rune-Forged Blade and Rune-Ward Plate recipes. Unique crafts record
  `crafted:<recipe_id>` in `claimed_rewards`.
- Added the `ForgeState` Sanctum station with a numbered recipe menu, costs, requirements
  and one-time status, plus `GET /forge` and `POST /forge/craft`.
- Added a focus-trapped Forge modal to the web client; assets are at `v=35`.
- Added legendary crafted items to the weapon/armor data and a rare Rune Draught potion.
- Tests cover recipe data, resource consumption, unique-once crafting, missing resources,
  shard persistence, Sanctum access and the forge API. 613 tests pass.

## Campaign dashboard (2026-10-27)

- Added `GameState.get_campaign_state()` and `GET /campaign`. It reports the seven main-story
  chapters with active/ready/completed/not-started status, campaign completion, Runeheart
  choice, faction standing, Rune Trials best/runs, Rune Shards, capstone unlock state and the
  current landmark.
- Included the campaign object in `/state` and added a client Campaign panel with progress,
  chapter objectives/status tags and endgame summary. Assets are at `v=36`.
- Tests cover chapter status mapping, endgame fields, `/state` exposure, the API endpoint and
  missing-session errors. 616 tests pass.

## New Cycle / New Game+ (2026-10-27)

- Added `Player.cycle`, `data/cycles/cycles.json` and `core/cycles.py`. Enemy HP, damage and
  AC scale by cycle, while encounter, quest and trial-completion rewards use the cycle reward
  multiplier.
- Added `Game.start_new_cycle()`: resets quests, cleared areas, campaign flags, conditions,
  allies, defeats, map state and non-forged reward flags; keeps level, XP, equipment,
  inventory, gold, achievements, faction standing, Rune Shards, Rune Trials records and
  forged `crafted:*` gear.
- The tavern offers option 16 / `new cycle` / `ng+` only after the Sanctum quest is completed,
  with a confirmation prompt. A fresh MapManager and TavernState are installed.
- Added the Cyclebreaker achievement, campaign-dashboard cycle display and AI context/recap
  cycle awareness. Client assets are at `v=37`.
- Tests cover retention/reset rules, map reset, cycle persistence, scaling data, combat
  scaling once, reward multipliers, Tavern unlock gating and the Cyclebreaker achievement.
  622 tests pass.

## Ally commands and party panel (2026-10-27)

- Added persistent `Player.ally_stances` with Attack, Guard and Support. Combat ally actions
  now follow the stance: Guard contributes +1 player AC while alive, Support performs a
  once-per-fight heal or condition cleanse, and Attack keeps the existing target focus.
- Added `core/party.py`, combat ally command parsing (`Violet: guard`), dynamic quick actions,
  stance data in `/combat`, and support healing scaled by Violet's Watch standing.
- Added `GET /party`, `POST /party/stance`, and a web-client Party panel with stance buttons;
  ally stance tags also appear in the combat card. Assets are at `v=38`.
- AI context and recap now include recruited allies and their stances.
- Tests cover defaults/persistence, guard AC and non-attacking behaviour, support healing and
  cleansing, command parsing, party data, API updates and combat snapshot exposure. 631 tests
  pass.

## Landmark panels (2026-10-27)

- Added `GameState.get_landmark_state()` and `GET /landmark`. It reports the current
  Waystation, Underroad, Sanctum, Rune Trials or Forge with a description, status entries and
  the same action list as its numbered menu; non-landmark states return `active: false`.
- Added `WaystationState.available_actions()` and included the landmark object in `/state`.
- Added a client Landmark card with status tags and clickable action buttons, leaving the
  terminal-style menus untouched. Assets are at `v=39`.
- Tests cover each landmark's status/actions, inactive states, `/state` exposure, the API
  endpoint and missing-session errors. 636 tests pass.

## Non-combat utility magic (2026-10-27)

- Added Wizard **Detect Magic**, Rogue **Disguise Self** and Cleric **Comprehend
  Languages** to the starting ability catalogue. All use the existing utility-effect path:
  refused in combat and no mana spent when there is no valid target.
- Added `magical` metadata to interactive objects. Detect Magic reveals hidden magical traps
  and identifies nearby magical objects, including the Rune Pillar and Magic Altar.
- Disguise Self sets a persisted `player.disguised` state, grants advantage on Stealth checks,
  and unlocks a one-use bluff option in Mirt's dialogue that consumes the disguise. Long rests
  and New Cycles clear it; the client shows a Disguised condition tag and assets are at `v=40`.
- Comprehend Languages reads the Bandit Ledger (starting the Underroad quest), Rune Pillar
  inscriptions and magical altar text without a check.
- Tests cover magical discovery, refused targets, stealth advantage, the dialogue bluff,
  ledger/quest interaction, Rune Pillar text, mana spending and disguise persistence. 643
  tests pass.

## Violet's Watch side quest (2026-10-27)

- Added `watchman_ledger` ("The Watchman's Cut"), offered by Violet at Friendly Violet's
  Watch standing after `shadows_of_the_market` is completed.
- Added the warehouse **Watch Cache** and `Watch Ledger` document item. Acquiring the ledger
  marks the quest ready; opening the cache before accepting also works through the existing
  target-item flow.
- Violet's turn-in offers three outcomes: give the evidence to Violet (+8 Violet's Watch),
  give it to Mirt (+8 Mirt's Network and 60 gold), or keep it (−5 Violet's Watch). All grant
  the base quest reward and unlock the Watch Whistleblower achievement.
- Added document item support to the catalogue, item use path and `/item_details`, plus the
  generic `add_gold` dialogue effect and `quest_completed` achievement condition.
- Tests cover offer gating, cache/ledger readiness, all three outcomes, achievement
  completion and repeat-offer suppression. 650 tests pass.

## Ally abilities and loyalty (2026-10-27)

- Added `data/party/ally_abilities.json` and Violet's data-driven Field Dressing, Antidote
  and Calming Word. NPC data now carries `ally_abilities`, and ally ability definitions are
  loaded by `core.party`.
- Support stance selects the most useful ready ability for the player's condition/health.
  Abilities use round cooldowns, with friendly/trusted Violet's Watch loyalty reducing them;
  explicit commands such as `Violet: antidote` also work as free combat orders.
- Added loyalty derived from faction standing. Hostile allies refuse to act; party entries
  expose loyalty, `will_act` and ability details. Combat snapshots expose stances, loyalty,
  abilities and active cooldowns.
- Party panel now shows loyalty and ability buttons during combat. AI context/recap include
  ally loyalty. Assets are at `v=41`.
- Tests cover ability data, support selection, explicit orders, cooldowns, loyalty refusal,
  party/API exposure and persistence. 656 tests pass.

## Mirt's Network side quest (2026-10-27)

- Added `silent_partner` ("The Silent Partner"), offered by Mirt at Friendly Mirt's Network
  standing after `underroad_chapter` is completed.
- Added the market **Merchant's Lockbox** and `Merchant Ledger` document. Recovering the
  ledger readies the quest through the existing target-item flow.
- Mirt's turn-in choices give the ledger to Mirt (+8 Mirt's Network), protect the trade
  (+8 Underroad Smugglers and an extra 80 gold), or keep it (−5 Mirt's Network). All grant the
  base reward and unlock The Silent Partner achievement.
- Tests cover offer gating, lockbox/ledger readiness, all three outcomes, achievement
  completion and repeat-offer suppression. 663 tests pass.

## Broader conditions and counterplay (2026-10-27)

- `data/conditions/conditions.json` now also defines **Blinded** (attack/check
  disadvantage, incoming attacks have advantage, CON 12 save), **Restrained** (the same
  penalties, cannot flee, STR 13 save) and **Charmed** (cannot attack the charmer, WIS 13
  save).
- Conditions can declare `blocks_escape`, `blocks_attacks_against_source` and an
  `escape_action` with either a skill check or a saving throw. Charmed entries record the
  charmer in `source`; the enemy ability data uses `"source": "attacker"`.
- `CombatState` gained dynamic **Stand up**, **Break Free** and **Resist the Charm** menu
  entries after the maneuvers, with matching aliases and `available_actions` entries.
  Escape actions cost the turn on success or failure. Charmed weapon attacks and damaging
  class abilities against the charmer are refused without consuming the turn, while other
  targets remain attackable.
- Restrained blocks `flee` outright; the attempt does not roll. The hints system now calls
  out Blinded, Restrained and Charmed with their counterplay.
- Sources: bandits gained **Blinding Powder**, giant spiders **Sticky Web**, the Smuggler
  Lord **Silver Tongue**, and the Underroad gained a hidden **Blinding Dust Trap** at
  `(12, 2)`. The Conditions card labels and tooltips were extended and assets bumped to
  `?v=42`.
- Tests: `tests/test_extended_conditions.py` covers both-way roll flags, the trap source,
  blocked fleeing, successful/failed Break Free, quick-action discovery, source-specific
  Charmed attacks and abilities, the Wisdom escape save, Silver Tongue source recording,
  and the spider/bandit sources. Data integrity validates the new condition flags and
  escape actions. 675 tests pass.

## The Quiet Cargo — Underroad side quest (2026-10-27)

- Nessa, a surviving tunnel runner, is reachable from the cleared Underroad menu as menu
  option 5 / `talk to Nessa`. Her dialogue is offered only after `underroad_chapter` is
  completed and `quiet_cargo` has not started; the informational branch is gated the same
  way so it cannot bypass the offer condition.
- **The Quiet Cargo** (`quiet_cargo`) asks the player to search the hidden **Watch Impound
  Wagon** at `(23, 8)` in the market, beside the old warehouse. The wagon is a concealed
  chest (detection DC 13) and yields the target-item **Cargo Manifest**, which readies the
  quest through the existing item-acquisition hook.
- Turn-in has three outcomes from Nessa's dialogue:
  - give the manifest to Nessa: +8 Underroad Smugglers and the unique **Runner's Satchel**
    (defense +1, dexterity +1, rare);
  - send it to Violet's Watch: +8 Violet's Watch and 100 gold;
  - sell it to Mirt: +8 Mirt's Network and 100 gold.
  All three complete the quest, grant the base 120 gold/220 XP reward and unlock The Quiet
  Cargo achievement.
- The wagon token is `Q` to avoid colliding with Violet's `I` on the same market map.
  Documents, accessories, the NPC definition, dialogue graph, quest, achievement and docs
  were updated; no frontend asset change was needed because the Underroad menu and dialogue
  card consume the existing `available_actions` and dialogue data.
- Tests: `tests/test_quiet_cargo.py` covers offer gating (including the info-branch bypass),
  hidden-wagon search and manifest readiness, all three outcomes, the Runner's Satchel,
  achievement completion, repeat suppression and Underroad menu access. 685 tests pass.

## AI scene descriptions (2026-10-27)

- Added `data/scenes/locations.json` with one deterministic description for every map
  (`tavern`, `market`, `cellar`, `warehouse`, `vault`, `road`, `waystation`, `underroad`
  and `sanctum`). `DataManager` now registers the `scenes` data directory.
- `ai/scene.py` builds the engine description from the location entry plus nearby NPCs and
  objects, cleared-area state, stealth and the current state (combat/dialogue). Hidden
  objects stay hidden. `generate_scene` optionally asks the narrator for atmosphere and
  returns `source: "engine"` on any failure, refusal or disabled narration. It never changes
  state.
- Added `describe` to the narrator protocol, `NullNarrator`, Claude and OpenAI adapters,
  with a dedicated scene prompt in `ai/prompts.py` and a 256-token cap. The scene prompt
  keeps the engine facts authoritative and forbids new places, items, NPCs or outcomes.
- `POST /describe` returns `session_id`, `description` and `source`, logs a
  `type: "description"` event and reuses the session narrator/memory. Recaps exclude
  descriptions from their recent-event input.
- The web client gained a **Scene** button in the log actions, a `Scene` log label, a
  description log style and busy-state handling. Assets are at `?v=43`.
- Tests: `tests/test_scene.py` covers catalogue coverage, deterministic descriptions,
  nearby NPCs, cleared/stealth wording, AI success/failure/decline, narrators without
  `describe`, no state mutation and the API/logging path. Narrator adapter tests cover the
  scene prompt on both providers. 703 tests pass.

## Nessa's black market (2026-10-27)

- New `data/items/black_market_stock.json` defines access at Underroad reputation 5,
  four tier thresholds and ten data-driven stock entries. Runner's Cache sells Smoke Bomb,
  Antidote, Spider Poison and Healing Potion; Friendly adds Greater Healing Potion,
  Thief's Gloves and Dexterity Potion; Trusted adds Boots of Speed and the unique
  **Smuggler's Nightglass** (dexterity +2, initiative +2); Allied adds Rune Draught.
- `core/black_market.py` handles access (requires completed `quiet_cargo` plus positive
  Underroad standing), tier selection, prices, discounts (5% trusted, 10% allied), locked
  and purchased states, and purchases. Unique purchases use the
  `black_market:<item name>` claimed-reward flag, which New Cycle now retains alongside
  `crafted:*` flags so an inventory-persisted unique item cannot be bought twice.
- `BlackMarketState` is a new menu state reached from Underroad menu option 6 /
  `Nessa's cache`. It lists every stock row, including locked tiers and their requirements,
  and returns to the Underroad with `leave`. It is registered for save/load.
- API: `GET /black_market` and `POST /black_market/buy`, restricted to `BlackMarketState`.
  Purchases add `black_market` snapshots and engine output. `GET /black_market` outside the
  state returns `409`; the buy call returns `bought: false`.
- Web client: a **Black market** log-action button appears only in the state and opens
  Nessa's Cache modal with tier, standing, gold, discount, locked stock, unique/sold status
  and per-item Buy buttons. Assets are at `?v=44`.
- Underroad `available_actions` exposes `Nessa's cache` once unlocked, and the `Underroad`
  landmark panel inherits it.
- Tests: `tests/test_black_market.py` covers access gating, tier stock, discounts, purchase
  success, locked/insufficient-gold refusal, unique exhaustion and player-round-trip state,
  menu access and the API. Data integrity validates the stock definition.
  **715 tests pass.**

## Difficulty presets (2026-10-27)

- Added `data/difficulty/difficulty.json` with **Story**, **Standard** and **Hard**. Each
  defines enemy HP/damage/AC modifiers, a quest/encounter/trial reward percentage, inn rest
  cost (5/10/15 gold) and defeat gold loss (10/20/30).
- `core/difficulty.py` exposes the catalogue, player difficulty fallback, enemy scaling,
  reward multiplier, rest cost and defeat loss helpers. `DataManager` registers the
  `difficulty` directory.
- `Player.difficulty` defaults to `standard`, survives `to_dict`/`from_dict` and is retained
  through New Cycle. Old saves without the field load as Standard.
- `CombatState._apply_cycle_scaling` now combines New Cycle and difficulty modifiers, with
  HP/AC floors and negative Story modifiers handled safely. Quest, encounter and Rune
  Trials completion rewards multiply both sources. Tavern rest and defeat recovery use the
  difficulty values.
- `POST /start` accepts `difficulty` and rejects unknown values with `400`.
  `GET /difficulties` lists the presets. `GET /state` exposes `difficulty`; the campaign
  object includes its id, name and description; AI context includes the difficulty name.
- The start screen has a difficulty selector populated from `/difficulties` with a
  description. The Campaign panel summary shows the active preset. Assets are at `?v=46`.
- Fixed a mobile entry bug uncovered by the added start-screen field: the page now scrolls
  to the top when entering the game or returning to the start screen, so the sticky topbar
  no longer covers the Map button.
- Tests: `tests/test_difficulty.py` covers the catalogue, default/persistence, Story/Hard
  combat scaling, New Cycle stacking, quest and encounter rewards, rest/defeat costs,
  context/campaign exposure, `/start` selection/rejection and `/difficulties`. A browser
  test also selects Hard on the start screen and verifies the created session.
  **728 tests pass.**

## Elite enemies and encounter variety (2026-10-27)

- Added four elite monsters with `"elite": true` in `data/monsters/monsters.json`:
  **Goblin Hexer**, **Orc Berserker**, **Risen Champion** and **Smuggler Enforcer**. Their
  stats, weapons, armor, rewards and abilities are data-driven.
- Added three abilities in `data/monsters/abilities.json`: **Hex Bolt** (WIS save, blinded),
  **Reckless Cleave** (DEX save, weakened) and **Grave Guard** (WIS save, frightened, enemy
  guard). Smuggler Enforcers reuse Dirty Trick and Shield Bash.
- Added four curated encounters: **Goblin Warband**, **Orc Raiders**, **The Restless Dead**
  and **Smugglers' Enforcers**. They appear at the end of the tavern encounter list, so the
  existing numbered choices keep their order. The road table adds Goblin Warband at level
  3, Smugglers' Enforcers at 4 and Orc Raiders at 5; the list now uses a min-level map
  instead of one-off filtering.
- `Enemy.elite` survives save/load. Encounter objects expose `elite`, `/combat` exposes it
  per enemy, the web card renders an **Elite** tag, and AI context includes it.
- Fixed a latent input-consumption bug exposed by having more than seven curated
  encounters: the command that opened the encounter list could be reread as an encounter
  index. The list now clears that pending command and waits for a fresh choice.
- Tests: `tests/test_elite_enemies.py` covers elite load/round-trip, encounter flags and
  rewards, combat snapshots, Hex Bolt/Reckless Cleave/Grave Guard, road level gates and the
  tavern catalogue. The browser test now asserts the Elite tag. **736 tests pass.**

## AI NPC dialogue colour (2026-10-27)

- Added `ai/dialogue.py` and `POST /dialogue/voice`. The engine supplies the current
  deterministic line plus NPC name, profession and node; the narrator may add delivery,
  posture and tone without changing the line or options.
- Added `dialogue` to the narrator protocol, `NullNarrator`, Claude and OpenAI adapters,
  with a dedicated prompt and the same 256-token cap. Prompt rules forbid new choices,
  actions, items, NPCs, numbers, quest changes and hidden information.
- Engine fallback returns the exact NPC line with `source: "engine"` and leaves the dialogue
  card and node unchanged. AI prose is logged as `dialogue_voice` and excluded from recap
  recent-event input; engine fallback is not logged again.
- The dialogue card gained a **Voice** button. With AI disabled/unavailable it shows a toast
  instead of duplicating the line in the log. Assets are at `?v=48`.
- Tests: `tests/test_dialogue_voice.py` covers engine fallback, no state mutation, context
  shape, AI success/failure/decline, missing narrator, no active dialogue and the API 409.
  Provider tests cover the dialogue prompt; the browser smoke test clicks Voice and asserts
  the engine fallback toast. **748 tests pass.**

## The Runeheart Gate epilogue (2026-10-27)

- Added a new `runeheart_gate` dungeon map and scene description, reached from the Sanctum
  menu option 6 / `gate` once the Sanctum is clear and the Runeheart vault choice has been
  made.
- `RuneheartGateState` runs two encounters: **The Gate Wardens** (two sentinels + an echo)
  and **The Runeheart Sovereign** (boss + two echoes). The wardens encounter grants the
  `runeheart_gate_wardens` flag via new generic `grants_flag` encounter metadata.
- Runeheart choice branches:
  - **kept** adds a third Runeheart Echo to the boss fight;
  - **Mirt** adds Mirt's Factor as a temporary combat ally;
  - **Violet** fully heals and clears conditions, then adds a Watch Medic ally.
- Added the Runeheart Sovereign, Runeheart Echo, Heart Seal ability, Heartseal legendary
  accessory, Heart of the Gate achievement and the auto-completing `runeheart_gate` quest.
- Campaign completion now requires both `sanctum_chapter` and `runeheart_gate`, and New
  Cycle uses the same condition. The Campaign dashboard now tracks eight chapters. The
  Runeheart Gate has its own landmark panel.
- Tests: `tests/test_runeheart_gate.py` covers map/encounter definitions, Sanctum gating,
  quest start, all three Runeheart branches, warden progress, boss completion/rewards and
  the return to the Sanctum. Campaign/New Cycle/state-registry tests were updated.
  **758 tests pass.**

## Cycle Omens (2026-10-27)

- Added `data/cycles/omens.json` with **Rune Surge**, **Smugglers' Moon**, **Watch
  Crackdown** and **Long Winter**. `core/omens.py` provides the catalogue, current omen,
  enemy scaling, reward/shard multipliers, rest bonus and Mirt/black-market discount
  bonuses.
- New Cycle confirmation now moves to an Omen choice (or no omen) before calling
  `Game.start_new_cycle(omen_id)`. `Player.cycle_omen` persists in saves; choosing no omen
  clears it. Existing direct `start_new_cycle()` calls still work and clear the omen.
- Omens stack with difficulty and cycle scaling: enemy AC/HP, quest/encounter/trial rewards,
  Rune Shards, inn rest cost, Mirt market discount and black-market prices all read the
  active omen.
- `GET /state` exposes `cycle_omen`; the campaign object includes its id/name/description;
  the Campaign panel summarises it and AI context includes the name.
- Tests: `tests/test_cycle_omens.py` covers catalogue, persistence, New Cycle selection,
  enemy/reward/shard/rest/shop effects, black-market pricing, campaign/AI exposure and the
  tavern choice flow. **772 tests pass.**

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
| `pytest` suite (imports, state stack, save/load, items, data integrity, API, AI narration, AI memory, hints, achievements, utility spells, locks, vault, quests, enemy abilities, encounters, saving throws, conditions, combat status, attack rolls/AC, Defend/Aim, defeat recovery, session recap, equipment economy, road/wilderness/loot, Broken Waystation, Underroad, bounty board, bounty web panel, progression achievements, weapon properties, enemy attack profiles, roadside events, Rune Pillar, hardening, rest, accessibility, web client routes, browser smoke/mobile) | 508 passed |
| Live smoke test (Flask server, `/app`, start/state/abilities/inventory/actions/command/save/load) | passed |

The last comparison is the strongest evidence: the pristine Italian code and the finished
English code place every object and NPC in exactly the same cells.
