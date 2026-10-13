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


def test_palpite_1x2_e_sempre_o_favorito_do_modelo():
    analise = analisar_jogo(_evento(), _forcas(casa_forte=True, jogos=12), "Liga Teste")
    s = analise.sugestao
    assert s.tipo == "1x2"
    assert "Casa" in s.texto
    assert s.confianca == "alta"
    assert s.probabilidade == analise.prob_modelo["casa"]


def test_poucos_jogos_continua_a_dar_palpite_mas_avisa_confianca_baixa():
    analise = analisar_jogo(_evento(), _forcas(casa_forte=True, jogos=2), "Liga Teste")
    assert analise.sugestao.tipo == "1x2"
    assert analise.sugestao.confianca == "baixa"
    assert any("Poucos jogos" in aviso for aviso in analise.avisos)


def test_mostra_sempre_as_duas_opinioes_de_golos_over_under_e_btts():
    analise = analisar_jogo(_evento(), _forcas(casa_forte=True, jogos=12), "Liga Teste")
    assert len(analise.alternativas) == 2
    textos = [a.texto for a in analise.alternativas]
    assert any("golos" in t.lower() for t in textos)
    assert any("ambas marcam" in t.lower() for t in textos)
    for golos in analise.alternativas:
        assert golos.tipo == "golos"
        assert golos.odd_minima > 1 / golos.probabilidade
        assert golos.confianca == "média"  # sem odds reais de golos, nunca passa de média


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
