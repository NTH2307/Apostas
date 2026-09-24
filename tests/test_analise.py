from datetime import date

import app.analise as analise_mod
from app.analise import analisar_competicao


def _evento(casa, fora, hora_inicio="2026-09-25T15:00:00Z"):
    return {
        "id": f"{casa}-{fora}", "desporto": "soccer_teste", "hora_inicio": hora_inicio,
        "equipas": [casa, fora],
        "bookmakers": {"Casa X": {casa: 1.9, "Draw": 3.4, fora: 4.0}},
    }


def test_analisar_competicao_sem_jogos_terminados(monkeypatch):
    monkeypatch.setattr(analise_mod, "buscar_jogos_terminados", lambda competicao, limite: [])
    resultado = analisar_competicao("PL", "soccer_epl", date(2026, 9, 24), date(2026, 9, 30))
    assert resultado.nota is not None
    assert resultado.analises == []


def test_analisar_competicao_sem_jogos_no_periodo_diz_a_proxima_data(monkeypatch):
    jogos = [{"casa": "A", "fora": "B", "golos_casa": 1, "golos_fora": 0}]
    monkeypatch.setattr(analise_mod, "buscar_jogos_terminados", lambda competicao, limite: jogos)
    monkeypatch.setattr(analise_mod, "buscar_odds", lambda desporto: [_evento("A", "B", "2026-10-15T15:00:00Z")])

    resultado = analisar_competicao("PL", "soccer_epl", date(2026, 9, 24), date(2026, 9, 30))
    assert "15/10/2026" in resultado.nota
    assert resultado.analises == []


def test_analisar_competicao_analisa_jogos_do_periodo(monkeypatch):
    jogos = [
        {"casa": "A", "fora": "B", "golos_casa": 2, "golos_fora": 0},
        {"casa": "B", "fora": "A", "golos_casa": 0, "golos_fora": 2},
    ] * 6
    monkeypatch.setattr(analise_mod, "buscar_jogos_terminados", lambda competicao, limite: jogos)
    monkeypatch.setattr(analise_mod, "buscar_odds", lambda desporto: [
        _evento("A", "B"), _evento("Equipa C", "Equipa D"),
    ])

    resultado = analisar_competicao("PL", "soccer_epl", date(2026, 9, 24), date(2026, 9, 30))
    assert len(resultado.analises) == 1
    assert resultado.analises[0].casa == "A"
    assert resultado.sem_dados == ["Equipa C vs Equipa D"]


def test_analisar_competicao_sem_lesoes_por_omissao(monkeypatch):
    jogos = [{"casa": "A", "fora": "B", "golos_casa": 1, "golos_fora": 0}] * 6
    monkeypatch.setattr(analise_mod, "buscar_jogos_terminados", lambda competicao, limite: jogos)
    monkeypatch.setattr(analise_mod, "buscar_odds", lambda desporto: [_evento("A", "B")])
    chamadas = []
    monkeypatch.setattr(analise_mod, "procurar_equipa_id", lambda nome: chamadas.append(nome) or 1)

    resultado = analisar_competicao("PL", "soccer_epl", date(2026, 9, 24), date(2026, 9, 30))
    assert chamadas == []
    assert resultado.analises[0].lesoes_casa == []


def test_analisar_competicao_com_lesoes_preenche_e_usa_cache(monkeypatch):
    jogos = [{"casa": "A", "fora": "B", "golos_casa": 1, "golos_fora": 0}] * 6
    monkeypatch.setattr(analise_mod, "buscar_jogos_terminados", lambda competicao, limite: jogos)
    monkeypatch.setattr(analise_mod, "buscar_odds", lambda desporto: [_evento("A", "B"), _evento("B", "A")])
    chamadas_id = []
    monkeypatch.setattr(analise_mod, "procurar_equipa_id", lambda nome: chamadas_id.append(nome) or 1)
    monkeypatch.setattr(analise_mod, "lesoes_recentes", lambda team_id: [{"jogador": "X", "motivo": "Y", "data": "2026-09-20"}])

    resultado = analisar_competicao("PL", "soccer_epl", date(2026, 9, 24), date(2026, 9, 30), com_lesoes=True)

    assert resultado.analises[0].lesoes_casa == [{"jogador": "X", "motivo": "Y", "data": "2026-09-20"}]
    assert resultado.analises[0].lesoes_fora == [{"jogador": "X", "motivo": "Y", "data": "2026-09-20"}]
    # A e B aparecem em ambos os jogos (casa/fora trocados) -> só 1 pedido por equipa, graças à cache
    assert sorted(chamadas_id) == ["A", "B"]


def test_analisar_competicao_erro_nas_lesoes_nao_rebenta(monkeypatch, capsys):
    jogos = [{"casa": "A", "fora": "B", "golos_casa": 1, "golos_fora": 0}] * 6
    monkeypatch.setattr(analise_mod, "buscar_jogos_terminados", lambda competicao, limite: jogos)
    monkeypatch.setattr(analise_mod, "buscar_odds", lambda desporto: [_evento("A", "B")])
    monkeypatch.setattr(analise_mod, "procurar_equipa_id", lambda nome: (_ for _ in ()).throw(RuntimeError("sem chave")))

    resultado = analisar_competicao("PL", "soccer_epl", date(2026, 9, 24), date(2026, 9, 30), com_lesoes=True)
    assert resultado.analises[0].lesoes_casa == []
    assert "sem chave" in capsys.readouterr().out
