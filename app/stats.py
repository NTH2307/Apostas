"""Estatísticas de golos por equipa via football-data.org
(https://www.football-data.org, free tier: 10 pedidos/minuto, cobre as
principais ligas europeias). Usado para calcular a força de ataque/defesa
de cada equipa, input do modelo de Poisson (ver app/poisson.py).

Cada jogo pesa mais ou menos consoante a antiguidade (decaimento
exponencial, ver `_pesos_por_recencia`/`MODELO_MEIA_VIDA_DIAS`) — uma
equipa em má fase recente não fica "escondida" atrás de bons resultados
de há meses.
"""
import time
from datetime import datetime

import requests

import config


def buscar_jogos_terminados(competicao: str, limite: int = 200) -> list[dict]:
    """Jogos já terminados de uma competição (código football-data.org, ex:
    'PL', 'PD', 'SA', 'BL1', 'FL1', 'PPL', 'CL'), mais recentes primeiro.
    Cada jogo: {"casa": str, "fora": str, "golos_casa": int, "golos_fora": int, "data": str}.

    Se o free tier limitar o número de pedidos por minuto (HTTP 429), espera
    pelo tempo indicado em Retry-After e tenta mais uma vez antes de desistir.
    """
    if not config.FOOTBALL_DATA_API_KEY:
        raise RuntimeError(
            "FOOTBALL_DATA_API_KEY não configurada — cria uma chave grátis em "
            "https://www.football-data.org/client/register e define "
            "FOOTBALL_DATA_API_KEY no .env."
        )

    resposta = _pedir_com_retry_em_429(competicao)
    resposta.raise_for_status()
    jogos = resposta.json().get("matches", [])
    jogos = sorted(jogos, key=lambda j: j["utcDate"], reverse=True)
    return _normalizar_jogos(jogos)[:limite]


def listar_competicoes(filtro: str | None = None) -> list[dict]:
    """Lista as competições disponíveis no teu plano da football-data.org
    (o código a usar em `--competicao`) — para encontrares a chave certa em
    vez de adivinhar (ex: para a Liga das Nações). `filtro` procura (sem
    distinguir maiúsculas/minúsculas) no nome ou código."""
    if not config.FOOTBALL_DATA_API_KEY:
        raise RuntimeError(
            "FOOTBALL_DATA_API_KEY não configurada — cria uma chave grátis em "
            "https://www.football-data.org/client/register e define "
            "FOOTBALL_DATA_API_KEY no .env."
        )
    resposta = requests.get(
        f"{config.FOOTBALL_DATA_BASE_URL}/competitions",
        headers={"X-Auth-Token": config.FOOTBALL_DATA_API_KEY},
        timeout=15,
    )
    resposta.raise_for_status()
    competicoes = resposta.json().get("competitions", [])
    return _filtrar_competicoes(competicoes, filtro)


def _filtrar_competicoes(competicoes: list[dict], filtro: str | None) -> list[dict]:
    if not filtro:
        return competicoes
    filtro_lower = filtro.lower()
    return [
        c for c in competicoes
        if filtro_lower in c.get("name", "").lower()
        or filtro_lower in c.get("code", "").lower()
        or filtro_lower in (c.get("area") or {}).get("name", "").lower()
    ]


def _pedir_com_retry_em_429(competicao: str, tentativas: int = 2):
    for tentativa in range(tentativas):
        resposta = requests.get(
            f"{config.FOOTBALL_DATA_BASE_URL}/competitions/{competicao}/matches",
            headers={"X-Auth-Token": config.FOOTBALL_DATA_API_KEY},
            params={"status": "FINISHED"},
            timeout=15,
        )
        if resposta.status_code == 429 and tentativa < tentativas - 1:
            espera = int(resposta.headers.get("Retry-After", 60))
            print(f"[football-data.org] limite de pedidos/minuto atingido — a aguardar {espera}s e a repetir '{competicao}'...")
            time.sleep(espera)
            continue
        return resposta
    return resposta


def _normalizar_jogos(jogos_brutos: list[dict]) -> list[dict]:
    return [
        {
            "casa": j["homeTeam"]["name"],
            "fora": j["awayTeam"]["name"],
            "golos_casa": j["score"]["fullTime"]["home"],
            "golos_fora": j["score"]["fullTime"]["away"],
            "data": j.get("utcDate", ""),
        }
        for j in jogos_brutos
        if j.get("score", {}).get("fullTime", {}).get("home") is not None
    ]


def _encolher(total: float, n_jogos: int, media_liga: float, peso_prior: float) -> float:
    """Força relativa à média da liga, "encolhida" para 1.0 (equipa média)
    como se a equipa tivesse mais `peso_prior` jogos perfeitamente médios.
    Com muitos jogos quase não mexe; com 1-2 jogos impede conclusões
    extremas (ex: "nunca marca" só porque falhou 2 jogos)."""
    if not media_liga or n_jogos + peso_prior == 0:
        return 1.0
    bruto = (total / n_jogos / media_liga) if n_jogos else 1.0
    return (n_jogos * bruto + peso_prior * 1.0) / (n_jogos + peso_prior)


def _parse_data(data_str: str):
    if not data_str:
        return None
    try:
        return datetime.fromisoformat(data_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def _pesos_por_recencia(jogos: list[dict], meia_vida_dias: float) -> list[float]:
    """Peso de cada jogo por decaimento exponencial: um jogo `meia_vida_dias`
    mais antigo do que o mais recente da amostra pesa metade. Jogos sem
    data reconhecível (ou meia_vida_dias<=0) pesam sempre 1.0 (sem decaimento)."""
    if not meia_vida_dias:
        return [1.0] * len(jogos)
    datas = [_parse_data(j.get("data", "")) for j in jogos]
    referencia = max((d for d in datas if d), default=None)
    if not referencia:
        return [1.0] * len(jogos)
    return [
        0.5 ** (max((referencia - d).days, 0) / meia_vida_dias) if d else 1.0
        for d in datas
    ]


def calcular_forcas(jogos: list[dict], peso_prior: float | None = None, meia_vida_dias: float | None = None) -> dict:
    """A partir de jogos terminados, calcula a força de ataque/defesa de
    cada equipa em casa e fora, relativa à média da competição.

    Devolve {"media_golos_casa": float, "media_golos_fora": float,
    "equipas": {"<nome>": {"ataque_casa", "defesa_casa", "ataque_fora",
    "defesa_fora", "jogos"}}}. As forças são encolhidas para a média da
    liga consoante o peso de jogos disponível (ver `_encolher`, peso
    `config.MODELO_PESO_PRIOR`; `peso_prior=0` dá as forças brutas) e cada
    jogo pesa mais ou menos consoante a antiguidade (`config.MODELO_MEIA_VIDA_DIAS`;
    `meia_vida_dias=0` desativa o decaimento). `equipas[x]["jogos"]`
    continua a ser a contagem real de jogos (não pesada), usada para medir
    confiança da amostra.
    """
    if peso_prior is None:
        peso_prior = config.MODELO_PESO_PRIOR
    if meia_vida_dias is None:
        meia_vida_dias = config.MODELO_MEIA_VIDA_DIAS
    if not jogos:
        return {"media_golos_casa": 0.0, "media_golos_fora": 0.0, "equipas": {}}

    pesos = _pesos_por_recencia(jogos, meia_vida_dias)
    soma_pesos = sum(pesos)
    media_golos_casa = sum(j["golos_casa"] * p for j, p in zip(jogos, pesos)) / soma_pesos
    media_golos_fora = sum(j["golos_fora"] * p for j, p in zip(jogos, pesos)) / soma_pesos

    marcados_casa: dict = {}
    sofridos_casa: dict = {}
    peso_casa: dict = {}
    n_casa: dict = {}
    marcados_fora: dict = {}
    sofridos_fora: dict = {}
    peso_fora: dict = {}
    n_fora: dict = {}

    for j, p in zip(jogos, pesos):
        casa, fora = j["casa"], j["fora"]
        marcados_casa[casa] = marcados_casa.get(casa, 0) + j["golos_casa"] * p
        sofridos_casa[casa] = sofridos_casa.get(casa, 0) + j["golos_fora"] * p
        peso_casa[casa] = peso_casa.get(casa, 0) + p
        n_casa[casa] = n_casa.get(casa, 0) + 1

        marcados_fora[fora] = marcados_fora.get(fora, 0) + j["golos_fora"] * p
        sofridos_fora[fora] = sofridos_fora.get(fora, 0) + j["golos_casa"] * p
        peso_fora[fora] = peso_fora.get(fora, 0) + p
        n_fora[fora] = n_fora.get(fora, 0) + 1

    equipas = {}
    for nome in set(n_casa) | set(n_fora):
        pc, pf = peso_casa.get(nome, 0), peso_fora.get(nome, 0)
        equipas[nome] = {
            "ataque_casa": _encolher(marcados_casa.get(nome, 0), pc, media_golos_casa, peso_prior),
            "defesa_casa": _encolher(sofridos_casa.get(nome, 0), pc, media_golos_fora, peso_prior),
            "ataque_fora": _encolher(marcados_fora.get(nome, 0), pf, media_golos_fora, peso_prior),
            "defesa_fora": _encolher(sofridos_fora.get(nome, 0), pf, media_golos_casa, peso_prior),
            "jogos": n_casa.get(nome, 0) + n_fora.get(nome, 0),
        }

    return {"media_golos_casa": media_golos_casa, "media_golos_fora": media_golos_fora, "equipas": equipas}
