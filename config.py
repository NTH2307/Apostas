"""
Configuração do BettingBot. Revê estes valores antes de usar a sério —
sobretudo os marcados com ⚠️.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Fonte de odds (The Odds API — https://the-odds-api.com, tem free tier) ---
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
ODDS_API_BASE_URL = os.getenv("ODDS_API_BASE_URL", "https://api.the-odds-api.com/v4")
DESPORTOS = [d.strip() for d in os.getenv("DESPORTOS", "soccer_epl,tennis_atp,basketball_nba").split(",") if d.strip()]
REGIOES = os.getenv("REGIOES", "eu")            # eu, uk, us, au — casas de apostas cobertas
MERCADOS = os.getenv("MERCADOS", "h2h")         # h2h = vencedor (moneyline / 1X2 sem empate em 2 vias)

# --- Deteção de arbitragem/valor ---
MARGEM_MINIMA_ARBITRAGEM = float(os.getenv("MARGEM_MINIMA_ARBITRAGEM", 0.01))  # 1% de lucro mínimo garantido
MARGEM_MINIMA_VALOR = float(os.getenv("MARGEM_MINIMA_VALOR", 0.03))            # 3% acima da probabilidade justa estimada

# Ignora apostas de valor em odds acima disto — em odds muito altas
# (azarões), o "valor" calculado é muito mais sensível a ruído de uma única
# bookmaker e ao "favorite-longshot bias" (ver README). None desativa o limite.
ODD_MAXIMA_VALOR = float(os.getenv("ODD_MAXIMA_VALOR", 4.0))

# Lista de bookmakers a considerar (nomes como aparecem na The Odds API,
# separados por vírgula). Vazio = todas. Usa isto para excluir casas não
# licenciadas na tua jurisdição ou pouco fiáveis do cálculo.
BOOKMAKERS_FIAVEIS = [b.strip() for b in os.getenv("BOOKMAKERS_FIAVEIS", "").split(",") if b.strip()]

# --- Modelo estatístico próprio (golos, ver app/stats.py e app/poisson.py) ---
# Estatísticas de golos via football-data.org (free tier, cobre as
# principais ligas europeias): https://www.football-data.org/client/register
FOOTBALL_DATA_API_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "")
FOOTBALL_DATA_BASE_URL = os.getenv("FOOTBALL_DATA_BASE_URL", "https://api.football-data.org/v4")
MODELO_JOGOS_HISTORICO = int(os.getenv("MODELO_JOGOS_HISTORICO", 200))  # jogos terminados usados para calcular forças
MODELO_MARGEM_MINIMA = float(os.getenv("MODELO_MARGEM_MINIMA", 0.05))   # mais exigente que o valor de mercado — o modelo também pode estar errado
# "Jogos fictícios" de equipa média somados a cada equipa ao calcular forças
# — impede que 1-2 jogos atípicos deem forças extremas (ex: 0 golos esperados).
MODELO_PESO_PRIOR = float(os.getenv("MODELO_PESO_PRIOR", 5))
# Um jogo com esta antiguidade (em dias) pesa metade de um jogo de hoje —
# dá mais peso à forma recente do que à média da época toda. 0 desativa
# (todos os jogos pesam igual).
MODELO_MEIA_VIDA_DIAS = float(os.getenv("MODELO_MEIA_VIDA_DIAS", 60))

# --- Sugestões de aposta (comando `apostas`, ver app/recomendacao.py) ---
# O palpite do 1X2 é sempre o lado favorito do modelo — opinião pura do
# modelo, nunca comparada com odds nem com casas de apostas.
# Peso do modelo vs. média da liga na probabilidade de golos (over/under,
# ambas marcam) — não temos odds desses mercados para comparar. Estas duas
# opiniões aparecem sempre, tal como o 1X2 — nunca são escondidas.
APOSTAS_PESO_MODELO_GOLOS = float(os.getenv("APOSTAS_PESO_MODELO_GOLOS", 0.6))
# Janela de dias a analisar por omissão — alarga para veres sempre vários
# jogos de várias ligas (a maioria das ligas não joga todos os dias).
APOSTAS_DIAS = int(os.getenv("APOSTAS_DIAS", 5))
RELATORIO_PATH = os.getenv("RELATORIO_PATH", os.path.join(os.path.dirname(__file__), "relatorio_apostas.html"))

# Nota sobre lesões: chegámos a integrar a API-Football, mas o free tier
# dela só dá acesso a épocas de 2022-2024, não à época atual — inútil para
# lesões de agora. O relatório mostra em vez disso um link de pesquisa
# manual por equipa (app/recomendacao.py, `link_pesquisa_lesoes`), sem
# custo nem configuração.

# Pares "código football-data.org:chave The Odds API" para `modelo --todas`
# — todas as competições de futebol de clubes cobertas pelo free tier da
# football-data.org (o modelo de Poisson só serve para futebol, não
# basquetebol; competições de seleções como a Liga das Nações não estão
# disponíveis no free tier — usa `python main.py competicoes` para
# confirmares o que o teu plano cobre). Edita à vontade; separa por vírgula.
COMPETICOES_MODELO = [
    tuple(par.split(":")) for par in os.getenv(
        "COMPETICOES_MODELO",
        "PL:soccer_epl,PD:soccer_spain_la_liga,SA:soccer_italy_serie_a,"
        "BL1:soccer_germany_bundesliga,FL1:soccer_france_ligue_one,"
        "PPL:soccer_portugal_primeira_liga,CL:soccer_uefa_champs_league,"
        "ELC:soccer_efl_champ,DED:soccer_netherlands_eredivisie,"
        "BSA:soccer_brazil_campeonato,CLI:soccer_conmebol_copa_libertadores",
    ).split(",") if par.strip()
]

# --- Gestão de risco ⚠️ revê sempre antes de arriscar dinheiro real ---
CAPITAL_INICIAL = float(os.getenv("CAPITAL_INICIAL", 100))     # unidades monetárias (ex: EUR)
STAKE_MAXIMA_POR_APOSTA = float(os.getenv("STAKE_MAXIMA_POR_APOSTA", 10))
FRACAO_KELLY = float(os.getenv("FRACAO_KELLY", 0.25))          # Kelly fracionado — reduz variância vs. Kelly completo

# --- Execução ⚠️ desligado por omissão — só a Betfair Exchange tem API pública
# para apostar por programa; qualquer outra casa nestes campos só serve para
# registo/simulação, nunca envia ordens reais.
EXECUCAO_AUTOMATICA = os.getenv("EXECUCAO_AUTOMATICA", "false").lower() == "true"
MODO_PAPER = os.getenv("MODO_PAPER", "true").lower() == "true"  # simula apostas sem gastar dinheiro real

BETFAIR_APP_KEY = os.getenv("BETFAIR_APP_KEY", "")
BETFAIR_USERNAME = os.getenv("BETFAIR_USERNAME", "")
BETFAIR_PASSWORD = os.getenv("BETFAIR_PASSWORD", "")
BETFAIR_CERTS_DIR = os.getenv("BETFAIR_CERTS_DIR", "")  # pasta com client-2048.crt / client-2048.key

# --- Ciclo do bot em modo live ---
INTERVALO_VERIFICACAO_SEGUNDOS = int(os.getenv("INTERVALO_VERIFICACAO_SEGUNDOS", 300))

# --- Notificações Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Ficheiros locais ---
ESTADO_PATH = os.getenv("ESTADO_PATH", os.path.join(os.path.dirname(__file__), "estado.json"))
