"""CLI do BettingBot: `arbitragem`, `valor`, `desportos` ou `live`."""
import argparse
from datetime import date

import config
from app.arbitrage import detetar_arbitragem, detetar_valor, filtrar_bookmakers
from app.live import correr_loop, resumo_diario
from app.model import avaliar_evento, encontrar_nome_equivalente
from app.odds import amanha, buscar_odds, carregar_json, filtrar_por_dia, listar_desportos
from app.poisson import golos_esperados, probabilidades
from app.stats import buscar_jogos_terminados, calcular_forcas


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


def cmd_modelo(args):
    try:
        jogos = buscar_jogos_terminados(args.competicao, limite=args.jogos_historico)
    except Exception as e:
        print(f"Erro a obter estatísticas para '{args.competicao}': {e}")
        return
    forcas = calcular_forcas(jogos)
    if not forcas["equipas"]:
        print(f"Sem jogos terminados suficientes para '{args.competicao}' — não dá para calcular o modelo.")
        return
    print(f"Modelo calculado a partir de {len(jogos)} jogos terminados de '{args.competicao}'.")

    eventos = buscar_odds(args.desporto)
    dia = date.fromisoformat(args.dia) if getattr(args, "dia", None) else (amanha() if getattr(args, "amanha", False) else None)
    if dia:
        eventos = filtrar_por_dia(eventos, dia)
    bookmakers = args.bookmakers.split(",") if getattr(args, "bookmakers", None) else config.BOOKMAKERS_FIAVEIS
    eventos = [filtrar_bookmakers(e, bookmakers) for e in eventos]

    sem_dados = 0
    discrepancias = 0
    for evento in eventos:
        casa_nome, fora_nome = evento["equipas"]
        casa_equiv = encontrar_nome_equivalente(casa_nome, forcas["equipas"])
        fora_equiv = encontrar_nome_equivalente(fora_nome, forcas["equipas"])
        if not casa_equiv or not fora_equiv:
            print(f"\n{casa_nome} vs {fora_nome}: sem dados suficientes no modelo "
                  f"(equipa não encontrada nas estatísticas de '{args.competicao}').")
            sem_dados += 1
            continue

        lambda_casa, lambda_fora = golos_esperados(forcas, casa_equiv, fora_equiv)
        probs = probabilidades(lambda_casa, lambda_fora)
        nomes_por_lado = {"casa": casa_nome, "empate": "empate", "fora": fora_nome}
        lado_favorito = max(("casa", "empate", "fora"), key=lambda lado: probs[lado])

        print(
            f"\n{casa_nome} vs {fora_nome} — modelo: {lambda_casa:.2f}-{lambda_fora:.2f} golos esperados\n"
            f"  1X2 modelo: casa {probs['casa'] * 100:.0f}% empate {probs['empate'] * 100:.0f}% "
            f"fora {probs['fora'] * 100:.0f}% (favorito do modelo: {nomes_por_lado[lado_favorito]})\n"
            f"  Golos: over 2.5 {probs['over_2.5'] * 100:.0f}% / under 2.5 {probs['under_2.5'] * 100:.0f}% "
            f"| Ambas marcam: sim {probs['btts_sim'] * 100:.0f}% / não {probs['btts_nao'] * 100:.0f}%"
        )

        oportunidades = avaliar_evento(evento, forcas, margem_minima=args.margem_minima)
        discrepancias += len(oportunidades)
        for o in oportunidades:
            print(
                f"  💡 mercado paga mais do que o modelo acha justo: {o.resultado} @ {o.odd} ({o.bookmaker}) "
                f"— modelo dá {o.probabilidade_modelo * 100:.0f}% (valor {o.valor * 100:.1f}%)"
            )

    print(
        f"\n{discrepancias} discrepância(s) modelo-vs-mercado (1X2) em "
        f"{len(eventos) - sem_dados} jogo(s) analisados ({sem_dados} sem dados suficientes no modelo)."
    )
    print(
        "\n⚠️ Isto é uma segunda opinião estatística (modelo de Poisson a partir de golos "
        "marcados/sofridos da época), não uma previsão garantida. 'Golos'/'ambas marcam' são "
        "só a opinião do modelo — ainda não comparados com odds reais desses mercados. O "
        "modelo pode estar errado tanto quanto o mercado, ou mais — usa para pesquisares mais, "
        "nunca como certeza."
    )


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

    p_modelo = subparsers.add_parser(
        "modelo",
        help="calcula um modelo estatístico próprio (golos marcados/sofridos, football-data.org) e compara com as odds de mercado",
    )
    p_modelo.add_argument("--competicao", required=True, help="código da competição na football-data.org, ex: PL, PD, SA, BL1, FL1, PPL, CL")
    p_modelo.add_argument("--desporto", required=True, help="chave da MESMA competição na The Odds API, ex: soccer_epl")
    p_modelo.add_argument(
        "--jogos-historico", type=int, default=config.MODELO_JOGOS_HISTORICO,
        help="quantos jogos terminados usar para calcular as forças (omissão: MODELO_JOGOS_HISTORICO no .env, 200)",
    )
    p_modelo.add_argument("--margem-minima", type=float, default=config.MODELO_MARGEM_MINIMA)
    p_modelo.add_argument("--bookmakers", help="lista de bookmakers a considerar, separados por vírgula (omissão: BOOKMAKERS_FIAVEIS no .env)")
    p_modelo.add_argument("--amanha", action="store_true", help="só jogos que começam amanhã, hora de Portugal")
    p_modelo.add_argument("--dia", help="só jogos neste dia, formato AAAA-MM-DD, hora de Portugal")
    p_modelo.set_defaults(func=cmd_modelo)

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
