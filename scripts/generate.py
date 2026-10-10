import io
import os
import re
from datetime import date
from html import escape
from pathlib import Path

import cv2
import numpy as np
import requests
from bs4 import BeautifulSoup
from PIL import Image

USER = "danbenba"
AVATAR = "https://danbenba.dev/profile.png"
OUT = Path(__file__).resolve().parent.parent / "assets"
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
BG = "#0d1117"
BORDER = "#30363d"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
ACCENT = "#4C8DFF"
DENSE = " .:-=+*o#%@"
EXCLUDED_LANG_REPOS = {"PassGen", "UnderGame"}
LANG_COLORS = {
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "C#": "#178600", "Java": "#b07219",
    "CSS": "#663399", "HTML": "#e34c26", "Python": "#3572A5", "Batchfile": "#C1F12E",
    "Shell": "#89e051", "Visual Basic .NET": "#945db7", "Rust": "#dea584", "C": "#555555",
    "C++": "#f34b7d", "Astro": "#ff5a03", "PHP": "#4F5D95", "Kotlin": "#A97BFF", "Go": "#00ADD8",
    "Dockerfile": "#384d54", "MDX": "#fcb32c", "Vue": "#41b883", "Svelte": "#ff3e00",
}
HEAT = ["#161b22", "#0c2d6b", "#1a4fa8", "#2f6fe0", "#4c8dff", "#a5c8ff"]

COLS, ROWS = 96, 50
CHAR_W, CHAR_H = 3.75, 6.72
CARD_W, CARD_H = 470, 370


def frame(w, h, title):
    return (
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" fill="{BG}" stroke="{BORDER}"/>'
        f'<circle cx="20" cy="18" r="5" fill="#ff5f57"/><circle cx="36" cy="18" r="5" fill="#febc2e"/>'
        f'<circle cx="52" cy="18" r="5" fill="#28c840"/>'
        f'<text x="{w / 2}" y="22" text-anchor="middle" font-size="11" fill="{MUTED}">{escape(title)}</text>'
    )


def ascii_portrait():
    raw = Image.open(io.BytesIO(requests.get(AVATAR, timeout=30).content)).convert("RGBA")
    rgba = np.array(raw).astype(np.float32)
    premul = rgba[..., :3] * (rgba[..., 3:] / 255)
    color = cv2.resize(premul, (COLS, ROWS), interpolation=cv2.INTER_AREA)
    alpha = cv2.resize(rgba[..., 3], (COLS, ROWS), interpolation=cv2.INTER_AREA)
    true_rgb = color / np.maximum(alpha[..., None] / 255, 1e-3)
    lum = np.clip(true_rgb @ np.array([0.299, 0.587, 0.114]), 0, 255)
    lum = cv2.equalizeHist(lum.astype(np.uint8)).astype(float) * 0.6 + lum * 0.4

    def tint(x, y):
        rgb = color[y, x] / max(alpha[y, x] / 255, 1e-3)
        px = np.clip(rgb, 0, 255).astype(np.uint8).reshape(1, 1, 3)
        hh, ss, vv = cv2.cvtColor(px, cv2.COLOR_RGB2HSV)[0, 0].astype(float)
        if ss < 130 and vv < 120:
            ss = 0
        vv = 72 + vv / 255 * 183
        out = cv2.cvtColor(np.array([[[hh, ss, vv]]], dtype=np.uint8), cv2.COLOR_HSV2RGB)[0, 0]
        q = (out // 8 * 8).astype(int)
        return "#%02x%02x%02x" % tuple(q)

    w = int(COLS * CHAR_W + 40)
    h = int(ROWS * CHAR_H + 60)
    body = []
    for y in range(ROWS):
        runs = []
        for x in range(COLS):
            if alpha[y, x] < 40:
                ch, fill = " ", None
            else:
                ch = DENSE[max(1, min(len(DENSE) - 1, int(lum[y, x] / 256 * len(DENSE))))]
                fill = tint(x, y)
            if runs and (runs[-1][1] == fill or ch == " "):
                runs[-1][0] += ch
            else:
                runs.append([ch, fill])
        line = "".join(r[0] for r in runs).rstrip()
        if not line:
            continue
        spans = "".join(
            f'<tspan fill="{f}">{escape(t)}</tspan>' if f else escape(t) for t, f in runs
        ).rstrip()
        ty = 46 + y * CHAR_H
        delay = 0.25 + y * 0.07
        body.append(
            f'<clipPath id="c{y}"><rect x="20" y="{ty - CHAR_H}" height="{CHAR_H + 2}" width="0">'
            f'<animate attributeName="width" from="0" to="{w - 40}" begin="{delay:.2f}s" dur="0.45s" fill="freeze"/>'
            f"</rect></clipPath>"
            f'<text x="20" y="{ty:.1f}" clip-path="url(#c{y})" xml:space="preserve">{spans}</text>'
        )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<g font-family="{FONT}">{frame(w, h, "dany@danbenba: ~/portrait")}</g>'
        f'<g font-family="{FONT}" font-size="6.25" font-weight="700">{"".join(body)}</g></svg>'
    )
    (OUT / "ascii.svg").write_text(svg)


def contributions():
    html = requests.get(f"https://github.com/users/{USER}/contributions", timeout=30).text
    soup = BeautifulSoup(html, "html.parser")
    days = {}
    for td in soup.select("td[data-date]"):
        days[td["data-date"]] = int(td.get("data-level", 0))
    counts = {}
    for tip in soup.select("tool-tip"):
        target = soup.find(id=tip.get("for"))
        if target is None or not target.get("data-date"):
            continue
        m = re.match(r"(\d+|No) contribution", tip.get_text(strip=True))
        counts[target["data-date"]] = 0 if not m or m.group(1) == "No" else int(m.group(1))
    h2 = soup.find("h2")
    total = re.sub(r"\s+", " ", h2.get_text()).strip() if h2 else ""
    return dict(sorted(days.items())), counts, total


def streaks(counts):
    ordered = [c for _, c in sorted(counts.items())]
    best = cur = 0
    for c in ordered:
        cur = cur + 1 if c > 0 else 0
        best = max(best, cur)
    current = 0
    for c in reversed(ordered[:-1] if ordered and ordered[-1] == 0 else ordered):
        if c == 0:
            break
        current += 1
    return current, best


def heatmap(days, total):
    cell, gap = 11, 3
    dates = list(days)
    first = date.fromisoformat(dates[0])
    offset = (first.weekday() + 1) % 7
    weeks = (len(dates) + offset + 6) // 7
    w = 40 + weeks * (cell + gap) - gap + 40
    h = 46 + 7 * (cell + gap) + 32
    rects = []
    for i, d in enumerate(dates):
        idx = i + offset
        col, row = divmod(idx, 7)
        x = 40 + col * (cell + gap)
        y = 46 + row * (cell + gap)
        delay = 0.2 + (col + row) * 0.025
        rects.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" fill="{HEAT[days[d]]}" opacity="0">'
            f'<animate attributeName="opacity" from="0" to="1" begin="{delay:.3f}s" dur="0.3s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" from="0 -6" to="0 0" begin="{delay:.3f}s" dur="0.3s" fill="freeze"/>'
            f"</rect>"
        )
    months = []
    seen = set()
    for i, d in enumerate(dates):
        dt = date.fromisoformat(d)
        key = (dt.year, dt.month)
        if dt.day <= 7 and key not in seen:
            seen.add(key)
            col = (i + offset) // 7
            months.append(f'<text x="{40 + col * (cell + gap)}" y="40">{dt.strftime("%b")}</text>')
    labels = "".join(
        f'<text x="12" y="{46 + r * (cell + gap) + 9}">{n}</text>' for r, n in ((1, "Mon"), (3, "Wed"), (5, "Fri"))
    )
    legend_x = w - 40 - 6 * (cell + gap) - 64
    legend = f'<text x="{legend_x}" y="{h - 14}">Less</text>' + "".join(
        f'<rect x="{legend_x + 30 + k * (cell + gap)}" y="{h - 23}" width="{cell}" height="{cell}" rx="2.5" fill="{c}"/>'
        for k, c in enumerate(HEAT)
    ) + f'<text x="{legend_x + 34 + 6 * (cell + gap)}" y="{h - 14}">More</text>'
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<g font-family="{FONT}">{frame(w, h, "git log --graph --since=1.year")}'
        f'<g font-size="9" fill="{MUTED}">{"".join(months)}{labels}{legend}'
        f'<text x="40" y="{h - 14}" fill="{TEXT}">{escape(total)}</text></g>'
        f'{"".join(rects)}</g></svg>'
    )
    (OUT / "heatmap.svg").write_text(svg)


def api():
    s = requests.Session()
    s.headers["Accept"] = "application/vnd.github+json"
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    return s


def github_stats():
    s = api()
    user = s.get(f"https://api.github.com/users/{USER}", timeout=30).json()
    repos = s.get(f"https://api.github.com/users/{USER}/repos?per_page=100", timeout=30).json()
    own = [r for r in repos if isinstance(r, dict) and not r.get("fork")]
    stars = sum(r.get("stargazers_count", 0) for r in own)

    def search(q):
        r = s.get("https://api.github.com/search/issues", params={"q": q, "per_page": 1}, timeout=30).json()
        return r.get("total_count", 0)

    prs = search(f"author:{USER} type:pr")
    merged = search(f"author:{USER} type:pr is:merged")
    issues = search(f"author:{USER} type:issue")
    langs = {}
    for r in own:
        if r["name"] in EXCLUDED_LANG_REPOS:
            continue
        data = s.get(r["languages_url"], timeout=30).json()
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, int):
                    langs[k] = langs.get(k, 0) + v
    return {"user": user, "stars": stars, "prs": prs, "merged": merged, "issues": issues, "langs": langs}


def icon(name, x, y, size):
    raw = (Path(__file__).resolve().parent.parent / "assets" / "icons" / f"{name}.svg").read_text()
    inner = raw[raw.index(">") + 1:raw.rindex("</svg>")]
    return f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="0 0 24 24">{inner}</svg>'


def stats_card(st, total):
    w, h = 440, 190
    contribs = total.split(" ")[0] if total else "—"
    rows = [
        ("star", "Stars earned", f'{st["stars"]:,}'),
        ("activity", "Contributions (1y)", contribs),
        ("send", "Pull requests", f'{st["prs"]:,} · {st["merged"]:,} merged'),
        ("chat", "Issues opened", f'{st["issues"]:,}'),
        ("folder", "Public repos", f'{st["user"].get("public_repos", 0):,}'),
        ("people", "Followers", f'{st["user"].get("followers", 0):,}'),
    ]
    out = []
    for i, (ic, label, value) in enumerate(rows):
        y = 50 + i * 22
        delay = 0.3 + i * 0.12
        out.append(
            f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{delay:.2f}s" dur="0.35s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" from="-10 0" to="0 0" begin="{delay:.2f}s" dur="0.35s" fill="freeze"/>'
            f'{icon(ic, 22, y - 13, 16)}'
            f'<text x="46" y="{y}" font-size="12.5" fill="{TEXT}">{escape(label)}</text>'
            f'<text x="290" y="{y}" font-size="12.5" font-weight="700" fill="#ffffff" text-anchor="end">{escape(value)}</text></g>'
        )
    cx, cy, r = 365, 100, 46
    circ = 2 * 3.14159 * r
    ring = (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{BORDER}" stroke-width="7"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{ACCENT}" stroke-width="7" stroke-linecap="round" '
        f'stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ:.1f}" transform="rotate(-90 {cx} {cy})">'
        f'<animate attributeName="stroke-dashoffset" from="{circ:.1f}" to="{circ * 0.08:.1f}" begin="0.4s" dur="1.4s" fill="freeze" calcMode="spline" keySplines="0.2 0.8 0.2 1" keyTimes="0;1"/></circle>'
        f'<text x="{cx}" y="{cy + 2}" font-size="17" font-weight="700" fill="#ffffff" text-anchor="middle">{escape(contribs)}</text>'
        f'<text x="{cx}" y="{cy + 18}" font-size="9" fill="{MUTED}" text-anchor="middle">this year</text>'
    )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<g font-family="{FONT}">{frame(w, h, "gh stats --user danbenba")}{"".join(out)}{ring}</g></svg>'
    )
    (OUT / "stats.svg").write_text(svg)


def langs_card(st):
    w, h = 380, 190
    langs = sorted(st["langs"].items(), key=lambda kv: -kv[1])[:8]
    tot = sum(v for _, v in langs) or 1
    bar, x = [], 22.0
    span = w - 44
    for i, (name, v) in enumerate(langs):
        bw = span * v / tot
        delay = 0.3 + i * 0.1
        bar.append(
            f'<rect x="{x:.1f}" y="44" height="8" width="0" fill="{LANG_COLORS.get(name, "#8b949e")}">'
            f'<animate attributeName="width" from="0" to="{bw:.1f}" begin="{delay:.2f}s" dur="0.5s" fill="freeze"/></rect>'
        )
        x += bw
    legend = []
    for i, (name, v) in enumerate(langs):
        col, row = divmod(i, 4)
        lx = 22 + col * 175
        ly = 82 + row * 24
        delay = 0.5 + i * 0.1
        legend.append(
            f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{delay:.2f}s" dur="0.35s" fill="freeze"/>'
            f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{LANG_COLORS.get(name, "#8b949e")}"/>'
            f'<text x="{lx + 16}" y="{ly}" font-size="12" fill="{TEXT}">{escape(name)}</text>'
            f'<text x="{lx + 160}" y="{ly}" font-size="12" fill="{MUTED}" text-anchor="end">{v / tot * 100:.1f}%</text></g>'
        )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<defs><clipPath id="bar"><rect x="22" y="44" width="{span}" height="8" rx="4"/></clipPath></defs>'
        f'<g font-family="{FONT}">{frame(w, h, "top languages")}'
        f'<rect x="22" y="44" width="{span}" height="8" rx="4" fill="{BORDER}"/>'
        f'<g clip-path="url(#bar)">{"".join(bar)}</g>{"".join(legend)}</g></svg>'
    )
    (OUT / "langs.svg").write_text(svg)


def info_card(st, counts, total):
    user, stars = st["user"], st["stars"]
    current, best = streaks(counts) if counts else (0, 0)
    age_years = date.today().year - 2021
    rows = [
        ("title", "dany@danbenba"),
        ("rule", ""),
        ("kv", "OS", "macOS · Linux · Windows (ex-tweaker)"),
        ("kv", "Role", "Fullstack Developer · Freelance"),
        ("kv", "Uptime", f"{age_years} years shipping code (since 2021)"),
        ("kv", "Location", "France 🇫🇷"),
        ("kv", "Shell", "zsh + Claude Code + Codex"),
        ("kv", "Stack", "TypeScript · React · Node · Astro"),
        ("kv", "Infra", "Docker · Dokploy · Vercel · Cloudflare"),
        ("kv", "Design", "Figma · Framer"),
        ("kv", "Building", "MCP servers · SaaS · AI agents"),
        ("rule", ""),
        ("kv", "Repos", f'{user.get("public_repos", "?")} public · ★ {stars}'),
        ("kv", "Followers", str(user.get("followers", "?"))),
        ("kv", "Contribs", f"{total.split(' ')[0]} in the last year" if total else "—"),
        ("kv", "Streak", f"{current}d current · {best}d best"),
        ("palette", ""),
    ]
    out = []
    y = 54
    for i, row in enumerate(rows):
        delay = 0.3 + i * 0.12
        anim = (
            f'<animate attributeName="opacity" from="0" to="1" begin="{delay:.2f}s" dur="0.35s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" from="-10 0" to="0 0" begin="{delay:.2f}s" dur="0.35s" fill="freeze"/>'
        )
        kind = row[0]
        if kind == "title":
            out.append(f'<g opacity="0">{anim}<text x="24" y="{y}" font-size="14" font-weight="700">'
                       f'<tspan fill="{ACCENT}">dany</tspan><tspan fill="{TEXT}">@</tspan><tspan fill="{ACCENT}">danbenba</tspan></text></g>')
            y += 14
        elif kind == "rule":
            out.append(f'<g opacity="0">{anim}<line x1="24" x2="{CARD_W - 24}" y1="{y - 4}" y2="{y - 4}" stroke="{BORDER}" stroke-dasharray="3 3"/></g>')
            y += 12
        elif kind == "kv":
            out.append(f'<g opacity="0">{anim}<text x="24" y="{y}" font-size="12.5">'
                       f'<tspan fill="{ACCENT}" font-weight="700">{escape(row[1])}</tspan>'
                       f'<tspan fill="{MUTED}">: </tspan><tspan fill="{TEXT}">{escape(row[2])}</tspan></text></g>')
            y += 19
        elif kind == "palette":
            sw = "".join(f'<rect x="{24 + k * 26}" y="{y}" width="22" height="12" rx="3" fill="{c}"/>'
                         for k, c in enumerate(["#ff5f57", "#febc2e", "#28c840", "#58a6ff", "#bc8cff", ACCENT, "#a5c8ff", TEXT]))
            out.append(f'<g opacity="0">{anim}{sw}</g>')
            y += 18
    cursor_y = y + 8
    out.append(
        f'<text x="24" y="{cursor_y}" font-size="12.5" fill="{MUTED}" opacity="0">'
        f'<animate attributeName="opacity" from="0" to="1" begin="{0.3 + len(rows) * 0.12:.2f}s" dur="0.2s" fill="freeze"/>'
        f'<tspan fill="{ACCENT}">❯</tspan> <tspan fill="{ACCENT}">▋</tspan>'
        f"</text>"
    )
    h = cursor_y + 20
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_W}" height="{h}" viewBox="0 0 {CARD_W} {h}">'
        f'<style>@keyframes b{{50%{{opacity:0}}}}.cur{{animation:b 1s step-end infinite}}</style>'
        f'<g font-family="{FONT}">{frame(CARD_W, h, "neofetch")}{"".join(out)}</g></svg>'
    ).replace(f'<tspan fill="{ACCENT}">▋</tspan>', f'<tspan class="cur" fill="{ACCENT}">▋</tspan>')
    (OUT / "info-card.svg").write_text(svg)


def main():
    OUT.mkdir(exist_ok=True)
    ascii_portrait()
    days, counts, total = contributions()
    heatmap(days, total)
    st = github_stats()
    info_card(st, counts, total)
    stats_card(st, total)
    langs_card(st)


if __name__ == "__main__":
    main()
