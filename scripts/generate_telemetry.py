#!/usr/bin/env python3
"""
Generates a btop/tmux-inspired terminal monitor SVG (dark & light themes)
with a 3D isometric contribution matrix, weekly signal trace, 24h circadian
histogram, and live process table from GitHub GraphQL contribution data.
Zero external dependencies (Python 3 stdlib only).
"""

import datetime
import json
import os
import urllib.request

GITHUB_USER = os.environ.get("GITHUB_USER", "berndof")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

GRAPHQL_QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      totalIssueContributions
      totalPullRequestContributions
      totalRepositoryContributions
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
            weekday
          }
        }
      }
    }
  }
}
"""


def fetch_data():
    if not GITHUB_TOKEN:
        return None
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": GRAPHQL_QUERY, "variables": {"login": GITHUB_USER}}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "berndof-telemetry-generator",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload["data"]["user"]


def fetch_commit_hours():
    """Sample commit timestamps across key repos to compute real hour-of-day (BRT, UTC-3) activity."""
    if not GITHUB_TOKEN:
        return [8, 12, 15, 19, 6, 2, 0, 1, 4, 11, 18, 22, 14, 20, 25, 28, 24, 19, 14, 16, 21, 26, 29, 18]
    repos = [
        "gruposcc/infrascc10",
        "gruposcc/gestao-torres",
        "gruposcc/caddy-reverse-proxy",
        "gruposcc/zabbix-agent",
        "berndof/opencode-orchestrator",
        "berndof/opencode-remote",
        "berndof/eleicao-2026",
        "berndof/fusion_solar_scraper",
        "berndof/dse855-scraper",
    ]
    hours = [0] * 24
    for repo in repos:
        url = f"https://api.github.com/repos/{repo}/commits?per_page=100"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "User-Agent": "berndof-telemetry-generator",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                commits = json.loads(resp.read().decode("utf-8"))
                for c in commits:
                    author = (c.get("author") or {}).get("login", "")
                    email = ((c.get("commit") or {}).get("author") or {}).get("email", "")
                    if author == GITHUB_USER or "berndof" in email or "bernardo" in email:
                        date_str = ((c.get("commit") or {}).get("author") or {}).get("date", "")
                        if date_str:
                            dt = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                            brt_hour = (dt.hour - 3) % 24
                            hours[brt_hour] += 1
        except Exception:
            continue
    if sum(hours) == 0:
        hours = [8, 12, 15, 19, 6, 2, 0, 1, 4, 11, 18, 22, 14, 20, 25, 28, 24, 19, 14, 16, 21, 26, 29, 18]
    return hours


def render_iso_cube(cx, cy, h, wx, wy, colors, delay_s=0.0, is_peak=False):
    top_fill, left_fill, right_fill, stroke_col = colors
    t_top = (cx, cy - wy - h)
    t_right = (cx + wx, cy - h)
    t_bottom = (cx, cy + wy - h)
    t_left = (cx - wx, cy - h)

    b_right = (cx + wx, cy)
    b_bottom = (cx, cy + wy)
    b_left = (cx - wx, cy)

    top_pts = f"{t_top[0]:.1f},{t_top[1]:.1f} {t_right[0]:.1f},{t_right[1]:.1f} {t_bottom[0]:.1f},{t_bottom[1]:.1f} {t_left[0]:.1f},{t_left[1]:.1f}"
    left_pts = f"{t_left[0]:.1f},{t_left[1]:.1f} {t_bottom[0]:.1f},{t_bottom[1]:.1f} {b_bottom[0]:.1f},{b_bottom[1]:.1f} {b_left[0]:.1f},{b_left[1]:.1f}"
    right_pts = f"{t_bottom[0]:.1f},{t_bottom[1]:.1f} {t_right[0]:.1f},{t_right[1]:.1f} {b_right[0]:.1f},{b_right[1]:.1f} {b_bottom[0]:.1f},{b_bottom[1]:.1f}"

    cls = ' class="peak-cube"' if is_peak else ""
    style = f' style="animation-delay: {delay_s:.2f}s"' if is_peak else ""

    parts = [f'<g{cls}{style}>']
    if h > 0.5:
        parts.append(f'<polygon points="{left_pts}" fill="{left_fill}" stroke="{stroke_col}" stroke-width="0.35"/>')
        parts.append(f'<polygon points="{right_pts}" fill="{right_fill}" stroke="{stroke_col}" stroke-width="0.35"/>')
    parts.append(f'<polygon points="{top_pts}" fill="{top_fill}" stroke="{stroke_col}" stroke-width="0.4"/>')
    parts.append("</g>")
    return "".join(parts)


def generate_svg(user_data, commit_hours, mode="dark"):
    cc = user_data["contributionsCollection"]
    cal = cc["contributionCalendar"]
    total_contribs = cal["totalContributions"]
    public_commits = cc["totalCommitContributions"]
    private_contribs = cc["restrictedContributionsCount"]
    weeks = cal["weeks"]

    active_days = 0
    max_day = 0
    peak_coords = None
    weekly_totals = []
    for w_idx, w in enumerate(weeks):
        w_sum = 0
        for d in w["contributionDays"]:
            c = d["contributionCount"]
            w_sum += c
            if c > 0:
                active_days += 1
            if c >= max_day and c > 0:
                max_day = c
                peak_coords = (w_idx, d["weekday"], c)
        weekly_totals.append(w_sum)

    avg_wk = total_contribs / max(1, len(weekly_totals))
    max_wk = max(weekly_totals) if weekly_totals else 0

    priv_pct = round((private_contribs / max(1, public_commits + private_contribs)) * 100, 1)
    pub_pct = round(100.0 - priv_pct, 1)

    today = datetime.date.today()
    typo_fixed_date = datetime.date(2026, 10, 15)
    typo_free_days = max(1, (today - typo_fixed_date).days)
    uptime_days = max(1, (today - datetime.date(2023, 3, 26)).days)
    up_y = uptime_days // 365
    up_d = uptime_days % 365

    if mode == "dark":
        bg = "#0c1017"
        term_bar = "#111722"
        panel_bg = "#0f141d"
        row_alt = "#141b26"
        panel_border = "#263244"
        grid_line = "#1b2432"
        text_main = "#d8dee9"
        text_muted = "#64748b"
        text_dim = "#475569"
        accent = "#10b981"
        accent_cyan = "#38bdf8"
        accent_warn = "#f59e0b"
        accent_zombie = "#ef4444"
        tmux_bg = "#131b26"
        tmux_pill_fg = "#090d12"
        levels = [
            ("#151d2a", "#0f1620", "#0b1018", "#1e293b"),  # 0
            ("#065f46", "#064e3b", "#022c22", "#047857"),  # 1
            ("#059669", "#047857", "#065f46", "#10b981"),  # 2
            ("#10b981", "#059669", "#047857", "#34d399"),  # 3
            ("#34d399", "#10b981", "#059669", "#6ee7b7"),  # 4
        ]
    else:
        bg = "#f1f5f9"
        term_bar = "#e2e8f0"
        panel_bg = "#ffffff"
        row_alt = "#f8fafc"
        panel_border = "#cbd5e1"
        grid_line = "#e2e8f0"
        text_main = "#0f172a"
        text_muted = "#64748b"
        text_dim = "#94a3b8"
        accent = "#059669"
        accent_cyan = "#0284c7"
        accent_warn = "#d97706"
        accent_zombie = "#dc2626"
        tmux_bg = "#e2e8f0"
        tmux_pill_fg = "#ffffff"
        levels = [
            ("#e2e8f0", "#cbd5e1", "#94a3b8", "#cbd5e1"),  # 0
            ("#a7f3d0", "#6ee7b7", "#34d399", "#6ee7b7"),  # 1
            ("#34d399", "#10b981", "#059669", "#10b981"),  # 2
            ("#10b981", "#059669", "#047857", "#059669"),  # 3
            ("#059669", "#047857", "#065f46", "#047857"),  # 4
        ]

    # 3D Isometric Grid in Pane 1 (x=12..388, y=38..314)
    wx = 4.65
    wy = 2.45
    origin_x = 76.0
    origin_y = 160.0

    cubes_svg = []
    peak_marker_svg = ""
    month_labels_svg = []
    seen_months = set()
    month_names = ["", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

    for w_idx, w in enumerate(weeks):
        days = w["contributionDays"]
        if days:
            first_date = days[0].get("date", "")
            if len(first_date) >= 7:
                ym = first_date[:7]
                m_num = int(first_date[5:7])
                if ym not in seen_months and w_idx % 8 == 2:
                    seen_months.add(ym)
                    mx = origin_x + (w_idx * wx) - (7.2 * 3.8)
                    my = origin_y + (w_idx * wy * 0.52) + (7.2 * 4.2) + 8
                    month_labels_svg.append(
                        f'<text x="{mx:.1f}" y="{my:.1f}" fill="{text_dim}" font-size="7.5" class="mono">{month_names[m_num]}</text>'
                    )

        for d in days:
            d_idx = d["weekday"]
            c = d["contributionCount"]
            cx = origin_x + (w_idx * wx) - (d_idx * 3.8)
            cy = origin_y + (w_idx * wy * 0.52) + (d_idx * 4.2)
            if c == 0:
                lvl = 0
                h = 1.4
            elif c <= 2:
                lvl = 1
                h = 5.5 + c * 2.0
            elif c <= 6:
                lvl = 2
                h = 11.5 + (c - 2) * 2.4
            elif c <= 14:
                lvl = 3
                h = 21.0 + (c - 6) * 1.7
            else:
                lvl = 4
                h = min(50.0, 34.0 + (c - 14) * 1.0)

            is_peak = lvl >= 3
            delay = ((w_idx * 7 + d_idx) % 20) * 0.15
            cubes_svg.append(render_iso_cube(cx, cy, h, 3.75, 2.05, levels[lvl], delay, is_peak))

            if peak_coords and (w_idx, d_idx) == (peak_coords[0], peak_coords[1]):
                py_top = cy - 2.05 - h - 5
                peak_marker_svg = (
                    f'<line x1="{cx:.1f}" y1="{py_top:.1f}" x2="{cx:.1f}" y2="{py_top - 10:.1f}" stroke="{accent_cyan}" stroke-width="0.9" stroke-dasharray="1.5,1.5"/>'
                    f'<text x="{cx:.1f}" y="{py_top - 13:.1f}" text-anchor="middle" fill="{accent_cyan}" font-size="8" font-weight="bold" class="mono">{c}/d</text>'
                )

    # Split bar in Pane 1 (x=284..374)
    split_total_w = 88.0
    priv_bar_w = (priv_pct / 100.0) * split_total_w

    # Pane 2: Weekly Commit Oscilloscope (x=398..646, y=38..160)
    osc_x0, osc_x1 = 410, 634
    osc_y0, osc_y1 = 72, 140
    max_w_val = max(max_wk, 10)
    osc_pts = []
    area_pts = [f"{osc_x0},{osc_y1}"]
    n_weeks = len(weekly_totals)
    for i, val in enumerate(weekly_totals):
        px = osc_x0 + (i / max(1, n_weeks - 1)) * (osc_x1 - osc_x0)
        py = osc_y1 - (val / max_w_val) * (osc_y1 - osc_y0 - 6)
        osc_pts.append(f"{px:.1f},{py:.1f}")
        area_pts.append(f"{px:.1f},{py:.1f}")
    area_pts.append(f"{osc_x1},{osc_y1}")
    osc_polyline = " ".join(osc_pts)
    osc_area = " ".join(area_pts)

    # Pane 3: 24h Circadian Histogram (x=656..868, y=38..160)
    hist_x0, hist_x1 = 668, 856
    hist_y0, hist_y1 = 76, 140
    max_hr = max(max(commit_hours), 1)
    bar_w = (hist_x1 - hist_x0) / 24.0
    bars_svg = []
    for hr, count in enumerate(commit_hours):
        bh = max(1.8, (count / max_hr) * (hist_y1 - hist_y0))
        bx = hist_x0 + hr * bar_w
        by = hist_y1 - bh
        # Track background
        bars_svg.append(
            f'<rect x="{bx:.1f}" y="{hist_y0}" width="{bar_w - 2.0:.1f}" height="{hist_y1 - hist_y0}" rx="1" fill="{grid_line}" opacity="0.35"/>'
        )
        if hr >= 22 or hr <= 4:
            bcol = accent_cyan if count > 0 else grid_line
        else:
            bcol = accent if count > 0 else grid_line
        bars_svg.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w - 2.0:.1f}" height="{bh:.1f}" rx="1" fill="{bcol}" opacity="0.92"/>'
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 352" width="100%" height="100%">
  <defs>
    <linearGradient id="oscGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.35"/>
      <stop offset="100%" stop-color="{accent}" stop-opacity="0.0"/>
    </linearGradient>
    <linearGradient id="scanGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="{accent_cyan}" stop-opacity="0.0"/>
      <stop offset="50%" stop-color="{accent_cyan}" stop-opacity="0.28"/>
      <stop offset="100%" stop-color="{accent_cyan}" stop-opacity="0.0"/>
    </linearGradient>
    <clipPath id="oscClip">
      <rect x="{osc_x0}" y="{osc_y0 - 8}" width="{osc_x1 - osc_x0}" height="{osc_y1 - osc_y0 + 12}"/>
    </clipPath>
    <style>
      .mono {{ font-family: 'JetBrains Mono', 'Fira Code', 'SFMono-Regular', Consolas, 'Liberation Mono', monospace; }}
      .led-ok {{ animation: blinkOk 2.8s infinite ease-in-out; }}
      .scanline {{ animation: sweep 6s infinite linear; }}
      .peak-cube {{ animation: floatPeak 3.4s infinite ease-in-out; }}
      .pulse-path {{ stroke-dasharray: 700; stroke-dashoffset: 700; animation: drawWave 2.8s ease-out forwards; }}
      @keyframes blinkOk {{ 0%, 100% {{ opacity: 0.95; }} 50% {{ opacity: 0.25; }} }}
      @keyframes sweep {{
        0% {{ transform: translateX(-45px); }}
        100% {{ transform: translateX(240px); }}
      }}
      @keyframes floatPeak {{
        0%, 100% {{ filter: brightness(1.0); }}
        50% {{ filter: brightness(1.24); }}
      }}
      @keyframes drawWave {{
        to {{ stroke-dashoffset: 0; }}
      }}
    </style>
  </defs>

  <!-- Outer Terminal Window -->
  <rect x="2" y="2" width="876" height="348" rx="6" fill="{bg}" stroke="{panel_border}" stroke-width="1.2"/>

  <!-- Terminal Window Header Bar -->
  <path d="M 2 8 Q 2 2 8 2 L 872 2 Q 878 2 878 8 L 878 28 L 2 28 Z" fill="{term_bar}"/>
  <line x1="2" y1="28" x2="878" y2="28" stroke="{panel_border}" stroke-width="1"/>
  <circle cx="16" cy="15" r="3.2" fill="{text_dim}" opacity="0.6"/>
  <circle cx="27" cy="15" r="3.2" fill="{text_dim}" opacity="0.6"/>
  <circle cx="38" cy="15" r="3.2" fill="{text_dim}" opacity="0.6"/>
  <text x="440" y="18.5" text-anchor="middle" fill="{text_muted}" font-size="10" class="mono">berndof@fln-noc: ~ (tmux)</text>
  <text x="866" y="18.5" text-anchor="end" fill="{text_muted}" font-size="9" class="mono">up {up_y}y {up_d}d │ load: 0.42 0.86 1.05</text>

  <!-- ======================================================================= -->
  <!-- PANE 1: 3D Isometric Commit Matrix (btop box style)                     -->
  <!-- ======================================================================= -->
  <rect x="12" y="38" width="376" height="276" rx="3" fill="{panel_bg}" stroke="{panel_border}" stroke-width="1"/>
  <rect x="22" y="32" width="114" height="11" fill="{panel_bg}"/>
  <text x="26" y="41" fill="{text_main}" font-size="9.5" class="mono"><tspan fill="{text_muted}">┤</tspan><tspan fill="{accent}" font-weight="bold">¹</tspan> commits (52w)<tspan fill="{text_muted}">├</tspan></text>

  <text x="24" y="57" fill="{text_muted}" font-size="9" class="mono"><tspan fill="{text_main}" font-weight="bold">{total_contribs}</tspan> total  │  <tspan fill="{accent_cyan}" font-weight="bold">{active_days}d</tspan> active  │  max <tspan fill="{accent}" font-weight="bold">{max_day}/d</tspan></text>
  <text x="24" y="71" fill="{text_muted}" font-size="8.5" class="mono">split: <tspan fill="{accent}">{priv_pct}% @gruposcc</tspan> / <tspan fill="{accent_cyan}">{pub_pct}% pub</tspan></text>

  <!-- Mini Split Bar -->
  <rect x="284" y="64" width="{split_total_w}" height="5" rx="2" fill="{accent_cyan}" opacity="0.8"/>
  <rect x="284" y="64" width="{priv_bar_w:.1f}" height="5" rx="2" fill="{accent}"/>

  <!-- 3D Isometric Cubes & Month Ticks -->
  <g transform="translate(0, 6)">
    {"".join(month_labels_svg)}
    {"".join(cubes_svg)}
    {peak_marker_svg}
  </g>

  <text x="24" y="303" fill="{text_muted}" font-size="8" class="mono">z-scale: ░ 0   ▒ 1-2   ▓ 3-6   █ 15+ (3am rabbit hole)</text>

  <!-- ======================================================================= -->
  <!-- PANE 2: Weekly Commit Rate Oscilloscope                                 -->
  <!-- ======================================================================= -->
  <rect x="398" y="38" width="248" height="122" rx="3" fill="{panel_bg}" stroke="{panel_border}" stroke-width="1"/>
  <rect x="408" y="32" width="124" height="11" fill="{panel_bg}"/>
  <text x="412" y="41" fill="{text_main}" font-size="9.5" class="mono"><tspan fill="{text_muted}">┤</tspan><tspan fill="{accent}" font-weight="bold">²</tspan> throughput (wk)<tspan fill="{text_muted}">├</tspan></text>
  <text x="636" y="56" text-anchor="end" fill="{text_muted}" font-size="8.5" class="mono">avg <tspan fill="{text_main}">{avg_wk:.1f}/w</tspan> · max <tspan fill="{accent}">{max_wk}/w</tspan></text>

  <line x1="{osc_x0}" y1="88" x2="{osc_x1}" y2="88" stroke="{grid_line}" stroke-width="0.8" stroke-dasharray="2,3"/>
  <line x1="{osc_x0}" y1="114" x2="{osc_x1}" y2="114" stroke="{grid_line}" stroke-width="0.8" stroke-dasharray="2,3"/>
  <line x1="{osc_x0}" y1="{osc_y1}" x2="{osc_x1}" y2="{osc_y1}" stroke="{grid_line}" stroke-width="1"/>

  <g clip-path="url(#oscClip)">
    <polygon points="{osc_area}" fill="url(#oscGrad)"/>
    <polyline points="{osc_polyline}" fill="none" stroke="{accent}" stroke-width="1.7" class="pulse-path"/>
    <rect x="{osc_x0}" y="{osc_y0 - 6}" width="40" height="{osc_y1 - osc_y0 + 10}" fill="url(#scanGrad)" class="scanline"/>
  </g>

  <text x="{osc_x0}" y="151" fill="{text_dim}" font-size="7.5" class="mono">-52w</text>
  <text x="{(osc_x0 + osc_x1) / 2:.0f}" y="151" text-anchor="middle" fill="{text_dim}" font-size="7.5" class="mono">-26w</text>
  <text x="{osc_x1}" y="151" text-anchor="end" fill="{text_dim}" font-size="7.5" class="mono">now</text>

  <!-- ======================================================================= -->
  <!-- PANE 3: Circadian Activity (24h BRT / UTC-3)                            -->
  <!-- ======================================================================= -->
  <rect x="656" y="38" width="212" height="122" rx="3" fill="{panel_bg}" stroke="{panel_border}" stroke-width="1"/>
  <rect x="666" y="32" width="114" height="11" fill="{panel_bg}"/>
  <text x="670" y="41" fill="{text_main}" font-size="9.5" class="mono"><tspan fill="{text_muted}">┤</tspan><tspan fill="{accent_cyan}" font-weight="bold">³</tspan> hours (utc-3)<tspan fill="{text_muted}">├</tspan></text>

  <text x="668" y="56" fill="{text_muted}" font-size="8" class="mono"><tspan fill="{accent_cyan}">■</tspan> 22-04h "so mais um fix"</text>

  {"".join(bars_svg)}
  <line x1="{hist_x0}" y1="{hist_y1}" x2="{hist_x1}" y2="{hist_y1}" stroke="{grid_line}" stroke-width="1"/>
  <text x="668" y="151" fill="{text_dim}" font-size="7.5" class="mono">00h</text>
  <text x="715" y="151" fill="{text_dim}" font-size="7.5" class="mono">06h</text>
  <text x="762" y="151" fill="{text_dim}" font-size="7.5" class="mono">12h</text>
  <text x="809" y="151" fill="{text_dim}" font-size="7.5" class="mono">18h</text>
  <text x="856" y="151" text-anchor="end" fill="{text_dim}" font-size="7.5" class="mono">23h</text>

  <!-- ======================================================================= -->
  <!-- PANE 4: Process Table (btop / htop proc view)                           -->
  <!-- ======================================================================= -->
  <rect x="398" y="170" width="470" height="144" rx="3" fill="{panel_bg}" stroke="{panel_border}" stroke-width="1"/>
  <rect x="408" y="164" width="144" height="11" fill="{panel_bg}"/>
  <text x="412" y="173" fill="{text_main}" font-size="9.5" class="mono"><tspan fill="{text_muted}">┤</tspan><tspan fill="{accent}" font-weight="bold">⁴</tspan> proc (user=berndof)<tspan fill="{text_muted}">├</tspan></text>
  <text x="856" y="173" text-anchor="end" fill="{text_muted}" font-size="8.5" class="mono">tasks: <tspan fill="{text_main}">6</tspan> (<tspan fill="{accent_warn}">1 zombie</tspan>)</text>

  <!-- Table Header -->
  <text x="410" y="190" fill="{text_muted}" font-size="8.5" font-weight="bold" class="mono" xml:space="preserve">  PID  S   CPU%   MEM     TIME+   COMMAND</text>
  <line x1="406" y1="195" x2="860" y2="195" stroke="{grid_line}" stroke-width="1"/>

  <!-- Alternating Row Highlights -->
  <rect x="404" y="199" width="458" height="16" rx="1.5" fill="{row_alt}"/>
  <rect x="404" y="233" width="458" height="16" rx="1.5" fill="{row_alt}"/>
  <rect x="404" y="267" width="458" height="16" rx="1.5" fill="{row_alt}"/>

  <!-- Process Rows -->
  <text x="410" y="210" fill="{text_main}" font-size="8.5" class="mono" xml:space="preserve">  412  <tspan fill="{accent}">S</tspan>    2.4   18M   418:12   <tspan fill="{accent_cyan}">chisel</tspan> client --psk [scc10-noc]</text>
  <text x="410" y="227" fill="{text_main}" font-size="8.5" class="mono" xml:space="preserve">  855  <tspan fill="{accent}">R</tspan>    8.1   36M   104:08   <tspan fill="{accent}">python3</tspan> dse855_zabbix.py --coax-port-80</text>
  <text x="410" y="244" fill="{text_main}" font-size="8.5" class="mono" xml:space="preserve"> 1337  <tspan fill="{accent}">R</tspan>   24.6   94M   289:44   <tspan fill="{accent_cyan}">opencode</tspan> --agents 5 --trust-none</text>
  <text x="410" y="261" fill="{text_main}" font-size="8.5" class="mono" xml:space="preserve"> 2026  <tspan fill="{accent}">R</tspan>   61.2  240M    19:03   <tspan fill="{accent}">python3</tspan> monte_carlo.py -n 30000 --still-unsure</text>
  <text x="410" y="278" fill="{text_main}" font-size="8.5" class="mono" xml:space="preserve"> 4004  <tspan fill="{accent}">S</tspan>    0.8   12M    62:15   <tspan fill="{accent_cyan}">uvicorn</tspan> app:app --zero-bundler</text>
  <text x="410" y="295" fill="{text_muted}" font-size="8.5" class="mono" xml:space="preserve">  817  <tspan fill="{accent_zombie}" font-weight="bold">Z</tspan>    0.0    0B     0:00   <tspan fill="{text_muted}">[Hello, Wolrd!] &lt;defunct&gt;</tspan></text>

  <!-- ======================================================================= -->
  <!-- BOTTOM TMUX STATUS BAR                                                  -->
  <!-- ======================================================================= -->
  <rect x="12" y="322" width="856" height="20" rx="2.5" fill="{tmux_bg}" stroke="{panel_border}" stroke-width="0.8"/>
  <rect x="12" y="322" width="64" height="20" rx="2.5" fill="{accent}"/>
  <circle cx="23" cy="332" r="2.8" fill="{tmux_pill_fg}" class="led-ok"/>
  <text x="46" y="335" text-anchor="middle" fill="{tmux_pill_fg}" font-size="8.8" font-weight="bold" class="mono">0:noc</text>

  <text x="88" y="335" fill="{text_muted}" font-size="8.8" class="mono"><tspan fill="{text_main}" font-weight="bold">0:btop*</tspan>   1:scc10-ssh   2:zabbix-proxy   3:rf-towers</text>
  <text x="858" y="335" text-anchor="end" fill="{text_muted}" font-size="8.5" class="mono">py · ts · bash · php · sql  │  node_modules: <tspan fill="{accent}" font-weight="bold">0B</tspan>  │  typo-free: <tspan fill="{accent_warn}" font-weight="bold">{typo_free_days}d</tspan></text>
</svg>
"""
    return svg


def _mock_user_data():
    """Fallback structure for local dry-runs when GITHUB_TOKEN is not set."""
    weeks = []
    for w in range(53):
        days = []
        for d in range(7):
            c = ((w * 3 + d * 5) % 11) if (w + d) % 4 == 0 else 0
            date_str = (datetime.date(2025, 10, 15) + datetime.timedelta(days=w * 7 + d)).isoformat()
            days.append({"contributionCount": c, "date": date_str, "weekday": d})
        weeks.append({"contributionDays": days})
    return {
        "contributionsCollection": {
            "totalCommitContributions": 54,
            "restrictedContributionsCount": 341,
            "contributionCalendar": {
                "totalContributions": 395,
                "weeks": weeks,
            },
        }
    }


def main():
    out_dir = os.environ.get("OUT_DIR", "dist")
    os.makedirs(out_dir, exist_ok=True)
    user_data = fetch_data() or _mock_user_data()
    commit_hours = fetch_commit_hours()

    dark_svg = generate_svg(user_data, commit_hours, mode="dark")
    light_svg = generate_svg(user_data, commit_hours, mode="light")

    with open(os.path.join(out_dir, "noc-telemetry-dark.svg"), "w", encoding="utf-8") as f:
        f.write(dark_svg)
    with open(os.path.join(out_dir, "noc-telemetry-light.svg"), "w", encoding="utf-8") as f:
        f.write(light_svg)
    print(f"Generated {out_dir}/noc-telemetry-dark.svg and {out_dir}/noc-telemetry-light.svg successfully.")


if __name__ == "__main__":
    main()
