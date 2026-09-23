"""Testes rápidos do modelo (sem pygame). Rodar: python -m game.tests"""

from __future__ import annotations

import json
from pathlib import Path

from .world import World

BASE = json.loads((Path(__file__).parent.parent / "config.json").read_text(encoding="utf-8"))


def test_basic():
    w = World(BASE, )
    p = w.populate()
    w.update_active_areas()
    assert len(w.active_cells) <= BASE["max_active_areas"]
    assert p is not None
    assert w.total_npcs >= 9
    assert all(len(a.npcs) > 0 for row in w.areas for a in row)
    viewport = w.areas[1][1]
    assert viewport.active  # área central deve estar ativa
    print(f"[ok] populate + áreas ativas {len(w.active_cells)} <= 4, área central ativa")


def test_activation_ring_default():
    """Com o raio padrão, os vizinhos ao redor ficam ativos mesmo no centro
    (inimigos não "desaparecem")."""
    cfg = json.loads(json.dumps(BASE))
    cfg["npc"]["per_area_range"] = [1, 1]
    cfg["npc"]["contact_damage"] = 0
    w = World(cfg)
    w.populate()
    w.update_active_areas()
    center_cell = w.areas[1][1]
    assert center_cell.active
    # ao menos um vizinho deve estar ativo com o anel de carregamento
    assert len(w.active_cells) >= 2, f"anel de carregamento ausente: {w.active_cells}"
    assert len(w.active_cells) <= w.max_active, f"excedeu o limite: {w.active_cells}"
    print(f"[ok] anel ao redor: {len(w.active_cells)} áreas ativas no centro {w.active_cells}")


def test_activation_boundary():
    """Com ativação curta, uma área vizinha só ativa-se perto da borda."""
    cfg = json.loads(json.dumps(BASE))
    cfg["activation_distance"] = 50
    cfg["npc"]["per_area_range"] = [1, 1]
    cfg["npc"]["contact_damage"] = 0
    w = World(cfg)
    p = w.populate()
    w.update_active_areas()
    cur = (p.x // w.size, p.y // w.size)
    before = len(w.active_cells)
    assert cur == (1, 1)

    # no centro da área central só ela deve estar ativa
    assert w.active_cells == [(1, 1)], f"esperado só a central, veio {w.active_cells}"

    # move o jogador para perto da borda direita da área central
    p.x = w.size - 1
    p.y = w.size / 2
    w.update_active_areas()
    cells = w.active_cells
    assert (1, 0) in cells, f"vizinha à direita deveria ativar-se, ativas={cells}"
    assert len(cells) <= w.max_active
    print(f"[ok] ativação na borda: {before} -> {len(cells)} áreas ativas {cells}")


def test_npc_chase_and_death():
    cfg = json.loads(json.dumps(BASE))
    cfg["npc"]["per_area_range"] = [1, 1]
    cfg["npc"]["contact_damage"] = 50
    cfg["npc"]["speed"] = 0
    w = World(cfg)
    p = w.populate()
    w.update_active_areas()
    npc = w.active_areas[0].npcs[0]
    npc.x, npc.y = p.x + 15, p.y  # sobreposto (raio 8+10=18 > 15)
    w.update(1.0)
    assert p.health < p.max_health, "dano de contato deveria reduzir a saúde"
    print(f"[ok] dano de contato aplicado: HP {p.health:.1f}")


def test_ammo_damage():
    cfg = json.loads(json.dumps(BASE))
    cfg["ammo_effect"] = {"radius": 1e6, "damage": 1e9}
    cfg["npc"]["per_area_range"] = [5, 5]
    w = World(cfg)
    p = w.populate()
    # encontra uma munição e move o jogador para cima dela
    for row in w.areas:
        for area in row:
            for it in area.items:
                if it.kind == "ammo":
                    p.x, p.y = it.x, it.y
                    w.update_active_areas()
                    w.update(0.1)
                    assert w.remaining_npcs == 0, "todos os NPCs deveriam morrer"
                    print(f"[ok] munição eliminou todos os NPCs (abates={p.kills})")
                    return


def test_npc_migration():
    """NPC que cruza a fronteira deve migrar para a área de destino, senão
    "some" quando a área antiga for desativada."""
    cfg = json.loads(json.dumps(BASE))
    cfg["activation_distance"] = 50
    cfg["npc"]["per_area_range"] = [1, 1]
    cfg["npc"]["contact_damage"] = 0
    cfg["npc"]["speed"] = 300
    w = World(cfg)
    p = w.populate()
    # jogador perto da borda direita da área CENTRAL (col 1, row 1)
    p.x, p.y = 2 * w.size - 1, 1.5 * w.size
    w.update_active_areas()
    central = w.areas[1][1]
    right = w.areas[1][2]  # vizinha à direita da central
    assert right.active and central.active
    npc = right.npcs[0]
    npc.x, npc.y = 2 * w.size + 15, 1.5 * w.size  # área direita, próxima à fronteira
    dt = 1.0 / 60.0
    for _ in range(int(0.5 / dt)):
        w.update(dt)
        if npc.area is central:
            break
    assert npc.area is central, "NPC deveria migrar para a área central"
    assert npc in central.npcs and npc not in right.npcs
    print("[ok] NPC migrou da área direita para a central ao cruzar a fronteira")


def test_survival_objective():
    cfg = json.loads(json.dumps(BASE))
    cfg["npc"]["per_area_range"] = [2, 2]
    cfg["npc"]["contact_damage"] = 1000  # garante morte rápida
    w = World(cfg)
    p = w.populate()
    dt = 1.0 / 60.0
    for _ in range(int(5.0 / dt)):
        w.update(dt)
        if p.health <= 0:
            break
    assert p.health <= 0 and not p.alive
    print("[ok] jogador morre; objetivo de sobrevivência é perdido")


if __name__ == "__main__":
    test_basic()
    test_activation_ring_default()
    test_activation_boundary()
    test_npc_migration()
    test_npc_chase_and_death()
    test_ammo_damage()
    test_survival_objective()
    print("TODOS OS TESTES PASSARAM")