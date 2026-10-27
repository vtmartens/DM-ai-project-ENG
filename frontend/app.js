/* Dependency-free web client for the DM AI backend.
 *
 * Served by Flask at /app. If opened from another static server, pass
 * ?api=http://127.0.0.1:5000 or set localStorage["dm_api_base"].
 */

const params = new URLSearchParams(window.location.search);
const API_BASE = (
  params.get("api") ||
  localStorage.getItem("dm_api_base") ||
  (window.location.protocol === "file:" ? "http://127.0.0.1:5000" : window.location.origin)
).replace(/\/+$/, "");

const SESSION_KEY = "dm_session_id";
const THEME_KEY = "dm_theme";

const store = {
  sessionId: localStorage.getItem(SESSION_KEY) || null,
  state: null,
  classes: {},
  achievements: [],
  log: [],
  busy: false,
};

const el = {
  startScreen: document.getElementById("start-screen"),
  gameScreen: document.getElementById("game-screen"),
  startForm: document.getElementById("start-form"),
  startButton: document.getElementById("start-button"),
  startError: document.getElementById("start-error"),
  playerName: document.getElementById("player-name"),
  classSelect: document.getElementById("class-select"),
  classSummary: document.getElementById("class-summary"),
  savesList: document.getElementById("saves-list"),
  refreshSaves: document.getElementById("refresh-saves"),
  connection: document.getElementById("connection"),
  themeToggle: document.getElementById("theme-toggle"),
  charName: document.getElementById("char-name"),
  charClass: document.getElementById("char-class"),
  charLevel: document.getElementById("char-level"),
  hpFill: document.getElementById("hp-fill"),
  hpText: document.getElementById("hp-text"),
  hpBar: document.querySelector(".hp-bar"),
  statGold: document.getElementById("stat-gold"),
  statLocation: document.getElementById("stat-location"),
  statPosition: document.getElementById("stat-position"),
  statsGrid: document.getElementById("stats-grid"),
  conditionsList: document.getElementById("conditions-list"),
  questList: document.getElementById("quest-list"),
  achievementsList: document.getElementById("achievements-list"),
  achievementsCount: document.getElementById("achievements-count"),
  abilitiesList: document.getElementById("abilities-list"),
  skillsList: document.getElementById("skills-list"),
  inventoryList: document.getElementById("inventory-list"),
  equipment: document.getElementById("equipment"),
  refreshInventory: document.getElementById("refresh-inventory"),
  log: document.getElementById("log"),
  commandForm: document.getElementById("command-form"),
  commandInput: document.getElementById("command-input"),
  sendButton: document.getElementById("send-button"),
  commandStatus: document.getElementById("command-status"),
  quickActions: document.getElementById("quick-actions"),
  saveGame: document.getElementById("save-game"),
  loadGame: document.getElementById("load-game"),
  newGame: document.getElementById("new-game"),
  itemPanel: document.getElementById("item-panel"),
  loadModal: document.getElementById("load-modal"),
  closeLoadModal: document.getElementById("close-load-modal"),
  modalSavesList: document.getElementById("modal-saves-list"),
  combatCard: document.getElementById("combat-card"),
  dialogueCard: document.getElementById("dialogue-card"),
  showMap: document.getElementById("show-map"),
  askHint: document.getElementById("ask-hint"),
  showRecap: document.getElementById("show-recap"),
  mapModal: document.getElementById("map-modal"),
  closeMapModal: document.getElementById("close-map-modal"),
  mapModalTitle: document.getElementById("map-modal-title"),
  mapMeta: document.getElementById("map-meta"),
  mapAscii: document.getElementById("map-ascii"),
  mapLegend: document.getElementById("map-legend"),
  toast: document.getElementById("toast"),
};

let toastTimer = null;
let thinkingTimer = null;
let activeModal = null;
let modalTrigger = null;
let modalKeydownHandler = null;

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

/* ------------------------------------------------------------------ API */

async function api(path, { method = "GET", body = null } = {}) {
  const options = { method, headers: {} };
  if (body !== null) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, options);
  } catch (error) {
    setConnection(false);
    throw new Error(
      `Cannot reach the API at ${API_BASE}. Start the server with "python server.py" and open /app.`
    );
  }

  setConnection(true);
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      (data && (data.error || data.message)) || `Request failed (${response.status})`;
    const err = new Error(message);
    err.status = response.status;
    err.data = data;
    throw err;
  }
  return data;
}

function setConnection(online) {
  el.connection.dataset.state = online ? "online" : "offline";
  el.connection.textContent = online ? "online" : "offline";
}

/* -------------------------------------------------------------- theme */

function storedTheme() {
  return localStorage.getItem(THEME_KEY) || "dark";
}

function applyTheme(theme, persist = true) {
  const light = theme === "light";
  document.documentElement.dataset.theme = light ? "light" : "dark";
  if (persist) localStorage.setItem(THEME_KEY, light ? "light" : "dark");
  el.themeToggle.textContent = light ? "Dark" : "Light";
  const label = light ? "Switch to dark theme" : "Switch to light theme";
  el.themeToggle.setAttribute("aria-label", label);
  el.themeToggle.title = label;
}

function toggleTheme() {
  const next = storedTheme() === "light" ? "dark" : "light";
  applyTheme(next, true);
  if (store.sessionId) {
    api("/preferences", {
      method: "POST",
      body: { session_id: store.sessionId, preferences: { theme: next } },
    }).catch(() => {
      /* preference persistence is best-effort */
    });
  }
}

/* ---------------------------------------------------------- start menu */

async function loadClasses() {
  try {
    store.classes = await api("/classes");
  } catch (error) {
    el.startError.textContent = error.message;
    return;
  }

  const names = Object.keys(store.classes).sort();
  el.classSelect.innerHTML = "";
  for (const name of names) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name.charAt(0).toUpperCase() + name.slice(1);
    el.classSelect.appendChild(option);
  }

  const preferred = names.includes("fighter") ? "fighter" : names[0];
  if (preferred) el.classSelect.value = preferred;
  renderClassSummary();
}

function renderClassSummary() {
  const name = el.classSelect.value;
  const data = store.classes[name];
  if (!data) {
    el.classSummary.textContent = "Select a class to see its details.";
    return;
  }

  el.classSummary.innerHTML = "";
  const description = document.createElement("p");
  description.textContent = data.description || "";
  el.classSummary.appendChild(description);

  const stats = document.createElement("p");
  const base = data.base_stats || {};
  const order = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"];
  stats.textContent = order
    .filter((key) => key in base)
    .map((key) => `${key.slice(0, 3).toUpperCase()} ${base[key]}`)
    .join(" · ");
  el.classSummary.appendChild(stats);

  const vitals = document.createElement("p");
  vitals.textContent = `HP ${data.hp_base ?? "?"} · Mana ${data.mana_base ?? 0}`;
  el.classSummary.appendChild(vitals);

  const tags = document.createElement("div");
  tags.className = "tag-list";
  for (const ability of data.special_abilities || []) {
    const tag = document.createElement("span");
    tag.className = "tag ability";
    tag.textContent = ability;
    tags.appendChild(tag);
  }
  el.classSummary.appendChild(tags);
}

async function startGame(event) {
  event.preventDefault();
  if (store.busy) return;

  const name = (el.playerName.value || "Adventurer").trim() || "Adventurer";
  const charClass = el.classSelect.value;
  if (!charClass) {
    el.startError.textContent = "Choose a class first.";
    return;
  }

  setBusy(true, "Opening the tavern…");
  el.startError.textContent = "";
  try {
    const data = await api("/start", {
      method: "POST",
      body: { name, char_class: charClass },
    });
    enterGame(data.session_id, data.state, data.output);
    showToast("New game started.", "success");
  } catch (error) {
    el.startError.textContent = error.message;
  } finally {
    setBusy(false);
  }
}

async function loadSave(fileName) {
  if (store.busy) return;
  setBusy(true, "Loading…");
  try {
    const data = await api("/load", { method: "POST", body: { file_name: fileName } });
    enterGame(data.session_id, data.state, data.output);
    closeLoadModal();
    showToast("Save loaded.", "success");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    setBusy(false);
  }
}

function enterGame(sessionId, state, output) {
  store.sessionId = sessionId;
  store.state = state || null;
  localStorage.setItem(SESSION_KEY, sessionId);

  el.log.innerHTML = "";
  store.log = [];
  if (Array.isArray(output) && output.length) {
    appendOutput(output);
  } else if (state && state.output) {
    appendMessage(state.output, "narrative");
  }
  scrollLogToBottom();

  el.startScreen.classList.add("hidden");
  el.gameScreen.classList.remove("hidden");
  closeItemPanel();
  closeMapModal();

  if (state) renderState(state);
  refreshSidePanels(state);
  el.commandInput.focus({ preventScroll: true });
}

/* ------------------------------------------------------------ session */

async function restoreSession() {
  if (!store.sessionId) return false;
  try {
    const state = await api(`/state?session_id=${encodeURIComponent(store.sessionId)}`);
    if (!state || state.state === "NoneState") throw new Error("No active state");

    store.state = state;
    el.startScreen.classList.add("hidden");
    el.gameScreen.classList.remove("hidden");
    renderState(state);

    try {
      const log = await api(`/log?session_id=${encodeURIComponent(store.sessionId)}&max=200`);
      el.log.innerHTML = "";
      store.log = [];
      for (const message of log.events || []) {
        appendMessage(message.text, message.type);
      }
      if (!store.log.length) appendMessage("Session resumed.", "system");
      renderDialogue(state.dialogue);
      if (state.dialogue?.active) {
        window.requestAnimationFrame(scrollLogToLatestNarration);
      }
    } catch {
      appendMessage("Session resumed.", "system");
    }
    scrollLogToBottom();

    refreshSidePanels(state);
    el.commandInput.focus({ preventScroll: true });
    return true;
  } catch (error) {
    if (error.status === 404) {
      clearSession();
      return false;
    }
    showToast(error.message, "error");
    return false;
  }
}

function clearSession() {
  store.sessionId = null;
  store.state = null;
  localStorage.removeItem(SESSION_KEY);
  el.gameScreen.classList.add("hidden");
  el.startScreen.classList.remove("hidden");
  el.log.innerHTML = "";
  store.log = [];
  el.combatCard.classList.add("hidden");
  el.combatCard.innerHTML = "";
  el.dialogueCard.classList.add("hidden");
  el.dialogueCard.innerHTML = "";
  el.achievementsList.innerHTML = "";
  el.achievementsCount.textContent = "0 / 0";
  store.achievements = [];
  closeMapModal();
  closeLoadModal();
  refreshSaves();
}

function newGame() {
  if (!window.confirm("Start a new game? Unsaved progress will be lost.")) return;
  clearSession();
  el.startError.textContent = "";
  el.playerName.focus();
}

/* -------------------------------------------------------------- state */

function renderState(state) {
  if (!state) return;
  store.state = state;

  el.charName.textContent = state.name || "Adventurer";
  el.charClass.textContent = state.char_class || "";
  el.charLevel.textContent = `Lv ${state.stats?.level ?? 1}`;

  const hp = Number(state.hp ?? 0);
  const maxHp = Number(state.max_hp ?? 0);
  const ratio = maxHp > 0 ? Math.max(0, Math.min(1, hp / maxHp)) : 0;
  el.hpFill.style.width = `${ratio * 100}%`;
  el.hpText.textContent = `${hp} / ${maxHp}`;
  el.hpBar.setAttribute("aria-valuenow", String(Math.round(ratio * 100)));

  el.statGold.textContent = state.stats?.gold ?? 0;
  el.statLocation.textContent = state.position?.map
    ? String(state.position.map).replace(/^\w/, (c) => c.toUpperCase())
    : "—";
  el.statPosition.textContent =
    state.position && state.position.x != null
      ? `(${state.position.x}, ${state.position.y})`
      : "—";

  renderStats(state.stats || {});
  renderConditions(state.conditions || {});

  if (state.preferences?.theme && !localStorage.getItem(THEME_KEY)) {
    applyTheme(state.preferences.theme, true);
  }

  renderCombat(state.combat);
  renderDialogue(state.dialogue);
  if (state.dialogue?.active) {
    window.requestAnimationFrame(scrollLogToLatestNarration);
  }
}

function applyState(state) {
  const before = new Set(store.state?.achievements || []);
  renderState(state);
  notifyNewAchievements(before, state?.achievements);
}

function notifyNewAchievements(before, after) {
  const fresh = (after || []).filter((id) => !before.has(id));
  if (!fresh.length) return;

  const names = new Map(
    (store.achievements || []).map((achievement) => [achievement.id, achievement.name])
  );
  const label = fresh.map((id) => names.get(id)).filter(Boolean).join(", ");
  showToast(
    label ? `Achievement unlocked: ${label}` : "Achievement unlocked!",
    "success"
  );
}

function renderCombat(combat) {
  if (!combat || !combat.in_combat) {
    el.combatCard.classList.add("hidden");
    el.combatCard.innerHTML = "";
    return;
  }

  el.combatCard.classList.remove("hidden");
  el.combatCard.innerHTML = "";

  const head = document.createElement("div");
  head.className = "combat-head";
  const title = document.createElement("h3");
  title.textContent = `Combat — round ${combat.round ?? 1}`;
  const turn = document.createElement("span");
  turn.className = "muted";
  turn.textContent = `Turn: ${combat.turn_of ?? "player"}`;
  head.append(title, turn);
  el.combatCard.appendChild(head);

  const playerStatus = document.createElement("div");
  playerStatus.className = "enemy-status";
  if (combat.effects?.defending) {
    addStatusTag(playerStatus, "Defending · +4 AC", "guard");
  }
  if (combat.effects?.aiming) {
    addStatusTag(playerStatus, "Aiming · advantage", "cooldown");
  }
  if (playerStatus.children.length) el.combatCard.appendChild(playerStatus);

  const livingEnemies = (combat.enemies || []).filter((enemy) => enemy.hp > 0);

  for (const enemy of combat.enemies || []) {
    const row = document.createElement("div");
    row.className = "enemy-row";
    const name = document.createElement("span");
    name.textContent = enemy.name;
    const hp = document.createElement("span");
    hp.className = "muted";
    hp.textContent = `${enemy.hp} / ${enemy.max_hp} HP · AC ${enemy.ac ?? "?"}`;
    row.append(name, hp);

    if (livingEnemies.length > 1) {
      const target = document.createElement("button");
      target.type = "button";
      target.className = "ghost small";
      target.textContent = enemy.name === combat.target ? "Targeted" : "Target";
      target.disabled = enemy.hp <= 0 || enemy.name === combat.target;
      target.addEventListener("click", () => sendCommand(`target ${enemy.name}`));
      row.appendChild(target);
    }

    const bar = document.createElement("div");
    bar.className = "enemy-hp-bar";
    const fill = document.createElement("div");
    fill.className = "enemy-hp-fill";
    const ratio = enemy.max_hp > 0 ? Math.max(0, Math.min(1, enemy.hp / enemy.max_hp)) : 0;
    fill.style.width = `${ratio * 100}%`;
    bar.appendChild(fill);

    el.combatCard.append(row, bar);

    const statuses = document.createElement("div");
    statuses.className = "enemy-status";
    if (Number(enemy.guard || 0) > 0) {
      addStatusTag(statuses, `Guard ${enemy.guard}`, "guard");
    }
    for (const cooldown of enemy.cooldowns || []) {
      if (Number(cooldown.remaining || 0) > 0) {
        addStatusTag(
          statuses,
          `${cooldown.name}: ${cooldown.remaining}`,
          "cooldown"
        );
      }
    }
    if (statuses.children.length) el.combatCard.appendChild(statuses);
  }

  for (const ally of combat.allies || []) {
    const row = document.createElement("div");
    row.className = "enemy-row";
    const name = document.createElement("span");
    name.textContent = `${ally.name} (ally)`;
    const hp = document.createElement("span");
    hp.className = "muted";
    hp.textContent = `${ally.hp} / ${ally.max_hp} HP`;
    row.append(name, hp);
    el.combatCard.appendChild(row);
  }
}

function addStatusTag(container, text, kind) {
  const tag = document.createElement("span");
  tag.className = `status-tag ${kind}`;
  tag.textContent = text;
  container.appendChild(tag);
}

function renderConditions(conditions) {
  el.conditionsList.innerHTML = "";
  const entries =
    conditions && typeof conditions === "object"
      ? Object.entries(conditions)
      : [];

  if (!entries.length) {
    const note = document.createElement("span");
    note.className = "empty-note";
    note.textContent = "None";
    el.conditionsList.appendChild(note);
    return;
  }

  for (const [name, value] of entries) {
    const tag = document.createElement("span");
    const slug = String(name).toLowerCase().replace(/[^a-z0-9_-]+/g, "-");
    tag.className = `tag condition condition-${slug}`;
    tag.textContent = conditionLabel(name, value);
    tag.title = conditionTitle(name, value);
    el.conditionsList.appendChild(tag);
  }
}

function conditionLabel(name, value) {
  const key = String(name).toLowerCase();
  if (key === "poison" && value && typeof value === "object") {
    const damage = Number(value.damage ?? 0);
    const turns = Number(value.turns ?? value.duration ?? 0);
    return `Poisoned · ${damage}/turn · ${turns} turn${turns === 1 ? "" : "s"}`;
  }
  if (key === "guidance" && value && typeof value === "object") {
    return `Guidance +${Number(value.bonus ?? 2)}`;
  }
  if (
    ["burning", "frightened", "weakened"].includes(key) &&
    value &&
    typeof value === "object"
  ) {
    const turns = Number(value.turns ?? 0);
    const label = key.charAt(0).toUpperCase() + key.slice(1);
    return `${label} · ${turns} turn${turns === 1 ? "" : "s"}`;
  }
  if (key === "advantage") return "Advantage";
  if (key === "disadvantage") return "Disadvantage";
  if (value && typeof value === "object") {
    const details = Object.entries(value)
      .map(([stat, amount]) => `${stat} ${amount}`)
      .join(", ");
    return details ? `${name}: ${details}` : String(name);
  }
  return value === true ? String(name) : `${name} ${value}`;
}

function conditionTitle(name, value) {
  if (value && typeof value === "object") {
    return (
      Object.entries(value)
        .map(([stat, amount]) => `${stat}: ${amount}`)
        .join(", ") || String(name)
    );
  }
  return `${name}: ${value}`;
}

function renderDialogue(dialogue) {
  if (!dialogue || !dialogue.active) {
    el.dialogueCard.classList.add("hidden");
    el.dialogueCard.innerHTML = "";
    return;
  }

  el.dialogueCard.classList.remove("hidden");
  el.dialogueCard.innerHTML = "";

  const head = document.createElement("div");
  head.className = "combat-head";
  const title = document.createElement("h3");
  title.textContent = dialogue.npc || "Dialogue";
  const node = document.createElement("span");
  node.className = "muted";
  node.textContent = dialogue.node || "";
  head.append(title, node);

  const text = document.createElement("p");
  text.textContent = dialogue.text || "";

  const options = document.createElement("div");
  options.className = "dialogue-options";
  for (const option of dialogue.options || []) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost small";
    button.textContent = `${option.index}. ${option.text}`;
    button.addEventListener("click", () => sendCommand(String(option.index)));
    options.appendChild(button);
  }

  el.dialogueCard.append(head, text, options);
}

function renderStats(stats) {
  // Show the base ability score with its modifier, matching the class preview.
  const abilities = [
    ["strength_base", "strength", "STR"],
    ["dexterity_base", "dexterity", "DEX"],
    ["constitution_base", "constitution", "CON"],
    ["intelligence_base", "intelligence", "INT"],
    ["wisdom_base", "wisdom", "WIS"],
    ["charisma_base", "charisma", "CHA"],
  ];
  const extras = [
    ["mana", "Mana"],
    ["mana_max", "Mana max"],
    ["ac", "AC"],
    ["attack_bonus", "Attack"],
    ["initiative", "Init"],
    ["experience", "XP"],
  ];

  el.statsGrid.innerHTML = "";

  for (const [baseKey, modifierKey, label] of abilities) {
    if (!(baseKey in stats)) continue;
    const base = stats[baseKey];
    const modifier = stats[modifierKey];
    const valueText =
      modifier === undefined
        ? `${base}`
        : `${base} (${modifier >= 0 ? "+" : ""}${modifier})`;

    const cell = document.createElement("div");
    cell.className = "stat-cell";
    const name = document.createElement("span");
    name.textContent = label;
    const value = document.createElement("strong");
    value.textContent = valueText;
    cell.append(name, value);
    el.statsGrid.appendChild(cell);
  }

  for (const [key, label] of extras) {
    if (!(key in stats)) continue;
    const cell = document.createElement("div");
    cell.className = "stat-cell";
    const name = document.createElement("span");
    name.textContent = label;
    const value = document.createElement("strong");
    value.textContent = stats[key];
    cell.append(name, value);
    el.statsGrid.appendChild(cell);
  }
}

async function refreshSidePanels(state = null) {
  if (!store.sessionId) return;

  try {
    if (!state) {
      state = await api(`/state?session_id=${encodeURIComponent(store.sessionId)}`);
      renderState(state);
    }

    const [abilities, inventory, actions, missions, achievements] = await Promise.all([
      api(`/abilities?session_id=${encodeURIComponent(store.sessionId)}`),
      api(`/inventory?session_id=${encodeURIComponent(store.sessionId)}`),
      api(`/available_actions?session_id=${encodeURIComponent(store.sessionId)}`),
      api(`/missions?session_id=${encodeURIComponent(store.sessionId)}`),
      api(`/achievements?session_id=${encodeURIComponent(store.sessionId)}`),
    ]);

    renderAbilities(abilities);
    renderQuests(missions);
    renderAchievements(achievements);
    renderInventory(inventory);
    renderQuickActions(actions);
  } catch (error) {
    if (error.status === 404) {
      clearSession();
      showToast("Session expired. Start a new game.", "error");
    }
  }
}

function renderAbilities(data) {
  el.abilitiesList.innerHTML = "";
  el.skillsList.innerHTML = "";

  const details =
    Array.isArray(data.ability_details) && data.ability_details.length
      ? data.ability_details
      : (data.abilities || []).map((name) => ({ name }));
  const mana = Number(data.mana || 0);
  const inCombat = Boolean(data.in_combat);

  for (const ability of details) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "tag ability";
    const cost = Number(ability.mana_cost || 0);
    const locked = ability.unlocked === false;
    const requiredLevel = Number(ability.required_level || 1);

    if (ability.usable_in_combat === false) {
      button.classList.add("utility");
    }

    if (locked) {
      button.classList.add("locked");
      button.textContent = `${ability.name} · Lv ${requiredLevel}`;
      button.disabled = true;
      button.title = `${ability.name} unlocks at level ${requiredLevel}${
        ability.description ? `: ${ability.description}` : ""
      }`;
    } else {
      button.textContent = cost ? `${ability.name} · ${cost}` : ability.name;
      const lacksMana = cost > mana;
      const wrongContext = Boolean(ability.combat_only) && !inCombat;
      const utilityInCombat = ability.usable_in_combat === false && inCombat;
      button.disabled = lacksMana || wrongContext || utilityInCombat;
      if (lacksMana) {
        button.title = `${ability.name}: needs ${cost} mana (you have ${mana})`;
      } else if (wrongContext) {
        button.title = `${ability.name}: can only be used in combat`;
      } else if (utilityInCombat) {
        button.title = `${ability.name}: can only be used outside combat`;
      } else {
        button.title = ability.description || ability.name;
      }
    }

    button.addEventListener("click", () => useAbility(ability.name));
    el.abilitiesList.appendChild(button);
  }
  if (!el.abilitiesList.children.length) {
    const note = document.createElement("span");
    note.className = "empty-note";
    note.textContent = "No class abilities.";
    el.abilitiesList.appendChild(note);
  }

  for (const skill of data.skills || []) {
    const tag = document.createElement("span");
    tag.className = "tag skill";
    tag.textContent = skill;
    el.skillsList.appendChild(tag);
  }
}

function renderQuests(data) {
  el.questList.innerHTML = "";
  const active = data.active || [];
  if (!active.length) {
    const note = document.createElement("li");
    note.className = "empty-note";
    note.textContent = "No active quests.";
    el.questList.appendChild(note);
    return;
  }

  for (const quest of active) {
    const item = document.createElement("li");
    const ready = typeof quest === "object" && quest.status === "ready";
    if (ready) item.classList.add("ready");

    const title = document.createElement("strong");
    title.textContent =
      typeof quest === "string" ? quest : quest.title || quest.id || "Quest";
    const objective = document.createElement("span");
    objective.textContent =
      typeof quest === "string"
        ? ""
        : ready
          ? `Ready to turn in — speak to ${quest.turn_in || "the quest giver"}.`
          : quest.objective || quest.description || "";
    item.append(title, objective);
    el.questList.appendChild(item);
  }
}

function renderAchievements(data) {
  const achievements = Array.isArray(data?.achievements) ? data.achievements : [];
  const unlocked = Number(data?.unlocked ?? 0);
  const total = Number(data?.total ?? achievements.length);
  store.achievements = achievements;

  el.achievementsList.innerHTML = "";
  el.achievementsCount.textContent = `${unlocked} / ${total}`;

  if (!achievements.length) {
    const note = document.createElement("li");
    note.className = "empty-note";
    note.textContent = "No achievements available.";
    el.achievementsList.appendChild(note);
    return;
  }

  for (const achievement of achievements) {
    const entry = document.createElement("li");
    entry.className = `achievement ${achievement.unlocked ? "unlocked" : "locked"}`;
    if (achievement.difficulty) entry.dataset.difficulty = achievement.difficulty;

    const head = document.createElement("div");
    head.className = "achievement-head";
    const name = document.createElement("strong");
    name.textContent = achievement.name || achievement.id || "Achievement";
    const score = document.createElement("span");
    score.className = "achievement-score";
    score.textContent = achievement.unlocked
      ? `${achievement.score ?? 0} pts`
      : "Locked";
    head.append(name, score);

    const description = document.createElement("span");
    description.className = "achievement-desc";
    description.textContent = achievement.description || "";

    entry.append(head, description);

    if (achievement.unlocked && achievement.unlock_date) {
      const date = document.createElement("span");
      date.className = "achievement-date";
      date.textContent = achievement.unlock_date;
      entry.appendChild(date);
    }

    el.achievementsList.appendChild(entry);
  }
}

function renderInventory(data) {
  el.inventoryList.innerHTML = "";
  const items = data.inventory || [];
  for (const item of items) {
    const name = typeof item === "string" ? item : item.name;
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = name;
    button.addEventListener("click", () => showItemDetails(name));
    li.appendChild(button);
    el.inventoryList.appendChild(li);
  }
  if (!items.length) {
    const note = document.createElement("p");
    note.className = "empty-note";
    note.textContent = "Your pack is empty.";
    el.inventoryList.appendChild(note);
  }

  const equipment = data.equipment || {};
  el.equipment.innerHTML = "";
  addEquipmentRow("Weapon", equipment.weapon);
  addEquipmentRow("Armor", equipment.armor);
  const accessories = Array.isArray(equipment.accessories)
    ? equipment.accessories.filter(Boolean).join(", ")
    : "";
  addEquipmentRow("Accessories", accessories);
}

function addEquipmentRow(label, value) {
  const row = document.createElement("div");
  const name = document.createElement("strong");
  name.textContent = `${label}: `;
  const detail = document.createElement("span");
  detail.textContent = value || "—";
  row.append(name, detail);
  el.equipment.appendChild(row);
}

function renderQuickActions(data) {
  el.quickActions.innerHTML = "";
  const actions = data.actions || [];
  const targets = data.targets || {};

  for (const action of actions) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost small";
    button.textContent = action;
    button.addEventListener("click", () => sendCommand(action));
    el.quickActions.appendChild(button);
  }

  const hints = [];
  if (targets.items?.length) hints.push(`Items nearby: ${targets.items.join(", ")}`);
  if (targets.npc?.length) hints.push(`NPCs nearby: ${targets.npc.join(", ")}`);
  if (targets.directions?.length) hints.push(`Exits: ${targets.directions.join(", ")}`);
  for (const hint of hints) {
    const span = document.createElement("span");
    span.className = "empty-note";
    span.textContent = hint;
    el.quickActions.appendChild(span);
  }
}

/* --------------------------------------------------------------- log */

function scrollLogToBottom() {
  // The immediate set can run before the new nodes are laid out; the frame
  // callback catches the real scrollHeight.
  el.log.scrollTop = el.log.scrollHeight;
  window.requestAnimationFrame(() => {
    el.log.scrollTop = el.log.scrollHeight;
  });
}

function scrollLogToLatestNarration() {
  const entries = el.log.querySelectorAll(".log-entry.narration");
  const latest = entries[entries.length - 1];
  if (!latest) return;

  const logRect = el.log.getBoundingClientRect();
  const entryRect = latest.getBoundingClientRect();
  el.log.scrollTop = el.log.scrollTop + (entryRect.top - logRect.top) - 8;
}

function appendOutput(messages) {
  const incoming = (messages || []).filter((message) => message && message.text != null);
  if (!incoming.length) return;

  // The web runner re-renders the current menu before processing a command so
  // that the state machine can consume it. Collapse that repeated block instead
  // of showing the same menu twice.
  const keyOf = (message) => `${message.type || "narrative"}\u0000${message.text}`;
  const existing = store.log.map(keyOf);
  const incomingKeys = incoming.map(keyOf);

  let overlap = Math.min(existing.length, incomingKeys.length);
  while (overlap > 0) {
    const tail = existing.slice(-overlap);
    const head = incomingKeys.slice(0, overlap);
    if (tail.every((value, index) => value === head[index])) break;
    overlap -= 1;
  }

  const start = overlap >= 3 ? overlap : 0;
  for (let index = start; index < incoming.length; index += 1) {
    appendMessage(incoming[index].text, incoming[index].type);
  }
  scrollLogToBottom();
}

function appendMessage(text, type = "narrative") {
  if (text == null || text === "") return;

  // The runner can carry the previous prompt into the next batch. One prompt
  // line is enough; the input box is the actual prompt.
  const previous = store.log[store.log.length - 1];
  if (
    type === "prompt" &&
    previous &&
    previous.type === "prompt" &&
    previous.text === text
  ) {
    return;
  }

  const entry = document.createElement("div");
  entry.className = `log-entry ${type || "narrative"}`;

  if (type === "narration") {
    const kind = document.createElement("span");
    kind.className = "log-kind";
    kind.textContent = "Dungeon Master";
    entry.appendChild(kind);
  } else if (type === "system") {
    const kind = document.createElement("span");
    kind.className = "log-kind";
    kind.textContent = "System";
    entry.appendChild(kind);
  } else if (type === "error") {
    const kind = document.createElement("span");
    kind.className = "log-kind";
    kind.textContent = "Error";
    entry.appendChild(kind);
  } else if (type === "hint") {
    const kind = document.createElement("span");
    kind.className = "log-kind";
    kind.textContent = "Hint";
    entry.appendChild(kind);
  } else if (type === "recap") {
    const kind = document.createElement("span");
    kind.className = "log-kind";
    kind.textContent = "Previously";
    entry.appendChild(kind);
  }

  const body = document.createElement("span");
  body.textContent = text;
  entry.appendChild(body);

  el.log.appendChild(entry);
  store.log.push({ text, type });

  while (store.log.length > 400) {
    store.log.shift();
    if (el.log.firstElementChild) el.log.firstElementChild.remove();
  }
}

/* ----------------------------------------------------------- commands */

async function sendCommand(command) {
  const text = String(command ?? "").trim();
  if (!text || !store.sessionId || store.busy) return;

  store.busy = true;
  el.commandInput.value = "";
  setBusy(true, "Resolving…");

  thinkingTimer = window.setTimeout(() => {
    if (store.busy) el.commandStatus.textContent = "The Dungeon Master is thinking…";
  }, 600);

  try {
    const data = await api("/command", {
      method: "POST",
      body: { session_id: store.sessionId, command: text },
    });
    appendOutput(data.output);
    if (data.state) applyState(data.state);
    if (data.end) {
      showToast("The game has ended. Start a new game to continue.", "error");
    }
    refreshSidePanels(data.state);
  } catch (error) {
    appendMessage(error.message, "error");
    scrollLogToBottom();
    if (error.status === 404) {
      clearSession();
      showToast("Session expired. Start a new game.", "error");
    }
  } finally {
    store.busy = false;
    window.clearTimeout(thinkingTimer);
    setBusy(false);
    el.commandInput.focus({ preventScroll: true });
  }
}

async function useAbility(name) {
  if (!store.sessionId || store.busy) return;

  store.busy = true;
  setBusy(true, `Using ${name}…`);
  thinkingTimer = window.setTimeout(() => {
    if (store.busy) el.commandStatus.textContent = "The Dungeon Master is thinking…";
  }, 600);

  try {
    const data = await api("/use_ability", {
      method: "POST",
      body: { session_id: store.sessionId, ability_name: name },
    });
    appendOutput(data.output || []);
    if (data.state) applyState(data.state);
    refreshSidePanels(data.state);
  } catch (error) {
    appendMessage(error.message, "error");
    scrollLogToBottom();
    if (error.status === 404) {
      clearSession();
      showToast("Session expired. Start a new game.", "error");
    }
  } finally {
    store.busy = false;
    window.clearTimeout(thinkingTimer);
    setBusy(false);
    el.commandInput.focus({ preventScroll: true });
  }
}

function setBusy(busy, status = "") {
  el.sendButton.disabled = busy;
  el.commandInput.disabled = busy;
  el.startButton.disabled = busy;
  el.saveGame.disabled = busy;
  el.loadGame.disabled = busy;
  el.newGame.disabled = busy;
  if (el.askHint) el.askHint.disabled = busy;
  if (el.showRecap) el.showRecap.disabled = busy;
  el.commandStatus.textContent = status;
}

/* ------------------------------------------------------------- items */

async function showItemDetails(name) {
  if (!store.sessionId) return;
  try {
    const item = await api(
      `/item_details?session_id=${encodeURIComponent(store.sessionId)}&object_name=${encodeURIComponent(name)}`
    );
    renderItemPanel(item);
  } catch (error) {
    showToast(error.message, "error");
  }
}

function renderItemPanel(item) {
  el.itemPanel.innerHTML = "";
  el.itemPanel.classList.remove("hidden");

  const header = document.createElement("div");
  header.className = "card-header";
  const title = document.createElement("h3");
  title.textContent = item.name || "Item";
  const close = document.createElement("button");
  close.type = "button";
  close.className = "ghost small";
  close.textContent = "Close";
  close.addEventListener("click", closeItemPanel);
  header.append(title, close);
  el.itemPanel.appendChild(header);

  const meta = document.createElement("p");
  meta.className = "item-meta";
  meta.textContent = `${item.type || "item"} · ${item.value ?? 0} gold`;
  el.itemPanel.appendChild(meta);

  if (item.description) {
    const description = document.createElement("p");
    description.className = "item-desc";
    description.textContent = item.description;
    el.itemPanel.appendChild(description);
  }

  if (item.effect && Object.keys(item.effect).length) {
    const effects = document.createElement("p");
    effects.className = "item-effects";
    effects.textContent = `Effects: ${Object.entries(item.effect)
      .map(([key, value]) => `${key} ${value}`)
      .join(", ")}`;
    el.itemPanel.appendChild(effects);
  }

  const actions = document.createElement("div");
  actions.className = "item-actions";
  for (const use of item.uses || []) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = use.action === "drop" ? "ghost small" : "primary small";
    button.textContent = use.description || use.action;
    button.addEventListener("click", () => useItem(item.name, use.action));
    actions.appendChild(button);
  }
  el.itemPanel.appendChild(actions);
}

function closeItemPanel() {
  el.itemPanel.classList.add("hidden");
  el.itemPanel.innerHTML = "";
}

async function useItem(name, action) {
  if (!store.sessionId) return;
  try {
    const path = action === "equip" ? "/equipment" : "/item";
    const data = await api(path, {
      method: "POST",
      body: { session_id: store.sessionId, item: name, action },
    });
    appendOutput(data.output);
    if (data.state) applyState(data.state);
    closeItemPanel();
    refreshSidePanels(data.state);
  } catch (error) {
    showToast(error.message, "error");
  }
}

/* ------------------------------------------------------------- saves */

async function saveGame() {
  if (!store.sessionId) return;
  const name = store.state?.name || "adventurer";
  const safe = name.replace(/[^a-z0-9]+/gi, "_").toLowerCase();
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  const fileName = `save_${safe}_${stamp}.json`;

  try {
    await api("/save", {
      method: "POST",
      body: { session_id: store.sessionId, file_name: fileName },
    });
    showToast(`Saved as ${fileName}`, "success");
    refreshSaves();
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function deleteSave(fileName) {
  try {
    await api("/delete_save", { method: "POST", body: { file_name: fileName } });
    showToast("Save deleted.", "success");
    await refreshSaves();
    await refreshModalSaves();
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function refreshSaves() {
  try {
    const data = await api("/list_saves");
    renderSaves(el.savesList, data.saves || []);
  } catch (error) {
    el.savesList.innerHTML = "";
    const note = document.createElement("p");
    note.className = "empty-note";
    note.textContent = error.message;
    el.savesList.appendChild(note);
  }
}

async function refreshModalSaves() {
  if (el.loadModal.classList.contains("hidden")) return;
  try {
    const data = await api("/list_saves");
    renderSaves(el.modalSavesList, data.saves || []);
  } catch (error) {
    el.modalSavesList.innerHTML = "";
    const note = document.createElement("p");
    note.className = "empty-note";
    note.textContent = error.message;
    el.modalSavesList.appendChild(note);
  }
}

function renderSaves(container, saves) {
  container.innerHTML = "";
  if (!saves.length) {
    const note = document.createElement("p");
    note.className = "empty-note";
    note.textContent = "No saves yet.";
    container.appendChild(note);
    return;
  }

  for (const save of saves) {
    const entry = document.createElement("div");
    entry.className = "save-entry";

    const meta = document.createElement("div");
    meta.className = "save-meta";
    const title = document.createElement("span");
    title.className = "save-title";
    title.textContent = save.player || "Unknown";
    const sub = document.createElement("span");
    sub.className = "save-sub";
    sub.textContent = [
      save.char_class,
      `Lv ${save.level ?? 1}`,
      save.map,
      save.data,
    ]
      .filter(Boolean)
      .join(" · ");
    meta.append(title, sub);

    const actions = document.createElement("div");
    actions.className = "save-actions";
    const load = document.createElement("button");
    load.type = "button";
    load.className = "primary small";
    load.textContent = "Load";
    load.addEventListener("click", () => loadSave(save.file));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "ghost small";
    remove.textContent = "Delete";
    remove.addEventListener("click", () => {
      if (window.confirm(`Delete ${save.file}?`)) deleteSave(save.file);
    });
    actions.append(load, remove);

    entry.append(meta, actions);
    container.appendChild(entry);
  }
}

function openModal(modal) {
  if (!modal || activeModal === modal) return;

  // Only one dialog is open at a time.
  const trigger = document.activeElement;
  if (activeModal && activeModal !== modal) {
    closeModal(activeModal, { restoreFocus: false });
  }

  modalTrigger = trigger;
  activeModal = modal;
  modal.classList.remove("hidden");
  document.body.classList.add("modal-open");
  document.querySelector(".topbar")?.setAttribute("inert", "");
  document.querySelector("main.shell")?.setAttribute("inert", "");
  document.querySelectorAll(".skip-link").forEach((link) => link.setAttribute("inert", ""));

  const focusable = focusableElements(modal);
  const target = focusable[0] || modal;
  if (target === modal && !modal.hasAttribute("tabindex")) {
    modal.setAttribute("tabindex", "-1");
  }
  target.focus({ preventScroll: true });

  modalKeydownHandler = (event) => trapModalFocus(event, modal);
  document.addEventListener("keydown", modalKeydownHandler);
}

function focusableElements(modal) {
  return Array.from(modal.querySelectorAll(FOCUSABLE_SELECTOR)).filter(
    (element) => !element.disabled && element.offsetParent !== null
  );
}

function trapModalFocus(event, modal) {
  if (event.key !== "Tab") return;

  const focusable = focusableElements(modal);
  if (!focusable.length) {
    event.preventDefault();
    return;
  }

  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  const active = document.activeElement;
  const outside = !modal.contains(active);

  if (event.shiftKey && (active === first || outside)) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && (active === last || outside)) {
    event.preventDefault();
    first.focus();
  }
}

function closeModal(modal, { restoreFocus = true } = {}) {
  if (!modal || modal.classList.contains("hidden")) return;

  modal.classList.add("hidden");
  document.body.classList.remove("modal-open");
  document.querySelector(".topbar")?.removeAttribute("inert");
  document.querySelector("main.shell")?.removeAttribute("inert");
  document.querySelectorAll(".skip-link").forEach((link) => link.removeAttribute("inert"));

  if (modalKeydownHandler) {
    document.removeEventListener("keydown", modalKeydownHandler);
    modalKeydownHandler = null;
  }

  const trigger = modalTrigger;
  if (activeModal === modal) activeModal = null;
  modalTrigger = null;

  if (restoreFocus && trigger && trigger.isConnected) {
    trigger.focus({ preventScroll: true });
  }
}

function openLoadModal() {
  openModal(el.loadModal);
  refreshModalSaves();
}

function closeLoadModal() {
  closeModal(el.loadModal);
}

async function askHint() {
  if (!store.sessionId || store.busy) return;

  store.busy = true;
  el.askHint.disabled = true;
  el.commandStatus.textContent = "Asking the Dungeon Master…";

  try {
    const data = await api("/hint", {
      method: "POST",
      body: { session_id: store.sessionId },
    });
    if (data && data.hint) {
      appendMessage(data.hint, "hint");
      scrollLogToBottom();
    }
  } catch (error) {
    appendMessage(error.message, "error");
    scrollLogToBottom();
    if (error.status === 404) {
      clearSession();
      showToast("Session expired. Start a new game.", "error");
    }
  } finally {
    store.busy = false;
    el.askHint.disabled = false;
    el.commandStatus.textContent = "";
  }
}

async function showRecap() {
  if (!store.sessionId || store.busy) return;

  store.busy = true;
  el.showRecap.disabled = true;
  el.commandStatus.textContent = "Recalling the story…";

  try {
    const data = await api("/recap", {
      method: "POST",
      body: { session_id: store.sessionId },
    });
    if (data && data.recap) {
      appendMessage(data.recap, "recap");
      scrollLogToBottom();
    }
  } catch (error) {
    appendMessage(error.message, "error");
    scrollLogToBottom();
    if (error.status === 404) {
      clearSession();
      showToast("Session expired. Start a new game.", "error");
    }
  } finally {
    store.busy = false;
    el.showRecap.disabled = false;
    el.commandStatus.textContent = "";
  }
}

async function showMapView() {
  if (!store.sessionId) return;
  try {
    const data = await api(
      `/map_view?session_id=${encodeURIComponent(store.sessionId)}`
    );
    el.mapModalTitle.textContent = `${String(data.map).replace(/^\w/, (c) => c.toUpperCase())} — Map`;
    el.mapMeta.textContent = `Position (${data.position.x}, ${data.position.y}) · ${data.width} × ${data.height}`;
    el.mapAscii.textContent = data.ascii;
    renderMapLegend(data.legend);
    openModal(el.mapModal);
  } catch (error) {
    showToast(error.message, "error");
  }
}

function closeMapModal() {
  closeModal(el.mapModal);
}

function renderMapLegend(legend) {
  const entries = [
    { token: "P", names: ["you"] },
    { token: "#", names: ["wall"] },
    { token: ".", names: ["floor"] },
    ...(legend || []).filter((entry) => entry.token !== "P"),
  ];

  el.mapLegend.innerHTML = "";
  for (const entry of entries) {
    const item = document.createElement("li");
    const code = document.createElement("code");
    code.textContent = entry.token;
    const names = document.createElement("span");
    const members =
      entry.members && entry.members.length
        ? entry.members
        : (entry.names || []).map((name) => ({ name, type: "" }));
    names.textContent = members
      .map((member) => {
        const name = String(member.name || "");
        const display = name.charAt(0).toUpperCase() + name.slice(1);
        return String(member.type || "").toLowerCase() === "npc"
          ? `${display} (NPC)`
          : display;
      })
      .join(", ");
    item.append(code, names);
    el.mapLegend.appendChild(item);
  }
}

/* ------------------------------------------------------------- toast */

function showToast(message, kind = "") {
  el.toast.textContent = message;
  el.toast.className = `toast ${kind}`.trim();
  el.toast.classList.remove("hidden");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => el.toast.classList.add("hidden"), 3800);
}

/* -------------------------------------------------------------- init */

function bindEvents() {
  el.startForm.addEventListener("submit", startGame);
  el.classSelect.addEventListener("change", renderClassSummary);
  el.refreshSaves.addEventListener("click", refreshSaves);
  el.themeToggle.addEventListener("click", toggleTheme);
  el.commandForm.addEventListener("submit", (event) => {
    event.preventDefault();
    sendCommand(el.commandInput.value);
  });
  el.saveGame.addEventListener("click", saveGame);
  el.loadGame.addEventListener("click", openLoadModal);
  el.newGame.addEventListener("click", newGame);
  el.refreshInventory.addEventListener("click", () => refreshSidePanels(store.state));
  el.showMap.addEventListener("click", showMapView);
  el.askHint.addEventListener("click", askHint);
  el.showRecap.addEventListener("click", showRecap);
  el.closeLoadModal.addEventListener("click", closeLoadModal);
  el.closeMapModal.addEventListener("click", closeMapModal);
  el.loadModal.addEventListener("click", (event) => {
    if (event.target === el.loadModal) closeLoadModal();
  });
  el.mapModal.addEventListener("click", (event) => {
    if (event.target === el.mapModal) closeMapModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (activeModal) {
        event.preventDefault();
        closeModal(activeModal);
        return;
      }
      closeItemPanel();
    }
  });
}

async function init() {
  applyTheme(storedTheme(), false);
  bindEvents();
  await loadClasses();
  refreshSaves();

  if (store.sessionId) {
    const restored = await restoreSession();
    if (!restored) showStart();
  } else {
    showStart();
  }
}

function showStart() {
  el.gameScreen.classList.add("hidden");
  el.startScreen.classList.remove("hidden");
  el.playerName.focus();
}

init();
