"""Loop live: a cada N segundos, busca odds dos desportos configurados,
procura arbitragens e apostas de valor, notifica sempre, e executa
(só Betfair — ver app/executor.py) se EXECUCAO_AUTOMATICA=true.
"""
import time

import config
from app.arbitrage import detetar_arbitragem, detetar_valor, filtrar_bookmakers
from app.executor import executar_aposta
from app.notifier import enviar_alerta
from app.odds import buscar_odds


def verificar_uma_vez(desporto: str) -> dict:
    eventos = buscar_odds(desporto)
    eventos = [filtrar_bookmakers(e, config.BOOKMAKERS_FIAVEIS) for e in eventos]
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

        odd_maxima = config.ODD_MAXIMA_VALOR if config.ODD_MAXIMA_VALOR > 0 else None
        for oportunidade in detetar_valor(evento, margem_minima=config.MARGEM_MINIMA_VALOR, odd_maxima=odd_maxima):
            resumo["valores"] += 1
            enviar_alerta(
                f"📈 VALOR {oportunidade.valor * 100:.1f}% — {' vs '.join(oportunidade.equipas)}: "
                f"{oportunidade.resultado} @ {oportunidade.odd} ({oportunidade.bookmaker}, "
                f"prob. justa {oportunidade.probabilidade_justa * 100:.1f}%)"
            )

    return resumo


def resumo_diario(desportos: list | None = None) -> dict:
    """Corre UMA verificação (não contínua) sobre `desportos` (omissão:
    DESPORTOS no .env), e envia sempre um resumo por Telegram no fim —
    mesmo "sem oportunidades hoje" — para saberes que a verificação correu
    e não ficares às escuras. Pensado para correr uma vez por dia (ex: via
    Agendador de Tarefas do Windows), ao contrário de `correr_loop`, que
    corre para sempre.

    Uma competição sem dados (chave errada, API em baixo, etc.) não pára as
    restantes — fica só registada na secção de erros do resumo.
    """
    desportos = desportos or config.DESPORTOS
    totais = {"arbitragens": 0, "valores": 0, "erros": []}

    for desporto in desportos:
        try:
            resumo = verificar_uma_vez(desporto)
            totais["arbitragens"] += resumo["arbitragens"]
            totais["valores"] += resumo["valores"]
        except Exception as e:
            totais["erros"].append(f"{desporto}: {e}")

    if totais["arbitragens"] or totais["valores"]:
        texto = (
            f"📋 Resumo diário: {totais['arbitragens']} arbitragem(ns) e "
            f"{totais['valores']} aposta(s) de valor encontradas em "
            f"{len(desportos)} competição(ões) — ver mensagens acima."
        )
    else:
        texto = (
            f"📋 Resumo diário: nada encontrado hoje em {len(desportos)} "
            f"competição(ões). Mercado eficiente hoje, sem vantagem clara."
        )
    if totais["erros"]:
        texto += "\n⚠️ Falhou a verificar: " + "; ".join(totais["erros"])

    enviar_alerta(texto)
    print(texto)
    return totais


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
