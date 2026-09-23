"""Execução de apostas. Por omissão em modo paper (simulado) — só liga
EXECUCAO_AUTOMATICA no config depois de validares bem a estratégia.

Mesmo com EXECUCAO_AUTOMATICA=true, só apostas identificadas como "Betfair"
são executadas de facto — é a única casa com API pública para apostar por
programa. Apostas noutras bookmakers ficam sempre em modo paper/registo
manual, porque essas casas não oferecem API de execução (e apostar por bot
nelas viola normalmente os termos de serviço).
"""
import config


def executar_aposta(
    bookmaker: str,
    resultado: str,
    odd: float,
    stake: float,
    market_id: str | None = None,
    selection_id: int | None = None,
) -> dict:
    registo_base = {
        "bookmaker": bookmaker,
        "resultado": resultado,
        "odd": odd,
        "stake": stake,
    }

    pode_executar_real = (
        config.EXECUCAO_AUTOMATICA
        and not config.MODO_PAPER
        and bookmaker.strip().lower() == "betfair"
        and market_id is not None
        and selection_id is not None
    )

    if not pode_executar_real:
        if bookmaker.strip().lower() != "betfair" and config.EXECUCAO_AUTOMATICA and not config.MODO_PAPER:
            motivo = "sem API de execução"
        else:
            motivo = "paper"
        registo = {**registo_base, "modo": motivo}
        print(f"[PAPER] Aposta simulada ({motivo}): {registo}")
        return registo

    from app.betfair_client import apostar, criar_sessao

    trading = criar_sessao()
    resposta = apostar(trading, market_id, selection_id, odd, stake)
    registo = {**registo_base, "modo": "real", "resposta_betfair": resposta}
    print(f"[REAL] Aposta executada na Betfair: {registo}")
    return registo
