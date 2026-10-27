"""The Runeheart Gate epilogue beneath the Sealed Sanctum."""

from core.quests import build_ally_party, start_quest
from entities.npc import NPC
from states.base_state import BaseGameState
from states.sanctum import SanctumState
from util.helpers import press_enter


class RuneheartGateState(BaseGameState):
    """Two-stage epilogue encounter whose aid depends on the Runeheart choice."""

    def __init__(self, game=None):
        super().__init__(game)
        self.state_name = "runeheart_gate"
        self.phase = "main_menu"
        self.last_input = None

    def available_actions(self, game=None):
        game = game or getattr(self, "game", None)
        if game is None:
            return ["leave"]
        player = game.player
        if self._sovereign_cleared(player):
            return ["leave"]
        if self._wardens_cleared(player):
            return ["sovereign", "leave"]
        return ["wardens", "leave"]

    def run(self, game):
        self._ensure_map(game)
        self._ensure_quest(game)
        self._main_menu(game)

    def _ensure_map(self, game):
        map_obj = game.map_manager.get_map("runeheart_gate")
        if map_obj is None:
            return
        game.map_manager.set_current_map("runeheart_gate")
        if (
            game.player.current_map != "runeheart_gate"
            or not map_obj.is_valid_position(game.player.x, game.player.y)
        ):
            x, y = map_obj.player_start_position
            game.player.set_position("runeheart_gate", x, y)

    def _ensure_quest(self, game):
        player = game.player
        known = {
            quest.get("id")
            for quest in (
                list(getattr(player, "active_quests", []) or [])
                + list(getattr(player, "completed_quests", []) or [])
            )
            if isinstance(quest, dict)
        }
        if "runeheart_gate" not in known:
            start_quest(player, "runeheart_gate", game)

    @staticmethod
    def _claimed(player):
        return set(
            flag
            for flag in (getattr(player, "claimed_rewards", []) or [])
            if isinstance(flag, str)
        )

    @classmethod
    def _branch(cls, player):
        claimed = cls._claimed(player)
        if "runeheart_kept" in claimed:
            return "kept"
        if "runeheart_mirt" in claimed:
            return "mirt"
        if "runeheart_violet" in claimed:
            return "violet"
        return "none"

    @classmethod
    def _wardens_cleared(cls, player):
        return "runeheart_gate_wardens" in cls._claimed(player) or (
            "runeheart_gate"
            in (getattr(player, "cleared_areas", []) or [])
        )

    @classmethod
    def _sovereign_cleared(cls, player):
        return "runeheart_gate" in (
            getattr(player, "cleared_areas", []) or []
        )

    def _branch_intro(self, branch):
        if branch == "kept":
            return (
                "The Runeheart Amulet burns against your chest. The gate "
                "answers it, and the heartbeat below quickens with hunger."
            )
        if branch == "mirt":
            return (
                "Mirt's factor waits at the stair with a lantern and a "
                "knife. 'Mirt thought you might need someone practical.'"
            )
        if branch == "violet":
            return (
                "A Watch medic waits at the stair, satchel open. Violet's "
                "people have not forgotten the Runeheart."
            )
        return (
            "The stair descends into a hall of black stone and white fire. "
            "A heartbeat sounds beneath the floor."
        )

    def _main_menu(self, game):
        player = game.player
        branch = self._branch(player)
        cleared = self._sovereign_cleared(player)

        game.io.show_message("\n=== THE RUNEHEART GATE ===")
        game.io.show_message(self._branch_intro(branch))
        game.io.show_message(f"Gold: {player.gold}")

        if cleared:
            game.io.show_message(
                "\nThe Sovereign is broken and the gate is silent."
            )
            game.io.show_message("1. Return to the Sanctum")
        elif self._wardens_cleared(player):
            game.io.show_message(
                "\nThe Gate Wardens are broken. Beyond them, the Runeheart "
                "Sovereign waits with its echoes."
            )
            game.io.show_message("1. Confront the Runeheart Sovereign")
            game.io.show_message("2. Return to the Sanctum")
        else:
            game.io.show_message(
                "\nTwo Gate Sentinels and a Runeheart Echo hold the descent."
            )
            game.io.show_message("1. Break the Gate Wardens")
            game.io.show_message("2. Return to the Sanctum")

        choice = str(
            game.io.request_input("\nChoice: ") or ""
        ).strip().casefold()
        self.last_input = choice

        if cleared:
            if choice in {"1", "leave", "return", "sanctum", "exit"}:
                self._leave(game)
                return
            game.io.show_message("Invalid choice.")
        elif self._wardens_cleared(player):
            if choice in {"1", "sovereign", "confront", "fight"}:
                if self._confront_sovereign(game, branch):
                    return
            elif choice in {"2", "leave", "return", "sanctum", "exit"}:
                self._leave(game)
                return
            else:
                game.io.show_message("Invalid choice.")
        else:
            if choice in {"1", "wardens", "confront", "fight"}:
                if self._confront_wardens(game):
                    return
            elif choice in {"2", "leave", "return", "sanctum", "exit"}:
                self._leave(game)
                return
            else:
                game.io.show_message("Invalid choice.")

        press_enter(game)

    def _confront_wardens(self, game):
        from core.encounters import build_encounter
        from states.combat import CombatState

        encounter = build_encounter("runeheart_wardens")
        if encounter is None:
            game.io.show_message("The Gate Wardens cannot be found.")
            return False

        game.io.show_message(
            f"\n{encounter['title']}: {encounter['description']}"
        )
        game.push_state(
            CombatState(
                enemies=encounter["enemies"],
                encounter=encounter,
                allies=build_ally_party(game.player),
            )
        )
        return True

    def _confront_sovereign(self, game, branch):
        from core.encounters import build_encounter
        from states.combat import CombatState

        encounter = build_encounter("runeheart_sovereign")
        if encounter is None:
            game.io.show_message("The Runeheart Sovereign cannot be found.")
            return False

        enemies = list(encounter["enemies"])
        allies = build_ally_party(game.player)

        if branch == "kept":
            from entities.enemy import Enemy

            extra = Enemy(
                "Runeheart Echo C", monster_type="runeheart_echo"
            )
            extra.name = "Runeheart Echo C"
            enemies.append(extra)
            encounter["enemies"] = enemies
            game.io.show_message(
                "The Runeheart's hunger splits the dark. A third echo steps "
                "out beside the Sovereign."
            )
        elif branch == "mirt":
            allies.append(NPC("Mirt's Factor"))
            game.io.show_message(
                "Mirt's factor draws a knife and takes position at your "
                "shoulder."
            )
        elif branch == "violet":
            player = game.player
            player.hp = player.hp_max
            conditions = getattr(player, "conditions", None)
            if isinstance(conditions, dict):
                conditions.clear()
            allies.append(NPC("Watch Medic"))
            game.io.show_message(
                "The Watch medic binds your wounds and clears the worst of "
                "the lingering effects before the gate opens."
            )

        game.io.show_message(
            f"\n{encounter['title']}: {encounter['description']}"
        )
        game.push_state(
            CombatState(
                enemies=enemies,
                encounter=encounter,
                allies=allies,
            )
        )
        return True

    def _leave(self, game):
        game.io.show_message(
            "You climb the spiral stair back into the silent Sanctum."
        )
        game.map_manager.set_current_map("sanctum")
        game.player.set_position("sanctum", 2, 7)
        game.change_state(SanctumState(game))

    def resume(self, game):
        if self._sovereign_cleared(game.player):
            game.io.show_message("\nThe Runeheart Gate is silent.")
        else:
            game.io.show_message("\nYou return to the Runeheart Gate.")

    def to_dict(self):
        data = super().to_dict()
        data["phase"] = self.phase
        return data

    @classmethod
    def from_dict(cls, data, game=None):
        state = cls(game)
        state.phase = data.get("phase", "main_menu")
        return state
