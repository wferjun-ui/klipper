# Análise crítica de funções do Klipper + melhorias propostas/implementadas

Este documento foi refeito para focar no que você pediu:

1. **melhorar funções** (não só listar recursos),
2. **analisar fragilidades reais**,
3. **entregar um fluxo guiado de calibração passo-a-passo com botão/instrução ao usuário**.

---

## 1) Fragilidades detectadas em função real do código

Módulo analisado: `klippy/extras/screws_tilt_adjust.py`

### Fragilidade A — arredondamento de minutos pode gerar `:60`

Na função de cálculo de ajuste das roscas, o arredondamento de minutos podia produzir `60`, resultando em saída inválida/estranha para o usuário (ex.: `02:60`).

### Fragilidade B — validação de `MAX_DEVIATION` dependia de truthy/falsy

A validação usava `if self.max_diff ...`, o que ignora casos limite (ex.: `0.0`) por comportamento booleano, ao invés de checagem explícita.

---

## 2) Melhorias implementadas no código

### Melhoria 1 — normalização de minuto 60 -> incremento de volta completa

Quando o arredondamento gera 60 minutos:
- incrementa `full_turns` em 1,
- força `minutes = 0`.

Resultado: saída sempre coerente no formato de ajuste.

### Melhoria 2 — comparação robusta para `MAX_DEVIATION`

Troca de condição para:
- `self.max_diff is not None`

Resultado: regra aplicada de forma consistente e previsível, inclusive em limites.

---

## 3) Assistente de calibração passo-a-passo (um botão + instruções)

Entreguei um fluxo prático para você usar no Klipper:

- **Arquivo de macros**: `config/sample-calibration-wizard.cfg`
- **Guia de uso**: `docs/Calibration_Assistant_PTBR.md`

### O que o assistente faz

1. Inicia calibração por perfil (`PA`, `SHAPER`, `SPEED`).
2. Dispara impressão de teste automática por arquivo.
3. Recebe parâmetros do usuário (`CAL_WIZARD_SET ...`).
4. Aplica no firmware (`CAL_WIZARD_APPLY ...`).
5. Avança etapas com instruções claras (`CAL_WIZARD_NEXT`).
6. Salva melhores valores via `SAVE_VARIABLE` (opcional).

### Comandos principais do assistente

- `CAL_WIZARD_START PROFILE=PA|SHAPER|SPEED`
- `CAL_WIZARD_PRINT_TEST PROFILE=...`
- `CAL_WIZARD_SET ...`
- `CAL_WIZARD_APPLY PROFILE=... [SAVE=1]`
- `CAL_WIZARD_NEXT`
- `CAL_WIZARD_STATUS`

### Interface “botão/instrução”

O macro usa `RESPOND TYPE=command MSG="action:prompt_*"` para hosts compatíveis (ex.: Mainsail/Fluidd com suporte a prompt), com fallback textual via `RESPOND`/`M117`.

---

## 4) Como isso te aproxima de “calibração perfeita”

Você passa a ter um loop controlado:

1. imprimir teste,
2. avaliar critério específico,
3. inserir número,
4. aplicar ajuste,
5. repetir,
6. salvar melhor valor.

Com isso, o processo deixa de ser “tentativa e erro solta” e vira calibração guiada e reproduzível.
