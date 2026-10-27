
# Dungeon Master AI – Python RPG Engine (Backend Only)

This repository contains the **backend core** of a modular role-playing game (RPG) engine, designed in Python using a clean object-oriented architecture and a stack-based finite state machine (FSM). The project aims to evolve into an AI-driven, narratively rich RPG system, where a virtual Dungeon Master powered by an LLM (Claude by default) can enhance player immersion.

![Image description](Image.png)

> Originally written in Italian; the codebase, its data files and its in-game text are now English.
> See `GLOSSARY.md` for the Italian→English term mapping and `NOTES.md` for known pre-existing
> issues (including a correction to the requirements note under **Requirements** below).

## 🏗️ Architecture Overview

The project is organized into well-defined modules:

DM-AI-EN/

├── main.py # Entry point (terminal client)

├── server.py # Flask REST API backend

├── core/ # Game loop, I/O interface, web session state

├── entities/ # Player, NPCs, enemies, shared logic

├── items/ # Objects and interactive elements

├── states/ # Game states (map, combat, inventory, etc.)

├── util/ # Dice rolling, helper functions, data loading, config

├── data/ # Game data in JSON format

└── world/ # Map system, tile controller, environment


Each game phase (map exploration, combat, dialogues, inventory management) is handled through a **stacked FSM** (`BaseState`), enabling smooth transitions and layered interactions (e.g., opening a chest pauses exploration and pushes a dialog or loot state).

## 🔮 Features

- Modular structure ready for extension
- Complete core game logic (movement, combat, dialogues, inventory)
- ASCII-based map system using a tile controller
- Entity factory system for dynamic content generation
- Full separation of game logic from user interface (ready for future web/GUI/AI integrations)
- Dependency-free web client served at `/app` (character creation, log, quests, achievements, inventory, saves; focus-managed modals, skip links and a mobile-first layout)
- Natural-language target commands in the tavern, market and map screen: “talk to Durnan”, “attack the goblin”, “use Healing Potion”, “go to the market”, “examine the chair”, “south”
- Class abilities with mana costs in combat: Powerful Blow, Parry, Magic Missile, Mage Shield, Sneak Attack, Evade, Cure Wounds and Blessing. Use them from the combat menu, with `/use_ability`, or by typing “cast Magic Missile” / “use ability Cure Wounds”
- Non-combat utility spells: Knock (open a locked door or chest within two steps without a key), Mage Hand (operate a door, chest or lever at range) and Guidance (+2 to the next ability check). Use them from the abilities panel or with `/use_ability`; they are refused in combat and do not spend mana when there is no valid target
- Class-based level progression: HP/mana growth follows the class data, and level-3/5/7 abilities unlock automatically (Fierce Attack, Fireball, Backstab, Restoration, and more)
- Enemy abilities: goblins use Poison Arrow, orcs and the Iron Sentinel Shield Bash, cultists Dark Bolt, specters Spectral Touch, wolves/trolls Savage Bite, and the Sentinel repairs itself. Abilities have cooldowns, telegraphs in the combat log, poison/self-heal/guard effects, and fall back to basic attacks
- Saving throws and advantage: Poison Arrow, Shield Bash, Dark Bolt, Dirty Trick and Bone Volley call for ability saves; success halves damage and prevents poison. Ability checks and saves support advantage/disadvantage from conditions, with both dice shown in the log
- Attack rolls and armor class: player, enemy and ally weapon attacks roll d20 + attack bonus against AC. Natural 20s are critical hits, natural 1s always miss, and the log shows the roll, bonus, total and target AC. AC combines Dexterity and armor/defense, while armor still reduces damage. The stats panel shows AC and Attack, and enemy cards show their AC; class abilities and save-based monster abilities resolve by their own rules
- Defend and Aim: spend a combat turn to raise your guard (+4 AC until your next turn) or steady your aim (advantage on your next weapon attack). Both are on the combat menu, in the API action list and available as natural-language commands; the combat state exposes both effects and the card shows the active status
- Timed conditions: burning (damage each combat round), frightened (disadvantage on checks and saves) and weakened (-2 weapon damage). Dark Bolt, Shield Bash and the dragon's Flame Breath apply them; each condition saves to end and expires after its duration
- Combat status: the web client shows each enemy's guard and ability cooldowns in the combat card, plus a Conditions panel for poison, Guidance and advantage/disadvantage
- Tavern rest: menu option 14 (or typing `rest` / `sleep` / `recover`) buys a long rest for 10 gold, restoring HP and mana and clearing poison, Guidance, advantage/disadvantage and timed conditions. It refuses when you are already rested or cannot pay
- Defeat and recovery: losing a fight no longer leaves you at 1 HP where you fell. You wake in the tavern with half your HP and mana, lose up to 20 gold, and all conditions are cleared. Quest progress, opened routes and other world state are preserved, so you can rest or try the fight again
- Curated encounters: the tavern fight menu offers Goblin Scouts, an Orc Patrol, a Bone Pack and a Wolf Pack, each with a difficulty label and a gold/experience completion bonus on victory
- Group combat: the tavern's “Fight an enemy” menu offers a pair of goblins; every living enemy acts each round, allies can fight alongside you, and you can choose the current target from the combat menu or combat card
- Story slice: Violet's “Shadows in the Market” quest leads to a new warehouse area and a three-enemy cult fight against Vargas and his hooded cultists. Violet joins as a recruitable ally, and the quest log has its own sidebar panel. Mirt's existing Vargas job is also a tracked quest (“A Debt to Collect”). Defeating Vargas makes both quests ready to turn in; return to Violet and Mirt for the rewards and follow-up hooks
- Specific keys and locks: keyed doors on the map block travel until opened with a matching key, Knock, or (where wired) a lever; direct “go to <map>” travel is checked as reachability from the player's current map, so an open door elsewhere cannot unlock a distant area, and a matching key opens the final door. The warehouse needs the key Violet gives you when you accept her quest, while the market→cellar route is open and the tavern cellar door is an optional locked shortcut. Poison works over several turns; antidotes clear poison; initiative accessories affect who acts first in combat
- Sealed Vault: beneath the warehouse, behind the Vault Door. The Warehouse Key opens the sealed strongbox holding the Vault Key; inside, the Iron Sentinel guards a Relic Chest whose Sentinel Key drops from the guardian and yields Sentinel's Edge and a greater healing potion
- The Sentinel's Sigil: Mirt offers a quest to recover Sentinel's Edge from the vault; picking up the relic marks the objective ready, and turning it in grants gold, experience and the Vault Warden's Signet accessory
- Save/load integrity preserves equipped weapon, armor and accessory bonuses, level-up defense, initiative, conditions and recruited allies across round trips
- Achievements: movement, combat wins (including clean streaks), item collection, map exploration, gold, legendary equipment and quests completed without fighting unlock the eight achievements in `data/achievements/achievements.json`; progress and unlock times survive save/load
- Ask the Dungeon Master for a hint: deterministic hints point at the active quest, a locked door and matching key, low HP, a nearby NPC/object or the current combat target; `POST /hint` and the web client's Hint button optionally have the configured AI narrator rephrase them, with no state changes and an engine fallback
- Direct approach with pathfinding: “go to Durnan” or “walk to barrel” moves next to the target in one command; “go to exit” or “leave” walks to the nearest map exit and steps through it (works from the tavern and the market)
- Fully testable backend (no Pygame dependencies in this repo)
- Centralized data loading system via data_manager.py using JSON format
- Improved monster combat system with monster type selection and difficulty levels
- Advanced map navigation system with destination selection state
- Enhanced interaction with potions and inventory items
- Improved placement of NPCs and interactive objects on maps

## 🚀 Current Roadmap

✅ Centralized data loading system via data_manager.py using JSON format  
✅ Improved monster combat system:  
   - Specific monster type selection  
   - Customizable difficulty levels  
   - Rewards and experience points proportional to difficulty  
✅ Enhanced map navigation:  
   - Dedicated map selection state  
   - Ability to choose destination at game start  
   - Elimination of automatic redirection to tavern  
✅ Improved interaction with objects and potions:  
   - More intuitive user interface for item usage  
   - Optimized potion effects  
   - Advanced inventory management  
✅ Enhanced placement of NPCs and interactive objects on maps:  
   - Precise predefined positions to improve gameplay experience  
   - Alternative positioning system when main positions are occupied  
✅ Add modular I/O interfaces (text, GUI, AI)  
🟡 Web client (dependency-free SPA in `frontend/`; React/Vite optional later)  
🟡 Implement Dungeon Master AI (narration and hint rephrasing slices; decisions remain deterministic)
🟡 D&D rules improvement (saving throws, advantage/disadvantage, attack rolls and AC); cover, flanking and broader conditions remain future work
🟡 Class abilities, mana and level-based unlocks; utility spells (Knock, Mage Hand, Guidance) added, broader non-combat spell utility remains future work\
🟡 Multiple enemies, target selection, allies and curated encounters; broader encounter tuning and balancing remain future work\
⬜ Online multiplayer implementation  
⬜ AI-generated game scenarios and realistic NPC faces  
⬜ AI-generated game scenes implementation  
⬜ AI voice synthesis integration for DM narration  

## 🧠 Future Vision: Dungeon Master AI

This project will serve as the backend foundation for an AI-driven narrative experience. Planned integrations include:

- LLM-powered Dungeon Master (Claude by default) that reacts to in-game events and generates dynamic descriptions or dialogues — narration and optional hint rephrasing are in `ai/`
- Natural language command parsing — deterministic target resolution is implemented for the tavern hub; AI interpretation is still future work
- Decision tree to narrative generation mapping
- Future web UI or terminal interface based on abstracted `IOInterface`

## 🎮 Getting Started

Clone the repository and run the main game loop:

```bash
git clone https://github.com/yourusername/DM-AI-EN.git
cd DM-AI-EN
python main.py
```

The game will launch in a text-based interface, allowing you to explore, interact, fight, and talk to characters.

To run the REST API instead, install its dependencies first:

```bash
pip install -r requirements.txt
python server.py
```

Then open <http://127.0.0.1:5000/app> for the web client. See
[`frontend/README.md`](frontend/README.md) and the REST contract in
[`docs/API.md`](docs/API.md).

## 📋 Requirements
- Python 3.10+
- The terminal game (`main.py`) uses only the Python standard library.
- The REST API (`server.py`) requires Flask and flask-cors (`requirements.txt`).

## 🧪 Tests
The suite covers module imports, the state stack, save/load round trips, item effects, data
integrity and the REST API.

```bash
pip install -r requirements-dev.txt
python -m pytest
```

CI runs the same suite on Python 3.10 and 3.13 (`.github/workflows/tests.yml`), including a
headless-browser smoke test of the web client (Chrome in CI, Edge locally).

## 🧙 AI Dungeon Master (optional)

The engine can append one short, atmospheric Dungeon Master paragraph per turn. The
deterministic engine text is always shown unchanged; the model only adds prose. If the
feature is off, credentials are missing, the request times out, or the model refuses,
the game simply continues without the extra paragraph. The DM also keeps a small bounded
memory of recent engine events (default 8) so narration and hints can refer back to what
just happened.

For a step-by-step **free/local setup** (Ollama, LM Studio, free cloud tiers), see
[`docs/AI_SETUP.md`](docs/AI_SETUP.md).

Install the optional dependency:

```bash
pip install -r requirements-ai.txt
```

Claude is the default provider:

```bash
# bash
export ANTHROPIC_API_KEY="..."          # or: ant auth login
DM_AI_NARRATION=1 python main.py
DM_AI_NARRATION=1 python server.py
```

```powershell
# PowerShell
$env:ANTHROPIC_API_KEY="..."
$env:DM_AI_NARRATION="1"; python main.py
$env:DM_AI_NARRATION="1"; python server.py
```

Any OpenAI-compatible endpoint also works — Ollama, LM Studio, vLLM, OpenRouter, Groq, or
the local gateway on this machine:

```powershell
$env:DM_AI_NARRATION="1"
$env:DM_AI_PROVIDER="openai"          # or "openai-compatible"
$env:DM_AI_BASE_URL="http://127.0.0.1:11434/v1"
$env:DM_AI_MODEL="deepseek-v4.1-flash:cloud"   # a model the endpoint actually serves
$env:DM_AI_API_KEY="not-needed"       # local endpoints often accept any value
python main.py
```

Hosted examples: `DM_AI_BASE_URL=https://openrouter.ai/api/v1` with an OpenRouter key and a
`:free` model, or `DM_AI_BASE_URL=https://api.groq.com/openai/v1` with a Groq key. Free
tiers are rate-limited and carry their own data/terms, so check them first.

Settings:

- `DM_AI_PROVIDER` — `claude` (default) or `openai` / `openai-compatible`
- `DM_AI_MODEL` — `claude-opus-5-5` for Claude; `gpt-4o-mini` for OpenAI-compatible unless set
- `DM_AI_BASE_URL` — OpenAI-compatible endpoint (falls back to `OPENAI_BASE_URL`)
- `DM_AI_API_KEY` — optional; falls back to `OPENAI_API_KEY` for the OpenAI-compatible provider
- `DM_AI_MAX_TOKENS` — default `1024`
- `DM_AI_TIMEOUT` — request timeout in seconds, default `20`
- `DM_AI_MEMORY_TURNS` — recent events kept for AI continuity, default `8`; `0` disables memory

The test suite uses fake narrators, so it never makes network calls.

## 👥 Contribute
I'm seeking collaborators who want to help build:

- Web interface polish, accessibility and mobile UX (HIGH PRIORITY)
- AI narrative engine (Claude or any OpenAI-compatible endpoint)
- Storyline and world-building
- UI/UX feedback or playtesting

Feel free to open issues, forks or reach out directly.
