# REST API contract

The Flask backend in `server.py` exposes a JSON API for the terminal engine. CORS is
enabled, so a browser client can run on a different origin.

- Default base URL: `http://127.0.0.1:5000` (`python server.py`)
- Browser client: `GET /app` (see `frontend/README.md`)
- All request and response bodies are JSON unless noted otherwise.

## Errors

Errors use a single shape:

```json
{"error": "Human-readable message"}
```

| Status | Meaning |
|---|---|
| `400` | Missing or invalid input |
| `404` | Session, save, item or map not found |
| `409` | Save refused by the engine (combat, dialogue, market transaction) |
| `501` | Explicitly not implemented (currently `POST /use_ability`) |
| `500` | Unexpected server error |

## Message types

Endpoints that run a game command return `output`, a list of messages:

```json
[
  {"type": "narration", "text": "Warmth folds around you..."},
  {"type": "narrative", "text": "You enter the tavern."},
  {"type": "system", "text": "Saved."},
  {"type": "error", "text": "Invalid choice."},
  {"type": "prompt", "text": "Choice: "},
  {"type": "map", "text": "#####\n#.P.#\n#####"}
]
```

`narration` is only emitted when the server has AI narration enabled. When present, it is
emitted **before** the engine `narrative` messages it was generated from, so clients that
render in order show the DM paragraph first. `narrative` is the engine's own text and is
authoritative; `narration` is optional prose and must never be treated as game state. `map`
is preformatted ASCII; render it in a monospace, whitespace-preserving block.

## Session flow

1. `POST /start` (new game) or `POST /load` (existing save) returns a `session_id`.
2. Keep the `session_id` and send it with every session-scoped request.
3. `POST /command` advances the game and returns `output` plus the updated `state`.
4. Side panels use `GET /state`, `/abilities`, `/inventory`, and `/available_actions`.
5. `POST /save` / `POST /load` manage files under `saves/`.

Sessions are cached in memory and persisted as `sessions/session_<id>.pickle`; they survive
a server restart. A stale `session_id` returns `404`.

## The state object

`GET /state` and the `state` field in command responses share this shape:

```json
{
  "name": "Aria",
  "char_class": "wizard",
  "hp": 6,
  "max_hp": 6,
  "state": "TavernState",
  "output": "last raw output text",
  "position": {"map": "tavern", "x": 5, "y": 5},
  "inventory": ["Healing Potion", "Common Key"],
  "equipment": {
    "weapon": "staff",
    "armor": "Wizard's Robe",
    "accessories": []
  },
  "stats": {
    "strength": -2,
    "dexterity": 0,
    "constitution": -1,
    "intelligence": 4,
    "wisdom": 1,
    "charisma": 0,
    "strength_base": 6,
    "dexterity_base": 10,
    "constitution_base": 8,
    "intelligence_base": 16,
    "wisdom_base": 12,
    "charisma_base": 10,
    "gold": 10,
    "level": 1,
    "experience": 0,
    "mana": 20,
    "mana_max": 20
  },
  "active_quests": [],
  "completed_quests": [],
  "preferences": {},
  "combat": {"in_combat": false},
  "dialogue": {"active": false}
}
```

`combat` and `dialogue` are context snapshots with the same shapes as `GET /combat` and the
`dialogue` field of `POST /dialogue`; clients can render combat/enemy HP and clickable
dialogue options directly from `/state`.

`strength`, `dexterity`, etc. are **effective modifiers** (they include equipped gear).
`strength_base`, `dexterity_base`, etc. are the ability scores shown in the class preview.
The web client renders a base score with the modifier, for example `INT 16 (+4)`; use
`*_base` when you need the raw ability score.

A compact player summary is also returned by `/start`, `/load`, and `/import_save`:

```json
{
  "name": "Aria",
  "char_class": "wizard",
  "hp": 6,
  "hp_max": 6,
  "level": 1,
  "experience": 0,
  "gold": 10,
  "map": "tavern",
  "position": {"x": 5, "y": 5},
  "mana": 20,
  "mana_max": 20
}
```

## Endpoints

### Session and gameplay

#### `POST /start`

```json
{"name": "Aria", "char_class": "wizard"}
```

Response:

```json
{
  "session_id": "uuid",
  "message": "Game started",
  "player": { ...player summary... },
  "state": { ...state... },
  "output": [ ...messages... ]
}
```

`char_class` must match a key in `GET /classes` (lowercased in the engine).

#### `POST /command`

```json
{"session_id": "uuid", "command": "1"}
```

Response:

```json
{
  "output": [ ...messages... ],
  "state": { ...state... },
  "state_name": "TavernState",
  "end": false
}
```

`end` becomes `true` when the state stack is empty.

Free-text commands are still accepted. In the tavern hub and on the map screen the engine
resolves targets deterministically: `talk to Durnan`, `attack the goblin`,
`use Healing Potion`, `go to the market`, `examine the chair`, `interact with the barrel`.
`go` / `walk` / `move` / `approach` to an NPC or object also pathfinds to an adjacent cell
in one command, respecting walls and occupied cells. On the map screen, `south`,
`move east`, etc. also move directly. Unknown targets show a message and fall back to the
corresponding menu.

#### `GET /state?session_id=...`

Returns the state object above.

#### `GET /log?session_id=...&max=50`

Returns the rolling event log:

```json
{"events": [{"type": "narrative", "text": "...", "time": 1790000000.0}]}
```

#### `POST /save`

```json
{"session_id": "uuid", "file_name": "save.json"}
```

Returns `200` with `{"message": "..."}`, or `409` if the engine refuses (combat, dialogue,
or a market transaction).

#### `POST /load`

```json
{"session_id": "uuid (optional)", "file_name": "save.json"}
```

Without `session_id`, a fresh session is created for the save. With an unknown
`session_id`, the response is `404`. On success:

```json
{
  "session_id": "uuid",
  "message": "Game loaded from save.json",
  "player": { ...player summary... },
  "state": { ...state... },
  "output": [ ...messages... ]
}
```

#### `GET /list_saves`

```json
{
  "saves": [
    {
      "file": "save_aria.json",
      "player": "Aria",
      "level": 1,
      "char_class": "wizard",
      "map": "tavern",
      "data": "26/10/2026 12:00:00",
      "version": "1.0.0"
    }
  ]
}
```

`GET /saves` is a legacy shape with different field names; prefer `/list_saves`.

#### `POST /delete_save`

```json
{"file_name": "save_aria.json"}
```

#### `POST /preferences`

```json
{"session_id": "uuid", "preferences": {"theme": "dark"}}
```

Preferences are merged into the session and exposed in `state.preferences`.

### Character and inventory

#### `GET /classes`

Returns the full class catalogue from `data/classes/classes.json`:

```json
{
  "fighter": {
    "description": "...",
    "base_stats": {"strength": 15, "...": 0},
    "special_abilities": ["Powerful Blow", "Parry"],
    "starting_equipment": ["Short Sword", "Wooden Shield", "Leather Armor"],
    "hp_base": 12,
    "mana_base": 0,
    "progression": {"...": "..."}
  }
}
```

#### `GET /stats?session_id=...`

```json
{"name": "Aria", "char_class": "wizard", "hp": 6, "max_hp": 6, "stats": { ... }}
```

#### `GET /abilities?session_id=...`

```json
{
  "abilities": ["Magic Missile", "Mage Shield"],
  "skills": ["arcana", "history"],
  "skill_proficiencies": {"arcana": true, "history": true},
  "mana": 20,
  "mana_max": 20
}
```

`POST /use_ability` returns `501` with `{"implemented": false}`: the engine has no ability
execution yet. Clients should disable the action.

#### `GET /inventory?session_id=...`

```json
{
  "inventory": ["Healing Potion", "Common Key"],
  "equipment": {"weapon": "staff", "armor": "Wizard's Robe", "accessories": []}
}
```

#### `GET /item_details?session_id=...&object_name=Healing%20Potion`

Use `object_name` or `item_id`. Response is the item's serialized fields plus:

```json
{
  "name": "Healing Potion",
  "type": "heal",
  "effect": {"heal": 10},
  "value": 25,
  "description": "A potion that restores 10 hit points",
  "asset_url": "/asset/items/item_default.png",
  "uses": [
    {"action": "use", "description": "Use this item"},
    {"action": "examine", "description": "Examine the item in detail"},
    {"action": "drop", "description": "Drop the item"}
  ]
}
```

#### `POST /item`

```json
{"session_id": "uuid", "item": "Healing Potion", "action": "use"}
```

Runs the command `<action> <item>` and returns `output` and `state`.

#### `POST /equipment`

```json
{"session_id": "uuid", "action": "equip", "item": "Short Sword", "slot": ""}
```

`action` is `equip`, `unequip`, or `examine`. Returns `output`, `state`, and `equipment`.

### World and narrative

#### `GET /map?session_id=...` / `GET /position?session_id=...`

Returns the player's map, coordinates, and serializable nearby items/NPCs:

```json
{
  "map": "tavern",
  "x": 5,
  "y": 5,
  "nearby_items": [{"position": [6, 5], "name": "table", "type": "interactive_object"}],
  "nearby_npcs": [{"position": [6, 6], "name": "Durnan", "type": null}]
}
```

#### `GET /map_view?session_id=...`

Returns the current map as an ASCII grid with the player marked `P`:

```json
{
  "map": "tavern",
  "width": 25,
  "height": 15,
  "position": {"x": 5, "y": 5},
  "ascii": "#########################\n#B..F....................#\n...",
  "legend": [
    {"token": "P", "names": ["You"], "types": ["player"],
     "members": [{"name": "You", "type": "player"}]},
    {"token": "B", "names": ["counter"], "types": ["interactive_object"],
     "members": [{"name": "counter", "type": "interactive_object"}]},
    {"token": "D", "names": ["Durnan"], "types": ["NPC"],
     "members": [{"name": "Durnan", "type": "NPC"}]},
    {"token": "E", "names": ["Elminster"], "types": ["NPC"],
     "members": [{"name": "Elminster", "type": "NPC"}]},
    {"token": "S", "names": ["chair"], "types": ["interactive_object"],
     "members": [{"name": "chair", "type": "interactive_object"}]},
    {"token": "T", "names": ["table"], "types": ["interactive_object"],
     "members": [{"name": "table", "type": "interactive_object"}]}
  ]
}
```

Walls are `#`, floors are `.`, and every other cell is a single-character token.
`legend` maps each token to the name(s) and type(s) it represents; a token can group
several objects (for example, two doors). `members` keeps the type per name, so clients can
label characters — the web client appends `(NPC)`.

#### `POST /move`

```json
{"session_id": "uuid", "direction": "north"}
```

`direction` is `north`, `south`, `east`, or `west`. Returns `{"movement": true, "state": {...}}`.

#### `GET /npcs?session_id=...`

Returns a list of NPC names placed on the current map.

#### `GET /available_actions?session_id=...`

```json
{
  "actions": ["examine", "pick_up", "talk", "use", "look"],
  "targets": {
    "items": ["table"],
    "npc": ["Durnan"],
    "directions": ["north", "east"]
  },
  "context": "TavernState"
}
```

#### `POST /dialogue`

```json
{"session_id": "uuid", "npc": "Durnan", "option": "start"}
```

Returns `output`, `state`, and:

```json
{
  "dialogue": {
    "active": true,
    "npc": "Durnan",
    "node": "start",
    "text": "Welcome to the Yawning Portal...",
    "options": [{"index": 1, "text": "...", "target": "info_tavern"}]
  },
  "options_dialogue": [ ...same options... ]
}
```

#### `POST /explore`

```json
{"session_id": "uuid"}
```

Runs `look` and returns `output`, `state`, plus nearby `items`, `exits`, and `npc` names.

#### `GET /combat?session_id=...`

```json
{
  "in_combat": true,
  "round": 1,
  "turn_of": "player",
  "enemies": [{"name": "Goblin", "hp": 10, "max_hp": 10}],
  "available_actions": ["attack", "use item", "change equipment", "flee"]
}
```

Outside combat: `{"in_combat": false}`.

#### `POST /combat_action`

```json
{"session_id": "uuid", "action": "attack", "target": ""}
```

Returns `output`, `state`, and `combat`.

### Reference data

#### `GET /missions?session_id=...`

```json
{"active": [], "completed": [], "in_progress": {}}
```

#### `GET /tutorial?session_id=...&type=combat`

Returns all tutorials or one category from `data/tutorials/tutorials.json`.

#### `GET /achievements?session_id=...`

```json
{
  "achievements": [
    {"id": "first_step", "name": "First Step", "unlocked": false, "...": "..."}
  ],
  "total": 5,
  "unlocked": 0
}
```

Achievement conditions are not evaluated by the engine yet, so `unlocked` is `false`
unless a future state supplies unlock data.

#### `GET /assets_info` / `GET /assets_info?type=items`

```json
{"assets": {"characters": [], "environments": [], "items": [], "enemies": [], "note": "..."}}
```

With `type`, `assets` is the matching list. The backend ships no artwork, so these lists
are empty by design; clients should use placeholders.

#### `GET /asset/<path:file_name>`

Serves a file from the repository's `assets/` directory. Returns `404` when missing.

#### `GET /notifications?session_id=...`

Returns in-memory notifications for the session. `POST /read_notification` marks one read
or all read with `{"all": true}`.

#### `POST /export_save`

```json
{"session_id": "uuid", "file_name": "export.json"}
```

Returns the save as a download. The file name is sanitized.

#### `POST /import_save`

Multipart form with a `file` field (`.json`). Saves it under a unique name, creates a new
session, and returns `{session_id, message, player, state}`.

### Web client

#### `GET /app` and `GET /app/<path:file_name>`

Serves `frontend/index.html` and its static files. See `frontend/README.md`.

## Notes for client authors

- Treat `output` as an ordered transcript; render `narration` differently from `narrative`.
- The engine's messages are authoritative. Never derive game state from the AI prose.
- `stats` are modifiers, not base scores.
- Prefer `/list_saves` over `/saves`.
- Handle `409` on save (combat/dialogue/market) as a normal refusal, not a crash.
- `POST /use_ability` is `501` until ability execution exists.
- Asset catalogues are empty; use CSS/placeholder art.
