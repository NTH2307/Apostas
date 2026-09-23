from app.model import avaliar_evento, encontrar_nome_equivalente, normalizar_nome_equipa


def test_normalizar_nome_equipa_remove_sufixos_e_prefixos_comuns():
    assert normalizar_nome_equipa("Arsenal FC") == "arsenal"
    assert normalizar_nome_equipa("FC Barcelona") == "barcelona"
    assert normalizar_nome_equipa("AFC Bournemouth") == "bournemouth"
    assert normalizar_nome_equipa("Sporting CP") == "sporting"
    assert normalizar_nome_equipa("Manchester City") == "manchester city"


def test_normalizar_nome_equipa_remove_acentos_e_pontuacao():
    assert normalizar_nome_equipa("1. FC Köln") == "koln"
    assert normalizar_nome_equipa("Deportivo La Coruña") == "deportivo la coruna"


def test_encontrar_nome_equivalente_ignora_sufixo_e_maiusculas():
    disponiveis = ["Arsenal FC", "Chelsea FC", "Manchester City FC"]
    assert encontrar_nome_equivalente("Arsenal", disponiveis) == "Arsenal FC"
    assert encontrar_nome_equivalente("arsenal", disponiveis) == "Arsenal FC"


def test_encontrar_nome_equivalente_sem_correspondencia():
    assert encontrar_nome_equivalente("Benfica", ["Arsenal FC"]) is None


def _evento(equipas, bookmakers):
    return {"id": "e1", "desporto": "teste", "hora_inicio": "", "equipas": equipas, "bookmakers": bookmakers}


def test_avaliar_evento_sem_dados_do_modelo_devolve_vazio():
    forcas = {"media_golos_casa": 1.5, "media_golos_fora": 1.2, "equipas": {}}
    evento = _evento(["Time A", "Time B"], {"Casa X": {"Time A": 1.9, "Draw": 3.4, "Time B": 4.0}})
    assert avaliar_evento(evento, forcas) == []


def test_avaliar_evento_deteta_discrepancia_quando_modelo_favorece_muito_a_casa():
    forcas = {
        "media_golos_casa": 1.5, "media_golos_fora": 1.2,
        "equipas": {
            "Time A FC": {"ataque_casa": 2.0, "defesa_casa": 0.5, "ataque_fora": 1.8, "defesa_fora": 0.6},
            "Time B FC": {"ataque_casa": 0.5, "defesa_casa": 1.8, "ataque_fora": 0.4, "defesa_fora": 2.0},
        },
    }
    # odds "normais" (a favorecerem pouco a casa) mas o modelo acha a casa MUITO mais forte
    evento = _evento(
        ["Time A", "Time B"],
        {"Casa X": {"Time A": 2.0, "Draw": 3.3, "Time B": 3.6}},
    )
    oportunidades = avaliar_evento(evento, forcas, margem_minima=0.05)
    assert any(o.resultado == "Time A" for o in oportunidades)


def test_avaliar_evento_sem_discrepancia_quando_modelo_concorda_com_mercado():
    forcas = {
        "media_golos_casa": 1.4, "media_golos_fora": 1.1,
        "equipas": {
            "Time A FC": {"ataque_casa": 1.0, "defesa_casa": 1.0, "ataque_fora": 1.0, "defesa_fora": 1.0},
            "Time B FC": {"ataque_casa": 1.0, "defesa_casa": 1.0, "ataque_fora": 1.0, "defesa_fora": 1.0},
        },
    }
    evento = _evento(
        ["Time A", "Time B"],
        {"Casa X": {"Time A": 2.6, "Draw": 3.1, "Time B": 2.7}},
    )
    # equipas neutras -> modelo dá probabilidade parecida com o mercado, sem discrepância grande
    oportunidades = avaliar_evento(evento, forcas, margem_minima=0.2)
    assert oportunidades == []
