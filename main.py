"""Jogo "Simples World" - Atividade prática de representação do mundo.

Execução:
    python main.py [caminho_para_config.json]

Controles:
    WASD / Setas ....... mover
    P ................. pausar
    R ................. reiniciar nível
    ESC ............... voltar ao início (na tela inicial, fecha)
    Q ................. sair
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import sys
import time
from pathlib import Path

import pygame

from game.camera import Viewport
from game.entities import Item, Player
from game.world import World

# ----------------------------------------------------------------------
# Constantes visuais
# ----------------------------------------------------------------------
COLOR_BG = (14, 15, 20)
COLOR_AREA_INACTIVE = (26, 28, 36)
COLOR_AREA_ACTIVE = (38, 48, 66)
COLOR_GRID = (58, 64, 80)
COLOR_PLAYER = (0, 220, 255)
COLOR_NPC = (230, 60, 60)
COLOR_HEALTH = (60, 220, 90)
COLOR_AMMO = (250, 210, 60)
COLOR_TEXT = (235, 235, 235)
COLOR_TEXT_DIM = (150, 155, 165)
COLOR_HUD_BG = (10, 11, 14, 180)


def lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class Effects:
    """Efeitos visuais da explosão de TNT (dano em área)."""

    def __init__(self):
        self.explosions: list[dict] = []

    def spawn_explosion(self, x, y, radius):
        self.explosions.append({"x": x, "y": y, "radius": radius, "t": 0.0})

    def update(self, dt):
        for e in self.explosions:
            e["t"] += dt
        self.explosions = [e for e in self.explosions if e["t"] < 0.6]

    def draw(self, surface, cam, color=COLOR_AMMO):
        z = cam.zoom
        for e in self.explosions:
            p = min(1.0, e["t"] / 0.6)
            r = (8.0 + (e["radius"] - 8.0) * p) * z  # cresce até a área de dano
            sx, sy = cam.to_screen(e["x"], e["y"])
            side = int(r * 2 + 8)
            surf = pygame.Surface((side, side), pygame.SRCALPHA)
            # flash preenchido de baixa opacidade (delineia a área de dano)
            flash_alpha = int(90 * (1 - p))
            pygame.draw.circle(surf, (*color, flash_alpha), (side // 2, side // 2), int(r * 0.92))
            # anel de contorno nítido
            ring_alpha = int(240 * (1 - p))
            pygame.draw.circle(surf, (*color, ring_alpha), (side // 2, side // 2), int(r), width=3)
            surface.blit(surf, (int(sx - side / 2), int(sy - side / 2)))


class Game:
    def __init__(self, config: dict):
        pygame.init()
        self.config = config
        vp = config["viewport"]
        # Janela maximizada (modo janela), usando a área de trabalho disponível.
        area = self._work_area()
        if area is not None:
            width, height, px, py = area
            os.environ["SDL_VIDEO_WINDOW_POS"] = f"{px},{py}"
        else:
            width, height, px, py = vp["width"], vp["height"], 0, 0
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        pygame.display.set_caption("Simples World - Representação do Mundo (IA p/ Jogos)")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 18)
        self.font_big = pygame.font.Font(None, 60)
        self.font_med = pygame.font.Font(None, 32)

        self.survival_time = float(config.get("survival_time", 90.0))
        self.zoom = float(config.get("viewport_zoom", 1.75))
        self.camera = Viewport(width, height, zoom=self.zoom)
        self.world: World | None = None
        self.effects = Effects()
        self.state = "MENU"
        self.result = None
        self.time_start = 0.0
        self._new_level()

    @staticmethod
    def _work_area():
        """Retorna (largura, altura, x, y) da área de trabalho (sem taskbar)."""
        try:
            import ctypes

            user32 = ctypes.windll.user32

            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                            ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

            rect = RECT()
            # SPI_GETWORKAREA = 0x0030
            if user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
                w, h = rect.right - rect.left, rect.bottom - rect.top
                if w > 0 and h > 0:
                    return (w, h, rect.left, rect.top)
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    def _new_level(self):
        self.world = World(self.config)
        self.world.populate()
        cam = self.camera
        self.camera.x = max(0.0, self.world.player.x - cam.world_width / 2.0)
        self.camera.y = max(0.0, self.world.player.y - cam.world_height / 2.0)
        self.effects = Effects()
        self.time_start = time.monotonic()

    def _time_left(self):
        return max(0.0, self.survival_time - (time.monotonic() - self.time_start))

    # ------------------------------------------------------------------
    # Entrada
    # ------------------------------------------------------------------
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit()
            elif event.type == pygame.VIDEORESIZE:
                self.camera.width = event.w
                self.camera.height = event.h
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    self.quit()
                elif event.key == pygame.K_ESCAPE:
                    if self.state == "MENU":
                        self.quit()
                    else:
                        self.state = "MENU"
                elif event.key == pygame.K_r and self.state in ("PLAYING", "PAUSED", "WON", "LOST"):
                    self._new_level()
                    self.state = "PLAYING"
                elif event.key == pygame.K_p and self.state == "PLAYING":
                    self.state = "PAUSED"
                elif event.key in (pygame.K_p, pygame.K_SPACE) and self.state == "PAUSED":
                    self.state = "PLAYING"
                elif event.key == pygame.K_RETURN and self.state == "MENU":
                    self.state = "PLAYING"
                    self._new_level()

    def _keyboard_movement(self):
        player = self.world.player
        keys = pygame.key.get_pressed()
        dx = keys[pygame.K_d] - keys[pygame.K_a] + keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]
        dy = keys[pygame.K_s] - keys[pygame.K_w] + keys[pygame.K_DOWN] - keys[pygame.K_UP]
        player.set_input(float(dx), float(dy))

    def quit(self):
        pygame.quit()
        sys.exit(0)

    # ------------------------------------------------------------------
    # Loop principal (assíncrono para o pygbag web; idêntico no desktop)
    # ------------------------------------------------------------------
    async def run(self):
        while True:
            dt = min(self.clock.tick(120) / 1000.0, 0.05)
            self.handle_events()

            if self.state == "PLAYING":
                self._step(dt)

            self.draw()
            pygame.display.flip()
            await asyncio.sleep(0)

    def _step(self, dt):
        w = self.world
        self._keyboard_movement()
        w.player.update(dt, w.width, w.height)
        w.update(dt)
        for e in w.explosions:
            self.effects.spawn_explosion(e["x"], e["y"], e["radius"])
        w.explosions.clear()
        self.effects.update(dt)
        self.camera.follow(w.player.x, w.player.y, w.width, w.height, dt)

        if self._time_left() <= 0.0:
            self.result = True
            self.state = "WON"
        elif w.player.health <= 0.0:
            self.result = False
            self.state = "LOST"

    # ------------------------------------------------------------------
    # Desenho
    # ------------------------------------------------------------------
    def draw(self):
        w = self.world
        cam = self.camera
        self.screen.fill(COLOR_BG)
        z = cam.zoom

        # --- Áreas da malha (recorte pela viewport) ---
        vx0, vy0, vx1, vy1 = cam.visible_world()
        for row in w.areas:
            for area in row:
                if area.right < vx0 or area.bottom < vy0 or area.left > vx1 or area.top > vy1:
                    continue
                sx, sy = cam.to_screen(area.left, area.top)
                rect = pygame.Rect(int(sx), int(sy), int(area.size * z), int(area.size * z))
                color = COLOR_AREA_ACTIVE if area.active else COLOR_AREA_INACTIVE
                pygame.draw.rect(self.screen, color, rect)
                pygame.draw.rect(self.screen, COLOR_GRID, rect, 1)
                # rótulo da área
                label = f"A{area.col + 1},{area.row + 1}"
                txt = self.font_small.render(f"{label}", True,
                                             COLOR_TEXT_DIM if not area.active else COLOR_AMMO)
                self.screen.blit(txt, (int(sx + 8), int(sy + 8)))

        # --- Itens (apenas áreas ativas) ---
        for area in w.active_areas:
            for item in area.items:
                self._draw_item(item)

        # --- NPCs (apenas áreas ativas) ---
        for area in w.active_areas:
            for npc in area.npcs:
                sx, sy = cam.to_screen(npc.x, npc.y)
                if sx < -60 or sy < -60 or sx > self.screen.get_width() + 60 or sy > self.screen.get_height() + 60:
                    continue
                frac = max(0.0, min(1.0, npc.health / w.config["npc"]["health"]))
                color = lerp_color(COLOR_NPC, (240, 160, 60), frac)
                r = int(npc.radius * z)
                pygame.draw.circle(self.screen, color, (int(sx), int(sy)), r)
                pygame.draw.circle(self.screen, (0, 0, 0), (int(sx), int(sy)), r, 2)

        # --- Jogador ---
        self._draw_player()

        self.effects.draw(self.screen, cam)

        # --- HUD / telas ---
        if self.state == "MENU":
            self._draw_menu()
        elif self.state == "PLAYING":
            self._draw_hud()
        elif self.state == "PAUSED":
            self._draw_hud()
            self._draw_center_text("PAUSADO", "[P] continuar   [R] reiniciar   [ESC] menu")
        elif self.state == "WON":
            self._draw_hud()
            self._draw_center_text("VOCÊ SOBREVIVEU!", "[R] jogar novamente   [ESC] menu", COLOR_HEALTH)
        elif self.state == "LOST":
            self._draw_hud()
            self._draw_center_text("VOCÊ MORREU", "[R] tentar de novo   [ESC] menu", COLOR_NPC)

    # ------------------------------------------------------------------
    def _draw_item(self, item):
        cam = self.camera
        z = cam.zoom
        sx, sy = cam.to_screen(item.x, item.y)
        if sx < -40 or sy < -40 or sx > self.screen.get_width() + 40 or sy > self.screen.get_height() + 40:
            return
        if item.kind == "health":
            self._draw_health_icon(sx, sy, 9 * z)
        else:
            self._draw_tnt_icon(sx, sy, 0.45 * z)

    def _draw_health_icon(self, cx, cy, r):
        """Círculo verde com cruz branca (primeiros socorros)."""
        pygame.draw.circle(self.screen, (20, 70, 30), (int(cx), int(cy)), int(r))
        pygame.draw.circle(self.screen, COLOR_HEALTH, (int(cx), int(cy)), int(r), 2)
        w = int(r * 0.6)
        h = max(2, int(r * 0.28))
        pygame.draw.rect(self.screen, COLOR_HEALTH, (int(cx) - w, int(cy) - h // 2, 2 * w, h))
        pygame.draw.rect(self.screen, COLOR_HEALTH, (int(cx) - h // 2, int(cy) - w, h, 2 * w))

    def _draw_tnt_icon(self, cx, cy, c):
        """Caixote de TNT com pavio e faísca."""
        if c <= 0:
            return
        x, y = int(cx), int(cy)
        box = pygame.Rect(x - int(15 * c), y - int(11 * c), int(30 * c), int(22 * c))
        if box.w < 4:
            return
        pygame.draw.rect(self.screen, (200, 74, 34), box)
        pygame.draw.rect(self.screen, (130, 44, 20), box, 2)
        pygame.draw.rect(self.screen, (120, 50, 22), (box.x + int(3 * c), box.y + int(8 * c),
                                                      box.w - int(6 * c), int(6 * c)))
        txt = self.font_small.render("TNT", True, (250, 210, 160))
        tw, th = txt.get_width(), txt.get_height()
        txt2 = pygame.transform.smoothscale(txt, (max(3, int(tw * 0.55 * c)), max(2, int(th * 0.55 * c))))
        self.screen.blit(txt2, (x - txt2.get_width() // 2, y - txt2.get_height() // 2))
        pygame.draw.line(self.screen, (90, 60, 40), (x + int(11 * c), y - int(9 * c)),
                         (x + int(18 * c), y - int(15 * c)), 2)
        pygame.draw.circle(self.screen, (255, 210, 80), (x + int(19 * c), y - int(16 * c)), max(2, int(3 * c)))

    def _draw_player(self):
        cam = self.camera
        p = self.world.player
        z = cam.zoom
        sx, sy = cam.to_screen(p.x, p.y)
        r = int(p.radius * z)
        pygame.draw.circle(self.screen, COLOR_PLAYER, (int(sx), int(sy)), r)
        pygame.draw.circle(self.screen, (255, 255, 255), (int(sx), int(sy)), r, 2)
        # indicador de direção
        dx, dy = p.vx, p.vy
        length = math.hypot(dx, dy)
        if length > 0:
            endx = int(sx + (dx / length) * (p.radius + 6) * z)
            endy = int(sy + (dy / length) * (p.radius + 6) * z)
            pygame.draw.line(self.screen, (255, 255, 255), (int(sx), int(sy)), (endx, endy), 2)

    # ------------------------------------------------------------------
    def _draw_hud(self):
        p = self.world.player
        w = self.world
        surf_w, surf_h = self.screen.get_size()
        bar_w, bar_h = 260, 16
        bx, by = 14, 12
        row2 = by + 46
        panel_h = row2 + 24

        panel = pygame.Surface((surf_w, panel_h), pygame.SRCALPHA)
        panel.fill(COLOR_HUD_BG)
        self.screen.blit(panel, (0, 0))

        # Linha 1 — saúde (esquerda) | tempo | itens usados (direita)
        txt = self.font_small.render("SAÚDE", True, COLOR_TEXT_DIM)
        self.screen.blit(txt, (bx, by))
        frac = max(0.0, min(1.0, p.health / p.max_health))
        pygame.draw.rect(self.screen, (40, 40, 48), (bx, by + 18, bar_w, bar_h))
        pygame.draw.rect(self.screen, lerp_color(COLOR_NPC, COLOR_HEALTH, frac),
                         (bx, by + 18, int(bar_w * frac), bar_h))
        pygame.draw.rect(self.screen, (255, 255, 255), (bx, by + 18, bar_w, bar_h), 1)

        time_left = self._time_left()
        ttxt = self.font.render(f"TEMPO: {int(time_left)}s", True, COLOR_TEXT)
        self.screen.blit(ttxt, (bx + bar_w + 30, by + 4))

        used = self.font_small.render(
            f"Primeiros socorros usados: {p.health_picked}   TNT usada: {p.ammo_picked}",
            True, COLOR_TEXT_DIM,
        )
        self.screen.blit(used, (surf_w - used.get_width() - 16, by + 4))

        # Linha 2 — estatísticas (esquerda) | legenda (direita)
        info = self.font_small.render(
            f"Áreas ativas: {len(w.active_cells)}/{w.cols * w.rows}   "
            f"Inimigos restantes: {w.remaining_npcs}   "
            f"Abates: {p.kills}",
            True, COLOR_TEXT_DIM,
        )
        self.screen.blit(info, (bx, row2))
        self._draw_legend(row2)

    def _draw_legend(self, y):
        """Legenda topo-direita com os MESMOS ícones usados no mundo."""
        surf_w = self.screen.get_width()
        margin = 16
        entries = [("health", "Primeiros socorros (cura)"),
                   ("tnt", "TNT (dano em área)")]
        gap = 26
        total = sum(gap + self.font_small.size(text)[0] for _, text in entries)
        x = surf_w - total - margin
        icon_center = y + 9
        for kind, text in entries:
            label = self.font_small.render(text, True, COLOR_TEXT_DIM)
            if kind == "health":
                self._draw_health_icon(x + 7, icon_center, 6)
            else:
                self._draw_tnt_icon(x + 7, icon_center, 0.34)
            self.screen.blit(label, (x + gap, y))
            x += gap + label.get_width()

    def _draw_center_text(self, title, subtitle, color=COLOR_TEXT):
        w, h = self.screen.get_size()
        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 170))
        self.screen.blit(bg, (0, 0))
        t1 = self.font_big.render(title, True, color)
        t2 = self.font.render(subtitle, True, COLOR_TEXT_DIM)
        self.screen.blit(t1, (w // 2 - t1.get_width() // 2, h // 2 - 40))
        self.screen.blit(t2, (w // 2 - t2.get_width() // 2, h // 2 + 20))

    def _draw_menu(self):
        w, h = self.screen.get_size()
        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 200))
        self.screen.blit(bg, (0, 0))

        title = self.font_big.render("SIMPLES WORLD", True, COLOR_PLAYER)
        self.screen.blit(title, (w // 2 - title.get_width() // 2, 80))

        lines = [
            "Representação do mundo de um jogo simples",
            "",
            "Sobreviva por %d segundos em uma malha de %dx%d áreas." % (
                int(self.survival_time), self.world.cols, self.world.rows),
            "Inimigos perseguem você em linha reta. Apenas as áreas próximas",
            "ficam ativas e só os NPCs das áreas ativas são atualizados.",
            "",
            "Primeiros socorros (+): recuperam a saúde",
            "TNT: causa dano aos inimigos ao redor",
            "",
            "[WASD / Setas] mover   [P] pausar   [R] reiniciar   [Q] sair",
        ]
        y = 180
        for i, line in enumerate(lines):
            if i == 0:
                y += 10
                continue
            color = COLOR_TEXT if i < len(lines) - 3 else COLOR_TEXT_DIM
            img = self.font.render(line, True, color)
            self.screen.blit(img, (w // 2 - img.get_width() // 2, y))
            y += 34

        hint = self.font_med.render("Pressione ENTER para começar", True, COLOR_AMMO)
        self.screen.blit(hint, (w // 2 - hint.get_width() // 2, h - 120))


def load_config(path: str | None = None) -> dict:
    if path is None:
        path = Path(__file__).parent / "config.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


async def main():
    config = load_config(sys.argv[1] if len(sys.argv) > 1 else None)
    await Game(config).run()


if __name__ == "__main__":
    asyncio.run(main())