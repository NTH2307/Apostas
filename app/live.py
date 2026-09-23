"""Loop live: a cada N segundos, busca odds dos desportos configurados,
procura arbitragens e apostas de valor, notifica sempre, e executa
(só Betfair — ver app/executor.py) se EXECUCAO_AUTOMATICA=true.
"""
import time

import config
from app.arbitrage import detetar_arbitragem, detetar_valor
from app.executor import executar_aposta
from app.notifier import enviar_alerta
from app.odds import buscar_odds


def verificar_uma_vez(desporto: str) -> dict:
    eventos = buscar_odds(desporto)
    resumo = {"arbitragens": 0, "valores": 0}

    for evento in eventos:
        arb = detetar_arbitragem(evento, margem_minima=config.MARGEM_MINIMA_ARBITRAGEM)
        if arb:
            resumo["arbitragens"] += 1
            stakes = arb.stakes(config.CAPITAL_INICIAL)
            texto = " | ".join(
                f"{m.resultado} @ {m.odd} ({m.bookmaker}, stake {stakes[m.resultado]})"
                for m in arb.melhores_odds
            )
            enviar_alerta(f"💰 ARBITRAGEM {arb.margem * 100:.2f}% — {' vs '.join(arb.equipas)}: {texto}")
            for m in arb.melhores_odds:
                executar_aposta(m.bookmaker, m.resultado, m.odd, stakes[m.resultado])

        for oportunidade in detetar_valor(evento, margem_minima=config.MARGEM_MINIMA_VALOR):
            resumo["valores"] += 1
            enviar_alerta(
                f"📈 VALOR {oportunidade.valor * 100:.1f}% — {' vs '.join(oportunidade.equipas)}: "
                f"{oportunidade.resultado} @ {oportunidade.odd} ({oportunidade.bookmaker}, "
                f"prob. justa {oportunidade.probabilidade_justa * 100:.1f}%)"
            )

    return resumo


def correr_loop():
    print(
        f"BettingBot em modo live: {', '.join(config.DESPORTOS)} "
        f"(execução automática: {config.EXECUCAO_AUTOMATICA and not config.MODO_PAPER}, só Betfair)"
    )
    while True:
        for desporto in config.DESPORTOS:
            try:
                resumo = verificar_uma_vez(desporto)
                print(f"{desporto}: {resumo['arbitragens']} arbitragens, {resumo['valores']} apostas de valor")
            except Exception as e:
                print(f"Erro ao verificar {desporto}: {e}")
        time.sleep(config.INTERVALO_VERIFICACAO_SEGUNDOS)
