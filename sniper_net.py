#!/usr/bin/env python3
"""
SNIPER//NET  -  2D platformer sniper game with an in-game hacker console

Install:  pip install pygame
Run:      python sniper_net.py

CONTROLS
  A / D or arrows ... move            W / Space / Up ... jump
  Mouse ............. aim             Left click ....... fire (bolt-action)
  Hold right click .. scope in        Mouse wheel ...... change zoom (while scoped)
  Hold Shift ........ steady aim (scoped)    R ......... reload
  ` (backtick) or F1  open / close the hacker console
  Esc ............... quit            Enter ............ restart after dying
"""
import math
import random
import sys

import pygame

W, H = 1280, 720
WORLD_W, WORLD_H = 3600, 900
FPS = 60

GREEN = (80, 255, 120)
DGREEN = (30, 120, 60)
WHITE = (235, 235, 235)
RED = (255, 70, 70)
YELLOW = (255, 220, 90)
CYAN = (90, 220, 255)
GREY = (120, 130, 140)


def clip(rect, a, b):
    """Rect.clipline with integer coordinates (safe across pygame versions)."""
    return rect.clipline(int(a[0]), int(a[1]), int(b[0]), int(b[1]))


# --------------------------------------------------------------------------- #
#  Entities
# --------------------------------------------------------------------------- #
class Player:
    def __init__(self, x, y):
        self.w, self.h = 26, 46
        self.x, self.y = float(x), float(y)
        self.rect = pygame.Rect(int(x), int(y), self.w, self.h)
        self.vx = self.vy = 0.0
        self.on_ground = False
        self.coyote = 0.0
        self.jump_buf = 0.0
        self.hp = self.max_hp = 100
        self.mag_size = 5
        self.mag = 5
        self.reserve = 30
        self.cooldown = 0.0
        self.reload_t = 0.0

    @property
    def cx(self):
        return self.rect.centerx

    def teleport(self, x, y):
        self.x, self.y = float(x), float(y)
        self.rect.topleft = (int(x), int(y))
        self.vx = self.vy = 0.0

    def update(self, dt, game, keys, scoped):
        cfg = game.cfg
        move = int(bool(keys[pygame.K_d] or keys[pygame.K_RIGHT])) - \
               int(bool(keys[pygame.K_a] or keys[pygame.K_LEFT]))
        speed = cfg["speed"] * (0.35 if scoped else 1.0)
        accel = 14 if self.on_ground or cfg["fly"] else 7
        self.vx += (move * speed - self.vx) * min(1.0, accel * dt)

        if cfg["fly"]:
            vert = int(bool(keys[pygame.K_s] or keys[pygame.K_DOWN])) - \
                   int(bool(keys[pygame.K_w] or keys[pygame.K_UP] or keys[pygame.K_SPACE]))
            self.vy += (vert * speed - self.vy) * min(1.0, 10 * dt)
        else:
            self.coyote = 0.1 if self.on_ground else self.coyote - dt
            self.jump_buf -= dt
            if self.jump_buf > 0 and self.coyote > 0:
                self.vy = -cfg["jump"]
                self.jump_buf = 0
                self.coyote = 0
            self.vy = min(self.vy + cfg["gravity"] * dt, 1400)

        solid = [] if cfg["noclip"] else game.platforms

        # horizontal
        self.x += self.vx * dt
        self.x = max(0, min(WORLD_W - self.w, self.x))
        self.rect.x = round(self.x)
        for p in solid:
            if self.rect.colliderect(p):
                if self.vx > 0:
                    self.rect.right = p.left
                elif self.vx < 0:
                    self.rect.left = p.right
                self.x = self.rect.x
                self.vx = 0

        # vertical
        self.y += self.vy * dt
        self.rect.y = round(self.y)
        self.on_ground = False
        for p in solid:
            if self.rect.colliderect(p):
                if self.vy > 0:
                    self.rect.bottom = p.top
                    self.on_ground = True
                elif self.vy < 0:
                    self.rect.top = p.bottom
                self.y = self.rect.y
                self.vy = 0

        if self.y > WORLD_H + 300:  # fell out of the world
            self.teleport(200, 600)

        self.cooldown = max(0.0, self.cooldown - dt)
        if self.reload_t > 0:
            self.reload_t -= dt
            if self.reload_t <= 0:
                need = self.mag_size - self.mag
                take = min(need, self.reserve)
                self.mag += take
                self.reserve -= take


class Enemy:
    def __init__(self, plat, x):
        self.w, self.h = 26, 46
        self.plat = plat
        self.x = float(x)
        self.rect = pygame.Rect(int(x), plat.top - self.h, self.w, self.h)
        self.dir = random.choice((-1, 1))
        self.hp = self.max_hp = 100
        self.speed = random.uniform(40, 70)
        self.aim_t = 0.0
        self.aim_time = 1.1
        self.cool = random.uniform(0.5, 1.5)
        self.stun = 0.0
        self.flash = 0.0
        self.state = "patrol"

    @property
    def head(self):
        return pygame.Rect(self.rect.x + 3, self.rect.y, self.rect.w - 6, 13)

    @property
    def eye(self):
        return (self.rect.centerx, self.rect.y + 14)

    def update(self, dt, g):
        self.flash = max(0.0, self.flash - dt)
        if self.stun > 0:
            self.stun -= dt
            self.state = "stunned"
            self.aim_t = 0
            return
        p = g.player
        target = (p.rect.centerx, p.rect.y + 16)
        eye = self.eye
        dist = math.hypot(target[0] - eye[0], target[1] - eye[1])
        seen = p.hp > 0 and dist < g.cfg["enemy_range"] and g.los(eye, target)
        self.cool = max(0.0, self.cool - dt)

        if seen:
            self.state = "aim"
            self.dir = 1 if target[0] > eye[0] else -1
            if self.cool <= 0:
                self.aim_t += dt
                if self.aim_t >= self.aim_time:
                    self.fire(g, eye, target)
                    self.aim_t = 0
                    self.cool = random.uniform(1.2, 2.4)
        else:
            self.state = "patrol"
            self.aim_t = max(0.0, self.aim_t - dt * 2)
            self.x += self.dir * self.speed * dt
            if self.x < self.plat.left + 8:
                self.x, self.dir = self.plat.left + 8, 1
            elif self.x + self.w > self.plat.right - 8:
                self.x, self.dir = self.plat.right - 8 - self.w, -1
            self.rect.x = int(self.x)

    def fire(self, g, eye, target):
        if random.random() < 0.65:
            g.damage_player(random.randint(8, 14))
            end = target
        else:
            end = (target[0] + random.randint(-70, 70), target[1] + random.randint(-70, 70))
        g.tracers.append([eye, end, 0.12, RED])


# --------------------------------------------------------------------------- #
#  Hacker console
# --------------------------------------------------------------------------- #
class Console:
    def __init__(self, game):
        self.game = game
        self.open = False
        self.text = ""
        self.lines = []
        self.history = []
        self.hidx = 0
        self.queue = []  # [delay, text, color, callback]
        self.font = pygame.font.SysFont("consolas,couriernew,dejavusansmono,monospace", 16)
        self.blink = 0.0
        self.panel_h = 340
        self.scan = pygame.Surface((W, self.panel_h), pygame.SRCALPHA)
        for y in range(0, self.panel_h, 3):
            pygame.draw.line(self.scan, (0, 0, 0, 45), (0, y), (W, y))
        self.say("== NEURAL//OS v1.337  root access granted ==", GREEN)
        self.say("type 'help' for commands  |  TAB autocompletes  |  UP/DOWN history", DGREEN)

    def say(self, text, color=GREEN):
        for part in str(text).split("\n"):
            self.lines.append((part, color))
        self.lines = self.lines[-300:]

    def schedule(self, delay, text, color=GREEN, callback=None):
        self.queue.append([delay, text, color, callback])

    def toggle(self):
        self.open = not self.open
        self.blink = 0.0

    def update(self, dt):
        self.blink += dt
        if self.queue:
            self.queue[0][0] -= dt
            if self.queue[0][0] <= 0:
                _, text, color, cb = self.queue.pop(0)
                if text:
                    self.say(text, color)
                if cb:
                    cb()

    def handle_key(self, ev):
        if ev.key == pygame.K_ESCAPE:
            self.open = False
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            cmd = self.text.strip()
            self.text = ""
            if cmd:
                self.history.append(cmd)
                self.hidx = len(self.history)
                self.say("> " + cmd, WHITE)
                self.game.run_command(cmd)
        elif ev.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
        elif ev.key == pygame.K_UP:
            if self.history:
                self.hidx = max(0, self.hidx - 1)
                self.text = self.history[self.hidx]
        elif ev.key == pygame.K_DOWN:
            if self.history:
                self.hidx = min(len(self.history), self.hidx + 1)
                self.text = self.history[self.hidx] if self.hidx < len(self.history) else ""
        elif ev.key == pygame.K_TAB:
            matches = [c for c in self.game.command_names() if c.startswith(self.text.lower())]
            if len(matches) == 1:
                self.text = matches[0] + " "
            elif matches:
                self.say("  ".join(matches), DGREEN)
        elif ev.unicode and ev.unicode.isprintable() and ev.unicode != "`":
            self.text += ev.unicode

    def draw(self, surf):
        if not self.open:
            return
        panel = pygame.Surface((W, self.panel_h), pygame.SRCALPHA)
        panel.fill((0, 14, 4, 228))
        panel.blit(self.scan, (0, 0))
        pygame.draw.line(panel, GREEN, (0, self.panel_h - 1), (W, self.panel_h - 1), 2)
        lh = self.font.get_height() + 2
        max_lines = (self.panel_h - 40) // lh
        y = 8
        for text, color in self.lines[-max_lines:]:
            panel.blit(self.font.render(text, True, color), (12, y))
            y += lh
        cursor = "_" if int(self.blink * 2) % 2 == 0 else " "
        prompt = self.font.render("root@neural:~# " + self.text + cursor, True, GREEN)
        panel.blit(prompt, (12, self.panel_h - 28))
        surf.blit(panel, (0, 0))


# --------------------------------------------------------------------------- #
#  Game
# --------------------------------------------------------------------------- #
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("SNIPER//NET")
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas,couriernew,dejavusansmono,monospace", 18)
        self.big = pygame.font.SysFont("consolas,couriernew,dejavusansmono,monospace", 44, bold=True)
        pygame.mouse.set_visible(False)

        self.cfg = {
            "god": False, "infammo": False, "fly": False, "noclip": False, "esp": False,
            "speed": 260.0, "jump": 560.0, "gravity": 1500.0,
            "timescale": 1.0, "zoom": 3.0, "enemy_range": 750.0,
        }

        self.platforms = self.build_level()
        self.build_background()
        self.scope_r = 230
        self.scope_mask = pygame.Surface((self.scope_r * 2, self.scope_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.scope_mask, (255, 255, 255, 255),
                           (self.scope_r, self.scope_r), self.scope_r)

        self.console = Console(self)
        self.time = 0.0
        self.cam = [0.0, 0.0]
        self.shake = 0.0
        self.hurt_flash = 0.0
        self.reset()

    # ----- setup --------------------------------------------------------- #
    def build_level(self):
        plats = [pygame.Rect(0, 820, WORLD_W, 80)]
        for x, y, w in [
            (300, 700, 260), (650, 620, 220), (950, 540, 260), (1300, 640, 300),
            (1650, 560, 240), (1950, 470, 260), (2300, 600, 300), (2650, 520, 220),
            (2950, 640, 280), (3250, 540, 250), (600, 430, 180), (1500, 420, 200),
            (2500, 380, 220), (3100, 400, 200), (1100, 360, 200), (1900, 300, 180),
        ]:
            plats.append(pygame.Rect(x, y, w, 20))
        # a few pillars to hide behind
        for x, h in [(820, 100), (1760, 120), (2860, 110)]:
            plats.append(pygame.Rect(x, 820 - h, 36, h))
        return plats

    def build_background(self):
        rnd = random.Random(7)
        self.bg = pygame.Surface((W, H))
        for y in range(H):
            t = y / H
            pygame.draw.line(self.bg, (int(8 + 22 * t), int(10 + 14 * t), int(28 + 40 * t)), (0, y), (W, y))
        for _ in range(140):
            self.bg.set_at((rnd.randrange(W), rnd.randrange(int(H * 0.6))),
                           rnd.choice([(200, 200, 255), (120, 120, 180)]))
        self.skyline = []
        for layer, color in ((0.25, (16, 20, 44)), (0.5, (22, 28, 58))):
            x = 0
            while x < WORLD_W:
                w, h = rnd.randint(60, 150), rnd.randint(120, 380)
                self.skyline.append((layer, color, pygame.Rect(x, 0, w, h)))
                x += w + rnd.randint(10, 50)

    def reset(self):
        self.player = Player(200, 700)
        self.enemies = []
        self.tracers = []
        self.particles = []
        self.texts = []
        self.wave = 1
        self.score = 0
        self.kills = 0
        self.spawn_wave()

    def spawn_enemy(self):
        choices = [p for p in self.platforms if p.w >= 180]
        for _ in range(40):
            p = random.choice(choices)
            x = random.randint(p.left + 20, p.right - 50)
            if abs(x - self.player.cx) > 400:
                e = Enemy(p, x)
                self.enemies.append(e)
                return e
        return None

    def spawn_wave(self, n=None):
        for _ in range(n if n is not None else 4 + self.wave * 2):
            self.spawn_enemy()

    # ----- helpers -------------------------------------------------------- #
    def los(self, a, b):
        return not any(clip(p, a, b) for p in self.platforms)

    def gun_origin(self):
        return (self.player.rect.centerx, self.player.rect.y + 16)

    def mouse_world(self):
        mx, my = pygame.mouse.get_pos()
        return mx + self.cam[0], my + self.cam[1]

    def aim_angle(self):
        o = self.gun_origin()
        m = self.mouse_world()
        return math.atan2(m[1] - o[1], m[0] - o[0])

    def cast(self, origin, ang, maxd=2600):
        d = (math.cos(ang), math.sin(ang))
        end = (origin[0] + d[0] * maxd, origin[1] + d[1] * maxd)

        def dist(pt):
            return math.hypot(pt[0] - origin[0], pt[1] - origin[1])

        best, hit = maxd, None
        for p in self.platforms:
            c = clip(p, origin, end)
            if c and dist(c[0]) < best:
                best, hit = dist(c[0]), None
        for e in self.enemies:
            c = clip(e.head, origin, end)
            is_head = bool(c)
            if not c:
                c = clip(e.rect, origin, end)
            if c and dist(c[0]) < best:
                best, hit = dist(c[0]), (e, is_head)
        return (origin[0] + d[0] * best, origin[1] + d[1] * best), hit

    def float_text(self, text, pos, color=YELLOW):
        self.texts.append([text, pos[0], pos[1], 1.2, color])

    def burst(self, pos, color, n=14, speed=220):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            s = random.uniform(40, speed)
            self.particles.append([pos[0], pos[1], math.cos(a) * s, math.sin(a) * s - 60,
                                   random.uniform(0.3, 0.7), color])

    def damage_player(self, n):
        if self.cfg["god"] or self.player.hp <= 0:
            return
        self.player.hp = max(0, self.player.hp - n)
        self.hurt_flash = 0.25
        self.shake = max(self.shake, 8)

    # ----- actions -------------------------------------------------------- #
    def scoped(self):
        return pygame.mouse.get_pressed()[2] and self.player.hp > 0 and not self.console.open

    def shoot(self):
        p = self.player
        if p.hp <= 0 or p.cooldown > 0 or p.reload_t > 0:
            return
        if p.mag <= 0:
            self.float_text("RELOAD! (R)", (p.rect.centerx, p.rect.y - 20), RED)
            return
        if not self.cfg["infammo"]:
            p.mag -= 1
        p.cooldown = 0.9

        steady = self.scoped() and pygame.key.get_mods() & pygame.KMOD_SHIFT
        spread = 0.0003 if steady else (0.003 if self.scoped() else 0.06)
        ang = self.aim_angle() + random.uniform(-spread, spread)
        origin = self.gun_origin()
        end, hit = self.cast(origin, ang)
        self.tracers.append([origin, end, 0.25, YELLOW])
        self.shake = max(self.shake, 6)

        if hit:
            e, head = hit
            e.hp -= 150 if head else 70
            e.flash = 0.15
            self.burst(end, RED if head else (255, 150, 60))
            if e.hp <= 0:
                self.enemies.remove(e)
                self.kills += 1
                gain = 150 if head else 100
                self.score += gain
                self.burst(e.rect.center, (255, 200, 80), 30, 320)
                self.float_text("HEADSHOT +%d" % gain if head else "+%d" % gain,
                                (e.rect.centerx, e.rect.y - 10), RED if head else YELLOW)
        else:
            self.burst(end, GREY, 6, 120)

    def reload(self):
        p = self.player
        if p.reload_t <= 0 and p.mag < p.mag_size and p.reserve > 0 and p.hp > 0:
            p.reload_t = 1.8

    # ----- console commands ---------------------------------------------- #
    def command_names(self):
        return sorted(n[4:] for n in dir(self) if n.startswith("cmd_"))

    def run_command(self, line):
        parts = line.split()
        name, args = parts[0].lower(), parts[1:]
        fn = getattr(self, "cmd_" + name, None)
        if not fn:
            self.console.say("command not found: %s  (try 'help')" % name, RED)
            return
        try:
            fn(args)
        except Exception as ex:  # bad args etc.
            self.console.say("error: %s" % ex, RED)

    def _flag(self, key, args, label):
        if args:
            self.cfg[key] = args[0].lower() in ("1", "on", "true", "yes")
        else:
            self.cfg[key] = not self.cfg[key]
        self.console.say("%s: %s" % (label, "ON" if self.cfg[key] else "OFF"))

    def _num(self, key, args, label, lo, hi):
        if not args:
            self.console.say("%s = %s" % (label, self.cfg[key]))
            return
        self.cfg[key] = max(lo, min(hi, float(args[0])))
        self.console.say("%s set to %s" % (label, self.cfg[key]))

    def cmd_help(self, args):
        """help             - list commands"""
        self.console.say("available commands:", WHITE)
        for n in self.command_names():
            doc = (getattr(self, "cmd_" + n).__doc__ or n).strip()
            self.console.say("  " + doc, DGREEN)

    def cmd_clear(self, args):
        """clear            - clear the console"""
        self.console.lines = []

    def cmd_god(self, args):
        """god [on|off]     - toggle invincibility"""
        self._flag("god", args, "god mode")

    def cmd_heal(self, args):
        """heal             - restore full health"""
        self.player.hp = self.player.max_hp
        self.console.say("health restored")

    def cmd_ammo(self, args):
        """ammo [n]         - give ammo (default 30)"""
        self.player.reserve += int(args[0]) if args else 30
        self.console.say("reserve ammo: %d" % self.player.reserve)

    def cmd_infammo(self, args):
        """infammo [on|off] - unlimited ammo"""
        self._flag("infammo", args, "infinite ammo")

    def cmd_fly(self, args):
        """fly [on|off]     - fly mode (W/S to move vertically)"""
        self._flag("fly", args, "fly")

    def cmd_noclip(self, args):
        """noclip [on|off]  - walk through platforms"""
        self._flag("noclip", args, "noclip")

    def cmd_esp(self, args):
        """esp [on|off]     - enemy boxes + health bars"""
        self._flag("esp", args, "ESP")

    def cmd_speed(self, args):
        """speed [n]        - move speed (default 260)"""
        self._num("speed", args, "speed", 50, 1200)

    def cmd_jump(self, args):
        """jump [n]         - jump power (default 560)"""
        self._num("jump", args, "jump", 100, 1500)

    def cmd_gravity(self, args):
        """gravity [n]      - gravity (default 1500)"""
        self._num("gravity", args, "gravity", 0, 5000)

    def cmd_timescale(self, args):
        """timescale [n]    - slow-mo / fast-forward (0.1 - 3)"""
        self._num("timescale", args, "timescale", 0.1, 3.0)

    def cmd_zoom(self, args):
        """zoom [n]        - scope zoom (2 - 8)"""
        self._num("zoom", args, "scope zoom", 2.0, 8.0)

    def cmd_spawn(self, args):
        """spawn [n]        - spawn n enemies (default 1)"""
        n = int(args[0]) if args else 1
        self.spawn_wave(min(n, 40))
        self.console.say("spawned %d enemies (%d alive)" % (n, len(self.enemies)))

    def cmd_killall(self, args):
        """killall          - delete every enemy"""
        n = len(self.enemies)
        self.enemies.clear()
        self.console.say("terminated %d processes" % n)

    def cmd_tp(self, args):
        """tp x y           - teleport (world is 3600x900)"""
        self.player.teleport(float(args[0]), float(args[1]))
        self.console.say("teleported")

    def cmd_score(self, args):
        """score [n]        - set your score"""
        if args:
            self.score = int(args[0])
        self.console.say("score = %d" % self.score)

    def cmd_wave(self, args):
        """wave [n]         - jump to wave n (respawns enemies)"""
        self.wave = int(args[0]) if args else self.wave + 1
        self.enemies.clear()
        self.spawn_wave()
        self.console.say("now on wave %d" % self.wave)

    def cmd_hack(self, args):
        """hack             - EMP-hack all enemies (offline for 8s)"""
        def go():
            for e in self.enemies:
                e.stun = 8.0
        c = self.console
        c.schedule(0.0, "[*] scanning local network ...", GREEN)
        c.schedule(0.5, "[*] found %d hostile nodes" % len(self.enemies), GREEN)
        c.schedule(0.5, "[*] bypassing firewall ............ OK", GREEN)
        c.schedule(0.5, "[*] injecting payload ............. OK", GREEN)
        c.schedule(0.6, "[+] ACCESS GRANTED - enemies offline for 8s", YELLOW, go)

    def cmd_quit(self, args):
        """quit             - exit the game"""
        pygame.quit()
        sys.exit()

    # ----- update --------------------------------------------------------- #
    def update(self, dt):
        p = self.player
        keys = pygame.key.get_pressed()
        scoped = self.scoped()

        if p.hp > 0:
            p.update(dt, self, keys, scoped)
        for e in self.enemies:
            e.update(dt, self)

        if not self.enemies and p.hp > 0:
            self.wave += 1
            self.spawn_wave()
            p.reserve += 6
            self.float_text("WAVE %d  (+6 ammo)" % self.wave, (p.cx, p.rect.y - 50), CYAN)

        # camera
        tx = max(0, min(WORLD_W - W, p.rect.centerx - W / 2))
        ty = max(0, min(WORLD_H - H, p.rect.centery - H / 2))
        self.cam[0] += (tx - self.cam[0]) * min(1.0, 8 * dt)
        self.cam[1] += (ty - self.cam[1]) * min(1.0, 8 * dt)

        self.shake = max(0.0, self.shake - 40 * dt)
        self.hurt_flash = max(0.0, self.hurt_flash - dt)

        for t in self.tracers:
            t[2] -= dt
        self.tracers = [t for t in self.tracers if t[2] > 0]
        for q in self.particles:
            q[0] += q[2] * dt
            q[1] += q[3] * dt
            q[3] += 700 * dt
            q[4] -= dt
        self.particles = [q for q in self.particles if q[4] > 0]
        for t in self.texts:
            t[2] -= 40 * dt
            t[3] -= dt
        self.texts = [t for t in self.texts if t[3] > 0]

    # ----- drawing -------------------------------------------------------- #
    def draw(self):
        s = self.screen
        ox = oy = 0
        if self.shake > 0:
            ox, oy = random.uniform(-self.shake, self.shake), random.uniform(-self.shake, self.shake)
        cx, cy = int(self.cam[0] + ox), int(self.cam[1] + oy)

        s.blit(self.bg, (0, 0))
        for layer, color, r in self.skyline:
            rr = pygame.Rect(r.x - cx * layer, H - r.h - cy * layer * 0.4 + 60, r.w, r.h)
            if -200 < rr.x < W:
                pygame.draw.rect(s, color, rr)

        for plat in self.platforms:
            r = plat.move(-cx, -cy)
            if r.right < 0 or r.left > W:
                continue
            pygame.draw.rect(s, (38, 46, 70), r)
            pygame.draw.rect(s, (90, 220, 255), (r.x, r.y, r.w, 3))

        for e in self.enemies:
            self.draw_enemy(e, cx, cy)

        self.draw_player(cx, cy)

        for a, b, life, color in self.tracers:
            alpha = max(0, min(255, int(life * 1500)))
            line = pygame.Surface((W, H), pygame.SRCALPHA)
            pygame.draw.line(line, (*color, alpha), (a[0] - cx, a[1] - cy), (b[0] - cx, b[1] - cy), 2)
            s.blit(line, (0, 0))

        for x, y, _, _, life, color in self.particles:
            pygame.draw.rect(s, color, (x - cx, y - cy, 3, 3))

        for text, x, y, life, color in self.texts:
            img = self.font.render(text, True, color)
            s.blit(img, (x - cx - img.get_width() // 2, y - cy))

        if self.scoped():
            self.draw_scope()
        else:
            mx, my = pygame.mouse.get_pos()
            pygame.draw.circle(s, WHITE, (mx, my), 9, 1)
            pygame.draw.line(s, WHITE, (mx - 14, my), (mx - 5, my))
            pygame.draw.line(s, WHITE, (mx + 5, my), (mx + 14, my))
            pygame.draw.line(s, WHITE, (mx, my - 14), (mx, my - 5))
            pygame.draw.line(s, WHITE, (mx, my + 5), (mx, my + 14))

        if self.hurt_flash > 0:
            v = pygame.Surface((W, H), pygame.SRCALPHA)
            v.fill((255, 0, 0, int(self.hurt_flash * 300)))
            s.blit(v, (0, 0))

        self.draw_hud()
        self.console.draw(s)
        pygame.display.flip()

    def draw_player(self, cx, cy):
        p = self.player
        r = p.rect.move(-cx, -cy)
        if p.hp <= 0:
            pygame.draw.rect(self.screen, (60, 60, 70), (r.x - 10, r.bottom - 14, 46, 14))
            return
        pygame.draw.rect(self.screen, (60, 190, 230), r)
        pygame.draw.rect(self.screen, (230, 240, 255), (r.x + 3, r.y, r.w - 6, 13))
        ang = self.aim_angle()
        o = (self.gun_origin()[0] - cx, self.gun_origin()[1] - cy)
        tip = (o[0] + math.cos(ang) * 52, o[1] + math.sin(ang) * 52)
        pygame.draw.line(self.screen, (25, 25, 35), o, tip, 5)

        if self.scoped():  # laser sight
            end, _ = self.cast(self.gun_origin(), ang)
            pygame.draw.line(self.screen, (255, 40, 40), tip, (end[0] - cx, end[1] - cy), 1)

    def draw_enemy(self, e, cx, cy):
        r = e.rect.move(-cx, -cy)
        if r.right < -50 or r.left > W + 50:
            return
        body = (255, 255, 255) if e.flash > 0 else ((90, 90, 110) if e.stun > 0 else (210, 70, 70))
        pygame.draw.rect(self.screen, body, r)
        pygame.draw.rect(self.screen, (40, 40, 50), (r.x + 3, r.y, r.w - 6, 13))
        eye_x = r.centerx + e.dir * 4
        pygame.draw.rect(self.screen, (0, 255, 255) if e.stun > 0 else (255, 230, 0),
                         (eye_x - 2, r.y + 5, 4, 3))
        pygame.draw.line(self.screen, (25, 25, 30), (r.centerx, r.y + 22),
                         (r.centerx + e.dir * 26, r.y + 22), 4)

        if e.state == "aim" and e.aim_t > 0:  # telegraph the shot
            p = self.player
            t = (p.rect.centerx - cx, p.rect.y + 16 - cy)
            a = (e.eye[0] - cx, e.eye[1] - cy)
            pygame.draw.line(self.screen, (255, 60, 60), a, t, 1)

        if self.cfg["esp"]:
            pygame.draw.rect(self.screen, GREEN, r.inflate(8, 8), 1)
            pygame.draw.rect(self.screen, (60, 0, 0), (r.x - 4, r.y - 12, r.w + 8, 5))
            pygame.draw.rect(self.screen, GREEN, (r.x - 4, r.y - 12, (r.w + 8) * max(0, e.hp) // e.max_hp, 5))

    def draw_scope(self):
        s = self.screen
        r = self.scope_r
        mx, my = pygame.mouse.get_pos()
        size = int(2 * r / self.cfg["zoom"])
        src = pygame.Rect(0, 0, size, size)
        src.center = (mx, my)
        src.clamp_ip(s.get_rect())
        lens = pygame.transform.smoothscale(s.subsurface(src).copy(), (2 * r, 2 * r)).convert_alpha()
        lens.blit(self.scope_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        dark = pygame.Surface((W, H), pygame.SRCALPHA)
        dark.fill((0, 0, 0, 175))
        s.blit(dark, (0, 0))
        s.blit(lens, (mx - r, my - r))
        pygame.draw.circle(s, (10, 10, 10), (mx, my), r, 6)
        pygame.draw.line(s, (20, 20, 20), (mx - r, my), (mx + r, my), 1)
        pygame.draw.line(s, (20, 20, 20), (mx, my - r), (mx, my + r), 1)
        pygame.draw.line(s, (255, 40, 40), (mx - 40, my), (mx + 40, my), 1)
        pygame.draw.line(s, (255, 40, 40), (mx, my - 40), (mx, my + 40), 1)
        pygame.draw.circle(s, (255, 40, 40), (mx, my), 2)
        z = self.font.render("%.1fx" % self.cfg["zoom"], True, GREEN)
        s.blit(z, (mx + r - 60, my + r - 40))

    def draw_hud(self):
        s = self.screen
        p = self.player
        pygame.draw.rect(s, (40, 10, 10), (20, 20, 240, 18))
        pygame.draw.rect(s, (60, 220, 90), (20, 20, int(240 * p.hp / p.max_hp), 18))
        pygame.draw.rect(s, WHITE, (20, 20, 240, 18), 1)
        s.blit(self.font.render("HP %d" % p.hp, True, WHITE), (268, 19))

        if p.reload_t > 0:
            ammo = "RELOADING..."
        else:
            ammo = "AMMO %d/%s" % (p.mag, "inf" if self.cfg["infammo"] else p.reserve)
        s.blit(self.font.render(ammo, True, YELLOW), (20, 48))
        if p.cooldown > 0 and p.reload_t <= 0:
            s.blit(self.font.render("bolt cycling...", True, GREY), (20, 72))

        info = "WAVE %d    SCORE %d    KILLS %d    ENEMIES %d" % (
            self.wave, self.score, self.kills, len(self.enemies))
        img = self.font.render(info, True, CYAN)
        s.blit(img, (W - img.get_width() - 20, 20))

        tags = [k.upper() for k in ("god", "fly", "noclip", "esp", "infammo") if self.cfg[k]]
        if self.cfg["timescale"] != 1.0:
            tags.append("TIME x%.1f" % self.cfg["timescale"])
        if tags:
            timg = self.font.render("[" + " ".join(tags) + "]", True, GREEN)
            s.blit(timg, (W - 20 - timg.get_width(), 46))

        hint = self.font.render("` console | RMB scope | R reload", True, GREY)
        s.blit(hint, (20, H - 28))

        if p.hp <= 0:
            t1 = self.big.render("YOU WERE TERMINATED", True, RED)
            t2 = self.font.render("press ENTER to restart", True, WHITE)
            s.blit(t1, (W // 2 - t1.get_width() // 2, H // 2 - 40))
            s.blit(t2, (W // 2 - t2.get_width() // 2, H // 2 + 20))

    # ----- main loop ------------------------------------------------------ #
    def handle_event(self, ev):
        if ev.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_BACKQUOTE, pygame.K_F1):
                self.console.toggle()
                return
            if self.console.open:
                self.console.handle_key(ev)
                return
            if ev.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()
            if ev.key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
                self.player.jump_buf = 0.12
            elif ev.key == pygame.K_r:
                self.reload()
            elif ev.key == pygame.K_RETURN and self.player.hp <= 0:
                self.reset()
        elif self.console.open:
            return
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.shoot()
        elif ev.type == pygame.MOUSEWHEEL and self.scoped():
            self.cfg["zoom"] = max(2.0, min(8.0, self.cfg["zoom"] + ev.y * 0.5))

    def run(self, max_frames=None):
        frames = 0
        while max_frames is None or frames < max_frames:
            real_dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for ev in pygame.event.get():
                self.handle_event(ev)
            self.console.update(real_dt)
            if not self.console.open:  # game pauses while the console is open
                self.time += real_dt
                self.update(real_dt * self.cfg["timescale"])
            self.draw()
            frames += 1


if __name__ == "__main__":
    Game().run()
