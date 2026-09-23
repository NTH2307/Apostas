from app.staking import calcular_stake, kelly_fracionado


def test_kelly_e_zero_sem_valor_esperado_positivo():
    # odd 1.90 implica probabilidade justa de mercado ~52.6%; com a mesma
    # probabilidade real não há edge (odd * prob == 1)
    assert kelly_fracionado(odd=1.90, probabilidade=1 / 1.90) == 0.0


def test_kelly_e_negativo_vira_zero_nunca_aposta_contra_si_proprio():
    assert kelly_fracionado(odd=1.50, probabilidade=0.4) == 0.0


def test_kelly_fracionado_e_menor_que_kelly_completo():
    completo = kelly_fracionado(odd=2.50, probabilidade=0.50, fracao=1.0)
    fracionado = kelly_fracionado(odd=2.50, probabilidade=0.50, fracao=0.25)
    assert completo > 0
    assert fracionado == completo * 0.25


def test_calcular_stake_respeita_o_limite_maximo(monkeypatch):
    import config
    monkeypatch.setattr(config, "STAKE_MAXIMA_POR_APOSTA", 5)
    # edge grande -> Kelly pediria muito mais do que o limite
    stake = calcular_stake(capital=1000, odd=3.0, probabilidade=0.6, fracao=1.0)
    assert stake == 5


def test_calcular_stake_nunca_negativa():
    stake = calcular_stake(capital=1000, odd=1.50, probabilidade=0.4)
    assert stake == 0.0
