import copy
import random
import unittest

import main


def make_pair():
    player = main.Player()
    enemy = main.Enemy()
    player.enemy = enemy
    enemy.enemy = player
    return player, enemy


def play_turns(pair_, moves):
    player, enemy = pair_
    for player_move, enemy_move in moves:
        main.resolve_turn(player, enemy, player_move, enemy_move)
    return player, enemy


SINGLE_TURN_CASES = [
    # player_move, enemy_move, player_hp, enemy_hp, player_energy,
    # player_effects, enemy_effects, player_shield_cd
    ('dodge', 'dodge', 100, 100, 10, {}, {}, 0),
    ('fire', 'dodge', 100, 95, 7, {}, {'fire': 2}, 0),
    ('poison', 'dodge', 100, 98, 9, {}, {'poison': 4}, 0),
    ('sword', 'sword', 90, 92, 10, {}, {}, 0),
    ('sword', 'shield', 100, 100, 10, {}, {}, 0),
    ('heal', 'sword', 100, 100, 8, {}, {}, 0),
    ('fire', 'sword', 90, 95, 7, {}, {'fire': 2}, 0),
    ('dodge', 'sword', 95, 100, 10, {}, {}, 0),
    ('shield', 'sword', 100, 100, 10, {}, {}, 2),
    ('cleanse', 'fire', 100, 100, 10, {}, {}, 0),
    ('Fire', 'DODGE', 100, 95, 7, {}, {'fire': 2}, 0),
    ('POISON', 'Sword', 90, 98, 9, {}, {'poison': 4}, 0),
]

MULTI_TURN_CASES = [
    # Bug 1 regression: fire and poison on the same target tick independently.
    ([('fire', 'dodge'), ('poison', 'dodge')],
     100, 88, 6, {'fire': 1, 'poison': 4}),
    ([('dodge', 'fire'), ('dodge', 'poison')],
     88, 100, 10, {}),
    # Full damage budget: fire 3x5 + poison 5x2 = 25.
    ([('fire', 'dodge'), ('Poison', 'dodge'), ('dodge', 'dodge'),
      ('dodge', 'dodge'), ('dodge', 'dodge'), ('dodge', 'dodge')],
     100, 75, 6, {}),
    # Re-applying fire refreshes instead of stacking.
    ([('fire', 'dodge'), ('fire', 'dodge'), ('dodge', 'dodge'),
      ('dodge', 'dodge'), ('dodge', 'dodge')],
     100, 80, 4, {}),
    # Cleanse in the same turn wipes effects before the tick.
    ([('dodge', 'fire'), ('cleanse', 'dodge')],
     95, 100, 10, {}),
    # Poison burns its full course: 5 ticks x 2 = 10.
    ([('poison', 'dodge'), ('dodge', 'dodge'), ('dodge', 'dodge'),
      ('dodge', 'dodge'), ('dodge', 'dodge'), ('dodge', 'dodge')],
     100, 90, 9, {}),
]

CASE_VARIANTS = [
    'fire', 'Fire', 'FIRE', 'Poison', 'pOiSoN', 'Shield', 'SHIELD',
    'Sword', 'DODGE', 'HeAl', 'cleanse', 'CLEANSE',
]

INVALID_CASES = [
    ('fire', 2, 'Not enough energy!'),
    ('poison', 0, 'Not enough energy!'),
    ('heal', 1, 'Not enough energy!'),
    ('nope', 10, 'Invalid action!'),
    ('', 10, 'Invalid action!'),
    ('FIRE', 2, 'Not enough energy!'),
]


class TurnResolutionTests(unittest.TestCase):

    def test_single_turn_table(self):
        for (pm, em, php, ehp, pen, pfx, efx, cd) in SINGLE_TURN_CASES:
            with self.subTest(player_move=pm, enemy_move=em):
                player, enemy = make_pair()
                main.resolve_turn(player, enemy, pm, em)
                self.assertEqual(player.health, php)
                self.assertEqual(enemy.health, ehp)
                self.assertEqual(player.energy, pen)
                self.assertEqual(dict(player.effects), pfx)
                self.assertEqual(dict(enemy.effects), efx)
                self.assertEqual(player.until_shield, cd)

    def test_multi_turn_table(self):
        for moves, php, ehp, pen, enemy_fx in MULTI_TURN_CASES:
            with self.subTest(moves=moves):
                player, enemy = play_turns(make_pair(), moves)
                self.assertEqual(player.health, php)
                self.assertEqual(enemy.health, ehp)
                self.assertEqual(player.energy, pen)
                self.assertEqual(dict(enemy.effects), enemy_fx)

    def test_fire_and_poison_same_turn_both_tick(self):
        # Bug 1: neither dot may swallow the other's tick.
        player, enemy = make_pair()
        main.resolve_turn(player, enemy, 'fire', 'dodge')
        main.resolve_turn(player, enemy, 'poison', 'dodge')
        self.assertEqual(enemy.health, 88)
        self.assertEqual(enemy.effects, {'fire': 1, 'poison': 4})
        main.resolve_turn(player, enemy, 'dodge', 'dodge')
        self.assertEqual(enemy.health, 81)
        self.assertEqual(enemy.effects, {'poison': 3})

    def test_uppercase_fire_poison_regression(self):
        player, enemy = make_pair()
        main.resolve_turn(player, enemy, 'Fire', 'dodge')
        self.assertEqual(enemy.health, 95)
        self.assertEqual(enemy.effects, {'fire': 2})
        main.resolve_turn(player, enemy, 'POISON', 'dodge')
        self.assertEqual(enemy.health, 88)
        self.assertEqual(enemy.effects, {'fire': 1, 'poison': 4})

    def test_shield_cooldown_advances_for_any_case_input(self):
        # Bug 2: mixed/uppercase "shield" must still engage and drive cooldown.
        table = [
            ('Shield', 2, 100),
            ('sword', 1, 90),
            ('sword', 0, 80),
            ('SHIELD', 2, 80),
        ]
        player, enemy = make_pair()
        for idx, (move, cd, hp) in enumerate(table):
            with self.subTest(turn=idx, move=move):
                main.resolve_turn(player, enemy, move, 'sword')
                self.assertEqual(player.until_shield, cd)
                self.assertEqual(player.health, hp)

    def test_shield_rejected_while_cooling_down(self):
        player, enemy = make_pair()
        main.resolve_turn(player, enemy, 'shield', 'dodge')
        for bad_move in ('shield', 'Shield', 'SHIELD'):
            with self.subTest(move=bad_move):
                with self.assertRaises(main.InvalidMove):
                    main.resolve_turn(player, enemy, bad_move, 'dodge')
        self.assertEqual(player.until_shield, 2)

    def test_normalize_move_table(self):
        for variant in CASE_VARIANTS:
            with self.subTest(variant=variant):
                self.assertEqual(main.normalize_move(variant), variant.lower())
                self.assertIn(main.normalize_move(variant), main.MOVES)

    def test_invalid_moves_table(self):
        for move, energy, message in INVALID_CASES:
            with self.subTest(move=move):
                player, enemy = make_pair()
                player.energy = energy
                with self.assertRaises(main.InvalidMove) as ctx:
                    main.resolve_turn(player, enemy, move, 'dodge')
                self.assertEqual(str(ctx.exception), message)

    def test_energy_cost_table(self):
        expected = {'fire': 3, 'poison': 1, 'heal': 2,
                    'sword': 0, 'shield': 0, 'dodge': 0, 'cleanse': 0}
        for move in main.MOVES:
            with self.subTest(move=move):
                self.assertEqual(main.ENERGY_COST.get(move, 0), expected[move])

    def test_dot_table_definition(self):
        self.assertEqual(
            list(main.DOT_EFFECTS),
            [('fire', 'fire_dmg'), ('poison', 'poison_dmg')])


class SnapshotRollbackTests(unittest.TestCase):

    def _state(self, combatant):
        return {
            'health': combatant.health,
            'energy': combatant.energy,
            'move': combatant.move,
            'effects': copy.deepcopy(combatant.effects),
            'history': copy.deepcopy(combatant.history),
            'until_shield': combatant.until_shield,
        }

    def test_failure_full_rollback_table(self):
        failing_moves = [
            ('fire', 2), ('FIRE', 2), ('heal', 1), ('HEAL', 1),
            ('poison', 0), ('nope', 10), ('', 10),
        ]
        for failing_move, energy in failing_moves:
            with self.subTest(move=failing_move):
                player, enemy = play_turns(make_pair(), [
                    ('fire', 'dodge'), ('poison', 'dodge')])
                player.energy = energy
                before_p, before_e = self._state(player), self._state(enemy)
                with self.assertRaises(main.InvalidMove):
                    main.resolve_turn(player, enemy, failing_move, 'sword')
                self.assertEqual(self._state(player), before_p)
                self.assertEqual(self._state(enemy), before_e)

    def test_snapshot_deep_copies_effects_and_history(self):
        player, enemy = make_pair()
        main.resolve_turn(player, enemy, 'dodge', 'fire')
        main.resolve_turn(player, enemy, 'dodge', 'poison')
        snapshot = player.snapshot()
        snapshot['effects']['fire'] = 99
        snapshot['history'].append('tampered')
        self.assertEqual(player.effects.get('fire'), 1)
        self.assertNotIn('tampered', player.history)

    def test_restore_deep_copies_snapshot(self):
        player, enemy = make_pair()
        main.resolve_turn(player, enemy, 'fire', 'dodge')
        snapshot = player.snapshot()
        player.restore(snapshot)
        player.effects['poison'] = 7
        player.history.append('x')
        self.assertEqual(snapshot['effects'], {})
        self.assertEqual(snapshot['history'], ['fire'])

    def test_failure_does_not_pollute_next_turn(self):
        player, enemy = make_pair()
        for turn, bad in enumerate(('fire', 'Fire', 'FIRE', 'nope', '')):
            player.energy = 2
            with self.subTest(turn=turn, bad=bad):
                with self.assertRaises(main.InvalidMove):
                    main.resolve_turn(player, enemy, bad, 'sword')
        # A valid turn afterwards runs exactly as if nothing failed.
        main.resolve_turn(player, enemy, 'poison', 'dodge')
        self.assertEqual(player.health, 100)
        self.assertEqual(enemy.health, 98)
        self.assertEqual(enemy.effects, {'poison': 4})
        self.assertEqual(player.history, ['poison'])

    def test_unexpected_error_rolls_back_both_sides(self):
        player, enemy = make_pair()
        main.resolve_turn(player, enemy, 'fire', 'dodge')
        main.resolve_turn(player, enemy, 'poison', 'dodge')
        before_p, before_e = self._state(player), self._state(enemy)

        def boom(self):
            raise RuntimeError('simulated engine fault')

        original = main.Player.check_effects
        main.Player.check_effects = boom
        try:
            with self.assertRaises(RuntimeError):
                main.resolve_turn(player, enemy, 'heal', 'sword')
        finally:
            main.Player.check_effects = original
        self.assertEqual(self._state(player), before_p)
        self.assertEqual(self._state(enemy), before_e)

    def test_rollback_keeps_combatant_links(self):
        player, enemy = make_pair()
        with self.assertRaises(main.InvalidMove):
            main.resolve_turn(player, enemy, 'nope', 'dodge')
        self.assertIs(player.enemy, enemy)
        self.assertIs(enemy.enemy, player)


class DeterminismTests(unittest.TestCase):

    def test_deterministic_under_dict_iteration_reordering(self):
        # Same state, reached with different dict insertion orders, must
        # resolve identically: dict ordering must never drive the result.
        script = [('dodge', 'fire'), ('dodge', 'poison'),
                  ('dodge', 'dodge'), ('dodge', 'dodge')]
        player_a, enemy_a = play_turns(make_pair(), script)
        player_b, enemy_b = play_turns(make_pair(), script)
        # Rebuild effects with reversed insertion order, identical contents.
        for combatant in (player_b, enemy_b):
            reordered = {k: combatant.effects[k]
                         for k in reversed(list(combatant.effects))}
            combatant.effects.clear()
            combatant.effects.update(reordered)
        main.resolve_turn(player_a, enemy_a, 'dodge', 'dodge')
        main.resolve_turn(player_b, enemy_b, 'dodge', 'dodge')
        self.assertEqual((player_a.health, dict(player_a.effects)),
                         (player_b.health, dict(player_b.effects)))
        self.assertEqual((enemy_a.health, dict(enemy_a.effects)),
                         (enemy_b.health, dict(enemy_b.effects)))
        self.assertEqual(player_a.health, 77)

    def test_repeated_runs_are_identical(self):
        script = [('fire', 'dodge'), ('Poison', 'dodge'), ('dodge', 'sword'),
                  ('heal', 'dodge'), ('dodge', 'dodge')]
        reference = None
        for seed in range(20):
            random.seed(seed)
            player, enemy = play_turns(make_pair(), script)
            state = (player.health, enemy.health, player.energy,
                     tuple(sorted(player.effects.items())),
                     tuple(sorted(enemy.effects.items())),
                     tuple(player.history), player.until_shield)
            if reference is None:
                reference = state
            self.assertEqual(state, reference)

    def test_history_records_normalized_lowercase(self):
        script = [('Fire', 'dodge'), ('POISON', 'dodge'), ('Sword', 'sword')]
        player, _ = play_turns(make_pair(), script)
        self.assertEqual(player.history, ['fire', 'poison', 'sword'])

    def test_format_effects_sorted_and_stable(self):
        combatant, _ = make_pair()
        combatant.effects = {'poison': 1, 'fire': 2}
        first = main.format_effects(combatant.effects)
        combatant.effects = {'fire': 2, 'poison': 1}
        second = main.format_effects(combatant.effects)
        self.assertEqual(first, second)
        self.assertLess(first.index('Fire'), first.index('Poison'))

    def test_enemy_weights_are_deterministic_table(self):
        # AI decision table only needs to be deterministic given the same state.
        player, enemy = make_pair()
        script = [('sword', 'dodge')] * 5
        play_turns((player, enemy), script)
        random.seed(1234)
        enemy.take_turn()
        first = enemy.move
        player2, enemy2 = make_pair()
        play_turns((player2, enemy2), script)
        random.seed(1234)
        enemy2.take_turn()
        self.assertEqual(first, enemy2.move)


if __name__ == '__main__':
    unittest.main(verbosity=2)
