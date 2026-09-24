"""Transforma a análise de um jogo numa sugestão concreta — "neste jogo,
aposta isto" — ou em "não apostes neste jogo" quando não há razão para isso.

Como decide, por ordem:
1. **Resultado (1X2)**: junta a probabilidade do modelo de golos com a do
   consenso do mercado (o mercado pesa mais — ver APOSTAS_PESO_MODELO) e
   compara com a melhor odd disponível. Só sugere se o valor esperado for
   positivo e plausível: valores enormes são tratados como sinal de dados
   insuficientes, não como oportunidade.
2. **Golos** (mais/menos de 2.5, ambas marcam): não temos odds destes
   mercados, por isso a sugestão vem com a **odd mínima** a partir da qual
   a aposta tem valor segundo o modelo — confirmas tu na tua casa.
3. Se nenhum dos dois passar os critérios: "sem aposta recomendada".

⚠️ Isto não é uma previsão garantida — é a melhor leitura estatística que
estes dados permitem. Mesmo sugestões de confiança "alta" perdem muitas
vezes; a vantagem, se existir, só aparece ao fim de muitas apostas.
"""
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import quote

import config
from app.arbitrage import melhores_odds_por_resultado, probabilidades_implicitas_justas
from app.model import encontrar_nome_equivalente
from app.odds import hora_local
from app.poisson import golos_esperados, probabilidades
from app.staking import calcular_stake

LADOS_1X2 = ("casa", "empate", "fora")
MERCADOS_GOLOS = (
    ("over_2.5", "Mais de 2.5 golos"),
    ("under_2.5", "Menos de 2.5 golos"),
    ("btts_sim", "Ambas marcam — Sim"),
    ("btts_nao", "Ambas marcam — Não"),
)
ORDEM_CONFIANCA = {"alta": 2, "média": 1, "baixa": 0}


@dataclass
class Sugestao:
    tipo: str  # "1x2", "golos" ou "nenhuma"
    texto: str
    confianca: str  # "alta", "média" ou "baixa"
    probabilidade: float | None = None
    odd: float | None = None
    bookmaker: str | None = None
    odd_minima: float | None = None  # golos: só vale a pena apostar a partir desta odd
    stake: float | None = None
    valor: float | None = None


@dataclass
class AnaliseJogo:
    competicao: str
    inicio: datetime | None
    casa: str
    fora: str
    golos_esperados_casa: float
    golos_esperados_fora: float
    prob_modelo: dict
    prob_mercado: dict
    prob_final: dict
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


def _prob_mercado_1x2(evento: dict, casa: str, fora: str) -> dict:
    justas = probabilidades_implicitas_justas(evento)
    nomes = {"casa": casa, "empate": "Draw", "fora": fora}
    if not all(nomes[lado] in justas for lado in LADOS_1X2):
        return {}
    return {lado: justas[nomes[lado]] for lado in LADOS_1X2}


def _sugestao_1x2(evento, casa, fora, prob_final, confianca_base, capital, avisos) -> Sugestao | None:
    nomes = {"casa": casa, "empate": "Draw", "fora": fora}
    rotulos = {"casa": f"Vitória do {casa}", "empate": "Empate", "fora": f"Vitória do {fora}"}
    melhores = {m.resultado: m for m in melhores_odds_por_resultado(evento)}

    candidatos = []
    for lado in LADOS_1X2:
        melhor = melhores.get(nomes[lado])
        if not melhor:
            continue
        if config.ODD_MAXIMA_VALOR > 0 and melhor.odd > config.ODD_MAXIMA_VALOR:
            continue
        candidatos.append((melhor.odd * prob_final[lado] - 1, lado, melhor))
    if not candidatos:
        return None

    valor, lado, melhor = max(candidatos, key=lambda c: c[0])
    if valor < config.APOSTAS_MARGEM_MINIMA:
        return None

    confianca = confianca_base
    if valor > config.APOSTAS_VALOR_SUSPEITO:
        confianca = "baixa"
        avisos.append(
            f"O valor calculado para '{rotulos[lado]}' ({valor * 100:.0f}%) é grande demais para ser credível — "
            "costuma querer dizer que o modelo não sabe algo que o mercado sabe (lesões, rotação, etc.)."
        )

    return Sugestao(
        tipo="1x2",
        texto=f"{rotulos[lado]} @ {melhor.odd} ({melhor.bookmaker})",
        confianca=confianca,
        probabilidade=prob_final[lado],
        odd=melhor.odd,
        bookmaker=melhor.bookmaker,
        stake=calcular_stake(capital, melhor.odd, prob_final[lado]),
        valor=valor,
    )


def _sugestao_golos(prob_golos: dict, confianca_base: str) -> Sugestao | None:
    chave, rotulo = max(MERCADOS_GOLOS, key=lambda m: prob_golos[m[0]])
    prob = prob_golos[chave]
    if prob < config.APOSTAS_PROB_MIN_GOLOS:
        return None
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


def analisar_jogo(evento: dict, forcas: dict, competicao: str, capital: float | None = None) -> AnaliseJogo | None:
    """Analisa um jogo e escolhe a sugestão principal. Devolve None se
    alguma das equipas não existir nas estatísticas da competição."""
    capital = config.CAPITAL_INICIAL if capital is None else capital
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

    prob_mercado = _prob_mercado_1x2(evento, casa, fora)
    w = config.APOSTAS_PESO_MODELO
    prob_final = {
        lado: (w * prob_modelo[lado] + (1 - w) * prob_mercado[lado]) if prob_mercado else prob_modelo[lado]
        for lado in LADOS_1X2
    }
    if not prob_mercado:
        avisos.append("Sem odds de 1X2 suficientes para comparar com o mercado — só a opinião do modelo.")

    prob_liga = probabilidades(forcas["media_golos_casa"], forcas["media_golos_fora"])
    wg = config.APOSTAS_PESO_MODELO_GOLOS
    prob_golos = {chave: wg * prob_modelo[chave] + (1 - wg) * prob_liga[chave] for chave, _ in MERCADOS_GOLOS}

    if confianca_base == "baixa":
        avisos.append(
            f"Poucos jogos na amostra ({jogos_min}) para pelo menos uma das equipas — o modelo é pouco fiável aqui."
        )

    sugestao_1x2 = _sugestao_1x2(evento, casa, fora, prob_final, confianca_base, capital, avisos) if prob_mercado else None
    sugestao_golos = _sugestao_golos(prob_golos, confianca_base)

    alternativas = []
    if sugestao_1x2 and sugestao_1x2.confianca != "baixa":
        principal = sugestao_1x2
        if sugestao_golos:
            alternativas.append(sugestao_golos)
    elif sugestao_golos and sugestao_golos.confianca != "baixa":
        principal = sugestao_golos
        if sugestao_1x2:
            alternativas.append(sugestao_1x2)
    else:
        principal = Sugestao(
            tipo="nenhuma",
            texto="Sem aposta recomendada neste jogo",
            confianca=confianca_base,
        )
        alternativas.extend(s for s in (sugestao_1x2, sugestao_golos) if s)

    return AnaliseJogo(
        competicao=competicao,
        inicio=hora_local(evento),
        casa=casa,
        fora=fora,
        golos_esperados_casa=lambda_casa,
        golos_esperados_fora=lambda_fora,
        prob_modelo=prob_modelo,
        prob_mercado=prob_mercado,
        prob_final=prob_final,
        prob_golos=prob_golos,
        jogos_min=jogos_min,
        sugestao=principal,
        alternativas=alternativas,
        avisos=avisos,
        link_lesoes_casa=link_pesquisa_lesoes(casa),
        link_lesoes_fora=link_pesquisa_lesoes(fora),
    )


def chave_ordenacao(analise: AnaliseJogo) -> tuple:
    """Ordena sugestões da mais para a menos recomendável: primeiro as que
    têm aposta, depois por confiança, depois 1X2 (comparado com odds reais)
    antes de golos, e por fim pelo valor/probabilidade."""
    s = analise.sugestao
    return (
        s.tipo != "nenhuma",
        ORDEM_CONFIANCA.get(s.confianca, 0),
        s.tipo == "1x2",
        s.valor if s.valor is not None else (s.probabilidade or 0),
    )
