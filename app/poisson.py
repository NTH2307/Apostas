"""Modelo de Poisson para golos: a partir dos golos esperados de cada
equipa (ver `golos_esperados`, que usa as forças calculadas em
app/stats.py), estima probabilidades de 1X2, over/under golos (a
qualquer linha, não só 2.5), e ambas marcam (BTTS). É um modelo simples e
conhecido publicamente — não é segredo nem garantia de acerto, só
estatística sobre resultados passados.
"""
import math

MAX_GOLOS = 8  # a probabilidade de mais do que isto num jogo é desprezável


def _poisson(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * lam ** k / math.factorial(k)


def golos_esperados(forcas: dict, equipa_casa: str, equipa_fora: str):
    """Devolve (golos_esperados_casa, golos_esperados_fora), ou None se
    faltarem dados de alguma das equipas em `forcas` (ver app/stats.py)."""
    equipas = forcas.get("equipas", {})
    if equipa_casa not in equipas or equipa_fora not in equipas:
        return None

    dados_casa = equipas[equipa_casa]
    dados_fora = equipas[equipa_fora]
    lambda_casa = forcas["media_golos_casa"] * dados_casa["ataque_casa"] * dados_fora["defesa_fora"]
    lambda_fora = forcas["media_golos_fora"] * dados_fora["ataque_fora"] * dados_casa["defesa_casa"]
    return lambda_casa, lambda_fora


def _matriz_golos(lambda_casa: float, lambda_fora: float) -> list:
    return [
        [_poisson(gc, lambda_casa) * _poisson(gf, lambda_fora) for gf in range(MAX_GOLOS + 1)]
        for gc in range(MAX_GOLOS + 1)
    ]


def probabilidade_over(lambda_casa: float, lambda_fora: float, linha: float) -> float:
    """Probabilidade de o total de golos do jogo ser maior do que `linha`
    (ex: 1.5, 2.5, 3.5) — qualquer linha, não só 2.5."""
    matriz = _matriz_golos(lambda_casa, lambda_fora)
    return sum(
        matriz[gc][gf]
        for gc in range(MAX_GOLOS + 1) for gf in range(MAX_GOLOS + 1)
        if gc + gf > linha
    )


def probabilidades(lambda_casa: float, lambda_fora: float) -> dict:
    """Probabilidades de mercado a partir dos golos esperados de cada
    equipa: 1X2, over/under 2.5 golos, ambas marcam (BTTS)."""
    matriz = _matriz_golos(lambda_casa, lambda_fora)

    p_casa = sum(matriz[gc][gf] for gc in range(MAX_GOLOS + 1) for gf in range(MAX_GOLOS + 1) if gc > gf)
    p_empate = sum(matriz[gc][gf] for gc in range(MAX_GOLOS + 1) for gf in range(MAX_GOLOS + 1) if gc == gf)
    p_fora = sum(matriz[gc][gf] for gc in range(MAX_GOLOS + 1) for gf in range(MAX_GOLOS + 1) if gc < gf)

    p_over_25 = sum(matriz[gc][gf] for gc in range(MAX_GOLOS + 1) for gf in range(MAX_GOLOS + 1) if gc + gf > 2.5)
    p_under_25 = 1 - p_over_25

    p_btts_sim = sum(matriz[gc][gf] for gc in range(1, MAX_GOLOS + 1) for gf in range(1, MAX_GOLOS + 1))
    p_btts_nao = 1 - p_btts_sim

    return {
        "casa": p_casa, "empate": p_empate, "fora": p_fora,
        "over_2.5": p_over_25, "under_2.5": p_under_25,
        "btts_sim": p_btts_sim, "btts_nao": p_btts_nao,
    }
