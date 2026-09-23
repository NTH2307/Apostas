"""Deteção de arbitragem (surebets) e apostas de valor entre bookmakers,
para um único evento já normalizado (ver app/odds.py).
"""
from dataclasses import dataclass


@dataclass
class MelhorOdd:
    resultado: str
    bookmaker: str
    odd: float


@dataclass
class OportunidadeArbitragem:
    evento_id: str
    equipas: list
    melhores_odds: list  # list[MelhorOdd]
    margem: float  # lucro garantido, ex: 0.02 = 2%

    def stakes(self, capital_total: float) -> dict:
        """Devolve {resultado: stake} que garante (em teoria) o mesmo lucro
        independentemente do resultado do evento."""
        soma_inversos = sum(1 / m.odd for m in self.melhores_odds)
        return {
            m.resultado: round(capital_total / m.odd / soma_inversos, 2)
            for m in self.melhores_odds
        }


@dataclass
class OportunidadeValor:
    evento_id: str
    equipas: list
    resultado: str
    bookmaker: str
    odd: float
    probabilidade_justa: float  # probabilidade implícita "de-vigged" do consenso
    valor: float  # (odd * probabilidade_justa) - 1 -> edge estimado


def filtrar_bookmakers(evento: dict, permitidos: list) -> dict:
    """Devolve uma cópia do evento só com os bookmakers cujo nome (sem
    distinguir maiúsculas/minúsculas) está em `permitidos`. Lista vazia ou
    None = sem filtro (mantém todos os bookmakers).

    Útil para excluir casas pouco fiáveis ou não licenciadas na tua
    jurisdição do cálculo — tanto do consenso de "probabilidade justa" como
    das odds consideradas para arbitragem/valor.
    """
    if not permitidos:
        return evento
    permitidos_norm = {p.strip().lower() for p in permitidos}
    bookmakers_filtrados = {
        nome: odds for nome, odds in evento["bookmakers"].items()
        if nome.strip().lower() in permitidos_norm
    }
    return {**evento, "bookmakers": bookmakers_filtrados}


def melhores_odds_por_resultado(evento: dict) -> list[MelhorOdd]:
    """Para cada resultado possível, encontra a melhor odd disponível entre
    todos os bookmakers do evento."""
    melhor: dict[str, MelhorOdd] = {}
    for bookmaker, odds in evento["bookmakers"].items():
        for resultado, odd in odds.items():
            atual = melhor.get(resultado)
            if atual is None or odd > atual.odd:
                melhor[resultado] = MelhorOdd(resultado=resultado, bookmaker=bookmaker, odd=odd)
    return list(melhor.values())


def detetar_arbitragem(evento: dict, margem_minima: float = 0.0) -> OportunidadeArbitragem | None:
    """Uma arbitragem (surebet) existe quando a soma das probabilidades
    implícitas (1/odd) das MELHORES odds de cada resultado é < 1 —
    apostando proporcionalmente em cada resultado em bookmakers diferentes,
    ganha-se sempre, seja qual for o resultado real do evento.

    ⚠️ Isto é arbitragem teórica: ignora limites de stake por bookmaker, o
    atraso entre colocar cada aposta (as odds movem-se entretanto), e o
    risco real de a bookmaker limitar ou fechar contas que apostam em
    arbitragem de forma sistemática. Ver README.
    """
    melhores = melhores_odds_por_resultado(evento)
    # precisa de resultados cobertos por pelo menos 2 bookmakers diferentes,
    # senão não é arbitragem real (é só uma casa com odd mais alta em tudo)
    if len(melhores) < 2 or len({m.bookmaker for m in melhores}) < 2:
        return None

    soma_inversos = sum(1 / m.odd for m in melhores)
    if soma_inversos == 0:
        return None
    margem = 1 / soma_inversos - 1
    if margem <= margem_minima:
        return None

    return OportunidadeArbitragem(
        evento_id=evento["id"],
        equipas=evento["equipas"],
        melhores_odds=melhores,
        margem=margem,
    )


def detetar_valor(evento: dict, margem_minima: float = 0.0, odd_maxima: float | None = None) -> list[OportunidadeValor]:
    """Estima a probabilidade "justa" de cada resultado removendo o overround
    médio do mercado (consenso entre bookmakers), e assinala quando a odd de
    um bookmaker específico paga acima dessa probabilidade justa.

    ⚠️ Isto é uma heurística (proxy do que profissionais chamam "closing
    line value"), não um modelo preditivo real do resultado do evento — o
    consenso do mercado já embute a opinião coletiva de milhares de
    apostadores, por isso "valor" aqui só significa que uma casa está, neste
    momento, a pagar mais do que as outras acham justo — não que a aposta
    vai ganhar.

    ⚠️ Em odds muito altas (azarões), um pequeno erro absoluto na odd de uma
    única bookmaker vira um "valor" percentual enorme, e entra em jogo o
    "favorite-longshot bias" (as casas tendem a pagar ligeiramente a mais em
    azarões de propósito, sem que isso signifique lucro real a longo prazo).
    Usa `odd_maxima` para ignorar odds acima desse valor — ver
    `config.ODD_MAXIMA_VALOR`.
    """
    probabilidades_justas = probabilidades_implicitas_justas(evento)
    if not probabilidades_justas:
        return []

    oportunidades = []
    for bookmaker, odds in evento["bookmakers"].items():
        for resultado, odd in odds.items():
            if odd_maxima is not None and odd > odd_maxima:
                continue
            prob_justa = probabilidades_justas.get(resultado)
            if not prob_justa:
                continue
            valor = odd * prob_justa - 1
            if valor > margem_minima:
                oportunidades.append(OportunidadeValor(
                    evento_id=evento["id"],
                    equipas=evento["equipas"],
                    resultado=resultado,
                    bookmaker=bookmaker,
                    odd=odd,
                    probabilidade_justa=prob_justa,
                    valor=valor,
                ))
    return sorted(oportunidades, key=lambda o: o.valor, reverse=True)


def probabilidades_implicitas_justas(evento: dict) -> dict:
    """Probabilidade implícita média de cada resultado entre bookmakers,
    normalizada para somar 1 (remove o overround/margem de cada casa)."""
    somas: dict = {}
    contagens: dict = {}
    for odds in evento["bookmakers"].values():
        for resultado, odd in odds.items():
            somas[resultado] = somas.get(resultado, 0) + 1 / odd
            contagens[resultado] = contagens.get(resultado, 0) + 1

    medias = {r: somas[r] / contagens[r] for r in somas}
    total = sum(medias.values())
    if total == 0:
        return {}
    return {r: p / total for r, p in medias.items()}
