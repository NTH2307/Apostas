"""Gera um relatório HTML autónomo (um só ficheiro, sem dependências
externas) com as sugestões de aposta, agrupadas por dia — abre-se no
browser em vez de leres tudo no PowerShell."""
from collections import defaultdict
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from app.odds import FUSO_PADRAO
from app.recomendacao import AnaliseJogo, chave_ordenacao

DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

CSS = """
:root {
  --bg: #f6f7f9; --card: #ffffff; --text: #1b1f24; --muted: #5f6b7a; --border: #e3e6eb;
  --verde: #1a7f4b; --verde-bg: #e7f5ee; --azul: #1f5fbf; --azul-bg: #e8f0fc;
  --cinza: #6b7280; --cinza-bg: #f0f1f3; --aviso: #9a5b00; --aviso-bg: #fff4e0;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #111418; --card: #1a1e24; --text: #e8eaed; --muted: #9aa4b2; --border: #2a3039;
    --verde: #5fd39a; --verde-bg: #15301f; --azul: #7fb0ff; --azul-bg: #16243a;
    --cinza: #a3aab5; --cinza-bg: #23282f; --aviso: #ffc266; --aviso-bg: #33270f;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 860px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 1.6rem; margin: 0 0 4px; }
h2 { font-size: 1.15rem; margin: 32px 0 12px; text-transform: capitalize; }
.sub { color: var(--muted); margin: 0 0 16px; }
.resumo { display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0; }
.resumo span { background: var(--card); border: 1px solid var(--border); border-radius: 999px; padding: 4px 12px; }
.top { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 4px 16px; }
.top li { padding: 10px 0; border-bottom: 1px solid var(--border); list-style: none; }
.top li:last-child { border-bottom: 0; }
.top ol { margin: 0; padding: 0; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 16px; margin-bottom: 12px; }
.meta { color: var(--muted); font-size: 0.85rem; }
.jogo { font-weight: 600; font-size: 1.05rem; margin: 2px 0 10px; }
.pick { border-radius: 8px; padding: 10px 12px; font-weight: 600; }
.pick.x1x2 { background: var(--verde-bg); color: var(--verde); }
.pick.golos { background: var(--azul-bg); color: var(--azul); }
.pick.nenhuma { background: var(--cinza-bg); color: var(--cinza); font-weight: 500; }
.pick small { display: block; font-weight: 400; color: var(--text); opacity: 0.85; margin-top: 2px; }
.badge { display: inline-block; font-size: 0.75rem; border-radius: 999px; padding: 1px 8px; margin-left: 6px;
  border: 1px solid currentColor; font-weight: 500; }
.alt { margin-top: 8px; font-size: 0.9rem; color: var(--muted); }
.aviso { background: var(--aviso-bg); color: var(--aviso); border-radius: 8px; padding: 8px 10px; margin-top: 8px; font-size: 0.88rem; }
.lesoes { margin-top: 8px; font-size: 0.85rem; color: var(--muted); }
.lesoes a { color: var(--azul); }
details { margin-top: 10px; }
summary { cursor: pointer; color: var(--muted); font-size: 0.9rem; }
table { border-collapse: collapse; width: 100%; margin-top: 8px; font-size: 0.88rem; }
th, td { text-align: right; padding: 4px 6px; border-bottom: 1px solid var(--border); }
th:first-child, td:first-child { text-align: left; }
.notas { color: var(--muted); font-size: 0.9rem; }
.notas li { margin: 4px 0; }
footer { margin-top: 40px; color: var(--muted); font-size: 0.85rem; border-top: 1px solid var(--border); padding-top: 16px; }
"""


def _data_extenso(dia) -> str:
    return f"{DIAS_SEMANA[dia.weekday()]}, {dia.day} de {MESES[dia.month - 1]}"


def _pct(p) -> str:
    return "—" if p is None else f"{p * 100:.0f}%"


def _texto_sugestao(analise: AnaliseJogo) -> str:
    s = analise.sugestao
    if s.tipo == "1x2":
        base = f"Opinião do modelo · probabilidade estimada {_pct(s.probabilidade)}"
        if s.odd is not None:
            return f"Stake sugerida: {s.stake:.2f}€ · {base} · valor vs. odd da casa {s.valor * 100:.1f}%"
        return f"{base} · sem odd desta casa para calcular stake/valor"
    if s.tipo == "golos":
        return (f"Probabilidade estimada {_pct(s.probabilidade)} — compara com a odd na tua casa; "
                f"abaixo de {s.odd_minima:.2f} não compensa")
    return "Dados insuficientes para uma opinião fiável."


def _bloco_lesoes(casa: str, fora: str, link_casa: str, link_fora: str) -> str:
    return (
        "<div class='lesoes'>Lesões/notícias de última hora: "
        f"<a href='{escape(link_casa)}' target='_blank' rel='noopener'>{escape(casa)}</a>"
        " · "
        f"<a href='{escape(link_fora)}' target='_blank' rel='noopener'>{escape(fora)}</a>"
        "</div>"
    )


def _card(analise: AnaliseJogo) -> str:
    s = analise.sugestao
    hora = analise.inicio.strftime("%H:%M") if analise.inicio else "—"
    classe = {"1x2": "x1x2", "golos": "golos"}.get(s.tipo, "nenhuma")
    prefixo = "🎯 Aposta: " if s.tipo != "nenhuma" else "⛔ "
    badge = f'<span class="badge">confiança {escape(s.confianca)}</span>' if s.tipo != "nenhuma" else ""

    alternativas = "".join(
        f'<div class="alt">Alternativa: {escape(a.texto)} <span class="badge">confiança {escape(a.confianca)}</span></div>'
        for a in analise.alternativas
    )
    avisos = "".join(f'<div class="aviso">⚠️ {escape(a)}</div>' for a in analise.avisos)
    lesoes = _bloco_lesoes(analise.casa, analise.fora, analise.link_lesoes_casa, analise.link_lesoes_fora)

    linhas_1x2 = "".join(
        f"<tr><td>{escape(rotulo)}</td><td>{_pct(analise.prob_modelo[lado])}</td>"
        f"<td>{_pct(analise.prob_mercado.get(lado))}</td><td><strong>{_pct(analise.prob_final[lado])}</strong></td></tr>"
        for lado, rotulo in (("casa", analise.casa), ("empate", "Empate"), ("fora", analise.fora))
    )
    linhas_golos = "".join(
        f"<tr><td>{escape(rotulo)}</td><td>{_pct(analise.prob_golos[chave])}</td>"
        f"<td>{1 / analise.prob_golos[chave]:.2f}</td></tr>"
        for chave, rotulo in (("over_2.5", "Mais de 2.5 golos"), ("under_2.5", "Menos de 2.5 golos"),
                              ("btts_sim", "Ambas marcam — Sim"), ("btts_nao", "Ambas marcam — Não"))
        if analise.prob_golos[chave] > 0
    )

    return f"""
<article class="card">
  <div class="meta">{hora} · {escape(analise.competicao)}</div>
  <div class="jogo">{escape(analise.casa)} vs {escape(analise.fora)}</div>
  <div class="pick {classe}">{prefixo}{escape(s.texto)}{badge}<small>{escape(_texto_sugestao(analise))}</small></div>
  {alternativas}
  {avisos}
  {lesoes}
  <details>
    <summary>Ver os números</summary>
    <p class="meta">Golos esperados (modelo): {analise.golos_esperados_casa:.2f} – {analise.golos_esperados_fora:.2f}
      · jogos na amostra da equipa com menos dados: {analise.jogos_min}</p>
    <table>
      <tr><th>Resultado</th><th>Modelo</th><th>Mercado</th><th>Final</th></tr>
      {linhas_1x2}
    </table>
    <table>
      <tr><th>Golos</th><th>Probabilidade</th><th>Odd justa</th></tr>
      {linhas_golos}
    </table>
  </details>
</article>"""


def gerar_html(resultados: list, inicio, fim, top: int = 10, gerado_em: datetime | None = None) -> str:
    """`resultados`: lista de ResultadoCompeticao (ver app/analise.py)."""
    gerado_em = gerado_em or datetime.now(ZoneInfo(FUSO_PADRAO))
    analises = [a for r in resultados for a in r.analises]
    melhores = sorted(analises, key=chave_ordenacao, reverse=True)
    confianca_alta = sum(1 for a in analises if a.sugestao.confianca == "alta")

    top_html = "".join(
        f"<li><span class='meta'>{escape(_data_extenso(a.inicio.date()) if a.inicio else '')} · "
        f"{a.inicio.strftime('%H:%M') if a.inicio else ''} · {escape(a.competicao)}</span><br>"
        f"<strong>{escape(a.casa)} vs {escape(a.fora)}</strong> → {escape(a.sugestao.texto)}"
        f"<span class='badge'>confiança {escape(a.sugestao.confianca)}</span></li>"
        for a in melhores[:top]
    ) or "<li>Nenhum jogo analisado neste período.</li>"

    por_dia = defaultdict(list)
    for a in analises:
        por_dia[a.inicio.date() if a.inicio else None].append(a)
    seccoes = ""
    for dia in sorted(por_dia, key=lambda d: (d is None, d)):
        jogos = sorted(por_dia[dia], key=lambda a: (a.inicio is None, a.inicio))
        titulo = _data_extenso(dia) if dia else "Data desconhecida"
        seccoes += f"<h2>{escape(titulo)}</h2>" + "".join(_card(a) for a in jogos)

    notas = "".join(
        f"<li><strong>{escape(r.nome)}</strong>: {escape(r.nota)}</li>" for r in resultados if r.nota
    )
    sem_dados = "".join(
        f"<li><strong>{escape(r.nome)}</strong>: {escape(', '.join(r.sem_dados))}</li>" for r in resultados if r.sem_dados
    )
    bloco_notas = ""
    if notas:
        bloco_notas += f"<h2>Competições sem jogos analisados</h2><ul class='notas'>{notas}</ul>"
    if sem_dados:
        bloco_notas += (
            "<h2>Jogos sem dados suficientes</h2><p class='notas'>Equipas que não foi possível reconhecer "
            f"nas estatísticas (nomes diferentes entre as duas fontes, ou equipa recém-chegada):</p>"
            f"<ul class='notas'>{sem_dados}</ul>"
        )

    periodo = inicio.strftime("%d/%m") if inicio == fim else f"{inicio.strftime('%d/%m')} a {fim.strftime('%d/%m')}"
    return f"""<!DOCTYPE html>
<html lang="pt-PT">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Apostas do dia</title>
<style>{CSS}</style>
</head>
<body>
<main>
  <h1>Apostas do dia</h1>
  <p class="sub">Jogos de {periodo} · gerado em {gerado_em.strftime('%d/%m/%Y às %H:%M')}</p>
  <div class="resumo">
    <span>{len(analises)} jogos analisados</span>
    <span>{confianca_alta} com confiança alta</span>
  </div>
  <h2>Os palpites mais fortes</h2>
  <div class="top"><ol>{top_html}</ol></div>
  {seccoes}
  {bloco_notas}
  <footer>
    <p><strong>Como ler isto.</strong> O palpite no resultado (verde) é sempre a opinião do modelo — o lado que ele
    acha mais provável, não uma comparação de valor com a casa de apostas; a odd aparece só como referência, quando
    existe. "Aposta" em golos (azul) diz-te a odd mínima a partir da qual compensa — confirma-a na tua casa.
    A confiança depende de quantos jogos há na amostra de cada equipa.</p>
    <p>⚠️ Isto é uma leitura estatística, não uma garantia: mesmo as sugestões de confiança alta perdem muitas vezes, e as
    casas de apostas têm mais informação do que este modelo (lesões, onzes, motivação). Aposta só o que estás disposto a
    perder. Se o jogo deixar de ser diversão, procura ajuda em <a href="https://www.sicad.pt">sicad.pt</a>.</p>
    <p>⚠️ Os links de "lesões/notícias de última hora" são só atalhos de pesquisa — não entram no cálculo das
    probabilidades. Confirma sempre antes do jogo, sobretudo perto da hora do apito inicial.</p>
  </footer>
</main>
</body>
</html>
"""
