"""Obtenção de odds via The Odds API (https://the-odds-api.com) — tem free
tier (500 pedidos/mês). Alternativa sem chave/API: carregar um snapshot
local em JSON (ver `carregar_json`, útil para testes e para o modo demo).

Formato normalizado de cada evento (dict):
{
    "id": str,
    "desporto": str,
    "hora_inicio": str (ISO 8601),
    "equipas": [str, str],
    "bookmakers": {
        "<nome_bookmaker>": {"<nome_resultado>": <odd float>, ...},
        ...
    },
}
"""
import json

import requests

import config


def buscar_odds(desporto: str, mercado: str | None = None) -> list[dict]:
    """Busca odds ao vivo/pré-jogo para um desporto (ex: 'soccer_epl').
    Lança RuntimeError com mensagem clara se faltar a chave da API.
    """
    if not config.ODDS_API_KEY:
        raise RuntimeError(
            "ODDS_API_KEY não configurada — cria uma chave grátis em "
            "https://the-odds-api.com e define ODDS_API_KEY no .env, ou usa "
            "--json com um snapshot local."
        )

    resposta = requests.get(
        f"{config.ODDS_API_BASE_URL}/sports/{desporto}/odds",
        params={
            "apiKey": config.ODDS_API_KEY,
            "regions": config.REGIOES,
            "markets": mercado or config.MERCADOS,
            "oddsFormat": "decimal",
        },
        timeout=15,
    )
    resposta.raise_for_status()
    return [_normalizar_evento(evento, desporto) for evento in resposta.json()]


def carregar_json(caminho: str) -> list[dict]:
    """Carrega um snapshot de eventos já normalizado (ver `data/exemplo_odds.json`),
    ou no formato bruto da The Odds API (deteta automaticamente pelo campo
    'bookmakers' ser lista em vez de dict)."""
    with open(caminho) as f:
        eventos = json.load(f)

    normalizados = []
    for evento in eventos:
        if isinstance(evento.get("bookmakers"), list):
            normalizados.append(_normalizar_evento(evento, evento.get("sport_key", "")))
        else:
            normalizados.append(evento)
    return normalizados


def _normalizar_evento(evento: dict, desporto: str) -> dict:
    bookmakers = {}
    for bookmaker in evento.get("bookmakers", []):
        mercados = bookmaker.get("markets", [])
        if not mercados:
            continue
        outcomes = mercados[0].get("outcomes", [])
        odds_por_resultado = {o["name"]: float(o["price"]) for o in outcomes if o.get("price")}
        if odds_por_resultado:
            bookmakers[bookmaker.get("title", bookmaker.get("key", "?"))] = odds_por_resultado

    return {
        "id": evento.get("id", ""),
        "desporto": desporto,
        "hora_inicio": evento.get("commence_time", ""),
        "equipas": [evento.get("home_team", ""), evento.get("away_team", "")],
        "bookmakers": bookmakers,
    }
