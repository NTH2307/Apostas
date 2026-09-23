from app.poisson import _poisson, golos_esperados, probabilidades


def test_poisson_soma_um_sobre_o_suporte():
    total = sum(_poisson(k, 1.7) for k in range(50))
    assert abs(total - 1.0) < 1e-9


def test_poisson_lambda_zero_da_tudo_a_zero_golos():
    assert _poisson(0, 0) == 1.0
    assert _poisson(1, 0) == 0.0


def test_probabilidades_1x2_somam_um():
    # a grelha é truncada em MAX_GOLOS, por isso não soma exatamente 1
    probs = probabilidades(1.8, 1.1)
    assert abs(probs["casa"] + probs["empate"] + probs["fora"] - 1.0) < 1e-3


def test_probabilidades_over_under_somam_um():
    probs = probabilidades(1.8, 1.1)
    assert abs(probs["over_2.5"] + probs["under_2.5"] - 1.0) < 1e-9


def test_probabilidades_btts_somam_um():
    probs = probabilidades(1.8, 1.1)
    assert abs(probs["btts_sim"] + probs["btts_nao"] - 1.0) < 1e-9


def test_equipas_com_mesmos_golos_esperados_tem_1x2_simetrico():
    probs = probabilidades(1.4, 1.4)
    assert abs(probs["casa"] - probs["fora"]) < 1e-9


def test_equipa_casa_com_mais_golos_esperados_e_mais_favorita():
    probs = probabilidades(2.5, 0.8)
    assert probs["casa"] > probs["fora"]
    assert probs["casa"] > probs["empate"]


def test_golos_esperados_maior_ataque_da_mais_golos_esperados():
    forcas = {
        "media_golos_casa": 1.5, "media_golos_fora": 1.2,
        "equipas": {
            "Forte": {"ataque_casa": 1.6, "defesa_casa": 0.7, "ataque_fora": 1.5, "defesa_fora": 0.8},
            "Fraco": {"ataque_casa": 0.6, "defesa_casa": 1.3, "ataque_fora": 0.5, "defesa_fora": 1.4},
        },
    }
    lambda_casa, lambda_fora = golos_esperados(forcas, "Forte", "Fraco")
    assert lambda_casa > lambda_fora


def test_golos_esperados_devolve_none_se_faltar_equipa():
    forcas = {"media_golos_casa": 1.5, "media_golos_fora": 1.2, "equipas": {"A": {}}}
    assert golos_esperados(forcas, "A", "B") is None
