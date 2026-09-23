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
