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

### 2.6 Streaks (sequências)
- **Cada hábito tem a sua streak própria** e o seu **limiar mínimo** para contar o dia (por defeito 100 %; ex.: água 80 %, ginásio 100 %).
- Bónus de streak: `+1 % de XP por dia de streak, até +30 %`.

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
Os atributos guardam casas decimais e a UI mostra o valor inteiro. Além disso, cada **Level Up dá 3 pontos livres** para distribuíres à mão (mais os extras dos tiers de classe, ver 3.7).

### 3.4 Nível e curva de XP (exponencial suave)
```
XP necessário para passar do nível n para n+1 = round(12 × n^1.5)
```
| Nível | XP para o seguinte |
|---|---|
| 1 | 12 |
| 5 | 134 |
| 10 | 379 |
| 25 | 1 500 |
| 50 | 4 243 |
| 100 | 12 000 |

**Justificação:** os primeiros níveis são rápidos, o que motiva no início, e depois o ritmo abranda sem crescer tão depressa como uma exponencial pura (`a^n`), que tornaria os níveis altos impossíveis.

**Como foi calibrada (`tools/simular_progressao.py`):** a primeira proposta (`100 × n^1.5`) punha um jogador normal
a demorar ~4 anos até ao nível 40. O simulador corre a progressão dia a dia para 3 perfis e
permitiu escolher o coeficiente 12:

| Perfil (XP base/dia, cumprimento) | Nível 10 | 1st Job Change (Lv 40) | 2nd Adv. (Lv 50) | 3rd Adv. (Lv 65) | 4th Adv. (Lv 80) | Monarch (Lv 100) |
|---|---|---|---|---|---|---|
| Casual (145, 65 %) | 14 dias | 12,5 meses | 20,6 meses | 3,1 anos | 4,9 anos | 8,4 anos |
| Regular (250, 80 %) | 7 dias | 6,1 meses | 10,2 meses | 18,5 meses | 2,4 anos | 4,0 anos |
| Hardcore (420, 95 %) | 4 dias | 3,1 meses | 5,2 meses | 9,7 meses | 15,5 meses | 2,1 anos |

Pressupostos do modelo: bónus de streak enche em 30 dias, bónus de Skills chega ao teto em 2 anos, metade do Gold é gasto na Shop.

### 3.5 HP
```
HP máximo = 100 + 5 × (VIT − 10)
Recuperação: +10 HP por cada dia com todas as dailies a 100 %; poções (Loot) restauram HP.
```

### 3.6 Hunter Rank (por nível)
| E | D | C | B | A | S | National Level |
|---|---|---|---|---|---|---|
| 1–9 | 10–19 | 20–34 | 35–49 | 50–69 | 70–99 | 100+ |

### 3.7 Job Change e avanços de classe
**1st Job Change (nível 40):** aparece a *Job Change Quest*: **14 dias seguidos** em que todas as dailies atingem o
limiar da sua streak. Ao completá-la recebes a classe do teu **atributo dominante** (o mais alto nesse momento).
A partir daí a classe segue a sua linha. Cada avanço exige **nível mínimo + Gold** e o Gold é **pago** (sai da conta).

| Tier | Requisito | STR | AGI | INT | WIS | PER | CHA | VIT | END | TEN |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Lv 40 + Job Change Quest | Warrior | Assassin | Mage | Sage | Ranger | Commander | Guardian | Knight | Berserker |
| 2 | Lv 50 + 3 000 Gold | Gladiator | Shadow Blade | Sorcerer | Oracle | Sniper | Tactician | Paladin | Iron Knight | Unyielding |
| 3 | Lv 65 + 8 000 Gold | Warlord | Phantom | Archmage | Hierophant | Eagle Eye | General | Holy Knight | Juggernaut | Undying |
| 4 | Lv 80 + 15 000 Gold | Titan | Night Reaper | Arcane Sovereign | Grand Sage | Starseer | Sovereign | Aegis | Colossus | Immortal |
| 5 | Lv 100 + 30 000 Gold | Monarch of Iron | Monarch of Shadows | Monarch of Knowledge | Monarch of Wisdom | Monarch of Insight | Monarch of Crowns | Monarch of Life | Monarch of Stone | Monarch of Will |

**Recompensas de cada tier** (extra aos 3 pontos livres normais por nível):
| Tier | Pontos livres extra | Bónus de XP nos hábitos cujo atributo principal é o da classe |
|---|---|---|
| 1 | +10 | +5 % |
| 2 | +15 | +10 % |
| 3 | +20 | +15 % |
| 4 | +25 | +20 % |
| 5 | +30 | +25 % |

**Porque é que o Gold é pago e não apenas "possuído":** funciona como *gold sink*. Obriga a escolher entre gastar
na Shop (recompensas reais) e poupar para evoluir a classe, e impede a acumulação infinita de Gold.

### 3.8 Títulos
Desbloqueados por conquistas (ex.: "The One Who Overcame Adversity" = sair da Penalty Zone; "Unbreakable" = streak de 66 dias). O título ativo aparece na Status Window.

---

## 4. Penalty Zone
1. Falhar hábitos tira HP (fórmula 2.5).
2. **HP = 0 → Penalty Zone:**
   - perdes **10 % do XP do nível atual** (nunca desces de nível) e **20 % do Gold**;
   - a **Shop fica bloqueada**;
   - é gerada uma **Penalty Quest** obrigatória, um hábito extra de rank igual ou superior ao teu rank médio, com prazo de 24 h.
3. Completar a Penalty Quest devolve **50 % do HP** e desbloqueia a Shop. Se falhares, é gerada outra.

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
- **Com IA (opcional):** se houver chave de API nas Settings, o motor envia um resumo (atributo, hábito, gatilho) e a IA devolve nome e descrição temáticos. Se falhar ou estiver sem internet, usa as tabelas.
- O motor de regras decide sempre **quando** e **que tipo** de Skill aparece. A IA só escreve o texto.

### 5.3 Nível (Proficiency pelo uso)
- Cada vez que completas um hábito ligado à Skill, ela ganha **proficiência** (`+r`).
- Lv.1 → Lv.10 (MAX). Proficiência para o nível seguinte: `10 × nível`.

### 5.4 Efeito: bónus de XP
`+2 % de XP por nível da Skill` nos hábitos ligados. O bónus total das Skills tem um teto de **+50 %** para não desequilibrar.

---

## 6. Recompensas

### 6.1 Gold e Shop
- O Gold ganha-se com os hábitos (2.5).
- **Shop com recompensas criadas por ti** (ex.: "1 h de videojogos = 300 Gold"). A app sugere preços por rank.
- Bloqueada durante a Penalty Zone.

### 6.2 Loot (inventário)
Cada hábito completado tem uma probabilidade de *drop* (tabela 2.4). Itens:
| Item | Efeito |
|---|---|
| HP Potion | +30 HP |
| Streak Shield | Protege a streak de um hábito numa falha |
| XP Scroll | ×2 XP nas próximas 3 quests |
| Gold Pouch | +50 a 200 Gold |

### 6.3 Achievements
Exemplos: "First Step" (1.ª quest), "Week Warrior" (7 dias a 100 %), "Level 10", "Survivor" (sair da Penalty Zone), "Polyglot" (100 h de línguas).

---

## 7. Estatísticas
- **Calendário por hábito:** cada dia é pintado com intensidade proporcional a `r` (0 % vazio → 100 % cor máxima). Nos quantitativos, 1,5/2 L aparece a 75 %.
- **Weekly Report `[SYSTEM]`:** gerado na segunda-feira com o resumo da semana anterior: XP/Gold ganho, níveis subidos, taxa de cumprimento por hábito, melhor e pior hábito, streaks, Skills novas ou subidas, HP perdido e passagens pela Penalty Zone.

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
- **Ecrã principal:** à esquerda a **Status Window** (nome, nível, Hunter Rank, título, classe, barras de HP e XP, 9 atributos, pontos livres). À direita as **Quests** em separadores **Daily / Weekly / Monthly**.
- **Barra lateral:** Status · Quests · Skills · Inventory · Shop · Calendar · Report · Achievements · Settings.
- Popups animados `[SYSTEM]` para Level Up, Skill nova, Loot e Penalty.

---

## 12. Arquitetura (resumo)
```
app/
  models/        dataclasses: Player, Habit, HabitLog, Skill, Item, ...
  engine/        lógica pura do jogo (XP, níveis, HP, streaks, skills, loot) — sem UI, 100 % testável
  persistence/   SQLite (repositórios)
  services/      relógio/catch-up, lembretes, IA opcional, PIN
  ui/            PySide6 (janelas, widgets, tema "System")
tests/           pytest para o engine
```
**Princípio-chave:** separar **regras do jogo (engine)** da **interface (ui)**. Isto permite testar as fórmulas automaticamente e trocar a UI sem mexer nas regras.
Distribuição: **PyInstaller** gera um `.exe` para Windows.
