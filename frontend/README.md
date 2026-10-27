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
- Command input, quick actions from `GET /available_actions`, and menu-number play. The
  tavern quick actions include **Rest** (10 gold); resting restores HP/mana and clears
  conditions.
- Natural-language target commands in the tavern, market and map screen: “talk to Durnan”,
  “attack the goblin”, “use Healing Potion”, “go to the market”, “examine the chair”, and
  direction words such as “south” or “move east”. Unknown targets fall back to the normal
  menu.
- Direct approach with pathfinding: “go to Durnan” or “walk to barrel” moves next to the
  target in one command, respecting walls and occupied cells. “go to exit” / “leave” walks
  to the nearest map exit, steps through it and enters the destination state.
- Character panel: HP, level, gold, location, abilities, skills; ability scores show the
  base value with its effective modifier (for example `INT 16 (+4)`), matching the class
  preview. The stats panel also shows armor class, attack bonus and initiative. Class abilities are clickable
  buttons with mana costs; unavailable abilities
  (not enough mana, or combat-only outside combat) are disabled with an explanation.
  Utility spells (Knock, Mage Hand, Guidance) are tinted blue and are disabled during
  combat, while combat abilities are disabled outside it.
  Progression abilities appear as dashed `Lv 3/5/7` entries until the player unlocks them.
- Ability use goes through `POST /use_ability`; using one is a combat action, so the enemy
  retaliates and victory/rewards resolve normally.
- Map modal (`GET /map_view`) with the ASCII map, the player's position, and a token
  legend generated from the objects/NPCs actually on the map; characters are labelled
  `(NPC)` so it is clear who can be talked to. Map exits are shown as `>` and named in the
  legend (“Exit to market”). The **Road** area is on the same map, and moving there can
  trigger wandering encounters or roadside events — a traveling merchant, shrine, stranded
  wagon, wounded traveler or ambush. Its far end leads to the **Broken Waystation**, a
  menu-driven boss landmark with a strongbox, a cleared-area campfire rest and a Mirt quest
  hook. After clearing it, descend into the Underroad chapter, fight the Smuggler Lord and
  claim the unique cache reward. The signet then opens the capstone Sealed Sanctum, where
  the Rune Warden guards the Runeheart vault; the Sanctum menu and its log-driven ward/boss
  flow use the same client rendering. The vault's Rune Pillar is also interactive: use
  `interact with Rune Pillar` nearby to attempt its Arcana challenge. On the map screen,
  **Search** quick actions make a Perception check for hidden traps and caches; hidden
  objects stay out of the map and legend until found, and detected traps can be disarmed
  with `disarm <trap>` or by interacting with them. **Sneak** makes a Stealth check against
  nearby NPCs; a hidden character appears as a **Hidden** tag, and attacking from stealth
  starts a surprise round shown as **Surprised** tags on the enemies.
- **Bounties** button in the tavern opens a focus-trapped Bounty Board modal (`GET /bounties`)
  with each contract's objective, status, progress and reward. **Accept** and **Claim**
  buttons call `/bounties/accept` and `/bounties/claim`; accepted contracts also appear in
  the Quests panel with their progress.
- Combat card with every enemy's name/HP, armor class and the current round (from `state.combat`).
  With multiple enemies, each row has a Target button; the current target is marked.
  Defending and Aiming effects appear as status tags, and if the player is defeated the log
  explains the recovery and the session returns to the tavern.
  Recruited allies appear below the enemies. Enemy abilities and their telegraphs appear in
  the adventure log, and the card reflects HP changes. Status tags show each enemy's physical
  guard, ability cooldowns and conditions such as Prone or Staggered. Trip and Shove are
  available as quick actions; their contested Athletics checks and outcomes appear in the log.
- Conditions panel driven by `state.conditions`: poisoned duration/damage, Guidance,
  advantage/disadvantage, and timed burning/frightened/weakened effects are rendered as
  colour-coded tags and update after each action.
- Quests panel driven by `GET /missions`, showing each active quest and its objective.
  Completed objectives change to “Ready to turn in — speak to …” until rewards are collected.
- Achievements panel driven by `GET /achievements`, with an unlocked/total count, score,
  description and unlock date for each entry. Locked achievements stay visible as goals,
  and a toast announces new unlocks as they happen.
- **Hint** button (`POST /hint`) that appends a Dungeon Master hint to the log. The engine
  always supplies a deterministic hint; when AI narration is enabled the model may rephrase
  it, and any failure falls back to the engine wording.
- **Recap** button (`POST /recap`) that appends a “Previously” summary of the player, quests,
  conditions, defeats and recent events. It uses the same engine fallback and optional AI
  rephrasing as hints.
- Clickable dialogue options (from `state.dialogue`), in addition to typing numbers. The
  play area puts the Adventure log (with the DM narration first) at the top, and the NPC
  dialogue/options card below it. The log keeps the NPC text and consequences but omits
  the numbered choice list, which is shown only as buttons in the dialogue card.
- Inventory list with item details and use/equip actions. Keys can be used on an adjacent
  matching lock, poison applies over several combat turns, and antidotes clear poison.
- **Shop** button in the market (`GET /shop`, `POST /shop/buy`, `POST /shop/sell`) opening a
  modal with affordable gear, prices, effects and weapon properties. Buy adds the item to the
  inventory; Sell lists non-equipped items at half value. Equipment stat changes update the
  character panel and combat stats immediately; the Attack stat follows finesse/ranged
  weapon rules.
- Save button that writes a timestamped save.
- Light/dark theme, persisted through `POST /preferences` when a session exists.
- Session resume from `localStorage` via `GET /state` and `GET /log`.
- Accessibility: skip links, labelled landmarks, focus-trapped modals with focus restore
  and an inert background, theme action labels for assistive tech, and text tokens that
  meet WCAG AA contrast in both themes.
- Mobile: the play area (log + command) comes first below 980px, controls have 44px touch
  targets, and the map/load modals fit the viewport without horizontal page scroll.

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
