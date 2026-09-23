"""Cliente Betfair Exchange — a única casa de apostas com API pública para
apostar por programa (as casas de odds fixas normais proíbem bots nos
termos de serviço e podem fechar a conta). Requer o pacote opcional
`betfairlightweight` e uma conta Betfair com App Key + certificados
(ver README, secção "Execução automática (Betfair Exchange)").
"""
import config


def criar_sessao():
    """Cria e autentica um cliente betfairlightweight a partir das
    credenciais no .env. Nunca falha em silêncio: lança ImportError se
    faltar a dependência, ou RuntimeError se faltarem credenciais."""
    try:
        import betfairlightweight
    except ImportError as e:
        raise ImportError(
            "betfairlightweight não instalado — corre "
            "`pip install betfairlightweight` para usar execução real na Betfair."
        ) from e

    if not (config.BETFAIR_APP_KEY and config.BETFAIR_USERNAME and config.BETFAIR_PASSWORD):
        raise RuntimeError(
            "Credenciais Betfair em falta — define BETFAIR_APP_KEY, "
            "BETFAIR_USERNAME, BETFAIR_PASSWORD e BETFAIR_CERTS_DIR no .env "
            "(ver README para como obter a App Key e gerar os certificados)."
        )

    trading = betfairlightweight.APIClient(
        username=config.BETFAIR_USERNAME,
        password=config.BETFAIR_PASSWORD,
        app_key=config.BETFAIR_APP_KEY,
        certs=config.BETFAIR_CERTS_DIR or None,
    )
    trading.login()
    return trading


def apostar(trading, market_id: str, selection_id: int, odd: float, stake: float, lado: str = "BACK") -> dict:
    """Coloca uma ordem limite na Betfair Exchange. lado: 'BACK' (apostar a
    favor) ou 'LAY' (apostar contra, só possível na Exchange)."""
    from betfairlightweight import filters

    instrucao = filters.place_instruction(
        order_type="LIMIT",
        selection_id=selection_id,
        side=lado,
        limit_order=filters.limit_order(size=stake, price=odd, persistence_type="LAPSE"),
    )
    resposta = trading.betting.place_orders(market_id=market_id, instructions=[instrucao])
    return resposta._data if hasattr(resposta, "_data") else resposta
