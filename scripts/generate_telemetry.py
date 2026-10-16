#!/usr/bin/env python3
"""
Generates an animated NOC Telemetry & 3D Isometric Contribution Skyline SVG
(dark and light themes) from live GitHub GraphQL contribution data.
Zero external dependencies (Python 3 stdlib only).
"""

import datetime
import json
import math
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
        # Fallback distribution if API rate-limited
        hours = [8, 12, 15, 19, 6, 2, 0, 1, 4, 11, 18, 22, 14, 20, 25, 28, 24, 19, 14, 16, 21, 26, 29, 18]
    return hours


def render_iso_cube(cx, cy, h, wx, wy, colors, delay_s=0.0, is_peak=False):
    """
    Renders a single 3D isometric column at screen center (cx, cy) with height h.
    wx, wy are the half-width and half-height of the isometric diamond tile.
    """
    top_fill, left_fill, right_fill, stroke_col = colors
    # Base diamond vertices:
    # Top: (cx, cy - wy), Right: (cx + wx, cy), Bottom: (cx, cy + wy), Left: (cx - wx, cy)
    # Extruded upwards by h:
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
    weekly_totals = []
    for w in weeks:
        w_sum = 0
        for d in w["contributionDays"]:
            c = d["contributionCount"]
            w_sum += c
            if c > 0:
                active_days += 1
            if c > max_day:
                max_day = c
        weekly_totals.append(w_sum)

    priv_pct = round((private_contribs / max(1, public_commits + private_contribs)) * 100, 1)
    pub_pct = round(100.0 - priv_pct, 1)

    if mode == "dark":
        bg = "#0b0f17"
        panel_bg = "#111827"
        panel_border = "#1f2937"
        grid_line = "#1e293b"
        text_main = "#e2e8f0"
        text_muted = "#64748b"
        accent = "#10b981"
        accent_cyan = "#06b6d4"
        accent_warn = "#f59e0b"
        accent_purple = "#8b5cf6"
        levels = [
            ("#161f30", "#0f172a", "#0b1120", "#1e293b"),  # 0
            ("#065f46", "#064e3b", "#022c22", "#047857"),  # 1
            ("#059669", "#047857", "#065f46", "#10b981"),  # 2
            ("#10b981", "#059669", "#047857", "#34d399"),  # 3
            ("#34d399", "#10b981", "#059669", "#6ee7b7"),  # 4 (peak)
        ]
    else:
        bg = "#f8fafc"
        panel_bg = "#ffffff"
        panel_border = "#cbd5e1"
        grid_line = "#e2e8f0"
        text_main = "#0f172a"
        text_muted = "#64748b"
        accent = "#059669"
        accent_cyan = "#0284c7"
        accent_warn = "#d97706"
        accent_purple = "#7c3aed"
        levels = [
            ("#e2e8f0", "#cbd5e1", "#94a3b8", "#cbd5e1"),  # 0
            ("#a7f3d0", "#6ee7b7", "#34d399", "#6ee7b7"),  # 1
            ("#34d399", "#10b981", "#059669", "#10b981"),  # 2
            ("#10b981", "#059669", "#047857", "#059669"),  # 3
            ("#059669", "#047857", "#065f46", "#047857"),  # 4
        ]

    # Build 3D Isometric Grid in Left Panel
    # Grid dimensions: 53 weeks (x) by 7 days (y)
    # Isometric projection:
    # screen_x = origin_x + (w_idx - d_idx) * wx
    # screen_y = origin_y + (w_idx + d_idx) * wy
    wx = 4.6
    wy = 2.45
    origin_x = 68.0
    origin_y = 148.0

    cubes_svg = []
    for w_idx, w in enumerate(weeks):
        for d in w["contributionDays"]:
            d_idx = d["weekday"]
            c = d["contributionCount"]
            cx = origin_x + (w_idx * wx) - (d_idx * 3.8)
            cy = origin_y + (w_idx * wy * 0.52) + (d_idx * 4.2)
            if c == 0:
                lvl = 0
                h = 1.5
            elif c <= 2:
                lvl = 1
                h = 6.0 + c * 2.0
            elif c <= 6:
                lvl = 2
                h = 12.0 + (c - 2) * 2.5
            elif c <= 14:
                lvl = 3
                h = 22.0 + (c - 6) * 1.8
            else:
                lvl = 4
                h = min(54.0, 36.0 + (c - 14) * 1.1)

            is_peak = lvl >= 3
            delay = ((w_idx * 7 + d_idx) % 20) * 0.15
            cubes_svg.append(render_iso_cube(cx, cy, h, 3.8, 2.1, levels[lvl], delay, is_peak))

    # Build Weekly Oscilloscope Waveform (Right Top Panel)
    # Panel area: x=375..860, y=68..178
    osc_x0, osc_x1 = 388, 852
    osc_y0, osc_y1 = 88, 166
    max_w = max(max(weekly_totals), 10)
    osc_pts = []
    area_pts = [f"{osc_x0},{osc_y1}"]
    n_weeks = len(weekly_totals)
    for i, val in enumerate(weekly_totals):
        px = osc_x0 + (i / max(1, n_weeks - 1)) * (osc_x1 - osc_x0)
        py = osc_y1 - (val / max_w) * (osc_y1 - osc_y0 - 8)
        osc_pts.append(f"{px:.1f},{py:.1f}")
        area_pts.append(f"{px:.1f},{py:.1f}")
    area_pts.append(f"{osc_x1},{osc_y1}")
    osc_polyline = " ".join(osc_pts)
    osc_area = " ".join(area_pts)

    # Build Circadian Commit Histogram (Right Bottom Panel: 24 hours BRT)
    # Panel area: x=388..645, y=218..288
    hist_x0, hist_x1 = 390, 642
    hist_y0, hist_y1 = 228, 282
    max_hr = max(max(commit_hours), 1)
    bar_w = (hist_x1 - hist_x0) / 24.0
    bars_svg = []
    for hr, count in enumerate(commit_hours):
        bh = max(2.0, (count / max_hr) * (hist_y1 - hist_y0))
        bx = hist_x0 + hr * bar_w
        by = hist_y1 - bh
        # Highlight late night (22h-04h) in cyan/purple, daytime in emerald
        if hr >= 22 or hr <= 4:
            bcol = accent_cyan if count > 0 else grid_line
        else:
            bcol = accent if count > 0 else grid_line
        bars_svg.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w - 2.2:.1f}" height="{bh:.1f}" rx="1.2" fill="{bcol}" opacity="0.9"/>'
        )

    # Workload split bar width (x=668..852)
    split_w = 180
    priv_w = (priv_pct / 100.0) * split_w

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 325" width="100%" height="100%">
  <defs>
    <linearGradient id="oscGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.42"/>
      <stop offset="100%" stop-color="{accent}" stop-opacity="0.0"/>
    </linearGradient>
    <linearGradient id="scanGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="{accent_cyan}" stop-opacity="0.0"/>
      <stop offset="50%" stop-color="{accent_cyan}" stop-opacity="0.35"/>
      <stop offset="100%" stop-color="{accent_cyan}" stop-opacity="0.0"/>
    </linearGradient>
    <clipPath id="oscClip">
      <rect x="{osc_x0}" y="{osc_y0 - 10}" width="{osc_x1 - osc_x0}" height="{osc_y1 - osc_y0 + 14}"/>
    </clipPath>
    <style>
      .mono {{ font-family: 'JetBrains Mono', 'Fira Code', 'SFMono-Regular', Consolas, monospace; }}
      .led-ok {{ animation: blinkOk 2.4s infinite ease-in-out; }}
      .led-fast {{ animation: blinkFast 1.1s infinite ease-in-out; }}
      .led-warn {{ animation: blinkWarn 1.8s infinite ease-in-out; }}
      .scanline {{ animation: sweep 5.5s infinite linear; }}
      .peak-cube {{ animation: floatPeak 3.2s infinite ease-in-out; }}
      .pulse-path {{ stroke-dasharray: 900; stroke-dashoffset: 900; animation: drawWave 3.5s ease-out forwards; }}
      @keyframes blinkOk {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} }}
      @keyframes blinkFast {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.2; }} }}
      @keyframes blinkWarn {{ 0%, 100% {{ opacity: 0.95; }} 50% {{ opacity: 0.25; }} }}
      @keyframes sweep {{
        0% {{ transform: translateX(-60px); }}
        100% {{ transform: translateX(480px); }}
      }}
      @keyframes floatPeak {{
        0%, 100% {{ filter: brightness(1.0); }}
        50% {{ filter: brightness(1.28); }}
      }}
      @keyframes drawWave {{
        to {{ stroke-dashoffset: 0; }}
      }}
    </style>
  </defs>

  <!-- Outer Rack Frame -->
  <rect x="2" y="2" width="876" height="321" rx="10" fill="{bg}" stroke="{panel_border}" stroke-width="1.5"/>

  <!-- Top Rack Status Bar -->
  <rect x="12" y="10" width="856" height="34" rx="6" fill="{panel_bg}" stroke="{panel_border}" stroke-width="1"/>
  <circle cx="28" cy="27" r="4.5" fill="{accent}" class="led-ok"/>
  <text x="40" y="31" fill="{text_main}" font-size="11.5" font-weight="bold" class="mono">BERNDOF // NOC &amp; AGENT TELEMETRY DECK v2.6</text>

  <!-- Rack Status Pills -->
  <circle cx="388" cy="27" r="3.5" fill="{accent}" class="led-fast"/>
  <text x="397" y="30.5" fill="{text_muted}" font-size="9.5" class="mono">SCC10-NOC: <tspan fill="{accent}" font-weight="bold">ONLINE</tspan></text>

  <circle cx="522" cy="27" r="3.5" fill="{accent_cyan}" class="led-ok"/>
  <text x="531" y="30.5" fill="{text_muted}" font-size="9.5" class="mono">ZABBIX-PIPE: <tspan fill="{accent_cyan}" font-weight="bold">60.0Hz</tspan></text>

  <circle cx="658" cy="27" r="3.5" fill="{accent_purple}" class="led-fast"/>
  <text x="667" y="30.5" fill="{text_muted}" font-size="9.5" class="mono">AGENTS: <tspan fill="{accent_purple}" font-weight="bold">SWARM-OK</tspan></text>

  <circle cx="782" cy="27" r="3.5" fill="{accent_warn}" class="led-warn"/>
  <text x="791" y="30.5" fill="{text_muted}" font-size="9.5" class="mono">TYPO: <tspan fill="{accent_warn}" font-weight="bold">RIP</tspan></text>

  <!-- LEFT PANEL: 3D Isometric Contribution Skyline -->
  <rect x="12" y="52" width="352" height="258" rx="7" fill="{panel_bg}" stroke="{panel_border}" stroke-width="1"/>
  <text x="24" y="71" fill="{text_main}" font-size="10.5" font-weight="bold" class="mono">3D ISOMETRIC COMMIT TOPOLOGY (52W)</text>
  <text x="24" y="85" fill="{text_muted}" font-size="9" class="mono">Total: <tspan fill="{accent}" font-weight="bold">{total_contribs}</tspan> ops across <tspan fill="{accent_cyan}" font-weight="bold">{active_days}</tspan> active days (peak: {max_day}/day)</text>

  <!-- Isometric Matrix Render -->
  <g transform="translate(0, 6)">
    {"".join(cubes_svg)}
  </g>

  <!-- Legend in Left Panel -->
  <text x="24" y="297" fill="{text_muted}" font-size="8.5" class="mono"> ELEVATION :: [0] idle  [1-2] routine  [3-6] deep-dive  [15+] 3am-rabbit-hole</text>

  <!-- RIGHT TOP PANEL: 52-Week Commit Oscilloscope -->
  <rect x="372" y="52" width="496" height="126" rx="7" fill="{panel_bg}" stroke="{panel_border}" stroke-width="1"/>
  <text x="386" y="71" fill="{text_main}" font-size="10.5" font-weight="bold" class="mono">LIVE SIGNAL OSCILLOSCOPE // WEEKLY COMMIT THROUGHPUT</text>
  <text x="735" y="71" fill="{accent}" font-size="9.5" class="mono">λ = {total_contribs} events/yr</text>

  <!-- Oscilloscope Grid Lines -->
  <line x1="{osc_x0}" y1="98" x2="{osc_x1}" y2="98" stroke="{grid_line}" stroke-width="0.8" stroke-dasharray="3,3"/>
  <line x1="{osc_x0}" y1="128" x2="{osc_x1}" y2="128" stroke="{grid_line}" stroke-width="0.8" stroke-dasharray="3,3"/>
  <line x1="{osc_x0}" y1="{osc_y1}" x2="{osc_x1}" y2="{osc_y1}" stroke="{grid_line}" stroke-width="1"/>

  <!-- Waveform + Sweeping Radar Scanline -->
  <g clip-path="url(#oscClip)">
    <polygon points="{osc_area}" fill="url(#oscGrad)"/>
    <polyline points="{osc_polyline}" fill="none" stroke="{accent}" stroke-width="2" class="pulse-path"/>
    <rect x="{osc_x0}" y="{osc_y0 - 8}" width="55" height="{osc_y1 - osc_y0 + 12}" fill="url(#scanGrad)" class="scanline"/>
  </g>

  <!-- RIGHT BOTTOM LEFT PANEL: Circadian Anomaly Detector (24h BRT) -->
  <rect x="372" y="186" width="282" height="124" rx="7" fill="{panel_bg}" stroke="{panel_border}" stroke-width="1"/>
  <text x="386" y="205" fill="{text_main}" font-size="10.5" font-weight="bold" class="mono">CIRCADIAN ANOMALY (24H BRT)</text>
  <text x="386" y="218" fill="{text_muted}" font-size="8.5" class="mono"><tspan fill="{accent_cyan}">■</tspan> Night-Owl (22h-04h)   <tspan fill="{accent}">■</tspan> Day Ops (05h-21h)</text>

  {"".join(bars_svg)}
  <line x1="{hist_x0}" y1="{hist_y1}" x2="{hist_x1}" y2="{hist_y1}" stroke="{grid_line}" stroke-width="1"/>
  <text x="390" y="296" fill="{text_muted}" font-size="8" class="mono">00h</text>
  <text x="450" y="296" fill="{text_muted}" font-size="8" class="mono">06h</text>
  <text x="510" y="296" fill="{text_muted}" font-size="8" class="mono">12h</text>
  <text x="570" y="296" fill="{text_muted}" font-size="8" class="mono">18h</text>
  <text x="622" y="296" fill="{text_muted}" font-size="8" class="mono">23h</text>

  <!-- RIGHT BOTTOM RIGHT PANEL: Domain & Org Split -->
  <rect x="662" y="186" width="206" height="124" rx="7" fill="{panel_bg}" stroke="{panel_border}" stroke-width="1"/>
  <text x="674" y="205" fill="{text_main}" font-size="10.5" font-weight="bold" class="mono">NAMESPACE ALLOCATION</text>

  <text x="674" y="224" fill="{text_muted}" font-size="9" class="mono">@gruposcc (Private):</text>
  <text x="810" y="224" fill="{accent}" font-size="9" font-weight="bold" class="mono">{priv_pct}%</text>

  <text x="674" y="239" fill="{text_muted}" font-size="9" class="mono">Public Lab / Chaos:</text>
  <text x="810" y="239" fill="{accent_cyan}" font-size="9" font-weight="bold" class="mono">{pub_pct}%</text>

  <!-- Split Progress Bar -->
  <rect x="674" y="248" width="{split_w}" height="9" rx="4" fill="{accent_cyan}" opacity="0.85"/>
  <rect x="674" y="248" width="{priv_w:.1f}" height="9" rx="4" fill="{accent}"/>

  <!-- Mini System Diagnostics Telemetry -->
  <text x="674" y="274" fill="{text_muted}" font-size="8.5" class="mono">PRIVATE OPS :: <tspan fill="{text_main}" font-weight="bold">{private_contribs} commits</tspan></text>
  <text x="674" y="287" fill="{text_muted}" font-size="8.5" class="mono">PUBLIC LAB  :: <tspan fill="{text_main}" font-weight="bold">{public_commits} commits</tspan></text>
  <text x="674" y="300" fill="{text_muted}" font-size="8.5" class="mono">MONTE CARLO :: <tspan fill="{accent_warn}" font-weight="bold">30,000 runs</tspan></text>
</svg>
"""
    return svg


def main():
    os.makedirs("dist", exist_ok=True)
    user_data = fetch_data()
    commit_hours = fetch_commit_hours()

    dark_svg = generate_svg(user_data, commit_hours, mode="dark")
    light_svg = generate_svg(user_data, commit_hours, mode="light")

    with open("dist/noc-telemetry-dark.svg", "w", encoding="utf-8") as f:
        f.write(dark_svg)
    with open("dist/noc-telemetry-light.svg", "w", encoding="utf-8") as f:
        f.write(light_svg)
    print("Generated dist/noc-telemetry-dark.svg and dist/noc-telemetry-light.svg successfully.")


if __name__ == "__main__":
    main()
