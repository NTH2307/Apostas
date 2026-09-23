"""CLI do BettingBot: `arbitragem`, `valor` ou `live`."""
import argparse

import config
from app.arbitrage import detetar_arbitragem, detetar_valor, filtrar_bookmakers
from app.live import correr_loop
from app.odds import buscar_odds, carregar_json


def _carregar_eventos(args):
    if args.json:
        eventos = carregar_json(args.json)
    else:
        eventos = buscar_odds(args.desporto or config.DESPORTOS[0])

    bookmakers = args.bookmakers.split(",") if getattr(args, "bookmakers", None) else config.BOOKMAKERS_FIAVEIS
    return [filtrar_bookmakers(e, bookmakers) for e in eventos]


def cmd_arbitragem(args):
    eventos = _carregar_eventos(args)
    encontradas = 0
    for evento in eventos:
        arb = detetar_arbitragem(evento, margem_minima=args.margem_minima)
        if not arb:
            continue
        encontradas += 1
        stakes = arb.stakes(args.capital)
        print(f"\n{' vs '.join(arb.equipas)} — margem {arb.margem * 100:.2f}%")
        for m in arb.melhores_odds:
            print(f"  {m.resultado}: {m.odd} @ {m.bookmaker} — apostar {stakes[m.resultado]}")

    print(f"\n{encontradas} arbitragem(ns) encontrada(s) em {len(eventos)} evento(s).")
    if encontradas:
        print(
            "\n⚠️ Arbitragem teórica: ignora limites de stake por bookmaker, o "
            "tempo entre colocares as várias apostas (as odds movem-se "
            "entretanto), e o risco real de a casa limitar ou fechar contas "
            "que apostam em arbitragem de forma sistemática. Confirma sempre "
            "as odds na própria casa antes de apostar."
        )


def cmd_valor(args):
    eventos = _carregar_eventos(args)
    odd_maxima = args.odd_maxima if args.odd_maxima and args.odd_maxima > 0 else None
    total = 0
    for evento in eventos:
        for o in detetar_valor(evento, margem_minima=args.margem_minima, odd_maxima=odd_maxima):
            total += 1
            print(
                f"{' vs '.join(o.equipas)}: {o.resultado} @ {o.odd} ({o.bookmaker}) "
                f"— valor {o.valor * 100:.1f}% (prob. justa {o.probabilidade_justa * 100:.1f}%)"
            )

    print(f"\n{total} aposta(s) de valor encontrada(s) em {len(eventos)} evento(s)"
          f"{f' (odds até {odd_maxima})' if odd_maxima else ''}.")
    print(
        "\n⚠️ 'Valor' aqui é uma heurística (desvio face ao consenso do "
        "mercado após remover o overround de cada casa), não uma previsão "
        "fiável do resultado — não é garantia de lucro."
    )


def cmd_live(_args):
    correr_loop()


def main():
    parser = argparse.ArgumentParser(description="BettingBot — análise de odds desportivas (arbitragem e valor)")
    subparsers = parser.add_subparsers(dest="comando", required=True)

    def _args_comuns(p):
        p.add_argument("--json", help="ficheiro JSON local com eventos (evita precisar de ODDS_API_KEY)")
        p.add_argument("--desporto", help="chave do desporto na The Odds API, ex: soccer_epl (omissão: 1º em DESPORTOS)")
        p.add_argument(
            "--bookmakers",
            help="lista de bookmakers a considerar, separados por vírgula (omissão: BOOKMAKERS_FIAVEIS no .env, vazio = todas)",
        )

    p_arb = subparsers.add_parser("arbitragem", help="procura arbitragens (surebets) entre bookmakers")
    _args_comuns(p_arb)
    p_arb.add_argument("--margem-minima", type=float, default=config.MARGEM_MINIMA_ARBITRAGEM)
    p_arb.add_argument("--capital", type=float, default=config.CAPITAL_INICIAL)
    p_arb.set_defaults(func=cmd_arbitragem)

    p_valor = subparsers.add_parser("valor", help="procura apostas de valor (odd acima da probabilidade justa estimada)")
    _args_comuns(p_valor)
    p_valor.add_argument("--margem-minima", type=float, default=config.MARGEM_MINIMA_VALOR)
    p_valor.add_argument(
        "--odd-maxima",
        type=float,
        default=config.ODD_MAXIMA_VALOR,
        help="ignora odds acima disto — reduz falsos positivos em azarões (omissão: ODD_MAXIMA_VALOR no .env, 4.0). Usa 0 para desativar.",
    )
    p_valor.set_defaults(func=cmd_valor)

    p_live = subparsers.add_parser("live", help="corre o bot continuamente (alertas e/ou execução na Betfair)")
    p_live.set_defaults(func=cmd_live)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
