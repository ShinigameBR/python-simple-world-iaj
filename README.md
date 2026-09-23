# Simple World — Representação do Mundo (IA para Jogos I)

Nível de jogo com **9 áreas em uma malha regular 3×3**, itens coletáveis
(primeiros socorros e munição/TNT) e NPCs que perseguem o jogador em linha
reta. A **viewport é independente da malha** e, a cada iteração, um **anel
de carregamento** mantém ativas as áreas ao redor do jogador — **no máximo
4** — tendo somente os NPCs dessas áreas atualizados.

Objetivo: **sobreviver pelo tempo configurado** (`survival_time`,
padrão 90s).

## 🕹️ Jogar agora (no navegador)

Compilado para WebAssembly com **pygbag** e hospedado no **GitHub Pages**:

**https://ShinigameBR.github.io/python-simple-world-iaj/**

## Executar

```bash
python -m venv .venv                 # (opcional, recomendado) cria ambiente virtual
.venv\Scripts\activate               # Windows       |  source .venv/bin/activate (Linux/macOS)
pip install -r requirements.txt
python main.py                # jogo com janela pygame
python main.py outro.json     # joga com outra configuração (padrão/template em config.json)
```

Se não usar venv, basta `pip install -r requirements.txt`.

## Controles

| Tecla | Ação |
|---|---|
| WASD / Setas | Mover |
| P | Pausar |
| R | Reiniciar nível |
| ENTER | Começar (menu) |
| ESC / Q | Menu / Sair |

## Modelo (sem gráficos) e testes

```bash
python -m game.tests          # testes do modelo (áreas ativas, dano, coleta, morte)
python -m game.simulation [N] # balanceamento: N partidas por cenário (padrão 20)
python -m game.smoke_test     # smoke test da renderização (sem abrir janela)
```

O relatório de balanceamento fica em `docs/balance_report.md` e a solução
escrita (documento para entrega, com escolhas de projeto e link de teste)
em `docs/solucao.md` / `docs/solucao.pdf`.

## Estrutura

```
main.py                 — loop pygame, input, estados, HUD, renderização
config.json             — estado inicial e parâmetros do mundo (JSON)
game/
  world.py              — Area e World: malha, áreas ativas, atualização seletiva
  entities.py           — Player, NPC, Item
  camera.py             — Viewport (janela independente da malha)
  simulation.py         — análise headless de balanceamento
  tests.py              — testes do modelo
  smoke_test.py         — smoke test da renderização
docs/
  solucao.md/.pdf       — documento da entrega
  balance_report.md     — relatório de balanceamento gerado
  screenshot*           — capturas de tela
```