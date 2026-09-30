import copy
import random
import curses

MOVES = ['sword', 'shield', 'fire', 'dodge', 'heal', 'poison', 'cleanse']
MOVES_COLORS = {0: 2,
                1: 1,
                2: 7,
                3: 1,
                4: 3,
                5: 7,
                6: 3}
CHOOSE_MESSAGE = f'Choose your action: '

ENERGY_COST = {'fire': 3,
               'poison': 1,
               'heal': 2}

DOT_EFFECTS = (('fire', 'fire_dmg'),
               ('poison', 'poison_dmg'))


class InvalidMove(ValueError):
    pass


def normalize_move(move):
    return str(move).lower()


def validate_move(combatant, move):
    if move not in MOVES:
        raise InvalidMove('Invalid action!')
    cost = ENERGY_COST.get(move, 0)
    if combatant.energy - cost < 0:
        raise InvalidMove('Not enough energy!')
    if move == 'shield' and combatant.until_shield:
        raise InvalidMove(
            f'You will be able to use shield again in {combatant.until_shield} turns.')


class Player:
    def __init__(self):
        self.health = 100
        self.energy = 10
        self.enemy = None
        self.move = 'None'
        self.effects = {}
        self.history = []

        self.sword_dmg = 8
        self.poison_dmg = 2
        self.fire_dmg = 5
        self.fire_time = 3
        self.poison_time = 5
        self.dodged_dmg = 2

        self.until_shield = 0

    def take_turn(self, stdscr):
        stdscr.addstr(5, 0, CHOOSE_MESSAGE)
        offset = 0
        for i in range(len(MOVES)):
            move = MOVES[i]
            add = ' | ' if i < len(MOVES) - 1 else ''
            c = 0 if move == 'shield' and self.until_shield else 1
            stdscr.addstr(6, offset, move.swapcase(), curses.color_pair(MOVES_COLORS[c]))
            stdscr.addstr(6, offset + len(move), add, curses.color_pair(1))
            offset += len(move) + 3
        stdscr.refresh()

        move = []
        cursor_x = 0

        while True:
            key = stdscr.getch(8, cursor_x)

            if key in [curses.KEY_ENTER, 10, 13]:
                move_str = normalize_move(''.join(move))
                try:
                    validate_move(self, move_str)
                except InvalidMove as msg:
                    stdscr.addstr(10, 0, " " * 100)
                    stdscr.addstr(10, 0, str(msg), curses.color_pair(2))
                    stdscr.refresh()
                    move.clear()
                    cursor_x = 0
                    stdscr.addstr(8, 0, " " * 100)
                    stdscr.move(8, 0)
                    continue
                stdscr.addstr(10, 0, " " * 100)
                return move_str

            elif key in [curses.KEY_BACKSPACE, 127]:
                if move:
                    move.pop()
                    cursor_x -= 1
                    stdscr.addstr(8, cursor_x, " ")
                    stdscr.move(8, cursor_x)

            elif 32 <= key <= 126:
                move.append(chr(key))
                stdscr.addstr(8, cursor_x, chr(key))
                cursor_x += 1

            stdscr.refresh()

    def snapshot(self):
        state = vars(self).copy()
        state.pop('enemy', None)
        return copy.deepcopy(state)

    def restore(self, snapshot):
        enemy = self.enemy
        self.__dict__.update(copy.deepcopy(snapshot))
        self.enemy = enemy

    def check_effects(self):
        if self.move == 'cleanse':
            self.effects.clear()
            return
        for effect, damage_attr in DOT_EFFECTS:
            if effect in self.effects:
                self.effects[effect] -= 1
                self.health -= getattr(self.enemy, damage_attr)
                if self.effects[effect] == 0:
                    del self.effects[effect]

    def play(self):
        self.until_shield = max(0, self.until_shield - 1)
        if self.move == 'shield':
            self.until_shield = 2
        if self.enemy.move == 'sword':
            if self.move != 'shield':
                if self.move == 'dodge':
                    self.health -= self.enemy.sword_dmg // 2
                else:
                    self.health -= self.enemy.sword_dmg
        if self.move == 'fire':
            self.enemy.effects['fire'] = self.fire_time
            self.energy -= 3
        if self.move == 'poison':
            self.enemy.effects['poison'] = self.poison_time
            self.energy -= 1
        if self.move == 'heal':
            self.health = min(self.health + 10, 100)
            self.energy -= 2


def resolve_turn(player, enemy, player_move, enemy_move):
    player_move = normalize_move(player_move)
    enemy_move = normalize_move(enemy_move)

    validate_move(player, player_move)

    snapshots = (player.snapshot(), enemy.snapshot())
    try:
        player.move = player_move
        enemy.move = enemy_move

        enemy.play()
        player.play()

        player.check_effects()
        enemy.check_effects()

        player.history.append(player_move)
        if len(player.history) > 10:
            player.history = player.history[len(player.history) - 10:]
    except Exception:
        player.restore(snapshots[0])
        enemy.restore(snapshots[1])
        raise
    return player_move, enemy_move


class Enemy(Player):
    def __init__(self):
        super().__init__()
        self.energy = 10000
        self.effects = {}
        self.sword_dmg = 10

    def take_turn(self):
        sw, sh, f, d, h, p, c = [5] * len(MOVES)
        amounts = [self.enemy.history.count(m) for m in MOVES]

        if self.enemy.history.count('sword') == max(amounts):
            sw, sh, f, d, h, p, c = 9, 10, 5, 6, 8, 5, 3
        elif self.enemy.history.count('shield') == max(amounts):
            sw, sh, f, d, h, p, c = 3, 3, 8, 4, 4, 8, 4
        elif self.enemy.history.count('fire') == max(amounts):
            sw, sh, f, d, h, p, c = 8, 5, 7, 4, 8, 5, 10
        elif self.enemy.history.count('dodge') == max(amounts):
            sw, sh, f, d, h, p, c = 8, 4, 8, 3, 7, 8, 4
        elif self.enemy.history.count('heal') == max(amounts):
            sw, sh, f, d, h, p, c = 6, 5, 8, 4, 7, 7, 4
        elif self.enemy.history.count('poison') == max(amounts):
            sw, sh, f, d, h, p, c = 8, 5, 7, 4, 8, 7, 10
        elif self.enemy.history.count('cleanse') == max(amounts):
            sw, sh, f, d, h, p, c = 10, 5, 5, 6, 7, 5, 5

        if self.enemy.energy < 3:
            sw = min(10, sw + 2)

        if self.health < 50:
            h = min(10, c + 2)
        if self.health < 25:
            c = min(10, c + 1)
            h = min(10, c + 4)
            d = min(10, c + 1)
            sh = min(10, c + 2)

        if self.enemy.history.count('sword') > 4:
            sh = min(10, sh + 1)

        if self.enemy.health < 25:
            sw = min(10, sw + 2)
            p = min(10, p + 2)
            f = min(10, c + 2)

        if self.health < 15:
            sh = min(10, sh + 2)
            h = min(10, h + 3)
            c = min(10, c + 2)
            d = max(1, d - 2)
            sw = max(1, sw - 2)
            p = max(1, p - 2)
            f = max(1, f - 2)

        if self.enemy.health < 10:
            sw = 10

        if self.enemy.until_shield:
            sw = min(10, sw + 1)

        if 'fire' in self.enemy.history[-2:] or 'poison' in self.enemy.history[-2:]:
            c = min(10, c + 2)
            h = min(10, c + 1)

        if 'fire' in self.enemy.effects.keys():
            f = max(1, f - 2)
        if 'poison' in self.enemy.effects.keys():
            p = max(1, p - 2)

        if not self.effects.keys():
            c = 0

        if self.enemy.history.count('poison') + self.enemy.history.count('fire') > 4:
            c = min(10, c + 1)

        weights = (sw, sh, f, d, h, p, c)

        self.move = random.choices(MOVES, k=1, weights=weights)[0]
        self.energy = 10000


def format_effects(effects):
    return ' | '.join(
        f'{name.capitalize().ljust(6, " ")} {turns}'
        for name, turns in sorted(effects.items()))


def main(stdscr):
    curses.start_color()

    curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(7, curses.COLOR_MAGENTA, curses.COLOR_BLACK)

    player = Player()
    enemy = Enemy()
    player.enemy = enemy
    enemy.enemy = player

    while True:
        stdscr.clear()
        restart = False
        if player.health <= 0 and enemy.health <= 0:
            stdscr.addstr(0, 0, 'The battle drained both of you.', curses.color_pair(4))
            restart = True
        elif player.health <= 0:
            stdscr.addstr(0, 0, 'You died!', curses.color_pair(2))
            restart = True
        elif enemy.health <= 0:
            stdscr.addstr(0, 0, 'You won!', curses.color_pair(3))
            restart = True

        if restart:
            player = Player()
            enemy = Enemy()
            player.enemy = enemy
            enemy.enemy = player
            stdscr.addstr(10, 0, 'Press any key to restart...')
        else:
            player_fx = format_effects(player.effects)
            enemy_fx = format_effects(enemy.effects)
            stdscr.addstr(0, 0, f'You   | Hp {str(player.health).rjust(3, " ")} '
                                f'| Energy {str(player.energy).rjust(2, " ")} | '
                                f'{player_fx}', curses.color_pair(1))
            stdscr.addstr(1, 0, f'Enemy | Hp {str(enemy.health).rjust(3, " ")} |           '
                                f'| {enemy_fx}', curses.color_pair(4))

            player_move = player.take_turn(stdscr)
            enemy.take_turn()
            enemy_move = enemy.move

            try:
                resolve_turn(player, enemy, player_move, enemy_move)
            except Exception:
                player.move = normalize_move(player_move)
                enemy.move = normalize_move(enemy_move)
                stdscr.addstr(10, 0, 'Action failed; the battle state is unchanged.',
                              curses.color_pair(2))
            else:
                player_msg = f'You played {player.move.swapcase()}!'
                enemy_msg = f'Enemy played {enemy.move.swapcase()}!'

                stdscr.addstr(10, 0, player_msg, curses.color_pair(1))
                stdscr.addstr(10, len(player_msg), ' | ')
                stdscr.addstr(10, len(player_msg) + 3, enemy_msg, curses.color_pair(4))

            stdscr.addstr(11, 0, 'Press any key to continue...')

        stdscr.refresh()
        stdscr.getch()


if __name__ == '__main__':
    curses.wrapper(main)
