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
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

import config

FUSO_PADRAO = "Europe/Lisbon"


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


def bookmakers_em_eventos(eventos: list[dict]) -> dict:
    """Conta em quantos eventos aparece cada bookmaker — usa isto (via o
    comando `bookmakers`) para confirmares o nome exato de uma casa (ex:
    "Betclic" pode aparecer como "Betclic (FR)") antes de a pores em
    BOOKMAKERS_FIAVEIS, em vez de adivinhar."""
    contagens: dict = {}
    for evento in eventos:
        for nome in evento.get("bookmakers", {}):
            contagens[nome] = contagens.get(nome, 0) + 1
    return dict(sorted(contagens.items(), key=lambda item: item[1], reverse=True))


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


def listar_desportos(filtro: str | None = None) -> list[dict]:
    """Lista as chaves de desporto/competição suportadas pela The Odds API
    (o valor a usar em `--desporto`) — ex: para encontrares a chave exata da
    Liga das Nações ou da Liga Portugal. `filtro` procura (sem distinguir
    maiúsculas/minúsculas) na chave, título ou descrição.
    """
    if not config.ODDS_API_KEY:
        raise RuntimeError(
            "ODDS_API_KEY não configurada — cria uma chave grátis em "
            "https://the-odds-api.com e define ODDS_API_KEY no .env."
        )
    resposta = requests.get(
        f"{config.ODDS_API_BASE_URL}/sports",
        params={"apiKey": config.ODDS_API_KEY},
        timeout=15,
    )
    resposta.raise_for_status()
    return _filtrar_desportos(resposta.json(), filtro)


def _filtrar_desportos(desportos: list[dict], filtro: str | None) -> list[dict]:
    if not filtro:
        return desportos
    filtro_lower = filtro.lower()
    return [
        d for d in desportos
        if filtro_lower in d.get("key", "").lower()
        or filtro_lower in d.get("title", "").lower()
        or filtro_lower in d.get("description", "").lower()
    ]


def hoje(fuso: str = FUSO_PADRAO) -> date:
    return datetime.now(ZoneInfo(fuso)).date()


def amanha(fuso: str = FUSO_PADRAO) -> date:
    return hoje(fuso) + timedelta(days=1)


def filtrar_por_dia(eventos: list[dict], dia: date, fuso: str = FUSO_PADRAO) -> list[dict]:
    """Mantém só os eventos cuja hora de início, convertida para `fuso`
    (omissão: hora de Portugal), cai no dia indicado. Eventos sem
    `hora_inicio` são descartados."""
    zona = ZoneInfo(fuso)
    filtrados = []
    for evento in eventos:
        hora = evento.get("hora_inicio")
        if not hora:
            continue
        inicio = datetime.fromisoformat(hora.replace("Z", "+00:00")).astimezone(zona)
        if inicio.date() == dia:
            filtrados.append(evento)
    return filtrados


def hora_local(evento: dict, fuso: str = FUSO_PADRAO) -> datetime | None:
    """Hora de início do evento no fuso indicado (omissão: hora de
    Portugal), ou None se o evento não tiver `hora_inicio`."""
    hora = evento.get("hora_inicio")
    if not hora:
        return None
    return datetime.fromisoformat(hora.replace("Z", "+00:00")).astimezone(ZoneInfo(fuso))


def filtrar_por_intervalo(
    eventos: list[dict], inicio: date, fim: date, fuso: str = FUSO_PADRAO, agora: datetime | None = None,
) -> list[dict]:
    """Eventos cuja data (hora de Portugal) está entre `inicio` e `fim`,
    inclusive, e que ainda não começaram (odds de jogos já a decorrer são
    ao vivo e não fazem sentido para sugestões pré-jogo)."""
    agora = agora or datetime.now(ZoneInfo(fuso))
    filtrados = []
    for evento in eventos:
        inicio_evento = hora_local(evento, fuso)
        if inicio_evento and inicio <= inicio_evento.date() <= fim and inicio_evento > agora:
            filtrados.append(evento)
    return filtrados


def jogos_comecados_no_periodo(
    eventos: list[dict], inicio: date, fim: date, fuso: str = FUSO_PADRAO, agora: datetime | None = None,
) -> list[dict]:
    """Eventos cuja data (hora de Portugal) cai no intervalo pedido mas que
    já começaram (o inverso de `filtrar_por_intervalo`). Usa isto para
    distinguir "não havia jogos agendados" de "havia jogos, mas já tinham
    começado quando o relatório foi gerado — sem valor pré-jogo"."""
    agora = agora or datetime.now(ZoneInfo(fuso))
    comecados = []
    for evento in eventos:
        inicio_evento = hora_local(evento, fuso)
        if inicio_evento and inicio <= inicio_evento.date() <= fim and inicio_evento <= agora:
            comecados.append(evento)
    return comecados


def proxima_data_com_jogos(eventos: list[dict], fuso: str = FUSO_PADRAO) -> date | None:
    """A data (no fuso indicado, omissão hora de Portugal) do jogo mais
    próximo entre `eventos` — útil para saber "quando é a próxima jornada"
    quando um dia pedido (ex: amanhã) não tem jogos. None se a lista
    estiver vazia ou nenhum evento tiver `hora_inicio`."""
    zona = ZoneInfo(fuso)
    datas = []
    for evento in eventos:
        hora = evento.get("hora_inicio")
        if not hora:
            continue
        datas.append(datetime.fromisoformat(hora.replace("Z", "+00:00")).astimezone(zona).date())
    return min(datas) if datas else None


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
