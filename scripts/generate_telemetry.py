#!/usr/bin/env python3
"""
Generates:
1. noc-telemetry-{dark,light}.svg — 2x2 symmetrical terminal telemetry deck:
   - Pane 1: 2D square-cell contribution matrix (52w)
   - Pane 2: 24h circadian commit histogram (UTC-3)
   - Pane 3: 52-week commit throughput oscilloscope (same size & X-axis as Pane 1)
   - Pane 4: Commit-weighted stack & repository telemetry (auto-updates from commits)
2. noc-pipeline-{dark,light}.svg — NOC-styled architecture & philosophy pipeline diagram
3. Patches Platane/snk SVG palettes for high contrast in dark & light themes.

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
import xml.etree.ElementTree as ET

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
      first: 35
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
        defaultBranchRef {
          target {
            ... on Commit {
              history(first: 60) {
                nodes {
                  committedDate
                  author {
                    email
                    user {
                      login
                    }
                  }
                }
              }
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
        with urllib.request.urlopen(req, timeout=25) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload["data"]["user"]

    try:
        res = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={GRAPHQL_QUERY}", "-f", f"login={GITHUB_USER}"],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
        payload = json.loads(res.stdout)
        return payload["data"]["user"]
    except Exception:
        return None


def analyze_repos_and_commits(user_data):
    """
    Extracts from the single GraphQL response:
    1. 24h commit distribution in BRT (UTC-3)
    2. Commit-weighted language/stack distribution across active repositories
       (automatically shifts as new commits are pushed to any repo).
    """
    default_hours = [8, 12, 15, 19, 6, 2, 0, 1, 4, 11, 18, 22, 14, 20, 25, 28, 24, 19, 14, 16, 21, 26, 29, 18]
    hours = [0] * 24

    repos_info = (user_data or {}).get("repositories") or {}
    nodes = repos_info.get("nodes") or []
    total_repos = repos_info.get("totalCount") or len(nodes) or 22
    priv_repos = sum(1 for r in nodes if r.get("isPrivate"))
    pub_repos = max(0, len(nodes) - priv_repos)
    if not nodes:
        priv_repos, pub_repos = 12, 10

    cat_commit_weights = collections.Counter()
    cat_repos = collections.defaultdict(set)
    active_repos_count = 0

    for r in nodes:
        rname = r.get("nameWithOwner", "")
        edges = ((r.get("languages") or {}).get("edges")) or []
        hist_nodes = (
            (((r.get("defaultBranchRef") or {}).get("target") or {}).get("history") or {}).get("nodes") or []
        )

        my_commits = 0
        for c in hist_nodes:
            author = c.get("author") or {}
            login = ((author.get("user") or {}).get("login") or "").lower()
            email = (author.get("email") or "").lower()
            if login == GITHUB_USER.lower() or "berndof" in email or "bernardo" in email:
                my_commits += 1
                date_str = c.get("committedDate") or ""
                if date_str:
                    try:
                        dt = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        brt_hour = (dt.hour - 3) % 24
                        hours[brt_hour] += 1
                    except Exception:
                        pass

        # Map repository languages to the 4 stack buckets
        repo_lang_scores = collections.Counter()
        for e in edges:
            lname = ((e.get("node") or {}).get("name")) or ""
            sz = int(e.get("size") or 0)
            score = min(sz, 75000) + 6000
            if lname == "Python":
                cat = "python"
            elif lname in ("Shell", "Makefile", "Dockerfile", "Batchfile", "PowerShell"):
                cat = "sh / bash"
            elif lname in ("HTML", "CSS", "JavaScript", "Mako", "Jinja"):
                cat = "html+css+js"
            else:
                cat = "sql / php / ts"
            repo_lang_scores[cat] += score
            cat_repos[cat].add(rname)

        if my_commits > 0 and repo_lang_scores:
            active_repos_count += 1
            tot_repo_score = sum(repo_lang_scores.values()) or 1
            for cat, sc in repo_lang_scores.items():
                # Weight each repo's language share by the user's commits in that repo
                cat_commit_weights[cat] += my_commits * (sc / tot_repo_score)

    if sum(hours) == 0:
        hours = default_hours

    if sum(cat_commit_weights.values()) == 0:
        cat_commit_weights["python"] = 37.4
        cat_commit_weights["sh / bash"] = 26.9
        cat_commit_weights["html+css+js"] = 22.2
        cat_commit_weights["sql / php / ts"] = 13.5
        cat_repos["python"] = set(range(13))
        cat_repos["sh / bash"] = set(range(12))
        cat_repos["html+css+js"] = set(range(5))
        cat_repos["sql / php / ts"] = set(range(5))
        active_repos_count = 20

    meta = {
        "python": ("daemons, cli &amp; data", "accent"),
        "sh / bash": ("automation, cron &amp; glue", "cyan"),
        "html+css+js": ("vanilla web, zero bloat", "warn"),
        "sql / php / ts": ("schemas, portals &amp; types", "muted"),
    }

    tot_w = sum(cat_commit_weights.values()) or 1.0
    rows = []
    for key in ("python", "sh / bash", "html+css+js", "sql / php / ts"):
        pct = round((cat_commit_weights[key] / tot_w) * 100.0, 1)
        desc, col_key = meta[key]
        rows.append(
            {
                "label": key,
                "desc": desc,
                "pct": pct,
                "repos": len(cat_repos[key]),
                "col_key": col_key,
            }
        )

    # Sort dynamically by commit-weighted share so most active stack is on top
    rows.sort(key=lambda r: r["pct"], reverse=True)
    diff = round(100.0 - sum(r["pct"] for r in rows), 1)
    if rows and abs(diff) > 0:
        rows[0]["pct"] = round(rows[0]["pct"] + diff, 1)

    stack_stats = {
        "total_repos": total_repos,
        "priv_repos": priv_repos,
        "pub_repos": pub_repos,
        "active_repos": active_repos_count,
        "rows": rows,
    }
    return hours, stack_stats


def _palette(mode):
    if mode == "dark":
        return {
            "bg": "#0c1017",
            "term_bar": "#111722",
            "panel_bg": "#0f141d",
            "panel_border": "#263244",
            "grid_line": "#1b2432",
            "text_main": "#d8dee9",
            "text_muted": "#64748b",
            "text_dim": "#475569",
            "accent": "#10b981",
            "cyan": "#38bdf8",
            "warn": "#f59e0b",
            "muted": "#94a3b8",
            "tmux_bg": "#131b26",
            "tmux_pill_fg": "#090d12",
            "cells": [
                ("#151d2a", "#1e293b"),  # 0: empty
                ("#065f46", "#047857"),  # 1: 1-2
                ("#059669", "#10b981"),  # 2: 3-6
                ("#10b981", "#34d399"),  # 3: 7-14
                ("#34d399", "#6ee7b7"),  # 4: 15+
            ],
        }
    return {
        "bg": "#f1f5f9",
        "term_bar": "#e2e8f0",
        "panel_bg": "#ffffff",
        "panel_border": "#cbd5e1",
        "grid_line": "#e2e8f0",
        "text_main": "#0f172a",
        "text_muted": "#64748b",
        "text_dim": "#94a3b8",
        "accent": "#059669",
        "cyan": "#0284c7",
        "warn": "#d97706",
        "muted": "#64748b",
        "tmux_bg": "#e2e8f0",
        "tmux_pill_fg": "#ffffff",
        "cells": [
            ("#e2e8f0", "#cbd5e1"),  # 0: empty
            ("#a7f3d0", "#6ee7b7"),  # 1: 1-2
            ("#34d399", "#10b981"),  # 2: 3-6
            ("#10b981", "#059669"),  # 3: 7-14
            ("#047857", "#065f46"),  # 4: 15+
        ],
    }


def generate_telemetry_svg(user_data, commit_hours, stack_stats, mode="dark"):
    p = _palette(mode)
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

    # =========================================================================
    # PANE 1: 2D Square Contribution Matrix (x=12..472, y=38..166, 460x128)
    # =========================================================================
    grid_x0 = 44.0
    grid_y0 = 75.0
    pitch = 7.92
    cell_s = 6.1  # Exact 1:1 square cells

    cells_svg = []
    month_labels_svg = []
    seen_months = set()
    last_label_x = -30.0
    month_names = ["", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

    for w_idx, w in enumerate(weeks):
        days = w["contributionDays"]
        gx = grid_x0 + w_idx * pitch

        for d in days:
            first_date = d.get("date", "")
            if len(first_date) >= 10 and first_date[8:10] in ("01", "02", "03", "04", "05", "06", "07"):
                ym = first_date[:7]
                m_num = int(first_date[5:7])
                if ym not in seen_months and (gx - last_label_x) >= 22.0 and gx <= 440.0:
                    seen_months.add(ym)
                    last_label_x = gx
                    month_labels_svg.append(
                        f'<text x="{gx:.1f}" y="{grid_y0 - 4.5:.1f}" fill="{p["text_dim"]}" font-size="7.5" class="mono">{month_names[m_num]}</text>'
                    )
                break

        for d in days:
            d_idx = d["weekday"]
            c = d["contributionCount"]
            gy = grid_y0 + d_idx * pitch
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
            fill_c, stroke_c = p["cells"][lvl]
            cells_svg.append(
                f'<rect x="{gx:.1f}" y="{gy:.1f}" width="{cell_s}" height="{cell_s}" rx="1.2" fill="{fill_c}" stroke="{stroke_c}" stroke-width="0.45"/>'
            )

    legend_cells_svg = []
    lx0 = 70.0
    for idx, (fill_c, stroke_c) in enumerate(p["cells"]):
        lx = lx0 + idx * 9.5
        legend_cells_svg.append(
            f'<rect x="{lx:.1f}" y="149.0" width="6.0" height="6.0" rx="1.1" fill="{fill_c}" stroke="{stroke_c}" stroke-width="0.45"/>'
        )

    split_total_w = 72.0
    priv_bar_w = (priv_pct / 100.0) * split_total_w

    # =========================================================================
    # PANE 2: 24h Circadian Histogram (x=482..868, y=38..166, 386x128)
    # =========================================================================
    hist_x0, hist_x1 = 496.0, 854.0
    hist_y0, hist_y1 = 68.0, 138.0
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
            f'<rect x="{bx:.1f}" y="{hist_y0:.1f}" width="{bar_w:.1f}" height="{hist_y1 - hist_y0:.1f}" rx="1.2" fill="{p["grid_line"]}" opacity="0.35"/>'
        )
        if hr >= 22 or hr <= 4:
            bcol = p["cyan"] if count > 0 else p["grid_line"]
        else:
            bcol = p["accent"] if count > 0 else p["grid_line"]
        bars_svg.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" rx="1.2" fill="{bcol}" opacity="0.92"/>'
        )

    # =========================================================================
    # PANE 3: Weekly Commit Throughput (x=12..472, y=176..304, 460x128)
    # Identical box size (460x128) & inner plot dimensions (418x53.6) as Pane 1!
    # =========================================================================
    osc_x0 = grid_x0
    osc_x1 = grid_x0 + (max(1, len(weekly_totals) - 1)) * pitch + cell_s
    osc_y0 = 222.0
    osc_y1 = 222.0 + (6 * pitch + cell_s)  # 275.6 (exact same height as 7-row square grid!)
    max_w_val = max(max_wk, 10)
    mid_w_val = max_w_val // 2
    osc_pts = []
    area_pts = [f"{osc_x0:.1f},{osc_y1:.1f}"]
    peak_dots_svg = []
    n_weeks = len(weekly_totals)
    for i, val in enumerate(weekly_totals):
        px = osc_x0 + (i / max(1, n_weeks - 1)) * (osc_x1 - osc_x0)
        py = osc_y1 - (val / max_w_val) * (osc_y1 - osc_y0 - 2.0)
        osc_pts.append(f"{px:.1f},{py:.1f}")
        area_pts.append(f"{px:.1f},{py:.1f}")
        if val >= max_w_val * 0.45 and val > 0:
            peak_dots_svg.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="1.8" fill="{p["cyan"]}"/>')
    area_pts.append(f"{osc_x1:.1f},{osc_y1:.1f}")
    osc_polyline = " ".join(osc_pts)
    osc_area = " ".join(area_pts)

    # =========================================================================
    # PANE 4: Commit-Weighted Stack Telemetry (x=482..868, y=176..304, 386x128)
    # =========================================================================
    stack_bar_x0 = 496.0
    stack_bar_w = 358.0
    stack_segments_svg = []
    cur_x = stack_bar_x0
    for r in stack_stats["rows"]:
        seg_w = max(2.0, (r["pct"] / 100.0) * stack_bar_w)
        if cur_x + seg_w > stack_bar_x0 + stack_bar_w:
            seg_w = max(0.0, (stack_bar_x0 + stack_bar_w) - cur_x)
        col = p[r["col_key"]]
        stack_segments_svg.append(
            f'<rect x="{cur_x:.1f}" y="203" width="{seg_w:.1f}" height="6" rx="1" fill="{col}" opacity="0.92"/>'
        )
        cur_x += seg_w

    stack_rows_svg = []
    row_ys = [226, 245, 264, 283]
    max_row_pct = max((r["pct"] for r in stack_stats["rows"]), default=50.0)
    for idx, r in enumerate(stack_stats["rows"][:4]):
        ry = row_ys[idx]
        col = p[r["col_key"]]
        bar_bg_x = 586.0
        bar_max_w = 64.0
        fill_w = max(3.0, (r["pct"] / max(1.0, max_row_pct)) * bar_max_w)
        pct_str = f"{r['pct']:>4.1f}%"
        stack_rows_svg.append(
            f'  <circle cx="500" cy="{ry - 3}" r="2.5" fill="{col}"/>'
            f'<text x="508" y="{ry}" fill="{p["text_main"]}" font-size="8.4" font-weight="bold" class="mono">{r["label"]}</text>'
            f'<rect x="{bar_bg_x}" y="{ry - 6.2}" width="{bar_max_w}" height="5" rx="1.5" fill="{p["grid_line"]}"/>'
            f'<rect x="{bar_bg_x}" y="{ry - 6.2}" width="{fill_w:.1f}" height="5" rx="1.5" fill="{col}"/>'
            f'<text x="688" y="{ry}" text-anchor="end" fill="{p["text_main"]}" font-size="8.2" class="mono">{pct_str}</text>'
            f'<text x="696" y="{ry}" fill="{p["text_muted"]}" font-size="7.9" class="mono">│ {r["repos"]:>2}r · {r["desc"]}</text>'
        )
    stack_block_svg = "\n".join(stack_rows_svg)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 342" width="100%" height="100%">
  <defs>
    <linearGradient id="oscGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{p["accent"]}" stop-opacity="0.34"/>
      <stop offset="100%" stop-color="{p["accent"]}" stop-opacity="0.0"/>
    </linearGradient>
    <linearGradient id="scanGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="{p["cyan"]}" stop-opacity="0.0"/>
      <stop offset="50%" stop-color="{p["cyan"]}" stop-opacity="0.24"/>
      <stop offset="100%" stop-color="{p["cyan"]}" stop-opacity="0.0"/>
    </linearGradient>
    <clipPath id="oscClip">
      <rect x="{osc_x0:.1f}" y="{osc_y0 - 6:.1f}" width="{osc_x1 - osc_x0:.1f}" height="{osc_y1 - osc_y0 + 10:.1f}"/>
    </clipPath>
    <style>
      .mono {{ font-family: 'JetBrains Mono', 'Fira Code', 'SFMono-Regular', Consolas, 'Liberation Mono', monospace; }}
      .led-ok {{ animation: blinkOk 2.8s infinite ease-in-out; }}
      .scanline {{ animation: sweep 6.5s infinite linear; }}
      @keyframes blinkOk {{ 0%, 100% {{ opacity: 0.95; }} 50% {{ opacity: 0.25; }} }}
      @keyframes sweep {{
        0% {{ transform: translateX(-55px); }}
        100% {{ transform: translateX(430px); }}
      }}
    </style>
  </defs>

  <!-- Outer Terminal Window -->
  <rect x="2" y="2" width="876" height="338" rx="6" fill="{p["bg"]}" stroke="{p["panel_border"]}" stroke-width="1.2"/>

  <!-- Terminal Window Header Bar -->
  <path d="M 2 8 Q 2 2 8 2 L 872 2 Q 878 2 878 8 L 878 28 L 2 28 Z" fill="{p["term_bar"]}"/>
  <line x1="2" y1="28" x2="878" y2="28" stroke="{p["panel_border"]}" stroke-width="1"/>
  <circle cx="16" cy="15" r="3.2" fill="{p["text_dim"]}" opacity="0.6"/>
  <circle cx="27" cy="15" r="3.2" fill="{p["text_dim"]}" opacity="0.6"/>
  <circle cx="38" cy="15" r="3.2" fill="{p["text_dim"]}" opacity="0.6"/>
  <text x="440" y="18.5" text-anchor="middle" fill="{p["text_muted"]}" font-size="9.5" class="mono">berndof :: github telemetry</text>
  <text x="866" y="18.5" text-anchor="end" fill="{p["text_muted"]}" font-size="8.5" class="mono">updated: {today_iso} (auto 12h)</text>

  <!-- ======================================================================= -->
  <!-- PANE 1: 2D Square Contribution Matrix (460x128)                         -->
  <!-- ======================================================================= -->
  <rect x="12" y="38" width="460" height="128" rx="3" fill="{p["panel_bg"]}" stroke="{p["panel_border"]}" stroke-width="1"/>
  <rect x="22" y="32" width="114" height="11" fill="{p["panel_bg"]}"/>
  <text x="26" y="41" fill="{p["text_main"]}" font-size="9.5" class="mono"><tspan fill="{p["text_muted"]}">┤</tspan><tspan fill="{p["accent"]}" font-weight="bold">¹</tspan> commits (52w)<tspan fill="{p["text_muted"]}">├</tspan></text>

  <text x="24" y="56" fill="{p["text_muted"]}" font-size="8.5" class="mono"><tspan fill="{p["text_main"]}" font-weight="bold">{total_contribs}</tspan> total │ <tspan fill="{p["cyan"]}" font-weight="bold">{active_days}d</tspan> active │ max <tspan fill="{p["accent"]}" font-weight="bold">{max_day}/d</tspan></text>
  <text x="458" y="56" text-anchor="end" fill="{p["text_muted"]}" font-size="8.2" class="mono"><tspan fill="{p["accent"]}">{priv_pct}% @gruposcc</tspan> / <tspan fill="{p["cyan"]}">{pub_pct}% pub</tspan></text>

  <!-- Weekday Labels (aligned with rows 1, 3, 5) -->
  <text x="24" y="88.0" fill="{p["text_dim"]}" font-size="7.2" class="mono">mon</text>
  <text x="24" y="103.8" fill="{p["text_dim"]}" font-size="7.2" class="mono">wed</text>
  <text x="24" y="119.6" fill="{p["text_dim"]}" font-size="7.2" class="mono">fri</text>

  <!-- Month Ticks & 1:1 Square Cells -->
  {"".join(month_labels_svg)}
  {"".join(cells_svg)}

  <!-- Footer Legend & Split Bar -->
  <text x="24" y="154.5" fill="{p["text_muted"]}" font-size="7.8" class="mono">less</text>
  {"".join(legend_cells_svg)}
  <text x="122" y="154.5" fill="{p["text_muted"]}" font-size="7.8" class="mono">more (0 · 1-2 · 3-6 · 7-14 · 15+/d)</text>
  <rect x="386" y="149.5" width="{split_total_w}" height="4.5" rx="2" fill="{p["cyan"]}" opacity="0.85"/>
  <rect x="386" y="149.5" width="{priv_bar_w:.1f}" height="4.5" rx="2" fill="{p["accent"]}"/>

  <!-- ======================================================================= -->
  <!-- PANE 2: Circadian Activity (386x128)                                    -->
  <!-- ======================================================================= -->
  <rect x="482" y="38" width="386" height="128" rx="3" fill="{p["panel_bg"]}" stroke="{p["panel_border"]}" stroke-width="1"/>
  <rect x="492" y="32" width="114" height="11" fill="{p["panel_bg"]}"/>
  <text x="496" y="41" fill="{p["text_main"]}" font-size="9.5" class="mono"><tspan fill="{p["text_muted"]}">┤</tspan><tspan fill="{p["cyan"]}" font-weight="bold">²</tspan> hours (utc-3)<tspan fill="{p["text_muted"]}">├</tspan></text>

  <text x="496" y="56" fill="{p["text_muted"]}" font-size="8.2" class="mono"><tspan fill="{p["accent"]}">■</tspan> day {day_pct}%   <tspan fill="{p["cyan"]}">■</tspan> 22-04h {night_pct}%</text>
  <text x="854" y="56" text-anchor="end" fill="{p["text_muted"]}" font-size="8.2" class="mono">peak: <tspan fill="{p["text_main"]}" font-weight="bold">{peak_hr:02d}:00</tspan></text>

  {"".join(bars_svg)}
  <line x1="{hist_x0}" y1="{hist_y1}" x2="{hist_x1}" y2="{hist_y1}" stroke="{p["grid_line"]}" stroke-width="1"/>
  <text x="496" y="154" fill="{p["text_dim"]}" font-size="7.5" class="mono">00h</text>
  <text x="585" y="154" fill="{p["text_dim"]}" font-size="7.5" class="mono">06h</text>
  <text x="675" y="154" fill="{p["text_dim"]}" font-size="7.5" class="mono">12h</text>
  <text x="764" y="154" fill="{p["text_dim"]}" font-size="7.5" class="mono">18h</text>
  <text x="854" y="154" text-anchor="end" fill="{p["text_dim"]}" font-size="7.5" class="mono">23h</text>

  <!-- ======================================================================= -->
  <!-- PANE 3: Weekly Commit Throughput (460x128 — identical size to Pane 1)   -->
  <!-- ======================================================================= -->
  <rect x="12" y="176" width="460" height="128" rx="3" fill="{p["panel_bg"]}" stroke="{p["panel_border"]}" stroke-width="1"/>
  <rect x="22" y="170" width="128" height="11" fill="{p["panel_bg"]}"/>
  <text x="26" y="179" fill="{p["text_main"]}" font-size="9.5" class="mono"><tspan fill="{p["text_muted"]}">┤</tspan><tspan fill="{p["accent"]}" font-weight="bold">³</tspan> throughput (52w)<tspan fill="{p["text_muted"]}">├</tspan></text>

  <text x="24" y="196" fill="{p["text_muted"]}" font-size="8.2" class="mono">30d: <tspan fill="{p["text_main"]}" font-weight="bold">{last_30d}</tspan> commits │ active: <tspan fill="{p["text_main"]}">{active_weeks}/52w</tspan></text>
  <text x="458" y="196" text-anchor="end" fill="{p["text_muted"]}" font-size="8.2" class="mono">avg <tspan fill="{p["text_main"]}">{avg_wk:.1f}/w</tspan> · max <tspan fill="{p["accent"]}" font-weight="bold">{max_wk}/w</tspan></text>

  <!-- Y-Axis Labels (matching Pane 1 weekday label column) -->
  <text x="39" y="{osc_y0 + 5:.1f}" text-anchor="end" fill="{p["text_dim"]}" font-size="7.0" class="mono">{max_w_val}</text>
  <text x="39" y="{(osc_y0 + osc_y1) / 2 + 2:.1f}" text-anchor="end" fill="{p["text_dim"]}" font-size="7.0" class="mono">{mid_w_val}</text>
  <text x="39" y="{osc_y1:.1f}" text-anchor="end" fill="{p["text_dim"]}" font-size="7.0" class="mono">0</text>

  <line x1="{osc_x0:.1f}" y1="{osc_y0:.1f}" x2="{osc_x1:.1f}" y2="{osc_y0:.1f}" stroke="{p["grid_line"]}" stroke-width="0.8" stroke-dasharray="2,3"/>
  <line x1="{osc_x0:.1f}" y1="{(osc_y0 + osc_y1) / 2:.1f}" x2="{osc_x1:.1f}" y2="{(osc_y0 + osc_y1) / 2:.1f}" stroke="{p["grid_line"]}" stroke-width="0.8" stroke-dasharray="2,3"/>
  <line x1="{osc_x0:.1f}" y1="{osc_y1:.1f}" x2="{osc_x1:.1f}" y2="{osc_y1:.1f}" stroke="{p["grid_line"]}" stroke-width="1"/>

  <g clip-path="url(#oscClip)">
    <polygon points="{osc_area}" fill="url(#oscGrad)"/>
    <polyline points="{osc_polyline}" fill="none" stroke="{p["accent"]}" stroke-width="1.65"/>
    {"".join(peak_dots_svg)}
    <rect x="{osc_x0:.1f}" y="{osc_y0 - 4:.1f}" width="48" height="{osc_y1 - osc_y0 + 6:.1f}" fill="url(#scanGrad)" class="scanline"/>
  </g>

  <text x="{osc_x0:.1f}" y="292" fill="{p["text_dim"]}" font-size="7.5" class="mono">-52w</text>
  <text x="{(osc_x0 + osc_x1) / 2:.1f}" y="292" text-anchor="middle" fill="{p["text_dim"]}" font-size="7.5" class="mono">-26w</text>
  <text x="{osc_x1:.1f}" y="292" text-anchor="end" fill="{p["text_dim"]}" font-size="7.5" class="mono">now</text>

  <!-- ======================================================================= -->
  <!-- PANE 4: Commit-Weighted Stack Telemetry (386x128)                       -->
  <!-- ======================================================================= -->
  <rect x="482" y="176" width="386" height="128" rx="3" fill="{p["panel_bg"]}" stroke="{p["panel_border"]}" stroke-width="1"/>
  <rect x="492" y="170" width="154" height="11" fill="{p["panel_bg"]}"/>
  <text x="496" y="179" fill="{p["text_main"]}" font-size="9.5" class="mono"><tspan fill="{p["text_muted"]}">┤</tspan><tspan fill="{p["accent"]}" font-weight="bold">⁴</tspan> stack (by commits)<tspan fill="{p["text_muted"]}">├</tspan></text>
  <text x="854" y="196" text-anchor="end" fill="{p["text_muted"]}" font-size="8.2" class="mono"><tspan fill="{p["text_main"]}" font-weight="bold">{stack_stats["total_repos"]}</tspan> repos ({stack_stats["priv_repos"]} priv · {stack_stats["pub_repos"]} pub)</text>
  <text x="496" y="196" fill="{p["text_muted"]}" font-size="8.2" class="mono">weighted by commits across <tspan fill="{p["accent"]}" font-weight="bold">{stack_stats["active_repos"]}</tspan> active repos</text>

  <!-- Proportional Stack Bar -->
  {"".join(stack_segments_svg)}

  <!-- Stack Breakdown Rows -->
{stack_block_svg}

  <!-- ======================================================================= -->
  <!-- BOTTOM STATUS BAR                                                       -->
  <!-- ======================================================================= -->
  <rect x="12" y="312" width="856" height="20" rx="2.5" fill="{p["tmux_bg"]}" stroke="{p["panel_border"]}" stroke-width="0.8"/>
  <rect x="12" y="312" width="68" height="20" rx="2.5" fill="{p["accent"]}"/>
  <circle cx="22" cy="322" r="2.6" fill="{p["tmux_pill_fg"]}" class="led-ok"/>
  <text x="49" y="325" text-anchor="middle" fill="{p["tmux_pill_fg"]}" font-size="8.5" font-weight="bold" class="mono">0:noc</text>

  <text x="92" y="325" fill="{p["text_muted"]}" font-size="8.4" class="mono">prefer: <tspan fill="{p["text_main"]}">sh + python</tspan> │ <tspan fill="{p["text_main"]}">html + css + js (as God intended)</tspan> │ <tspan fill="{p["text_main"]}">raw sql</tspan></text>
  <text x="858" y="325" text-anchor="end" fill="{p["text_muted"]}" font-size="8.2" class="mono">typo-free: <tspan fill="{p["warn"]}" font-weight="bold">{typo_free_days}d</tspan></text>
</svg>
"""
    return svg


def generate_pipeline_svg(mode="dark"):
    """
    Generates a NOC/terminal-styled architecture & workflow pipeline SVG
    with a window title bar, port-to-port bus connectors, command headers,
    and structured rows.
    """
    p = _palette(mode)
    row_bg = "#141b26" if mode == "dark" else "#f8fafc"

    stages = [
        {
            "num": "¹",
            "title": "signal &amp; hardware",
            "cmd": "$ listen --raw",
            "badge": "in",
            "col": p["cyan"],
            "lines": [
                ("rf / sensors", "telemetry"),
                ("legacy gear", "raw http/tcp"),
                ("edge &amp; apis", "streams"),
            ],
        },
        {
            "num": "²",
            "title": "glue &amp; collectors",
            "cmd": "$ pipe | parse",
            "badge": "sh/py",
            "col": p["accent"],
            "lines": [
                ("sh / bash", "coreutils"),
                ("python3", "stdlib-first"),
                ("cron + awk", "zero bloat"),
            ],
        },
        {
            "num": "³",
            "title": "state &amp; compute",
            "cmd": "$ query --fast",
            "badge": "core",
            "col": p["accent"],
            "lines": [
                ("raw sql", "no heavy orm"),
                ("unix daemons", "low ram"),
                ("models", "stochastic"),
            ],
        },
        {
            "num": "⁴",
            "title": "output &amp; web ui",
            "cmd": "$ serve --plain",
            "badge": "out",
            "col": p["warn"],
            "lines": [
                ("html+css+js", "vanilla web"),
                ("↳ as God", "intended"),
                ("zabbix / tui", "alerts &amp; hud"),
            ],
        },
    ]

    cards_svg = []
    connectors_svg = []
    x0 = 12.0
    card_w = 196.0
    gap = 24.0
    card_y = 38.0
    card_h = 98.0

    for idx, st in enumerate(stages):
        cx = x0 + idx * (card_w + gap)
        title_box_w = len(st["title"].replace("&amp;", "&")) * 5.8 + 26

        cards_svg.append(
            f'  <rect x="{cx:.1f}" y="{card_y:.1f}" width="{card_w:.1f}" height="{card_h:.1f}" rx="3" fill="{p["panel_bg"]}" stroke="{p["panel_border"]}" stroke-width="1"/>'
            f'  <rect x="{cx + 8:.1f}" y="{card_y - 6:.1f}" width="{title_box_w:.1f}" height="11" fill="{p["panel_bg"]}"/>'
            f'  <text x="{cx + 11:.1f}" y="{card_y + 3:.1f}" fill="{p["text_main"]}" font-size="9" class="mono">'
            f'<tspan fill="{p["text_muted"]}">┤</tspan><tspan fill="{st["col"]}" font-weight="bold">{st["num"]}</tspan> {st["title"]}<tspan fill="{p["text_muted"]}">├</tspan></text>'
            f'  <text x="{cx + 10:.1f}" y="{card_y + 18:.1f}" fill="{p["text_muted"]}" font-size="7.8" class="mono">{st["cmd"]}</text>'
            f'  <rect x="{cx + card_w - 38:.1f}" y="{card_y + 9.5:.1f}" width="30" height="11" rx="2" fill="{row_bg}" stroke="{p["grid_line"]}" stroke-width="0.7"/>'
            f'  <text x="{cx + card_w - 23:.1f}" y="{card_y + 17.5:.1f}" text-anchor="middle" fill="{st["col"]}" font-size="7.2" font-weight="bold" class="mono">{st["badge"]}</text>'
            f'  <line x1="{cx + 8:.1f}" y1="{card_y + 24:.1f}" x2="{cx + card_w - 8:.1f}" y2="{card_y + 24:.1f}" stroke="{p["grid_line"]}" stroke-width="1"/>'
        )

        for l_idx, (left_txt, right_txt) in enumerate(st["lines"]):
            ry = card_y + 30.0 + l_idx * 21.0
            if l_idx % 2 == 0:
                cards_svg.append(
                    f'  <rect x="{cx + 6:.1f}" y="{ry:.1f}" width="{card_w - 12:.1f}" height="17" rx="1.5" fill="{row_bg}"/>'
                )
            ty = ry + 11.5
            if left_txt.startswith("↳"):
                cards_svg.append(
                    f'  <text x="{cx + 14:.1f}" y="{ty:.1f}" fill="{p["warn"]}" font-size="8.0" font-style="italic" class="mono">{left_txt} {right_txt}</text>'
                )
            else:
                cards_svg.append(
                    f'  <circle cx="{cx + 13:.1f}" cy="{ty - 2.8:.1f}" r="2.0" fill="{st["col"]}"/>'
                    f'  <text x="{cx + 20:.1f}" y="{ty:.1f}" fill="{p["text_main"]}" font-size="8.2" font-weight="bold" class="mono">{left_txt}</text>'
                    f'  <text x="{cx + card_w - 10:.1f}" y="{ty:.1f}" text-anchor="end" fill="{p["text_muted"]}" font-size="7.6" class="mono">{right_txt}</text>'
                )

        if idx < len(stages) - 1:
            ax0 = cx + card_w
            ax1 = cx + card_w + gap
            ay = card_y + card_h / 2.0
            connectors_svg.append(
                f'  <line x1="{ax0:.1f}" y1="{ay:.1f}" x2="{ax1:.1f}" y2="{ay:.1f}" stroke="{p["grid_line"]}" stroke-width="2.2"/>'
                f'  <line x1="{ax0 + 3:.1f}" y1="{ay:.1f}" x2="{ax1 - 5:.1f}" y2="{ay:.1f}" stroke="{p["accent"]}" stroke-width="1.5" stroke-dasharray="3,3" class="flow-line"/>'
                f'  <circle cx="{ax0:.1f}" cy="{ay:.1f}" r="2.6" fill="{p["panel_bg"]}" stroke="{st["col"]}" stroke-width="1.2"/>'
                f'  <polygon points="{ax1 - 1.5:.1f},{ay:.1f} {ax1 - 6.5:.1f},{ay - 3.2:.1f} {ax1 - 6.5:.1f},{ay + 3.2:.1f}" fill="{p["accent"]}"/>'
            )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 172" width="100%" height="100%">
  <defs>
    <style>
      .mono {{ font-family: 'JetBrains Mono', 'Fira Code', 'SFMono-Regular', Consolas, 'Liberation Mono', monospace; }}
      .flow-line {{ animation: flowDash 1.2s infinite linear; }}
      @keyframes flowDash {{
        to {{ stroke-dashoffset: -12; }}
      }}
    </style>
  </defs>

  <!-- Outer Terminal Window -->
  <rect x="2" y="2" width="876" height="168" rx="6" fill="{p["bg"]}" stroke="{p["panel_border"]}" stroke-width="1.2"/>

  <!-- Terminal Header Bar -->
  <path d="M 2 8 Q 2 2 8 2 L 872 2 Q 878 2 878 8 L 878 26 L 2 26 Z" fill="{p["term_bar"]}"/>
  <line x1="2" y1="26" x2="878" y2="26" stroke="{p["panel_border"]}" stroke-width="1"/>
  <circle cx="16" cy="14" r="3.0" fill="{p["text_dim"]}" opacity="0.6"/>
  <circle cx="26" cy="14" r="3.0" fill="{p["text_dim"]}" opacity="0.6"/>
  <circle cx="36" cy="14" r="3.0" fill="{p["text_dim"]}" opacity="0.6"/>
  <text x="440" y="17.5" text-anchor="middle" fill="{p["text_muted"]}" font-size="9.2" class="mono">berndof :: architecture &amp; workflow pipeline</text>
  <text x="866" y="17.5" text-anchor="end" fill="{p["text_muted"]}" font-size="8.2" class="mono">policy: keep-it-lightweight</text>

  <!-- Pipeline Stage Cards & Animated Bus Connectors -->
{chr(10).join(cards_svg)}
{chr(10).join(connectors_svg)}

  <!-- Bottom Principle Bar -->
  <rect x="12" y="143" width="856" height="19" rx="2.5" fill="{p["tmux_bg"]}" stroke="{p["panel_border"]}" stroke-width="0.8"/>
  <rect x="12" y="143" width="58" height="19" rx="2.5" fill="{p["cyan"]}"/>
  <text x="41" y="155.5" text-anchor="middle" fill="{p["tmux_pill_fg"]}" font-size="8.2" font-weight="bold" class="mono">unix</text>
  <text x="80" y="155.5" fill="{p["text_muted"]}" font-size="8.2" class="mono">if a shell script + python + plain <tspan fill="{p["text_main"]}">html/css/js</tspan> solves it, skip the 200MB framework · <tspan fill="{p["accent"]}">runs on a toaster</tspan></text>
  <text x="858" y="155.5" text-anchor="end" fill="{p["text_dim"]}" font-size="8" class="mono">0B bloat</text>
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
        "repositories": {"totalCount": 22, "nodes": []},
        "contributionsCollection": {
            "totalCommitContributions": 58,
            "restrictedContributionsCount": 827,
            "contributionCalendar": {
                "totalContributions": 895,
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
    commit_hours, stack_stats = analyze_repos_and_commits(user_data)

    outputs = {
        "noc-telemetry-dark.svg": generate_telemetry_svg(user_data, commit_hours, stack_stats, mode="dark"),
        "noc-telemetry-light.svg": generate_telemetry_svg(user_data, commit_hours, stack_stats, mode="light"),
        "noc-pipeline-dark.svg": generate_pipeline_svg(mode="dark"),
        "noc-pipeline-light.svg": generate_pipeline_svg(mode="light"),
    }

    for fname, svg_content in outputs.items():
        ET.fromstring(svg_content)  # Validate well-formed XML before writing
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as f:
            f.write(svg_content)

    patch_snake_svgs(out_dir)
    print(f"Generated {', '.join(outputs.keys())} in {out_dir}/ successfully.")


if __name__ == "__main__":
    main()
