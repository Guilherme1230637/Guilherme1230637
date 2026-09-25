# Especificação — Awaken System (app de hábitos estilo Solo Leveling)

> Documento de requisitos e regras de jogo. Reúne todas as decisões tomadas nas rondas de perguntas.
> Os valores numéricos foram aprovados e calibrados com `tools/simular_progressao.py`; podem ser ajustados depois de testar a app.

---

## 1. Visão geral

App **desktop para Windows** que permite registar hábitos diários, semanais e mensais e transforma a vida real
num RPG: cada hábito cumprido dá **XP, Gold e atributos**; falhar tira **HP** e pode levar à **Penalty Zone**.
A estética imita as janelas azuis do "Sistema" do manhwa *Solo Leveling*.

| Decisão | Escolha |
|---|---|
| Plataforma | Windows (desktop) |
| Linguagem / UI | Python 3.11+ com PySide6 (Qt) |
| Base de dados | SQLite (ficheiro local, sem servidor) |
| Idioma da interface | Inglês |
| Estilo visual | "System" do Solo Leveling (azul translúcido, brilho, mensagens `[SYSTEM]`) |
| Sincronização | Não (dados só no PC) |
| Backup | Não (há só um botão discreto "Export" para JSON) |
| Proteção | PIN numérico ao abrir |
| IA | Opcional (Claude API), só para dar nome/descrição às Skills |

**Porque não mobile?** Uma app nativa para iPhone precisa de um Mac (Xcode). Sem pagar 99 USD/ano, a app deixa de abrir
ao fim de 7 dias, e a alternativa Expo Go depende de um PC ligado. Ficou decidido: desktop.

---

## 2. Hábitos (Quests)

### 2.1 Tipos
| Tipo | Exemplo | Como se regista | Percentagem de cumprimento `r` |
|---|---|---|---|
| **Sim/Não** | "Fazer a cama" | Check | `r = 1` ou `0` |
| **Quantitativo** | "Beber 2 L de água" | Valor (ex.: 1,5) | `r = min(valor / alvo, 1)` |
| **Contador (N× por dia)** | "3× alongamentos" | Botão **+1** | `r = min(vezes / N, 1)` |
| **Temporizado** | "Estudar 60 min", "Praticar japonês 30 min" | Timer integrado (start/pause/stop) ou minutos à mão | `r = min(minutos / alvo, 1)` |
| **Negativo com limite** | "Máx. 1 h de redes sociais", "Não fumar" (limite 0) | Valor consumido | ver 2.3 |

### 2.2 Periodicidade (secções separadas na UI)
- **Daily**: reinicia todos os dias à **00:00**.
- **Weekly**: alvo de N vezes por semana (segunda a domingo), avaliado domingo às 24:00.
- **Monthly**: alvo de N vezes por mês, avaliado no último dia do mês às 24:00.
- **Um só modelo:** cada hábito guarda **um valor por período**. "Ginásio 3× por semana" é um contador cujo período é a semana.
- **Alvo proporcional:** nos hábitos quantitativos, contador e timer, se parte do período esteve em **pausa** ou foi antes
  de o hábito ser criado, o alvo ajusta-se aos dias ativos (ex.: 2 dias de pausa → alvo 3 × 5/7).
  Sim/Não e limites não se ajustam. Um período inteiro em pausa não conta.

### 2.3 Hábitos negativos (limite diário)
```
se valor ≤ limite:           r = 1
se limite > 0 e valor > limite: r = max(0, 1 − (valor − limite) / limite)
se limite = 0 e valor > 0:   r = 0        (caso especial: evita divisão por zero)
```
Exemplo: limite 60 min, gastei 90 min → excesso 30 → `r = 1 − 30/60 = 0,5`.

### 2.4 Rank de dificuldade (E → S)
Quanto mais alto o rank do hábito, mais XP, Gold e atributos dá, e mais HP tira quando falhas.

| Rank | XP base | Gold base | Penalização HP base | Pontos de atributo base | Loot drop |
|---|---|---|---|---|---|
| E | 10 | 5 | 5 | 0,2 | 3 % |
| D | 20 | 10 | 8 | 0,4 | 5 % |
| C | 35 | 18 | 12 | 0,6 | 8 % |
| B | 55 | 28 | 16 | 0,8 | 12 % |
| A | 80 | 40 | 22 | 1,0 | 17 % |
| S | 120 | 60 | 30 | 1,5 | 25 % |

### 2.5 Recompensa e penalização proporcionais (sem limiar)
```
XP ganho   = XP_base(rank)   × r × (1 + bónus_streak + bónus_skills + bónus_itens)
Gold ganho = Gold_base(rank) × r
HP perdido = HP_base(rank)   × (1 − r)
```
Fazer 75 % dá 75 % do XP e a penalização corresponde apenas aos 25 % em falta.

**Quando é que se recebe:**
- **XP, Gold e atributos:** no momento do registo, de forma incremental (ir de 50 % para 75 % dá a diferença).
  Calcula-se `round(total(novo)) − round(total(antigo))`, por isso vários registos parciais dão exatamente o mesmo que
  um único a 100 %. Corrigir um registo para baixo retira a diferença.
- **Hábitos negativos (LIMIT):** só no fecho do período, porque só aí se sabe se o limite foi respeitado.
- **HP perdido e streak:** no fecho do período (meia-noite, domingo ou fim do mês).

### 2.6 Streaks (sequências)
- **Cada hábito tem a sua streak própria** e o seu **limiar mínimo** para contar o dia (por defeito 100 %; ex.: água 80 %, ginásio 100 %).
- Bónus de streak: `+1 % de XP por período de streak, até +30 %` (dias nos diários, semanas nos semanais, meses nos mensais).
- A streak é atualizada no **fecho do período**.

---

## 3. Personagem

### 3.1 Início
Nível 1, todos os atributos a **10**, Hunter Rank **E**, HP 100/100.

### 3.2 Atributos (9)
| Sigla | Atributo | Hábitos típicos |
|---|---|---|
| STR | Strength (Força) | Musculação, flexões |
| AGI | Agility (Agilidade) | Corrida, desporto, cardio |
| VIT | Vitality (Vitalidade) | Sono, alimentação, água |
| END | Endurance (Resistência) | Treinos longos, caminhadas |
| INT | Intelligence (Inteligência) | Estudo, línguas, programação |
| PER | Perception (Perceção) | Meditação, foco, *journaling* |
| CHA | Charisma (Carisma) | Socializar, falar em público |
| WIS | Wisdom (Sabedoria) | Leitura, finanças, reflexão |
| TEN | Tenacity (Tenacidade/Resiliência) | Hábitos negativos vencidos, tarefas difíceis |

### 3.3 Ligação hábito → atributos (pesos livres)
Cada hábito distribui **percentagens que somam 100 %** pelos atributos. A app **sugere** uma distribuição lógica por categoria e tu ajustas.
```
Exemplo "Estudar 60 min" (rank C): INT 60 %, WIS 30 %, TEN 10 %
Ganho de atributo_i = pontos_base(rank) × peso_i × r
→ INT +0,36 · WIS +0,18 · TEN +0,06   (com r = 1)
```
Os atributos guardam casas decimais e a UI mostra o valor inteiro. Além disso, cada **Level Up dá 3 pontos livres** para distribuíres à mão (mais os extras de cada subida de ranking, ver 3.7).

### 3.4 Nível e curva de XP
```
XP necessário para passar do nível n para n+1 = round(100 + 2 × n^1.5)
```
| Nível | XP para o seguinte |
|---|---|
| 1 | 102 |
| 5 | 122 |
| 10 | 163 |
| 25 | 350 |
| 40 | 606 |
| 55 | 916 |
| 70 | 1 271 |
| 85 | 1 667 |
| 100 | 2 100 |

**Objetivo de design:** um jogador Regular chega ao **nível 40 em 1,5 a 2 meses**.

**Porque tem duas partes:**
- `100` (**base fixa**): garante que cada nível custa sempre pelo menos ~meio dia de hábitos. Sem ela, os primeiros
  níveis seriam quase gratuitos (com `2 × n^1.5`, o nível 1 custaria 2 XP e subirias vários níveis no primeiro clique).
- `2 × n^1.5` (**termo polinomial**): faz o custo crescer com o nível. Nos níveis baixos domina a base (a curva é quase
  plana); nos níveis altos domina este termo (a curva acelera).
- Nota de rigor: `n^1.5` é uma função **potência (polinomial)**, não exponencial. Uma exponencial seria `a^n` e cresceria
  depressa demais para um jogo de longo prazo.

**Como foi calibrada (`tools/simular_progressao.py`):** o simulador corre a progressão dia a dia para 3 perfis de
jogador, com bónus de streak, bónus de Skills e custos em Gold. Curvas testadas (perfil Regular, só nível):

| Curva | Nível 1 custa | Nível 40 em |
|---|---|---|
| `100 × n^1.5` (1.ª versão) | 100 XP | ~4,3 anos |
| `12 × n^1.5` (2.ª versão) | 12 XP | ~6 meses |
| `50 + 3 × n^1.5` | 53 XP | 58 dias |
| **`100 + 2 × n^1.5` (escolhida)** | **102 XP** | **50 dias** |
| `100 + 0,3 × n^2` | 100 XP | 43 dias |

Resultado final, com os custos de Gold da secção 3.7 (tempo até atingir cada ranking):

| Ranking | Casual (145 XP/dia, 65 %) | Regular (250, 80 %) | Hardcore (420, 95 %) |
|---|---|---|---|
| Bronze (Lv 10) | 12 dias | 6 dias | 3 dias |
| Silver (Lv 25) | 44 dias | 22 dias | 12 dias |
| Gold (Lv 40) | 3,4 meses | **49 dias** | 26 dias |
| Dark Gold (Lv 55) | 6,2 meses | 3,0 meses | 46 dias |
| Legend (Lv 70) | 10,1 meses | 4,9 meses | 2,5 meses |
| Heavenly Fate (Lv 85) | 15,0 meses | 7,3 meses | 3,7 meses |
| Heavenly Star (Lv 100) | 21,0 meses | 10,3 meses | 5,3 meses |
| Heavenly Axis (Lv 115) | 2,4 anos | 13,8 meses | 7,1 meses |
| Dao of Dragon (Lv 130) | 3,1 anos | 17,8 meses | 9,2 meses |
| Martial Ancestor (Lv 145) | 3,8 anos | 22,2 meses | 11,7 meses |
| Deity (Lv 160) | 4,7 anos | 2,3 anos | 14,4 meses |
| Emperor (Lv 175) | 5,6 anos | 2,7 anos | 17,4 meses |
| Supreme (Lv 190) | 6,7 anos | 3,2 anos | 20,6 meses |

**Efeito do Gold (atraso face a "só nível"):** Hardcore 0 dias · Regular 0 dias · Casual até ~45 dias.
O Gold trava apenas quem cumpre pouco, ou seja, **mede a consistência** (ver 3.7).
Estes objetivos estão protegidos por testes automáticos (`tests/test_balance.py`).

Pressupostos do modelo: hábitos fixos (na realidade o jogador tende a juntar hábitos de rank mais alto, o que acelera),
bónus de streak enche em 30 dias, bónus de Skills chega ao teto em 2 anos, bónus de XP do ranking atual incluído, todo o Gold é guardado para breakthroughs.

### 3.5 HP
```
HP máximo = 100 + 5 × (VIT − 10)
Recuperação: +10 HP por cada dia com todas as dailies a 100 %; poções (Loot) restauram HP.
```

### 3.6 Hunter Rank (por nível)
| E | D | C | B | A | S | National Level |
|---|---|---|---|---|---|---|
| 1–9 | 10–19 | 20–34 | 35–49 | 50–69 | 70–99 | 100+ |

### 3.7 Ranking de cultivação (estilo *Tales of Demons and Gods*)
Substitui o antigo Job Change e as classes. Os **atributos e as Skills não mudam**.

- Começas **Unranked**. Para subir de ranking precisas de **nível mínimo + Gold**. O Gold é **pago** e sai da conta.
- **Sem bottleneck:** continuas a subir de nível normalmente, mesmo sem Gold para o próximo ranking.
- Os rankings sobem **por ordem**, sem saltar nenhum, **a cada 15 níveis**.
- Popup: `[SYSTEM] Breakthrough successful! You have reached Silver Rank.`

| # | Ranking | Requisito | Subdivisão | Pontos livres extra | Bónus de XP global |
|---|---|---|---|---|---|
| 0 | Unranked | — (início) | — | — | — |
| 1 | **Bronze** | Lv 10 + 500 Gold | ★1 → ★5 | +5 | +2 % |
| 2 | **Silver** | Lv 25 + 1 500 Gold | ★1 → ★5 | +10 | +4 % |
| 3 | **Gold** | Lv 40 + 2 500 Gold | ★1 → ★5 | +15 | +6 % |
| 4 | **Dark Gold** | Lv 55 + 4 000 Gold | ★1 → ★5 | +20 | +8 % |
| 5 | **Legend** | Lv 70 + 5 500 Gold | ★1 → ★5 | +25 | +10 % |
| 6 | **Heavenly Fate** | Lv 85 + 7 000 Gold | Stage 1 → 10 | +30 | +12 % |
| 7 | **Heavenly Star** | Lv 100 + 9 000 Gold | Stage 1 → 10 | +35 | +14 % |
| 8 | **Heavenly Axis** | Lv 115 + 10 500 Gold | Stage 1 → 10 | +40 | +16 % |
| 9 | **Dao of Dragon** | Lv 130 + 12 000 Gold | Stage 1 → 10 | +45 | +18 % |
| 10 | **Martial Ancestor** | Lv 145 + 13 500 Gold | Stage 1 → 10 | +50 | +20 % |
| 11 | **Deity** | Lv 160 + 14 500 Gold | Stage 1 → 10 | +55 | +22 % |
| 12 | **Emperor** | Lv 175 + 16 500 Gold | Stage 1 → 10 | +60 | +24 % |
| 13 | **Supreme** | Lv 190 + 18 500 Gold | Stage 1 → 10 | +65 | +26 % |

- **Pontos livres extra:** somam-se uma vez, no momento do breakthrough, aos 3 pontos normais por nível.
- **Bónus de XP global:** aplica-se a todos os hábitos e **não é cumulativo** (vale o do ranking atual).

#### Estrelas e estágios: regra de cálculo
Dentro de um ranking, a subdivisão mede **a fração do caminho em XP** entre o nível do ranking atual e o nível do
seguinte (para Supreme, o "seguinte" é o nível 205, mantendo o intervalo de 15):
```
progresso   = (XP_total_atual − XP_total(nível do ranking)) / (XP_total(nível do ranking seguinte) − XP_total(nível do ranking))
subdivisão  = min( floor(progresso × N) + 1 , N )        N = 5 estrelas (Bronze→Legend) · N = 10 estágios (Heavenly Fate→Supreme)
```
- **Porque XP e não níveis:** 5 estrelas dividem bem 15 níveis (3 cada), mas 10 estágios não (1,5 níveis cada). Com XP a
  regra é igual para ambos e cada ★ vale exatamente 20 % do caminho, e cada estágio 10 %.
- **O `min(…, N)`:** se já tens nível para o ranking seguinte mas não pagaste, ficas no máximo (★5 ou Stage 10) e não
  passas para um "★6" inexistente.
- Exemplo real (início de cada nível): **Bronze** ★1 nos níveis 10–14, ★2 em 15–17, ★3 em 18–20, ★4 em 21–22, ★5 em 23–24.
  As primeiras estrelas levam mais níveis porque os níveis mais baixos custam menos XP.
  **Heavenly Fate:** Stage 1 nos níveis 85–86, … Stage 10 no nível 99.

**Para que serve o Gold:** **só** para breakthroughs de ranking (a Shop foi removida, ver 6.1). É pago, não basta tê-lo.

**Porque é que o Gold não é redundante com o nível:** o Gold ganha-se **sem bónus** (streaks, Skills e ranking não o
multiplicam) e perde-se na Penalty Zone (−20 %). Por isso o XP mede o volume total e o Gold mede a **consistência**. Um
jogador que cumpre pouco atinge o nível mas não junta Gold suficiente, e tem de melhorar a consistência para romper.

**Como foram definidos os custos:** cada custo ≈ o Gold que um jogador Regular ganha entre o ranking anterior e esse
(simulador). Iterações: (1) custos a crescer depressa faziam o Gold atrasar o Supreme quase 4 anos; (2) com a Shop
removida o Gold poupado duplicou, e os custos foram duplicados em conformidade; (3) ao ligar o simulador ao motor,
verificou-se que o simulador ignorava o bónus de XP dos rankings. Com o bónus incluído o XP chega mais cedo e o Gold passava
a atrasar o Regular até ~4 meses, por isso os custos foram recalculados com a mesma regra.

### 3.8 Títulos
Desbloqueados por conquistas (ex.: "The One Who Overcame Adversity" = sair da Penalty Zone; "Unbreakable" = streak de 66 dias). O título ativo aparece na Status Window.

---

## 4. Penalty Zone
1. Falhar hábitos tira HP (fórmula 2.5).
2. **HP = 0 → Penalty Zone:**
   - perdes **10 % do XP do nível atual** (nunca desces de nível) e **20 % do Gold**;
   - os **breakthroughs de ranking ficam bloqueados**;
   - é gerada uma **Penalty Quest** obrigatória com prazo até ao fim do dia seguinte. O rank é a **média dos ranks dos
     teus hábitos, arredondada para cima** (ex.: E e D → D), e a tarefa é sorteada de uma lista por rank
     (ex.: C → "Do 100 push-ups", "Run 5 km", "Study for 60 minutes").
3. Completar a Penalty Quest devolve **50 % do HP** e desbloqueia os breakthroughs. Se falhares, é gerada outra.

---

## 5. Skills (geração híbrida)

### 5.1 Quando aparece uma Skill (motor de regras)
| Gatilho | Limiares |
|---|---|
| Nº de vezes que completaste **um hábito** | 10, 30, 100 |
| Nº total de missões de **uma categoria/atributo dominante** | 25, 50, 100, 250 |
| **Streak** de um hábito | 7, 21, 66 dias |

### 5.2 Nome e descrição
- **Sem IA:** composição a partir de tabelas por atributo (ex.: prefixo "Iron" + núcleo STR "Body" → **"Iron Body"**).
- Tabelas: 4 prefixos × 4 núcleos por atributo = 16 nomes; esgotados, acrescenta-se um numeral ("Iron Body II"). Nunca há nomes repetidos.
- **Com IA (opcional):** se houver chave de API nas Settings, o motor envia um resumo (atributo, hábito, gatilho) e a IA devolve nome e descrição temáticos. Se falhar ou estiver sem internet, usa as tabelas.
- O motor de regras decide sempre **quando** e **que tipo** de Skill aparece. A IA só escreve o texto.

### 5.3 Nível (Proficiency pelo uso)
- Cada vez que um período de um hábito ligado à Skill fecha com `r > 0`, ela ganha **proficiência** (`+r`).
- Skills de hábito/streak ligam-se a esse hábito; Skills de atributo ligam-se a **todos** os hábitos cujo atributo principal (maior peso) é esse.
- Lv.1 → Lv.10 (MAX). Proficiência para o nível seguinte: `10 × nível`.

### 5.4 Efeito: bónus de XP
`+2 % de XP por nível da Skill` nos hábitos ligados. O bónus total das Skills tem um teto de **+50 %** para não desequilibrar.

---

## 6. Recompensas

### 6.1 Gold
- O Gold ganha-se com os hábitos (2.5) e com o item Gold Pouch.
- Serve **exclusivamente** para pagar os breakthroughs de ranking (3.7).
- **Shop removida:** com duas utilizações, o Gold perdia peso em ambas; concentrado nos rankings, cada moeda conta.

### 6.2 Loot (inventário)
Cada período fechado como cumprido (atingiu o limiar da streak) tem uma probabilidade de *drop* (tabela 2.4).
O sorteio é feito no **fecho**, não no registo: assim não dá para marcar e desmarcar um hábito até sair loot.
Se há drop, o item sai com os pesos: HP Potion 40 %, XP Scroll 25 %, Streak Shield 20 %, Gold Pouch 15 %. Itens:
| Item | Efeito |
|---|---|
| HP Potion | +30 HP (sem efeito na Penalty Zone: aí só a Penalty Quest resolve) |
| Streak Shield | Protege a streak de um hábito numa falha (gasto **automaticamente**) |
| XP Scroll | ×2 XP nas próximas 3 quests |
| Gold Pouch | +50 a 200 Gold |

### 6.3 Achievements
Exemplos: "First Step" (1.ª quest), "Week Warrior" (7 dias a 100 %), "Level 10", "Survivor" (sair da Penalty Zone), "Polyglot" (100 h de línguas).

---

## 7. Estatísticas
- **Calendário por hábito:** cada dia é pintado com intensidade proporcional a `r` (0 % vazio → 100 % cor máxima). Nos quantitativos, 1,5/2 L aparece a 75 %.
- **Weekly Report `[SYSTEM]`:** gerado no fecho de domingo (vês na segunda-feira) com o resumo da semana anterior: XP/Gold ganho, níveis subidos, taxa de cumprimento por hábito, melhor e pior hábito, streaks, Skills novas ou subidas, HP perdido e passagens pela Penalty Zone.

---

## 8. Tempo e ausência
- Dia vira às **00:00**, semana começa à segunda.
- **Catch-up:** ao abrir a app, os dias em falta são processados um a um, pela ordem, com as penalizações de cada dia.
- **Modo Pausa:** ativado à mão (férias, doença). Os dias em pausa não contam.

---

## 9. Segurança
- **PIN numérico de 4 a 6 dígitos**, guardado como *hash* **PBKDF2-HMAC-SHA256 com salt aleatório** (nunca em texto simples).
- 5 tentativas erradas → espera de 30 s.
- **Limitação assumida:** o PIN protege o acesso à app, mas **não cifra** o ficheiro da base de dados.
- A chave de API da IA (se usada) fica no **Windows Credential Manager** (biblioteca `keyring`), não na base de dados.

---

## 10. Notificações
- **Lembretes de horário** por hábito (ex.: "[SYSTEM] Daily Quest has arrived" às 08:00).
- Nota técnica: os lembretes só disparam com a app a correr. Ao fechar a janela, a app minimiza para o ícone junto ao relógio do Windows.

---

## 11. Interface
- **Ecrã principal:** à esquerda a **Status Window** (nome, nível, Hunter Rank, ranking de cultivação com estrela/estágio, título, barras de HP e XP, 9 atributos, pontos livres). À direita as **Quests** em separadores **Daily / Weekly / Monthly**.
- **Barra lateral:** Status · Quests · Skills · Inventory · Ranking · Calendar · Report · Achievements · Settings.
- Popups animados `[SYSTEM]` para Level Up, Skill nova, Loot e Penalty.

---

## 12. Arquitetura
```
awaken/
  engine/              lógica pura do jogo — sem UI nem base de dados, 100 % testável
    config.py          TODOS os números de equilíbrio (fonte única)
    leveling.py        curva de XP, Level Up, Hunter Rank
    cultivation.py     rankings, breakthroughs, estrelas/estágios
    habits.py          tipos de hábito, % de cumprimento, recompensas, HP, streaks
    player.py          estado da personagem e ações (XP, atributos, HP, Penalty Zone)
    periods.py         dia / semana / mês
    skills.py          gatilhos, nomes (tabelas; IA ligável), proficiência
    items.py           loot e inventário
    achievements.py    estatísticas, achievements e títulos
    penalty.py         Penalty Quest
    report.py          Weekly Report
    state.py           GameState: registo de progresso, fecho do dia, catch-up, pausa, itens
  persistence/         SQLite (a fazer)
  services/            relógio, lembretes, IA opcional, PIN (a fazer)
  ui/                  PySide6 (a fazer)
tests/                 pytest: uma bateria por módulo + test_balance (objetivos de design)
tools/
  simular_progressao.py  simulador de equilíbrio; lê os números de awaken/engine/config.py
```
**Princípio-chave:** separar **regras do jogo (engine)** da **interface (ui)**. Isto permite testar as fórmulas automaticamente e trocar a UI sem mexer nas regras.
**Fonte única de verdade:** o simulador importa a curva e os rankings do motor, por isso os dois nunca discordam.
Distribuição: **PyInstaller** gera um `.exe` para Windows.
