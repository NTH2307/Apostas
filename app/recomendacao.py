"""Transforma a análise de um jogo numa opinião concreta — sem olhar a
odds nem a casas de apostas, é só a opinião do modelo.

Para cada jogo, o modelo olha para **vários mercados possíveis**
(resultado 1X2, mais/menos de 1.5/2.5/3.5 golos, ambas marcam). Em vez de
escolher o mercado com a probabilidade mais alta — isso daria quase
sempre "mais de 1.5 golos", porque é um mercado estruturalmente fácil em
qualquer jogo de futebol, não porque o modelo saiba algo especial sobre
este jogo em concreto — escolhe o mercado em que **este jogo mais se
desvia do normal para a liga**. Um jogo entre duas equipas muito
defensivas pode ter um "menos de 2.5 golos" muito mais decisivo do que o
normal; um jogo entre uma equipa muito mais forte do que a outra pode ter
o 1X2 muito mais decisivo do que o normal — e é isso que aparece como
opinião principal. Quando mais do que um mercado se destaca claramente do
normal para o mesmo jogo, mostra mais do que uma opinião
(`APOSTAS_DESVIO_EXTRA`) — nunca um número fixo.

Para os mercados de golos não temos odds reais para comparar, por isso
vêm com uma **odd mínima** só informativa — confirmas tu na tua casa, se
quiseres.

⚠️ Isto não é uma previsão garantida — é a opinião do modelo. Mesmo
palpites de confiança "alta" perdem muitas vezes; as casas de apostas têm
normalmente mais informação do que este modelo (lesões, onzes, motivação).
Cantos, cartões e marcador individual não entram aqui — não há dados
fiáveis e gratuitos para os calcular (ver README).
"""
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import quote

import config
from app.model import encontrar_nome_equivalente
from app.odds import hora_local
from app.poisson import golos_esperados, probabilidade_over, probabilidades

LADOS_1X2 = ("casa", "empate", "fora")
LIMIARES_GOLOS = (1.5, 2.5, 3.5)
ORDEM_CONFIANCA = {"alta": 2, "média": 1, "baixa": 0}
# Com menos jogos do que isto na amostra, as forças de ataque/defesa são
# quase só o prior (equipa média) — o modelo não tem dados reais para
# distinguir as equipas, por isso qualquer jogo nestas condições dá
# praticamente o mesmo resultado. Em vez de fingir um palpite específico,
# diz isso claramente e não mostra alternativas (seriam só ruído).
AMOSTRA_MINIMA_FIAVEL = 3


@dataclass
class Sugestao:
    tipo: str  # "1x2" ou "golos" — qualquer um pode ser o palpite principal
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


def _odd_minima(prob: float) -> float:
    # exige 5% acima da odd justa, para compensar a margem de erro do modelo
    return round(1 / prob * 1.05, 2)


def _candidato_1x2(casa: str, fora: str, prob_modelo: dict, prob_liga: dict) -> tuple:
    """(Sugestao, desvio) — desvio = o quanto este jogo se afasta do que é
    normal para a liga nesse lado, usado para comparar com outros
    mercados e decidir qual mostrar como opinião."""
    rotulos = {"casa": f"Vitória do {casa}", "empate": "Empate", "fora": f"Vitória do {fora}"}
    lado = max(LADOS_1X2, key=lambda l: prob_modelo[l])
    sugestao = Sugestao(tipo="1x2", texto=rotulos[lado], confianca="", probabilidade=prob_modelo[lado])
    return sugestao, abs(prob_modelo[lado] - prob_liga[lado])


def _candidato_over_under(limiar: float, prob_blend: float, desvio: float) -> tuple:
    if prob_blend >= 0.5:
        rotulo, prob = f"Mais de {limiar} golos", prob_blend
    else:
        rotulo, prob = f"Menos de {limiar} golos", 1 - prob_blend
    sugestao = Sugestao(
        tipo="golos", texto=f"{rotulo} — só se a odd for ≥ {_odd_minima(prob):.2f}",
        confianca="", probabilidade=prob, odd_minima=_odd_minima(prob),
    )
    return sugestao, desvio


def _candidato_btts(prob_blend_sim: float, desvio: float) -> tuple:
    if prob_blend_sim >= 0.5:
        rotulo, prob = "Ambas marcam — Sim", prob_blend_sim
    else:
        rotulo, prob = "Ambas marcam — Não", 1 - prob_blend_sim
    sugestao = Sugestao(
        tipo="golos", texto=f"{rotulo} — só se a odd for ≥ {_odd_minima(prob):.2f}",
        confianca="", probabilidade=prob, odd_minima=_odd_minima(prob),
    )
    return sugestao, desvio


def _com_confianca(sugestao: Sugestao, confianca_base: str) -> Sugestao:
    # mercados de golos: sem odds reais para comparar, nunca passam de "média"
    sugestao.confianca = confianca_base if sugestao.tipo == "1x2" else (
        "média" if confianca_base == "alta" else confianca_base
    )
    return sugestao


def analisar_jogo(evento: dict, forcas: dict, competicao: str) -> AnaliseJogo | None:
    """Analisa um jogo em vários mercados (1X2, golos a várias linhas,
    ambas marcam) e escolhe como opinião principal aquele em que este
    jogo mais se desvia do normal para a liga — não é sempre o mesmo tipo
    de mercado. Mostra como alternativas os outros mercados em que o
    desvio também é claro. Devolve None se alguma das equipas não existir
    nas estatísticas da competição."""
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

    media_casa, media_fora = forcas["media_golos_casa"], forcas["media_golos_fora"]
    prob_liga = probabilidades(media_casa, media_fora)
    wg = config.APOSTAS_PESO_MODELO_GOLOS

    prob_golos = {"btts_sim": wg * prob_modelo["btts_sim"] + (1 - wg) * prob_liga["btts_sim"]}
    prob_golos["btts_nao"] = 1 - prob_golos["btts_sim"]
    desvio_over = {}
    for limiar in LIMIARES_GOLOS:
        p_modelo_over = probabilidade_over(lambda_casa, lambda_fora, limiar)
        p_liga_over = probabilidade_over(media_casa, media_fora, limiar)
        prob_golos[f"over_{limiar}"] = wg * p_modelo_over + (1 - wg) * p_liga_over
        desvio_over[limiar] = abs(p_modelo_over - p_liga_over)

    dados_insuficientes = jogos_min < AMOSTRA_MINIMA_FIAVEL
    if dados_insuficientes:
        avisos.append(
            f"Só {jogos_min} jogo(s) de amostra esta temporada para pelo menos uma das equipas — não há dados "
            "reais suficientes para as distinguir; os números abaixo são quase só a média da liga, não uma "
            "leitura destas equipas em concreto."
        )
    elif confianca_base == "baixa":
        avisos.append(
            f"Poucos jogos na amostra ({jogos_min}) para pelo menos uma das equipas — o modelo é pouco fiável aqui."
        )

    candidatos = [_candidato_1x2(casa, fora, prob_modelo, prob_liga)]
    for limiar in LIMIARES_GOLOS:
        candidatos.append(_candidato_over_under(limiar, prob_golos[f"over_{limiar}"], desvio_over[limiar]))
    candidatos.append(_candidato_btts(prob_golos["btts_sim"], abs(prob_modelo["btts_sim"] - prob_liga["btts_sim"])))
    candidatos.sort(key=lambda c: c[1], reverse=True)

    principal = _com_confianca(candidatos[0][0], confianca_base)
    if dados_insuficientes:
        principal.texto += " — dados insuficientes esta temporada"
        alternativas = []
    else:
        alternativas = [
            _com_confianca(sugestao, confianca_base)
            for sugestao, desvio in candidatos[1:]
            if desvio >= config.APOSTAS_DESVIO_EXTRA
        ]

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
