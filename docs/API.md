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
come from `POST /hint` and `recap` entries from `POST /recap`; both are also kept in the
event log.

## Session flow

1. `POST /start` (new game) or `POST /load` (existing save) returns a `session_id`.
2. Keep the `session_id` and send it with every session-scoped request.
3. `POST /command` advances the game and returns `output` plus the updated `state`.
4. Side panels use `GET /state`, `/abilities`, `/inventory`, `/available_actions`,
   `GET /bounties`, `POST /hint` and `POST /recap`.
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
etc. also move directly. Unknown targets show a message and fall back to the corresponding
menu. In the tavern, `rest`, `sleep`, `recover` and `nap` take a long rest (10 gold), restore
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
quests, conditions, defeat count and the freshest recent events. It is available even when
AI narration is off. With a narrator configured, `source` is `"ai"` and the model rephrases
the same facts; any failure or refusal returns the engine recap with `source: "engine"`.
Recaps never change game state. The result is appended to `/log` with `type: "recap"`, and
previous recaps are excluded from the next recap's recent events.

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
  "abilities": ["Magic Missile", "Mage Shield", "Knock"],
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
use `unlocked` and `required_level` to render them as disabled “Lv 3/5/7” entries.
`combat_only` abilities are refused outside combat; `usable_in_combat: false` marks utility
spells (Knock, Mage Hand, Guidance), which are refused inside combat. `in_combat` reports
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
combat, or no valid target for Knock/Mage Hand) returns `200` with `"used": false` and an
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
      "sell_price": 22,
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
change gold or inventory.

#### `POST /shop/sell`

```json
{"session_id": "uuid", "item": "Healing Potion"}
```

Sells a non-equipped inventory item for half its value. Returns `output`, `state`, `sold`,
`message`, and the updated `shop` object. Equipped gear is refused with a message.

Both shop actions are also available as normal commands, for example `buy Chainmail` or
`shop` to browse the numbered stock list.

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
tavern, the Broken Waystation, the Underroad, the bounty board and the Rune Pillar each
advertise their own commands. In the tavern, `rest` is the long-rest action (10 gold; restores
HP and mana and clears conditions) and `bounties` opens the bounty board. In the market it
includes `shop`, `buy` and `sell`, which drive the shop modal and the numbered terminal shop.
The waystation advertises `confront`, `strongbox`, `rest`, `underroad` and `leave`; the
Underroad advertises `confront`, `cache` and `leave`; the bounty board advertises `accept`,
`claim` and `leave`; the Rune Pillar advertises `study` and `leave`.
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
  "target": "Goblin A",
  "conditions": {"poison": {"damage": 2, "turns": 3}},
  "effects": {"defending": false, "aiming": true},
  "enemies": [
    {"name": "Goblin A", "hp": 10, "max_hp": 10, "ac": 13, "guard": 0,
     "conditions": {"prone": {"turns": 2}},
     "cooldowns": [{"id": "poison_arrow", "name": "Poison Arrow", "remaining": 2}]},
    {"name": "Goblin B", "hp": 10, "max_hp": 10, "ac": 13, "guard": 0,
     "conditions": {}, "cooldowns": []}
  ],
  "allies": [],
  "available_actions": [
    "attack",
    "defend",
    "aim",
    "use item",
    "use ability",
    "change equipment",
    "flee",
    "trip",
    "shove",
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
prone, staggered) include a `turns` counter and tick at the end of each combat round.
`effects.defending` is true while Defend adds +4 AC through the enemy phase;
`effects.aiming` is true until the next weapon attack consumes the advantage.

`trip` and `shove` are data-driven maneuvers from `data/combat/maneuvers.json`. Each makes a
contested Athletics check against the target's Acrobatics or Athletics. Trip applies
`prone`: attacks against the target have advantage, its attacks have disadvantage, and it
spends its next action standing up. Shove applies `staggered`: disadvantage on attacks and
no special abilities for a round. Both conditions affect the target's next action, appear in
the log, and are included in the enemy snapshot.

Outside combat: `{"in_combat": false}`.

#### `POST /combat_action`

```json
{"session_id": "uuid", "action": "attack", "target": "Goblin B"}
```

Returns `output`, `state`, and `combat`. A non-empty `target` selects that enemy before
the action, so `"attack"` with `"Goblin B"` attacks that enemy directly. `"defend"` spends
the turn for +4 AC until the next round, and `"aim"` spends it to give the next weapon attack
advantage; both also work as normal commands via `POST /command`. `"trip"` and `"shove"`
resolve contested skill checks and apply their condition to the selected target; they are
also available as normal commands, menu options 9 and 10, and quick actions.

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
