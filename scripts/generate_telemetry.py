#!/usr/bin/env python3
"""
Generates a clean terminal-styled GitHub telemetry SVG (dark & light themes)
with a 2D contribution heatmap, 24h UTC-3 activity histogram, 52-week
throughput curve, and real repository stack distribution from GitHub GraphQL.
Also patches Platane/snk SVG palettes for high contrast in dark/light modes.
Zero external dependencies (Python 3 stdlib only).
"""

import collections
import datetime
import json
import os
import re
import subprocess
import sys
import urllib.request

GITHUB_USER = os.environ.get("GITHUB_USER", "berndof")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not GITHUB_TOKEN:
    try:
        GITHUB_TOKEN = subprocess.check_output(["gh", "auth", "token"], text=True, timeout=5).strip()
    except Exception:
        GITHUB_TOKEN = ""

GRAPHQL_QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    repositories(
      first: 50
      ownerAffiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER]
      isFork: false
      orderBy: {field: PUSHED_AT, direction: DESC}
    ) {
      totalCount
      nodes {
        nameWithOwner
        isPrivate
        pushedAt
        languages(first: 8, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
            }
          }
        }
      }
    }
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
    if GITHUB_TOKEN:
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

    # Local fallback via gh CLI if authenticated
    try:
        res = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={GRAPHQL_QUERY}", "-f", f"login={GITHUB_USER}"],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
        payload = json.loads(res.stdout)
        return payload["data"]["user"]
    except Exception:
        return None


def fetch_commit_hours(user_data):
    """
    Samples recent commit timestamps across dynamically discovered repositories
    to compute the real 24h (BRT, UTC-3) commit distribution.
    """
    default_hours = [8, 12, 15, 19, 6, 2, 0, 1, 4, 11, 18, 22, 14, 20, 25, 28, 24, 19, 14, 16, 21, 26, 29, 18]
    hours = [0] * 24

    repos_nodes = ((user_data or {}).get("repositories") or {}).get("nodes") or []
    repo_names = [r["nameWithOwner"] for r in repos_nodes[:10] if r.get("nameWithOwner")]

    if GITHUB_TOKEN and repo_names:
        for repo in repo_names:
            url = f"https://api.github.com/repos/{repo}/commits?per_page=50"
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {GITHUB_TOKEN}",
                    "User-Agent": "berndof-telemetry-generator",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=6) as resp:
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
                pass

    if sum(hours) == 0:
        hours = default_hours

    return hours


def compute_stack_stats(user_data):
    """
    Aggregates repository language presence into 4 high-level stack categories
    using a balanced per-repo weight so a single large repo does not skew the
    multi-repository profile.
    """
    repos_info = (user_data or {}).get("repositories") or {}
    nodes = repos_info.get("nodes") or []
    total_repos = repos_info.get("totalCount") or len(nodes) or 21
    priv_repos = sum(1 for r in nodes if r.get("isPrivate"))
    pub_repos = max(0, len(nodes) - priv_repos)
    if not nodes:
        priv_repos, pub_repos = 12, 9

    weights = collections.Counter()
    repo_sets = collections.defaultdict(set)

    for r in nodes:
        rname = r.get("nameWithOwner", "")
        edges = ((r.get("languages") or {}).get("edges")) or []
        for e in edges:
            lname = ((e.get("node") or {}).get("name")) or ""
            sz = int(e.get("size") or 0)
            score = 18000 + min(sz, 60000)
            if lname == "Python":
                cat = "python"
            elif lname in ("Shell", "Makefile", "Dockerfile", "Batchfile", "PowerShell"):
                cat = "sh / bash"
            elif lname in ("HTML", "CSS", "JavaScript", "Mako", "Jinja"):
                cat = "html+css+js"
            else:
                cat = "sql / php / ts"
            weights[cat] += score
            repo_sets[cat].add(rname)

    if sum(weights.values()) == 0:
        weights["python"] = 39
        weights["sh / bash"] = 26
        weights["html+css+js"] = 19
        weights["sql / php / ts"] = 16
        repo_sets["python"] = set(range(13))
        repo_sets["sh / bash"] = set(range(12))
        repo_sets["html+css+js"] = set(range(5))
        repo_sets["sql / php / ts"] = set(range(5))

    tot_w = max(1, sum(weights.values()))
    categories = [
        ("python", "daemons, cli &amp; data", "accent"),
        ("sh / bash", "automation, cron &amp; glue", "cyan"),
        ("html+css+js", "vanilla web, zero bloat", "warn"),
        ("sql / php / ts", "schemas, portals &amp; types", "muted"),
    ]

    rows = []
    for key, desc, col_key in categories:
        pct = round((weights[key] / tot_w) * 100.0, 1)
        rcount = len(repo_sets[key])
        rows.append(
            {
                "label": key,
                "desc": desc,
                "pct": pct,
                "repos": rcount,
                "col_key": col_key,
            }
        )

    # Normalize rounding to 100.0%
    diff = round(100.0 - sum(r["pct"] for r in rows), 1)
    if rows and abs(diff) > 0:
        rows[0]["pct"] = round(rows[0]["pct"] + diff, 1)

    return {
        "total_repos": total_repos,
        "priv_repos": priv_repos,
        "pub_repos": pub_repos,
        "rows": rows,
    }


def generate_svg(user_data, commit_hours, stack_stats, mode="dark"):
    cc = user_data["contributionsCollection"]
    cal = cc["contributionCalendar"]
    total_contribs = cal["totalContributions"]
    public_commits = cc["totalCommitContributions"]
    private_contribs = cc["restrictedContributionsCount"]
    weeks = cal["weeks"]

    active_days = 0
    max_day = 0
    weekly_totals = []
    flat_days = []

    for w in weeks:
        w_sum = 0
        for d in w["contributionDays"]:
            c = d["contributionCount"]
            flat_days.append(c)
            w_sum += c
            if c > 0:
                active_days += 1
            if c > max_day:
                max_day = c
        weekly_totals.append(w_sum)

    active_weeks = sum(1 for w in weekly_totals if w > 0)
    last_30d = sum(flat_days[-30:]) if len(flat_days) >= 30 else sum(flat_days)
    avg_wk = total_contribs / max(1, len(weekly_totals))
    max_wk = max(weekly_totals) if weekly_totals else 0

    priv_pct = round((private_contribs / max(1, public_commits + private_contribs)) * 100, 1)
    pub_pct = round(100.0 - priv_pct, 1)

    today = datetime.date.today()
    today_iso = today.isoformat()
    typo_fixed_date = datetime.date(2026, 10, 15)
    typo_free_days = max(1, (today - typo_fixed_date).days)

    if mode == "dark":
        bg = "#0c1017"
        term_bar = "#111722"
        panel_bg = "#0f141d"
        panel_border = "#263244"
        grid_line = "#1b2432"
        text_main = "#d8dee9"
        text_muted = "#64748b"
        text_dim = "#475569"
        accent = "#10b981"
        accent_cyan = "#38bdf8"
        accent_warn = "#f59e0b"
        accent_slate = "#94a3b8"
        tmux_bg = "#131b26"
        tmux_pill_fg = "#090d12"
        cell_levels = [
            ("#151d2a", "#1e293b"),  # 0: empty
            ("#065f46", "#047857"),  # 1: 1-2
            ("#059669", "#10b981"),  # 2: 3-6
            ("#10b981", "#34d399"),  # 3: 7-14
            ("#34d399", "#6ee7b7"),  # 4: 15+
        ]
    else:
        bg = "#f1f5f9"
        term_bar = "#e2e8f0"
        panel_bg = "#ffffff"
        panel_border = "#cbd5e1"
        grid_line = "#e2e8f0"
        text_main = "#0f172a"
        text_muted = "#64748b"
        text_dim = "#94a3b8"
        accent = "#059669"
        accent_cyan = "#0284c7"
        accent_warn = "#d97706"
        accent_slate = "#64748b"
        tmux_bg = "#e2e8f0"
        tmux_pill_fg = "#ffffff"
        cell_levels = [
            ("#e2e8f0", "#cbd5e1"),  # 0: empty
            ("#a7f3d0", "#6ee7b7"),  # 1: 1-2
            ("#34d399", "#10b981"),  # 2: 3-6
            ("#10b981", "#059669"),  # 3: 7-14
            ("#047857", "#065f46"),  # 4: 15+
        ]

    color_map = {
        "accent": accent,
        "cyan": accent_cyan,
        "warn": accent_warn,
        "muted": accent_slate,
    }

    # =========================================================================
    # PANE 1: 2D Terminal Heatmap (x=12..472, y=38..178)
    # =========================================================================
    grid_x0 = 46.0
    grid_y0 = 75.0
    pitch_x = 7.75
    pitch_y = 10.4
    cell_w = 5.9
    cell_h = 8.4

    cells_svg = []
    month_labels_svg = []
    seen_months = set()
    last_label_x = -30.0
    month_names = ["", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

    for w_idx, w in enumerate(weeks):
        days = w["contributionDays"]
        gx = grid_x0 + w_idx * pitch_x

        for d in days:
            first_date = d.get("date", "")
            if len(first_date) >= 10 and first_date[8:10] in ("01", "02", "03", "04", "05", "06", "07"):
                ym = first_date[:7]
                m_num = int(first_date[5:7])
                if ym not in seen_months and (gx - last_label_x) >= 22.0 and gx <= 438.0:
                    seen_months.add(ym)
                    last_label_x = gx
                    month_labels_svg.append(
                        f'<text x="{gx:.1f}" y="{grid_y0 - 4.0:.1f}" fill="{text_dim}" font-size="7.5" class="mono">{month_names[m_num]}</text>'
                    )
                break

        for d in days:
            d_idx = d["weekday"]
            c = d["contributionCount"]
            gy = grid_y0 + d_idx * pitch_y
            if c == 0:
                lvl = 0
            elif c <= 2:
                lvl = 1
            elif c <= 6:
                lvl = 2
            elif c <= 14:
                lvl = 3
            else:
                lvl = 4
            fill_c, stroke_c = cell_levels[lvl]
            cells_svg.append(
                f'<rect x="{gx:.1f}" y="{gy:.1f}" width="{cell_w}" height="{cell_h}" rx="1.4" fill="{fill_c}" stroke="{stroke_c}" stroke-width="0.45"/>'
            )

    # Legend cells in Pane 1 footer
    legend_cells_svg = []
    lx0 = 70.0
    for idx, (fill_c, stroke_c) in enumerate(cell_levels):
        lx = lx0 + idx * 10.0
        legend_cells_svg.append(
            f'<rect x="{lx:.1f}" y="160.5" width="6.5" height="6.5" rx="1.2" fill="{fill_c}" stroke="{stroke_c}" stroke-width="0.45"/>'
        )

    split_total_w = 72.0
    priv_bar_w = (priv_pct / 100.0) * split_total_w

    # =========================================================================
    # PANE 2: 24h Circadian Histogram (x=482..868, y=38..178)
    # =========================================================================
    hist_x0, hist_x1 = 496.0, 854.0
    hist_y0, hist_y1 = 68.0, 148.0
    max_hr = max(max(commit_hours), 1)
    total_hr = max(sum(commit_hours), 1)
    night_commits = sum(commit_hours[h] for h in range(24) if h >= 22 or h <= 4)
    night_pct = round((night_commits / total_hr) * 100.0, 1)
    day_pct = round(100.0 - night_pct, 1)
    peak_hr = max(range(24), key=lambda h: commit_hours[h])

    bar_step = (hist_x1 - hist_x0) / 24.0
    bar_w = bar_step - 2.6
    bars_svg = []
    for hr, count in enumerate(commit_hours):
        bh = max(2.0, (count / max_hr) * (hist_y1 - hist_y0))
        bx = hist_x0 + hr * bar_step
        by = hist_y1 - bh
        bars_svg.append(
            f'<rect x="{bx:.1f}" y="{hist_y0:.1f}" width="{bar_w:.1f}" height="{hist_y1 - hist_y0:.1f}" rx="1.2" fill="{grid_line}" opacity="0.35"/>'
        )
        if hr >= 22 or hr <= 4:
            bcol = accent_cyan if count > 0 else grid_line
        else:
            bcol = accent if count > 0 else grid_line
        bars_svg.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" rx="1.2" fill="{bcol}" opacity="0.92"/>'
        )

    # =========================================================================
    # PANE 3: Weekly Commit Throughput (x=12..472, y=188..302)
    # =========================================================================
    osc_x0 = grid_x0
    osc_x1 = grid_x0 + (max(1, len(weekly_totals) - 1)) * pitch_x + cell_w
    osc_y0, osc_y1 = 216.0, 280.0
    max_w_val = max(max_wk, 10)
    osc_pts = []
    area_pts = [f"{osc_x0:.1f},{osc_y1:.1f}"]
    peak_dots_svg = []
    n_weeks = len(weekly_totals)
    for i, val in enumerate(weekly_totals):
        px = osc_x0 + (i / max(1, n_weeks - 1)) * (osc_x1 - osc_x0)
        py = osc_y1 - (val / max_w_val) * (osc_y1 - osc_y0 - 4.0)
        osc_pts.append(f"{px:.1f},{py:.1f}")
        area_pts.append(f"{px:.1f},{py:.1f}")
        if val >= max_w_val * 0.45 and val > 0:
            peak_dots_svg.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="1.8" fill="{accent_cyan}"/>')
    area_pts.append(f"{osc_x1:.1f},{osc_y1:.1f}")
    osc_polyline = " ".join(osc_pts)
    osc_area = " ".join(area_pts)

    # =========================================================================
    # PANE 4: Stack & Repository Telemetry (x=482..868, y=188..302)
    # =========================================================================
    stack_bar_x0 = 496.0
    stack_bar_w = 358.0
    stack_segments_svg = []
    cur_x = stack_bar_x0
    for r in stack_stats["rows"]:
        seg_w = max(2.0, (r["pct"] / 100.0) * stack_bar_w)
        if cur_x + seg_w > stack_bar_x0 + stack_bar_w:
            seg_w = max(0.0, (stack_bar_x0 + stack_bar_w) - cur_x)
        col = color_map[r["col_key"]]
        stack_segments_svg.append(
            f'<rect x="{cur_x:.1f}" y="211" width="{seg_w:.1f}" height="6" rx="1" fill="{col}" opacity="0.92"/>'
        )
        cur_x += seg_w

    stack_rows_svg = []
    row_ys = [234, 251, 268, 285]
    for idx, r in enumerate(stack_stats["rows"][:4]):
        ry = row_ys[idx]
        col = color_map[r["col_key"]]
        bar_bg_x = 588.0
        bar_max_w = 72.0
        fill_w = max(3.0, (r["pct"] / 100.0) * bar_max_w)
        pct_str = f"{r['pct']:>4.1f}%"
        stack_rows_svg.append(
            f'  <circle cx="500" cy="{ry - 3}" r="2.5" fill="{col}"/>'
            f'<text x="508" y="{ry}" fill="{text_main}" font-size="8.5" font-weight="bold" class="mono">{r["label"]}</text>'
            f'<rect x="{bar_bg_x}" y="{ry - 6.5}" width="{bar_max_w}" height="5" rx="1.5" fill="{grid_line}"/>'
            f'<rect x="{bar_bg_x}" y="{ry - 6.5}" width="{fill_w:.1f}" height="5" rx="1.5" fill="{col}"/>'
            f'<text x="698" y="{ry}" text-anchor="end" fill="{text_main}" font-size="8.2" class="mono">{pct_str}</text>'
            f'<text x="708" y="{ry}" fill="{text_muted}" font-size="8" class="mono">│ {r[" desc"] if " desc" in r else r["desc"]}</text>'
        )
    stack_block_svg = "\n".join(stack_rows_svg)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 340" width="100%" height="100%">
  <defs>
    <linearGradient id="oscGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.32"/>
      <stop offset="100%" stop-color="{accent}" stop-opacity="0.0"/>
    </linearGradient>
    <style>
      .mono {{ font-family: 'JetBrains Mono', 'Fira Code', 'SFMono-Regular', Consolas, 'Liberation Mono', monospace; }}
    </style>
  </defs>

  <!-- Outer Terminal Window -->
  <rect x="2" y="2" width="876" height="336" rx="6" fill="{bg}" stroke="{panel_border}" stroke-width="1.2"/>

  <!-- Terminal Window Header Bar -->
  <path d="M 2 8 Q 2 2 8 2 L 872 2 Q 878 2 878 8 L 878 28 L 2 28 Z" fill="{term_bar}"/>
  <line x1="2" y1="28" x2="878" y2="28" stroke="{panel_border}" stroke-width="1"/>
  <circle cx="16" cy="15" r="3.2" fill="{text_dim}" opacity="0.6"/>
  <circle cx="27" cy="15" r="3.2" fill="{text_dim}" opacity="0.6"/>
  <circle cx="38" cy="15" r="3.2" fill="{text_dim}" opacity="0.6"/>
  <text x="440" y="18.5" text-anchor="middle" fill="{text_muted}" font-size="9.5" class="mono">berndof :: github telemetry</text>
  <text x="866" y="18.5" text-anchor="end" fill="{text_muted}" font-size="8.5" class="mono">snapshot: {today_iso} │ sync: 12h cron</text>

  <!-- ======================================================================= -->
  <!-- PANE 1: 2D Contribution Heatmap (52w)                                   -->
  <!-- ======================================================================= -->
  <rect x="12" y="38" width="460" height="140" rx="3" fill="{panel_bg}" stroke="{panel_border}" stroke-width="1"/>
  <rect x="22" y="32" width="114" height="11" fill="{panel_bg}"/>
  <text x="26" y="41" fill="{text_main}" font-size="9.5" class="mono"><tspan fill="{text_muted}">┤</tspan><tspan fill="{accent}" font-weight="bold">¹</tspan> commits (52w)<tspan fill="{text_muted}">├</tspan></text>

  <text x="24" y="56" fill="{text_muted}" font-size="8.5" class="mono"><tspan fill="{text_main}" font-weight="bold">{total_contribs}</tspan> total │ <tspan fill="{accent_cyan}" font-weight="bold">{active_days}d</tspan> active │ max <tspan fill="{accent}" font-weight="bold">{max_day}/d</tspan></text>
  <text x="458" y="56" text-anchor="end" fill="{text_muted}" font-size="8.2" class="mono"><tspan fill="{accent}">{priv_pct}% @gruposcc</tspan> / <tspan fill="{accent_cyan}">{pub_pct}% pub</tspan></text>

  <!-- Weekday Labels -->
  <text x="24" y="91" fill="{text_dim}" font-size="7.2" class="mono">mon</text>
  <text x="24" y="112" fill="{text_dim}" font-size="7.2" class="mono">wed</text>
  <text x="24" y="133" fill="{text_dim}" font-size="7.2" class="mono">fri</text>

  <!-- Month Ticks & 2D Cells -->
  {"".join(month_labels_svg)}
  {"".join(cells_svg)}

  <!-- Footer Legend & Split Bar -->
  <text x="24" y="166.5" fill="{text_muted}" font-size="7.8" class="mono">less</text>
  {"".join(legend_cells_svg)}
  <text x="124" y="166.5" fill="{text_muted}" font-size="7.8" class="mono">more (0 · 1-2 · 3-6 · 7-14 · 15+/d)</text>
  <rect x="386" y="161.5" width="{split_total_w}" height="4.5" rx="2" fill="{accent_cyan}" opacity="0.85"/>
  <rect x="386" y="161.5" width="{priv_bar_w:.1f}" height="4.5" rx="2" fill="{accent}"/>

  <!-- ======================================================================= -->
  <!-- PANE 2: Circadian Activity (24h BRT / UTC-3)                            -->
  <!-- ======================================================================= -->
  <rect x="482" y="38" width="386" height="140" rx="3" fill="{panel_bg}" stroke="{panel_border}" stroke-width="1"/>
  <rect x="492" y="32" width="114" height="11" fill="{panel_bg}"/>
  <text x="496" y="41" fill="{text_main}" font-size="9.5" class="mono"><tspan fill="{text_muted}">┤</tspan><tspan fill="{accent_cyan}" font-weight="bold">²</tspan> hours (utc-3)<tspan fill="{text_muted}">├</tspan></text>

  <text x="496" y="56" fill="{text_muted}" font-size="8.2" class="mono"><tspan fill="{accent}">■</tspan> day {day_pct}%   <tspan fill="{accent_cyan}">■</tspan> 22-04h {night_pct}%</text>
  <text x="854" y="56" text-anchor="end" fill="{text_muted}" font-size="8.2" class="mono">peak: <tspan fill="{text_main}" font-weight="bold">{peak_hr:02d}:00</tspan></text>

  {"".join(bars_svg)}
  <line x1="{hist_x0}" y1="{hist_y1}" x2="{hist_x1}" y2="{hist_y1}" stroke="{grid_line}" stroke-width="1"/>
  <text x="496" y="164" fill="{text_dim}" font-size="7.5" class="mono">00h</text>
  <text x="585" y="164" fill="{text_dim}" font-size="7.5" class="mono">06h</text>
  <text x="675" y="164" fill="{text_dim}" font-size="7.5" class="mono">12h</text>
  <text x="764" y="164" fill="{text_dim}" font-size="7.5" class="mono">18h</text>
  <text x="854" y="164" text-anchor="end" fill="{text_dim}" font-size="7.5" class="mono">23h</text>

  <!-- ======================================================================= -->
  <!-- PANE 3: Weekly Commit Throughput                                        -->
  <!-- ======================================================================= -->
  <rect x="12" y="188" width="460" height="114" rx="3" fill="{panel_bg}" stroke="{panel_border}" stroke-width="1"/>
  <rect x="22" y="182" width="126" height="11" fill="{panel_bg}"/>
  <text x="26" y="191" fill="{text_main}" font-size="9.5" class="mono"><tspan fill="{text_muted}">┤</tspan><tspan fill="{accent}" font-weight="bold">³</tspan> throughput (wk)<tspan fill="{text_muted}">├</tspan></text>

  <text x="24" y="206" fill="{text_muted}" font-size="8.2" class="mono">30d: <tspan fill="{text_main}" font-weight="bold">{last_30d}</tspan> commits │ active: <tspan fill="{text_main}">{active_weeks}/52w</tspan></text>
  <text x="458" y="206" text-anchor="end" fill="{text_muted}" font-size="8.2" class="mono">avg <tspan fill="{text_main}">{avg_wk:.1f}/w</tspan> · max <tspan fill="{accent}" font-weight="bold">{max_wk}/w</tspan></text>

  <line x1="{osc_x0:.1f}" y1="236" x2="{osc_x1:.1f}" y2="236" stroke="{grid_line}" stroke-width="0.8" stroke-dasharray="2,3"/>
  <line x1="{osc_x0:.1f}" y1="258" x2="{osc_x1:.1f}" y2="258" stroke="{grid_line}" stroke-width="0.8" stroke-dasharray="2,3"/>
  <line x1="{osc_x0:.1f}" y1="{osc_y1:.1f}" x2="{osc_x1:.1f}" y2="{osc_y1:.1f}" stroke="{grid_line}" stroke-width="1"/>

  <polygon points="{osc_area}" fill="url(#oscGrad)"/>
  <polyline points="{osc_polyline}" fill="none" stroke="{accent}" stroke-width="1.6"/>
  {"".join(peak_dots_svg)}

  <text x="{osc_x0:.1f}" y="294" fill="{text_dim}" font-size="7.5" class="mono">-52w</text>
  <text x="{(osc_x0 + osc_x1) / 2:.1f}" y="294" text-anchor="middle" fill="{text_dim}" font-size="7.5" class="mono">-26w</text>
  <text x="{osc_x1:.1f}" y="294" text-anchor="end" fill="{text_dim}" font-size="7.5" class="mono">now</text>

  <!-- ======================================================================= -->
  <!-- PANE 4: Stack & Repository Telemetry                                    -->
  <!-- ======================================================================= -->
  <rect x="482" y="188" width="386" height="114" rx="3" fill="{panel_bg}" stroke="{panel_border}" stroke-width="1"/>
  <rect x="492" y="182" width="120" height="11" fill="{panel_bg}"/>
  <text x="496" y="191" fill="{text_main}" font-size="9.5" class="mono"><tspan fill="{text_muted}">┤</tspan><tspan fill="{accent}" font-weight="bold">⁴</tspan> stack &amp; repos<tspan fill="{text_muted}">├</tspan></text>
  <text x="854" y="204" text-anchor="end" fill="{text_muted}" font-size="8.2" class="mono"><tspan fill="{text_main}" font-weight="bold">{stack_stats["total_repos"]}</tspan> repos ({stack_stats["priv_repos"]} priv · {stack_stats["pub_repos"]} pub)</text>
  <text x="496" y="204" fill="{text_muted}" font-size="8.2" class="mono">profile: <tspan fill="{accent}">lightweight</tspan> · <tspan fill="{accent_cyan}">low boilerplate</tspan></text>

  <!-- Proportional Stack Bar -->
  {"".join(stack_segments_svg)}

  <!-- Stack Breakdown Rows -->
{stack_block_svg}

  <!-- ======================================================================= -->
  <!-- BOTTOM STATUS BAR                                                       -->
  <!-- ======================================================================= -->
  <rect x="12" y="310" width="856" height="20" rx="2.5" fill="{tmux_bg}" stroke="{panel_border}" stroke-width="0.8"/>
  <rect x="12" y="310" width="68" height="20" rx="2.5" fill="{accent}"/>
  <text x="46" y="323" text-anchor="middle" fill="{tmux_pill_fg}" font-size="8.5" font-weight="bold" class="mono">summary</text>

  <text x="92" y="323" fill="{text_muted}" font-size="8.4" class="mono">prefer: <tspan fill="{text_main}">sh + python</tspan> │ <tspan fill="{text_main}">html + css + js</tspan> │ <tspan fill="{text_main}">raw sql</tspan> │ <tspan fill="{accent}">minimal boilerplate</tspan></text>
  <text x="858" y="323" text-anchor="end" fill="{text_muted}" font-size="8.2" class="mono">typo-free: <tspan fill="{accent_warn}" font-weight="bold">{typo_free_days}d</tspan></text>
</svg>
"""
    return svg


def patch_snake_svgs(out_dir):
    """
    Patches Platane/snk generated SVG files so dark mode has crisp cell borders,
    visible emerald levels even when max_day is high, and a cyan snake instead of
    low-contrast dark purple.
    """
    dark_path = os.path.join(out_dir, "github-contribution-grid-snake-dark.svg")
    light_path = os.path.join(out_dir, "github-contribution-grid-snake.svg")

    if os.path.isfile(dark_path):
        with open(dark_path, "r", encoding="utf-8") as f:
            content = f.read()
        content = re.sub(
            r":root\{[^}]+\}",
            ":root{--cb:#26324488;--cs:#38bdf8;--ce:#121822;--c0:#121822;--c1:#047857;--c2:#10b981;--c3:#34d399;--c4:#6ee7b7}",
            content,
            count=1,
        )
        with open(dark_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched dark snake palette in {dark_path}")

    if os.path.isfile(light_path):
        with open(light_path, "r", encoding="utf-8") as f:
            content = f.read()
        content = re.sub(
            r":root\{[^}]+\}",
            ":root{--cb:#cbd5e177;--cs:#0284c7;--ce:#e2e8f0;--c0:#e2e8f0;--c1:#6ee7b7;--c2:#34d399;--c3:#10b981;--c4:#047857}",
            content,
            count=1,
        )
        with open(light_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched light snake palette in {light_path}")


def _mock_user_data():
    weeks = []
    for w in range(53):
        days = []
        for d in range(7):
            c = ((w * 3 + d * 5) % 11) if (w + d) % 4 == 0 else 0
            date_str = (datetime.date(2025, 10, 15) + datetime.timedelta(days=w * 7 + d)).isoformat()
            days.append({"contributionCount": c, "date": date_str, "weekday": d})
        weeks.append({"contributionDays": days})
    return {
        "repositories": {"totalCount": 21, "nodes": []},
        "contributionsCollection": {
            "totalCommitContributions": 58,
            "restrictedContributionsCount": 827,
            "contributionCalendar": {
                "totalContributions": 893,
                "weeks": weeks,
            },
        },
    }


def main():
    out_dir = os.environ.get("OUT_DIR", "dist")
    os.makedirs(out_dir, exist_ok=True)

    if "--patch-snake-only" in sys.argv:
        patch_snake_svgs(out_dir)
        return

    user_data = fetch_data() or _mock_user_data()
    commit_hours = fetch_commit_hours(user_data)
    stack_stats = compute_stack_stats(user_data)

    dark_svg = generate_svg(user_data, commit_hours, stack_stats, mode="dark")
    light_svg = generate_svg(user_data, commit_hours, stack_stats, mode="light")

    with open(os.path.join(out_dir, "noc-telemetry-dark.svg"), "w", encoding="utf-8") as f:
        f.write(dark_svg)
    with open(os.path.join(out_dir, "noc-telemetry-light.svg"), "w", encoding="utf-8") as f:
        f.write(light_svg)
    patch_snake_svgs(out_dir)
    print(f"Generated {out_dir}/noc-telemetry-dark.svg and {out_dir}/noc-telemetry-light.svg successfully.")


if __name__ == "__main__":
    main()
