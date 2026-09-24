from datetime import datetime, timedelta, timezone

import pytest

import app.lesoes as lesoes_mod
from app.lesoes import lesoes_recentes, procurar_equipa_id


class _RespostaFalsa:
    def __init__(self, corpo):
        self._corpo = corpo

    def json(self):
        return self._corpo

    def raise_for_status(self):
        pass


def test_procurar_equipa_id_sem_api_key(monkeypatch):
    monkeypatch.setattr("config.API_FOOTBALL_KEY", "")
    with pytest.raises(RuntimeError):
        procurar_equipa_id("Benfica")


def test_procurar_equipa_id_devolve_primeiro_resultado(monkeypatch):
    monkeypatch.setattr("config.API_FOOTBALL_KEY", "chave-falsa")
    monkeypatch.setattr(lesoes_mod.requests, "get", lambda *a, **k: _RespostaFalsa(
        {"response": [{"team": {"id": 42, "name": "SL Benfica"}}]}
    ))
    assert procurar_equipa_id("Benfica") == 42


def test_procurar_equipa_id_sem_resultados_devolve_none(monkeypatch):
    monkeypatch.setattr("config.API_FOOTBALL_KEY", "chave-falsa")
    monkeypatch.setattr(lesoes_mod.requests, "get", lambda *a, **k: _RespostaFalsa({"response": []}))
    assert procurar_equipa_id("Equipa Inexistente") is None


def test_pedir_levanta_erro_da_api(monkeypatch):
    monkeypatch.setattr("config.API_FOOTBALL_KEY", "chave-falsa")
    monkeypatch.setattr(lesoes_mod.requests, "get", lambda *a, **k: _RespostaFalsa(
        {"response": [], "errors": {"token": "chave inválida"}}
    ))
    with pytest.raises(RuntimeError):
        procurar_equipa_id("Benfica")


def _data(dias_atras: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=dias_atras)).isoformat().replace("+00:00", "Z")


def test_lesoes_recentes_filtra_por_janela_de_dias(monkeypatch):
    monkeypatch.setattr("config.API_FOOTBALL_KEY", "chave-falsa")
    corpo = {"response": [
        {"player": {"name": "Jogador Recente", "reason": "Entorse"}, "fixture": {"date": _data(5)}},
        {"player": {"name": "Jogador Antigo", "reason": "Fratura"}, "fixture": {"date": _data(90)}},
    ]}
    monkeypatch.setattr(lesoes_mod.requests, "get", lambda *a, **k: _RespostaFalsa(corpo))

    resultado = lesoes_recentes(42, dias=30)
    nomes = [l["jogador"] for l in resultado]
    assert "Jogador Recente" in nomes
    assert "Jogador Antigo" not in nomes


def test_lesoes_recentes_nao_repete_jogador_mantem_mais_recente(monkeypatch):
    monkeypatch.setattr("config.API_FOOTBALL_KEY", "chave-falsa")
    corpo = {"response": [
        {"player": {"name": "Jogador X", "reason": "Entorse"}, "fixture": {"date": _data(20)}},
        {"player": {"name": "Jogador X", "reason": "Recuperado, nova lesão"}, "fixture": {"date": _data(2)}},
    ]}
    monkeypatch.setattr(lesoes_mod.requests, "get", lambda *a, **k: _RespostaFalsa(corpo))

    resultado = lesoes_recentes(42, dias=30)
    assert len(resultado) == 1
    assert resultado[0]["motivo"] == "Recuperado, nova lesão"


def test_lesoes_recentes_ignora_entradas_sem_data(monkeypatch):
    monkeypatch.setattr("config.API_FOOTBALL_KEY", "chave-falsa")
    corpo = {"response": [{"player": {"name": "Jogador Y", "reason": "?"}, "fixture": {}}]}
    monkeypatch.setattr(lesoes_mod.requests, "get", lambda *a, **k: _RespostaFalsa(corpo))
    assert lesoes_recentes(42, dias=30) == []
