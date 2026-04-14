# Assistente de calibração guiada (passo-a-passo) para Klipper

Este guia entrega um fluxo de calibração interativo com “um botão” usando macros.

Arquivo exemplo:
- `config/sample-calibration-wizard.cfg`

## O que este assistente resolve

1. Executar calibração em etapas com instruções na tela.
2. Aplicar parâmetros direto no firmware (`PA`, `SHAPER`, `SPEED`).
3. Rodar impressão de teste automática por perfil.
4. Receber feedback do usuário e iterar rapidamente.
5. Persistir melhor valor com `SAVE_VARIABLE` (opcional).

## Pré-requisitos

No `printer.cfg`, habilite:

```ini
[respond]

[save_variables]
filename: ~/printer_data/config/variables.cfg
```

> Se seu host suportar prompts (`action:prompt_*`), você verá botões e caixas de texto;
> caso contrário, as instruções aparecem via `RESPOND`/`M117`.

## Fluxo recomendado

### 1) Iniciar assistente

```gcode
CAL_WIZARD_START PROFILE=PA
```

Perfis aceitos:
- `PA`
- `SHAPER`
- `SPEED`

### 2) Rodar teste automático

```gcode
CAL_WIZARD_PRINT_TEST PROFILE=PA
```

Edite os nomes de arquivo no macro para seus testes reais no virtual SD.

### 3) Informar ajuste após avaliação visual

Exemplos:

```gcode
CAL_WIZARD_SET PA=0.034
CAL_WIZARD_SET FREQ_X=48.2 FREQ_Y=39.4
CAL_WIZARD_SET ACCEL=7000 SCV=6.5
```

### 4) Aplicar ajuste no firmware

```gcode
CAL_WIZARD_APPLY PROFILE=PA
```

Para salvar melhor valor:

```gcode
CAL_WIZARD_APPLY PROFILE=PA SAVE=1
```

### 5) Avançar no passo-a-passo

```gcode
CAL_WIZARD_NEXT
```

### 6) Consultar estado

```gcode
CAL_WIZARD_STATUS
```

## Critérios de avaliação por perfil

### PA
- Redução de blob em quinas.
- Costura menos evidente.
- Sem sub/sobre-extrusão em mudanças bruscas.

### SHAPER
- Menos eco/ringing após arestas.
- Sem excesso de suavização de detalhes finos.

### SPEED
- Sem perda de passos.
- Sem degradação forte de superfície.
- Ganho real de tempo com qualidade aceitável.

## Observações importantes

- O assistente é iterativo: teste -> feedback -> aplica -> reteste.
- Valores ideais variam por material e perfil de uso.
- Mantenha presets versionados para rastreabilidade.
