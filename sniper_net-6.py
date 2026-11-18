#!/usr/bin/env python3
"""
SNIPER//NET v0.2  -  2D platformer sniper game with map chooser, LAN chat,
hacker console and a "next update" countdown.

Mac install:  pip3 install pygame
Run (Terminal, not IDLE):  python3 sniper_net.py

CONTROLS
  A / D or arrows ........ move              W / Space / Up ... jump
  Mouse .................. aim               Left click ....... fire (bolt-action)
  Hold right click or Q .. scope in          Wheel / 2-finger scroll ... zoom
     (Mac trackpad: two-finger click = right click, or just hold Q)
  Hold Shift (scoped) .... steady aim        R ................ reload
  M ...................... map chooser       T ................ chat
  ` (backtick) ........... hacker console (F1 works too, with fn on a Mac)
  F11 / Alt+Enter ........ fullscreen    Esc ... quit              Enter ............ restart after dying

MULTIPLAYER CHAT (same Wi-Fi / LAN, or port-forward 5555 for the internet)
  Host:   open console ->  name Bob   then   host
  Friend: open console ->  name Alice then   join <host ip>
  Press T to chat.  Anything starting with / is run as a console command.
  (macOS may ask to let Python accept incoming connections - click Allow.)
"""
import json
import math
import queue
import random
import re
import socket
import sys
import threading
from datetime import datetime, timedelta

import pygame

if sys.platform == "win32":  # crisp rendering on high-DPI Windows screens
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

VERSION = "3.2"
# >>> Set this to your real release time (or use the console: nextupdate 2h30m)
NEXT_UPDATE = datetime(2026, 11, 22, 18, 0)

W, H = 1280, 720
FPS = 60
DEFAULT_PORT = 5555
FONT_NAMES = "menlo,monaco,consolas,couriernew,dejavusansmono,monospace"

GREEN = (80, 255, 120)
DGREEN = (30, 120, 60)
WHITE = (235, 235, 235)
RED = (255, 70, 70)
YELLOW = (255, 220, 90)
CYAN = (90, 220, 255)
GREY = (120, 130, 140)


# --------------------------------------------------------------------------- #
#  Maps
# --------------------------------------------------------------------------- #
def _tower_platforms():
    plats = [(0, 2120, 1400, 80)]
    cols = [60, 520, 980]
    seq = [0, 1, 2, 1]
    for i in range(17):
        plats.append((cols[seq[i % 4]], 2020 - 100 * i, 360, 20))
    plats.append((520, 320, 400, 20))  # summit
    return plats


MAPS = [
    {
        "name": "Neon Rooftops",
        "desc": "Classic city run.\nSniper perches up high.\nPillars for cover.",
        "w": 3600, "h": 900, "spawn": (200, 770),
        "top": (8, 10, 28), "bottom": (30, 24, 68), "accent": (90, 220, 255),
        "buildings": [(16, 20, 44), (22, 28, 58)],
        "platforms": [
            (0, 820, 3600, 80),
            (300, 720, 260, 20), (650, 640, 220, 20), (950, 560, 260, 20),
            (1300, 640, 300, 20), (1650, 560, 240, 20), (1950, 480, 260, 20),
            (2300, 600, 300, 20), (2650, 520, 220, 20), (2950, 640, 280, 20),
            (3250, 540, 250, 20),
            (1100, 460, 200, 20), (1450, 380, 200, 20), (1800, 300, 180, 20),
            (2150, 380, 200, 20), (2500, 300, 200, 20), (2850, 380, 220, 20),
            (3200, 300, 200, 20),
            (820, 720, 36, 100), (1760, 700, 36, 120), (2860, 710, 36, 110),
        ],
    },
    {
        "name": "Canyon Run",
        "desc": "Long open valley.\nCliffs and bridges.\nGreat for long shots.",
        "w": 4400, "h": 900, "spawn": (100, 560),
        "top": (60, 28, 24), "bottom": (150, 80, 50), "accent": (255, 170, 90),
        "buildings": [(80, 40, 36), (110, 56, 44)],
        "platforms": [
            (0, 820, 4400, 80),
            (0, 620, 260, 200), (260, 720, 180, 100),
            (800, 760, 120, 60), (1150, 730, 150, 90),
            (1300, 640, 300, 20), (1700, 560, 300, 20), (2100, 640, 300, 20),
            (2500, 540, 300, 20), (1900, 740, 120, 80), (2750, 740, 120, 80),
            (2900, 460, 220, 20), (3250, 380, 200, 20),
            (3150, 740, 150, 80), (3400, 720, 200, 100), (3600, 620, 800, 200),
        ],
    },
    {
        "name": "Sky Tower",
        "desc": "Tall zigzag climb.\nFight your way up.\nGravity is watching.",
        "w": 1400, "h": 2200, "spawn": (700, 2070),
        "top": (4, 6, 20), "bottom": (40, 30, 90), "accent": (200, 120, 255),
        "buildings": [(14, 12, 40), (24, 20, 60)],
        "platforms": _tower_platforms(),
    },
    {
        "name": "The Pit",
        "desc": "Small symmetric arena.\nFast, close fights.\nStairs and cover.",
        "w": 1800, "h": 900, "spawn": (150, 674),
        "top": (20, 8, 16), "bottom": (70, 20, 40), "accent": (255, 90, 130),
        "buildings": [(36, 14, 28), (50, 18, 38)],
        "platforms": [
            (0, 820, 1800, 80),
            (100, 720, 200, 20), (380, 620, 200, 20), (700, 520, 400, 20),
            (1220, 620, 200, 20), (1500, 720, 200, 20), (800, 420, 200, 20),
            (600, 740, 40, 80), (1160, 740, 40, 80), (880, 760, 40, 60),
        ],
    },
]

# Season 3 maps
MAPS.extend([
    {
        "name": "Molten Foundry", "desc": "Lava-lit factory.\nTight platforms and cover.\nSeason 3 arena.",
        "w": 2600, "h": 900, "spawn": (120, 770),
        "top": (28, 8, 8), "bottom": (110, 28, 12), "accent": (255, 105, 35),
        "buildings": [(40, 12, 8), (70, 20, 10)],
        "platforms": [(0,820,2600,80),(220,700,260,20),(560,610,240,20),(900,710,280,20),
                       (1240,590,260,20),(1580,690,240,20),(1910,560,280,20),(2250,700,220,20),
                       (700,470,180,20),(1100,390,220,20),(1510,450,180,20),(1860,360,220,20),
                       (500,760,45,60),(1700,760,45,60)]
    },
    {
        "name": "Glacier Base", "desc": "Frozen research base.\nHigh ice ledges.\nWatch your angles.",
        "w": 3000, "h": 900, "spawn": (140, 770),
        "top": (8, 22, 42), "bottom": (25, 70, 110), "accent": (110, 225, 255),
        "buildings": [(10, 35, 55), (18, 55, 80)],
        "platforms": [(0,820,3000,80),(240,710,240,20),(540,620,250,20),(850,700,220,20),
                       (1160,590,260,20),(1480,680,260,20),(1810,560,250,20),(2130,660,260,20),
                       (2470,550,300,20),(700,450,190,20),(1080,390,220,20),(1610,410,210,20),
                       (2020,360,210,20),(2650,390,180,20)]
    }
])



def clip(rect, a, b):
    """Rect.clipline with integer coordinates (safe across pygame versions)."""
    return rect.clipline(int(a[0]), int(a[1]), int(b[0]), int(b[1]))


class NoKeys:
    """Stand-in for pygame.key.get_pressed() while typing in chat."""
    def __getitem__(self, k):
        return False


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


# --------------------------------------------------------------------------- #
#  Networking (line-delimited JSON over TCP; host relays chat to everyone)
# --------------------------------------------------------------------------- #
class Net:
    def __init__(self):
        self.mode = None  # None | "connecting" | "host" | "client"
        self.inbox = queue.Queue()
        self.clients = {}  # host side: socket -> name
        self.lock = threading.Lock()
        self.sock = None
        self.gen = 0
        self.name = "Sniper%d" % random.randint(100, 999)

    @staticmethod
    def _send(sock, obj):
        try:
            sock.sendall((json.dumps(obj) + "\n").encode())
        except OSError:
            pass

    def _sys(self, text):
        self.inbox.put({"t": "sys", "text": text})

    # ---- host ---------------------------------------------------------- #
    def host(self, port=DEFAULT_PORT):
        self.stop()
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", port))
        srv.listen(8)
        self.sock, self.mode = srv, "host"
        gen = self.gen
        threading.Thread(target=self._accept_loop, args=(srv, gen), daemon=True).start()

    def _accept_loop(self, srv, gen):
        while gen == self.gen:
            try:
                c, _ = srv.accept()
            except OSError:
                break
            with self.lock:
                self.clients[c] = "?"
            threading.Thread(target=self._client_reader, args=(c, gen), daemon=True).start()

    def _client_reader(self, c, gen):
        buf = b""
        try:
            while gen == self.gen:
                data = c.recv(4096)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        self._host_handle(c, json.loads(line))
                    except ValueError:
                        pass
        except OSError:
            pass
        finally:
            with self.lock:
                name = self.clients.pop(c, "?")
            try:
                c.close()
            except OSError:
                pass
            if gen == self.gen:
                self._host_emit({"t": "sys", "text": "%s left" % name})

    def _host_handle(self, c, msg):
        t = msg.get("t")
        if t == "hello":
            name = str(msg.get("name", "?"))[:16]
            with self.lock:
                self.clients[c] = name
            self._host_emit({"t": "sys", "text": "%s joined" % name})
        elif t == "chat":
            with self.lock:
                name = self.clients.get(c, "?")
            self._host_emit({"t": "chat", "name": name, "text": str(msg.get("text", ""))[:200]})

    def _host_emit(self, msg):
        self.inbox.put(msg)
        with self.lock:
            socks = list(self.clients)
        for s in socks:
            self._send(s, msg)

    # ---- client -------------------------------------------------------- #
    def join(self, ip, port=DEFAULT_PORT):
        self.stop()
        self.mode = "connecting"
        gen = self.gen
        threading.Thread(target=self._connect, args=(ip, port, gen), daemon=True).start()

    def _connect(self, ip, port, gen):
        try:
            s = socket.create_connection((ip, port), timeout=6)
        except OSError as e:
            if gen == self.gen:
                self.mode = None
                self._sys("could not connect to %s:%d (%s)" % (ip, port, e))
            return
        if gen != self.gen:
            s.close()
            return
        s.settimeout(None)
        self.sock, self.mode = s, "client"
        self._send(s, {"t": "hello", "name": self.name})
        self._sys("connected to %s:%d" % (ip, port))
        buf = b""
        try:
            while gen == self.gen:
                data = s.recv(4096)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        self.inbox.put(json.loads(line))
                    except ValueError:
                        pass
        except OSError:
            pass
        if gen == self.gen:
            self.mode = None
            self._sys("disconnected from host")

    # ---- shared -------------------------------------------------------- #
    def say(self, text):
        if self.mode == "host":
            self._host_emit({"t": "chat", "name": self.name, "text": text})
        elif self.mode == "client":
            self._send(self.sock, {"t": "chat", "text": text})

    def players(self):
        if self.mode != "host":
            return []
        with self.lock:
            return [self.name] + [n for n in self.clients.values() if n != "?"]

    def stop(self):
        self.gen += 1
        self.mode = None
        socks = []
        with self.lock:
            socks = list(self.clients)
            self.clients.clear()
        if self.sock:
            socks.append(self.sock)
            self.sock = None
        for s in socks:
            try:
                s.shutdown(socket.SHUT_RDWR)  # wakes blocked readers + sends FIN
            except OSError:
                pass
            try:
                s.close()
            except OSError:
                pass


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

        self.x += self.vx * dt
        self.x = max(0, min(game.world_w - self.w, self.x))
        self.rect.x = round(self.x)
        for p in solid:
            if self.rect.colliderect(p):
                if self.vx > 0:
                    self.rect.right = p.left
                elif self.vx < 0:
                    self.rect.left = p.right
                self.x = self.rect.x
                self.vx = 0

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

        if self.y > game.world_h + 300:  # fell out of the world
            self.teleport(*game.spawn)

        self.cooldown = max(0.0, self.cooldown - dt)
        if self.reload_t > 0:
            self.reload_t -= dt
            if self.reload_t <= 0:
                take = min(self.mag_size - self.mag, self.reserve)
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
#  Chat box (T) - shows lobby messages
# --------------------------------------------------------------------------- #
class Chat:
    def __init__(self, game):
        self.game = game
        self.open = False
        self.text = ""
        self.log = []  # [prefix, pcolor, text, tcolor, time]
        self.font = pygame.font.SysFont(FONT_NAMES, 16)

    def add(self, prefix, pcolor, text, tcolor=WHITE):
        self.log.append([prefix, pcolor, text, tcolor, pygame.time.get_ticks() / 1000.0])
        self.log = self.log[-80:]

    def sys(self, text):
        self.add("* ", YELLOW, text, YELLOW)

    def open_box(self):
        self.open = True
        self.text = ""

    def handle_key(self, ev):
        if ev.key == pygame.K_ESCAPE:
            self.open = False
            self.text = ""
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            msg = self.text.strip()
            self.text = ""
            self.open = False
            if msg:
                self.game.send_chat(msg)
        elif ev.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
        elif ev.unicode and ev.unicode.isprintable() and len(self.text) < 120:
            self.text += ev.unicode

    def draw(self, surf):
        now = pygame.time.get_ticks() / 1000.0
        shown = [e for e in self.log if self.open or now - e[4] < 10][-8:]
        lh = self.font.get_height() + 3
        y_end = H - 62
        net = self.game.net
        status = None
        if net.mode == "host":
            status = "HOSTING - %d player(s)" % len(net.players())
        elif net.mode == "client":
            status = "ONLINE"
        elif net.mode == "connecting":
            status = "CONNECTING..."
        if shown:
            bg = pygame.Surface((660, len(shown) * lh + 6), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 110))
            surf.blit(bg, (12, y_end - len(shown) * lh - 3))
        y = y_end - len(shown) * lh
        for prefix, pc, text, tc, _ in shown:
            a = self.font.render(prefix, True, pc)
            surf.blit(a, (18, y))
            if len(text) > 85:
                text = text[:85] + "..."
            surf.blit(self.font.render(text, True, tc), (18 + a.get_width(), y))
            y += lh
        if status:
            surf.blit(self.font.render("[" + status + "]", True, GREEN),
                      (18, y_end - len(shown) * lh - 22))
        if self.open:
            box = pygame.Surface((660, 26), pygame.SRCALPHA)
            box.fill((0, 0, 0, 190))
            surf.blit(box, (12, H - 58))
            cursor = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
            surf.blit(self.font.render("say> " + self.text + cursor, True, WHITE), (18, H - 54))


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
        self.font = pygame.font.SysFont(FONT_NAMES, 16)
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
        panel.blit(self.font.render("root@neural:~# " + self.text + cursor, True, GREEN),
                   (12, self.panel_h - 28))
        surf.blit(panel, (0, 0))


# --------------------------------------------------------------------------- #
#  Game
# --------------------------------------------------------------------------- #
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("SNIPER//NET v" + VERSION)
        self.screen = pygame.display.set_mode((W, H), pygame.SCALED | pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(FONT_NAMES, 18)
        self.med = pygame.font.SysFont(FONT_NAMES, 24, bold=True)
        self.big = pygame.font.SysFont(FONT_NAMES, 44, bold=True)

        self.cfg = {
            "god": False, "infammo": False, "fly": False, "noclip": False, "esp": False,
            "speed": 260.0, "jump": 650.0, "gravity": 1500.0,
            "timescale": 1.0, "zoom": 3.0, "enemy_range": 750.0,
        }
        self.update_at = NEXT_UPDATE
        self.net = Net()
        self.console = Console(self)
        self.chat = Chat(self)

        self.scope_r = 230
        self.scope_mask = pygame.Surface((self.scope_r * 2, self.scope_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.scope_mask, (255, 255, 255, 255),
                           (self.scope_r, self.scope_r), self.scope_r)

        self.time = 0.0
        self.shake = 0.0
        self.hurt_flash = 0.0
        self.map_idx = 0
        self.load_map(0)
        self.menu_bg = self.bg.copy()
        self.thumbs = [self.make_thumb(m) for m in MAPS]
        self.menu_sel = 0
        self.started = False
        self.state = "menu"
        pygame.mouse.set_visible(True)

    # ----- maps ----------------------------------------------------------- #
    def load_map(self, idx):
        m = MAPS[idx]
        self.map_idx = idx
        self.world_w, self.world_h = m["w"], m["h"]
        self.platforms = [pygame.Rect(*r) for r in m["platforms"]]
        self.spawn = m["spawn"]
        self.accent = m["accent"]
        self.build_background(m)
        self.reset()

    def build_background(self, m):
        rnd = random.Random(m["name"])
        self.bg = pygame.Surface((W, H))
        t0, b0 = m["top"], m["bottom"]
        for y in range(H):
            t = y / H
            pygame.draw.line(self.bg, tuple(int(t0[i] + (b0[i] - t0[i]) * t) for i in range(3)),
                             (0, y), (W, y))
        for _ in range(140):
            self.bg.set_at((rnd.randrange(W), rnd.randrange(int(H * 0.6))),
                           rnd.choice([(200, 200, 255), (140, 140, 190)]))
        self.skyline = []
        for layer, color in zip((0.25, 0.5), m["buildings"]):
            x = 0
            while x < self.world_w:
                w, h = rnd.randint(60, 150), rnd.randint(120, 380)
                self.skyline.append((layer, color, pygame.Rect(x, 0, w, h)))
                x += w + rnd.randint(10, 50)

    def make_thumb(self, m):
        bw, bh = 260, 150
        surf = pygame.Surface((bw, bh))
        surf.fill(m["bottom"])
        pygame.draw.rect(surf, m["top"], (0, 0, bw, bh // 2))
        sc = min(bw / m["w"], bh / m["h"])
        ox, oy = (bw - m["w"] * sc) / 2, (bh - m["h"] * sc) / 2
        for x, y, w, h in m["platforms"]:
            r = pygame.Rect(ox + x * sc, oy + y * sc, max(2, w * sc), max(2, h * sc))
            pygame.draw.rect(surf, (60, 70, 100), r)
            pygame.draw.rect(surf, m["accent"], (r.x, r.y, r.w, 1))
        sx, sy = m["spawn"]
        pygame.draw.circle(surf, GREEN, (int(ox + sx * sc), int(oy + sy * sc)), 3)
        return surf

    def reset(self):
        self.player = Player(*self.spawn)
        self.enemies = []
        self.tracers = []
        self.particles = []
        self.texts = []
        self.wave = 1
        self.score = 0
        self.kills = 0
        self.spawn_wave()
        self.snap_camera()

    def snap_camera(self):
        p = self.player
        self.cam = [max(0, min(self.world_w - W, p.rect.centerx - W / 2)),
                    max(0, min(self.world_h - H, p.rect.centery - H / 2))]

    def start_map(self, idx):
        self.load_map(idx)
        self.state = "play"
        self.started = True
        pygame.mouse.set_visible(False)
        self.chat.sys("map: " + MAPS[idx]["name"])

    def open_menu(self):
        self.state = "menu"
        self.menu_sel = self.map_idx
        pygame.mouse.set_visible(True)

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

    # ----- chat / net ------------------------------------------------------ #
    def send_chat(self, msg):
        if msg.startswith("/"):
            self.run_command(msg[1:])
            return
        if self.net.mode in ("host", "client"):
            self.net.say(msg)
        else:
            self.chat.sys("not in a lobby - open the console (`) and type: host   or   join <ip>")

    def poll_net(self):
        while True:
            try:
                m = self.net.inbox.get_nowait()
            except queue.Empty:
                break
            if m.get("t") == "chat":
                mine = m.get("name") == self.net.name
                self.chat.add(str(m.get("name", "?")) + ": ", GREEN if mine else CYAN,
                              str(m.get("text", "")))
            elif m.get("t") == "sys":
                self.chat.sys(str(m.get("text", "")))

    # ----- update timer ---------------------------------------------------- #
    def update_timer_text(self):
        if self.update_at is None:
            return None, WHITE
        rem = int((self.update_at - datetime.now()).total_seconds())
        if rem <= 0:
            return "UPDATE READY - restart the game!", YELLOW
        d, rem = divmod(rem, 86400)
        h, rem = divmod(rem, 3600)
        m, s = divmod(rem, 60)
        return "NEXT UPDATE IN %s%02d:%02d:%02d" % ("%dd " % d if d else "", h, m, s), CYAN

    # ----- actions -------------------------------------------------------- #
    def scoped(self):
        if self.state != "play" or self.player.hp <= 0 or self.console.open:
            return False
        q = (not self.chat.open) and pygame.key.get_pressed()[pygame.K_q]
        return bool(pygame.mouse.get_pressed()[2] or q)

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
        if not parts:
            return
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
        """jump [n]         - jump power (default 650)"""
        self._num("jump", args, "jump", 100, 1500)

    def cmd_gravity(self, args):
        """gravity [n]      - gravity (default 1500)"""
        self._num("gravity", args, "gravity", 0, 5000)

    def cmd_timescale(self, args):
        """timescale [n]    - slow-mo / fast-forward (0.1 - 3)"""
        self._num("timescale", args, "timescale", 0.1, 3.0)

    def cmd_zoom(self, args):
        """zoom [n]         - scope zoom (2 - 8)"""
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
        """tp x y           - teleport (see 'pos' for where you are)"""
        self.player.teleport(float(args[0]), float(args[1]))
        self.console.say("teleported")

    def cmd_pos(self, args):
        """pos              - show your position and the map size"""
        p = self.player
        self.console.say("x=%d y=%d   map '%s' is %dx%d" % (
            p.rect.x, p.rect.y, MAPS[self.map_idx]["name"], self.world_w, self.world_h))

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

    # --- maps ---
    def cmd_maps(self, args):
        """maps             - list maps"""
        for i, m in enumerate(MAPS):
            mark = "*" if i == self.map_idx else " "
            self.console.say(" %s %d. %-15s %dx%d" % (mark, i + 1, m["name"], m["w"], m["h"]))

    def cmd_map(self, args):
        """map <n|name>     - load a map (M opens the chooser)"""
        if not args:
            self.open_menu()
            self.console.open = False
            return
        key = " ".join(args).lower()
        idx = None
        if key.isdigit() and 1 <= int(key) <= len(MAPS):
            idx = int(key) - 1
        else:
            for i, m in enumerate(MAPS):
                if key in m["name"].lower():
                    idx = i
                    break
        if idx is None:
            self.console.say("no such map - try 'maps'", RED)
            return
        self.start_map(idx)
        self.console.say("loaded " + MAPS[idx]["name"])

    # --- multiplayer chat ---
    def cmd_name(self, args):
        """name <nick>      - set your chat name (do it before host/join)"""
        if not args:
            self.console.say("your name is " + self.net.name)
            return
        self.net.name = args[0][:16]
        self.console.say("name set to " + self.net.name)

    def cmd_host(self, args):
        """host [port]      - start a chat lobby others can join"""
        port = int(args[0]) if args else DEFAULT_PORT
        try:
            self.net.host(port)
        except OSError as e:
            self.console.say("could not host: %s" % e, RED)
            return
        ip = local_ip()
        self.console.say("hosting on %s:%d" % (ip, port))
        self.console.say("friends join with:  join %s" % ip, YELLOW)
        self.chat.sys("lobby open - press T to chat")

    def cmd_join(self, args):
        """join <ip> [port] - join someone's chat lobby"""
        if not args:
            self.console.say("usage: join <ip> [port]", RED)
            return
        port = int(args[1]) if len(args) > 1 else DEFAULT_PORT
        self.net.join(args[0], port)
        self.console.say("connecting to %s:%d ..." % (args[0], port))

    def cmd_leave(self, args):
        """leave            - leave / close the lobby"""
        self.net.stop()
        self.chat.sys("left the lobby")
        self.console.say("disconnected")

    def cmd_players(self, args):
        """players          - who is in the lobby (host only)"""
        if self.net.mode == "host":
            self.console.say("players: " + ", ".join(self.net.players()))
        elif self.net.mode == "client":
            self.console.say("connected as %s (only the host sees the list)" % self.net.name)
        else:
            self.console.say("not in a lobby", RED)

    def cmd_say(self, args):
        """say <text>       - send a chat message"""
        self.send_chat(" ".join(args))

    # --- update timer ---
    def cmd_nextupdate(self, args):
        """nextupdate [2h30m | 2026-12-01 18:00 | off] - set/show update countdown"""
        if not args:
            self.console.say(self.update_timer_text()[0] or "no update timer set")
            return
        s = " ".join(args).strip().lower()
        if s in ("off", "none"):
            self.update_at = None
            self.console.say("update timer removed")
            return
        compact = s.replace(" ", "")
        m = re.fullmatch(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", compact)
        if compact.isdigit():  # bare number = minutes
            self.update_at = datetime.now() + timedelta(minutes=int(compact))
        elif m and any(m.groups()):
            d, h, mi, sec = (int(x or 0) for x in m.groups())
            self.update_at = datetime.now() + timedelta(days=d, hours=h, minutes=mi, seconds=sec)
        else:
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    self.update_at = datetime.strptime(s, fmt)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError("use e.g. 90m, 2h30m, 1d, or 2026-12-01 18:00")
        self.console.say(self.update_timer_text()[0], CYAN)

    def cmd_quit(self, args):
        """quit             - exit the game"""
        self.quit()

    def quit(self):
        self.net.stop()
        pygame.quit()
        sys.exit()

    # ----- update --------------------------------------------------------- #
    def update(self, dt):
        p = self.player
        keys = NoKeys() if self.chat.open else pygame.key.get_pressed()
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

        tx = max(0, min(self.world_w - W, p.rect.centerx - W / 2))
        ty = max(0, min(self.world_h - H, p.rect.centery - H / 2))
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
            mag = self.shake * float(getattr(self, "s3_shake_scale", 1.0))
            ox, oy = random.uniform(-mag, mag), random.uniform(-mag, mag)
        cx, cy = int(self.cam[0] + ox), int(self.cam[1] + oy)

        s.blit(self.bg, (0, 0))
        for layer, color, r in self.skyline:
            rr = pygame.Rect(r.x - cx * layer, H - r.h - cy * layer * 0.4 + 60, r.w, r.h)
            if -200 < rr.x < W:
                pygame.draw.rect(s, color, rr)

        for plat in self.platforms:
            r = plat.move(-cx, -cy)
            if r.right < 0 or r.left > W or r.bottom < 0 or r.top > H:
                continue
            pygame.draw.rect(s, (38, 46, 70), r)
            pygame.draw.rect(s, self.accent, (r.x, r.y, r.w, 3))

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
        self.draw_overlay()
        pygame.display.flip()

    def draw_overlay(self):
        self.draw_timer()
        self.chat.draw(self.screen)
        self.console.draw(self.screen)

    def draw_timer(self):
        text, color = self.update_timer_text()
        if not text:
            return
        img = self.font.render(text, True, color)
        box = pygame.Surface((img.get_width() + 24, 30), pygame.SRCALPHA)
        box.fill((0, 0, 0, 150))
        x = W // 2 - box.get_width() // 2
        self.screen.blit(box, (x, 14))
        pygame.draw.rect(self.screen, color, (x, 14, box.get_width(), 30), 1)
        self.screen.blit(img, (x + 12, 19))

    def draw_player(self, cx, cy):
        p = self.player
        r = p.rect.move(-cx, -cy)
        if p.hp <= 0:
            pygame.draw.rect(self.screen, (60, 60, 70), (r.x - 10, r.bottom - 14, 46, 14))
            return
        pygame.draw.rect(self.screen, (60, 190, 230), r)
        pygame.draw.rect(self.screen, (230, 240, 255), (r.x + 3, r.y, r.w - 6, 13))
        ang = self.aim_angle()
        gx, gy = self.gun_origin()
        o = (gx - cx, gy - cy)
        tip = (o[0] + math.cos(ang) * 52, o[1] + math.sin(ang) * 52)
        pygame.draw.line(self.screen, (25, 25, 35), o, tip, 5)

        if self.scoped():  # laser sight
            end, _ = self.cast(self.gun_origin(), ang)
            pygame.draw.line(self.screen, (255, 40, 40), tip, (end[0] - cx, end[1] - cy), 1)

        name = self.font.render(self.net.name, True, GREEN)
        self.screen.blit(name, (r.centerx - name.get_width() // 2, r.y - 22))

    def draw_enemy(self, e, cx, cy):
        r = e.rect.move(-cx, -cy)
        if r.right < -50 or r.left > W + 50 or r.bottom < -50 or r.top > H + 50:
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
            pygame.draw.rect(self.screen, GREEN,
                             (r.x - 4, r.y - 12, (r.w + 8) * max(0, e.hp) // e.max_hp, 5))

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

        info = "%s   WAVE %d   SCORE %d   KILLS %d   ENEMIES %d" % (
            MAPS[self.map_idx]["name"], self.wave, self.score, self.kills, len(self.enemies))
        img = self.font.render(info, True, CYAN)
        s.blit(img, (W - img.get_width() - 20, 56))

        tags = [k.upper() for k in ("god", "fly", "noclip", "esp", "infammo") if self.cfg[k]]
        if self.cfg["timescale"] != 1.0:
            tags.append("TIME x%.1f" % self.cfg["timescale"])
        if tags:
            timg = self.font.render("[" + " ".join(tags) + "]", True, GREEN)
            s.blit(timg, (W - 20 - timg.get_width(), 80))

        hint = self.font.render("` console | T chat | M maps | RMB or Q scope | R reload", True, GREY)
        s.blit(hint, (20, H - 28))

        if p.hp <= 0:
            t1 = self.big.render("YOU WERE TERMINATED", True, RED)
            t2 = self.font.render("press ENTER to restart", True, WHITE)
            s.blit(t1, (W // 2 - t1.get_width() // 2, H // 2 - 40))
            s.blit(t2, (W // 2 - t2.get_width() // 2, H // 2 + 20))

    # ----- map chooser ----------------------------------------------------- #
    def card_rect(self, i):
        return pygame.Rect(35 + i * 310, 190, 280, 350)

    def draw_menu(self):
        s = self.screen
        s.blit(self.menu_bg, (0, 0))
        title = self.big.render("SNIPER//NET", True, GREEN)
        s.blit(title, (W // 2 - title.get_width() // 2, 70))
        sub = self.font.render("v%s  -  choose your map" % VERSION, True, GREY)
        s.blit(sub, (W // 2 - sub.get_width() // 2, 130))

        for i, m in enumerate(MAPS):
            r = self.card_rect(i)
            sel = i == self.menu_sel
            card = pygame.Surface(r.size, pygame.SRCALPHA)
            card.fill((10, 14, 24, 215 if sel else 160))
            s.blit(card, r.topleft)
            pygame.draw.rect(s, m["accent"] if sel else (60, 70, 90), r, 3 if sel else 1)
            s.blit(self.thumbs[i], (r.x + 10, r.y + 10))
            s.blit(self.med.render(m["name"], True, WHITE), (r.x + 12, r.y + 172))
            for j, line in enumerate(m["desc"].split("\n")):
                s.blit(self.font.render(line, True, GREY), (r.x + 12, r.y + 212 + j * 22))
            s.blit(self.font.render("%d x %d" % (m["w"], m["h"]), True, m["accent"]),
                   (r.x + 12, r.y + 300))

        foot = "LEFT/RIGHT choose  |  ENTER or click to play  |  ` console  |  T chat"
        if self.started:
            foot += "  |  ESC resume"
        img = self.font.render(foot, True, GREY)
        s.blit(img, (W // 2 - img.get_width() // 2, H - 90))
        self.draw_overlay()
        pygame.display.flip()

    def menu_key(self, ev):
        if ev.key in (pygame.K_LEFT, pygame.K_a, pygame.K_UP):
            self.menu_sel = (self.menu_sel - 1) % len(MAPS)
        elif ev.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_DOWN):
            self.menu_sel = (self.menu_sel + 1) % len(MAPS)
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.start_map(self.menu_sel)
        elif ev.key == pygame.K_ESCAPE:
            if self.started:
                self.state = "play"
                pygame.mouse.set_visible(False)
            else:
                self.quit()
        elif pygame.K_1 <= ev.key <= pygame.K_9 and ev.key - pygame.K_1 < len(MAPS):
            self.start_map(ev.key - pygame.K_1)

    def menu_mouse(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            for i in range(len(MAPS)):
                if self.card_rect(i).collidepoint(ev.pos):
                    self.menu_sel = i
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i in range(len(MAPS)):
                if self.card_rect(i).collidepoint(ev.pos):
                    self.start_map(i)

    # ----- main loop ------------------------------------------------------ #
    def handle_event(self, ev):
        if ev.type == pygame.QUIT:
            self.quit()
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_F11 or (ev.key == pygame.K_RETURN and ev.mod & pygame.KMOD_ALT):
                pygame.display.toggle_fullscreen()  # F11 or Alt+Enter
                return
            if self.chat.open:
                self.chat.handle_key(ev)
                return
            if ev.key in (pygame.K_BACKQUOTE, pygame.K_F1):
                self.console.toggle()
                return
            if self.console.open:
                self.console.handle_key(ev)
                return
            if ev.key == pygame.K_t:
                self.chat.open_box()
                return
            if self.state == "menu":
                self.menu_key(ev)
                return
            if ev.key == pygame.K_ESCAPE:
                self.quit()
            elif ev.key == pygame.K_m:
                self.open_menu()
            elif ev.key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
                self.player.jump_buf = 0.12
            elif ev.key == pygame.K_r:
                self.reload()
            elif ev.key == pygame.K_RETURN and self.player.hp <= 0:
                self.reset()
            return
        if self.console.open or self.chat.open:
            return
        if self.state == "menu":
            self.menu_mouse(ev)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.shoot()
        elif ev.type == pygame.MOUSEWHEEL and self.scoped():
            self.cfg["zoom"] = max(2.0, min(8.0, self.cfg["zoom"] + ev.y * 0.5))

    def run(self, max_frames=None):
        frames = 0
        while max_frames is None or frames < max_frames:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for ev in pygame.event.get():
                self.handle_event(ev)
            self.poll_net()
            self.console.update(dt)
            if self.state == "play":
                if not self.console.open:  # game pauses while the console is open
                    self.time += dt
                    self.update(dt * self.cfg["timescale"])
                self.draw()
            else:
                self.draw_menu()
            frames += 1


# =========================== SEASON 3 UPDATE ==============================
# Local profile and progression are stored beside this script in season3_save.json.
import os as _s3_os
import time as _s3_time

S3_SAVE_FILE = _s3_os.path.join(_s3_os.path.dirname(_s3_os.path.abspath(__file__)), "season3_save.json")
S3_WEAPONS = [
    {"name":"Sniper", "damage":150, "cooldown":0.90, "spread":0.006, "mag":5, "reserve":30, "reload":1.8, "color":YELLOW},
    {"name":"Rifle", "damage":34, "cooldown":0.22, "spread":0.035, "mag":24, "reserve":120, "reload":1.5, "color":CYAN},
    {"name":"Burst Rifle", "damage":28, "cooldown":0.42, "spread":0.025, "mag":18, "reserve":90, "reload":1.6, "color":GREEN},
    {"name":"Shotgun", "damage":24, "cooldown":0.75, "spread":0.13, "mag":6, "reserve":36, "reload":1.9, "color":(255,170,90)},
    {"name":"SMG", "damage":18, "cooldown":0.10, "spread":0.07, "mag":32, "reserve":160, "reload":1.4, "color":(255,110,190)},
    {"name":"Molotov", "damage":95, "cooldown":1.25, "spread":0.015, "mag":3, "reserve":15, "reload":2.0, "color":(255,85,30)},
]
S3_RANKS = [(0,"Bronze"),(500,"Silver"),(1500,"Gold"),(3500,"Platinum"),(7000,"Diamond"),(12000,"Master")]
S3_REWARDS = [
    (0,"Skin Ticket"),(100,"Goodie Bag"),(250,"Neon Wrap"),(450,"Key Skin: Glitch"),
    (700,"Fist Skin: Ember"),(1000,"Skin Ticket"),(1400,"Arch Molotov"),
    (1850,"Goodie Bag"),(2400,"2000 Visits Skin"),(3000,"Season 3 Champion Wrap")
]

def _s3_default_profile():
    return {"xp":0,"skin_tickets":0,"goodie_bags":0,"unlocked":["Default"],"equipped":"Default",
            "claimed":[],"kills":0,"matches":0,"fake_online_seed":random.randint(120,680)}

def _s3_load_profile():
    try:
        with open(S3_SAVE_FILE,"r",encoding="utf-8") as f:
            data=json.load(f)
        base=_s3_default_profile(); base.update(data)
        return base
    except (OSError,ValueError,TypeError):
        return _s3_default_profile()

def _s3_save_profile(g):
    try:
        with open(S3_SAVE_FILE,"w",encoding="utf-8") as f:
            json.dump(g.s3_profile,f,indent=2)
    except OSError:
        pass

def _s3_rank(xp):
    result="Bronze"
    for threshold,name in S3_RANKS:
        if xp >= threshold: result=name
    return result

def _s3_award(g, amount, reason="XP"):
    old_rank=_s3_rank(g.s3_profile.get("xp",0))
    g.s3_profile["xp"] = max(0,int(g.s3_profile.get("xp",0))+int(amount))
    new_rank=_s3_rank(g.s3_profile["xp"])
    if new_rank != old_rank:
        g.float_text("RANK UP: "+new_rank,(g.player.cx,g.player.rect.y-65),CYAN)
    _s3_claim_rewards(g)
    _s3_save_profile(g)

def _s3_claim_rewards(g):
    p=g.s3_profile
    claimed=set(p.get("claimed",[]))
    for i,(threshold,reward) in enumerate(S3_REWARDS):
        if p.get("xp",0)>=threshold and i not in claimed:
            if reward=="Skin Ticket": p["skin_tickets"]=p.get("skin_tickets",0)+1
            elif reward=="Goodie Bag": p["goodie_bags"]=p.get("goodie_bags",0)+1
            else:
                if reward not in p["unlocked"]: p["unlocked"].append(reward)
            claimed.add(i)
    p["claimed"]=sorted(claimed)

def _s3_init_wrapper(original):
    def wrapped(self,*args,**kwargs):
        original(self,*args,**kwargs)
        self.s3_profile=_s3_load_profile()
        self.s3_weapon=0
        self.s3_return_state="play"
        self.s3_message="Season 3 is live!  B: Battle Pass  I: Armory  U: Skins"
        self.s3_message_until=_s3_time.time()+7
        self.s3_online_display=120 + (self.s3_profile.get("fake_online_seed",250)%561)
        _s3_claim_rewards(self)
        _s3_save_profile(self)
    return wrapped
Game.__init__ = _s3_init_wrapper(Game.__init__)

_s3_original_reset=Game.reset
def _s3_reset(self,*a,**kw):
    result=_s3_original_reset(self,*a,**kw)
    if hasattr(self,"s3_weapon"):
        w=S3_WEAPONS[self.s3_weapon]
        self.player.mag_size=w["mag"]; self.player.mag=w["mag"]; self.player.reserve=w["reserve"]
    return result
Game.reset=_s3_reset

_s3_original_load_map=Game.load_map
def _s3_load_map(self,idx,*a,**kw):
    result=_s3_original_load_map(self,idx,*a,**kw)
    if hasattr(self,"s3_weapon"):
        w=S3_WEAPONS[self.s3_weapon]
        self.player.mag_size=w["mag"]; self.player.mag=w["mag"]; self.player.reserve=w["reserve"]
    return result
Game.load_map=_s3_load_map

def _s3_shoot(self):
    p=self.player; w=S3_WEAPONS[self.s3_weapon]
    if p.hp<=0 or p.cooldown>0 or p.reload_t>0: return
    if p.mag<=0:
        self.float_text("RELOAD! (R)",(p.rect.centerx,p.rect.y-20),RED); return
    if not self.cfg["infammo"]: p.mag-=1
    p.cooldown=w["cooldown"]
    scoped=self.scoped()
    steady=scoped and bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
    spread=(0.0003 if steady else (0.003 if scoped else w["spread"]))
    origin=self.gun_origin(); ang=self.aim_angle()
    shots=6 if self.s3_weapon==3 else (3 if self.s3_weapon==2 else 1)
    hit_any=False
    for _ in range(shots):
        end,hit=self.cast(origin,ang+random.uniform(-spread,spread))
        self.tracers.append([origin,end,0.22,w["color"]])
        if hit:
            e,head=hit; hit_any=True
            damage=w["damage"]*(1.5 if head else 1)
            e.hp-=damage; e.flash=0.15
            self.burst(end,RED if head else w["color"],8,160)
            if e.hp<=0 and e in self.enemies:
                self.enemies.remove(e); self.kills+=1; self.score+=150 if head else 100
                self.s3_profile["kills"]=self.s3_profile.get("kills",0)+1
                _s3_award(self,150 if head else 100,"kill")
                self.burst(e.rect.center,(255,200,80),24,280)
                self.float_text("HEADSHOT!" if head else "+100",(e.rect.centerx,e.rect.y-10),YELLOW)
    if self.s3_weapon==5:
        # Molotov impact: a visible blast plus short-range area damage.
        self.burst(end,(255,85,20),42,360)
        for e in list(self.enemies):
            if math.hypot(e.rect.centerx-end[0],e.rect.centery-end[1])<150:
                e.hp-=w["damage"]
                if e.hp<=0 and e in self.enemies:
                    self.enemies.remove(e); self.kills+=1; self.score+=100
                    self.s3_profile["kills"]=self.s3_profile.get("kills",0)+1
                    _s3_award(self,100,"molotov")
    if not hit_any and self.s3_weapon!=5: self.burst(end,GREY,4,100)
    self.shake=max(self.shake,5 if self.s3_weapon in (1,2,4) else 7)
Game.shoot=_s3_shoot

def _s3_reload(self):
    p=self.player; w=S3_WEAPONS[self.s3_weapon]
    if p.reload_t<=0 and p.mag<p.mag_size and p.reserve>0 and p.hp>0: p.reload_t=w["reload"]
Game.reload=_s3_reload

_s3_original_update=Game.update
def _s3_update(self,dt):
    _s3_original_update(self,dt)
    if self.state=="play" and hasattr(self,"s3_profile") and getattr(self, "s3_mode", "") != "range":
        # Small survival XP; kills award additional XP.
        self.s3_xp_tick=getattr(self,"s3_xp_tick",0)+dt
        if self.s3_xp_tick>=10:
            self.s3_xp_tick=0; _s3_award(self,10,"survival")
Game.update=_s3_update; _s3_original_draw_hud = Game.draw_hud

def _s3_draw_hud(self):
    _s3_original_draw_hud(self)
    if hasattr(self,"s3_profile"):
        s=self.screen; w=S3_WEAPONS[self.s3_weapon]
        label=self.font.render("WEAPON: %s | RANK: %s | XP: %d | TICKETS: %d" %
            (w["name"],_s3_rank(self.s3_profile.get("xp",0)),self.s3_profile.get("xp",0),self.s3_profile.get("skin_tickets",0)),True,w["color"])
        s.blit(label,(20,96))
        if _s3_time.time()<getattr(self,"s3_message_until",0):
            msg=self.font.render(self.s3_message,True,YELLOW); s.blit(msg,(20,122))
        online=self.font.render("COMMUNITY ONLINE: %d (DEMO COUNTER)" % self.s3_online_display,True,GREY)
        s.blit(online,(W-310, H-28))
Game.draw_hud=_s3_draw_hud

def _s3_panel(self,title,lines,accent=CYAN):
    s=self.screen
    shade=pygame.Surface((W,H),pygame.SRCALPHA); shade.fill((3,7,18,225)); s.blit(shade,(0,0))
    heading=self.big.render(title,True,accent); s.blit(heading,(W//2-heading.get_width()//2,70))
    y=145
    for line in lines:
        img=self.font.render(line,True,WHITE if not line.startswith("[LOCKED]") else GREY)
        s.blit(img,(100,y)); y+=32
    foot=self.font.render("ESC or BACKSPACE: return to game/menu | Changes save automatically",True,GREY)
    s.blit(foot,(W//2-foot.get_width()//2,H-55))
    pygame.display.flip()
Game._s3_panel = _s3_panel

def _s3_card_rect(self,i):
    return pygame.Rect(30+(i%3)*410,145+(i//3)*270,380,235)
Game.card_rect=_s3_card_rect

def _s3_draw_menu(self):
    s=self.screen
    s.blit(self.menu_bg,(0,0))
    title=self.big.render("SNIPER//NET — SEASON 3",True,GREEN)
    s.blit(title,(W//2-title.get_width()//2,18))
    subtitle=self.font.render("Choose a map | B Battle Pass | I Armory | U Skins",True,GREY)
    s.blit(subtitle,(W//2-subtitle.get_width()//2,70))
    for i,m in enumerate(MAPS):
        r=self.card_rect(i); selected=i==self.menu_sel
        pygame.draw.rect(s,(10,14,24),r)
        pygame.draw.rect(s,m["accent"] if selected else (60,70,90),r,3 if selected else 1)
        thumb=self.thumbs[i]
        s.blit(thumb,(r.x+8,r.y+8))
        s.blit(self.med.render(m["name"],True,WHITE),(r.x+8,r.y+163))
        first=m["desc"].split("\n")[0]
        s.blit(self.font.render(first,True,GREY),(r.x+8,r.y+194))
        dims=self.font.render("%d x %d"%(m["w"],m["h"]),True,m["accent"])
        s.blit(dims,(r.right-dims.get_width()-8,r.y+194))
    txt="XP %d | Rank %s | Tickets %d | Community online: %d (demo counter)" % (self.s3_profile.get("xp",0),_s3_rank(self.s3_profile.get("xp",0)),self.s3_profile.get("skin_tickets",0),self.s3_online_display)
    img=self.font.render(txt,True,YELLOW); s.blit(img,(W//2-img.get_width()//2,H-38))
    self.draw_overlay(); pygame.display.flip()
Game.draw_menu=_s3_draw_menu

_s3_original_handle_event = Game.handle_event
def _s3_handle_event(self,ev):
    if ev.type==pygame.KEYDOWN and hasattr(self,"s3_profile"):
        if self.state in ("battlepass","armory","skins"):
            if ev.key in (pygame.K_ESCAPE,pygame.K_BACKSPACE):
                self.state=self.s3_return_state
                pygame.mouse.set_visible(self.state=="menu")
            elif self.state=="armory" and pygame.K_1<=ev.key<=pygame.K_6:
                self.s3_weapon=ev.key-pygame.K_1
                w=S3_WEAPONS[self.s3_weapon]
                self.player.mag_size=w["mag"]; self.player.mag=min(self.player.mag,w["mag"]); self.player.reserve=max(self.player.reserve,w["reserve"])
                self.s3_message="Equipped "+w["name"]; self.s3_message_until=_s3_time.time()+3
            elif self.state=="skins" and ev.key==pygame.K_RETURN:
                p=self.s3_profile
                if p.get("skin_tickets",0)>0:
                    p["skin_tickets"]-=1
                    skin=random.choice(["Neon Phantom","Arch Molotov","Ember Fists","Glitch Key","2000 Visits Skin"])
                    if skin not in p["unlocked"]: p["unlocked"].append(skin)
                    p["equipped"]=skin; self.s3_message="Unlocked: "+skin; self.s3_message_until=_s3_time.time()+4
                    _s3_save_profile(self)
                else:
                    self.s3_message="You need a Skin Ticket. Earn one in the Battle Pass."; self.s3_message_until=_s3_time.time()+4
            return
        if ev.key in (pygame.K_b,pygame.K_i,pygame.K_u):
            self.s3_return_state=self.state
            self.state={pygame.K_b:"battlepass",pygame.K_i:"armory",pygame.K_u:"skins"}[ev.key]
            pygame.mouse.set_visible(True)
            return
        if self.state=="play" and pygame.K_1<=ev.key<=pygame.K_6:
            self.s3_weapon=ev.key-pygame.K_1
            w=S3_WEAPONS[self.s3_weapon]
            self.player.mag_size=w["mag"]; self.player.mag=min(self.player.mag,w["mag"]); self.player.reserve=max(self.player.reserve,w["reserve"])
            self.s3_message="Equipped "+w["name"]; self.s3_message_until=_s3_time.time()+2
    _s3_original_handle_event(self,ev)
Game.handle_event=_s3_handle_event

_s3_original_run=Game.run
def _s3_run(self,max_frames=None):
    # The original run loop is retained; custom states draw progression screens instead of gameplay.
    frames=0
    while max_frames is None or frames<max_frames:
        dt=min(self.clock.tick(FPS)/1000.0,0.05)
        for ev in pygame.event.get(): self.handle_event(ev)
        self.poll_net(); self.console.update(dt)
        if self.state=="battlepass":
            p=self.s3_profile; lines=["SEASON 3 BATTLE PASS — XP %d / NEXT REWARD"%p.get("xp",0),"Rank: "+_s3_rank(p.get("xp",0)),"Skin Tickets: %d   Goodie Bags: %d"%(p.get("skin_tickets",0),p.get("goodie_bags",0)),""]
            for i,(threshold,reward) in enumerate(S3_REWARDS):
                status="CLAIMED/UNLOCKED" if i in p.get("claimed",[]) else ("AVAILABLE" if p.get("xp",0)>=threshold else "LOCKED")
                lines.append("[%s] Level %02d — %s — %d XP"%(status,i+1,reward,threshold))
            self._s3_panel("SEASON 3 // BATTLE PASS",lines,YELLOW)
        elif self.state=="armory":
            lines=["Choose a weapon with keys 1–6:",""]
            for i,w in enumerate(S3_WEAPONS): lines.append("%s %d. %-12s Damage %3d | Mag %2d | Reload %.1fs"%("[EQUIPPED]" if i==self.s3_weapon else "         ",i+1,w["name"],w["damage"],w["mag"],w["reload"]))
            lines += ["","Weapons: Sniper, Rifle, Burst Rifle, Shotgun, SMG, Molotov"]
            self._s3_panel("SEASON 3 // ARMORY",lines)
        elif self.state=="skins":
            p=self.s3_profile; lines=["Skin Tickets: %d"%p.get("skin_tickets",0),"Press ENTER to spend one ticket on a random skin.","Equipped skin: "+p.get("equipped","Default"),"","Unlocked cosmetics:"]+ ["• "+x for x in p.get("unlocked",["Default"]) ]
            lines += ["","Cosmetics include Arch Molotov, 2000 Visits Skin, Ember Fists, Glitch Key and wraps."]
            self._s3_panel("SEASON 3 // SKINS",lines,(255,150,210))
        elif self.state=="play":
            if not self.console.open:
                self.time+=dt; self.update(dt*self.cfg["timescale"])
            self.draw()
        else: self.draw_menu()
        frames+=1
Game.run=_s3_run



# Season 3 Reloaded: playable menu systems built on the existing Pygame game.
S3_EXTRA_ITEMS = [
    {"name":"Alien Dual Pistols","type":"weapon","price":900,"desc":"Dual energy pistols; no firing cooldown (demo)."},
    {"name":"Alien Rifle","type":"weapon","price":1200,"desc":"Energy rifle with controlled fire rate."},
    {"name":"Flare Gun","type":"weapon","price":500,"desc":"Signal flare sidearm."},
    {"name":"Medkit","type":"gear","price":350,"desc":"Practice gear item."},
    {"name":"Karambit - Neon","type":"knife skin","price":700,"desc":"Original curved knife cosmetic."},
    {"name":"Balisong - Circuit","type":"knife skin","price":700,"desc":"Original butterfly-knife cosmetic."},
    {"name":"Energy Bundle","type":"bundle","price":1500,"desc":"Alien-themed cosmetic bundle."},
    {"name":"Skin Case","type":"case","price":400,"desc":"Unlocks an original cosmetic."},
    {"name":"Weapon Charm - Orbit","type":"charm","price":250,"desc":"A cosmetic charm preview item."},
    {"name":"Wave Emote","type":"emote","price":200,"desc":"A lobby emote."},
]

def _s3_wallet_init(original):
    def wrapped(self,*a,**kw):
        original(self,*a,**kw)
        p=self.s3_profile
        p.setdefault('coins',1500); p.setdefault('inventory',['Default']); p.setdefault('platform','PC')
        p.setdefault('equipped_skin','Default'); p.setdefault('mobile_console',False)
        self.s3_page='home'; self.s3_shop_index=0; self.s3_vote_index=0
        self.s3_notice='Season 3 Reloaded | H: Lobby  J: Shop  K: Backpack  R: Range  V: Map vote  F2: Mobile console'
        self.s3_notice_until=_s3_time.time()+8
        _s3_save_profile(self)
    return wrapped
Game.__init__=_s3_wallet_init(Game.__init__)

_s3_prev_event=Game.handle_event
def _s3_extended_event(self,ev):
    p=getattr(self,'s3_profile',{})
    if ev.type==pygame.KEYDOWN and hasattr(self,'s3_profile'):
        pages={'h':'lobby','j':'shop','k':'backpack','r':'range','v':'vote','g':'weapons','o':'settings'}
        if ev.key==pygame.K_F2:
            p['mobile_console']=not p.get('mobile_console',False); _s3_save_profile(self)
            self.s3_message='Mobile console '+('enabled' if p['mobile_console'] else 'disabled'); self.s3_message_until=_s3_time.time()+3
            return
        if self.state in ('lobby','shop','backpack','range','vote','weapons','settings','mobileconsole'):
            if ev.key in (pygame.K_ESCAPE,pygame.K_BACKSPACE):
                self.state='menu'; pygame.mouse.set_visible(True); return
            if self.state=='shop':
                if ev.key in (pygame.K_DOWN,pygame.K_RIGHT): self.s3_shop_index=(self.s3_shop_index+1)%len(S3_EXTRA_ITEMS)
                elif ev.key in (pygame.K_UP,pygame.K_LEFT): self.s3_shop_index=(self.s3_shop_index-1)%len(S3_EXTRA_ITEMS)
                elif ev.key in (pygame.K_RETURN,pygame.K_SPACE):
                    item=S3_EXTRA_ITEMS[self.s3_shop_index]
                    if item['name'] in p['inventory']: self.s3_message='Already owned: '+item['name']
                    elif p['coins']<item['price']: self.s3_message='Not enough coins for '+item['name']
                    else:
                        p['coins']-=item['price']; p['inventory'].append(item['name']); self.s3_message='Purchased '+item['name']; _s3_save_profile(self)
                    self.s3_message_until=_s3_time.time()+3
                return
            if self.state=='backpack':
                if ev.key in (pygame.K_DOWN,pygame.K_RIGHT): self.s3_shop_index=(self.s3_shop_index+1)%max(1,len(p['inventory']))
                elif ev.key in (pygame.K_UP,pygame.K_LEFT): self.s3_shop_index=(self.s3_shop_index-1)%max(1,len(p['inventory']))
                elif ev.key in (pygame.K_RETURN,pygame.K_SPACE) and p['inventory']:
                    p['equipped_skin']=p['inventory'][self.s3_shop_index]; _s3_save_profile(self)
                    self.s3_message='Equipped '+p['equipped_skin']; self.s3_message_until=_s3_time.time()+3
                return
            if self.state=='vote':
                if ev.key in (pygame.K_LEFT,pygame.K_UP): self.s3_vote_index=(self.s3_vote_index-1)%len(MAPS)
                elif ev.key in (pygame.K_RIGHT,pygame.K_DOWN): self.s3_vote_index=(self.s3_vote_index+1)%len(MAPS)
                elif ev.key in (pygame.K_RETURN,pygame.K_SPACE): self.menu_sel=self.s3_vote_index; self.start_map(self.menu_sel); p['matches']=p.get('matches',0)+1; _s3_save_profile(self)
                return
            if self.state=='range':
                if ev.key==pygame.K_RETURN: self.start_map(self.menu_sel)
                return
            return
        if ev.key in (pygame.K_h,pygame.K_j,pygame.K_k,pygame.K_r,pygame.K_v,pygame.K_g,pygame.K_o):
            self.state=pages[pygame.key.name(ev.key)]; pygame.mouse.set_visible(True); self.s3_shop_index=0; return
    _s3_prev_event(self,ev)
Game.handle_event=_s3_extended_event

_s3_prev_draw_menu=Game.draw_menu
def _s3_rich_menu(self):
    _s3_prev_draw_menu(self)
    s=self.screen
    p=self.s3_profile
    # footer navigation bar drawn after the original map cards
    pygame.draw.rect(s,(4,8,18),(0,H-76,W,38))
    nav='H LOBBY   J SHOP   K BACKPACK   G WEAPONS   R RANGE   V MAP VOTE   O SETTINGS   F2 MOBILE CONSOLE'
    s.blit(self.font.render(nav,True,CYAN),(24,H-70))
    s.blit(self.font.render('LEVEL %d  |  %s  |  COINS %d  |  SKIN %s  |  %s'%(min(100,1+p.get('xp',0)//100),_s3_rank(p.get('xp',0)),p.get('coins',0),p.get('equipped_skin','Default'),p.get('platform','PC')),True,WHITE),(24,H-42))
Game.draw_menu=_s3_rich_menu

def _s3_draw_extra(self):
    p=self.s3_profile; s=self.screen
    s.fill((5,9,20))
    pygame.draw.rect(s,(12,22,40),(45,35,W-90,H-70),border_radius=14)
    title={'lobby':'SNIPER//NET // PLAYER LOBBY','shop':'FIELD SHOP // SEASON 3','backpack':'BACKPACK // YOUR INVENTORY','range':'SHOOTING RANGE','vote':'VOTE FOR THE NEXT MAP','weapons':'WEAPON LOADOUT','settings':'SETTINGS & PLATFORM','mobileconsole':'MOBILE DEVELOPER CONSOLE'}[self.state]
    s.blit(self.big.render(title,True,CYAN),(75,58))
    lines=[]
    if self.state=='lobby':
        lines=['LEVEL %d / 100'%min(100,1+p.get('xp',0)//100),'RANK: '+_s3_rank(p.get('xp',0)),'XP: %d  |  COINS: %d'%(p.get('xp',0),p.get('coins',0)),'Equipped cosmetic: '+p.get('equipped_skin','Default'),'Platform detected: '+p.get('platform','PC'),'','[PLAY] Use V to vote for a map, then choose a map with arrows and Enter.','[RANGE] Press R to enter practice range.','[SHOP] Press J to buy unlocks with earned demo coins.','[BACKPACK] Press K to equip owned items.']
    elif self.state=='shop':
        lines=['Coins: %d'%p.get('coins',0),'Use UP/DOWN to browse; ENTER to purchase.','']
        for i,it in enumerate(S3_EXTRA_ITEMS): lines.append(('▶ ' if i==self.s3_shop_index else '  ')+('%s — %d coins'%(it['name'],it['price']))+('  [OWNED]' if it['name'] in p['inventory'] else ''))
        lines+=['','Demo purchases are local only; no real-money payment is connected.']
    elif self.state=='backpack':
        lines=['Use UP/DOWN then ENTER to equip selected item.','Equipped: '+p.get('equipped_skin','Default'),'']
        for i,it in enumerate(p['inventory']): lines.append(('▶ ' if i==self.s3_shop_index%max(1,len(p['inventory'])) else '  ')+it)
    elif self.state=='range':
        lines=['Practice on The Pit with stationary and moving targets.','Hits, misses, and accuracy are tracked. Reset clears the range.','No match XP is awarded here.','Press START PRACTICE. Esc pauses.']
    elif self.state=='vote':
        lines=['Arrow keys to select; ENTER to start on the selected map.','']
        for i,m in enumerate(MAPS): lines.append(('▶ ' if i==self.s3_vote_index else '  ')+m['name']+' — '+m['desc'].split('\n')[0])
        lines+=['','Voting is local in this build; shared online votes need a server.']
    elif self.state=='weapons':
        lines=['Starting loadout: AR/Rifle, handgun, fists, grenades.','Season 3 playable weapon prototypes:']
        lines += [('%d. %s — %d damage, %d-round magazine'%(i+1,w['name'],w['damage'],w['mag'])) for i,w in enumerate(S3_WEAPONS)]
        lines += ['','Equip a weapon with its button. Alien weapons fire only after their cooldown.','Flare Gun, Grenade, and Fists are combat weapons. Gifting is unavailable without a server.']
    elif self.state=='settings':
        lines=['Mouse sensitivity and screen shake apply in play and are saved locally.','Fullscreen uses the button on this screen.','There is no audio asset pack, so there is no volume control yet.','Mobile touch controls are not in this desktop build.','Gifting is unavailable until an authenticated server exists.']
    else:
        lines=['Mobile console toggle: '+('ON' if p.get('mobile_console') else 'OFF'),'Console status: UI prototype; command execution is not connected.','F2 toggles visibility setting.','This does not make the desktop Pygame game run on a phone.']
    y=125
    for line in lines:
        col=YELLOW if line.startswith('▶') else (GREY if '[OWNED]' in line or 'not yet' in line.lower() else WHITE)
        s.blit(self.font.render(line,True,col),(90,y)); y+=28
    if _s3_time.time()<getattr(self,'s3_message_until',0): s.blit(self.font.render(self.s3_message,True,GREEN),(90,H-100))
    s.blit(self.font.render('ESC/BACKSPACE: main menu  |  UP/DOWN: browse  |  ENTER: select',True,GREY),(90,H-75))
    pygame.display.flip()

_s3_prev_run=Game.run
def _s3_full_run(self,max_frames=None):
    frames=0
    while max_frames is None or frames<max_frames:
        dt=min(self.clock.tick(FPS)/1000.0,0.05)
        for ev in pygame.event.get(): self.handle_event(ev)
        self.poll_net(); self.console.update(dt)
        if self.state in ('lobby','shop','backpack','range','vote','weapons','settings','mobileconsole'):
            _s3_draw_extra(self)
        elif self.state=='battlepass':
            p=self.s3_profile; lines=['XP: %d'%p.get('xp',0),'Rank: '+_s3_rank(p.get('xp',0)),'Coins: %d'%p.get('coins',0)] + ['Level %02d — %s — %d XP'%(i+1,reward,threshold) for i,(threshold,reward) in enumerate(S3_REWARDS)]
            self._s3_panel('SEASON 3 // BATTLE PASS',lines,YELLOW)
        elif self.state=='armory':
            lines=['Choose a weapon with keys 1–6:']+['%d. %-12s Damage %3d | Mag %2d | Reload %.1fs'%(i+1,w['name'],w['damage'],w['mag'],w['reload']) for i,w in enumerate(S3_WEAPONS)]
            self._s3_panel('SEASON 3 // ARMORY',lines)
        elif self.state=='skins':
            self._s3_panel('SEASON 3 // SKINS',['Skin Tickets: %d'%self.s3_profile.get('skin_tickets',0),'Equipped: '+self.s3_profile.get('equipped_skin','Default'),'Owned: '+', '.join(self.s3_profile.get('inventory',['Default']))])
        elif self.state=='play':
            if not self.console.open: self.time+=dt; self.update(dt*self.cfg['timescale'])
            self.draw()
        else: self.draw_menu()
        frames+=1
Game.run=_s3_full_run

# === Season 3 gameplay pass: functional sidearms, alien weapons, healing, melee ===
# These are gameplay systems, not menu-only labels. Keys: 7 flare, 8 alien duals,
# 9 alien rifle, X medkit, C knife. Alien gear must be owned in the local shop.
S3_WEAPONS.extend([
    {"name":"Flare Gun", "damage":55, "cooldown":0.85, "spread":0.012, "mag":1, "reserve":8, "reload":1.25, "color":(255,95,70)},
    {"name":"Alien Dual Pistols", "damage":20, "cooldown":0.18, "spread":0.045, "mag":30, "reserve":999, "reload":0.0, "color":(150,255,110), "infinite":True, "kind":"dual"},
    {"name":"Alien Rifle", "damage":42, "cooldown":0.32, "spread":0.018, "mag":30, "reserve":999, "reload":0.0, "color":(100,255,220), "infinite":True, "kind":"hitscan"},
])
_s3_base_shoot = Game.shoot
def _s3_real_shoot(self):
    if not hasattr(self, 's3_weapon') or self.s3_weapon < 6:
        return _s3_base_shoot(self)
    p=self.player; w=S3_WEAPONS[self.s3_weapon]
    if p.hp<=0 or p.cooldown>0 or p.reload_t>0: return
    owned=set(self.s3_profile.get('inventory',[])) | set(self.s3_profile.get('unlocked',[]))
    if self.s3_weapon in (7,8) and w['name'] not in owned:
        self.float_text('LOCKED — buy '+w['name']+' in Shop',(p.cx,p.rect.y-28),RED); return
    if not w.get('infinite') and p.mag<=0:
        self.float_text('RELOAD! (R)',(p.cx,p.rect.y-20),RED); return
    if not w.get('infinite'): p.mag-=1
    p.cooldown=w['cooldown']
    origin=self.gun_origin(); angle=self.aim_angle()
    end,hit=self.cast(origin,angle+random.uniform(-w['spread'],w['spread']))
    self.tracers.append([origin,end,0.30,w['color']])
    if hit:
        e,head=hit; e.hp-=w['damage']*(1.5 if head else 1); e.flash=0.18
        self.burst(end,w['color'],12,220)
        if e.hp<=0 and e in self.enemies:
            self.enemies.remove(e); self.kills+=1; self.score+=100
            self.s3_profile['kills']=self.s3_profile.get('kills',0)+1
            _s3_award(self,150 if head else 100,'kill')
            self.burst(e.rect.center,(255,220,100),22,280)
            self.float_text('HEADSHOT!' if head else '+100 XP',(e.rect.centerx,e.rect.y-12),YELLOW)
    else: self.burst(end,w['color'],5,130)
    self.shake=max(self.shake,4)
Game.shoot=_s3_real_shoot

_s3_base_handle=Game.handle_event
def _s3_gameplay_keys(self,ev):
    if ev.type==pygame.KEYDOWN and hasattr(self,'s3_profile') and self.state=='play' and not self.chat.open and not self.console.open:
        if ev.key==pygame.K_x:
            now=_s3_time.time(); ready=getattr(self,'s3_medkit_ready',0)
            if now < ready: self.float_text('MEDKIT READY IN %ds'%int(ready-now+1),(self.player.cx,self.player.rect.y-25),YELLOW)
            elif self.player.hp>=self.player.max_hp: self.float_text('HEALTH IS FULL',(self.player.cx,self.player.rect.y-25),CYAN)
            else:
                self.player.hp=min(self.player.max_hp,self.player.hp+45); self.s3_medkit_ready=now+12
                self.burst(self.player.rect.center,(70,255,130),18,180); self.float_text('+45 HEALTH',(self.player.cx,self.player.rect.y-25),GREEN)
            return
        if ev.key==pygame.K_c:
            # Short-range knife strike; targets must be close and in front of the player.
            p=self.player; reach=100; facing=1 if pygame.mouse.get_pos()[0] >= W//2 else -1
            victims=[e for e in self.enemies if abs(e.rect.centery-p.rect.centery)<75 and 0 < (e.rect.centerx-p.rect.centerx)*facing < reach]
            if victims:
                e=min(victims,key=lambda q:abs(q.rect.centerx-p.rect.centerx)); e.hp-=65; e.flash=.2
                self.burst(e.rect.center,(255,255,255),10,180)
                if e.hp<=0 and e in self.enemies:
                    self.enemies.remove(e); self.kills+=1; self.score+=100; _s3_award(self,100,'knife kill')
                self.float_text('KNIFE HIT',(e.rect.centerx,e.rect.y-15),WHITE)
            else: self.float_text('KNIFE: get closer and face target',(p.cx,p.rect.y-25),GREY)
            return
        if pygame.K_1<=ev.key<=pygame.K_9:
            idx=ev.key-pygame.K_1
            if idx<len(S3_WEAPONS):
                w=S3_WEAPONS[idx]; owned=set(self.s3_profile.get('inventory',[]))|set(self.s3_profile.get('unlocked',[]))
                if idx in (7,8) and w['name'] not in owned:
                    self.s3_message='LOCKED: buy '+w['name']+' in the shop'; self.s3_message_until=_s3_time.time()+3; return
                self.s3_weapon=idx; self.player.mag_size=w['mag']; self.player.mag=w['mag']; self.player.reserve=w['reserve']
                self.s3_message='EQUIPPED: '+w['name']; self.s3_message_until=_s3_time.time()+2
                return
    return _s3_base_handle(self,ev)
Game.handle_event=_s3_gameplay_keys

_s3_base_hud=Game.draw_hud
def _s3_real_hud(self):
    _s3_base_hud(self)
    if hasattr(self,'s3_weapon'):
        p=self.player; now=_s3_time.time(); w=S3_WEAPONS[self.s3_weapon]
        lines=[('X  MEDKIT  +45 HP  (12s cooldown)',(80,255,130)),('C  KNIFE  close-range melee',WHITE)]
        for i,(txt,col) in enumerate(lines): self.screen.blit(self.font.render(txt,True,col),(20,122+i*22))
        if now < getattr(self,'s3_medkit_ready',0):
            self.screen.blit(self.font.render('MEDKIT: %ds'%int(self.s3_medkit_ready-now+1),True,GREEN),(20,166))
        # Draw a weapon-coloured reticle so weapon choice is visible in combat.
        mx,my=pygame.mouse.get_pos(); pygame.draw.circle(self.screen,w['color'],(mx,my),7,1)
        pygame.draw.line(self.screen,w['color'],(mx-11,my),(mx-4,my),2); pygame.draw.line(self.screen,w['color'],(mx+4,my),(mx+11,my),2)
Game.draw_hud=_s3_real_hud

# ---------------------------------------------------------------------------
# Season 3 UI pass: mouse/touch-friendly buttons. Gameplay navigation and weapon
# selection are click-driven; number keys remain available to the developer console.
# ---------------------------------------------------------------------------
S3_UI_BUTTONS = []

def _s3_weapon_allowed(game, name):
    """Replaced by season3_core.install. Starter guns stay usable if that module fails to load."""
    owned = set(game.s3_profile.get("inventory", [])) | set(game.s3_profile.get("unlocked", []))
    if name in ("Alien Dual Pistols", "Alien Rifle"):
        return name in owned
    return True

def _s3_draw_pause(self):
    self.screen.fill((6, 10, 18))
    label = self.big.render("PAUSED", True, CYAN)
    self.screen.blit(label, (W // 2 - label.get_width() // 2, 160))
    pygame.display.flip()

def _s3_button(self, rect, label, action, *, accent=CYAN, enabled=True, small=False):
    """Draw a consistent clickable button and register its action for this frame."""
    rect = pygame.Rect(rect)
    mouse = pygame.mouse.get_pos()
    hover = rect.collidepoint(mouse)
    fill = (20, 38, 58) if enabled else (20, 22, 28)
    edge = accent if hover and enabled else ((70, 100, 125) if enabled else (55, 60, 68))
    pygame.draw.rect(self.screen, fill, rect, border_radius=8)
    pygame.draw.rect(self.screen, edge, rect, 2, border_radius=8)
    font = self.font if small else self.med
    image = font.render(label, True, WHITE if enabled else GREY)
    self.screen.blit(image, (rect.centerx-image.get_width()//2, rect.centery-image.get_height()//2))
    S3_UI_BUTTONS.append((rect, action, enabled))

def _s3_ui_menu(self):
    # Keep the existing animated/background artwork, then put actual controls on top.
    _s3_draw_menu(self)
    S3_UI_BUTTONS.clear()
    width, height = 154, 42
    labels = [
        ("LOBBY", "lobby"), ("PLAY", "vote"), ("LOADOUT", "weapons"),
        ("SHOP", "shop"), ("BACKPACK", "backpack"), ("RANGE", "range"),
        ("BATTLE PASS", "battlepass"), ("ARMORY", "armory"),
        ("SKINS", "skins"), ("SETTINGS", "settings")]
    columns = 5
    row_width = columns*width + (columns-1)*8
    start_x = (W-row_width)//2
    for index, (label, state) in enumerate(labels):
        row, col = divmod(index, columns)
        x = start_x + col*(width+8)
        y = H-105 + row*46
        _s3_button(self, (x,y,width,40), label, ("state",state), small=True)
    pygame.display.flip()

def _s3_ui_extra(self):
    if self.state == "pause":
        _s3_draw_pause(self)
        return
    _s3_draw_extra(self)
    S3_UI_BUTTONS.clear()
    # Navigation is always available as visible buttons, not memorized key numbers.
    nav = [("LOBBY","lobby"),("PLAY / VOTE","vote"),("LOADOUT","weapons"),
           ("SHOP","shop"),("BACKPACK","backpack"),("RANGE","range"),
           ("SETTINGS","settings"),("BACK","menu")]
    bw, bh, gap = 142, 38, 8
    total = len(nav)*bw + (len(nav)-1)*gap
    x0 = max(8,(W-total)//2)
    for i,(label,state) in enumerate(nav):
        _s3_button(self,(x0+i*(bw+gap),H-48,bw,bh),label,("state",state),small=True)
    if self.state == 'shop':
        # Item cards have direct BUY buttons; no numeric selection is needed.
        for i,item in enumerate(S3_EXTRA_ITEMS):
            col=i%3; row=i//3
            x=70+col*390; y=160+row*95
            if y+70 > H-75: continue
            is_case = item.get("type") == "case"
            owned = (item["name"] in self.s3_profile.get("inventory", [])) and not is_case
            label = ("BUY CASE  %d COINS" % item["price"]) if is_case else ("OWNED" if owned else ("BUY  %d COINS" % item["price"]))
            _s3_button(self,(x+230,y+4,140,38),label,("buy",i),enabled=not owned,small=True,accent=YELLOW)
    elif self.state == 'backpack':
        items=self.s3_profile.get('inventory',[])
        for i,item in enumerate(items):
            col=i%3; row=i//3
            x=70+col*390; y=165+row*72
            if y+42 > H-75: continue
            _s3_button(self,(x+190,y,170,38),'EQUIP',("equip",i),small=True,accent=GREEN)
    elif self.state == 'vote':
        for i,m in enumerate(MAPS):
            col=i%3; row=i//3
            x=70+col*390; y=190+row*100
            if y+48 > H-75: continue
            _s3_button(self,(x+210,y,145,42),'VOTE',( "map",i),accent=m['accent'],small=True)
    elif self.state == 'weapons':
        # Each weapon is a card/button. Locked shop weapons remain visibly locked.
        for i,w in enumerate(S3_WEAPONS):
            col=i%4; row=i//4
            x=55+col*300; y=185+row*88
            if y+48 > H-75: continue
            locked = not _s3_weapon_allowed(self, w["name"])
            _s3_button(self,(x,y,270,44),('LOCKED · '+w['name']) if locked else ('EQUIP · '+w['name']),('weapon',i),enabled=not locked,accent=w['color'],small=True)
    elif self.state == 'range':
        _s3_button(self,(W//2-120, H//2+45, 240, 52),'START PRACTICE',('start_range',),accent=GREEN)
    if getattr(self, "s3_decorate_screen", None):
        self.s3_decorate_screen()
    pygame.display.flip()

def _s3_ui_event(self, ev):
    if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
        # The button registry is rebuilt each rendered frame. Process the topmost
        # matching button, then let the game continue normally if nothing matched.
        for rect, action, enabled in reversed(S3_UI_BUTTONS):
            if enabled and rect.collidepoint(ev.pos):
                kind=action[0]
                if kind=='state':
                    self.state=action[1]
                    if self.state=='menu': pygame.mouse.set_visible(True)
                    else: pygame.mouse.set_visible(True)
                    self.s3_shop_index=0
                elif kind=='buy':
                    item=S3_EXTRA_ITEMS[action[1]]
                    p=self.s3_profile
                    if item['name'] in p.get('inventory',[]):
                        self.s3_message='Already owned: '+item['name']
                    elif p.get('coins',0) < item['price']:
                        self.s3_message='Not enough coins for '+item['name']
                    else:
                        p['coins']-=item['price']; p.setdefault('inventory',[]).append(item['name'])
                        _s3_save_profile(self); self.s3_message='Purchased '+item['name']
                    self.s3_message_until=_s3_time.time()+3
                elif kind=='equip':
                    items=self.s3_profile.get('inventory',[])
                    if 0 <= action[1] < len(items):
                        self.s3_profile['equipped_skin']=items[action[1]]
                        self.s3_profile['equipped']=items[action[1]]
                        _s3_save_profile(self); self.s3_message='Equipped '+items[action[1]]
                        self.s3_message_until=_s3_time.time()+3
                elif kind=='map':
                    self.menu_sel=action[1]; self.s3_vote_index=action[1]
                    self.state='menu'; pygame.mouse.set_visible(True)
                    # The vote chooses the next playable map in this local build.
                elif kind=='weapon':
                    idx=action[1]; w=S3_WEAPONS[idx]
                    self.s3_weapon=idx; self.player.mag_size=w['mag']; self.player.mag=w['mag']; self.player.reserve=w['reserve']
                    self.s3_message='Equipped '+w['name']; self.s3_message_until=_s3_time.time()+3
                elif kind=='start_range':
                    self.state='play'; self.s3_message='PRACTICE RUN — aim and fire at targets'; self.s3_message_until=_s3_time.time()+3
                return
    return _s3_prev_ui_event(self,ev)

_s3_prev_ui_event = Game.handle_event
Game.handle_event = _s3_ui_event

# Replace number-key weapon shortcuts in ordinary gameplay. Console input remains
# untouched, so developer commands can still use numbers when the console is open.
_s3_pre_number_handler = Game.handle_event
def _s3_no_number_weapon_keys(self, ev):
    if (ev.type == pygame.KEYDOWN and getattr(self,'state',None)=='play'
            and not getattr(self.console,'open',False)
            and not getattr(self.chat,'open',False)
            and pygame.K_1 <= ev.key <= pygame.K_9):
        self.s3_message='Choose weapons with the on-screen LOADOUT buttons.'
        self.s3_message_until=_s3_time.time()+2
        return
    return _s3_pre_number_handler(self,ev)
Game.handle_event = _s3_no_number_weapon_keys

# Render button-enhanced screens in the main loop.
def _s3_button_run(self,max_frames=None):
    frames=0
    while max_frames is None or frames<max_frames:
        dt=min(self.clock.tick(FPS)/1000.0,0.05)
        for ev in pygame.event.get(): self.handle_event(ev)
        self.poll_net(); self.console.update(dt)
        if self.state in ('lobby','shop','backpack','range','vote','weapons','settings','mobileconsole','pause'):
            _s3_ui_extra(self)
        elif self.state=='battlepass':
            lines=['XP: %d'%self.s3_profile.get('xp',0),'Rank: '+_s3_rank(self.s3_profile.get('xp',0)),'Coins: %d'%self.s3_profile.get('coins',0)] + ['Level %02d — %s — %d XP'%(i+1,reward,threshold) for i,(threshold,reward) in enumerate(S3_REWARDS)]
            self._s3_panel('SEASON 3 // BATTLE PASS',lines,YELLOW)
            S3_UI_BUTTONS.clear(); _s3_button(self,(W//2-90,H-55,180,38),'BACK TO MENU',('state','menu'),small=True); pygame.display.flip()
        elif self.state=='armory':
            lines=['Choose a weapon using the visible LOADOUT buttons.']+['%-18s Damage %3d | Mag %2d | Reload %.1fs'%(w['name'],w['damage'],w['mag'],w['reload']) for w in S3_WEAPONS]
            self._s3_panel('SEASON 3 // ARMORY',lines)
            S3_UI_BUTTONS.clear()
            for i,w in enumerate(S3_WEAPONS):
                locked = not _s3_weapon_allowed(self, w["name"])
                _s3_button(self,(40+(i%4)*310,180+(i//4)*64,290,42),('LOCKED '+w['name']) if locked else ('EQUIP '+w['name']),('weapon',i),enabled=not locked,accent=w['color'],small=True)
            _s3_button(self,(W//2-90,H-55,180,38),'BACK TO MENU',('state','menu'),small=True); pygame.display.flip()
        elif self.state=='skins':
            self._s3_panel('SEASON 3 // SKINS',['Skin Tickets: %d'%self.s3_profile.get('skin_tickets',0),'Equipped: '+self.s3_profile.get('equipped_skin','Default'),'Owned: '+', '.join(self.s3_profile.get('inventory',['Default']))])
            S3_UI_BUTTONS.clear(); _s3_button(self,(W//2-90,H-55,180,38),'BACK TO MENU',('state','menu'),small=True); pygame.display.flip()
        elif self.state=='play':
            if not self.console.open: self.time+=dt; self.update(dt*self.cfg['timescale'])
            self.draw()
            # Clickable loadout chips in the live HUD. The console keeps its own input.
            S3_UI_BUTTONS.clear()
            for i,w in enumerate(S3_WEAPONS):
                col, row = i % 6, i // 6
                x, y = 8 + col * 212, H - 78 + row * 28
                if y + 24 < H:
                    locked = not _s3_weapon_allowed(self, w["name"])
                    _s3_button(self,(x,y,204,24), w["name"][:16], ('weapon',i), enabled=not locked, accent=w['color'], small=True)
            if getattr(self, "s3_decorate_screen", None):
                self.s3_decorate_screen()
            pygame.display.flip()
        else:
            _s3_ui_menu(self)
        frames+=1
Game.run=_s3_button_run

import season3_core
season3_core.install(sys.modules[__name__])

if __name__ == "__main__":
    _save_override = _s3_os.environ.get("SNIPER_SAVE")
    if _save_override:
        S3_SAVE_FILE = _save_override
    _frame_limit = _s3_os.environ.get("SNIPER_MAX_FRAMES")
    Game().run(int(_frame_limit) if _frame_limit else None)
