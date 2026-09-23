"""Dimensionamento de apostas: Kelly fracionado (para apostas de valor). A
distribuição de stake para arbitragem tem fórmula própria — ver
`OportunidadeArbitragem.stakes` em app/arbitrage.py.
"""
import config


def kelly_fracionado(odd: float, probabilidade: float, fracao: float | None = None) -> float:
    """Fração do capital a apostar segundo o critério de Kelly, reduzida por
    `fracao` (Kelly fracionado — reduz a variância e a sensibilidade a erros
    na estimativa da probabilidade, ao custo de crescimento esperado mais
    lento do que o Kelly completo).

    Devolve 0 se a aposta não tiver valor esperado positivo
    (odd * probabilidade <= 1).
    """
    fracao = config.FRACAO_KELLY if fracao is None else fracao
    b = odd - 1
    if b <= 0:
        return 0.0
    kelly_completo = (b * probabilidade - (1 - probabilidade)) / b
    return max(0.0, kelly_completo) * fracao


def calcular_stake(capital: float, odd: float, probabilidade: float, fracao: float | None = None) -> float:
    fracao_capital = kelly_fracionado(odd, probabilidade, fracao)
    stake = capital * fracao_capital
    return round(min(stake, config.STAKE_MAXIMA_POR_APOSTA), 2)
