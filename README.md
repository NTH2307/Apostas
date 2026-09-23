# BettingBot

Ferramenta de análise de odds desportivas: procura **arbitragens** (surebets)
e **apostas de valor** entre várias casas de apostas, envia alertas
(Telegram), e — só na **Betfair Exchange** — pode colocar apostas
automaticamente.

## ⚠️ Importante — lê isto antes de arriscar dinheiro real

- **Isto não é aconselhamento de apostas nem uma máquina de ganhar dinheiro.**
  É uma ferramenta educacional/MVP. Apostar envolve risco real de perder
  dinheiro, incluindo tudo o que arriscares.
- **A esmagadora maioria dos apostadores perde dinheiro a longo prazo** — as
  casas de apostas fixam as odds com uma margem (overround) precisamente
  para isso. As duas únicas abordagens com fundamento matemático que este
  bot implementa são:
  - **Arbitragem**: apostar em todos os resultados possíveis em casas
    diferentes quando a soma das melhores odds disponíveis garante lucro
    seja qual for o resultado. Na teoria é "dinheiro grátis" — na prática,
    as janelas fecham-se em segundos, os limites de stake das casas de
    apostas fixas são baixos para contas novas/lucrativas, e **é normal as
    casas limitarem ou fecharem contas que apostam sistematicamente em
    arbitragem** (não é ilegal, mas viola quase sempre os termos de
    serviço delas, e o risco é a conta, não o dinheiro apostado).
  - **Valor (value betting)**: apostar quando uma casa paga uma odd acima
    da probabilidade "justa" estimada pelo consenso do mercado. Isto **não
    garante lucro em nenhuma aposta individual** — é uma vantagem
    estatística que só se manifesta a longo prazo, sobre centenas/milhares
    de apostas, exatamente como a vantagem da casa nos jogos de casino.
- Por omissão, o bot corre em **modo paper** (`MODO_PAPER=true` e
  `EXECUCAO_AUTOMATICA=false`): não aposta dinheiro real, só regista o que
  teria apostado. Só ativa execução automática depois de validares bem a
  deteção de oportunidades manualmente.
- **Execução automática real só funciona na Betfair Exchange** (ver secção
  própria abaixo) — é a única casa com API pública pensada para apostar por
  programa. Qualquer outra bookmaker configurada fica sempre em modo
  registo/paper, porque apostar por bot nessas plataformas normalmente
  viola os termos de serviço delas e pode levar ao fecho da conta.
- Guarda sempre as tuas credenciais (`.env`, nunca commitado) fora do
  controlo de versões.
- **Verifica sempre a legalidade das apostas desportivas online na tua
  jurisdição** antes de usar este bot com dinheiro real — varia por país
  (e, nalguns, por região).

## Como funciona

1. **Odds** (`app/odds.py`): obtém odds de várias casas de apostas via
   [The Odds API](https://the-odds-api.com) (tem free tier), ou carrega um
   snapshot local em JSON (`data/exemplo_odds.json`) — útil para testar sem
   precisar de chave de API.
2. **Arbitragem** (`app/arbitrage.py`, função `detetar_arbitragem`):
   compara a melhor odd de cada resultado entre todas as casas do evento;
   se a soma das probabilidades implícitas (1/odd) for menor que 1, há
   arbitragem — calcula também os stakes que garantem o mesmo retorno
   independentemente do resultado.
3. **Valor** (`app/arbitrage.py`, função `detetar_valor`): estima a
   probabilidade "justa" de cada resultado removendo o overround médio do
   mercado (consenso entre casas), e assinala odds que pagam acima dessa
   probabilidade justa.
4. **Modelo estatístico próprio** (`app/stats.py` + `app/poisson.py` +
   `app/model.py`, comando `modelo`): calcula a força de ataque/defesa de
   cada equipa a partir de golos marcados/sofridos reais (via
   [football-data.org](https://www.football-data.org)), estima
   probabilidades com um modelo de Poisson, e compara com as odds de
   mercado — uma segunda opinião independente do consenso das casas, em
   vez de só comparar casas entre si. Ver secção própria abaixo.
5. **Dimensionamento de apostas** (`app/staking.py`): Kelly fracionado para
   apostas de valor (reduz a variância face ao Kelly completo).
6. **Execução** (`app/executor.py` + `app/betfair_client.py`): em modo
   paper, só regista. Em modo real, só executa de facto apostas na Betfair
   Exchange — as restantes ficam sempre em registo manual.

## Instalar

```bash
cd bettingbot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edita o .env: ODDS_API_KEY, desportos, gestão de risco, Telegram
```

## Testar sem chave de API (dados de exemplo)

```bash
python main.py arbitragem --json data/exemplo_odds.json
python main.py valor --json data/exemplo_odds.json
```

## Com odds reais (precisa de `ODDS_API_KEY`)

Cria uma chave grátis em [the-odds-api.com](https://the-odds-api.com)
(free tier: 500 pedidos/mês) e define `ODDS_API_KEY` no `.env`.

```bash
python main.py arbitragem --desporto soccer_epl
python main.py valor --desporto tennis_atp --margem-minima 0.05
```

`--desporto` aceita várias chaves separadas por vírgula, para juntares
desportos diferentes numa só verificação — ex: só futebol e basquetebol:

```bash
python main.py valor --desporto soccer_epl,basketball_nba
```

### Encontrar a chave certa (ex: Liga das Nações, Liga Portugal)

A The Odds API tem uma chave por competição (não uma chave genérica
"futebol"). Para veres as disponíveis sem teres de consultar a
documentação:

```bash
python main.py desportos --filtro nations     # ex: soccer_uefa_nations_league
python main.py desportos --filtro portugal    # ex: soccer_portugal_primeira_liga
python main.py desportos                      # lista tudo
```

(lista completa também em
[the-odds-api.com/sports-odds-data/sports-apis.html](https://the-odds-api.com/sports-odds-data/sports-apis.html))

### Só jogos de um dia específico (ex: "amanhã")

```bash
python main.py valor --desporto soccer_epl --amanha
python main.py valor --desporto soccer_epl --dia 2026-09-28
```

Compara a hora de início de cada evento (que a API devolve em UTC) com o
dia indicado **na hora de Portugal** (`Europe/Lisbon`) — por isso um jogo às
23:30 UTC pode já contar como do dia seguinte, tal como aparece no teu
telemóvel.

### Reduzir falsos positivos (odds altas e bookmakers pouco fiáveis)

Em odds muito altas (azarões), um pequeno erro numa única bookmaker cria um
"valor" percentual desproporcionado, e há um efeito real bem documentado —
o **"favorite-longshot bias"**: as casas tendem a pagar ligeiramente a mais
em azarões de propósito, o que parece valor mas historicamente não se
traduz em lucro. Dois filtros ajudam a reduzir isto:

```bash
# só considera odds até 4.0, e só estas bookmakers
python main.py valor --desporto soccer_epl --odd-maxima 4.0 --bookmakers "Betfair,Betano,Bwin"
```

- `--odd-maxima` (ou `ODD_MAXIMA_VALOR` no `.env`, omissão 4.0, `0` desativa): ignora odds acima deste valor na deteção de **valor** (a arbitragem não é afetada — a garantia matemática dela não depende da magnitude da odd).
- `--bookmakers` (ou `BOOKMAKERS_FIAVEIS` no `.env`, separados por vírgula, vazio = todas): restringe o cálculo — tanto o consenso de probabilidade "justa" como as odds candidatas — só a estas casas. Usa nomes exatamente como a The Odds API os devolve (aparecem no output do bot); serve para excluir casas não licenciadas na tua jurisdição ou de fiabilidade duvidosa.

## Modelo estatístico próprio (golos, "quem ganha")

O `valor`/`arbitragem` só comparam casas de apostas entre si — nunca
"olham" para as equipas. O comando `modelo` faz isso: calcula a força de
ataque/defesa de cada equipa a partir de golos marcados/sofridos reais na
competição, estima golos esperados para o jogo com um **modelo de Poisson**
(a abordagem estatística clássica para golos em futebol), e compara essa
estimativa com as odds de mercado.

```bash
python main.py modelo --competicao PL --desporto soccer_epl --amanha
```

- `--competicao`: código da competição na **football-data.org** (ex: `PL`
  Premier League, `PD` La Liga, `SA` Serie A, `BL1` Bundesliga, `FL1`
  Ligue 1, `PPL` Primeira Liga, `CL` Champions League). Usa
  `python main.py competicoes --filtro <termo>` para encontrares o código
  exato de qualquer competição coberta pelo teu plano (ex: `--filtro
  nations` para a Liga das Nações, `--filtro europeu` para o Europeu) —
  **não adivinhes o código**, alguns são pouco óbvios e o comando confirma
  se a competição está mesmo disponível.
- `--desporto`: a chave da **mesma** competição na The Odds API (ex:
  `soccer_epl`) — usa `python main.py desportos --filtro <termo>` para
  encontrares a correspondente.
- Precisa de `FOOTBALL_DATA_API_KEY` no `.env` — cria uma chave grátis em
  [football-data.org/client/register](https://www.football-data.org/client/register).

Sem `--dia`/`--amanha`, mostra por omissão só a **próxima data com jogos**
agendados nessa competição (não despeja todas as jornadas futuras
misturadas) — e se pedires um dia sem jogos, diz-te qual é a próxima data
que tem, para ajustares o `--dia`.

⚠️ O free tier da football-data.org limita a 10 pedidos/minuto — `--todas`
espaça os pedidos automaticamente (~7s entre competições) para não
estourar o limite; se mesmo assim acontecer, tenta repetir uma vez
sozinho antes de desistir.

### Todas as ligas principais de uma vez

Em vez de correres liga a liga, `--todas` corre o modelo em todas as
competições de `COMPETICOES_MODELO` (.env — por omissão: Premier League,
La Liga, Serie A, Bundesliga, Ligue 1, Primeira Liga, Champions League):

```bash
python main.py modelo --todas --amanha
```

Uma competição que falhe (chave errada, sem jogos suficientes) fica
registada no resumo final e não trava as restantes. **Isto só cobre
futebol** — o modelo de Poisson e a football-data.org não servem para
basquetebol (é um desporto de pontuação muito diferente, precisaria de
outro modelo e outra fonte de dados).

Para adicionares mais competições (ex: Liga das Nações, outras ligas),
edita `COMPETICOES_MODELO` no `.env` no formato
`código_football_data:chave_the_odds_api`, separados por vírgula — usa
`competicoes --filtro` e `desportos --filtro` para confirmares os dois
códigos antes de adicionares:

```bash
python main.py competicoes --filtro nations
python main.py desportos --filtro nations
# .env: COMPETICOES_MODELO=PL:soccer_epl,...,<código_encontrado>:<chave_encontrada>
```

Para cada jogo mostra sempre: os golos esperados do modelo, a probabilidade
1X2 do modelo (e o favorito segundo o modelo), e a opinião do modelo sobre
over/under 2.5 golos e ambas marcam (BTTS). Quando o mercado paga mais do
que o modelo acha justo no 1X2, assinala isso como discrepância.

⚠️ Pontos importantes a levar a sério:
- **Golos/BTTS são só a opinião do modelo** — ainda não há comparação com
  odds reais desses mercados (só o 1X2/vencedor está integrado com odds).
- O modelo é uma **média da época** (não pesa jogos recentes mais do que
  antigos) e não sabe nada sobre lesões, suspensões, motivação ou
  contexto do jogo — só golos marcados/sofridos.
- **Isto não bate o mercado de forma fiável.** As casas de apostas sérias
  (Pinnacle, Betfair) já usam modelos deste tipo — e bem mais sofisticados
  — para fixar as odds em primeiro lugar. Uma discrepância pode ser o
  modelo a acertar onde o mercado erra, ou o modelo simplesmente a estar
  errado (falta-lhe informação que o mercado tem). Usa como ponto de
  partida para pesquisares mais, nunca como certeza.

## Resumo diário (recomendado para uso do dia a dia)

Em vez de correres `valor`/`arbitragem` à mão sempre que te lembras,
`resumo` corre **uma vez** sobre todas as competições em `DESPORTOS` (no
`.env`) e manda-te **sempre** uma mensagem de Telegram no fim — mesmo
"nada encontrado hoje" — para saberes que a verificação correu (silêncio
total seria ambíguo: bot avariado ou só sem oportunidades?).

```bash
python main.py resumo
```

Pensado para correr uma vez por dia via agendador, não à mão. No Windows,
usa o **Agendador de Tarefas** (Task Scheduler):
1. Cria uma tarefa nova → acionador "Diariamente" à hora que preferires.
2. Ação "Iniciar um programa": aponta para o `python.exe` dentro do
   `.venv` (ex: `C:\Users\<o teu utilizador>\reciboverde\bettingbot\.venv\Scripts\python.exe`),
   com argumentos `main.py resumo` e "Iniciar em"
   `C:\Users\<o teu utilizador>\reciboverde\bettingbot`.

⚠️ Cuidado com o número de competições em `DESPORTOS`: o free tier da The
Odds API é 500 pedidos/mês, e cada competição = 1 pedido por verificação
(`resumo` só faz 1 verificação, `live` faz uma a cada
`INTERVALO_VERIFICACAO_SEGUNDOS`). Com 8 competições, `resumo` 1x/dia fica
bem dentro do limite (~240/mês) — não metas "todas as competições
existentes" ou estouras a chave a meio do mês.

## Modo live (alertas e/ou execução automática)

```bash
python main.py live
```

Corre num loop (`Ctrl+C` para parar), verificando os desportos definidos em
`DESPORTOS` no `.env` a cada `INTERVALO_VERIFICACAO_SEGUNDOS`. Notifica por
Telegram sempre que encontra arbitragem ou valor; só coloca apostas reais
(Betfair) se `EXECUCAO_AUTOMATICA=true` e `MODO_PAPER=false`.

### Alertas por Telegram

1. Cria um bot com o [@BotFather](https://t.me/BotFather) e guarda o token.
2. Envia uma mensagem ao teu bot e visita
   `https://api.telegram.org/bot<TOKEN>/getUpdates` para obter o `chat_id`.
3. Preenche `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` no `.env`.

## Execução automática (Betfair Exchange)

1. Cria conta na [Betfair Exchange](https://www.betfair.com) e pede uma
   **App Key** (grátis, delayed data — ou paga, para dados em tempo real):
   [developer.betfair.com](https://developer.betfair.com/get-started/).
2. Gera um par de certificados cliente para login seguro (obrigatório para
   apostar por API — ver documentação da Betfair sobre "Non-Interactive
   (Certificate) Login").
3. `pip install betfairlightweight` (não vem no `requirements.txt` por
   omissão — só é preciso para execução real).
4. Preenche `BETFAIR_APP_KEY`, `BETFAIR_USERNAME`, `BETFAIR_PASSWORD` e
   `BETFAIR_CERTS_DIR` no `.env`.
5. Só depois de testares bem em modo paper: `EXECUCAO_AUTOMATICA=true` e
   `MODO_PAPER=false`.

⚠️ O bot atual identifica oportunidades por nome de equipa/resultado, mas
para apostar de facto na Betfair precisa do `market_id`/`selection_id`
exatos dessa casa — a integração completa de mapear eventos da The Odds
API para mercados da Betfair fica como próximo passo (ver abaixo);
por agora, a execução real por `app/betfair_client.py` está pronta a usar
quando tiveres esses IDs (ex: via `app.betting.list_market_catalogue` da
própria Betfair).

## Testes

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

Cobrem a matemática de arbitragem e de valor (deteção, filtragem por
margem mínima, cálculo de stakes), o Kelly fracionado, o carregamento de
odds (formato normalizado e formato bruto da The Odds API), o modelo de
Poisson e o cálculo de forças de ataque/defesa, e as regras de quando o
executor pode ou não executar uma ordem real. Correm automaticamente em CI
(`.github/workflows/bettingbot-tests.yml`) em cada push/PR que toque na
pasta `bettingbot/`.

## Estrutura do projeto

- `config.py` — todos os parâmetros (odds, deteção, modelo, risco, execução)
- `app/odds.py` — obtenção de odds (The Odds API ou JSON local)
- `app/arbitrage.py` — deteção de arbitragem e de apostas de valor
- `app/stats.py` — estatísticas de golos por equipa (football-data.org)
- `app/poisson.py` — modelo de Poisson (golos esperados → probabilidades)
- `app/model.py` — compara o modelo com as odds de mercado
- `app/staking.py` — dimensionamento de apostas (Kelly fracionado)
- `app/notifier.py` — alertas por Telegram
- `app/betfair_client.py` — cliente da Betfair Exchange (execução real)
- `app/executor.py` — execução de apostas (paper ou real, só Betfair)
- `app/live.py` — loop de verificação contínua e resumo diário
- `main.py` — CLI (`arbitragem` / `valor` / `modelo` / `resumo` / `desportos` / `live`)
- `data/exemplo_odds.json` — dados de exemplo para testar sem API key
- `tests/` — testes automatizados (pytest)

## Limitações atuais (é um MVP)

- Mercados de odds só de vencedor (`h2h`) — sem over/under, handicaps, etc.
  integrados com odds reais (o modelo calcula over/under e BTTS, mas ainda
  sem odds desses mercados para comparar).
- "Valor" (comparação entre casas) é uma heurística sobre o consenso do
  mercado. O `modelo` (comparação com golos reais) é mais parecido com uma
  previsão própria, mas continua a ser um modelo simples (média da época,
  sem lesões/suspensões/contexto) — nenhum dos dois garante lucro.
- Sem backtesting histórico real: ao contrário de preços de criptomoedas,
  odds históricas com resultados liquidados não estão disponíveis de forma
  simples e gratuita — o bot só analisa odds ao vivo/pré-jogo.
- Correspondência de nomes de equipas entre a The Odds API e a
  football-data.org é por normalização simples (remove acentos, pontuação,
  e tokens comuns de clube como "FC"/"AFC" do início ou fim do nome) —
  ajuda em casos comuns ("FC Barcelona" ↔ "Barcelona") mas pode falhar em
  nomes muito diferentes entre as duas fontes (traduções, abreviaturas
  pouco usuais).
- Execução automática limitada à Betfair Exchange, e ainda sem o mapeamento
  automático evento → `market_id`/`selection_id` da Betfair (ver secção
  acima).
- Sem gestão de posições simultâneas nem limite agregado de exposição
  entre eventos.

## Próximos passos possíveis

- Mapeamento automático de eventos da The Odds API para mercados da
  Betfair (via `list_market_catalogue`), para a execução real ficar
  completa.
- Integrar odds reais de over/under e BTTS, para o modelo comparar essas
  previsões com o mercado (não só o 1X2).
- Modelo com peso maior para jogos recentes (ex: decaimento exponencial)
  em vez de média simples da época.
- Registo em base de dados do histórico de oportunidades e apostas
  simuladas, para avaliar a estratégia ao longo do tempo (equivalente ao
  que o `cryptobot` já mostrou: comparar sempre com o resultado de "não
  fazer nada").
