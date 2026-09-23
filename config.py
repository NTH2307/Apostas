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
