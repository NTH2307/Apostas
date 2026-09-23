import app.live as live


def test_resumo_diario_sem_oportunidades_ainda_assim_envia_alerta(monkeypatch):
    monkeypatch.setattr(live, "verificar_uma_vez", lambda desporto: {"arbitragens": 0, "valores": 0})
    mensagens = []
    monkeypatch.setattr(live, "enviar_alerta", lambda texto: mensagens.append(texto) or True)

    totais = live.resumo_diario(["soccer_epl", "basketball_nba"])

    assert totais == {"arbitragens": 0, "valores": 0, "erros": []}
    assert len(mensagens) == 1
    assert "nada encontrado" in mensagens[0].lower()


def test_resumo_diario_soma_oportunidades_de_varios_desportos(monkeypatch):
    resultados = {"soccer_epl": {"arbitragens": 1, "valores": 2}, "basketball_nba": {"arbitragens": 0, "valores": 3}}
    monkeypatch.setattr(live, "verificar_uma_vez", lambda desporto: resultados[desporto])
    mensagens = []
    monkeypatch.setattr(live, "enviar_alerta", lambda texto: mensagens.append(texto) or True)

    totais = live.resumo_diario(["soccer_epl", "basketball_nba"])

    assert totais["arbitragens"] == 1
    assert totais["valores"] == 5
    assert "1 arbitragem" in mensagens[0]
    assert "5 aposta" in mensagens[0]


def test_resumo_diario_um_desporto_com_erro_nao_para_os_restantes(monkeypatch):
    def _verificar(desporto):
        if desporto == "chave_invalida":
            raise RuntimeError("404 not found")
        return {"arbitragens": 0, "valores": 1}

    monkeypatch.setattr(live, "verificar_uma_vez", _verificar)
    mensagens = []
    monkeypatch.setattr(live, "enviar_alerta", lambda texto: mensagens.append(texto) or True)

    totais = live.resumo_diario(["chave_invalida", "soccer_epl"])

    assert totais["valores"] == 1
    assert len(totais["erros"]) == 1
    assert "chave_invalida" in totais["erros"][0]
    assert "chave_invalida" in mensagens[0]


def test_resumo_diario_usa_desportos_do_config_por_omissao(monkeypatch):
    import config
    monkeypatch.setattr(config, "DESPORTOS", ["soccer_epl"])
    chamadas = []
    monkeypatch.setattr(live, "verificar_uma_vez", lambda desporto: chamadas.append(desporto) or {"arbitragens": 0, "valores": 0})
    monkeypatch.setattr(live, "enviar_alerta", lambda texto: True)

    live.resumo_diario()

    assert chamadas == ["soccer_epl"]
