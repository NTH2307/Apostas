"""CLI do BettingBot — `python main.py apostas` é o comando principal (diz-te,
jogo a jogo, o que apostar); os restantes são ferramentas de análise."""
import argparse
import time
import webbrowser
from datetime import date, timedelta
from pathlib import Path

import config
from app.analise import analisar_competicao
from app.arbitrage import detetar_arbitragem, detetar_valor, filtrar_bookmakers
from app.live import correr_loop, resumo_diario
from app.recomendacao import chave_ordenacao
from app.relatorio import gerar_html
from app.model import avaliar_evento, encontrar_nome_equivalente
from app.odds import (
    amanha, bookmakers_em_eventos, buscar_odds, carregar_json, filtrar_por_dia, hoje,
    listar_desportos, proxima_data_com_jogos,
)
from app.poisson import golos_esperados, probabilidades
from app.stats import buscar_jogos_terminados, calcular_forcas, listar_competicoes


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


def cmd_competicoes(args):
    competicoes = listar_competicoes(args.filtro)
    if not competicoes:
        print("Nenhuma competição encontrada (ou o teu plano da football-data.org não a inclui).")
        return
    for c in competicoes:
        area = (c.get("area") or {}).get("name", "")
        print(f"{c.get('code', '?'):8s} {c.get('name', ''):40s} {area}")


def cmd_bookmakers(args):
    desportos = _resolver_desportos(args)
    eventos = []
    for desporto in desportos:
        eventos.extend(buscar_odds(desporto))
    contagens = bookmakers_em_eventos(eventos)
    if not contagens:
        print(f"Nenhum bookmaker encontrado em {len(eventos)} evento(s) — tenta outro --desporto ou outra REGIOES no .env.")
        return
    print(f"Bookmakers em {len(eventos)} evento(s) de {', '.join(desportos)} (nome exato a usar em --bookmakers/BOOKMAKERS_FIAVEIS):\n")
    for nome, n in contagens.items():
        print(f"  {nome:30s} em {n} evento(s)")


def _correr_modelo_competicao(competicao: str, desporto: str, args) -> dict:
    """Corre o modelo para UM par competição (football-data.org)/desporto
    (The Odds API), imprime os resultados, e devolve as contagens para
    somares ao total quando corres várias competições (--todas)."""
    jogos = buscar_jogos_terminados(competicao, limite=args.jogos_historico)
    forcas = calcular_forcas(jogos)
    if not forcas["equipas"]:
        print(f"\n=== {competicao} ({desporto}) === sem jogos terminados suficientes — a saltar.")
        return {"discrepancias": 0, "jogos": 0, "sem_dados": 0}
    print(f"\n=== {competicao} ({desporto}) — modelo a partir de {len(jogos)} jogos terminados ===")

    eventos_todos = buscar_odds(desporto)
    dia = date.fromisoformat(args.dia) if getattr(args, "dia", None) else (amanha() if getattr(args, "amanha", False) else None)
    if dia is None:
        # sem --dia/--amanha: por omissão mostra só a PRÓXIMA jornada (data
        # mais próxima com jogos), em vez de despejar todas as jornadas
        # futuras misturadas sem indicar a quê dia pertence cada jogo.
        dia = proxima_data_com_jogos(eventos_todos)

    eventos = filtrar_por_dia(eventos_todos, dia) if dia else eventos_todos
    if dia and not eventos:
        proxima = proxima_data_com_jogos(eventos_todos)
        if proxima:
            print(f"  sem jogos em {dia.isoformat()} — próxima data com jogos: {proxima.isoformat()} (usa --dia {proxima.isoformat()})")
        else:
            print("  sem jogos agendados de todo nesta competição, neste momento.")
        return {"discrepancias": 0, "jogos": 0, "sem_dados": 0}
    if dia:
        print(f"  a mostrar jogos de {dia.isoformat()}")

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
                  f"(equipa não encontrada nas estatísticas de '{competicao}').")
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

    return {"discrepancias": discrepancias, "jogos": len(eventos) - sem_dados, "sem_dados": sem_dados}


def cmd_modelo(args):
    if args.todas:
        pares = config.COMPETICOES_MODELO
    elif args.competicao and args.desporto:
        pares = [(args.competicao, args.desporto)]
    else:
        print("Precisas de --competicao e --desporto, ou usa --todas para correr em todas as ligas de COMPETICOES_MODELO (.env).")
        return

    total = {"discrepancias": 0, "jogos": 0, "sem_dados": 0}
    falhas = []
    for indice, (competicao, desporto) in enumerate(pares):
        if indice > 0:
            # football-data.org free tier: 10 pedidos/minuto — espaça os
            # pedidos para não estourares o limite a meio de --todas
            # (mesmo assim, buscar_jogos_terminados tem retry se acontecer).
            time.sleep(7)
        try:
            resultado = _correr_modelo_competicao(competicao, desporto, args)
        except Exception as e:
            falhas.append(f"{competicao}: {e}")
            print(f"\n=== {competicao} ({desporto}) === erro: {e}")
            continue
        total["discrepancias"] += resultado["discrepancias"]
        total["jogos"] += resultado["jogos"]
        total["sem_dados"] += resultado["sem_dados"]

    print(
        f"\n{total['discrepancias']} discrepância(s) modelo-vs-mercado (1X2) em "
        f"{total['jogos']} jogo(s) analisados em {len(pares)} competição(ões) "
        f"({total['sem_dados']} sem dados suficientes no modelo"
        + (f", {len(falhas)} competição(ões) falharam: {'; '.join(falhas)}" if falhas else "")
        + ")."
    )
    print(
        "\n⚠️ Isto é uma segunda opinião estatística (modelo de Poisson a partir de golos "
        "marcados/sofridos da época), não uma previsão garantida. 'Golos'/'ambas marcam' são "
        "só a opinião do modelo — ainda não comparados com odds reais desses mercados. O "
        "modelo pode estar errado tanto quanto o mercado, ou mais — usa para pesquisares mais, "
        "nunca como certeza."
    )


def _intervalo_datas(args) -> tuple[date, date]:
    if getattr(args, "dia", None):
        dia = date.fromisoformat(args.dia)
        return dia, dia
    if getattr(args, "amanha", False):
        return amanha(), amanha()
    inicio = hoje()
    return inicio, inicio + timedelta(days=max(args.dias, 1) - 1)


def _linha_sugestao(analise) -> str:
    s = analise.sugestao
    quando = analise.inicio.strftime("%d/%m %H:%M") if analise.inicio else "—"
    extra = f" · stake {s.stake:.2f}€" if s.tipo == "1x2" and s.stake else ""
    return (f"📅 {quando} · {analise.competicao} · {analise.casa} vs {analise.fora}\n"
            f"   🎯 {s.texto}{extra} · confiança {s.confianca}")


def cmd_apostas(args):
    if args.competicao and args.desporto:
        pares = [(args.competicao, args.desporto)]
    elif args.competicao or args.desporto:
        print("Usa --competicao e --desporto juntos (ou nenhum dos dois, para todas as competições).")
        return
    else:
        pares = config.COMPETICOES_MODELO

    inicio, fim = _intervalo_datas(args)
    bookmakers = args.bookmakers.split(",") if args.bookmakers else None
    print(f"A analisar {len(pares)} competição(ões), jogos de {inicio.strftime('%d/%m')} a {fim.strftime('%d/%m')}...")

    resultados = []
    for indice, (competicao, desporto) in enumerate(pares):
        if indice > 0:
            time.sleep(7)  # free tier da football-data.org: 10 pedidos/minuto
        try:
            resultado = analisar_competicao(
                competicao, desporto, inicio, fim, bookmakers=bookmakers,
                jogos_historico=args.jogos_historico, capital=args.capital,
            )
        except Exception as e:
            print(f"  {competicao}: erro — {e}")
            continue
        resultados.append(resultado)
        print(f"  {resultado.nome}: {len(resultado.analises)} jogo(s) analisado(s)"
              + (f", {len(resultado.sem_dados)} sem dados" if resultado.sem_dados else "")
              + (f" ({resultado.nota})" if resultado.nota else ""))

    analises = [a for r in resultados for a in r.analises]
    com_aposta = sorted((a for a in analises if a.sugestao.tipo != "nenhuma"), key=chave_ordenacao, reverse=True)

    print(f"\n=== {len(com_aposta)} aposta(s) sugerida(s) em {len(analises)} jogo(s) analisados ===\n")
    for analise in com_aposta[:args.top]:
        print(_linha_sugestao(analise) + "\n")
    if len(com_aposta) > args.top:
        print(f"(+{len(com_aposta) - args.top} sugestões no relatório)\n")

    caminho = Path(args.saida or config.RELATORIO_PATH).resolve()
    caminho.write_text(gerar_html(resultados, inicio, fim, top=args.top), encoding="utf-8")
    print(f"Relatório completo (com todos os jogos e os números): {caminho}")
    if not args.sem_browser:
        webbrowser.open(caminho.as_uri())
    print(
        "\n⚠️ Leitura estatística, não garantia: as casas têm mais informação do que este modelo "
        "(lesões, onzes, motivação). Aposta só o que estás disposto a perder."
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

    p_competicoes = subparsers.add_parser(
        "competicoes",
        help="lista os códigos de competição disponíveis na football-data.org (para usar em `modelo --competicao`)",
    )
    p_competicoes.add_argument("--filtro", help="texto a procurar no nome/código/país, ex: 'nations' ou 'portugal'")
    p_competicoes.set_defaults(func=cmd_competicoes)

    p_bookmakers = subparsers.add_parser(
        "bookmakers",
        help="lista os nomes exatos das bookmakers que aparecem nos teus dados (para confirmares antes de pores em --bookmakers/BOOKMAKERS_FIAVEIS)",
    )
    p_bookmakers.add_argument(
        "--desporto",
        help="chave(s) de desporto na The Odds API, separadas por vírgula (omissão: DESPORTOS no .env)",
    )
    p_bookmakers.set_defaults(func=cmd_bookmakers)

    p_modelo = subparsers.add_parser(
        "modelo",
        help="calcula um modelo estatístico próprio (golos marcados/sofridos, football-data.org) e compara com as odds de mercado",
    )
    p_modelo.add_argument("--competicao", help="código da competição na football-data.org, ex: PL, PD, SA, BL1, FL1, PPL, CL (omite se usares --todas)")
    p_modelo.add_argument("--desporto", help="chave da MESMA competição na The Odds API, ex: soccer_epl (omite se usares --todas)")
    p_modelo.add_argument(
        "--todas",
        action="store_true",
        help="corre o modelo em todas as ligas de COMPETICOES_MODELO (.env) de uma vez, em vez de uma competição só (só futebol — o modelo de Poisson não serve para basquetebol)",
    )
    p_modelo.add_argument(
        "--jogos-historico", type=int, default=config.MODELO_JOGOS_HISTORICO,
        help="quantos jogos terminados usar para calcular as forças (omissão: MODELO_JOGOS_HISTORICO no .env, 200)",
    )
    p_modelo.add_argument("--margem-minima", type=float, default=config.MODELO_MARGEM_MINIMA)
    p_modelo.add_argument("--bookmakers", help="lista de bookmakers a considerar, separados por vírgula (omissão: BOOKMAKERS_FIAVEIS no .env)")
    p_modelo.add_argument("--amanha", action="store_true", help="só jogos que começam amanhã, hora de Portugal")
    p_modelo.add_argument("--dia", help="só jogos neste dia, formato AAAA-MM-DD, hora de Portugal")
    p_modelo.set_defaults(func=cmd_modelo)

    p_apostas = subparsers.add_parser(
        "apostas",
        help="diz-te, jogo a jogo, o que apostar (ou que não vale a pena) e abre um relatório no browser",
    )
    p_apostas.add_argument("--competicao", help="só esta competição (código football-data.org, ex: PL) — requer --desporto")
    p_apostas.add_argument("--desporto", help="chave da mesma competição na The Odds API (ex: soccer_epl) — requer --competicao")
    p_apostas.add_argument("--dias", type=int, default=config.APOSTAS_DIAS,
                           help=f"quantos dias a partir de hoje analisar (omissão: {config.APOSTAS_DIAS})")
    p_apostas.add_argument("--amanha", action="store_true", help="só jogos de amanhã")
    p_apostas.add_argument("--dia", help="só jogos deste dia, formato AAAA-MM-DD")
    p_apostas.add_argument("--bookmakers", help="só estas casas, separadas por vírgula (omissão: BOOKMAKERS_FIAVEIS no .env)")
    p_apostas.add_argument("--capital", type=float, default=config.CAPITAL_INICIAL,
                           help="banca total, para calcular a stake sugerida (omissão: CAPITAL_INICIAL no .env)")
    p_apostas.add_argument("--top", type=int, default=10, help="quantas sugestões mostrar no topo (omissão: 10)")
    p_apostas.add_argument("--jogos-historico", type=int, default=config.MODELO_JOGOS_HISTORICO)
    p_apostas.add_argument("--saida", help="onde gravar o relatório HTML (omissão: RELATORIO_PATH, relatorio_apostas.html)")
    p_apostas.add_argument("--sem-browser", action="store_true", help="não abrir o relatório no browser automaticamente")
    p_apostas.set_defaults(func=cmd_apostas)

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
