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
4. **Dimensionamento de apostas** (`app/staking.py`): Kelly fracionado para
   apostas de valor (reduz a variância face ao Kelly completo).
5. **Execução** (`app/executor.py` + `app/betfair_client.py`): em modo
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

Lista de chaves de desporto disponíveis:
[the-odds-api.com/sports-odds-data/sports-apis.html](https://the-odds-api.com/sports-odds-data/sports-apis.html).

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
odds (formato normalizado e formato bruto da The Odds API), e as regras de
quando o executor pode ou não executar uma ordem real. Correm
automaticamente em CI (`.github/workflows/bettingbot-tests.yml`) em cada
push/PR que toque na pasta `bettingbot/`.

## Estrutura do projeto

- `config.py` — todos os parâmetros (odds, deteção, risco, execução)
- `app/odds.py` — obtenção de odds (The Odds API ou JSON local)
- `app/arbitrage.py` — deteção de arbitragem e de apostas de valor
- `app/staking.py` — dimensionamento de apostas (Kelly fracionado)
- `app/notifier.py` — alertas por Telegram
- `app/betfair_client.py` — cliente da Betfair Exchange (execução real)
- `app/executor.py` — execução de apostas (paper ou real, só Betfair)
- `app/live.py` — loop de verificação contínua
- `main.py` — CLI (`arbitragem` / `valor` / `live`)
- `data/exemplo_odds.json` — dados de exemplo para testar sem API key
- `tests/` — testes automatizados (pytest)

## Limitações atuais (é um MVP)

- Mercados só de vencedor (`h2h`) — sem over/under, handicaps, etc.
- "Valor" é uma heurística sobre o consenso do mercado, não um modelo
  preditivo próprio treinado em dados históricos do desporto.
- Sem backtesting histórico real: ao contrário de preços de criptomoedas,
  odds históricas com resultados liquidados não estão disponíveis de forma
  simples e gratuita — o bot só analisa odds ao vivo/pré-jogo.
- Execução automática limitada à Betfair Exchange, e ainda sem o mapeamento
  automático evento → `market_id`/`selection_id` da Betfair (ver secção
  acima).
- Sem gestão de posições simultâneas nem limite agregado de exposição
  entre eventos.

## Próximos passos possíveis

- Mapeamento automático de eventos da The Odds API para mercados da
  Betfair (via `list_market_catalogue`), para a execução real ficar
  completa.
- Mais mercados (over/under, handicaps asiáticos).
- Registo em base de dados do histórico de oportunidades e apostas
  simuladas, para avaliar a estratégia ao longo do tempo (equivalente ao
  que o `cryptobot` já mostrou: comparar sempre com o resultado de "não
  fazer nada").
