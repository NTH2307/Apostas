import json
import os

from app.odds import carregar_json


def test_carregar_json_com_formato_ja_normalizado(tmp_path):
    caminho = tmp_path / "eventos.json"
    caminho.write_text(json.dumps([
        {
            "id": "e1",
            "desporto": "soccer_epl",
            "hora_inicio": "2026-01-01T00:00:00Z",
            "equipas": ["A", "B"],
            "bookmakers": {"Casa X": {"A": 1.9, "B": 2.0}},
        }
    ]))
    eventos = carregar_json(str(caminho))
    assert eventos[0]["bookmakers"]["Casa X"]["A"] == 1.9


def test_carregar_json_com_formato_bruto_the_odds_api(tmp_path):
    caminho = tmp_path / "eventos_brutos.json"
    caminho.write_text(json.dumps([
        {
            "id": "e2",
            "sport_key": "soccer_epl",
            "commence_time": "2026-01-01T00:00:00Z",
            "home_team": "Time A",
            "away_team": "Time B",
            "bookmakers": [
                {
                    "key": "casax",
                    "title": "Casa X",
                    "markets": [
                        {"key": "h2h", "outcomes": [
                            {"name": "Time A", "price": 1.9},
                            {"name": "Time B", "price": 2.0},
                        ]}
                    ],
                }
            ],
        }
    ]))
    eventos = carregar_json(str(caminho))
    evento = eventos[0]
    assert evento["equipas"] == ["Time A", "Time B"]
    assert evento["bookmakers"]["Casa X"]["Time A"] == 1.9
    assert evento["desporto"] == "soccer_epl"


def test_exemplo_incluido_no_repo_carrega_sem_erros():
    caminho = os.path.join(os.path.dirname(__file__), "..", "data", "exemplo_odds.json")
    eventos = carregar_json(caminho)
    assert len(eventos) == 3
    assert all("bookmakers" in e for e in eventos)
