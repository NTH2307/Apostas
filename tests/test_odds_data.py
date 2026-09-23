from datetime import date

from app.odds import _filtrar_desportos, filtrar_por_dia, proxima_data_com_jogos


def _evento(id_, hora_inicio):
    return {"id": id_, "desporto": "teste", "hora_inicio": hora_inicio, "equipas": ["A", "B"], "bookmakers": {}}


def test_filtrar_por_dia_mantem_so_eventos_desse_dia_no_fuso_de_portugal():
    eventos = [
        _evento("cedo_demais", "2026-09-27T22:30:00Z"),   # 23:30 em Lisboa (verão) -> dia 27
        _evento("no_dia", "2026-09-28T20:00:00Z"),         # 21:00 em Lisboa -> dia 28
        _evento("tarde_demais", "2026-09-29T10:00:00Z"),   # dia 29
        _evento("sem_hora", ""),
    ]
    filtrados = filtrar_por_dia(eventos, date(2026, 9, 28))
    assert [e["id"] for e in filtrados] == ["no_dia"]


def test_filtrar_por_dia_perto_da_meia_noite_muda_de_dia_com_o_fuso():
    # 23:30 UTC de dia 27 é já 00:30 do dia 28 em Lisboa (horário de verão, UTC+1)
    eventos = [_evento("perto_da_meia_noite", "2026-09-27T23:30:00Z")]
    assert [e["id"] for e in filtrar_por_dia(eventos, date(2026, 9, 28))] == ["perto_da_meia_noite"]
    assert filtrar_por_dia(eventos, date(2026, 9, 27)) == []


def test_proxima_data_com_jogos_devolve_a_data_mais_cedo():
    eventos = [
        _evento("depois", "2026-10-05T20:00:00Z"),
        _evento("mais_cedo", "2026-09-28T20:00:00Z"),
        _evento("sem_hora", ""),
    ]
    assert proxima_data_com_jogos(eventos) == date(2026, 9, 28)


def test_proxima_data_com_jogos_sem_eventos_devolve_none():
    assert proxima_data_com_jogos([]) is None
    assert proxima_data_com_jogos([_evento("sem_hora", "")]) is None


def test_filtrar_desportos_sem_filtro_devolve_tudo():
    desportos = [{"key": "soccer_epl", "title": "EPL"}, {"key": "basketball_nba", "title": "NBA"}]
    assert _filtrar_desportos(desportos, None) == desportos


def test_filtrar_desportos_procura_por_titulo_ou_chave_sem_distinguir_maiusculas():
    desportos = [
        {"key": "soccer_uefa_nations_league", "title": "UEFA Nations League", "description": ""},
        {"key": "basketball_nba", "title": "NBA", "description": ""},
    ]
    assert [d["key"] for d in _filtrar_desportos(desportos, "nations")] == ["soccer_uefa_nations_league"]
    assert [d["key"] for d in _filtrar_desportos(desportos, "NBA")] == ["basketball_nba"]
    assert _filtrar_desportos(desportos, "inexistente") == []
