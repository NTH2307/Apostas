from app.executor import executar_aposta


def test_modo_paper_por_omissao_nunca_executa_real(monkeypatch):
    import config
    monkeypatch.setattr(config, "MODO_PAPER", True)
    monkeypatch.setattr(config, "EXECUCAO_AUTOMATICA", False)

    registo = executar_aposta("Betfair", "Time A", 2.10, 10, market_id="1.234", selection_id=1)
    assert registo["modo"] == "paper"


def test_bookmaker_sem_api_fica_sempre_em_paper_mesmo_com_execucao_ligada(monkeypatch):
    import config
    monkeypatch.setattr(config, "MODO_PAPER", False)
    monkeypatch.setattr(config, "EXECUCAO_AUTOMATICA", True)

    registo = executar_aposta("Casa X (sem API)", "Time A", 2.10, 10)
    assert registo["modo"] == "sem API de execução"


def test_betfair_sem_market_id_fica_em_paper(monkeypatch):
    import config
    monkeypatch.setattr(config, "MODO_PAPER", False)
    monkeypatch.setattr(config, "EXECUCAO_AUTOMATICA", True)

    registo = executar_aposta("Betfair", "Time A", 2.10, 10)  # sem market_id/selection_id
    assert registo["modo"] == "paper"
