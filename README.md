
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
- Dependency-free web client served at `/app` (character creation, log, inventory, saves)
- Natural-language target commands in the tavern, market and map screen: “talk to Durnan”, “attack the goblin”, “use Healing Potion”, “go to the market”, “examine the chair”, “south”
- Class abilities with mana costs in combat: Powerful Blow, Parry, Magic Missile, Mage Shield, Sneak Attack, Evade, Cure Wounds and Blessing. Use them from the combat menu, with `/use_ability`, or by typing “cast Magic Missile” / “use ability Cure Wounds”
- Class-based level progression: HP/mana growth follows the class data, and level-3/5/7 abilities unlock automatically (Fierce Attack, Fireball, Backstab, Restoration, and more)
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
🟡 Implement Dungeon Master AI (Claude narration slice; decisions remain deterministic)  
⬜ D&D rules improvement and adherence to official system  
🟡 Class abilities, mana and level-based unlocks; broader non-combat spell utility remains future work\
⬜ Multiple combatants implementation (more enemies/allies)  
⬜ Online multiplayer implementation  
⬜ AI-generated game scenarios and realistic NPC faces  
⬜ AI-generated game scenes implementation  
⬜ AI voice synthesis integration for DM narration  

## 🧠 Future Vision: Dungeon Master AI

This project will serve as the backend foundation for an AI-driven narrative experience. Planned integrations include:

- LLM-powered Dungeon Master (Claude by default) that reacts to in-game events and generates dynamic descriptions or dialogues — the first slice, narration, is in `ai/`
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
the game simply continues without the extra paragraph.

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

The test suite uses fake narrators, so it never makes network calls.

## 👥 Contribute
I'm seeking collaborators who want to help build:

- Web interface polish, accessibility and mobile UX (HIGH PRIORITY)
- AI narrative engine (Claude or any OpenAI-compatible endpoint)
- Storyline and world-building
- UI/UX feedback or playtesting

Feel free to open issues, forks or reach out directly.
