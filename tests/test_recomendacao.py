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


def test_sugere_resultado_quando_modelo_e_mercado_apontam_para_valor_plausivel():
    analise = analisar_jogo(_evento(1.62, 3.9, 5.5), _forcas(casa_forte=True, jogos=12), "Liga Teste")
    s = analise.sugestao
    assert s.tipo == "1x2"
    assert "Casa" in s.texto
    assert s.odd == 1.62
    assert s.bookmaker == "Casa X"
    assert s.confianca == "alta"
    assert 0.03 <= s.valor <= 0.20
    assert s.stake > 0


def test_poucos_jogos_nao_sugere_aposta_e_avisa():
    analise = analisar_jogo(_evento(1.62, 3.9, 5.5), _forcas(casa_forte=True, jogos=2), "Liga Teste")
    assert analise.sugestao.tipo == "nenhuma"
    assert any("Poucos jogos" in aviso for aviso in analise.avisos)


def test_valor_grande_demais_e_tratado_como_suspeito_e_nao_como_aposta():
    # o mercado acha a casa azarona, o modelo acha-a muito favorita: não confiar
    analise = analisar_jogo(_evento(4.0, 3.6, 1.9), _forcas(casa_forte=True, jogos=12), "Liga Teste")
    assert analise.sugestao.tipo != "1x2"
    assert any("grande demais" in aviso for aviso in analise.avisos)
    assert any(a.tipo == "1x2" and a.confianca == "baixa" for a in analise.alternativas)


def test_sugestao_de_golos_vem_com_odd_minima_acima_da_odd_justa():
    analise = analisar_jogo(_evento(4.0, 3.6, 1.9), _forcas(casa_forte=True, jogos=12), "Liga Teste")
    s = analise.sugestao
    assert s.tipo == "golos"
    assert "Mais de 2.5 golos" in s.texto
    assert s.odd_minima > 1 / s.probabilidade
    assert s.confianca == "média"  # sem odds reais de golos, nunca passa de média


def test_mercado_alinhado_com_modelo_nao_sugere_nada():
    analise = analisar_jogo(_evento(2.2, 3.4, 3.3), _forcas(casa_forte=False, jogos=12), "Liga Teste")
    assert analise.sugestao.tipo == "nenhuma"


def test_equipa_desconhecida_devolve_none():
    evento = _evento(2.2, 3.4, 3.3)
    evento["equipas"] = ["Equipa Inexistente", "Fora"]
    assert analisar_jogo(evento, _forcas(casa_forte=False, jogos=12), "Liga Teste") is None


def test_probabilidade_final_mistura_modelo_e_mercado():
    analise = analisar_jogo(_evento(1.62, 3.9, 5.5), _forcas(casa_forte=True, jogos=12), "Liga Teste")
    for lado in ("casa", "empate", "fora"):
        baixo, alto = sorted((analise.prob_modelo[lado], analise.prob_mercado[lado]))
        assert baixo <= analise.prob_final[lado] <= alto


def test_ordenacao_poe_apostas_de_resultado_confiantes_primeiro():
    aposta_1x2 = analisar_jogo(_evento(1.62, 3.9, 5.5), _forcas(casa_forte=True, jogos=12), "Liga Teste")
    aposta_golos = analisar_jogo(_evento(4.0, 3.6, 1.9), _forcas(casa_forte=True, jogos=12), "Liga Teste")
    sem_aposta = analisar_jogo(_evento(2.2, 3.4, 3.3), _forcas(casa_forte=False, jogos=12), "Liga Teste")
    ordenadas = sorted([sem_aposta, aposta_golos, aposta_1x2], key=chave_ordenacao, reverse=True)
    assert [a.sugestao.tipo for a in ordenadas] == ["1x2", "golos", "nenhuma"]
