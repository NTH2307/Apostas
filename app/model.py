"""Compara as probabilidades do modelo de Poisson (app/poisson.py, a partir
de estatísticas reais de golos — app/stats.py) com as odds de mercado
(mercado h2h/vencedor), para encontrar jogos onde o modelo "discorda" do
mercado.

⚠️ Isto é uma segunda opinião estatística baseada em golos marcados/sofridos
da época, não uma previsão garantida — o modelo pode estar errado tanto
quanto o mercado, ou mais. Ver README.

Nota: over/under 2.5 golos e "ambas marcam" (BTTS) são calculados pelo
modelo (ver app/poisson.py) mas ainda não comparados com odds de mercado
para esses mercados — só o mercado h2h/vencedor está integrado.
"""
import re
import unicodedata
from dataclasses import dataclass

from app.arbitrage import melhores_odds_por_resultado
from app.poisson import golos_esperados, probabilidades

# Tokens comuns de nome de clube que aparecem tanto como prefixo ("FC
# Barcelona", "AFC Bournemouth", "1. FC Köln") como sufixo ("Arsenal FC",
# "Sporting CP" — "cp"/"sad"/"ud" são comuns em Portugal), consoante a
# fonte de dados — por isso removemos de ambos os lados, não só do fim.
TOKENS_RUIDO_CLUBE = frozenset({
    "1", "fc", "cf", "afc", "sc", "ac", "cd", "ud", "sad", "cp", "sv", "ssv",
    "vfb", "vfl", "tsg", "sg", "spvgg", "bv", "sk", "if", "bk", "fk",
})


@dataclass
class OportunidadeModelo:
    equipas: list
    resultado: str
    bookmaker: str
    odd: float
    probabilidade_modelo: float
    golos_esperados_casa: float
    golos_esperados_fora: float
    valor: float


def normalizar_nome_equipa(nome: str) -> str:
    """Normaliza um nome de equipa para comparar entre fontes de dados
    diferentes: remove acentos e pontuação, baixa maiúsculas, e retira
    tokens comuns de clube (FC, AFC, CF, ...) do INÍCIO ou do FIM do nome
    — a football-data.org costuma usar 'FC Barcelona'/'AFC Bournemouth',
    a The Odds API costuma usar só 'Barcelona'/'Bournemouth'.

    ⚠️ É uma normalização best-effort, não uma correspondência garantida —
    nomes muito diferentes entre as duas fontes (traduções, abreviaturas
    pouco comuns) continuam a poder falhar. Ver README, limitações."""
    sem_acentos = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    tokens = re.findall(r"[a-z0-9]+", sem_acentos.lower())
    while tokens and tokens[0] in TOKENS_RUIDO_CLUBE:
        tokens = tokens[1:]
    while tokens and tokens[-1] in TOKENS_RUIDO_CLUBE:
        tokens = tokens[:-1]
    return " ".join(tokens)


def encontrar_nome_equivalente(nome: str, nomes_disponiveis):
    """Encontra em `nomes_disponiveis` o nome equivalente a `nome`, depois
    de normalizar ambos. Devolve o nome ORIGINAL de `nomes_disponiveis`
    (a chave a usar em `forcas["equipas"]`), ou None se não encontrar."""
    alvo = normalizar_nome_equipa(nome)
    for candidato in nomes_disponiveis:
        if normalizar_nome_equipa(candidato) == alvo:
            return candidato
    return None


def avaliar_evento(evento: dict, forcas: dict, margem_minima: float = 0.0) -> list[OportunidadeModelo]:
    """Compara o modelo com as odds do evento. Devolve [] tanto quando não
    há discrepância como quando faltam dados de alguma equipa no modelo —
    usa `encontrar_nome_equivalente` diretamente se precisares de
    distinguir os dois casos (ver main.py, comando `modelo`)."""
    casa_nome, fora_nome = evento["equipas"]
    nomes_modelo = forcas.get("equipas", {})

    casa_equiv = encontrar_nome_equivalente(casa_nome, nomes_modelo)
    fora_equiv = encontrar_nome_equivalente(fora_nome, nomes_modelo)
    if not casa_equiv or not fora_equiv:
        return []

    eg = golos_esperados(forcas, casa_equiv, fora_equiv)
    if not eg:
        return []
    lambda_casa, lambda_fora = eg
    probs = probabilidades(lambda_casa, lambda_fora)

    prob_por_resultado = {casa_nome: probs["casa"], "Draw": probs["empate"], fora_nome: probs["fora"]}

    oportunidades = []
    for m in melhores_odds_por_resultado(evento):
        prob_modelo = prob_por_resultado.get(m.resultado)
        if prob_modelo is None:
            continue
        valor = m.odd * prob_modelo - 1
        if valor > margem_minima:
            oportunidades.append(OportunidadeModelo(
                equipas=evento["equipas"], resultado=m.resultado, bookmaker=m.bookmaker, odd=m.odd,
                probabilidade_modelo=prob_modelo, golos_esperados_casa=lambda_casa,
                golos_esperados_fora=lambda_fora, valor=valor,
            ))
    return sorted(oportunidades, key=lambda o: o.valor, reverse=True)
