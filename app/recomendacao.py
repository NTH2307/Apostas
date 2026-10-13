"""Transforma a análise de um jogo num conjunto de opiniões concretas, para
todos os jogos — sem olhar a odds nem a casas de apostas, é só a opinião
do modelo, em vários mercados (como numa casa de apostas, mas sem copiar
nenhuma):

1. **Resultado (1X2)**: o lado (casa/empate/fora) com maior probabilidade
   segundo o modelo de golos próprio — é sempre dinâmico, pode ser
   qualquer um dos três, não só a casa.
2. **Mais/menos de 2.5 golos**: o lado mais provável dos dois.
3. **Ambas marcam**: sim ou não, o mais provável dos dois.

Para os mercados de golos não temos odds reais para comparar, por isso
vêm com uma **odd mínima** só informativa — confirmas tu na tua casa, se
quiseres.

⚠️ Isto não é uma previsão garantida — é a opinião do modelo. Mesmo
palpites de confiança "alta" perdem muitas vezes; as casas de apostas têm
normalmente mais informação do que este modelo (lesões, onzes, motivação).
Cantos, cartões e outros mercados não entram aqui — não há dados fiáveis
e gratuitos para os calcular.
"""
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import quote

import config
from app.model import encontrar_nome_equivalente
from app.odds import hora_local
from app.poisson import golos_esperados, probabilidades

LADOS_1X2 = ("casa", "empate", "fora")
MERCADO_OVER_UNDER = (("over_2.5", "Mais de 2.5 golos"), ("under_2.5", "Menos de 2.5 golos"))
MERCADO_BTTS = (("btts_sim", "Ambas marcam — Sim"), ("btts_nao", "Ambas marcam — Não"))
MERCADOS_GOLOS = MERCADO_OVER_UNDER + MERCADO_BTTS
ORDEM_CONFIANCA = {"alta": 2, "média": 1, "baixa": 0}


@dataclass
class Sugestao:
    tipo: str  # "1x2" (sempre, é o palpite principal) ou "golos" (só como alternativa)
    texto: str
    confianca: str  # "alta", "média" ou "baixa"
    probabilidade: float | None = None
    odd_minima: float | None = None  # golos: só vale a pena apostar a partir desta odd


@dataclass
class AnaliseJogo:
    competicao: str
    inicio: datetime | None
    casa: str
    fora: str
    golos_esperados_casa: float
    golos_esperados_fora: float
    prob_modelo: dict
    prob_golos: dict
    jogos_min: int
    sugestao: Sugestao
    alternativas: list = field(default_factory=list)
    avisos: list = field(default_factory=list)
    link_lesoes_casa: str = ""  # pesquisa manual — sem API de lesões fiável no free tier, ver README
    link_lesoes_fora: str = ""


def link_pesquisa_lesoes(equipa: str) -> str:
    """Link de pesquisa Google para lesões da equipa — sem custo nem
    limites, ao contrário de uma API de lesões (o free tier da
    API-Football, por exemplo, só dá acesso a épocas de 2022-2024, não à
    época atual — inútil para lesões de agora). Confirma sempre perto da
    hora do jogo, as notícias mudam."""
    return f"https://www.google.com/search?q={quote(f'lesões {equipa} hoje')}"


def confianca_por_amostra(jogos_min: int) -> str:
    """Quanto mais jogos a equipa com menos dados tiver, mais fiável é o
    modelo para este jogo."""
    if jogos_min >= 10:
        return "alta"
    if jogos_min >= 5:
        return "média"
    return "baixa"


def _sugestao_1x2(casa: str, fora: str, prob_modelo: dict, confianca_base: str) -> Sugestao:
    """Palpite do modelo: o lado (casa/empate/fora) com maior probabilidade
    segundo o modelo de golos — opinião do modelo, sem olhar a odds."""
    rotulos = {"casa": f"Vitória do {casa}", "empate": "Empate", "fora": f"Vitória do {fora}"}
    lado = max(LADOS_1X2, key=lambda l: prob_modelo[l])
    return Sugestao(
        tipo="1x2",
        texto=rotulos[lado],
        confianca=confianca_base,
        probabilidade=prob_modelo[lado],
    )


def _sugestao_mercado_golos(prob_golos: dict, grupo: tuple, confianca_base: str) -> Sugestao:
    """Opinião do modelo num mercado de golos de duas vias (over/under,
    ou ambas marcam): o lado mais provável dos dois, sempre."""
    chave, rotulo = max(grupo, key=lambda m: prob_golos[m[0]])
    prob = prob_golos[chave]
    # exige 5% acima da odd justa, para compensar a margem de erro do modelo
    odd_minima = round(1 / prob * 1.05, 2)
    return Sugestao(
        tipo="golos",
        texto=f"{rotulo} — só se a odd for ≥ {odd_minima:.2f}",
        # sem odds reais para comparar, nunca passa de "média"
        confianca="média" if confianca_base == "alta" else confianca_base,
        probabilidade=prob,
        odd_minima=odd_minima,
    )


def _sugestoes_golos(prob_golos: dict, confianca_base: str) -> list:
    """Opinião do modelo sobre mais/menos de 2.5 golos E sobre ambas
    marcam — dois mercados independentes, sempre os dois, nunca só um."""
    return [
        _sugestao_mercado_golos(prob_golos, MERCADO_OVER_UNDER, confianca_base),
        _sugestao_mercado_golos(prob_golos, MERCADO_BTTS, confianca_base),
    ]


def analisar_jogo(evento: dict, forcas: dict, competicao: str) -> AnaliseJogo | None:
    """Analisa um jogo e escolhe a sugestão principal. Devolve None se
    alguma das equipas não existir nas estatísticas da competição."""
    casa, fora = evento["equipas"]
    equipas_modelo = forcas.get("equipas", {})
    casa_eq = encontrar_nome_equivalente(casa, equipas_modelo)
    fora_eq = encontrar_nome_equivalente(fora, equipas_modelo)
    if not casa_eq or not fora_eq:
        return None

    lambda_casa, lambda_fora = golos_esperados(forcas, casa_eq, fora_eq)
    prob_modelo = probabilidades(lambda_casa, lambda_fora)
    jogos_min = min(equipas_modelo[casa_eq].get("jogos", 0), equipas_modelo[fora_eq].get("jogos", 0))
    confianca_base = confianca_por_amostra(jogos_min)
    avisos = []

    prob_liga = probabilidades(forcas["media_golos_casa"], forcas["media_golos_fora"])
    wg = config.APOSTAS_PESO_MODELO_GOLOS
    prob_golos = {chave: wg * prob_modelo[chave] + (1 - wg) * prob_liga[chave] for chave, _ in MERCADOS_GOLOS}

    if confianca_base == "baixa":
        avisos.append(
            f"Poucos jogos na amostra ({jogos_min}) para pelo menos uma das equipas — o modelo é pouco fiável aqui."
        )

    principal = _sugestao_1x2(casa, fora, prob_modelo, confianca_base)
    alternativas = _sugestoes_golos(prob_golos, confianca_base)

    return AnaliseJogo(
        competicao=competicao,
        inicio=hora_local(evento),
        casa=casa,
        fora=fora,
        golos_esperados_casa=lambda_casa,
        golos_esperados_fora=lambda_fora,
        prob_modelo=prob_modelo,
        prob_golos=prob_golos,
        jogos_min=jogos_min,
        sugestao=principal,
        alternativas=alternativas,
        avisos=avisos,
        link_lesoes_casa=link_pesquisa_lesoes(casa),
        link_lesoes_fora=link_pesquisa_lesoes(fora),
    )


def chave_ordenacao(analise: AnaliseJogo) -> tuple:
    """Ordena jogos do palpite mais para o menos "forte": primeiro por
    confiança (amostra maior), depois pela probabilidade que o modelo dá
    ao lado escolhido."""
    s = analise.sugestao
    return (ORDEM_CONFIANCA.get(s.confianca, 0), s.probabilidade or 0)
