"""Junta estatísticas (football-data.org) e odds (The Odds API) de uma
competição e analisa cada jogo dentro de um intervalo de datas — ver
app/recomendacao.py para a lógica de cada sugestão."""
from dataclasses import dataclass, field
from datetime import date

import config
from app.arbitrage import filtrar_bookmakers
from app.odds import buscar_odds, filtrar_por_intervalo, jogos_comecados_no_periodo, proxima_data_com_jogos
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


def analisar_competicao(
    competicao: str,
    desporto: str,
    inicio: date,
    fim: date,
    bookmakers: list | None = None,
    jogos_historico: int | None = None,
    capital: float | None = None,
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
        comecados = jogos_comecados_no_periodo(eventos_todos, inicio, fim)
        if comecados:
            resultado.nota = (
                f"havia {len(comecados)} jogo(s) neste período, mas já tinham começado quando o "
                "relatório foi gerado — o bot só dá palpites pré-jogo; corre o `apostas` mais cedo "
                "para os veres"
            )
        else:
            proxima = proxima_data_com_jogos(eventos_todos)
            if proxima and proxima > fim:
                resultado.nota = f"sem jogos neste período — próxima data com jogos: {proxima.strftime('%d/%m/%Y')}"
            else:
                resultado.nota = "sem jogos agendados neste período"
        return resultado

    bookmakers = config.BOOKMAKERS_FIAVEIS if bookmakers is None else bookmakers
    for evento in eventos:
        analise: AnaliseJogo | None = analisar_jogo(filtrar_bookmakers(evento, bookmakers), forcas, nome, capital)
        if analise is None:
            resultado.sem_dados.append(" vs ".join(evento["equipas"]))
        else:
            resultado.analises.append(analise)
    return resultado
