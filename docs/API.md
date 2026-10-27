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
| `404` | Session, save, item, map or ability not found |
| `409` | Save refused by the engine (combat, dialogue, market transaction) |
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
is preformatted ASCII; render it in a monospace, whitespace-preserving block. `hint` entries
come from `POST /hint`, `description` entries from `POST /describe` and `recap` entries from
`POST /recap`; all are also kept in the event log.

## Session flow

1. `POST /start` (new game) or `POST /load` (existing save) returns a `session_id`.
2. Keep the `session_id` and send it with every session-scoped request.
3. `POST /command` advances the game and returns `output` plus the updated `state`.
4. Side panels use `GET /state`, `/abilities`, `/inventory`, `/available_actions`,
   `GET /bounties`, `POST /hint`, `POST /describe` and `POST /recap`.
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
    "mana_max": 20,
    "ac": 13,
    "attack_bonus": 1,
    "defense": 2,
    "initiative": 0
  },
  "active_quests": [],
  "completed_quests": [],
  "achievements": [],
  "timestamp_achievements": {},
  "conditions": {},
  "stealthed": false,
  "disguised": false,
  "reputation": {
    "factions": [
      {
        "id": "mirt_network",
        "name": "Mirt's Network",
        "description": "Merchants, informants and caravan masters who trade on Mirt's word.",
        "value": 0,
        "tier": "neutral",
        "tier_label": "Neutral"
      }
    ],
    "shop_discount": 0
  },
  "rune_trials": {"best": 0, "runs": 0},
  "rune_shards": 0,
  "cycle": 1,
  "party": {"allies": []},
  "landmark": {"active": false, "state": "TavernState"},
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

`ac` is the player's armor class and `attack_bonus` is the d20 bonus used by weapon
attacks; both follow the equipped weapon's finesse/ranged/attack-stat properties. `defense`
remains the damage-reduction value applied after a hit. Weapon attacks roll
`d20 + attack_bonus` against the target's AC; a natural 20 is a critical hit and a natural 1
always misses. Class abilities and save-based monster abilities resolve by their own rules
rather than this attack roll.

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
  "mana_max": 20,
  "ac": 13,
  "attack_bonus": 1
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

When the player's HP reaches 0 in combat, the engine resolves a defeat recovery instead of
ending the game: HP and mana are set to half their maximum (at least 1 HP), up to 20 gold is
lost, conditions are cleared, and the player is moved to the tavern. Quest progress and map
state are preserved. The response's `state.state` is then `"TavernState"` with the tavern
menu waiting for the next command.

Free-text commands are still accepted. In the tavern, market and on the map screen the
engine resolves targets deterministically: `talk to Durnan`, `attack the goblin`,
`use Healing Potion`, `go to the market`, `examine the chair`, `interact with the barrel`.
`go` / `walk` / `move` / `approach` to an NPC or object also pathfinds to an adjacent cell
in one command, respecting walls and occupied cells. `go to exit` (or `leave`) walks to the
nearest map exit, steps through it and enters the destination state; `go to exit to cellar`
picks a named exit when a map has more than one. On the map screen, `south`, `move east`,
etc. also move directly. On the map screen, `search` (or map menu option 6) searches the
nearby area for hidden traps and caches, `sneak` / `hide` attempts to avoid nearby observers,
and `disarm <trap>` attempts to disable a detected trap from an adjacent cell. Unknown
targets show a message and fall back to the corresponding menu. In the tavern, `rest`,
`sleep`, `recover` and `nap` take a long rest (10 gold), restore
HP and mana to their maximum and clear all conditions; the command is refused with a message
if you are already at full health and mana with no conditions, or if you cannot pay. Map
layout and exits are refreshed from `data/maps/` when an older save or session is loaded, so
fixes to door coordinates apply to existing games.

Keyed doors block both walking and `go to <map>`. A matching key in the inventory opens
the route (fast travel reports the unlock) and `Knock` opens a locked door within two
steps; without either, the command returns a message and the player stays on the same map.
The warehouse route needs the key Violet hands over when her quest is accepted.

#### `GET /state?session_id=...`

Returns the state object above.

#### `GET /log?session_id=...&max=50`

Returns the rolling event log:

```json
{"events": [{"type": "narrative", "text": "...", "time": 1790000000.0}]}
```

#### `POST /hint`

```json
{"session_id": "uuid"}
```

Returns a short, deterministic hint for the current state:

```json
{
  "session_id": "uuid",
  "hint": "The Cellar door is locked. Use Cellar Key on it.",
  "source": "engine"
}
```

`source` is `"engine"` when the hint comes from the engine, or `"ai"` when the configured
narrator rephrased it. AI phrasing uses the same opt-in narrator as narration
(`DM_AI_NARRATION`); without it, or on any model failure/refusal, the engine hint is returned
unchanged. Hints never change game state. The hint is also appended to the `/log` stream with
`type: "hint"`.

#### `POST /recap`

```json
{"session_id": "uuid"}
```

Returns a short summary of the story so far:

```json
{
  "session_id": "uuid",
  "recap": "Aria the Wizard is level 1, in the Market, with 6/6 HP and 20/20 mana, carrying 20 gold. Active quest: Shadows in the Market — ... (in progress). Recently: ...",
  "source": "engine"
}
```

The deterministic recap covers the player, location, HP/mana, gold, active and completed
quests, conditions, faction standing and shop discount, Runeheart/Sanctum campaign state,
Rune Trials depth/runs, capstone status, defeat count and the freshest recent events. It is
available even when AI narration is off. With a narrator configured, `source` is `"ai"` and
the model rephrases the same facts; any failure or refusal returns the engine recap with
`source: "engine"`. Recaps never change game state. The result is appended to `/log` with
`type: "recap"`, and previous recaps are excluded from the next recap's recent events.

The same opt-in narrator receives a compact context containing conditions, active quests,
faction standing, campaign flags, Rune Trials progress, combat target/round/cover/flanking,
nearby names and recent memory. See [`AI_SETUP.md`](AI_SETUP.md#narrator-context).

#### `POST /describe`

```json
{"session_id": "uuid"}
```

Returns a short description of the current location:

```json
{
  "session_id": "uuid",
  "description": "Warm firelight and pipe smoke fill the Yawning Portal. ...",
  "source": "engine"
}
```

The deterministic description comes from `data/scenes/locations.json` plus the player's
nearby NPCs/objects, cleared-area state and stealth flag. With a narrator configured,
`source` is `"ai"` and the model adds atmosphere around the same facts; any failure or
refusal returns the engine description with `source: "engine"`. Descriptions never change
game state. The result is appended to `/log` with `type: "description"` and is excluded from
the next recap's recent-event input.

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
  "abilities": ["Magic Missile", "Mage Shield", "Knock", "Detect Magic"],
  "ability_details": [
    {
      "id": "magic_missile",
      "name": "Magic Missile",
      "class": "wizard",
      "description": "Unerring arcane force deals 8 damage to your opponent, ignoring armor.",
      "mana_cost": 5,
      "combat_only": true,
      "usable_in_combat": true,
      "ignore_defense": true,
      "effect": {"type": "damage", "flat": 8},
      "required_level": 1,
      "unlocked": true
    },
    {
      "id": "knock",
      "name": "Knock",
      "class": "wizard",
      "description": "Open a locked door or chest within two steps without needing its key.",
      "mana_cost": 5,
      "combat_only": false,
      "usable_in_combat": false,
      "ignore_defense": false,
      "effect": {"type": "knock"},
      "required_level": 1,
      "unlocked": true
    },
    {
      "id": "fireball",
      "name": "Fireball",
      "class": "wizard",
      "description": "A level-3 burst of flame deals 12 damage.",
      "mana_cost": 8,
      "combat_only": true,
      "usable_in_combat": true,
      "ignore_defense": false,
      "effect": {"type": "damage", "flat": 12},
      "required_level": 3,
      "unlocked": false
    }
  ],
  "skills": ["arcana", "history"],
  "skill_proficiencies": {"arcana": true, "history": true},
  "mana": 20,
  "mana_max": 20,
  "in_combat": false
}
```

`abilities` remains a name list for simple clients and contains only unlocked abilities.
`ability_details` includes every class ability, including locked progression abilities;
use `unlocked` and `required_level` to render them as disabled “Lv 3/5/7/10” entries.
Level 10 unlocks each class capstone: Last Stand, Meteor Swarm, Assassinate or Divine
Intervention.
`combat_only` abilities are refused outside combat; `usable_in_combat: false` marks utility
spells (Knock, Mage Hand, Guidance, Detect Magic, Disguise Self, Comprehend Languages),
which are refused inside combat. `in_combat` reports
the current context.

#### `POST /use_ability`

```json
{"session_id": "uuid", "ability_id": "magic_missile"}
```

Use `ability_id` or `ability_name` (`"Magic Missile"`). The response has the same `output`,
`state`, `state_name` and `end` fields as `POST /command`, plus:

```json
{
  "used": true,
  "combat": {"in_combat": true, "...": "..."},
  "ability": {"name": "Magic Missile", "mana_cost": 5}
}
```

An unknown or not-yet-unlocked ability is `404`. A known, unlocked ability that cannot
currently be used (no mana, a combat-only ability outside combat, a utility spell inside
combat, or no valid target for Knock/Mage Hand/Comprehend Languages/Detect Magic) returns
`200` with `"used": false` and an
explanatory message in `output`; no mana is spent. In combat the ability consumes the
player's action, then the enemy retaliates or victory resolves normally.

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

Runs the command `<action> <item>` and returns `output` and `state`. Using a key tries an
adjacent matching lock (keys are reusable); using poison starts a damage-over-time effect;
using an antidote clears poison from the player.

#### `POST /equipment`

```json
{"session_id": "uuid", "action": "equip", "item": "Short Sword", "slot": ""}
```

`action` is `equip`, `unequip`, or `examine`. Returns `output`, `state`, and `equipment`.
Equipping applies every stat effect on the item, and unequipping removes the same effects.
Weapon `properties` may include `finesse`, `ranged`, `attack_stat` and `damage_bonus`;
`stats.attack_bonus` follows the equipped weapon's attack stat.

#### `GET /shop?session_id=...`

Returns the market stock and the player's sellable inventory. This endpoint is only
available while the current state is `MarketState`; otherwise it returns `409`.

```json
{
  "gold": 100,
  "stock": [
    {
      "name": "Chainmail",
      "type": "armor",
      "category": "Armor",
      "price": 45,
      "base_price": 45,
      "sell_price": 22,
      "reputation_discount": 0,
      "description": "Armor of interwoven metal rings...",
      "effect": {"defense": 4},
      "effect_text": "AC +4",
      "properties": {},
      "properties_text": "",
      "rarity": "common"
    }
  ],
  "sellable": [
    {
      "name": "Healing Potion",
      "type": "heal",
      "category": "Inventory",
      "price": 12,
      "description": "A potion that restores 10 hit points",
      "effect": {"heal": 10},
      "effect_text": "restores 10 HP",
      "rarity": "common",
      "equipped": false
    }
  ]
}
```

#### `POST /shop/buy`

```json
{"session_id": "uuid", "item": "Chainmail"}
```

Buys one stock item at `price`. Returns `output`, `state`, `bought`, `message`, and the
updated `shop` object. A failed purchase returns `bought: false` with the reason; it does not
change gold or inventory. Prices already include the Mirt's Network discount shown in
`reputation.shop_discount`; `base_price` keeps the undiscounted value.

#### `POST /shop/sell`

```json
{"session_id": "uuid", "item": "Healing Potion"}
```

Sells a non-equipped inventory item for half its value. Returns `output`, `state`, `sold`,
`message`, and the updated `shop` object. Equipped gear is refused with a message.

Both shop actions are also available as normal commands, for example `buy Chainmail` or
`shop` to browse the numbered stock list.

#### `GET /forge?session_id=...`

Available while the current state is `ForgeState` inside the cleared Sanctum. Returns the
player's Rune Shards, gold and recipe list:

```json
{
  "shards": 5,
  "gold": 80,
  "recipes": [
    {
      "id": "rune_draught",
      "name": "Rune Draught",
      "description": "Brew a restorative rune-water potion.",
      "shards": 2,
      "gold": 20,
      "result": "Rune Draught",
      "unique": false,
      "crafted": false,
      "can_craft": true,
      "reasons": []
    }
  ]
}
```

Recipes live in `data/crafting/recipes.json`. `reasons` explains insufficient shards/gold
or an already-forged unique item.

#### `POST /forge/craft`

```json
{"session_id": "uuid", "recipe_id": "rune_draught"}
```

Returns `output`, `state`, `crafted`, `message` and the refreshed `forge` object. Successful
crafts consume shards and gold, add the result item and mark unique recipes with a
`crafted:<recipe_id>` reward flag. Outside `ForgeState`, `/forge` and `/forge/craft` return
`409`.

#### `GET /black_market?session_id=...`

Available while the current state is `BlackMarketState`, reached from Nessa's cache in the
cleared Underroad. Returns the player's tier, standing, gold, discount and stock:

```json
{
  "unlocked": true,
  "reputation": 16,
  "tier": "friendly",
  "tier_label": "Friendly Stock",
  "discount": 0,
  "gold": 100,
  "items": [
    {
      "name": "Greater Healing Potion",
      "tier": "friendly",
      "tier_label": "Friendly Stock",
      "price": 40,
      "unique": false,
      "purchased": false,
      "available": true,
      "can_buy": true,
      "reasons": []
    }
  ]
}
```

Stock lives in `data/items/black_market_stock.json`. The shop opens only after
`quiet_cargo` is completed and Underroad Smugglers standing is at least 5. Lower tiers remain
buyable at higher standing; locked rows stay visible with their requirement. Trusted standing
adds a 5% discount, Allied adds 10%. `unique` stock is one-time and is recorded in
`claimed_rewards` as `black_market:<item name>`.

#### `POST /black_market/buy`

```json
{"session_id": "uuid", "item": "Smoke Bomb"}
```

Returns `output`, `state`, `bought`, `message` and the refreshed `black_market` object.
Purchases charge gold and add the item to the inventory. Locked, already-sold or unaffordable
items return `bought: false` with an explanatory message. Outside `BlackMarketState`,
`GET /black_market` returns `409` and the buy call returns `bought: false`.

#### `GET /bounties?session_id=...`

Returns the tavern bounty board. Only available in `TavernState` or `BountyBoardState`;
other states return `409`.

```json
{
  "gold": 100,
  "active_count": 1,
  "max_active": 2,
  "bounties": [
    {
      "id": "bounty_goblin_road",
      "title": "Goblin Toll",
      "description": "Goblin scouts have been shaking down travellers...",
      "objective": "Defeat 2 goblins.",
      "reward": {"gold": 40, "experience": 50},
      "status": "active",
      "progress": 1,
      "target_count": 2
    }
  ]
}
```

#### `POST /bounties/accept` / `POST /bounties/claim`

```json
{"session_id": "uuid", "bounty_id": "bounty_goblin_road"}
```

Accept adds the contract to the quest log, subject to the two-active limit. Claim requires a
ready contract and grants its rewards. Responses include `output`, `state`, `accepted` or
`claimed`, and the refreshed `bounties` object. Both actions are also available through the
tavern's numbered Bounty Board state.

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

Walls are `#`, floors are `.`, and `>` marks a map exit with no interactive object on its
cell. Cells that have a door object show the door's own token instead. Every other cell is a
single-character token. `legend` maps each token to the name(s) and type(s) it represents
(a `>` entry is named e.g. “Exit to market”); a token can group several objects. `members`
keeps the type per name, so clients can label characters — the web client appends `(NPC)`.
Undiscovered objects are deliberately omitted from both `ascii` and `legend`; a successful
map search reveals them, and only then do they appear in `/map`, `/map_view`, nearby lists
and targeted commands.

#### Searching and traps

Map menu option 6 or `search` rolls Perception and compares the result with each hidden
object's `detection_dc` inside a two-cell radius. A success reveals the object and logs its
name; hidden traps, caches and other objects remain absent from `/map_view`, `/map` and
targeted commands until then.

Detected traps can be disarmed from an adjacent cell with `disarm <trap>` or by interacting
with the trap. The disarm roll is an Investigation check against `disarm_dc`. On failure the
trap may spring (`trigger_on_failure`), calling for its `saving_throw_ability` save against
`saving_throw_difficulty` and dealing `damage` on failure. A trap is one-use: once triggered
or disarmed its state is persisted with the map. Trap definitions live in
`data/items/interactive_objects.json`; Cellar, Vault and Underroad place the shipped examples.

#### Stealth and surprise

Map menu option 7, `sneak` or `hide` rolls Stealth against the highest passive Perception
of NPCs within four cells. Success sets `state.stealthed` to `true` and shows a **Hidden**
tag in the web client. Moving while hidden (including `/move`, map-menu movement and
pathfinding) re-rolls the check; failure clears the flag.

Attacking an NPC while hidden breaks stealth and starts `CombatState` with a surprise
round. The opening weapon attack has advantage, the fastest enemy cannot seize initiative,
and the enemies lose their first turn. `/combat` exposes `surprised` at the top level and on
each living enemy, and the web client renders **Surprise round** / **Surprised** tags. The
pending surprise state is serialized with the combat state.

#### `POST /move`

```json
{"session_id": "uuid", "direction": "north"}
```

`direction` is `north`, `south`, `east`, or `west`. Returns `{"movement": true, "state": {...}}`.

The `road` map is reachable from the market at `(33, 7)` and starts at `(2, 7)`. Moving on
the road (via `POST /move`, direction commands, or the map menu) can start a wandering
encounter after a two-step grace period, with a three-step cooldown after each encounter.
At level 1–2 the encounter table uses Goblin Scouts and Wolf Pack; Orc Patrol is added from
level 3. Victories use the curated encounter reward and can additionally roll loot from
`data/monsters/loot_tables.json` into the player's inventory.

A triggered road step can instead open a data-driven `RoadEventState`: a traveling merchant
with shop stock, a one-time healing shrine, a stranded wagon with an Investigation check, a
wounded traveler reward, or an ambush that uses the road encounter system. Event definitions
live in `data/road/road_events.json`; one-time events are filtered after their reward flag is
recorded in `player.claimed_rewards`.

The road's far end leads to the **Broken Waystation** (`WaystationState`). Its actions are
`confront`, `strongbox`, `rest` and `leave`. Confronting the bandits starts the fixed
`waystation_chief` encounter; victory marks the area cleared, readies Mirt's
`waystation_trouble` quest and returns to the waystation menu. Opening the cleared strongbox
grants the unique Wayfarer's Cloak and 50 gold; the cleared campfire fully restores HP, mana
and clears conditions.

#### The Underroad

After clearing the Broken Waystation, the strongbox yields a Bandit Ledger and starts Mirt's
`underroad_chapter` quest. The Waystation menu then offers **Descend into the Underroad**,
which opens `UnderroadState` with `confront`, `cache` and `leave`. Confronting the Smuggler
Lord starts the fixed `underroad_boss` encounter; victory clears `underroad`, readies the
quest and unlocks the Underroad Delver achievement. The cleared cache grants the unique
Underroad Signet and 75 gold once. The Underroad map is hidden from the destination menu
until the Waystation is cleared.

After the chapter is turned in, the cleared tunnel also offers `talk to Nessa` (menu option
5). Nessa gives **The Quiet Cargo**: search the hidden Watch Impound Wagon beside the old
warehouse for the Cargo Manifest, then return to her. The manifest can go to Nessa
(+8 Underroad Smugglers and the Runner's Satchel), Violet's Watch (+8 Violet's Watch and
100 gold) or Mirt's Network (+8 Mirt's Network and 100 gold); all complete the quest and
unlock The Quiet Cargo achievement. The wagon is a hidden object with detection DC 13, so
it is found through the map's normal `search` action.

Completing The Quiet Cargo with positive Underroad standing also adds `Nessa's cache`
(menu option 6) to the cleared Underroad. It opens `BlackMarketState` and the tiered
contraband stock described under `GET /black_market`.

#### The Sealed Sanctum

After the Underroad is cleared and its cache has been claimed, the Underroad menu offers
**Enter the Sealed Sanctum**. The Signet wakes the sealed door. `SanctumState` starts the
`sanctum_chapter` quest and has a warded-threshold phase followed by the main menu:

- `amulet` raises the Rune-Ward Amulet, bypassing the ward.
- `force` calls for a DC 14 Constitution save; failure costs up to 8 HP and applies
  Weakened for two turns, but the player still gets through.
- `confront` starts the fixed `sanctum_boss` encounter against the Rune Warden and two
  Rune Sentinels. Victory clears `sanctum`, readies the quest and unlocks the Sanctum
  Breaker achievement.
- `vault` opens the Runeheart vault once for 120 gold and a choice: keep the unique
  Runeheart Amulet, give it to Mirt for +12 Mirt's Network standing and an extra 200 gold,
  or give it to Violet for +12 Violet's Watch standing and an extra 100 gold.
- `trials` opens the repeatable Rune Trials endgame.
- `forge` opens the Rune Forge crafting state.
- `leave` returns to the Underroad.

`/available_actions` reflects the current phase (`amulet`/`force` before the ward, then
`confront`/`vault`/`trials`/`leave`). Mirt offers the chapter after the Underroad is
completed, reminds, accepts the Rune Warden turn-in and provides the epilogue dialogue. The
`sanctum` map is hidden from the destination menu and is reachable only through the
Underroad.

#### The Rune Trials

After clearing the Sanctum, the cleared Sanctum menu offers **Enter the Rune Trials**.
`RuneTrialsState` runs `data/trials/rune_trials.json`:

- Five escalating waves built from existing monsters.
- Data-driven modifiers (`Empowered`, `Warded`, `Frenzied`) adjust enemy HP, damage or AC.
- Each wave awards Rune Shards, and a full clear adds completion shards.
- After each non-final victory, choose one boon: restore HP, restore mana or clear
  conditions.
- `state.rune_trials.best` tracks the deepest wave reached; `runs` counts full clears.
  `state.rune_shards` is the crafting currency.
- A completed run grants the trial completion reward and unlocks the Rune Trials Adept and
  Champion achievements. A defeat or flight ends the current run but preserves best depth.

The state exposes phase-dependent quick actions: `begin`/`leave` while preparing,
`mend`/`focus`/`cleanse`/`leave` while choosing a boon, and `restart`/`leave` after clearing
all five waves. Trial and boon state survive save/load.

#### The Rune Pillar

The vault's Rune Pillar is a `RunePillar` interactive object. Interacting with it opens
`RunePillarState` with actions `study` and `leave`. Studying makes a DC 15 Arcana check using
the player's Intelligence and Arcana proficiency, including condition advantage/disadvantage
and Guidance. Success grants the unique Rune-Ward Amulet once and records it in
`player.claimed_rewards`; failure deals 2 HP of damage, and the check can be retried. The
solved state and item survive save/load.

#### `GET /npcs?session_id=...`

Returns a list of NPC names placed on the current map.

#### `GET /available_actions?session_id=...`

```json
{
  "actions": ["rest", "bounties", "talk", "fight", "travel", "inventory", "map", "save"],
  "targets": {
    "items": ["table"],
    "npc": ["Durnan"],
    "directions": ["north", "east"]
  },
  "context": "TavernState"
}
```

The action list depends on the current state: combat, dialogue, market, inventory, the
tavern, the map, the Broken Waystation, the Underroad, the bounty board and the Rune Pillar
each advertise their own commands. In the tavern, `rest` is the long-rest action (10 gold;
restores HP and mana and clears conditions) and `bounties` opens the bounty board. In the
market it includes `shop`, `buy` and `sell`, which drive the shop modal and the numbered
terminal shop. The map advertises `search`, `sneak` and its four movement directions. The waystation
advertises `confront`, `strongbox`, `rest`, `underroad` and `leave`; the Underroad advertises
`confront`, `cache`, `sanctum`, `talk to Nessa` and `leave` after the area is cleared, adding
`Nessa's cache` when the black market is unlocked; the Sealed
Sanctum advertises its current `amulet`/`force` or `confront`/`vault`/`trials`/`forge`
actions; the Rune Trials advertise `begin`/`leave`, then their current boons; the Rune Forge
advertises its recipe ids and `leave`; Nessa's cache advertises its purchasable item names
and `leave`; the bounty board advertises `accept`, `claim` and `leave`; the Rune Pillar
advertises `study` and `leave`.
Bounty contracts are ordinary quests with `bounty: true` and `repeatable: true`, so their
progress and ready state appear in `GET /missions` and the web quest panel. Claimed bounties
return to the available list, while only the latest completion record is kept.

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

For web sessions, `output` contains the NPC text and consequences but not the numbered
choice list or “Choose an option” prompt; render `state.dialogue.options` as buttons
instead. Terminal-style IO still logs the numbered choices.

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
  "surprised": false,
  "target": "Goblin A",
  "conditions": {"poison": {"damage": 2, "turns": 3}},
  "effects": {"defending": false, "aiming": true},
  "enemies": [
    {"name": "Goblin A", "hp": 10, "max_hp": 10, "ac": 13, "guard": 0,
     "conditions": {"prone": {"turns": 2}}, "surprised": false,
     "cooldowns": [{"id": "poison_arrow", "name": "Poison Arrow", "remaining": 2}]},
    {"name": "Goblin B", "hp": 10, "max_hp": 10, "ac": 13, "guard": 0,
     "conditions": {}, "surprised": false, "cooldowns": []}
  ],
  "allies": [],
  "available_actions": [
    "attack",
    "defend",
    "aim",
    "take cover",
    "use item",
    "use ability",
    "change equipment",
    "flee",
    "trip",
    "shove",
    "stand up",
    "choose target"
  ]
}
```

Enemy attacks use data-driven `attack_stat` and `damage_bonus` values from the monster's
stats, so archers can roll with Dexterity while brutes use Strength; the combat log labels
the stat (`STR`/`DEX`/`INT`).

`target` is the enemy attacks and abilities currently affect. `choose target` appears when more
than one enemy is alive; clients can also send `target <name>` as a command. `conditions` is
the player's active condition map (same shape as `state.conditions`); each enemy also carries
its own `conditions` map. `guard` is the enemy's remaining physical guard, and `cooldowns`
lists ability names and rounds until reuse. Timed conditions (burning, frightened, weakened,
prone, staggered, blinded, restrained, charmed) include a `turns` counter and tick at the end
of each combat round. Blinded and Restrained give the player's attacks and checks
disadvantage while attacks against them have advantage; Restrained also sets
`blocks_escape`, so `flee` is refused. Charmed records the charmer's name in the condition
entry's `source` and prevents weapon attacks and damaging class abilities against that
enemy only.
`effects.defending` is true while Defend adds +4 AC through the enemy phase;
`effects.aiming` is true until the next weapon attack consumes the advantage.
`effects.covering` grants +2 AC and advantage on Dexterity saves through the enemy phase;
`effects.flanking` is true while a living ally is in the fight, granting +2 to the player's
weapon attacks. `surprised` is true during the opening round after a stealth attack; it is
also repeated on each living enemy for status rendering.

`trip` and `shove` are data-driven maneuvers from `data/combat/maneuvers.json`. Each makes a
contested Athletics check against the target's Acrobatics or Athletics. Trip applies
`prone`: attacks against the target have advantage, its attacks have disadvantage, and it
spends its next action standing up. Shove applies `staggered`: disadvantage on attacks and
no special abilities for a round. Both conditions affect the target's next action, appear in
the log, and are included in the enemy snapshot.

`take cover` spends the turn for +2 AC and advantage on Dexterity saves until the next
round; the combat card shows **Cover**. It is offered only when the player is adjacent to a
wall or an object with `provides_cover` (tables, barrels, counters, statues, chests and
similar terrain); otherwise the action is refused. While any living ally remains in the
fight, the player's weapon attacks gain +2 to hit and the card shows **Flanking**. Both
effects are exposed under `effects.covering` and `effects.flanking`.

Monsters may also declare `maneuvers` in their data. Wolves Trip, bandits/smugglers/sentinels
Shove, and the Rune Warden uses both. An enemy checks its maneuver chance with a d100, skips
maneuvers whose condition is already on the player, and starts a two-round maneuver cooldown
after using one. A prone player can use the `stand up` action from the combat menu, quick
actions or `/combat_action`; it costs the turn and clears Prone. Staggered prevents the player
from using class abilities, matching the enemy rule.

Conditions can declare an `escape_action`. Restrained offers **Break Free** (Athletics vs
DC 13) and Charmed offers **Resist the Charm** (Wisdom save vs DC 13); the action's label is
added to `available_actions`, shown after Stand Up in the menu, and costs the turn whether it
succeeds or fails. A successful action removes the condition; otherwise the normal
end-of-round save can still end it. Enemy abilities that apply Charmed use
`"source": "attacker"`, which the engine resolves to the enemy's name.

Blinding Powder, Sticky Web and Silver Tongue are enemy abilities in
`data/monsters/abilities.json`; bandits, giant spiders and the Smuggler Lord reference them.
The Underroad's hidden Blinding Dust Trap applies Blinded when its save fails.

Outside combat: `{"in_combat": false}`.

#### `POST /combat_action`

```json
{"session_id": "uuid", "action": "attack", "target": "Goblin B"}
```

Returns `output`, `state`, and `combat`. A non-empty `target` selects that enemy before
the action, so `"attack"` with `"Goblin B"` attacks that enemy directly. `"defend"` spends
the turn for +4 AC until the next round; `"aim"` gives the next weapon attack advantage;
`"take cover"` grants +2 AC and advantage on Dexterity saves until the next round when
nearby cover exists. All three are also available as normal commands via `POST /command`.
`"trip"` and `"shove"`
resolve contested skill checks and apply their condition to the selected target; they are
also available as normal commands, menu options 10 and 11, and quick actions. `"stand up"`
spends the turn to clear the player's Prone condition and is advertised only while prone.
`"break free"` and `"resist the charm"` likewise spend the turn on the active condition's
escape action and are advertised only while that condition is present.

Enemies also act on data-driven abilities with cooldowns. Their telegraphs and effects appear
in `output`; `combat.enemies` reflects the resulting HP. Abilities may deal damage, poison,
heal the enemy, or raise a guard that reduces the next physical attack. Some abilities call
for an ability save (CON, DEX, WIS, etc.); the roll, DC and outcome appear in `output`, and a
success halves or negates damage and can prevent poison.

### Reference data

#### `GET /missions?session_id=...`

```json
{
  "active": [
    {
      "id": "shadows_of_the_market",
      "title": "Shadows in the Market",
      "description": "Hooded figures have been seen around the old warehouse...",
      "objective": "Defeat Vargas and break up the cult cell in the old warehouse.",
      "target": "Vargas",
      "turn_in": "Violet",
      "status": "active"
    }
  ],
  "completed": [],
  "in_progress": {
    "shadows_of_the_market": {"status": "active"}
  }
}
```

Active quests can be `active` or `ready`; `ready` means the objective is complete and the
player must speak to the `turn_in` NPC before the reward is granted. Completed quests move
to `completed` with `"status": "completed"`.

#### `GET /reputation?session_id=...`

```json
{
  "factions": [
    {
      "id": "mirt_network",
      "name": "Mirt's Network",
      "description": "Merchants, informants and caravan masters who trade on Mirt's word.",
      "value": 12,
      "tier": "friendly",
      "tier_label": "Friendly"
    }
  ],
  "shop_discount": 5
}
```

Faction values start at 0. The tiers are `hostile` (≤ -10), `neutral`, `friendly` (10+),
`trusted` (25+) and `allied` (40+). Quest completion applies the quest's `faction` and
`reputation` values, and a friendly-or-better `quest_bonus` adds gold to the reward. Mirt's
Network `shop_discount` reduces market buy prices. Dialogue options may gate on
`{"reputation": {"faction": "mirt_network", "min": 10}}`; reputation conditions can also be
combined with quest conditions through `all` / `any`. The same reputation object is included
in `GET /state`.

#### `GET /campaign?session_id=...`

```json
{
  "chapters": [
    {
      "id": "vargas_debt",
      "title": "A Debt to Collect",
      "objective": "Find Vargas in the old warehouse and collect Mirt's debt.",
      "turn_in": "Mirt",
      "status": "active"
    }
  ],
  "completed_chapters": 1,
  "total_chapters": 7,
  "campaign_complete": false,
  "runeheart_choice": null,
  "reputation": {"factions": [], "shop_discount": 0},
  "rune_trials": {"best": 0, "runs": 0},
  "rune_shards": 0,
  "cycle": 1,
  "capstone": {"name": "Last Stand", "unlocked": false},
  "landmark": {"state": "TavernState", "location": "tavern"}
}
```

Chapters use the seven main story quests and report `not_started`, `active`, `ready` or
`completed`. The same campaign object is included in `GET /state`; the web client renders it
as the Campaign panel.

#### `GET /party?session_id=...`

Returns recruited allies, their base HP and persistent stance:

```json
{
  "allies": [
    {
      "name": "Violet",
      "hp": 14,
      "hp_max": 14,
      "stance": "guard",
      "stance_label": "Guard",
      "loyalty": "friendly",
      "loyalty_label": "Friendly",
      "will_act": true,
      "faction": "violet_watch",
      "description": "...",
      "abilities": [
        {
          "id": "field_dressing",
          "name": "Field Dressing",
          "description": "Bind a wound and restore health.",
          "cooldown": 3,
          "effect": {"type": "heal", "amount": 8}
        }
      ]
    }
  ]
}
```

#### `POST /party/stance`

```json
{"session_id": "uuid", "ally": "Violet", "stance": "support"}
```

Set `attack`, `guard` or `support`. Returns `output`, `state`, `changed` and the refreshed
`party` object. The same object is included in `GET /state`. Combat quick actions include
`Violet: attack`, `Violet: guard`, `Violet: support` and her ability commands; `/combat`
ally rows include `stance`, `loyalty`, `will_act`, abilities and active cooldowns. Guard
adds +1 AC to the player while the guarding ally lives; Support selects the most useful
available heal/condition-clearing ability. Ally abilities have round cooldowns, improve
with friendly loyalty and are refused by hostile allies.

#### `GET /landmark?session_id=...`

Returns the UI summary for the current menu-driven landmark. Outside a landmark state:

```json
{"active": false, "state": "TavernState"}
```

Inside one:

```json
{
  "active": true,
  "id": "waystation",
  "title": "The Broken Waystation",
  "description": "The ruined waystation is quiet...",
  "status": ["cleared", "strongbox waiting"],
  "actions": ["confront", "strongbox", "rest", "underroad", "leave"]
}
```

Landmark IDs are `waystation`, `underroad`, `sanctum`, `rune_trials` and `forge`. Status
entries cover clear/loot/ward/wave/boon/shard state; actions are the same commands accepted by
the corresponding state. The object is also included in `GET /state`.

#### New Cycle

After completing the `sanctum_chapter` quest, the tavern menu gains **16. Begin a new
cycle**. The same action is available as `new cycle` / `ng+`. A confirmation prompt then
calls `Game.start_new_cycle()`:

- resets quests, cleared areas, campaign flags, map state, conditions, allies and defeats
- clears `claimed_rewards` except `crafted:*` forge flags and `black_market:*` unique
  purchase flags
- keeps level, XP, equipment, inventory, gold, achievements, faction standing, Rune Shards,
  Rune Trials best/runs and forged gear
- increments `player.cycle`, restores HP/mana and returns to the Tavern

Enemy HP, damage and AC scale by `data/cycles/cycles.json`; encounter, quest and trial
completion rewards scale by the same cycle data. `GET /state` exposes the cycle in the
player/campaign data, and the Cyclebreaker achievement unlocks on cycle 2.

#### `GET /tutorial?session_id=...&type=combat`

Returns all tutorials or one category from `data/tutorials/tutorials.json`.

#### `GET /achievements?session_id=...`

```json
{
  "achievements": [
    {"id": "first_step", "name": "First Step", "unlocked": true, "unlock_date": "2026-10-26 20:15:00", "...": "..."}
  ],
  "total": 8,
  "unlocked": 1
}
```

Conditions are evaluated by the engine (`core/achievements.py`) from gameplay events:
movement, combat victories, unique items collected, areas visited, equipped equipment,
gold, damage-free victory streaks and quests completed without fighting. Unlock ids and
timestamps are also exposed as `achievements` / `timestamp_achievements` in `GET /state`
and survive save/load.

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
- `POST /use_ability` spends mana and consumes the combat turn; check `used` and render
  `output` even when it is `false`.
- Asset catalogues are empty; use CSS/placeholder art.
