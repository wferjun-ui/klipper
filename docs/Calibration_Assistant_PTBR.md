# Calibração guiada e automática (baseline + teste por velocidade) no Klipper

Este guia implementa exatamente o fluxo solicitado:

1. botão para **calibração inicial automática na ordem correta**;
2. botão para **teste automático por velocidade desejada**;
3. botão para **executar tudo junto**;
4. cálculo automático de parâmetros com **respeito aos limites do cfg**;
5. aviso de segurança + checklist pós-teste com recomendações de ajuste.

Arquivo principal:
- `config/sample-calibration-wizard.cfg`

---

## Botões/macros principais

- `CAL_BTN_BASELINE` → executa baseline automático
- `CAL_BTN_SPEED_TEST TARGET_SPEED=<mm/s>` → calcula e roda teste rápido
- `CAL_BTN_ALL_IN_ONE TARGET_SPEED=<mm/s>` → baseline + teste

Também disponíveis:
- `CAL_POST_TEST_REVIEW`
- `CAL_APPLY_USER_FEEDBACK ...`

---

## Ordem automática de calibração (baseline)

Macro: `CAL_AUTO_BASELINE`

Sequência executada:
1. `G28`
2. Nivelamento por arquitetura (condicional):
   - `QUAD_GANTRY_LEVEL` ou
   - `Z_TILT_ADJUST` ou
   - `SCREWS_TILT_CALCULATE`
3. `BED_MESH_CLEAR` + `BED_MESH_CALIBRATE` (se `bed_mesh` existir)
4. Orientação para refinamento com `PROBE_CALIBRATE` (quando aplicável)

> O fluxo usa detecção condicional de módulos e evita comandos inexistentes.

---

## Cálculo automático por velocidade desejada

Macro: `CAL_AUTO_SPEED_TEST TARGET_SPEED=<mm/s>`

Entradas:
- velocidade desejada do usuário (`TARGET_SPEED`)

Regras de segurança:
- `effective_speed = min(TARGET_SPEED, printer.toolhead.max_velocity)`
- aceleração calculada e limitada por `printer.toolhead.max_accel`
- `ACCEL_TO_DECEL <= ACCEL`
- `SCV` limitado em faixa segura

Parâmetros aplicados automaticamente:
- `SET_VELOCITY_LIMIT VELOCITY=... ACCEL=... ACCEL_TO_DECEL=... SQUARE_CORNER_VELOCITY=...`

> Os parâmetros calculados são estimativa inicial teórica segura, não “valor perfeito absoluto”. O ciclo de feedback é obrigatório para convergência prática.

---

## Impressão de teste rápida para avaliar qualidade

Macro: `CAL_PRINT_QUICK_DIAGNOSTIC`

O padrão inclui:
- perímetro quadrado (cantos/SCV),
- diagonais (ringing/dinâmica),
- linhas paralelas (constância de fluxo).

Isso reduz tempo de teste e permite avaliação visual objetiva.

---

## Pós-teste: perguntas e instruções ao usuário

Macro: `CAL_POST_TEST_REVIEW`

Mostra orientações diretas:
- blob em cantos → reduzir PA em passos pequenos,
- canto vazio → aumentar PA em passos pequenos,
- ringing → reduzir aceleração e revisar shaper,
- linhas faltando → reduzir velocidade e revisar temperatura,
- canto arredondado → reduzir SCV,
- impacto agressivo → reduzir `ACCEL_TO_DECEL`.

Para hosts compatíveis, há prompt em tela (`action:prompt_*`).

---

## Aplicação rápida de feedback

Macro: `CAL_APPLY_USER_FEEDBACK`

Exemplos:
```gcode
CAL_APPLY_USER_FEEDBACK ACCEL_FACTOR=0.85
CAL_APPLY_USER_FEEDBACK SCV_DELTA=-0.8
CAL_APPLY_USER_FEEDBACK SPEED_FACTOR=0.9
```

A macro aplica clamp novamente pelos limites do cfg.

---

## Fluxo recomendado (curto)

1. `CAL_BTN_BASELINE`
2. `CAL_BTN_SPEED_TEST TARGET_SPEED=150`
3. `CAL_POST_TEST_REVIEW`
4. `CAL_APPLY_USER_FEEDBACK ...`
5. repetir 2-4 até convergir.

Fluxo único:
```gcode
CAL_BTN_ALL_IN_ONE TARGET_SPEED=150
```

---

## Avisos importantes

- Antes de testar, aqueça cama/bico para condições reais.
- Use incrementos pequenos (5-15% para dinâmica; 0.002-0.005 para PA).
- Mesmo com automação, mantenha validação visual e métricas de peça.
