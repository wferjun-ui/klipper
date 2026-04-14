# Análise de melhorias focada **somente em funções do firmware Klipper**

> Escopo deste documento: **apenas recursos nativos do Klipper** (módulos, comandos e estratégias de configuração do firmware).
> 
> Fora de escopo: ajustes mecânicos, troca de hardware, melhorias de slicer e alterações de software externo.

## 1) Estratégia: extrair o máximo do Klipper via recursos internos

Para “aproximar do perfeito” no nível de firmware, o ganho vem de combinar corretamente estes blocos:

1. **Qualidade dinâmica de movimento** (`input_shaper`, limites dinâmicos)
2. **Controle de extrusão dinâmica** (`pressure_advance`)
3. **Primeira camada inteligente** (`bed_mesh`, `fade`, malha adaptativa por macro)
4. **Compensações geométricas/termais** (`axis_twist_compensation`, `skew_correction`, `z_thermal_adjust`)
5. **Nivelamento automático por arquitetura** (`z_tilt`, `quad_gantry_level`, `screws_tilt_adjust`)
6. **Automação por macros** (rotina de preparo, validação e fallback)

---

## 2) Funções do Klipper com maior impacto direto

## 2.1 `input_shaper` (vibração, ghosting, cantos)

**Função:** reduzir ressonância sem sacrificar tanto tempo de impressão.

**Recomendação de firmware:**
- Manter `[input_shaper]` ativo e versionado por perfil.
- Usar `SET_INPUT_SHAPER` para comparação rápida entre tipos (`mzv`, `ei`) e frequências.
- Criar macro de teste A/B de shaper (mesmo gcode, parâmetros diferentes).

**Comandos úteis:**
- `SET_INPUT_SHAPER SHAPER_TYPE=MZV`
- `SET_INPUT_SHAPER SHAPER_TYPE=EI`
- `SET_INPUT_SHAPER SHAPER_FREQ_X=<hz> SHAPER_FREQ_Y=<hz>`

---

## 2.2 `pressure_advance` (cantos, costura, transientes)

**Função:** melhorar transições de fluxo em aceleração/desaceleração.

**Recomendação de firmware:**
- Salvar PA por material/perfil via macro (`SET_PRESSURE_ADVANCE`).
- Evitar PA único global para todos os cenários.
- Manter `pressure_advance_smooth_time` conservador para evitar artefatos.

**Comando útil:**
- `SET_PRESSURE_ADVANCE ADVANCE=<valor> SMOOTH_TIME=<valor>`

---

## 2.3 `bed_mesh` (primeira camada em toda a mesa)

**Função:** compensar irregularidade de plano via malha.

**Recomendação de firmware:**
- Usar perfis de malha (`BED_MESH_PROFILE SAVE/LOAD`) por temperatura/material quando necessário.
- Ativar `fade` com critério para evitar transferir ondulação para o corpo da peça.
- Afinar `move_check_distance` e `split_delta_z` para trajetória Z mais estável.

**Comandos úteis:**
- `BED_MESH_CALIBRATE`
- `BED_MESH_PROFILE SAVE=<nome>`
- `BED_MESH_PROFILE LOAD=<nome>`
- `BED_MESH_CLEAR`

---

## 2.4 `PROBE_CALIBRATE` e `PROBE_ACCURACY` (z-offset robusto)

**Função:** estabilizar Z-offset e validar repetibilidade de sonda.

**Recomendação de firmware:**
- Criar rotina padrão de calibração em macro (sempre mesma sequência).
- Exigir `PROBE_ACCURACY` periódico e log de range/desvio.
- Recalibrar automaticamente após alterações que invalidam offset.

**Comandos úteis:**
- `PROBE_CALIBRATE`
- `PROBE_ACCURACY`
- `SAVE_CONFIG`

---

## 2.5 `axis_twist_compensation` (erro de leitura ao longo do X)

**Função:** corrigir viés de medição de sonda causado por torção efetiva no eixo/gantry.

**Recomendação de firmware:**
- Habilitar em máquinas onde a malha mostra padrão progressivo “lado A vs lado B”.
- Integrar no fluxo antes de calibrações finas de mesh.

**Comandos úteis:**
- `AXIS_TWIST_COMPENSATION_CALIBRATE`

---

## 2.6 `skew_correction` (ortogonalidade XY/XZ/YZ)

**Função:** compensar erro angular geométrico por transformação no firmware.

**Recomendação de firmware:**
- Usar apenas após validação geométrica por peça de referência.
- Salvar perfis de skew para cenários específicos se necessário.

**Comandos úteis:**
- `SET_SKEW XY=<ac,bd,ad> XZ=<ac,bd,ad> YZ=<ac,bd,ad>`
- `SKEW_PROFILE SAVE=<nome>` / `SKEW_PROFILE LOAD=<nome>`

---

## 2.7 `z_tilt`, `quad_gantry_level`, `screws_tilt_adjust` (nivelamento por arquitetura)

**Função:** alinhar plano de impressão usando os recursos próprios do Klipper.

**Recomendação de firmware:**
- Escolher **um fluxo oficial** de nivelamento conforme arquitetura da impressora.
- Inserir no `START_PRINT` para execução condicional e segura.

**Comandos úteis:**
- `Z_TILT_ADJUST`
- `QUAD_GANTRY_LEVEL`
- `SCREWS_TILT_CALCULATE`

---

## 2.8 `z_thermal_adjust` (deriva de Z por temperatura)

**Função:** compensar variação em Z relacionada a aquecimento.

**Recomendação de firmware:**
- Habilitar quando houver deriva reproduzível durante aquecimento/impressão.
- Ajustar `temp_coeff` com base em medição repetível e manter limite de correção.

**Comando útil:**
- `SET_Z_THERMAL_ADJUST ENABLE=1`

---

## 2.9 Controle dinâmico de limites (`SET_VELOCITY_LIMIT`)

**Função:** adaptar desempenho por tipo de peça sem reiniciar firmware.

**Recomendação de firmware:**
- Criar presets “qualidade”, “balanceado”, “rápido” em macro.
- Ajustar `ACCEL`, `ACCEL_TO_DECEL`, `SQUARE_CORNER_VELOCITY`, `MINIMUM_CRUISE_RATIO` em conjunto.

**Comando útil:**
- `SET_VELOCITY_LIMIT ACCEL=<v> ACCEL_TO_DECEL=<v> SQUARE_CORNER_VELOCITY=<v> MINIMUM_CRUISE_RATIO=<v>`

---

## 2.10 `exclude_object` (inteligência em falha parcial)

**Função:** excluir apenas um objeto com defeito durante impressão multi-objeto.

**Recomendação de firmware:**
- Habilitar para evitar perda total de produção.
- Integrar no fluxo do host para marcação consistente de objetos.

**Comando útil:**
- `EXCLUDE_OBJECT NAME=<objeto>`

---

## 3) “Pacote firmware” recomendado (alto impacto)

Se a meta for qualidade + velocidade + confiabilidade usando **só Klipper**, priorize este pacote:

1. `[input_shaper]`
2. `pressure_advance` por perfil
3. `[bed_mesh]` com perfis
4. `[axis_twist_compensation]` (se necessário)
5. `[z_tilt]` ou `[quad_gantry_level]` (conforme arquitetura)
6. `[z_thermal_adjust]` (se houver deriva)
7. `[exclude_object]`
8. Macros de orquestração (`START_PRINT`, `END_PRINT`, `CALIBRATION_CHECK`)

---

## 4) Fluxo de automação 100% firmware (exemplo)

Macro `START_PRINT` (lógica sugerida):

1. validar homing,
2. aquecer,
3. nivelamento automático da arquitetura (`Z_TILT_ADJUST` ou `QUAD_GANTRY_LEVEL`),
4. carregar/gerar `bed_mesh`,
5. aplicar preset dinâmico (`SET_VELOCITY_LIMIT`),
6. aplicar preset de material (`SET_PRESSURE_ADVANCE`),
7. iniciar impressão.

Isso reduz variabilidade operacional e aumenta repetibilidade entre trabalhos.

---

## 5) Inconsistências puramente de firmware a evitar

1. Habilitar recursos sem rotina de ordem (ex.: mesh antes de compensações necessárias).
2. Ajustar dinâmica sem preset/versionamento (perde rastreabilidade).
3. Misturar parâmetros de teste e produção no mesmo perfil sem controle.
4. Não usar perfis para PA, mesh e skew.
5. Não validar estado antes de imprimir (macro sem checagens).

---

## 6) KPIs para validar melhoria de firmware

- Redução de ringing visual após `input_shaper`.
- Menor variação de canto/quina após ajuste de PA + dinâmica.
- Menos falhas de primeira camada após fluxo `nivelamento + mesh + z-offset`.
- Menor descarte em impressão multi-objeto com `exclude_object`.
- Maior repetibilidade entre dias usando macros e presets versionados.

---

## 7) Conclusão objetiva

Se você quer foco estritamente no Klipper, o caminho é construir um **pipeline de firmware** com:

- compensações corretas,
- presets dinâmicos,
- perfil por contexto,
- automação por macro,
- validação por KPI.

Se quiser, no próximo passo eu posso te entregar um **conjunto de macros pronto** (somente Klipper) com:
- `START_PRINT` inteligente,
- seleção automática de perfil de PA/velocidade,
- carga de malha por perfil,
- rotina de verificação de estado antes da impressão.
