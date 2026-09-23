import pytest

from app.stats import calcular_forcas


def test_calcular_forcas_com_lista_vazia():
    forcas = calcular_forcas([])
    assert forcas == {"media_golos_casa": 0.0, "media_golos_fora": 0.0, "equipas": {}}


def test_calcular_forcas_medias_da_competicao():
    jogos = [
        {"casa": "A", "fora": "B", "golos_casa": 2, "golos_fora": 0},
        {"casa": "C", "fora": "A", "golos_casa": 1, "golos_fora": 3},
    ]
    forcas = calcular_forcas(jogos)
    assert forcas["media_golos_casa"] == pytest.approx(1.5)
    assert forcas["media_golos_fora"] == pytest.approx(1.5)


def test_calcular_forcas_equipa_com_bom_ataque_em_casa():
    jogos = [
        {"casa": "A", "fora": "B", "golos_casa": 2, "golos_fora": 0},
        {"casa": "C", "fora": "A", "golos_casa": 1, "golos_fora": 3},
    ]
    forcas = calcular_forcas(jogos)
    a = forcas["equipas"]["A"]
    assert a["ataque_casa"] == pytest.approx((2 / 1) / 1.5)
    assert a["defesa_casa"] == pytest.approx((0 / 1) / 1.5)
    assert a["ataque_fora"] == pytest.approx((3 / 1) / 1.5)
    assert a["defesa_fora"] == pytest.approx((1 / 1) / 1.5)


def test_calcular_forcas_equipa_so_com_jogos_em_casa_fica_neutra_fora():
    jogos = [
        {"casa": "A", "fora": "B", "golos_casa": 2, "golos_fora": 0},
        {"casa": "C", "fora": "A", "golos_casa": 1, "golos_fora": 3},
    ]
    forcas = calcular_forcas(jogos)
    # C só jogou em casa nesta amostra -> sem jogos fora, fica neutro (1.0)
    c = forcas["equipas"]["C"]
    assert c["ataque_fora"] == 1.0
    assert c["defesa_fora"] == 1.0
    # B só jogou fora nesta amostra -> sem jogos em casa, fica neutro (1.0)
    b = forcas["equipas"]["B"]
    assert b["ataque_casa"] == 1.0
    assert b["defesa_casa"] == 1.0
