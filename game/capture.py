"""Captura screenshots para inspeção. Uso: python -m game.capture"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, str(Path(__file__).parent.parent))
import pygame  # noqa: E402

from main import Game, load_config  # noqa: E402


def main():
    cfg = load_config()
    cfg.setdefault("player", {})["health"] = 100000  # invencível p/ screenshot
    cfg.setdefault("npc", {})["contact_damage"] = 0
    game = Game(cfg)
    out = Path(__file__).parent.parent / "docs" / "screenshots"
    out.mkdir(exist_ok=True)

    # tela inicial
    game.state = "MENU"
    game.draw()
    pygame.image.save(game.screen, str(out / "menu.png"))

    # jogando: movimenta o jogador para a borda para ativar áreas vizinhas
    game.state = "PLAYING"
    dt = 1.0 / 30.0
    for i in range(60):
        game.world.player.set_input(1.0, 0.0)
        game._step(dt)
    game.draw()
    pygame.image.save(game.screen, str(out / "play.png"))

    # pausado
    game.state = "PAUSED"
    game.draw()
    pygame.image.save(game.screen, str(out / "paused.png"))

    pygame.quit()
    print("screenshots salvos em", out)


if __name__ == "__main__":
    main()