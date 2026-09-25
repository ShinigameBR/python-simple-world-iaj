"""Câmera/viewport: janela de visualização independente da malha.

A viewport é uma janela (retângulo) sobre o mundo, totalmente
dissociada da discretização em áreas da malha. Ela pode estar
posicionada em qualquer lugar e pode expor pedaços de várias áreas
simultaneamente. A câmera acompanha o jogador com uma interpolação
suave, fica limitada às bordas do mundo e pode "aproximar" a cena
(fator de zoom: quanto maior, menor a porção do mundo visível).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Viewport:
    """Janela de visualização em coordenadas do mundo."""

    width: float
    height: float
    zoom: float = 1.75

    def __init__(self, width: float, height: float, zoom: float = 1.75):
        self.width = width
        self.height = height
        self.zoom = zoom
        self.x = 0.0
        self.y = 0.0

    @property
    def world_width(self) -> float:
        return self.width / self.zoom

    @property
    def world_height(self) -> float:
        return self.height / self.zoom

    def follow(self, target_x: float, target_y: float, world_width: float,
               world_height: float, dt: float) -> None:
        """Centraliza (com suavização) o jogador e trava nas bordas."""
        center_x = target_x - self.world_width / 2.0
        center_y = target_y - self.world_height / 2.0
        lerp = min(1.0, 6.0 * dt)
        self.x += (center_x - self.x) * lerp
        self.y += (center_y - self.y) * lerp
        self.x = max(0.0, min(world_width - self.world_width, self.x))
        self.y = max(0.0, min(world_height - self.world_height, self.y))

    def to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        return ((wx - self.x) * self.zoom, (wy - self.y) * self.zoom)

    def visible_world(self) -> tuple[float, float, float, float]:
        """BBox do mundo visível: (left, top, right, bottom)."""
        return (self.x, self.y,
                self.x + self.world_width, self.y + self.world_height)