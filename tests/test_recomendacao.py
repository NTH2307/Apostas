from app.recomendacao import analisar_jogo, chave_ordenacao, confianca_por_amostra


def _forcas(casa_forte: bool, jogos: int) -> dict:
    if casa_forte:
        casa = {"ataque_casa": 1.6, "defesa_casa": 0.7, "ataque_fora": 1.4, "defesa_fora": 0.8}
        fora = {"ataque_casa": 0.8, "defesa_casa": 1.3, "ataque_fora": 0.7, "defesa_fora": 1.4}
    else:
        casa = {"ataque_casa": 1.0, "defesa_casa": 1.0, "ataque_fora": 1.0, "defesa_fora": 1.0}
        fora = dict(casa)
    return {
        "media_golos_casa": 1.5,
        "media_golos_fora": 1.2,
        "equipas": {"Casa FC": {**casa, "jogos": jogos}, "Fora FC": {**fora, "jogos": jogos}},
    }


def _evento() -> dict:
    return {
        "id": "e1", "desporto": "soccer_teste", "hora_inicio": "2026-10-10T14:00:00Z",
        "equipas": ["Casa", "Fora"],
    }


def test_confianca_por_amostra():
    assert confianca_por_amostra(12) == "alta"
    assert confianca_por_amostra(6) == "média"
    assert confianca_por_amostra(2) == "baixa"


def test_opiniao_principal_e_o_mercado_mais_decisivo_nao_so_1x2():
    # casa muito mais forte: o 1X2 é o mercado mais decisivo (maior margem)
    decisivo = analisar_jogo(_evento(), _forcas(casa_forte=True, jogos=12), "Liga Teste")
    assert decisivo.sugestao.tipo == "1x2"
    assert "Casa" in decisivo.sugestao.texto

    # equipas equivalentes: o 1X2 fica equilibrado, mas golos continua decisivo —
    # a opinião principal passa a ser sobre golos, não sobre o resultado
    equilibrado = analisar_jogo(_evento(), _forcas(casa_forte=False, jogos=12), "Liga Teste")
    assert equilibrado.sugestao.tipo == "golos"


def test_mostra_mais_do_que_uma_opiniao_quando_mais_de_um_mercado_e_decisivo():
    analise = analisar_jogo(_evento(), _forcas(casa_forte=True, jogos=12), "Liga Teste")
    assert len(analise.alternativas) >= 1
    for alt in analise.alternativas:
        assert alt.tipo == "golos"
        assert alt.confianca == "média"  # sem odds reais de golos, nunca passa de média
        assert alt.odd_minima > 1 / alt.probabilidade


def test_poucos_jogos_continua_a_dar_opiniao_mas_avisa_confianca_baixa():
    analise = analisar_jogo(_evento(), _forcas(casa_forte=True, jogos=2), "Liga Teste")
    assert analise.sugestao.confianca == "baixa"
    assert any("Poucos jogos" in aviso for aviso in analise.avisos)


def test_equipa_desconhecida_devolve_none():
    evento = _evento()
    evento["equipas"] = ["Equipa Inexistente", "Fora"]
    assert analisar_jogo(evento, _forcas(casa_forte=False, jogos=12), "Liga Teste") is None


def test_ordenacao_poe_confianca_maior_primeiro_e_depois_probabilidade_maior():
    confianca_baixa = analisar_jogo(_evento(), _forcas(casa_forte=True, jogos=2), "Liga Teste")
    confianca_alta = analisar_jogo(_evento(), _forcas(casa_forte=True, jogos=12), "Liga Teste")
    ordenadas = sorted([confianca_baixa, confianca_alta], key=chave_ordenacao, reverse=True)
    assert ordenadas[0] is confianca_alta
    assert ordenadas[-1] is confianca_baixa
