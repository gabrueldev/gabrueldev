#!/usr/bin/env python3
"""Gera um SVG animado com o gráfico de contribuições do GitHub.

Uso:
    GITHUB_TOKEN=... python scripts/contrib_heatmap.py gabrueldev contrib-heatmap.svg
    python scripts/contrib_heatmap.py gabrueldev preview.svg --sample   # dados fictícios

Sem dependências externas: só a biblioteca padrão do Python.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import sys
import urllib.request
from html import escape

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            weekday
            contributionCount
            contributionLevel
          }
        }
      }
    }
  }
}
"""

LEVELS = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}

# Paleta verde do tema escuro do GitHub
COLORS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]

MONTHS_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
             "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def fetch_calendar(login: str, token: str) -> tuple[int, list[list[dict]]]:
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{login}-contrib-heatmap",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if data.get("errors"):
        raise SystemExit(f"Erro da API do GitHub: {data['errors']}")
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = [
        [
            {
                "date": d["date"],
                "weekday": d["weekday"],
                "count": d["contributionCount"],
                "level": LEVELS.get(d["contributionLevel"], 0),
            }
            for d in w["contributionDays"]
        ]
        for w in cal["weeks"]
    ]
    return cal["totalContributions"], weeks


def sample_calendar() -> tuple[int, list[list[dict]]]:
    """Dados fictícios só para pré-visualizar o visual."""
    rng = random.Random(7)
    today = dt.date.today()
    start = today - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)  # volta para domingo
    weeks, week, total = [], [], 0
    day = start
    while day <= today:
        busy = 0.35 + 0.5 * (day - start).days / 365
        count = 0 if rng.random() > busy else rng.choice([1, 2, 3, 4, 6, 8, 12, 18])
        level = 0 if count == 0 else 1 if count < 3 else 2 if count < 6 else 3 if count < 12 else 4
        total += count
        week.append({"date": day.isoformat(), "weekday": (day.weekday() + 1) % 7,
                     "count": count, "level": level})
        if len(week) == 7:
            weeks.append(week)
            week = []
        day += dt.timedelta(days=1)
    if week:
        weeks.append(week)
    return total, weeks


def build_svg(login: str, total: int, weeks: list[list[dict]]) -> str:
    cell, gap = 11, 3
    step = cell + gap
    pad_x, pad_top = 24, 74
    label_w = 30
    grid_x = pad_x + label_w
    grid_y = pad_top + 18
    n_weeks = len(weeks)
    width = grid_x + n_weeks * step - gap + pad_x
    height = grid_y + 7 * step - gap + 56

    sweep = 2.2  # segundos para a onda atravessar o gráfico
    delay_per_week = sweep / max(n_weeks, 1)

    out: list[str] = []
    a = out.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
      f'viewBox="0 0 {width} {height}" role="img" '
      f'aria-label="{total} contribuições no último ano">')
    a("<style>")
    a("""
  .bg { fill: #0d1117; stroke: #30363d; }
  .dot { opacity: .9; }
  .cmd { font: 600 14px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: #e6edf3; }
  .prompt { fill: #39d353; }
  .lbl { font: 10px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: #7d8590; }
  .total { font: 600 12px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: #e6edf3;
           opacity: 0; animation: fade .6s ease-out forwards; }
  .total b, .num { fill: #39d353; }
  .c { opacity: 0; transform-box: fill-box; transform-origin: center;
       animation: pop .45s cubic-bezier(.2,1.6,.4,1) forwards; }
  .c.l4 { animation-name: pop, glow; animation-duration: .45s, 2.4s;
          animation-iteration-count: 1, infinite; animation-direction: normal, alternate; }
  .cursor { fill: #39d353; animation: blink 1s steps(1) infinite; }
  @keyframes pop { 0% { opacity: 0; transform: scale(.2); } 100% { opacity: 1; transform: scale(1); } }
  @keyframes glow { from { opacity: 1; } to { opacity: .7; } }
  @keyframes fade { to { opacity: 1; } }
  @keyframes blink { 50% { opacity: 0; } }
  @media (prefers-reduced-motion: reduce) {
    .c, .total { animation: none; opacity: 1; }
  }
""")
    a("</style>")

    # Moldura estilo terminal
    a(f'<rect class="bg" x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="10"/>')
    for i, color in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        a(f'<circle class="dot" cx="{20 + i * 16}" cy="18" r="5" fill="{color}"/>')
    a(f'<line x1="0" y1="34" x2="{width}" y2="34" stroke="#30363d"/>')

    # Comando sendo "digitado"
    command = "./contributions.sh"
    prefix = f"{login}@github ~ $ "
    char_w = 8.43  # largura aproximada de um caractere monoespaçado a 14px
    cmd_x = pad_x
    cmd_y = 58
    typed_w = len(command) * char_w
    prefix_w = len(prefix) * char_w
    type_dur = 0.06 * len(command)
    a('<defs><clipPath id="type">')
    a(f'<rect x="{cmd_x + prefix_w:.1f}" y="{cmd_y - 16}" width="0" height="22">'
      f'<animate attributeName="width" from="0" to="{typed_w:.1f}" begin="0.3s" '
      f'dur="{type_dur:.2f}s" fill="freeze" calcMode="discrete" '
      f'values="{";".join(f"{i * char_w:.1f}" for i in range(len(command) + 1))}"/></rect>')
    a('</clipPath></defs>')
    a(f'<text class="cmd" x="{cmd_x}" y="{cmd_y}"><tspan class="prompt">{escape(prefix)}</tspan></text>')
    a(f'<text class="cmd" x="{cmd_x + prefix_w:.1f}" y="{cmd_y}" clip-path="url(#type)">{command}</text>')
    cursor_x0 = cmd_x + prefix_w
    a(f'<rect class="cursor" x="{cursor_x0:.1f}" y="{cmd_y - 12}" width="8" height="15">'
      f'<animate attributeName="x" begin="0.3s" dur="{type_dur:.2f}s" fill="freeze" calcMode="discrete" '
      f'values="{";".join(f"{cursor_x0 + i * char_w:.1f}" for i in range(len(command) + 1))}"/></rect>')

    grid_start = 0.3 + type_dur + 0.2

    # Rótulos dos meses
    last_month = None
    for wi, week in enumerate(weeks):
        first = dt.date.fromisoformat(week[0]["date"])
        if last_month is not None and first.month != last_month and wi < n_weeks - 2:
            a(f'<text class="lbl" x="{grid_x + wi * step}" y="{grid_y - 6}">{MONTHS_PT[first.month - 1]}</text>')
        last_month = first.month

    # Rótulos dos dias
    for row, name in ((1, "Seg"), (3, "Qua"), (5, "Sex")):
        a(f'<text class="lbl" x="{pad_x}" y="{grid_y + row * step + cell - 2}">{name}</text>')

    # Quadradinhos
    for wi, week in enumerate(weeks):
        for day in week:
            row = day["weekday"]
            delay = grid_start + wi * delay_per_week + row * 0.035
            lvl = day["level"]
            cls = "c l4" if lvl == 4 else "c"
            plural = "contribuição" if day["count"] == 1 else "contribuições"
            a(f'<rect class="{cls}" x="{grid_x + wi * step}" y="{grid_y + row * step}" '
              f'width="{cell}" height="{cell}" rx="2" fill="{COLORS[lvl]}" '
              f'style="animation-delay:{delay:.2f}s{"," + f"{delay + 0.45:.2f}s" if lvl == 4 else ""}">'
              f'<title>{day["date"]}: {day["count"]} {plural}</title></rect>')

    # Total + legenda
    end = grid_start + sweep + 0.3
    base_y = grid_y + 7 * step - gap + 30
    total_fmt = f"{total:,}".replace(",", ".")
    a(f'<text class="total" x="{grid_x}" y="{base_y}" style="animation-delay:{end:.2f}s">'
      f'<tspan class="num">{total_fmt}</tspan> contribuições no último ano</text>')
    lx = width - pad_x - 5 * step - 62
    a(f'<text class="lbl" x="{lx}" y="{base_y}">Menos</text>')
    for i, color in enumerate(COLORS):
        a(f'<rect x="{lx + 36 + i * step}" y="{base_y - 10}" width="{cell}" height="{cell}" rx="2" fill="{color}"/>')
    a(f'<text class="lbl" x="{lx + 36 + 5 * step + 4}" y="{base_y}">Mais</text>')

    a("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("login")
    parser.add_argument("output")
    parser.add_argument("--sample", action="store_true", help="usa dados fictícios")
    args = parser.parse_args()

    if args.sample:
        total, weeks = sample_calendar()
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            sys.exit("Defina GITHUB_TOKEN (ou use --sample).")
        total, weeks = fetch_calendar(args.login, token)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(build_svg(args.login, total, weeks))
    print(f"{args.output}: {total} contribuições, {len(weeks)} semanas")


if __name__ == "__main__":
    main()
