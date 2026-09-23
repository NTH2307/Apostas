"""Estatísticas de golos por equipa via football-data.org
(https://www.football-data.org, free tier: 10 pedidos/minuto, cobre as
principais ligas europeias). Usado para calcular a força de ataque/defesa
de cada equipa, input do modelo de Poisson (ver app/poisson.py).

⚠️ Isto trata todos os jogos da janela igualmente (não dá mais peso aos
mais recentes) — é uma média da época, não "forma recente" no sentido
estrito.
"""
import time

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


def calcular_forcas(jogos: list[dict]) -> dict:
    """A partir de jogos terminados, calcula a força de ataque/defesa de
    cada equipa em casa e fora, relativa à média da competição.

    Devolve {"media_golos_casa": float, "media_golos_fora": float,
    "equipas": {"<nome>": {"ataque_casa", "defesa_casa", "ataque_fora",
    "defesa_fora"}}}. Uma equipa com poucos ou nenhuns jogos numa das
    vertentes (casa/fora) fica com força neutra (1.0) nessa vertente.
    """
    if not jogos:
        return {"media_golos_casa": 0.0, "media_golos_fora": 0.0, "equipas": {}}

    media_golos_casa = sum(j["golos_casa"] for j in jogos) / len(jogos)
    media_golos_fora = sum(j["golos_fora"] for j in jogos) / len(jogos)

    marcados_casa: dict = {}
    sofridos_casa: dict = {}
    jogos_casa: dict = {}
    marcados_fora: dict = {}
    sofridos_fora: dict = {}
    jogos_fora: dict = {}

    for j in jogos:
        casa, fora = j["casa"], j["fora"]
        marcados_casa[casa] = marcados_casa.get(casa, 0) + j["golos_casa"]
        sofridos_casa[casa] = sofridos_casa.get(casa, 0) + j["golos_fora"]
        jogos_casa[casa] = jogos_casa.get(casa, 0) + 1

        marcados_fora[fora] = marcados_fora.get(fora, 0) + j["golos_fora"]
        sofridos_fora[fora] = sofridos_fora.get(fora, 0) + j["golos_casa"]
        jogos_fora[fora] = jogos_fora.get(fora, 0) + 1

    equipas = {}
    for nome in set(jogos_casa) | set(jogos_fora):
        n_casa = jogos_casa.get(nome, 0)
        n_fora = jogos_fora.get(nome, 0)
        equipas[nome] = {
            "ataque_casa": (marcados_casa.get(nome, 0) / n_casa / media_golos_casa) if n_casa and media_golos_casa else 1.0,
            "defesa_casa": (sofridos_casa.get(nome, 0) / n_casa / media_golos_fora) if n_casa and media_golos_fora else 1.0,
            "ataque_fora": (marcados_fora.get(nome, 0) / n_fora / media_golos_fora) if n_fora and media_golos_fora else 1.0,
            "defesa_fora": (sofridos_fora.get(nome, 0) / n_fora / media_golos_casa) if n_fora and media_golos_casa else 1.0,
        }

    return {"media_golos_casa": media_golos_casa, "media_golos_fora": media_golos_fora, "equipas": equipas}
