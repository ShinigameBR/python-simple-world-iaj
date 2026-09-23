"""Smoke test do jogo sem abrir janela (SDL dummy). Uso: python -m game.smoke_test"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent))
from main import Game, load_config  # noqa: E402


def main():
    cfg = load_config()
    game = Game(cfg)
    game.state = "PLAYING"
    dt = 1.0 / 30.0
    game._step(dt)
    game._step(dt)
    game.camera.follow(game.world.player.x, game.world.player.y,
                       game.world.width, game.world.height, dt)
    game.state = "MENU"
    game.draw()
    game.state = "PLAYING"
    game._step(dt)
    game.draw()
    # força vitória e derrota
    game.world.player.health = 1e9
    game.time_start = 0.0
    game.survival_time = -1.0
    game._step(dt)
    assert game.state == "WON"
    game.state = "LOST"
    game.draw()
    pygame.quit()
    print("[ok] smoke test: menu/hud/won/lost renderizados sem erro")


if __name__ == "__main__":
    main()