"""Versão web do jogo, executada no Pyodide (CPython em WebAssembly).

Este módulo reusa exatamente o mesmo modelo do jogo em `game/` e troca apenas a
camada de apresentação: em vez de desenhar com pygame, ele publica o estado do
mundo em um dicionário simples e deixa o JavaScript desenhar no canvas.

O loop é conduzido pelo JavaScript (requestAnimationFrame), que chama
`GameWeb.step()` a cada quadro. Não existe pygame aqui, então a dependência de
canvas/sdl2 desaparece e a página carrega normalmente no GitHub Pages.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from game.camera import Viewport
from game.entities import NPC, Player
from game.world import World

CONFIG_NAME = "config.json"
_HERE = Path(__file__).resolve().parent


def _find_config() -> Path:
    """Procura o config.json perto do modulo, na raiz ou um nivel acima."""
    for base in (_HERE, _HERE.parent):
        candidate = base / CONFIG_NAME
        if candidate.is_file():
            return candidate
    return _HERE / CONFIG_NAME

# Estados possíveis da sessão de jogo.
MENU, PLAYING, PAUSED, WON, LOST = "MENU", "PLAYING", "PAUSED", "WON", "LOST"


def load_config(path: str | None = None) -> dict:
    with open(path or _find_config(), encoding="utf-8") as f:
        return json.load(f)


class GameWeb:
    """Mesma mecânica de `main.py`, publicando o estado para o canvas."""

    def __init__(self, config: dict | None = None):
        self.config = config or load_config()
        self.vp_cfg = self.config.get("viewport", {})
        self.zoom = float(self.config.get("viewport_zoom", 1.75))
        self.vp = Viewport(
            float(self.vp_cfg.get("width", 1280)),
            float(self.vp_cfg.get("height", 720)),
            self.zoom,
        )

        self.rng = random.Random(self.config.get("random_seed", 42))
        self.world = World(self.config, rng=self.rng)
        self.world.populate()

        self.state = MENU
        self.time_left = float(self.config.get("survival_time", 90.0))
        self.kills = 0
        self.world.update_active_areas()
        self._center_camera()

        # explosões visuais, em coordenadas do mundo
        self.effects: list[dict] = []

    # ------------------------------------------------------------------
    # Entrada
    # ------------------------------------------------------------------
    def _center_camera(self) -> None:
        """Posiciona a viewport centrada no jogador, limitada as bordas."""
        w = self.world
        self.vp.x = max(0.0, min(w.width - self.vp.world_width,
                                 w.player.x - self.vp.world_width / 2.0))
        self.vp.y = max(0.0, min(w.height - self.vp.world_height,
                                 w.player.y - self.vp.world_height / 2.0))

    def set_input(self, dx: float, dy: float) -> None:
        self.world.player.set_input(float(dx), float(dy))

    def start(self) -> None:
        if self.state == MENU:
            self.state = PLAYING

    def toggle_pause(self) -> None:
        if self.state == PLAYING:
            self.state = PAUSED
        elif self.state == PAUSED:
            self.state = PLAYING

    def to_menu(self) -> None:
        self.state = MENU

    def resize(self, width: float, height: float) -> None:
        self.vp.width = float(width)
        self.vp.height = float(height)
        self._center_camera()

    def restart(self) -> None:
        seed = self.config.get("random_seed", 42)
        self.rng = random.Random(seed)
        self.world = World(self.config, rng=self.rng)
        self.world.populate()
        self.time_left = float(self.config.get("survival_time", 90.0))
        self.kills = 0
        self.effects.clear()
        self.world.update_active_areas()
        self._center_camera()
        self.state = PLAYING

    # ------------------------------------------------------------------
    # Simulação
    # ------------------------------------------------------------------
    def step(self, dt: float) -> None:
        if self.state != PLAYING:
            return

        dt = min(dt, 0.05)
        w = self.world
        player = w.player

        player.update(dt, w.width, w.height)
        w.update(dt)
        self.camera_follow(dt)

        # explosões do modelo viram efeitos visuais
        for event in w.explosions:
            self.effects.append({"x": event["x"], "y": event["y"],
                                 "r": event["radius"], "t": 0.0})
        w.explosions.clear()

        for effect in self.effects:
            effect["t"] += dt
        self.effects = [e for e in self.effects if e["t"] < 0.6]

        self.kills = player.kills

        if not player.alive:
            self.state = LOST
        else:
            self.time_left -= dt
            if self.time_left <= 0.0:
                self.time_left = 0.0
                self.state = WON

    def camera_follow(self, dt: float) -> None:
        w = self.world
        self.vp.follow(w.player.x, w.player.y, w.width, w.height, dt)

    # ------------------------------------------------------------------
    # Saída para o renderizador JavaScript
    # ------------------------------------------------------------------
    def snapshot(self) -> dict:
        w = self.world
        player = w.player
        left, top, right, bottom = self.vp.visible_world()
        z = self.zoom
        # margens iguais as do pygame (items 40px, npcs 60px em espaco de tela)
        m_item = 40.0 / z
        m_npc = 60.0 / z
        npc_max = float(self.config.get("npc", {}).get("health", 100.0))

        npcs, items, areas = [], [], []
        for row in w.areas:
            for area in row:
                if area.right < left or area.bottom < top or area.left > right or area.top > bottom:
                    continue
                areas.append([area.col, area.row, area.left, area.top, area.size,
                              1 if area.active else 0])
        for area in w.active_areas:
            for npc in area.npcs:
                if left - m_npc <= npc.x <= right + m_npc and top - m_npc <= npc.y <= bottom + m_npc:
                    npcs.append([round(npc.x, 1), round(npc.y, 1), npc.radius,
                                 round(npc.health, 2)])
            for item in area.items:
                if left - m_item <= item.x <= right + m_item and top - m_item <= item.y <= bottom + m_item:
                    items.append([round(item.x, 1), round(item.y, 1), item.kind])

        return {
            "state": self.state,
            "time": round(w.time, 2),
            "timeLeft": round(self.time_left, 1),
            "health": round(player.health, 1),
            "maxHealth": player.max_health,
            "kills": self.kills,
            "healthPicked": player.health_picked,
            "ammoPicked": player.ammo_picked,
            "remainingNpcs": w.remaining_npcs,
            "activeCells": [list(c) for c in w.active_cells],
            "totalCells": w.cols * w.rows,
            "cols": w.cols,
            "rows": w.rows,
            "npcMaxHealth": npc_max,
            "survivalTime": float(self.config.get("survival_time", 90.0)),
            "player": [round(player.x, 1), round(player.y, 1), player.radius,
                       round(player.vx, 3), round(player.vy, 3)],
            "npcs": npcs,
            "areas": areas,
            "items": items,
            "effects": [[round(e["x"], 1), round(e["y"], 1),
                          round(e["r"], 1), round(e["t"] / 0.6, 4)]
                         for e in self.effects],
            "camera": [round(self.vp.x, 1), round(self.vp.y, 1),
                       round(self.vp.world_width, 1),
                       round(self.vp.world_height, 1)],
            "zoom": self.zoom,
            "grid": [w.cols, w.rows, w.size],
            "worldSize": [w.width, w.height],
        }

    def info_lines(self) -> list[str]:
        w = self.world
        return [
            "Sobreviva ate o tempo acabar.",
            "",
            f"Tempo restante: {max(0, int(self.time_left))}s",
            f"Vida: {max(0, int(self.world.player.health))}",
            f"Inimigos restantes: {w.remaining_npcs}",
            f"Areas ativas: {len(w.active_cells)} de {w.cols * w.rows}",
            "",
            "Movimente-se com WASD ou setas. O circulo azul e voce.",
            "Inimigos vermelhos perseguem em linha reta e ferem",
            "por contato. Os quadrados verdes sao primeiros",
            "socorros e os amareis sao TNT (dano em area).",
            "",
            "Apenas as areas proximas sao simuladas: as areas",
            "distantes ficam congeladas, sem custo de CPU.",
        ]
