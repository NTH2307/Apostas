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


def _evento(odds_casa, odds_empate, odds_fora):
    return {
        "id": "e1", "desporto": "soccer_teste", "hora_inicio": "2026-10-10T14:00:00Z",
        "equipas": ["Casa", "Fora"],
        "bookmakers": {
            "Casa X": {"Casa": odds_casa, "Draw": odds_empate, "Fora": odds_fora},
            "Casa Y": {"Casa": round(odds_casa - 0.02, 2), "Draw": odds_empate, "Fora": odds_fora},
        },
    }


def test_confianca_por_amostra():
    assert confianca_por_amostra(12) == "alta"
    assert confianca_por_amostra(6) == "média"
    assert confianca_por_amostra(2) == "baixa"


def test_palpite_1x2_e_sempre_o_favorito_do_modelo_com_odd_de_referencia():
    analise = analisar_jogo(_evento(1.62, 3.9, 5.5), _forcas(casa_forte=True, jogos=12), "Liga Teste")
    s = analise.sugestao
    assert s.tipo == "1x2"
    assert "Casa" in s.texto
    assert s.odd == 1.62
    assert s.bookmaker == "Casa X"
    assert s.confianca == "alta"
    assert s.probabilidade == analise.prob_modelo["casa"]
    assert s.stake > 0


def test_poucos_jogos_continua_a_dar_palpite_mas_avisa_confianca_baixa():
    analise = analisar_jogo(_evento(1.62, 3.9, 5.5), _forcas(casa_forte=True, jogos=2), "Liga Teste")
    assert analise.sugestao.tipo == "1x2"
    assert analise.sugestao.confianca == "baixa"
    assert any("Poucos jogos" in aviso for aviso in analise.avisos)


def test_valor_grande_demais_continua_a_ser_palpite_mas_avisa_pouco_credivel():
    # o mercado acha a casa azarona, o modelo acha-a muito favorita: o palpite
    # aparece à mesma (é a opinião do modelo), mas com aviso de desconfiança
    analise = analisar_jogo(_evento(4.0, 3.6, 1.9), _forcas(casa_forte=True, jogos=12), "Liga Teste")
    assert analise.sugestao.tipo == "1x2"
    assert "Casa" in analise.sugestao.texto
    assert any("grande demais" in aviso for aviso in analise.avisos)


def test_sugestao_de_golos_aparece_como_alternativa_com_odd_minima_acima_da_odd_justa():
    analise = analisar_jogo(_evento(4.0, 3.6, 1.9), _forcas(casa_forte=True, jogos=12), "Liga Teste")
    golos = next(a for a in analise.alternativas if a.tipo == "golos")
    assert "Mais de 2.5 golos" in golos.texto
    assert golos.odd_minima > 1 / golos.probabilidade
    assert golos.confianca == "média"  # sem odds reais de golos, nunca passa de média


def test_mercado_alinhado_com_modelo_ainda_assim_da_palpite():
    analise = analisar_jogo(_evento(2.2, 3.4, 3.3), _forcas(casa_forte=False, jogos=12), "Liga Teste")
    assert analise.sugestao.tipo == "1x2"


def test_equipa_desconhecida_devolve_none():
    evento = _evento(2.2, 3.4, 3.3)
    evento["equipas"] = ["Equipa Inexistente", "Fora"]
    assert analisar_jogo(evento, _forcas(casa_forte=False, jogos=12), "Liga Teste") is None


def test_probabilidade_final_mistura_modelo_e_mercado():
    analise = analisar_jogo(_evento(1.62, 3.9, 5.5), _forcas(casa_forte=True, jogos=12), "Liga Teste")
    for lado in ("casa", "empate", "fora"):
        baixo, alto = sorted((analise.prob_modelo[lado], analise.prob_mercado[lado]))
        assert baixo <= analise.prob_final[lado] <= alto


def test_ordenacao_poe_confianca_maior_primeiro_e_depois_valor_maior():
    confianca_baixa = analisar_jogo(_evento(1.62, 3.9, 5.5), _forcas(casa_forte=True, jogos=2), "Liga Teste")
    valor_grande = analisar_jogo(_evento(4.0, 3.6, 1.9), _forcas(casa_forte=True, jogos=12), "Liga Teste")
    valor_moderado = analisar_jogo(_evento(1.62, 3.9, 5.5), _forcas(casa_forte=True, jogos=12), "Liga Teste")
    ordenadas = sorted([confianca_baixa, valor_grande, valor_moderado], key=chave_ordenacao, reverse=True)
    assert ordenadas[0] in (valor_grande, valor_moderado)
    assert ordenadas[-1] is confianca_baixa
