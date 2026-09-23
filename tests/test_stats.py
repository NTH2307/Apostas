import pytest

import app.stats as stats
from app.stats import _filtrar_competicoes, buscar_jogos_terminados, calcular_forcas, listar_competicoes


class _RespostaFalsa:
    def __init__(self, status_code, corpo=None, headers=None):
        self.status_code = status_code
        self._corpo = corpo or {}
        self.headers = headers or {}

    def json(self):
        return self._corpo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def test_calcular_forcas_com_lista_vazia():
    forcas = calcular_forcas([])
    assert forcas == {"media_golos_casa": 0.0, "media_golos_fora": 0.0, "equipas": {}}


def test_calcular_forcas_medias_da_competicao():
    jogos = [
        {"casa": "A", "fora": "B", "golos_casa": 2, "golos_fora": 0},
        {"casa": "C", "fora": "A", "golos_casa": 1, "golos_fora": 3},
    ]
    forcas = calcular_forcas(jogos)
    assert forcas["media_golos_casa"] == pytest.approx(1.5)
    assert forcas["media_golos_fora"] == pytest.approx(1.5)


def test_calcular_forcas_equipa_com_bom_ataque_em_casa():
    jogos = [
        {"casa": "A", "fora": "B", "golos_casa": 2, "golos_fora": 0},
        {"casa": "C", "fora": "A", "golos_casa": 1, "golos_fora": 3},
    ]
    forcas = calcular_forcas(jogos)
    a = forcas["equipas"]["A"]
    assert a["ataque_casa"] == pytest.approx((2 / 1) / 1.5)
    assert a["defesa_casa"] == pytest.approx((0 / 1) / 1.5)
    assert a["ataque_fora"] == pytest.approx((3 / 1) / 1.5)
    assert a["defesa_fora"] == pytest.approx((1 / 1) / 1.5)


def test_calcular_forcas_equipa_so_com_jogos_em_casa_fica_neutra_fora():
    jogos = [
        {"casa": "A", "fora": "B", "golos_casa": 2, "golos_fora": 0},
        {"casa": "C", "fora": "A", "golos_casa": 1, "golos_fora": 3},
    ]
    forcas = calcular_forcas(jogos)
    # C só jogou em casa nesta amostra -> sem jogos fora, fica neutro (1.0)
    c = forcas["equipas"]["C"]
    assert c["ataque_fora"] == 1.0
    assert c["defesa_fora"] == 1.0
    # B só jogou fora nesta amostra -> sem jogos em casa, fica neutro (1.0)
    b = forcas["equipas"]["B"]
    assert b["ataque_casa"] == 1.0
    assert b["defesa_casa"] == 1.0


def _corpo_com_um_jogo():
    return {"matches": [{
        "utcDate": "2026-09-20T15:00:00Z",
        "homeTeam": {"name": "A"}, "awayTeam": {"name": "B"},
        "score": {"fullTime": {"home": 2, "away": 1}},
    }]}


def test_buscar_jogos_terminados_sem_api_key(monkeypatch):
    monkeypatch.setattr("config.FOOTBALL_DATA_API_KEY", "")
    with pytest.raises(RuntimeError):
        buscar_jogos_terminados("PL")


def test_buscar_jogos_terminados_sucesso_direto(monkeypatch):
    monkeypatch.setattr("config.FOOTBALL_DATA_API_KEY", "chave-falsa")
    monkeypatch.setattr(stats.requests, "get", lambda *a, **k: _RespostaFalsa(200, _corpo_com_um_jogo()))

    jogos = buscar_jogos_terminados("PL")
    assert len(jogos) == 1
    assert jogos[0]["casa"] == "A"


def test_buscar_jogos_terminados_repete_apos_429(monkeypatch):
    monkeypatch.setattr("config.FOOTBALL_DATA_API_KEY", "chave-falsa")
    chamadas = []

    def _get_falso(*args, **kwargs):
        chamadas.append(1)
        if len(chamadas) == 1:
            return _RespostaFalsa(429, headers={"Retry-After": "0"})
        return _RespostaFalsa(200, _corpo_com_um_jogo())

    monkeypatch.setattr(stats.requests, "get", _get_falso)
    monkeypatch.setattr(stats.time, "sleep", lambda segundos: None)

    jogos = buscar_jogos_terminados("PL")
    assert len(chamadas) == 2
    assert len(jogos) == 1


def test_buscar_jogos_terminados_desiste_apos_429_persistente(monkeypatch):
    monkeypatch.setattr("config.FOOTBALL_DATA_API_KEY", "chave-falsa")
    monkeypatch.setattr(stats.requests, "get", lambda *a, **k: _RespostaFalsa(429, headers={"Retry-After": "0"}))
    monkeypatch.setattr(stats.time, "sleep", lambda segundos: None)

    with pytest.raises(Exception):
        buscar_jogos_terminados("PL")


def test_filtrar_competicoes_sem_filtro_devolve_tudo():
    competicoes = [{"code": "PL", "name": "Premier League"}, {"code": "EC", "name": "European Championship"}]
    assert _filtrar_competicoes(competicoes, None) == competicoes


def test_filtrar_competicoes_procura_por_nome_codigo_ou_pais():
    competicoes = [
        {"code": "EC", "name": "European Championship", "area": {"name": "Europe"}},
        {"code": "PPL", "name": "Primeira Liga", "area": {"name": "Portugal"}},
    ]
    assert [c["code"] for c in _filtrar_competicoes(competicoes, "portugal")] == ["PPL"]
    assert [c["code"] for c in _filtrar_competicoes(competicoes, "european")] == ["EC"]
    assert _filtrar_competicoes(competicoes, "inexistente") == []


def test_listar_competicoes_sem_api_key(monkeypatch):
    monkeypatch.setattr("config.FOOTBALL_DATA_API_KEY", "")
    with pytest.raises(RuntimeError):
        listar_competicoes()


def test_listar_competicoes_sucesso(monkeypatch):
    monkeypatch.setattr("config.FOOTBALL_DATA_API_KEY", "chave-falsa")
    corpo = {"competitions": [{"code": "PL", "name": "Premier League", "area": {"name": "England"}}]}
    monkeypatch.setattr(stats.requests, "get", lambda *a, **k: _RespostaFalsa(200, corpo))

    competicoes = listar_competicoes()
    assert competicoes[0]["code"] == "PL"
