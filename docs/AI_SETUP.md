# AI Dungeon Master setup

The AI Dungeon Master is optional. It appends one short atmospheric paragraph to a turn,
can rephrase the engine's hints and session recaps, add colour to location descriptions and
voice the current NPC line; the deterministic engine text is always shown unchanged. It
also keeps a small bounded memory of recent engine events so narration, hints, scenes,
dialogue voice and recaps can refer back to what just happened. If the model is unavailable,
slow, misconfigured, or refuses, the game continues without the paragraph and these extras
fall back to the engine wording.

This guide focuses on setups that do **not** require a paid API: local inference (Ollama,
LM Studio) and free cloud tiers. For the default Claude provider, see the README.

> Installing the Python SDKs costs nothing. Only actual API calls to a paid provider cost
> money. With `DM_AI_PROVIDER=openai` pointing at a local server, no Anthropic calls are made.

## Prerequisites

- Python 3.10+
- The game's runtime dependencies (`requirements.txt` for the Flask API; the terminal game
  uses only the standard library)
- The optional AI dependencies:

```bash
pip install -r requirements-ai.txt
```

If you only use an OpenAI-compatible local server, `pip install openai` is enough.

## Option 1: Ollama (recommended free setup)

Ollama runs models locally and exposes an OpenAI-compatible API on port `11434`.

### 1. Install Ollama

Download it from <https://ollama.com> for Windows, macOS, or Linux.

### 2. Pull a general-purpose model

Use an instruct/chat model, not a code-specialized one:

```bash
ollama pull llama3.1:8b      # good balance of prose quality and speed
# weaker hardware:
ollama pull llama3.2:3b
# other options: qwen2.5:7b, mistral:7b, gemma2:9b
```

Model names and tags change over time; `ollama list` shows what you have, and the Ollama
library lists what is available.

### 3. Configure and run

PowerShell:

```powershell
$env:DM_AI_NARRATION = "1"
$env:DM_AI_PROVIDER   = "openai"
$env:DM_AI_BASE_URL   = "http://localhost:11434/v1"
$env:DM_AI_MODEL      = "llama3.1:8b"
$env:DM_AI_API_KEY    = "not-needed"     # Ollama ignores it; the SDK requires a value
$env:DM_AI_TIMEOUT    = "120"            # generous for CPU-only machines
python main.py
```

bash / zsh:

```bash
export DM_AI_NARRATION=1
export DM_AI_PROVIDER=openai
export DM_AI_BASE_URL=http://localhost:11434/v1
export DM_AI_MODEL=llama3.1:8b
export DM_AI_API_KEY=not-needed
export DM_AI_TIMEOUT=120
python main.py
```

For the REST API, use the same variables and run `python server.py`.

### Verify the endpoint

```bash
curl http://localhost:11434/v1/models
```

If that lists your model, the adapter can reach it.

### Hardware guide

| Model size | RAM / VRAM | Speed | Notes |
|---|---:|---|---|
| 3B (`llama3.2:3b`, `phi3.5`) | ~4–8 GB | fast | usable; simpler prose |
| 7–8B (`llama3.1:8b`, `qwen2.5:7b`, `mistral:7b`) | ~8–16 GB | good | best free balance |
| 14B+ | 16–24 GB+ | slower | better prose; a GPU helps |

Narration makes **one synchronous call per turn**, so latency matters more than raw model
size. On CPU-only hardware, prefer a 3B/7B model and raise `DM_AI_TIMEOUT`.

## Option 2: LM Studio

LM Studio provides a desktop UI and a local OpenAI-compatible server.

1. Install LM Studio and download a model in its UI.
2. Start the local server (default port `1234`).
3. Configure:

```powershell
$env:DM_AI_NARRATION = "1"
$env:DM_AI_PROVIDER   = "openai"
$env:DM_AI_BASE_URL   = "http://localhost:1234/v1"
$env:DM_AI_MODEL      = "<model id shown by LM Studio>"
$env:DM_AI_API_KEY    = "not-needed"
python main.py
```

## Option 3: Free cloud tiers

These require an account and an API key, and are free only within their limits. Check each
provider's current models, rate limits, and terms — some free tiers log or train on prompts.

- **OpenRouter** — choose a model marked `:free`; base URL `https://openrouter.ai/api/v1`.
- **Groq** — fast free tier; base URL `https://api.groq.com/openai/v1`.
- **Google AI Studio (Gemini)** — free tier with an OpenAI-compatible endpoint; see Google's
  docs for the current base URL and model IDs.
- **Mistral / Hugging Face Inference API** — free tiers vary by account and model.

Example shape:

```powershell
$env:DM_AI_NARRATION = "1"
$env:DM_AI_PROVIDER   = "openai"
$env:DM_AI_BASE_URL   = "https://openrouter.ai/api/v1"
$env:DM_AI_API_KEY    = "<your own key>"
$env:DM_AI_MODEL      = "<a model marked :free>"
python main.py
```

Never ship a shared free key with a distributed copy of the game. Each player should supply
their own key, or use a local model.

## Option 4: Claude (paid)

Claude is the default provider and needs Anthropic credentials:

```bash
pip install -r requirements-ai.txt
export ANTHROPIC_API_KEY="..."      # or: ant auth login
export DM_AI_NARRATION=1
python main.py
```

If `ANTHROPIC_BASE_URL` is set in your environment, the SDK will send requests there instead
of to Anthropic. Unset it when using a real Anthropic key.

## Hints

The web client's **Hint** button calls `POST /hint`. The engine always produces a
deterministic hint (quest objective, locked door, low HP, nearby NPC/object, combat target,
or a prone/staggered combat warning). When a narrator is configured, it is asked to rewrite
that hint in one or two sentences. The model cannot add facts or change state; on failure or
refusal the engine hint is returned with `source: "engine"`.

AI hints use the same configuration as narration: set `DM_AI_NARRATION=1` (and the provider
variables below). Without it, the Hint button still works with engine wording.

## Scene descriptions

The web client's **Scene** button calls `POST /describe`. The engine builds a deterministic
description from `data/scenes/locations.json`, the nearby NPCs/objects, cleared-area state
and stealth. When a narrator is configured, it is asked to add atmosphere around those same
facts in two to four sentences. The model cannot add locations, items, NPCs or outcomes, and
it never changes state. On failure, refusal or disabled narration, the engine description is
returned with `source: "engine"`. Scenes use the same configuration as hints and narration.

## Dialogue voice

The dialogue card's **Voice** button calls `POST /dialogue/voice`. The engine supplies the
current NPC line, name, profession and node; when a narrator is configured it adds delivery,
posture and tone in a short in-character paragraph. The line and every option remain
authoritative, and the model may not add choices, items, secrets or outcomes. On failure,
refusal or disabled narration, the engine line is returned with `source: "engine"` and the
card is unchanged. AI voice prose is logged as `dialogue_voice`.

## Recaps

The web client's **Recap** button calls `POST /recap`. The engine builds a deterministic
summary of the player, location, resources, quests, conditions, faction standing, Runeheart
choice, Rune Trials progress, capstone status, defeats and recent events. When a narrator is
configured, it is asked to rewrite that summary in two to four sentences; the model cannot
add facts or change state. On failure, refusal or disabled narration, the engine recap is
returned with `source: "engine"`. Recaps use the same configuration as hints and narration.

## Narrator context

Narration, hints, scene descriptions, dialogue voice and recaps share one compact
serializable context:

- player name, class, level, HP, position and difficulty preset
- active quests and completed-quest count
- conditions
- faction standing and the current merchant discount, when nonzero
- campaign flags such as the Sanctum clear, Runeheart choice, Cycle Omen and quest completion
- Rune Trials best depth, completed runs and Rune Shard count
- recruited allies, stances and loyalty
- active combat round, target, enemies, allies, Cover and Flanking
- nearby item/NPC names and bounded recent-event memory

The context contains no inventory dump, full stat block or hidden map contents. The engine
remains authoritative; model prose never changes state.

## Memory

The narrator receives a bounded list of recent engine events (`context.recent`) for
continuity. It contains narrative text and non-numeric player actions, skips menu/state noise,
and defaults to 8 entries. Set `DM_AI_MEMORY_TURNS=0` to disable it; the value is clamped to
0–20. Memory is kept per session and survives web-session pickling; terminal runs keep it in
process memory only.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DM_AI_NARRATION` | off | Must be `1`, `true`, `yes`, or `on` to enable narration and AI-phrased hints/scenes/dialogue/recaps |
| `DM_AI_PROVIDER` | `claude` | `claude`, or `openai` / `openai-compatible` |
| `DM_AI_MODEL` | `claude-opus-5-5` (Claude), `gpt-4o-mini` (OpenAI-compatible) | Model name |
| `DM_AI_BASE_URL` | — | OpenAI-compatible base URL; falls back to `OPENAI_BASE_URL` |
| `DM_AI_API_KEY` | — | Optional; falls back to `OPENAI_API_KEY` |
| `DM_AI_MAX_TOKENS` | `1024` | Output cap per narration |
| `DM_AI_TIMEOUT` | `20` | Request timeout in seconds |
| `DM_AI_MEMORY_TURNS` | `8` | Recent events kept for AI continuity; `0` disables memory (max 20) |

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `connection refused` | The local server is not running (start Ollama / LM Studio) or the port is wrong |
| 404 “model not found” | The `DM_AI_MODEL` value does not match a pulled/downloaded model. Check `ollama list` or LM Studio's model id |
| Narration never appears | Check the game logs for `AI narrator`. A `finish_reason=length` means raise `DM_AI_MAX_TOKENS`; an authentication/permission error disables narration for the process |
| Very slow turns | Use a smaller model, enable GPU offload, or raise `DM_AI_TIMEOUT`. The game waits for the narration before showing the prompt |
| Empty narration from a reasoning model | Some models spend the token budget on hidden reasoning; use a non-reasoning instruct model or raise `DM_AI_MAX_TOKENS` |
| Hints show engine wording | AI hints need `DM_AI_NARRATION=1`; a failure or refusal also falls back to the engine hint |
| Scenes show engine wording | AI scene colour needs `DM_AI_NARRATION=1`; a failure or refusal also falls back to the engine description |
| The DM forgets recent events | Memory defaults to 8 entries; raise `DM_AI_MEMORY_TURNS` (max 20) or check that `DM_AI_MEMORY_TURNS` is not `0` |
| Engine menus or numbers changed | They cannot be changed by the narrator; it only appends text. If you see this, report it as a bug |

## Tests

The project's test suite uses fake narrators and makes no network calls:

```bash
pip install -r requirements-dev.txt
python -m pytest
```
