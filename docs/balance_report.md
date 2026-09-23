# Relatório de balanceamento

Gerado por `python -m game.simulation 20` (1 seed = 1 partida completa).
Política do jogador: gulosa (cura quando ferido, senão busca munição).

| Cenário | Inimigos | Taxa de sobrevivência | HP final médio | Abates médios | Morte aos (s) | Áreas ativas médias |
|---|---|---|---|---|---|---|
| 1. Baseline (3x3, areas 600px) | 600px x9 (4-9/area) | 50% | 45.8 | 52 | 75.7 | 4.0 |
| 2. Dezenas de inimigos | 600px x9 (3-5/area) | 70% | 66.3 | 33 | 80.3 | 4.0 |
| 3. Centenas de inimigos | 600px x9 (40-60/area) | 0% | 0.0 | 46 | 3.4 | 4.0 |
| 4. Milhares de inimigos | 600px x9 (300-500/area) | 0% | 0.0 | 28 | 0.5 | 4.0 |
| 5. Areas pequenas (300px) | 300px x9 (4-9/area) | 100% | 98.5 | 59 | - | 4.0 |
| 6. Areas grandes (900px) | 900px x9 (4-9/area) | 30% | 21.0 | 35 | 57.8 | 3.95 |
| 7. Ativacao curta (100px) | 600px x9 (4-9/area) | 100% | 95.4 | 53 | - | 1.23 |
| 8. Ativacao longa (500px) | 600px x9 (4-9/area) | 65% | 60.9 | 52 | 72.9 | 3.32 |
| 9. NPC veloz (speed 220) | 600px x9 (4-9/area) | 15% | 15.0 | 21 | 5.6 | 4.0 |
| 10. Contato mortal (dano 60/s) | 600px x9 (4-9/area) | 25% | 23.9 | 32 | 22.5 | 4.0 |
| 11. Sobreviver 30s | 600px x9 (4-9/area) | 100% | 84.8 | 52 | - | 4.0 |
| 12. Sobreviver 180s | 600px x9 (4-9/area) | 40% | 37.2 | 52 | 80.9 | 4.0 |
