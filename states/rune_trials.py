"""Repeatable post-campaign Rune Trials arena."""

from core.achievements import record_event
from core.crafting import add_rune_shards
from core.quests import build_ally_party
from core.trials import (
    apply_boon,
    boon_definitions,
    build_trial_wave,
    completion_reward,
    get_boon,
    max_waves,
    wave_definition,
)
from states.base_state import BaseGameState
from states.combat import CombatState
from states.sanctum import SanctumState
from util.helpers import press_enter


class RuneTrialsState(BaseGameState):
    """Wave-based challenge with between-wave boons."""

    def __init__(self, game=None):
        super().__init__(game)
        self.state_name = "rune_trials"
        self.phase = "menu"
        self.wave = 1
        self.boons = []
        self.active_combat = None
        self.last_input = None

    def available_actions(self, game=None):
        if self.phase == "boon":
            return [boon.get("id", "boon") for boon in boon_definitions()] + [
                "leave"
            ]
        if self.wave > max_waves():
            return ["restart", "leave"]
        return ["begin", "leave"]

    def run(self, game):
        self._ensure_map(game)
        if self.phase == "boon":
            self._boon_menu(game)
        else:
            self._main_menu(game)

    def _ensure_map(self, game):
        map_obj = game.map_manager.get_map("sanctum")
        if map_obj is None:
            return
        game.map_manager.set_current_map("sanctum")
        if (
            game.player.current_map != "sanctum"
            or not map_obj.is_valid_position(game.player.x, game.player.y)
        ):
            x, y = map_obj.player_start_position
            game.player.set_position("sanctum", x, y)

    def _main_menu(self, game):
        player = game.player
        limit = max_waves()
        game.io.show_message("\n=== THE RUNE TRIALS ===")
        game.io.show_message(
            "Rune-light circles the silent sanctum. The trial does not end; "
            "it only waits for the next challenger."
        )
        game.io.show_message(
            f"Best depth: wave {int(getattr(player, 'rune_trials_best', 0) or 0)} "
            f"/ {limit} · Completed runs: "
            f"{int(getattr(player, 'rune_trials_runs', 0) or 0)}"
        )

        if self.wave > limit:
            game.io.show_message(
                "\nYou have completed the Rune Trials. The gate is ready "
                "for another run."
            )
            game.io.show_message("1. Begin a new run")
            game.io.show_message("2. Leave the trials")
        else:
            game.io.show_message(f"\nNext wave: {self.wave} / {limit}")
            if self.boons:
                game.io.show_message(
                    f"Boons taken: {', '.join(self.boons)}."
                )
            game.io.show_message(f"1. Begin wave {self.wave}")
            game.io.show_message("2. View boons")
            game.io.show_message("3. Leave the trials")

        choice = str(
            game.io.request_input("\nChoice: ") or ""
        ).strip().casefold()
        self.last_input = choice

        if self.wave > limit:
            if choice in {"1", "restart", "begin", "again"}:
                self.wave = 1
                self.boons = []
                self._start_wave(game)
                return
            if choice in {"2", "leave", "exit", "return"}:
                self._leave(game)
                return
            game.io.show_message("Invalid choice.")
        elif choice in {"1", "begin", "start", "continue", "fight"}:
            self._start_wave(game)
            return
        elif choice in {"2", "boons", "view"}:
            if self.boons:
                game.io.show_message(
                    "Boons taken: " + ", ".join(self.boons) + "."
                )
            else:
                game.io.show_message("You have not taken any boons yet.")
        elif choice in {"3", "leave", "exit", "return"}:
            self._leave(game)
            return
        else:
            game.io.show_message("Invalid choice.")

        press_enter(game)

    def _start_wave(self, game):
        encounter = build_trial_wave(self.wave)
        if encounter is None:
            game.io.show_message("The trial gate does not answer.")
            self.phase = "menu"
            return

        modifier = encounter.get("modifier") or {}
        game.io.show_message(
            f"\nWave {self.wave}: {encounter['title']}"
        )
        game.io.show_message(encounter.get("description", ""))
        if modifier:
            game.io.show_message(
                f"Trial modifier — {modifier.get('name', 'Unknown')}: "
                f"{modifier.get('description', '')}"
            )
        names = ", ".join(enemy.name for enemy in encounter["enemies"])
        game.io.show_message(f"Enemies: {names}")

        combat = CombatState(
            enemies=encounter["enemies"],
            encounter=encounter,
            allies=build_ally_party(game.player),
        )
        self.active_combat = combat
        self.phase = "menu"
        game.push_state(combat)

    def _complete_wave(self, game):
        player = game.player
        limit = max_waves()
        player.rune_trials_best = max(
            int(getattr(player, "rune_trials_best", 0) or 0),
            self.wave,
        )
        wave = wave_definition(self.wave) or {}
        wave_shards = int(wave.get("rune_shards", 0) or 0)
        if wave_shards:
            add_rune_shards(player, wave_shards, game)
        record_event(player, "rune_trials_updated", game=game)

        if self.wave >= limit:
            player.rune_trials_runs = int(
                getattr(player, "rune_trials_runs", 0) or 0
            ) + 1
            reward = completion_reward()
            from core.cycles import reward_multiplier

            multiplier = reward_multiplier(getattr(player, "cycle", 1))
            gold = int(int(reward.get("gold", 0) or 0) * multiplier)
            experience = int(
                int(reward.get("experience", 0) or 0) * multiplier
            )
            shards = int(reward.get("rune_shards", 0) or 0)
            if gold:
                player.add_gold(gold, game)
            if experience:
                player.gain_experience(experience, game)
            if shards:
                add_rune_shards(player, shards, game)
            game.io.show_message(
                "\nThe Rune Trials are complete. The sanctum's light "
                "settles, and the gate waits for another run."
            )
            if gold or experience:
                parts = []
                if gold:
                    parts.append(f"{gold} gold")
                if experience:
                    parts.append(f"{experience} XP")
                game.io.show_message(
                    "Trial completion reward: " + ", ".join(parts) + "."
                )
            self.wave = limit + 1
            self.phase = "menu"
            record_event(player, "rune_trials_updated", game=game)
            return

        self.phase = "boon"
        game.io.show_message(
            "\nThe wave falls. Choose a boon before the next trial."
        )

    def _boon_menu(self, game):
        boons = boon_definitions()
        game.io.show_message("\n=== TRIAL BOONS ===")
        if not boons:
            self.wave += 1
            self.phase = "menu"
            return

        for index, boon in enumerate(boons, 1):
            game.io.show_message(
                f"{index}. {boon.get('name', 'Boon')} — "
                f"{boon.get('description', '')}"
            )
        game.io.show_message(f"{len(boons) + 1}. Leave the trials")

        choice = str(
            game.io.request_input("\nChoice: ") or ""
        ).strip().casefold()
        self.last_input = choice
        if choice in {str(len(boons) + 1), "leave", "exit"}:
            self._leave(game)
            return

        selected = None
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(boons):
                selected = boons[index]
        else:
            selected = get_boon(choice)

        if selected is None:
            game.io.show_message("Invalid boon.")
            press_enter(game)
            return

        apply_boon(game.player, selected, game)
        boon_id = str(selected.get("id", selected.get("name", "boon")))
        if boon_id not in self.boons:
            self.boons.append(boon_id)
        self.wave += 1
        self.phase = "menu"
        press_enter(game)

    def _leave(self, game):
        game.io.show_message(
            "You step back through the trial gate into the silent sanctum."
        )
        game.change_state(SanctumState(game))

    def _end_run(self, game, outcome):
        self.active_combat = None
        self.wave = 1
        self.boons = []
        self.phase = "menu"
        if outcome == "fled":
            game.io.show_message(
                "\nYou flee the trial. The gate dims, and the run is over."
            )
        else:
            game.io.show_message(
                "\nThe trial ends. The run is over, but your best depth remains."
            )

    def resume(self, game):
        if self.active_combat is None:
            return
        outcome = getattr(self.active_combat, "outcome", None)
        self.active_combat = None
        if outcome == "victory":
            self._complete_wave(game)
        else:
            self._end_run(game, outcome)

    def exit(self, game=None):
        self.active_combat = None
        super().exit(game)

    def to_dict(self):
        data = super().to_dict()
        data.update(
            {
                "phase": self.phase,
                "wave": self.wave,
                "boons": list(self.boons),
            }
        )
        return data

    @classmethod
    def from_dict(cls, data, game=None):
        state = cls(game)
        state.phase = data.get("phase", "menu")
        state.wave = max(1, int(data.get("wave", 1) or 1))
        state.boons = [
            str(boon) for boon in data.get("boons", []) or []
        ]
        state.active_combat = None
        return state
