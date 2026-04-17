"""
pygame で実装した爆裂魔法エフェクト

操作:
  R キー : やり直し
  ESC    : 終了
"""

import pygame
import math
import random
import sys

try:
    import numpy as _np

    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

pygame.init()

# ── サウンド ──────────────────────────────────────────────
_SOUND_OK = False
if _HAS_NUMPY:
    try:
        _SR = 44100
        pygame.mixer.init(_SR, -16, 2, 512)

        def _stereo(mono):
            s = _np.column_stack([mono, mono])
            return pygame.sndarray.make_sound(s)

        def _snd_hum():
            """詠唱中の低い魔力ハム音"""
            n = int(_SR * 6)
            t = _np.linspace(0, 6, n, False)
            w = (
                _np.sin(2 * _np.pi * 55 * t)
                + 0.5 * _np.sin(2 * _np.pi * 110 * t)
                + 0.25 * _np.sin(2 * _np.pi * 165 * t)
                + 0.12 * _np.sin(2 * _np.pi * 27.5 * t)
            )
            w /= _np.max(_np.abs(w)) + 1e-8
            return _stereo((w * 0.22 * 32767).astype(_np.int16))

        def _snd_charge():
            """詠唱終盤のエネルギー蓄積音（ピッチが上昇するトーン）"""
            n = int(_SR * 0.7)
            t = _np.linspace(0, 0.7, n, False)
            freqs = _np.linspace(90, 1400, n)
            phase = 2 * _np.pi * _np.cumsum(freqs / _SR)
            w = _np.sin(phase)
            rng = _np.random.default_rng(0)
            w = w * 0.75 + rng.uniform(-0.25, 0.25, n) * 0.25
            w *= (t / 0.7) * 0.7
            return _stereo((w * 32767).astype(_np.int16))

        def _snd_explosion():
            """爆発の衝撃音（サブベース＋広帯域ノイズ）"""
            dur = 3.0
            n = int(_SR * dur)
            t = _np.linspace(0, dur, n, False)
            thump = (
                _np.sin(2 * _np.pi * 35 * t) * _np.exp(-t * 1.8)
                + _np.sin(2 * _np.pi * 70 * t) * _np.exp(-t * 2.5) * 0.5
                + _np.sin(2 * _np.pi * 110 * t) * _np.exp(-t * 4) * 0.3
            )
            rng = _np.random.default_rng(1)
            noise = rng.uniform(-1, 1, n)
            noise *= (1 - _np.exp(-t * 80)) * _np.exp(-t * 1.2)
            w = _np.clip(thump * 0.65 + noise * 0.5, -1, 1)
            return _stereo((w * 0.9 * 32767).astype(_np.int16))

        def _snd_crackle():
            """炎のパチパチ音（ループ用）"""
            dur = 5.0
            n = int(_SR * dur)
            rng = _np.random.default_rng(2)
            noise = rng.uniform(-1, 1, n)
            noise = _np.convolve(noise, _np.ones(12) / 12, mode="same")
            noise /= _np.max(_np.abs(noise)) + 1e-8
            return _stereo((noise * 0.28 * 32767).astype(_np.int16))

        snd_hum = _snd_hum()
        snd_charge = _snd_charge()
        snd_explosion = _snd_explosion()
        snd_crackle = _snd_crackle()
        _SOUND_OK = True
    except Exception:
        pass

# ── 定数 ────────────────────────────────────────────────
WIDTH, HEIGHT = 1280, 720
FPS = 60
CENTER_X, CENTER_Y = WIDTH // 2, HEIGHT // 2 + 40
GROUND_Y = HEIGHT - 60  # 仮想地面

# タイムライン（秒）
T_CHANT_END = 4.5  # 詠唱終わり
T_CAST = 5.2  # 「爆裂魔法！！！」の叫び
T_FLASH = 5.5  # 閃光
T_PEAK = 6.5  # 爆発ピーク
T_SUSTAINED = 9.5  # 持続
T_FADE = 12.0  # フェードアウト
T_END = 15.0  # 終了

# 詠唱テキスト (時刻, テキスト)
CHANT = [
    (0.3, "Burn away this fleeting life of mine,"),
    # (1.2, "and bring ruin upon my enemies!"),
    (2.2, "O great conflagration,"),
    # (3.2, "reduce all to ash!"),
    (4.2, "EXPLOSION!!!"),
]

# ── 色 ──────────────────────────────────────────────────
BG_COLOR = (6, 1, 18)
WHITE = (255, 255, 255)
YELLOW = (255, 230, 50)
ORANGE = (255, 140, 0)
RED = (220, 30, 0)
PURPLE = (160, 40, 240)
GOLD = (255, 200, 0)


# ── フォント ─────────────────────────────────────────────
# macOS では pygame.font.SysFont がパスにスペースを含むフォントを
# 読み込めないため、ファイルパスで直接指定する。
_FONT_CANDIDATES = [
    ("/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc", True),
    ("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", False),
    ("/System/Library/Fonts/AppleSDGothicNeo.ttc", None),
    ("C:/Windows/Fonts/msgothic.ttc", None),
    ("C:/Windows/Fonts/meiryo.ttc", None),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", None),
]


def make_font(size, bold=False):
    import os

    for path, is_bold in _FONT_CANDIDATES:
        if not os.path.exists(path):
            continue
        if is_bold is not None and is_bold != bold:
            continue
        try:
            f = pygame.font.Font(path, size)
            f.render("あ", True, WHITE)
            return f
        except Exception:
            pass
    for path, _ in _FONT_CANDIDATES:
        if not os.path.exists(path):
            continue
        try:
            f = pygame.font.Font(path, size)
            f.render("あ", True, WHITE)
            return f
        except Exception:
            pass
    return pygame.font.SysFont(None, size, bold=bold)


font_chant = make_font(34, bold=True)
font_title = make_font(80, bold=True)
font_sub = make_font(38, bold=True)
font_hint = make_font(20)


# ── ユーティリティ ───────────────────────────────────────
def alpha_circle(surface, color_rgb, center, radius, alpha, width=0):
    if radius < 1:
        return
    r = int(radius)
    d = r * 2 + 4
    tmp = pygame.Surface((d, d), pygame.SRCALPHA)
    pygame.draw.circle(
        tmp, (*color_rgb, min(255, max(0, alpha))), (r + 2, r + 2), r, width
    )
    surface.blit(tmp, (center[0] - r - 2, center[1] - r - 2))


def draw_glow(surface, cx, cy, radius, color_rgb, max_alpha=120, steps=10):
    if radius < 1:
        return
    r = int(radius)
    tmp = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    for i in range(steps, 0, -1):
        fr = max(1, int(r * i / steps))
        a = int(max_alpha * (1 - i / steps) * 0.7)
        pygame.draw.circle(tmp, (*color_rgb, a), (r, r), fr)
    surface.blit(tmp, (cx - r, cy - r))


def lerp(a, b, t):
    return a + (b - a) * t


# ── パーティクル基本型 ───────────────────────────────────
class Particle:
    __slots__ = [
        "x",
        "y",
        "vx",
        "vy",
        "rgb",
        "size",
        "life",
        "max_life",
        "gravity",
        "drag",
        "glow",
    ]

    def __init__(
        self, x, y, vx, vy, rgb, size, life, gravity=0.12, drag=0.97, glow=False
    ):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.rgb = rgb
        self.size = float(size)
        self.life = int(life)
        self.max_life = int(life)
        self.gravity = gravity
        self.drag = drag
        self.glow = glow

    def update(self):
        self.vx *= self.drag
        self.vy *= self.drag
        self.vy += self.gravity
        self.x += self.vx
        self.y += self.vy
        self.life -= 1

    @property
    def alive(self):
        return self.life > 0

    def draw(self, surf, ox=0, oy=0):
        ratio = self.life / self.max_life
        alpha = int(255 * ratio)
        s = max(1, int(self.size * ratio))
        x, y = int(self.x + ox), int(self.y + oy)
        if s == 1:
            if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                surf.set_at((x, y), self.rgb)
            return
        if self.glow:
            draw_glow(surf, x, y, s * 2, self.rgb, alpha // 2)
        alpha_circle(surf, self.rgb, (x, y), s, alpha)


# ── 煙 ──────────────────────────────────────────────────
class SmokeParticle:
    def __init__(self, x, y):
        self.x = float(x) + random.uniform(-40, 40)
        self.y = float(y) + random.uniform(-15, 15)
        self.vx = random.uniform(-0.8, 0.8)
        self.vy = random.uniform(-2.2, -0.8)
        self.size = random.uniform(25, 60)
        self.life = random.randint(90, 180)
        self.max_life = self.life
        g = random.randint(45, 90)
        self.rgb = (g + 25, g + 10, g)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.size += 0.5
        self.vx *= 0.993
        self.life -= 1

    @property
    def alive(self):
        return self.life > 0

    def draw(self, surf, ox=0, oy=0):
        ratio = self.life / self.max_life
        alpha = int(90 * ratio)
        s = int(self.size)
        if s < 2:
            return
        alpha_circle(surf, self.rgb, (int(self.x + ox), int(self.y + oy)), s, alpha)


# ── 衝撃波 ──────────────────────────────────────────────
class Shockwave:
    def __init__(self, x, y, speed, max_r, rgb, thick=3):
        self.x = x
        self.y = y
        self.r = 0.0
        self.speed = speed
        self.max_r = max_r
        self.rgb = rgb
        self.thick = thick

    def update(self):
        self.r += self.speed

    @property
    def alive(self):
        return self.r < self.max_r

    def draw(self, surf, ox=0, oy=0):
        ratio = max(0.0, 1.0 - self.r / self.max_r)
        alpha = int(255 * ratio**0.7)
        alpha_circle(
            surf,
            self.rgb,
            (int(self.x + ox), int(self.y + oy)),
            int(self.r),
            alpha,
            self.thick,
        )


# ── ✨ Sparkle（詠唱中のキラキラ）────────────────────────
class Sparkle:
    """魔法陣周辺に現れる十字キラキラ"""

    def __init__(self, cx, cy, radius=150):
        ang = random.uniform(0, math.pi * 2)
        dist = random.uniform(radius * 1.6, radius * 6.4)
        self.x = cx + math.cos(ang) * dist
        self.y = cy + math.sin(ang) * dist
        self.life = random.randint(92, 148)
        self.max_life = self.life
        self.size = random.uniform(3, 9)
        self.rgb = random.choice(
            [
                (255, 255, 210),
                (210, 160, 255),
                (180, 100, 255),
                (255, 220, 100),
            ]
        )
        self.angle = random.uniform(0, math.pi * 2)
        self.spin = random.uniform(-0.18, 0.18)  # radians per frame

    def update(self):
        self.life -= 1
        self.angle += self.spin

    @property
    def alive(self):
        return self.life > 0

    def draw(self, surf, ox=0, oy=0):
        ratio = self.life / self.max_life
        # brightness peaks at mid-life, zero at both ends
        peak = 1.0 - abs(ratio - 0.5) * 2
        alpha = int(255 * peak)
        if alpha < 5:
            return
        s = self.size
        x = int(self.x + ox)
        y = int(self.y + oy)
        si = int(s * 2.5)  # arm half-length
        d = si * 2 + 4
        tmp = pygame.Surface((d, d), pygame.SRCALPHA)
        c = si + 2  # local centre
        col = (*self.rgb, alpha)

        # Tapered cross: draw 3 overlapping lines per axis, rotated by self.angle.
        # longest+thinnest first so shorter+thicker lines paint on top.
        # This gives a shape that is wide at the centre and pointed at tips.
        cos_a = math.cos(self.angle)
        sin_a = math.sin(self.angle)
        for arm, w in [(si, 1), (int(si * 0.55), 2), (int(si * 0.25), 3)]:
            dx, dy = cos_a * arm, sin_a * arm
            pygame.draw.line(tmp, col, (c - dx, c - dy), (c + dx, c + dy), w)
            # perpendicular axis
            pygame.draw.line(tmp, col, (c - dy, c + dx), (c + dy, c - dx), w)

        # Bright centre dot
        cr = max(1, int(s * 0.35))
        pygame.draw.circle(tmp, (*self.rgb, min(255, alpha + 50)), (c, c), cr)

        surf.blit(tmp, (x - si - 2, y - si - 2))


# ── ⚡ Lightning（詠唱終盤の稲妻）───────────────────────
class Lightning:
    """再帰的なジグザグ稲妻。数フレームで消える。"""

    def __init__(self, x1, y1, x2, y2, color=(200, 100, 255), depth=4):
        self.life = random.randint(3, 7)
        self.max_life = self.life
        self.color = color
        self.segments = self._build(x1, y1, x2, y2, depth)

    def _build(self, x1, y1, x2, y2, depth):
        if depth == 0:
            return [(x1, y1, x2, y2)]
        spread = math.hypot(x2 - x1, y2 - y1) * 0.35
        mx = (x1 + x2) / 2 + random.uniform(-spread, spread)
        my = (y1 + y2) / 2 + random.uniform(-spread, spread)
        return self._build(x1, y1, mx, my, depth - 1) + self._build(
            mx, my, x2, y2, depth - 1
        )

    def update(self):
        self.life -= 1

    @property
    def alive(self):
        return self.life > 0

    def draw(self, surf, ox=0, oy=0):
        ratio = self.life / self.max_life
        alpha = int(255 * ratio)
        # 全セグメントをまとめて 1 枚のサーフェスに描く
        tmp = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for x1, y1, x2, y2 in self.segments:
            p1 = (int(x1 + ox), int(y1 + oy))
            p2 = (int(x2 + ox), int(y2 + oy))
            pygame.draw.line(tmp, (*self.color, alpha), p1, p2, 2)
            pygame.draw.line(tmp, (255, 255, 255, alpha // 2), p1, p2, 1)
        surf.blit(tmp, (0, 0))


# ── 🪨 Debris（爆発時の破片）────────────────────────────
class Debris:
    """回転しながら飛散する岩・金属の破片"""

    __slots__ = [
        "x",
        "y",
        "vx",
        "vy",
        "size",
        "angle",
        "spin",
        "life",
        "max_life",
        "rgb",
    ]

    def __init__(self, x, y, vx, vy, size, rgb, life):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.size = float(size)
        self.angle = random.uniform(0, 360)
        self.spin = random.uniform(-10, 10)
        self.rgb = rgb
        self.life = int(life)
        self.max_life = int(life)

    def update(self):
        self.vx *= 0.96
        self.vy *= 0.96
        self.vy += 0.35
        self.x += self.vx
        self.y += self.vy
        self.angle += self.spin
        self.life -= 1
        # 地面で跳ね返り
        if self.y > GROUND_Y:
            self.y = GROUND_Y
            self.vy = -self.vy * 0.3
            self.vx *= 0.7
            self.spin *= 0.5

    @property
    def alive(self):
        return self.life > 0

    def draw(self, surf, ox=0, oy=0):
        ratio = self.life / self.max_life
        alpha = int(200 * ratio)
        s = max(2, int(self.size * (0.4 + 0.6 * ratio)))
        x = int(self.x + ox)
        y = int(self.y + oy)
        d = s * 2 + 4
        tmp = pygame.Surface((d, d), pygame.SRCALPHA)
        c = d // 2
        # 4角形ポリゴン（回転あり）
        pts = []
        for i in range(4):
            a = math.radians(self.angle + i * 90 + 45)
            pts.append((c + s * math.cos(a), c + s * math.sin(a)))
        pygame.draw.polygon(tmp, (*self.rgb, alpha), pts)
        # ハイライト
        bright = (
            min(255, self.rgb[0] + 60),
            min(255, self.rgb[1] + 40),
            min(255, self.rgb[2] + 20),
        )
        pygame.draw.line(
            tmp,
            (*bright, alpha // 2),
            (int(pts[0][0]), int(pts[0][1])),
            (int(pts[2][0]), int(pts[2][1])),
            1,
        )
        surf.blit(tmp, (x - c, y - c))


# ── 🌋 LavaDroplet（溶岩の飛沫）────────────────────────
class LavaDroplet:
    """放物線を描いて落下し、地面でじわじわ広がる溶岩"""

    def __init__(self, x, y):
        ang = random.uniform(-math.pi + 0.2, -0.2)
        speed = random.uniform(6, 20)
        self.x = float(x) + random.uniform(-30, 30)
        self.y = float(y)
        self.vx = math.cos(ang) * speed
        self.vy = math.sin(ang) * speed
        self.size = random.uniform(4, 12)
        self.life = random.randint(60, 140)
        self.max_life = self.life
        r = random.randint(200, 255)
        g = random.randint(20, 100)
        self.rgb = (r, g, 0)
        self.grounded = False
        self.pool_r = 0.0  # 着地後に広がる半径

    def update(self):
        if not self.grounded:
            self.vx *= 0.985
            self.vy += 0.45
            self.x += self.vx
            self.y += self.vy
            if self.y >= GROUND_Y:
                self.y = GROUND_Y
                self.grounded = True
                self.pool_r = self.size
        else:
            self.pool_r = min(self.pool_r + 0.4, self.size * 3)
        self.life -= 1

    @property
    def alive(self):
        return self.life > 0

    def draw(self, surf, ox=0, oy=0):
        ratio = self.life / self.max_life
        x = int(self.x + ox)
        y = int(self.y + oy)
        if not self.grounded:
            # 飛翔中：明るい球
            alpha = int(230 * ratio)
            s = max(2, int(self.size))
            alpha_circle(surf, self.rgb, (x, y), s, alpha)
            # 内側の白熱コア
            core = (255, min(255, self.rgb[1] + 80), 0)
            alpha_circle(surf, core, (x, y), max(1, s // 2), alpha)
        else:
            # 着地後：楕円形に広がるプール
            alpha = int(180 * ratio)
            pr = int(self.pool_r)
            if pr < 1:
                return
            tmp = pygame.Surface((pr * 2 + 4, pr + 4), pygame.SRCALPHA)
            pygame.draw.ellipse(
                tmp, (*self.rgb, alpha), (2, 2, pr * 2, max(1, pr // 2))
            )
            surf.blit(tmp, (x - pr - 2, y - pr // 4 - 2))


# ── 🔥 FireWisp（立ち昇る炎の精・軌跡付き）────────────
class FireWisp:
    """正弦波を描きながら高速上昇する炎の精霊。軌跡ラインを曳く。"""

    HISTORY = 22  # 保持する過去座標の数

    def __init__(self, x, y):
        self.base_x = float(x) + random.uniform(-80, 80)
        self.x = self.base_x
        self.y = float(y)
        self.vy = random.uniform(-9.5, -0.3)  # 速度アップ
        self.t = random.uniform(0, math.pi * 2)
        self.amp = random.uniform(10, 32)
        self.freq = random.uniform(0.5, 2.0)
        self.size = random.uniform(4, 10)
        self.life = random.randint(45, 90)
        self.max_life = self.life
        self.rgb = (255, random.randint(60, 200), random.randint(0, 20))
        self.history = []  # [(x, y), ...]

    def update(self):
        # 動かす前の位置を履歴に記録
        self.history.append((self.x, self.y))
        if len(self.history) > self.HISTORY:
            self.history.pop(0)
        self.t += 0.13
        self.y += self.vy
        self.x = self.base_x + self.amp * math.sin(self.t * self.freq)
        self.size = max(0.5, self.size * 0.992)
        self.life -= 1

    @property
    def alive(self):
        return self.life > 0 and self.size > 0.5

    def draw(self, surf, ox=0, oy=0):
        ratio = self.life / self.max_life
        alpha = int(220 * (ratio**0.5))
        s = max(1, int(self.size * ratio**0.35))

        # ── 軌跡ライン ──────────────────────────────
        n = len(self.history)
        if n >= 2:
            # 軌跡のバウンディングボックスだけの小サーフェスに描く
            all_pts = self.history + [(self.x, self.y)]
            xs = [p[0] + ox for p in all_pts]
            ys = [p[1] + oy for p in all_pts]
            pad = s + 6
            bx = int(min(xs)) - pad
            by = int(min(ys)) - pad
            bw = max(1, int(max(xs)) - bx + pad * 2)
            bh = max(1, int(max(ys)) - by + pad * 2)
            tmp = pygame.Surface((bw, bh), pygame.SRCALPHA)

            for i in range(n - 1):
                t_r = (i + 1) / n  # 0=古端 → 1=先頭近く
                a_tr = int(alpha * t_r * 0.85)
                w_tr = max(1, int(s * t_r * 0.75))
                hx1 = int(self.history[i][0] + ox) - bx
                hy1 = int(self.history[i][1] + oy) - by
                hx2 = int(self.history[i + 1][0] + ox) - bx
                hy2 = int(self.history[i + 1][1] + oy) - by
                # 古いほど緑成分を落として暗い赤橙に
                g_tr = int(self.rgb[1] * (t_r**0.6))
                pygame.draw.line(
                    tmp, (self.rgb[0], g_tr, 0, a_tr), (hx1, hy1), (hx2, hy2), w_tr
                )
            # 最新履歴位置 → 現在位置をつなぐ
            hx1 = int(self.history[-1][0] + ox) - bx
            hy1 = int(self.history[-1][1] + oy) - by
            hx2 = int(self.x + ox) - bx
            hy2 = int(self.y + oy) - by
            pygame.draw.line(
                tmp,
                (self.rgb[0], self.rgb[1], 0, int(alpha * 0.85)),
                (hx1, hy1),
                (hx2, hy2),
                max(1, int(s * 0.75)),
            )
            surf.blit(tmp, (bx, by))

        # ── 頭部：グロー＋サークル＋白熱コア ──────────
        x = int(self.x + ox)
        y = int(self.y + oy)
        draw_glow(surf, x, y, s * 3, self.rgb, int(alpha * 0.5), 6)
        alpha_circle(surf, self.rgb, (x, y), s, alpha)
        if s > 3:
            alpha_circle(surf, (255, 245, 200), (x, y), max(1, s // 3), alpha)


# ── 魔法陣描画 ───────────────────────────────────────────
def draw_magic_circle(surf, cx, cy, radius, angle_deg, alpha):
    if radius < 2 or alpha <= 0:
        return
    r = int(radius)
    a = min(255, max(0, int(alpha)))
    tmp = pygame.Surface((r * 2 + 20, r * 2 + 20), pygame.SRCALPHA)
    c = r + 10

    for factor, w in [(1.0, 2), (0.72, 1), (0.44, 1)]:
        fr = max(1, int(r * factor))
        pygame.draw.circle(tmp, (180, 60, 240, a), (c, c), fr, w)

    def star_points(cx_, cy_, outer, inner, n, rot):
        pts = []
        for i in range(n * 2):
            rr = outer if i % 2 == 0 else inner
            ang = math.radians(rot + i * 180 / n - 90)
            pts.append((cx_ + rr * math.cos(ang), cy_ + rr * math.sin(ang)))
        return pts

    star = star_points(c, c, r * 0.88, r * 0.40, 7, angle_deg * 2)
    if len(star) >= 3:
        pygame.draw.polygon(tmp, (220, 80, 255, a), star, 2)

    hex_pts = []
    for i in range(6):
        ang = math.radians(-angle_deg * 1.5 + i * 60)
        hex_pts.append((c + r * 0.52 * math.cos(ang), c + r * 0.52 * math.sin(ang)))
    pygame.draw.polygon(tmp, (200, 100, 255, int(a * 0.75)), hex_pts, 1)

    for i in range(12):
        ang = math.radians(angle_deg * 2 + i * 30)
        x1 = c + r * 0.42 * math.cos(ang)
        y1 = c + r * 0.42 * math.sin(ang)
        x2 = c + r * 1.02 * math.cos(ang)
        y2 = c + r * 1.02 * math.sin(ang)
        pygame.draw.line(
            tmp, (200, 80, 255, int(a * 0.4)), (int(x1), int(y1)), (int(x2), int(y2)), 1
        )

    surf.blit(tmp, (cx - r - 10, cy - r - 10))


# ── 火球描画 ─────────────────────────────────────────────
# グラデーションのカラーストップ (位置 0=中心 1=縁, R, G, B, A)
_FIREBALL_STOPS = [
    (0.00, 255, 255, 245, 255),  # 白熱コア
    (0.10, 255, 255, 200, 255),  # クリーム白
    (0.22, 255, 245, 120, 255),  # 明るい黄
    (0.38, 255, 210, 40, 255),  # 黄
    (0.52, 255, 140, 5, 255),  # 黄橙
    (0.65, 255, 80, 0, 250),  # 橙
    (0.77, 230, 35, 0, 240),  # 赤橙
    (0.88, 180, 10, 0, 225),  # 赤
    (1.00, 120, 5, 0, 200),  # 暗い赤（縁）
]


def _fireball_color(t):
    """位置 t (0=中心, 1=縁) に対する RGBA を補間して返す"""
    stops = _FIREBALL_STOPS
    for i in range(len(stops) - 1):
        p1, r1, g1, b1, a1 = stops[i]
        p2, r2, g2, b2, a2 = stops[i + 1]
        if p1 <= t <= p2:
            s = (t - p1) / (p2 - p1)
            return (
                int(r1 + (r2 - r1) * s),
                int(g1 + (g2 - g1) * s),
                int(b1 + (b2 - b1) * s),
                int(a1 + (a2 - a1) * s),
            )
    return (120, 5, 0, 200)


def draw_fireball(surf, cx, cy, radius):
    if radius < 2:
        return
    r = int(radius)

    # 外側グロー（2層）
    draw_glow(surf, cx, cy, r * 3, (255, 120, 0), 90, 14)
    draw_glow(surf, cx, cy, r * 2, (255, 80, 0), 130, 10)

    # 40段階の同心円でなめらかグラデーションを描く
    STEPS = 40
    tmp = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
    cc = r + 2
    # 外側から内側へ塗ることで上書きしながら中心を明るくする
    for i in range(STEPS, 0, -1):
        t = i / STEPS  # 1.0=縁, 0.0=中心
        fr = max(1, int(r * t))
        pygame.draw.circle(tmp, _fireball_color(t), (cc, cc), fr)

    surf.blit(tmp, (cx - r - 2, cy - r - 2))


# ── 爆発光線 ─────────────────────────────────────────────
def draw_rays(surf, cx, cy, inner_r, outer_r, alpha, count=24):
    if alpha <= 0 or outer_r <= 0:
        return
    ray_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(count):
        ang = math.radians(i * 360 / count + random.uniform(-3, 3))
        r2 = outer_r * random.uniform(0.7, 1.4)
        x1 = cx + inner_r * math.cos(ang)
        y1 = cy + inner_r * math.sin(ang)
        x2 = cx + r2 * math.cos(ang)
        y2 = cy + r2 * math.sin(ang)
        pygame.draw.line(
            ray_surf,
            (255, 240, 150, int(alpha)),
            (int(x1), int(y1)),
            (int(x2), int(y2)),
            2,
        )
    surf.blit(ray_surf, (0, 0))


# ── 地面クラック ─────────────────────────────────────────
def draw_cracks(surf, cx, cy, radius, alpha, ox=0, oy=0):
    if radius < 10 or alpha <= 0:
        return
    rng = random.Random(42)
    crack_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for _ in range(12):
        ang = rng.uniform(0, math.pi * 2)
        dist = rng.uniform(radius * 0.2, radius * 0.9)
        num_seg = rng.randint(3, 7)
        x_cur = cx + ox + rng.uniform(-5, 5)
        y_cur = cy + oy + rng.uniform(-5, 5)
        for _ in range(num_seg):
            dev = rng.uniform(-0.4, 0.4)
            seg = rng.uniform(dist * 0.1, dist * 0.25)
            x_next = x_cur + seg * math.cos(ang + dev)
            y_next = y_cur + seg * math.sin(ang + dev)
            pygame.draw.line(
                crack_surf,
                (80, 40, 20, int(alpha)),
                (int(x_cur), int(y_cur)),
                (int(x_next), int(y_next)),
                2,
            )
            x_cur, y_cur = x_next, y_next
            ang += dev
    surf.blit(crack_surf, (0, 0))


# ── 爆発トリガー ─────────────────────────────────────────
def spawn_explosion(particles, smokes, shockwaves, debris_list, lava_list):
    cx, cy = CENTER_X, CENTER_Y

    # メイン火の粉
    for _ in range(500):
        ang = random.uniform(0, math.pi * 2)
        speed = random.uniform(2.5, 22)
        vx = math.cos(ang) * speed
        vy = math.sin(ang) * speed - random.uniform(0, 10)
        t = random.random()
        if t < 0.12:
            rgb = (255, 255, 230)
        elif t < 0.35:
            rgb = (255, 230, 70)
        elif t < 0.65:
            rgb = (255, 130, 10)
        else:
            rgb = (210, 30, 0)
        particles.append(
            Particle(
                cx,
                cy,
                vx,
                vy,
                rgb,
                random.uniform(3, 16),
                random.randint(25, 90),
                gravity=0.22,
                glow=(t < 0.35),
            )
        )

    # 残り火エンバー
    for _ in range(250):
        ang = random.uniform(0, math.pi * 2)
        speed = random.uniform(1, 12)
        vx = math.cos(ang) * speed
        vy = math.sin(ang) * speed - random.uniform(3, 12)
        rgb = (255, random.randint(80, 220), 0)
        particles.append(
            Particle(
                cx,
                cy,
                vx,
                vy,
                rgb,
                random.uniform(1, 5),
                random.randint(80, 220),
                gravity=0.05,
                drag=0.99,
            )
        )

    # 紫の魔力破片
    for _ in range(80):
        ang = random.uniform(0, math.pi * 2)
        speed = random.uniform(3, 14)
        vx = math.cos(ang) * speed
        vy = math.sin(ang) * speed - random.uniform(2, 8)
        rgb = (random.randint(140, 220), 0, random.randint(180, 255))
        particles.append(
            Particle(
                cx,
                cy,
                vx,
                vy,
                rgb,
                random.uniform(2, 8),
                random.randint(20, 60),
                gravity=0.18,
                glow=True,
            )
        )

    # 🪨 岩/金属の破片
    for _ in range(100):
        ang = random.uniform(0, math.pi * 2)
        speed = random.uniform(4, 18)
        vx = math.cos(ang) * speed
        vy = math.sin(ang) * speed - random.uniform(2, 12)
        t = random.random()
        if t < 0.5:
            rgb = (
                random.randint(80, 130),
                random.randint(60, 100),
                random.randint(40, 70),
            )  # 岩
        else:
            rgb = (
                random.randint(140, 180),
                random.randint(120, 160),
                random.randint(100, 140),
            )  # 金属
        debris_list.append(
            Debris(cx, cy, vx, vy, random.uniform(4, 14), rgb, random.randint(60, 150))
        )

    # 🌋 溶岩の飛沫
    for _ in range(80):
        lava_list.append(LavaDroplet(cx, cy))

    # 衝撃波リング
    for speed, max_r, rgb, thick in [
        (14, 900, WHITE, 5),
        (9, 700, (255, 210, 120), 3),
        (5, 500, (255, 100, 0), 2),
        (3, 350, (255, 60, 0), 1),
    ]:
        shockwaves.append(Shockwave(cx, cy, speed, max_r, rgb, thick))

    # 衝撃波リングに沿って粒子を散らす
    for _ in range(120):
        ang = random.uniform(0, math.pi * 2)
        speed = random.uniform(10, 16)
        vx = math.cos(ang) * speed
        vy = math.sin(ang) * speed
        rgb = (255, random.randint(150, 255), random.randint(0, 80))
        particles.append(
            Particle(
                cx,
                cy,
                vx,
                vy,
                rgb,
                random.uniform(2, 6),
                random.randint(15, 40),
                gravity=0.1,
                glow=True,
            )
        )

    # 煙
    for _ in range(25):
        smokes.append(SmokeParticle(cx, cy))


# ── メインループ ─────────────────────────────────────────
def main():
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("EXPLOSION!")
    clock = pygame.time.Clock()

    def reset():
        return dict(
            start_ticks=pygame.time.get_ticks(),
            particles=[],
            smokes=[],
            shockwaves=[],
            sparkles=[],  # ✨ キラキラ
            lightnings=[],  # ⚡ 稲妻
            debris_list=[],  # 🪨 破片
            lava_list=[],  # 🌋 溶岩
            wisps=[],  # 🔥 炎の精
            explosion_done=False,
            flash_alpha=0.0,
            fireball_r=0.0,
            circle_r=0.0,
            circle_alpha=0.0,
            circle_angle=0.0,
            circle_spin=1.5,
            crack_alpha=0.0,
            shake_x=0,
            shake_y=0,
            shake_intensity=0.0,
            shake_frames=0,
            ray_alpha=0.0,
            snd_hum_on=False,
            snd_charge_on=False,
            snd_boom_on=False,
            snd_crackle_on=False,
        )

    state = reset()

    def now():
        return (pygame.time.get_ticks() - state["start_ticks"]) / 1000.0

    pause = False
    running = True
    stop_time = 0
    while running:
        clock.tick(FPS)
        t = now()

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                if ev.key == pygame.K_r:
                    if _SOUND_OK:
                        pygame.mixer.stop()
                    state = reset()
                    t = now()
                if ev.key == pygame.K_p:
                    stop_time = now()
                    pause = not pause
                    t = now()

        if pause:
            hint = font_title.render("PAUSED", True, (80, 80, 120))
            screen.blit(hint, (CENTER_X - 190, CENTER_Y - 40))
            pygame.display.flip()
            state["start_ticks"] = pygame.time.get_ticks() - stop_time * 1000.0
            continue

        st = state

        # ── スクリーンシェイク ──
        if st["shake_frames"] > 0:
            st["shake_x"] = random.randint(
                -int(st["shake_intensity"]), int(st["shake_intensity"])
            )
            st["shake_y"] = random.randint(
                -int(st["shake_intensity"]), int(st["shake_intensity"])
            )
            st["shake_intensity"] *= 0.92
            st["shake_frames"] -= 1
        else:
            st["shake_x"] = st["shake_y"] = 0

        # ── サウンドトリガー ──────────────────────────────
        if _SOUND_OK:
            if not st["snd_hum_on"]:
                snd_hum.play(-1)
                st["snd_hum_on"] = True
            if not st["snd_charge_on"] and t >= T_CHANT_END:
                snd_charge.play()
                st["snd_charge_on"] = True
            if not st["snd_boom_on"] and st["explosion_done"]:
                snd_hum.fadeout(300)
                snd_explosion.play()
                st["snd_boom_on"] = True
            if not st["snd_crackle_on"] and t >= T_PEAK:
                snd_crackle.set_volume(0.6)
                snd_crackle.play(-1)
                st["snd_crackle_on"] = True
            if st["snd_crackle_on"] and t >= T_FADE:
                prog = min(1.0, (t - T_FADE) / (T_END - T_FADE))
                snd_crackle.set_volume(max(0.0, 0.6 * (1.0 - prog)))

        # ── フェーズ別ロジック ──────────────────────────
        if t < T_CHANT_END:
            # 詠唱フェーズ：魔法陣展開 + ✨キラキラ出現
            prog = t / T_CHANT_END
            st["circle_r"] = lerp(0, 190, min(1, prog * 1.3))
            st["circle_alpha"] = lerp(0, 200, min(1, prog * 1.3))
            st["circle_spin"] = 1.5 + prog * 2

            # 紫エネルギーが収束
            if random.random() < 0.15:
                ang = random.uniform(0, math.pi * 2)
                dist = random.uniform(250, 500)
                px = CENTER_X + math.cos(ang) * dist
                py = CENTER_Y + math.sin(ang) * dist
                sp = random.uniform(3, 7)
                st["particles"].append(
                    Particle(
                        px,
                        py,
                        (CENTER_X - px) / dist * sp,
                        (CENTER_Y - py) / dist * sp,
                        (random.randint(100, 200), 0, random.randint(160, 255)),
                        random.uniform(2, 5),
                        random.randint(20, 45),
                        gravity=0,
                    )
                )

            # ✨ キラキラを魔法陣周辺にランダム生成
            if st["circle_r"] > 20 and random.random() < 0.25:
                st["sparkles"].append(Sparkle(CENTER_X, CENTER_Y, st["circle_r"]))

        elif t < T_CAST:
            # 詠唱完了：魔法陣が高速回転 + ⚡稲妻
            prog = (t - T_CHANT_END) / (T_CAST - T_CHANT_END)
            st["circle_r"] = lerp(190, 220, prog)
            st["circle_alpha"] = lerp(200, 255, prog)
            st["circle_spin"] = lerp(3.5, 18, prog)

            # エネルギー収束強化（橙色）
            if random.random() < 0.4:
                ang = random.uniform(0, math.pi * 2)
                dist = random.uniform(150, 400)
                px = CENTER_X + math.cos(ang) * dist
                py = CENTER_Y + math.sin(ang) * dist
                sp = random.uniform(5, 12)
                st["particles"].append(
                    Particle(
                        px,
                        py,
                        (CENTER_X - px) / dist * sp,
                        (CENTER_Y - py) / dist * sp,
                        (random.randint(180, 255), random.randint(50, 150), 0),
                        random.uniform(3, 7),
                        random.randint(15, 30),
                        gravity=-0.02,
                    )
                )

            # ⚡ 稲妻：魔法陣から周囲に向けて放電
            if random.random() < 0.35 * (1 + prog * 2):
                ang = random.uniform(0, math.pi * 2)
                dist = random.uniform(60, 280)
                ex = CENTER_X + math.cos(ang) * dist
                ey = CENTER_Y + math.sin(ang) * dist
                col = random.choice([(200, 100, 255), (255, 200, 100), (150, 200, 255)])
                st["lightnings"].append(Lightning(CENTER_X, CENTER_Y, ex, ey, col))

            # ✨ キラキラも継続（より密に）
            if random.random() < 0.4:
                st["sparkles"].append(Sparkle(CENTER_X, CENTER_Y, st["circle_r"] * 1.2))

        elif t < T_FLASH:
            # 爆発発動
            if not st["explosion_done"]:
                spawn_explosion(
                    st["particles"],
                    st["smokes"],
                    st["shockwaves"],
                    st["debris_list"],
                    st["lava_list"],
                )
                st["explosion_done"] = True
                st["flash_alpha"] = 255.0
                st["fireball_r"] = 5.0
                st["shake_intensity"] = 25.0
                st["shake_frames"] = 90
            st["circle_alpha"] = max(0, st["circle_alpha"] - 25)
            st["flash_alpha"] = max(0, st["flash_alpha"] - 18)
            st["fireball_r"] = min(220, st["fireball_r"] + 28)
            st["ray_alpha"] = min(180, st["ray_alpha"] + 40)

        elif t < T_PEAK:
            # ピーク
            prog = (t - T_FLASH) / (T_PEAK - T_FLASH)
            st["flash_alpha"] = max(0, st["flash_alpha"] - 8)
            st["fireball_r"] = lerp(220, 260, min(1, prog * 1.5))
            st["circle_alpha"] = 0.0
            st["ray_alpha"] = max(0, 180 - prog * 200)
            st["crack_alpha"] = min(200, st["crack_alpha"] + 15)

            if random.random() < 0.4:
                for _ in range(4):
                    st["smokes"].append(SmokeParticle(CENTER_X, CENTER_Y))

        elif t < T_SUSTAINED:
            # 持続燃焼：🔥炎の精が立ち昇る
            prog = (t - T_PEAK) / (T_SUSTAINED - T_PEAK)
            st["fireball_r"] = lerp(260, 100, prog**0.6)
            st["flash_alpha"] = 0
            st["ray_alpha"] = 0
            st["crack_alpha"] = max(0, 200 - prog * 50)

            if random.random() < 0.35:
                st["smokes"].append(
                    SmokeParticle(CENTER_X, CENTER_Y - st["fireball_r"] * 0.4)
                )

            # 🔥 炎の精を生成
            if random.random() < 0.3:
                st["wisps"].append(
                    FireWisp(CENTER_X, CENTER_Y - st["fireball_r"] * 0.5)
                )

            # 残り火
            if random.random() < 0.15:
                ang = random.uniform(0, math.pi * 2)
                sp = random.uniform(1, 6)
                st["particles"].append(
                    Particle(
                        CENTER_X,
                        CENTER_Y,
                        math.cos(ang) * sp,
                        math.sin(ang) * sp - 2,
                        (255, random.randint(80, 200), 0),
                        random.uniform(2, 6),
                        random.randint(20, 60),
                        gravity=0.1,
                    )
                )

        elif t < T_FADE:
            # フェードアウト
            prog = (t - T_SUSTAINED) / (T_FADE - T_SUSTAINED)
            st["fireball_r"] = max(0, lerp(100, 0, prog))
            st["crack_alpha"] = max(0, 150 - prog * 150)

            # 余韻の炎の精
            if random.random() < 0.1:
                st["wisps"].append(FireWisp(CENTER_X, CENTER_Y))

        # 魔法陣角度更新
        st["circle_angle"] += st["circle_spin"]

        # ── パーティクル更新 ──
        for p in st["particles"]:
            p.update()
        for s in st["smokes"]:
            s.update()
        for sw in st["shockwaves"]:
            sw.update()
        for sp in st["sparkles"]:
            sp.update()
        for ln in st["lightnings"]:
            ln.update()
        for db in st["debris_list"]:
            db.update()
        for lv in st["lava_list"]:
            lv.update()
        for w in st["wisps"]:
            w.update()

        st["particles"] = [p for p in st["particles"] if p.alive]
        st["smokes"] = [s for s in st["smokes"] if s.alive]
        st["shockwaves"] = [sw for sw in st["shockwaves"] if sw.alive]
        st["sparkles"] = [sp for sp in st["sparkles"] if sp.alive]
        st["lightnings"] = [ln for ln in st["lightnings"] if ln.alive]
        st["debris_list"] = [db for db in st["debris_list"] if db.alive]
        st["lava_list"] = [lv for lv in st["lava_list"] if lv.alive]
        st["wisps"] = [w for w in st["wisps"] if w.alive]

        # ── 描画 ─────────────────────────────────────────
        ox, oy = st["shake_x"], st["shake_y"]
        screen.fill(BG_COLOR)

        # 地面クラック
        if st["crack_alpha"] > 0:
            draw_cracks(screen, CENTER_X, CENTER_Y, 280, st["crack_alpha"], ox, oy)

        # 🌋 溶岩（地面に近いので最下層）
        for lv in st["lava_list"]:
            lv.draw(screen, ox, oy)

        # 外側グロー
        if st["fireball_r"] > 0:
            draw_glow(
                screen,
                CENTER_X + ox,
                CENTER_Y + oy,
                int(st["fireball_r"] * 3.5),
                (255, 80, 0),
                70,
                14,
            )

        # 煙
        for s in st["smokes"]:
            s.draw(screen, ox, oy)

        # 衝撃波
        for sw in st["shockwaves"]:
            sw.draw(screen, ox, oy)

        # 🪨 破片
        for db in st["debris_list"]:
            db.draw(screen, ox, oy)

        # 基本パーティクル（火の粉・エンバー・魔力破片）
        for p in st["particles"]:
            p.draw(screen, ox, oy)

        # 🔥 炎の精
        for w in st["wisps"]:
            w.draw(screen, ox, oy)

        # 魔法陣
        if st["circle_r"] > 1 and st["circle_alpha"] > 0:
            draw_glow(
                screen,
                CENTER_X + ox,
                CENTER_Y + oy,
                int(st["circle_r"] * 1.5),
                PURPLE,
                int(st["circle_alpha"] * 0.6),
            )
            draw_magic_circle(
                screen,
                CENTER_X + ox,
                CENTER_Y + oy,
                st["circle_r"],
                st["circle_angle"],
                st["circle_alpha"],
            )

        # ✨ キラキラ（魔法陣の上に重ねる）
        for sp in st["sparkles"]:
            sp.draw(screen, ox, oy)

        # 爆発光線
        if st["ray_alpha"] > 0:
            draw_rays(
                screen,
                CENTER_X + ox,
                CENTER_Y + oy,
                st["fireball_r"] * 0.7,
                st["fireball_r"] * 3.5,
                st["ray_alpha"],
            )

        # 火球
        if st["fireball_r"] > 1:
            draw_fireball(screen, CENTER_X + ox, CENTER_Y + oy, int(st["fireball_r"]))

        # ⚡ 稲妻（最前景）
        for ln in st["lightnings"]:
            ln.draw(screen, ox, oy)

        # 閃光オーバーレイ
        if st["flash_alpha"] > 0:
            fsurf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            fsurf.fill((255, 245, 210, int(st["flash_alpha"])))
            screen.blit(fsurf, (0, 0))

        # ── テキスト ──────────────────────────────────────
        if t < T_FLASH + 0.3:
            for i, (ct, text) in enumerate(CHANT):
                if t >= ct:
                    age = t - ct
                    if t > T_CAST:
                        a = max(0, int(255 - (t - T_CAST) / 0.3 * 255))
                    else:
                        a = min(255, int(age / 0.35 * 255))
                    try:
                        is_last = i == len(CHANT) - 1
                        f = font_sub if is_last else font_chant
                        col = GOLD if is_last else (220, 180, 255)
                        txt = f.render(text, True, col)
                        txt.set_alpha(a)
                        x = WIDTH // 2 - txt.get_width() // 2
                        y = HEIGHT // 2 - 130 + i * 50
                        shadow = f.render(text, True, (0, 0, 0))
                        shadow.set_alpha(a // 2)
                        screen.blit(shadow, (x + 2, y + 2))
                        screen.blit(txt, (x, y))
                    except Exception:
                        pass

        if st["explosion_done"] and t >= T_FLASH:
            dt_ex = t - T_FLASH
            if dt_ex < 0.4:
                scale = min(1.6, dt_ex / 0.25 * 1.6)
                a = min(255, int(dt_ex / 0.25 * 255))
            elif dt_ex < 1.0:
                scale = lerp(1.6, 1.0, (dt_ex - 0.4) / 0.6)
                a = 255
            elif dt_ex < T_FADE - T_FLASH - 1.0:
                scale = 1.0
                a = 255
            else:
                prog = (dt_ex - (T_FADE - T_FLASH - 1.0)) / 1.0
                scale = 1.0
                a = max(0, int(255 - prog * 255))

            if scale > 0 and a > 0:
                for text, font, color, yoff in [
                    ("EXPLOSION!!!", font_sub, (255, 140, 30), 40),
                ]:
                    try:
                        rendered = font.render(text, True, color)
                        w, h = rendered.get_size()
                        sw2 = max(1, int(w * scale))
                        sh2 = max(1, int(h * scale))
                        scaled = pygame.transform.scale(rendered, (sw2, sh2))
                        scaled.set_alpha(a)
                        shadow = font.render(text, True, (255, 80, 0))
                        ssw = pygame.transform.scale(shadow, (sw2 + 4, sh2 + 4))
                        ssw.set_alpha(a // 3)
                        sx = WIDTH // 2 - sw2 // 2
                        sy = HEIGHT // 4 + yoff - sh2 // 2
                        screen.blit(ssw, (sx - 2, sy - 2))
                        screen.blit(scaled, (sx, sy))
                    except Exception:
                        pass

        hint = font_hint.render("R: やり直し | ESC: 終了", True, (80, 80, 120))
        screen.blit(hint, (10, HEIGHT - 28))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
