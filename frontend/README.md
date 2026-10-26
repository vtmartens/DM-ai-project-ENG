# Web client

A dependency-free single-page client for the DM AI backend. No Node, bundler, or build
step is required; Flask serves it at `/app`.

## Run it

```bash
pip install -r requirements.txt
python server.py
```

Open <http://127.0.0.1:5000/app>.

If you serve this folder from a different static server (for example an IDE preview), tell
the client where the API lives:

```
http://localhost:8000/?api=http://127.0.0.1:5000
```

You can also set `localStorage["dm_api_base"]`.

## What it does

- Character creation (name + class, with class details from `GET /classes`).
- Load/delete saves from the start screen or the in-game Load modal.
- Live adventure log, including AI narration styled separately (`type: "narration"`).
- Command input, quick actions from `GET /available_actions`, and menu-number play.
- Natural-language target commands in the tavern, market and map screen: “talk to Durnan”,
  “attack the goblin”, “use Healing Potion”, “go to the market”, “examine the chair”, and
  direction words such as “south” or “move east”. Unknown targets fall back to the normal
  menu.
- Direct approach with pathfinding: “go to Durnan” or “walk to barrel” moves next to the
  target in one command, respecting walls and occupied cells. “go to exit” / “leave” walks
  to the nearest map exit, steps through it and enters the destination state.
- Character panel: HP, level, gold, location, abilities, skills; ability scores show the
  base value with its effective modifier (for example `INT 16 (+4)`), matching the class
  preview. Class abilities are clickable buttons with mana costs; unavailable abilities
  (not enough mana, or combat-only outside combat) are disabled with an explanation.
- Ability use goes through `POST /use_ability`; using one is a combat action, so the enemy
  retaliates and victory/rewards resolve normally.
- Map modal (`GET /map_view`) with the ASCII map, the player's position, and a token
  legend generated from the objects/NPCs actually on the map; characters are labelled
  `(NPC)` so it is clear who can be talked to. Map exits are shown as `>` and named in the
  legend (“Exit to market”).
- Combat card with enemy name/HP and the current round (from `state.combat`).
- Clickable dialogue options (from `state.dialogue`), in addition to typing numbers. The
  play area puts the Adventure log (with the DM narration first) at the top, and the NPC
  dialogue/options card below it. The log keeps the NPC text and consequences but omits
  the numbered choice list, which is shown only as buttons in the dialogue card.
- Inventory list with item details and use/equip actions.
- Save button that writes a timestamped save.
- Light/dark theme, persisted through `POST /preferences` when a session exists.
- Session resume from `localStorage` via `GET /state` and `GET /log`.

## AI narration

Narration is controlled by the server, not the client. Start the API with, for example:

```powershell
$env:DM_AI_NARRATION = "1"
$env:DM_AI_PROVIDER   = "openai"
$env:DM_AI_BASE_URL   = "http://localhost:11434/v1"
$env:DM_AI_MODEL      = "llama3.1:8b"
python server.py
```

See [`../docs/AI_SETUP.md`](../docs/AI_SETUP.md) for free/local model options. When
narration is enabled, the API emits `{"type": "narration", ...}` messages and the client
renders them in an accented, italic style.

## Files

- `index.html` — structure and screens.
- `styles.css` — dark/light themes, responsive layout.
- `app.js` — API calls, state rendering, log, inventory, saves.

The API shape is documented in [`../docs/API.md`](../docs/API.md).
