"""Entidades do jogo: jogador, NPCs e itens coletáveis."""

from __future__ import annotations

import math
from typing import Any


class Entity:
    """Classe base de qualquer personagem com posição, vida e raio."""

    def __init__(self, x: float, y: float, health: float, radius: float):
        self.x = x
        self.y = y
        self.health = health
        self.radius = radius
        self.alive = health > 0

    def distance_to(self, other: "Entity") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


class Player(Entity):
    """Personagem controlado pelo jogador."""

    def __init__(self, x: float, y: float, health: float = 100.0,
                 radius: float = 14.0, speed: float = 220.0,
                 health_per_pickup: float = 40.0, ammo_radius: float = 180.0,
                 ammo_damage: float = 100.0, max_health: float | None = None):
        super().__init__(x, y, health, radius)
        self.speed = speed
        self.max_health = max_health or health
        self.health_per_pickup = health_per_pickup
        self.ammo_radius = ammo_radius
        self.ammo_damage = ammo_damage
        self.vx = 0.0
        self.vy = 0.0
        self.kills = 0
        self.health_picked = 0
        self.ammo_picked = 0

    def set_input(self, dx: float, dy: float) -> None:
        length = math.hypot(dx, dy)
        if length > 0:
            dx, dy = dx / length, dy / length
        self.vx = dx
        self.vy = dy

    def update(self, dt: float, world_width: float, world_height: float) -> None:
        self.x += self.vx * self.speed * dt
        self.y += self.vy * self.speed * dt
        self.x = max(0.0, min(world_width - 1e-6, self.x))
        self.y = max(0.0, min(world_height - 1e-6, self.y))

    def heal(self, amount: float) -> None:
        self.health = min(self.max_health, self.health + amount)


class NPC(Entity):
    """Inimigo controlado por automação simples (persegue em linha reta)."""

    def __init__(self, x: float, y: float, speed: float = 150.0,
                 health: float = 100.0, radius: float = 12.0,
                 contact_damage: float = 30.0):
        super().__init__(x, y, health, radius)
        self.speed = speed
        self.contact_damage = contact_damage
        self.area: Any = None  # área (célula da malha) à qual o NPC pertence

    def chase(self, target: Entity, dt: float) -> None:
        """Move-se em linha reta na direção do alvo."""
        dx = target.x - self.x
        dy = target.y - self.y
        length = math.hypot(dx, dy)
        if length < 1e-9:
            return
        self.x += (dx / length) * self.speed * dt
        self.y += (dy / length) * self.speed * dt

    def contact_damage_to(self, target: Entity, dt: float) -> None:
        """Aplica dano por segundo enquanto houver sobreposição."""
        if self.alive and self.distance_to(target) < self.radius + target.radius:
            target.health -= self.contact_damage * dt


class Item:
    """Item coletável. kind: 'health' (primeiros socorros) ou 'ammo' (munição)."""

    PICKUP_RADIUS = 12.0

    def __init__(self, kind: str, x: float, y: float):
        self.kind = kind
        self.x = x
        self.y = y
        self.taken = False