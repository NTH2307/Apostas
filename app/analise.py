"""Junta estatísticas (football-data.org) e odds (The Odds API) de uma
competição e analisa cada jogo dentro de um intervalo de datas — ver
app/recomendacao.py para a lógica de cada sugestão."""
from dataclasses import dataclass, field
from datetime import date

import config
from app.arbitrage import filtrar_bookmakers
from app.lesoes import lesoes_recentes, procurar_equipa_id
from app.odds import buscar_odds, filtrar_por_intervalo, proxima_data_com_jogos
from app.recomendacao import AnaliseJogo, analisar_jogo
from app.stats import buscar_jogos_terminados, calcular_forcas

NOMES_COMPETICOES = {
    "PL": "Premier League",
    "PD": "La Liga",
    "SA": "Serie A",
    "BL1": "Bundesliga",
    "FL1": "Ligue 1",
    "PPL": "Liga Portugal",
    "CL": "Liga dos Campeões",
    "ELC": "Championship",
    "DED": "Eredivisie",
    "BSA": "Brasileirão",
    "CLI": "Taça Libertadores",
    "EC": "Europeu",
    "WC": "Mundial",
}


@dataclass
class ResultadoCompeticao:
    codigo: str
    nome: str
    analises: list = field(default_factory=list)  # list[AnaliseJogo]
    sem_dados: list = field(default_factory=list)  # "Casa vs Fora" sem equipa reconhecida
    nota: str | None = None


def _lesoes_para_equipa(nome_equipa: str, cache: dict) -> list:
    """Lesões recentes de uma equipa, com cache por nome (evita repetir o
    pedido à API-Football para a mesma equipa em competições diferentes
    dentro da mesma execução — a cota do free tier é curta, 100/dia)."""
    if nome_equipa in cache:
        return cache[nome_equipa]
    try:
        team_id = procurar_equipa_id(nome_equipa)
        lesoes = lesoes_recentes(team_id) if team_id else []
    except Exception as e:
        print(f"  [lesões] erro a obter para '{nome_equipa}': {e}")
        lesoes = []
    cache[nome_equipa] = lesoes
    return lesoes


def analisar_competicao(
    competicao: str,
    desporto: str,
    inicio: date,
    fim: date,
    bookmakers: list | None = None,
    jogos_historico: int | None = None,
    capital: float | None = None,
    com_lesoes: bool = False,
    cache_lesoes: dict | None = None,
) -> ResultadoCompeticao:
    nome = NOMES_COMPETICOES.get(competicao, competicao)
    resultado = ResultadoCompeticao(codigo=competicao, nome=nome)

    jogos = buscar_jogos_terminados(competicao, limite=jogos_historico or config.MODELO_JOGOS_HISTORICO)
    forcas = calcular_forcas(jogos)
    if not forcas["equipas"]:
        resultado.nota = "sem jogos terminados suficientes para calcular o modelo"
        return resultado

    eventos_todos = buscar_odds(desporto)
    eventos = filtrar_por_intervalo(eventos_todos, inicio, fim)
    if not eventos:
        proxima = proxima_data_com_jogos(eventos_todos)
        if proxima and proxima > fim:
            resultado.nota = f"sem jogos neste período — próxima data com jogos: {proxima.strftime('%d/%m/%Y')}"
        else:
            resultado.nota = "sem jogos agendados neste período"
        return resultado

    bookmakers = config.BOOKMAKERS_FIAVEIS if bookmakers is None else bookmakers
    cache_lesoes = {} if cache_lesoes is None else cache_lesoes
    for evento in eventos:
        analise: AnaliseJogo | None = analisar_jogo(filtrar_bookmakers(evento, bookmakers), forcas, nome, capital)
        if analise is None:
            resultado.sem_dados.append(" vs ".join(evento["equipas"]))
            continue
        if com_lesoes:
            analise.lesoes_casa = _lesoes_para_equipa(analise.casa, cache_lesoes)
            analise.lesoes_fora = _lesoes_para_equipa(analise.fora, cache_lesoes)
        resultado.analises.append(analise)
    return resultado
