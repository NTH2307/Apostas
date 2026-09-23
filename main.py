"""CLI do BettingBot: `arbitragem`, `valor`, `desportos` ou `live`."""
import argparse
from datetime import date

import config
from app.arbitrage import detetar_arbitragem, detetar_valor, filtrar_bookmakers
from app.live import correr_loop, resumo_diario
from app.odds import amanha, buscar_odds, carregar_json, filtrar_por_dia, listar_desportos


def _resolver_desportos(args) -> list:
    if args.desporto:
        return [d.strip() for d in args.desporto.split(",") if d.strip()]
    return config.DESPORTOS


def _carregar_eventos(args):
    if args.json:
        eventos = carregar_json(args.json)
    else:
        eventos = []
        for desporto in _resolver_desportos(args):
            eventos.extend(buscar_odds(desporto))

    bookmakers = args.bookmakers.split(",") if getattr(args, "bookmakers", None) else config.BOOKMAKERS_FIAVEIS
    eventos = [filtrar_bookmakers(e, bookmakers) for e in eventos]

    dia = None
    if getattr(args, "dia", None):
        dia = date.fromisoformat(args.dia)
    elif getattr(args, "amanha", False):
        dia = amanha()
    if dia:
        eventos = filtrar_por_dia(eventos, dia)

    return eventos


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


def cmd_desportos(args):
    for d in listar_desportos(args.filtro):
        estado = "" if d.get("active", True) else "  (inativo)"
        print(f"{d['key']:40s} {d.get('title', '')}{estado}")


def cmd_resumo(_args):
    resumo_diario()


def cmd_live(_args):
    correr_loop()


def main():
    parser = argparse.ArgumentParser(description="BettingBot — análise de odds desportivas (arbitragem e valor)")
    subparsers = parser.add_subparsers(dest="comando", required=True)

    def _args_comuns(p):
        p.add_argument("--json", help="ficheiro JSON local com eventos (evita precisar de ODDS_API_KEY)")
        p.add_argument(
            "--desporto",
            help="chave(s) de desporto na The Odds API, separadas por vírgula, ex: soccer_epl,basketball_nba "
                 "(omissão: DESPORTOS no .env). Usa `python main.py desportos` para veres as chaves disponíveis.",
        )
        p.add_argument(
            "--bookmakers",
            help="lista de bookmakers a considerar, separados por vírgula (omissão: BOOKMAKERS_FIAVEIS no .env, vazio = todas)",
        )
        p.add_argument(
            "--amanha",
            action="store_true",
            help="só jogos que começam amanhã, hora de Portugal (ignorado se usares --dia)",
        )
        p.add_argument("--dia", help="só jogos neste dia, formato AAAA-MM-DD, hora de Portugal")

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

    p_desportos = subparsers.add_parser("desportos", help="lista as chaves de desporto/competição disponíveis na The Odds API")
    p_desportos.add_argument("--filtro", help="texto a procurar na chave/título/descrição, ex: 'nations' ou 'portugal'")
    p_desportos.set_defaults(func=cmd_desportos)

    p_resumo = subparsers.add_parser(
        "resumo",
        help="corre UMA verificação sobre DESPORTOS (.env) e envia sempre um resumo por Telegram — pensado para correr 1x/dia via agendador",
    )
    p_resumo.set_defaults(func=cmd_resumo)

    p_live = subparsers.add_parser("live", help="corre o bot continuamente (alertas e/ou execução na Betfair)")
    p_live.set_defaults(func=cmd_live)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
