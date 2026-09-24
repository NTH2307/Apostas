"""Lesões de jogadores via API-Football (https://www.api-football.com,
free tier: 100 pedidos/dia). Puramente informativo — usado pelo relatório
do comando `apostas --lesoes` para mostrares ao lado de cada jogo, NUNCA
para ajustar as probabilidades do modelo (identificar quanto uma lesão
específica vale em golos esperados é um problema muito mais difícil do
que esta ferramenta tenta resolver).

⚠️ Os dados podem não estar atualizados ao minuto — confirma sempre na
véspera do jogo (site do clube, imprensa) antes de decidires com isto.
"""
from datetime import datetime, timedelta, timezone

import requests

import config


def _pedir(caminho: str, params: dict) -> list[dict]:
    if not config.API_FOOTBALL_KEY:
        raise RuntimeError(
            "API_FOOTBALL_KEY não configurada — cria uma chave grátis em "
            "https://dashboard.api-football.com/register e define "
            "API_FOOTBALL_KEY no .env."
        )
    resposta = requests.get(
        f"{config.API_FOOTBALL_BASE_URL}/{caminho}",
        headers={"x-apisports-key": config.API_FOOTBALL_KEY},
        params=params,
        timeout=15,
    )
    resposta.raise_for_status()
    corpo = resposta.json()
    erros = corpo.get("errors")
    if erros:
        raise RuntimeError(f"API-Football devolveu erro: {erros}")
    return corpo.get("response", [])


def procurar_equipa_id(nome: str) -> int | None:
    """ID da API-Football da equipa cujo nome mais se aproxima de `nome`,
    ou None se a pesquisa não devolver nada."""
    resultados = _pedir("teams", {"search": nome})
    if not resultados:
        return None
    return resultados[0]["team"]["id"]


def lesoes_recentes(team_id: int, dias: int | None = None) -> list[dict]:
    """Lesões reportadas para esta equipa nos últimos `dias` dias (omissão:
    LESOES_DIAS_RECENTES), mais recentes primeiro, sem repetir jogador.
    Cada item: {"jogador": str, "motivo": str, "data": str (AAAA-MM-DD)}."""
    dias = config.LESOES_DIAS_RECENTES if dias is None else dias
    ano = datetime.now(timezone.utc).year
    resultados = _pedir("injuries", {"team": team_id, "season": ano})
    limite = datetime.now(timezone.utc) - timedelta(days=dias)

    candidatos = []
    for r in resultados:
        data_str = r.get("fixture", {}).get("date", "")
        if not data_str:
            continue
        try:
            data = datetime.fromisoformat(data_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        if data < limite:
            continue
        jogador = r.get("player", {})
        candidatos.append({
            "jogador": jogador.get("name", "?"),
            "motivo": jogador.get("reason") or jogador.get("type") or "?",
            "data": data.date().isoformat(),
        })

    vistos = set()
    unicos = []
    for l in sorted(candidatos, key=lambda x: x["data"], reverse=True):
        if l["jogador"] not in vistos:
            vistos.add(l["jogador"])
            unicos.append(l)
    return unicos
