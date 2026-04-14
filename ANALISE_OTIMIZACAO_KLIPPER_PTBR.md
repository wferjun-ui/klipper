# Melhorias implementadas: calibração automática em ordem + teste guiado por velocidade

Atendendo ao pedido, a solução foi evoluída para um fluxo mais automático e prático:

1. botão de **calibração inicial automática**;
2. botão de **teste por velocidade desejada** com cálculo automático;
3. botão de **execução completa (all-in-one)**;
4. pós-teste com perguntas/instruções de ajuste.

---

## 1) Correções reais de fragilidade em função do Klipper

Arquivo: `klippy/extras/screws_tilt_adjust.py`

- Corrigido edge-case de arredondamento que podia resultar em `:60` minutos no ajuste.
- Tornada explícita a validação de desvio máximo com `is not None`.

Resultado: saída mais estável e validação mais previsível.

---

## 2) Calibração automática “na ordem correta”

Arquivo: `config/sample-calibration-wizard.cfg`

Macro principal: `CAL_AUTO_BASELINE` (botão `CAL_BTN_BASELINE`)

Ordem automática:
1. `G28`
2. nivelamento condicional pela arquitetura (`QUAD_GANTRY_LEVEL` / `Z_TILT_ADJUST` / `SCREWS_TILT_CALCULATE`)
3. `BED_MESH_CLEAR` + `BED_MESH_CALIBRATE` (quando disponível)
4. orientação de refinamento final para `PROBE_CALIBRATE`.

---

## 3) Teste automático por velocidade desejada

Macro principal: `CAL_AUTO_SPEED_TEST TARGET_SPEED=<mm/s>` (botão `CAL_BTN_SPEED_TEST`)

Implementação:
- recebe velocidade alvo do usuário,
- aplica clamp pelos limites do cfg (`max_velocity`, `max_accel`),
- calcula automaticamente `ACCEL`, `ACCEL_TO_DECEL`, `SCV` iniciais,
- aplica via `SET_VELOCITY_LIMIT`,
- executa teste rápido integrado (`CAL_PRINT_QUICK_DIAGNOSTIC`).

Inclui mensagens de segurança e advertências de validação.

---

## 4) Pós-teste guiado com instruções de ajuste

Macros:
- `CAL_POST_TEST_REVIEW`
- `CAL_APPLY_USER_FEEDBACK`

Pós-teste orienta o usuário com regras objetivas:
- blob em cantos -> reduzir PA,
- canto vazio -> aumentar PA,
- ringing -> reduzir aceleração,
- linhas faltando -> reduzir velocidade,
- canto arredondado -> reduzir SCV,
- impacto agressivo -> reduzir `ACCEL_TO_DECEL`.

---

## 5) Botão para executar tudo junto

Macro: `CAL_BTN_ALL_IN_ONE TARGET_SPEED=<mm/s>`

Executa:
1. baseline automático,
2. cálculo de parâmetros + teste rápido,
3. pronto para revisão guiada.

---

## 6) Limitações transparentes

- “Perfeição teórica” absoluta não é garantível sem iteração, porque material/temperatura/estado real variam.
- A implementação gera **ponto inicial otimizado e seguro**, depois converge com feedback visual do usuário.

Esse é o caminho mais robusto para chegar perto do ideal com segurança.
