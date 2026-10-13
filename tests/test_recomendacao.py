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


def _forcas_alto_marcador(jogos: int) -> dict:
    # equipas simétricas (1X2 fica perto da média da liga) mas ambas atacam
    # muito e defendem mal (golos desvia muito da média da liga)
    equipa = {"ataque_casa": 2.0, "defesa_casa": 1.8, "ataque_fora": 2.0, "defesa_fora": 1.8}
    return {
        "media_golos_casa": 1.5,
        "media_golos_fora": 1.2,
        "equipas": {"Casa FC": {**equipa, "jogos": jogos}, "Fora FC": {**equipa, "jogos": jogos}},
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


def test_opiniao_principal_e_1x2_quando_e_o_mercado_mais_fora_do_normal():
    analise = analisar_jogo(_evento(), _forcas(casa_forte=True, jogos=12), "Liga Teste")
    assert analise.sugestao.tipo == "1x2"
    assert "Casa" in analise.sugestao.texto
    assert analise.sugestao.confianca == "alta"
    # mostra mais do que uma opinião quando vários mercados se destacam no mesmo jogo
    assert len(analise.alternativas) >= 1
    for alt in analise.alternativas:
        assert alt.tipo == "golos"
        assert alt.confianca == "média"  # sem odds reais de golos, nunca passa de média


def test_opiniao_principal_pode_ser_golos_quando_e_o_mercado_mais_fora_do_normal():
    # equipas simétricas entre si: o 1X2 fica perto da média da liga, mas o
    # ritmo de golos está muito acima do normal — a opinião principal deve
    # refletir isso, não ficar presa ao resultado
    analise = analisar_jogo(_evento(), _forcas_alto_marcador(jogos=12), "Liga Teste")
    assert analise.sugestao.tipo == "golos"
    assert "golos" in analise.sugestao.texto.lower()


def test_poucos_jogos_continua_a_dar_opiniao_mas_avisa_confianca_baixa():
    analise = analisar_jogo(_evento(), _forcas(casa_forte=True, jogos=4), "Liga Teste")
    assert analise.sugestao.confianca == "baixa"
    assert any("Poucos jogos" in aviso for aviso in analise.avisos)


def test_amostra_quase_zero_diz_dados_insuficientes_e_nao_mostra_alternativas():
    # jogos=1: a amostra é tão pequena que as forças ficam quase só no prior
    # (equipa média) — a opinião tem de dizer isso claramente, não fingir
    # um palpite específico com alternativas que seriam só ruído
    analise = analisar_jogo(_evento(), _forcas(casa_forte=True, jogos=1), "Liga Teste")
    assert "dados insuficientes" in analise.sugestao.texto.lower()
    assert analise.alternativas == []
    assert any("não há dados reais suficientes" in aviso for aviso in analise.avisos)


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
