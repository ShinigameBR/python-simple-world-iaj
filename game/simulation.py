"""Simulação headless para análise de balanceamento.

Roda o modelo do mundo sem pygame, sob uma política simples e
determinística de "jogador" (guloso: busca cura quando ferido, senão
busca munição para limpar inimigos). Permite comparar cenários com
dezenas/centenas/milhares de inimigos, tamanhos de área, distâncias de
ativação, dano, velocidade e tempo de sobrevivência.

Execução:
    python -m game.simulation [sementes_por_cenario]
"""

from __future__ import annotations

import copy
import json
import math
import random
import sys
from pathlib import Path

from .world import World

BASE = json.loads((Path(__file__).parent.parent / "config.json").read_text(encoding="utf-8"))


def greedy_policy(world: World, dt: float) -> None:
    """Política simples: cura se ferido; senão busca munição; senão fica parado."""
    p = world.player
    if p is None or p.health <= 0:
        return

    best_health = None
    best_ammo = None
    bd_h = float("inf")
    bd_a = float("inf")
    for row in world.areas:
        for area in row:
            for item in area.items:
                if item.taken:
                    continue
                d = world.distance_to_player(item)
                if item.kind == "health" and d < bd_h:
                    bd_h, best_health = d, item
                elif item.kind == "ammo" and d < bd_a:
                    bd_a, best_ammo = d, item

    target = best_health if p.health < 0.8 * p.max_health else best_ammo
    if target is not None:
        dx = target.x - p.x
        dy = target.y - p.y
        norm = math.hypot(dx, dy)
        if norm > 1e-6:
            p.set_input(dx / norm, dy / norm)
            return
    p.set_input(0.0, 0.0)


def run_once(config: dict, duration: float, seed: int) -> dict:
    """Executa uma partida headless e devolve estatísticas."""
    world = World(config, rng=random.Random(seed))
    world.populate()
    dt = 1.0 / 60.0
    t = 0.0
    total_active_frames = 0
    frames = 0
    survival = duration
    survived = True

    while t < duration and world.player.health > 0:
        if frames % 5 == 0:
            greedy_policy(world, dt)
        world.player.update(dt, world.width, world.height)
        world.update(dt)
        total_active_frames += len(world.active_cells)
        frames += 1
        t += dt

    if world.player.health <= 0:
        survived = False
        survival = t

    return {
        "seed": seed,
        "survived": survived,
        "survival_time": survival,
        "final_health": max(0.0, round(world.player.health, 1)),
        "kills": world.player.kills,
        "health_picked": world.player.health_picked,
        "ammo_picked": world.player.ammo_picked,
        "remaining_npcs": world.remaining_npcs,
        "mean_active": round(total_active_frames / max(1, frames), 2),
        "total_npcs": world.total_npcs,
    }


# ----------------------------------------------------------------------
# Cenários de balanceamento
# ----------------------------------------------------------------------
def _variant(**overrides) -> dict:
    cfg = copy.deepcopy(BASE)
    for key, value in overrides.items():
        if isinstance(value, dict):
            dst = cfg.setdefault(key, {})
            dst.update(value)
        else:
            cfg[key] = value
    return cfg


def scenarios() -> list[tuple[str, dict]]:
    return [
        ("1. Baseline (3x3, areas 600px)", _variant()),
        ("2. Dezenas de inimigos", _variant(**{"npc": {"per_area_range": [3, 5]}})),
        ("3. Centenas de inimigos", _variant(**{"npc": {"per_area_range": [40, 60]}})),
        ("4. Milhares de inimigos", _variant(**{"npc": {"per_area_range": [300, 500]}})),
        ("5. Areas pequenas (300px)", _variant(area_size=300)),
        ("6. Areas grandes (900px)", _variant(area_size=900)),
        ("7. Ativacao curta (100px)", _variant(activation_distance=100)),
        ("8. Ativacao longa (500px)", _variant(activation_distance=500)),
        ("9. NPC veloz (speed 220)", _variant(**{"npc": {"speed": 220}})),
        ("10. Contato mortal (dano 60/s)", _variant(**{"npc": {"contact_damage": 60}})),
        ("11. Sobreviver 30s", _variant(survival_time=30)),
        ("12. Sobreviver 180s", _variant(survival_time=180)),
    ]


def summary(results: list[dict]) -> dict:
    n = len(results)
    survived = sum(1 for r in results if r["survived"])
    mean_death = sum(r["survival_time"] for r in results if not r["survived"])
    deaths = n - survived
    return {
        "seed": results[0]["seed"] if results else 0,
        "survival_rate": survived / max(1, n),
        "mean_final_health": round(sum(r["final_health"] for r in results) / max(1, n), 1),
        "mean_kills": round(sum(r["kills"] for r in results) / max(1, n), 1),
        "mean_death_time": round(mean_death / max(1, deaths), 1) if deaths else None,
        "mean_active": round(sum(r["mean_active"] for r in results) / max(1, n), 2),
        "total_npcs": results[0]["total_npcs"] if results else 0,
        "remaining_npcs": round(sum(r["remaining_npcs"] for r in results) / max(1, n), 1),
        "survival_time": results[0].get("survival_time_target", None),
    }


def main(n_seeds: int = 20) -> str:
    lines = [
        "# Relatório de balanceamento",
        "",
        f"Gerado por `python -m game.simulation {n_seeds}` (1 seed = 1 partida completa).",
        "Política do jogador: gulosa (cura quando ferido, senão busca munição).",
        "",
        "| Cenário | Inimigos | Taxa de sobrevivência | HP final médio | "
        "Abates médios | Morte aos (s) | Áreas ativas médias |",
        "|---|---|---|---|---|---|---|",
    ]
    rows = []
    for name, cfg in scenarios():
        res = [run_once(cfg, float(cfg.get("survival_time", 90)), seed=i) for i in range(n_seeds)]
        s = summary(res)
        rows.append((name, config_totals(cfg), s, res))

    for name, totals, s, res in rows:
        death = f"{s['mean_death_time']:.1f}" if s["mean_death_time"] is not None else "-"
        survived = f"{s['survival_rate'] * 100:.0f}%"
        lines.append(
            f"| {name} | {totals} | {survived} | {s['mean_final_health']} | "
            f"{s['mean_kills']:.0f} | {death} | {s['mean_active']} |"
        )
    report = "\n".join(lines)

    out = Path(__file__).parent.parent / "docs" / "balance_report.md"
    out.write_text(report + "\n", encoding="utf-8")
    print(report)
    return report


def config_totals(cfg: dict) -> int:
    size = int(cfg["area_size"])
    area_count = int(cfg["grid_cols"]) * int(cfg["grid_rows"])
    per_area = f"{cfg['npc']['per_area_range'][0]}-{cfg['npc']['per_area_range'][1]}"
    return f"{size}px x{area_count} ({per_area}/area)"


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    main(n)