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
- Character panel: HP, level, gold, location, stats, abilities, skills.
- Map modal (`GET /map_view`) with the ASCII map and the player's position.
- Combat card with enemy name/HP and the current round (from `state.combat`).
- Clickable dialogue options (from `state.dialogue`), in addition to typing numbers.
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
