"""Representação do mundo como malha regular de áreas.

O mundo é discretizado em uma malha regular (grid) de áreas. Cada área
concentra suas próprias entidades (NPCs e itens), permitindo que o estado
do mundo seja parcialmente ativado: apenas as áreas próximas ao jogador
ficam ativas e somente os NPCs dessas áreas são atualizados a cada
iteração da simulação (atualização seletiva).
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING, Optional

from .entities import Item, NPC, Player

if TYPE_CHECKING:
    pass


class Area:
    """Uma célula da malha: região finita que agrupa NPCs e itens."""

    def __init__(self, col: int, row: int, size: float):
        self.col = col
        self.row = row
        self.size = size
        self.left = col * size
        self.top = row * size
        self.right = self.left + size
        self.bottom = self.top + size
        self.npcs: list[NPC] = []
        self.items: list[Item] = []
        self.active = False

    @property
    def center(self) -> tuple[float, float]:
        return ((self.left + self.right) / 2.0, (self.top + self.bottom) / 2.0)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return (self.left, self.top, self.right, self.bottom)

    def __repr__(self) -> str:  # pragma: no cover - apenas debug
        return f"Area(col={self.col}, row={self.row}, active={self.active})"


class World:
    """Modelo do mundo: malha regular de 9 (ou mais) áreas + estado global."""

    def __init__(self, config: dict, rng: Optional[random.Random] = None):
        self.config = config
        self.cols = int(config["grid_cols"])
        self.rows = int(config["grid_rows"])
        self.size = float(config["area_size"])
        self.max_active = int(config.get("max_active_areas", 4))
        self.activation_distance = float(config.get("activation_distance", 0.4 * self.size))
        self.rng = rng or random.Random(config.get("random_seed"))

        self.areas: list[list[Area]] = [
            [Area(c, r, self.size) for c in range(self.cols)]
            for r in range(self.rows)
        ]
        self.width = self.cols * self.size
        self.height = self.rows * self.size
        self.player: Optional[Player] = None
        self.time = 0.0
        self.active_cells: list[tuple[int, int]] = []
        self.explosions: list[dict] = []  # eventos de TNT consumidos pela view/render

    # ------------------------------------------------------------------
    # Helpers espaciais
    # ------------------------------------------------------------------
    def cell_of(self, x: float, y: float) -> tuple[int, int]:
        c = max(0, min(self.cols - 1, int(x // self.size)))
        r = max(0, min(self.rows - 1, int(y // self.size)))
        return c, r

    def area_of(self, x: float, y: float) -> Area:
        c, r = self.cell_of(x, y)
        return self.areas[r][c]

    @staticmethod
    def distance_to_area(x: float, y: float, area: Area) -> float:
        """Distância de um ponto até a região da área (0 se estiver dentro)."""
        cx = min(max(x, area.left), area.right)
        cy = min(max(y, area.top), area.bottom)
        return math.hypot(x - cx, y - cy)

    # ------------------------------------------------------------------
    # Criação do nível
    # ------------------------------------------------------------------
    def random_point_in_area(self, area: Area, margin: float = 24.0) -> tuple[float, float]:
        x = self.rng.uniform(area.left + margin, area.right - margin)
        y = self.rng.uniform(area.top + margin, area.bottom - margin)
        return x, y

    def populate(self) -> Player:
        """Distribui o jogador, NPCs e itens pelo mundo."""
        pc = self.config["player"]
        nc = self.config["npc"]
        ic = self.config.get("items", {"health_per_area": 3, "ammo_per_area": 2})

        px, py = self.width / 2.0, self.height / 2.0
        self.player = Player(
            px, py,
            health=pc["health"],
            radius=pc["radius"],
            speed=pc["speed"],
            health_per_pickup=pc.get("health_per_pickup", 40.0),
            ammo_radius=self.config.get("ammo_effect", {}).get("radius", 180.0),
            ammo_damage=self.config.get("ammo_effect", {}).get("damage", 100.0),
        )

        lo, hi = nc["per_area_range"]
        for row in self.areas:
            for area in row:
                count = self.rng.randint(lo, hi)
                for _ in range(count):
                    x, y = self.random_point_in_area(area)
                    npc = NPC(
                        x, y,
                        speed=nc["speed"],
                        health=nc["health"],
                        radius=nc["radius"],
                        contact_damage=nc["contact_damage"],
                    )
                    npc.area = area
                    area.npcs.append(npc)

                for _ in range(ic.get("health_per_area", 3)):
                    x, y = self.random_point_in_area(area)
                    area.items.append(Item("health", x, y))
                for _ in range(ic.get("ammo_per_area", 2)):
                    x, y = self.random_point_in_area(area)
                    area.items.append(Item("ammo", x, y))

        self.total_npcs = sum(len(a.npcs) for row in self.areas for a in row)
        return self.player

    # ------------------------------------------------------------------
    # Áreas ativas (viewport lógico / escopo de percepção)
    # ------------------------------------------------------------------
    def update_active_areas(self) -> list[tuple[int, int]]:
        """Define, no máximo, `max_active` áreas ativas (anel ao redor do jogador).

        A área atual é sempre ativa. As áreas vizinhas (8-vizinhança) do
        jogador formam o "anel de carregamento": as mais próximas à sua
        borda entram no conjunto até preencher `max_active` vagas, desde que
        estejam dentro do raio de ativação (`activation_distance`). Com o
        raio padrão (1.6x o tamanho da área), os vizinhos ao redor ficam
        sempre ativos — evitando que os inimigos "desapareçam" quando o
        jogador está no centro ou cruza para outra área.
        """
        x, y = self.player.x, self.player.y
        c0, r0 = self.cell_of(x, y)
        current = self.areas[r0][c0]

        candidates: list[tuple[float, Area]] = []
        for row in self.areas:
            for area in row:
                if area is current:
                    continue
                if abs(area.col - c0) > 1 or abs(area.row - r0) > 1:
                    continue  # apenas vizinhas (anel de carregamento)
                d = self.distance_to_area(x, y, area)
                if d <= self.activation_distance:
                    candidates.append((d, area))
        candidates.sort(key=lambda t: t[0])

        active = [current]
        for _, area in candidates[: self.max_active - 1]:
            active.append(area)

        self.active_cells = []
        for row in self.areas:
            for area in row:
                area.active = area in active
                if area.active:
                    self.active_cells.append((area.col, area.row))
        return self.active_cells

    @property
    def active_areas(self) -> list[Area]:
        return [a for row in self.areas for a in row if a.active]

    # ------------------------------------------------------------------
    # Simulação (discreta, passo fixo dt)
    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        if self.player is None:
            return
        self.time += dt
        self.update_active_areas()

        # Apenas NPCs de áreas ativas são atualizados.
        # (print sobre uma cópia das listas: NPCs podem migrar de área.)
        active_npcs = [npc for area in self.active_areas for npc in list(area.npcs)]
        for npc in active_npcs:
            npc.chase(self.player, dt)
            npc.contact_damage_to(self.player, dt)
        self._migrate_npcs()

        # Coleta de itens (itens visíveis/ativos).
        for area in self.active_areas:
            for item in list(area.items):
                if item.taken:
                    continue
                if self.distance_to_player(item) < Item.PICKUP_RADIUS:
                    self._apply_item(item)

        self._cleanup()

    def _migrate_npcs(self) -> None:
        """Migra NPCs que cruzaram a fronteira para a área (célula) correta.

        Sem isso, um inimigo que fisicamente entra em uma área ativa
        continuaria registrado na lista da área antiga — e sumiria quando
        ela fosse desativada, mesmo estando dentro do anel de carregamento.
        """
        for npc in list(self._all_npcs()):
            dest = self.area_of(npc.x, npc.y)
            if dest is npc.area:
                continue
            if npc.area is not None:
                npc.area.npcs.remove(npc)
            dest.npcs.append(npc)
            npc.area = dest

    def _all_npcs(self) -> list:
        return [npc for row in self.areas for area in row for npc in area.npcs]

    def distance_to_player(self, item) -> float:
        return math.hypot(self.player.x - item.x, self.player.y - item.y)

    def _apply_item(self, item: Item) -> None:
        if item.kind == "health":
            self.player.heal(self.player.health_per_pickup)
            self.player.health_picked += 1
        elif item.kind == "ammo":
            self.player.ammo_picked += 1
            # Dano em área: inimigos ao redor sofrem danos.
            counter = 0
            for row in self.areas:
                for area in row:
                    for npc in list(area.npcs):
                        if math.hypot(npc.x - self.player.x, npc.y - self.player.y) <= self.player.ammo_radius:
                            npc.health -= self.player.ammo_damage
                            counter += 1
            self.player.kills += counter
            if counter > 0:
                self.explosions.append({"x": item.x, "y": item.y, "radius": self.player.ammo_radius})
        item.taken = True

    def _cleanup(self) -> None:
        for row in self.areas:
            for area in row:
                area.npcs = [npc for npc in area.npcs if npc.health > 0]
                area.items = [it for it in area.items if not it.taken]
        if self.player is not None and self.player.health <= 0:
            self.player.alive = False

    @property
    def remaining_npcs(self) -> int:
        return sum(len(a.npcs) for row in self.areas for a in row)

    @property
    def remaining_items(self) -> int:
        return sum(len(a.items) for row in self.areas for a in row)