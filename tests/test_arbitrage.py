from app.arbitrage import (
    detetar_arbitragem,
    detetar_valor,
    melhores_odds_por_resultado,
    probabilidades_implicitas_justas,
)


def _evento(bookmakers: dict, equipas=("A", "B")) -> dict:
    return {"id": "ev1", "desporto": "teste", "hora_inicio": "", "equipas": list(equipas), "bookmakers": bookmakers}


def test_melhores_odds_escolhe_a_odd_mais_alta_por_resultado():
    evento = _evento({
        "Casa X": {"A": 1.90, "B": 2.00},
        "Casa Y": {"A": 2.10, "B": 1.85},
    })
    melhores = {m.resultado: m for m in melhores_odds_por_resultado(evento)}
    assert melhores["A"].odd == 2.10
    assert melhores["A"].bookmaker == "Casa Y"
    assert melhores["B"].odd == 2.00
    assert melhores["B"].bookmaker == "Casa X"


def test_deteta_arbitragem_quando_soma_de_inversos_e_menor_que_um():
    # melhores odds: A=2.10 (Y), B=2.05 (X) -> 1/2.10 + 1/2.05 = 0.9631 < 1
    evento = _evento({
        "Casa X": {"A": 1.90, "B": 2.05},
        "Casa Y": {"A": 2.10, "B": 1.85},
    })
    arb = detetar_arbitragem(evento)
    assert arb is not None
    assert arb.margem > 0
    assert {m.bookmaker for m in arb.melhores_odds} == {"Casa X", "Casa Y"}


def test_nao_deteta_arbitragem_em_mercado_com_overround_tipico():
    # mesmas odds nas duas casas -> soma de inversos sempre > 1 (overround)
    evento = _evento({
        "Casa X": {"A": 1.90, "B": 1.90},
        "Casa Y": {"A": 1.90, "B": 1.90},
    })
    assert detetar_arbitragem(evento) is None


def test_nao_deteta_arbitragem_com_uma_so_bookmaker():
    # mesmo que a soma desse um número < 1 por erro de dados, uma única casa
    # não permite arbitragem real (precisa de apostar em casas diferentes)
    evento = _evento({"Casa X": {"A": 2.10, "B": 2.05}})
    assert detetar_arbitragem(evento) is None


def test_margem_minima_filtra_arbitragens_pequenas():
    evento = _evento({
        "Casa X": {"A": 1.90, "B": 2.05},
        "Casa Y": {"A": 2.10, "B": 1.85},
    })
    arb = detetar_arbitragem(evento)
    assert detetar_arbitragem(evento, margem_minima=arb.margem + 0.01) is None


def test_stakes_de_arbitragem_dao_o_mesmo_retorno_em_qualquer_resultado():
    evento = _evento({
        "Casa X": {"A": 1.90, "B": 2.05},
        "Casa Y": {"A": 2.10, "B": 1.85},
    })
    arb = detetar_arbitragem(evento)
    stakes = arb.stakes(100)

    retorno_se_a_ganha = stakes["A"] * 2.10
    retorno_se_b_ganha = stakes["B"] * 2.05
    # o retorno é igual em qualquer resultado a menos do arredondamento a
    # cêntimos de cada stake (diferença real, esperada num bot de apostas)
    assert abs(retorno_se_a_ganha - retorno_se_b_ganha) < 0.05
    assert sum(stakes.values()) <= 100.01  # nunca aposta mais do que o capital dado


def test_probabilidades_justas_somam_um():
    evento = _evento({
        "Casa X": {"A": 1.90, "B": 2.05},
        "Casa Y": {"A": 2.10, "B": 1.85},
    })
    probs = probabilidades_implicitas_justas(evento)
    assert abs(sum(probs.values()) - 1.0) < 1e-9


def test_deteta_valor_quando_odd_paga_acima_da_probabilidade_justa():
    # Casa Z destoa muito para cima em "A" face ao consenso das outras duas
    evento = _evento({
        "Casa X": {"A": 1.90, "B": 2.00},
        "Casa Y": {"A": 1.92, "B": 1.98},
        "Casa Z": {"A": 2.60, "B": 1.55},
    })
    oportunidades = detetar_valor(evento, margem_minima=0.05)
    assert any(o.bookmaker == "Casa Z" and o.resultado == "A" for o in oportunidades)


def test_nao_deteta_valor_em_mercado_consistente():
    evento = _evento({
        "Casa X": {"A": 1.95, "B": 1.95},
        "Casa Y": {"A": 1.95, "B": 1.95},
        "Casa Z": {"A": 1.95, "B": 1.95},
    })
    assert detetar_valor(evento, margem_minima=0.01) == []
