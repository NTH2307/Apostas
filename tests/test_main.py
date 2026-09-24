import argparse
import os

import main


def _caminho_exemplo():
    return os.path.join(os.path.dirname(__file__), "..", "data", "exemplo_odds.json")


def test_carregar_eventos_a_partir_de_json_local():
    args = argparse.Namespace(json=_caminho_exemplo(), desporto=None, bookmakers=None)
    eventos = main._carregar_eventos(args)
    assert len(eventos) == 3


def test_cmd_arbitragem_corre_sem_erros_sobre_o_exemplo(capsys):
    args = argparse.Namespace(json=_caminho_exemplo(), desporto=None, bookmakers=None, margem_minima=0.0, capital=100)
    main.cmd_arbitragem(args)
    saida = capsys.readouterr().out
    assert "arbitragem" in saida.lower()


def test_cmd_valor_corre_sem_erros_sobre_o_exemplo(capsys):
    args = argparse.Namespace(
        json=_caminho_exemplo(), desporto=None, bookmakers=None, margem_minima=0.0, odd_maxima=0,
    )
    main.cmd_valor(args)
    saida = capsys.readouterr().out
    assert "valor" in saida.lower()


def test_cmd_valor_respeita_odd_maxima(capsys):
    args = argparse.Namespace(
        json=_caminho_exemplo(), desporto=None, bookmakers=None, margem_minima=0.0, odd_maxima=2.0,
    )
    main.cmd_valor(args)
    saida = capsys.readouterr().out
    assert "odds até 2.0" in saida


def test_cmd_arbitragem_com_filtro_de_bookmakers_via_cli(capsys):
    args = argparse.Namespace(
        json=_caminho_exemplo(), desporto=None, bookmakers="Casa A", margem_minima=0.0, capital=100,
    )
    main.cmd_arbitragem(args)
    saida = capsys.readouterr().out
    # com só uma bookmaker por evento não há arbitragem possível
    assert "0 arbitragem(ns)" in saida


def test_carregar_eventos_filtra_por_dia():
    # os 3 eventos do exemplo: 2 em 2026-09-27 (hora de Portugal) e 1 em 2026-09-28
    args = argparse.Namespace(json=_caminho_exemplo(), desporto=None, bookmakers=None, dia="2026-09-27", amanha=False)
    eventos = main._carregar_eventos(args)
    assert len(eventos) == 2


def test_resolver_desportos_aceita_lista_separada_por_virgulas():
    args = argparse.Namespace(desporto="soccer_epl, basketball_nba")
    assert main._resolver_desportos(args) == ["soccer_epl", "basketball_nba"]


def test_resolver_desportos_sem_argumento_usa_config(monkeypatch):
    import config
    monkeypatch.setattr(config, "DESPORTOS", ["soccer_portugal_primeira_liga"])
    args = argparse.Namespace(desporto=None)
    assert main._resolver_desportos(args) == ["soccer_portugal_primeira_liga"]


def _evento_modelo(desporto, casa, fora):
    return {
        "id": f"{casa}-{fora}", "desporto": desporto, "hora_inicio": "", "equipas": [casa, fora],
        "bookmakers": {"Casa X": {casa: 1.9, "Draw": 3.4, fora: 4.0}},
    }


def test_cmd_bookmakers_lista_nomes_exatos(monkeypatch, capsys):
    monkeypatch.setattr(main, "buscar_odds", lambda desporto: [
        {"bookmakers": {"Betclic (FR)": {}, "Betfair": {}}},
    ])
    args = argparse.Namespace(desporto="soccer_epl")
    main.cmd_bookmakers(args)
    saida = capsys.readouterr().out
    assert "Betclic (FR)" in saida
    assert "Betfair" in saida


def test_cmd_bookmakers_sem_resultados_avisa(monkeypatch, capsys):
    monkeypatch.setattr(main, "buscar_odds", lambda desporto: [])
    args = argparse.Namespace(desporto="soccer_epl")
    main.cmd_bookmakers(args)
    saida = capsys.readouterr().out
    assert "Nenhum bookmaker" in saida


def test_cmd_competicoes_imprime_codigo_nome_e_pais(monkeypatch, capsys):
    monkeypatch.setattr(main, "listar_competicoes", lambda filtro: [
        {"code": "PPL", "name": "Primeira Liga", "area": {"name": "Portugal"}},
    ])
    args = argparse.Namespace(filtro="portugal")
    main.cmd_competicoes(args)
    saida = capsys.readouterr().out
    assert "PPL" in saida
    assert "Primeira Liga" in saida
    assert "Portugal" in saida


def test_cmd_competicoes_sem_resultados_avisa(monkeypatch, capsys):
    monkeypatch.setattr(main, "listar_competicoes", lambda filtro: [])
    args = argparse.Namespace(filtro="inexistente")
    main.cmd_competicoes(args)
    saida = capsys.readouterr().out
    assert "Nenhuma competição" in saida


def test_cmd_modelo_sem_competicao_nem_todas_avisa_e_nao_rebenta(capsys):
    args = argparse.Namespace(competicao=None, desporto=None, todas=False)
    main.cmd_modelo(args)
    saida = capsys.readouterr().out
    assert "--todas" in saida


def test_cmd_modelo_uma_competicao(monkeypatch, capsys):
    jogos = [{"casa": "Time A", "fora": "Time B", "golos_casa": 2, "golos_fora": 0}]
    monkeypatch.setattr(main, "buscar_jogos_terminados", lambda competicao, limite: jogos)
    monkeypatch.setattr(main, "buscar_odds", lambda desporto: [_evento_modelo(desporto, "Time A", "Time B")])

    args = argparse.Namespace(
        competicao="TESTE", desporto="soccer_teste", todas=False, jogos_historico=200,
        margem_minima=0.05, bookmakers=None, amanha=False, dia=None,
    )
    main.cmd_modelo(args)
    saida = capsys.readouterr().out
    assert "Time A vs Time B" in saida
    assert "1 jogo(s) analisados em 1 competição" in saida


def test_cmd_modelo_por_omissao_mostra_so_a_data_mais_proxima_com_jogos(monkeypatch, capsys):
    jogos = [{"casa": "Time A", "fora": "Time B", "golos_casa": 2, "golos_fora": 0}]
    monkeypatch.setattr(main, "buscar_jogos_terminados", lambda competicao, limite: jogos)
    eventos = [
        {
            "id": "longe", "desporto": "soccer_teste", "hora_inicio": "2026-10-10T15:00:00Z",
            "equipas": ["Time C", "Time D"], "bookmakers": {},
        },
        {
            "id": "perto", "desporto": "soccer_teste", "hora_inicio": "2026-09-25T15:00:00Z",
            "equipas": ["Time A", "Time B"],
            "bookmakers": {"Casa X": {"Time A": 1.9, "Draw": 3.4, "Time B": 4.0}},
        },
    ]
    monkeypatch.setattr(main, "buscar_odds", lambda desporto: eventos)

    args = argparse.Namespace(
        competicao="TESTE", desporto="soccer_teste", todas=False, jogos_historico=200,
        margem_minima=0.05, bookmakers=None, amanha=False, dia=None,
    )
    main.cmd_modelo(args)
    saida = capsys.readouterr().out
    assert "Time A vs Time B" in saida
    assert "Time C vs Time D" not in saida
    assert "2026-09-25" in saida


def test_cmd_modelo_avisa_proxima_data_quando_dia_pedido_nao_tem_jogos(monkeypatch, capsys):
    jogos = [{"casa": "Time A", "fora": "Time B", "golos_casa": 2, "golos_fora": 0}]
    monkeypatch.setattr(main, "buscar_jogos_terminados", lambda competicao, limite: jogos)
    eventos = [
        {
            "id": "e1", "desporto": "soccer_teste", "hora_inicio": "2026-09-30T15:00:00Z",
            "equipas": ["Time A", "Time B"],
            "bookmakers": {"Casa X": {"Time A": 1.9, "Draw": 3.4, "Time B": 4.0}},
        },
    ]
    monkeypatch.setattr(main, "buscar_odds", lambda desporto: eventos)

    args = argparse.Namespace(
        competicao="TESTE", desporto="soccer_teste", todas=False, jogos_historico=200,
        margem_minima=0.05, bookmakers=None, amanha=False, dia="2026-09-24",
    )
    main.cmd_modelo(args)
    saida = capsys.readouterr().out
    assert "próxima data com jogos: 2026-09-30" in saida
    assert "Time A vs Time B" not in saida


def test_cmd_modelo_todas_soma_varias_competicoes(monkeypatch, capsys):
    import config
    monkeypatch.setattr(config, "COMPETICOES_MODELO", [("C1", "soccer_c1"), ("C2", "soccer_c2")])
    monkeypatch.setattr(main.time, "sleep", lambda segundos: None)

    jogos_por_competicao = {
        "C1": [{"casa": "A", "fora": "B", "golos_casa": 1, "golos_fora": 0}],
        "C2": [{"casa": "C", "fora": "D", "golos_casa": 1, "golos_fora": 0}],
    }
    monkeypatch.setattr(main, "buscar_jogos_terminados", lambda competicao, limite: jogos_por_competicao[competicao])
    monkeypatch.setattr(main, "buscar_odds", lambda desporto: [
        _evento_modelo(desporto, *({"soccer_c1": ("A", "B"), "soccer_c2": ("C", "D")}[desporto]))
    ])

    args = argparse.Namespace(
        competicao=None, desporto=None, todas=True, jogos_historico=200,
        margem_minima=0.05, bookmakers=None, amanha=False, dia=None,
    )
    main.cmd_modelo(args)
    saida = capsys.readouterr().out
    assert "=== C1" in saida
    assert "=== C2" in saida
    assert "em 2 competição(ões)" in saida


def test_cmd_modelo_todas_uma_competicao_falha_nao_para_as_outras(monkeypatch, capsys):
    import config
    monkeypatch.setattr(config, "COMPETICOES_MODELO", [("QUEBRADA", "soccer_x"), ("C2", "soccer_c2")])
    monkeypatch.setattr(main.time, "sleep", lambda segundos: None)

    def _buscar_jogos(competicao, limite):
        if competicao == "QUEBRADA":
            raise RuntimeError("404 not found")
        return [{"casa": "C", "fora": "D", "golos_casa": 1, "golos_fora": 0}]

    monkeypatch.setattr(main, "buscar_jogos_terminados", _buscar_jogos)
    monkeypatch.setattr(main, "buscar_odds", lambda desporto: [_evento_modelo(desporto, "C", "D")])

    args = argparse.Namespace(
        competicao=None, desporto=None, todas=True, jogos_historico=200,
        margem_minima=0.05, bookmakers=None, amanha=False, dia=None,
    )
    main.cmd_modelo(args)
    saida = capsys.readouterr().out
    assert "QUEBRADA" in saida
    assert "=== C2" in saida
