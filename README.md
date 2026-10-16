<div align="center">

# `berndof` // Bernardo

[![Status](https://img.shields.io/badge/status-poking_at_systems-10b981?style=flat-square&logo=gnubash&logoColor=white)](#)
[![Org](https://img.shields.io/badge/day_ops-@gruposcc_%2F_SCC10-0ea5e9?style=flat-square)](#)
[![Job Title](https://img.shields.io/badge/job_title-404_not_found-6366f1?style=flat-square)](#)
[![Stack](https://img.shields.io/badge/stack-whatever_works-f59e0b?style=flat-square)](#)
[![Legacy](https://img.shields.io/badge/Hello,_Wolrd!-2023--2026_RIP-ef4444?style=flat-square)](#)

> *"For three years this profile just said `### Hello, Wolrd! 👋` (yes, with the typo).*  
> *I eventually decided to fix the typo and document the rabbit holes instead."*

</div>

---

### `$ whoami`

No corporate buzzwords or rigid job titles here — I just like things. Specifically, I like poking at systems to see how they work, automating things that mildly annoy me, keeping high-traffic news portals and broadcast infrastructure alive, orchestrating AI agents until they audit each other, running 30,000 Monte Carlo simulations to answer a weekend question, and coaxing industrial hardware into talking to monitoring servers.

*(~86% of my day-to-day production commits live behind private organization doors at [**@gruposcc**](https://github.com/gruposcc) / **SCC10**; my public repositories are just the chaotic R&D laboratory that escaped into the wild.)*

```mermaid
flowchart LR
    A["Curiosity / Mild Annoyance"] --> B{"Pick a Problem"}
    B -->| Broadcast & Portal Ops | C["SCC10 Infra & Tower NOC<br/>(IaC, Chisel/IPsec, Zabbix)"]
    B -->| Hardware has no API | D["Telemetry Necromancy<br/>(Playwright → Diesel/Solar/Radios)"]
    B -->| Too many LLMs | E["Multi-Agent Plumbing<br/>(Orchestration, MCP, SSH Tunnels)"]
    B -->| Public data exists | F["Statistical Rabbit Holes<br/>(Monte Carlo & Live Nowcasting)"]
```

---

### `$ watch -n 1 "berndof-telemetry --noc-hud --3d-topology"`

<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/berndof/berndof/output/noc-telemetry-dark.svg" />
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/berndof/berndof/output/noc-telemetry-light.svg" />
    <img alt="BERNDOF NOC & Agent Telemetry Deck" src="https://raw.githubusercontent.com/berndof/berndof/output/noc-telemetry-dark.svg" width="100%" />
  </picture>
</div>

---

### `$ cat /var/log/what-i-actually-do.log`

#### 📡 Broadcast Infra, Tower NOC & High-Traffic Portals (`@gruposcc` / SCC10)
Keeping media, radio/TV transmission towers, and news portal infrastructure running smoothly — especially when traffic spikes or hardware decides to be dramatic:
* **High-Traffic Portal Infrastructure (`scc10.com.br`)**: Infrastructure-as-Code state snapshots, automated `prod ↔ dev` drift auditing, Apache / PHP-FPM / MariaDB resilience tuning, AWS RDS SSL maintenance pipelines, local Docker parity stacks, and one-command rollbacks.
* **Network Plumbing & Reverse Tunnels**: Multi-hop Zabbix active/passive monitoring topologies, Caddy reverse proxies, Chisel tunnels with custom Header PSK validation behind Cloudflare WAF, and IPsec/Netplan routing across distributed sites.
* **Hardware & NOC Necromancy**: When transmission tower radios, **Deep Sea Electronics (DSE855)** diesel generator controllers, or **Huawei FusionSolar** inverters refuse to expose a civilized API, I write headless Playwright + async Python collectors to scrape their telemetry and pipe everything straight into **Zabbix**.

#### 🤖 Autonomous AI Agent Plumbing & Remote Dev Tooling
Building the scaffolding around CLI coding agents so they actually finish engineering tasks instead of burning tokens in an infinite loop:
* **Multi-Agent Orchestration**: Enforcing structured `recon → design → implement → verify` loops with strict MCP tool isolation, 2-level hierarchical memory spines, and TUI planning panels — because one LLM hallucinating is a bug, while five specialized agents cross-checking each other is *architecture*.
* **LLM Bridges & Observability**: Custom `stream-json` providers bridging local CLI ecosystems, quota-aware multi-provider gateways, and telemetry dashboards tracking whether agents are actually productive (Ideation-to-Execution Ratio, Plan Completion Rate, token/cost distribution).
* **Potato-Safe Remote Development**: Automated SSH tunnel managers, daemon health probes, and low-resource SSHFS kernel-cache mounts so heavy AI tooling can work against lightweight remote servers without frying their CPU or RAM.

#### 🎲 Statistical Rabbit Holes & Zero-Bundler Web Stacks
* **Nowcasting & Monte Carlo Ensembles**: Turning messy public datasets (TSE, IBGE, polling history) into real-time partial-count nowcasting models (**0.2 pp** backtest error at 85% counted), institute bias diagnostics, and 30,000-simulation Monte Carlo ensembles — complete with bilingual technical papers.
* **Zero-Bundler Web Tooling**: Building reactive internal tools and web apps with **FastAPI + HTMX + Jinja2 fragments + asyncpg** whenever a problem doesn't justify downloading 400 MB of `node_modules`.

---

### `$ man 7 berndof` — RFC 2119 Operational Axioms

| Directive | Rule of Engagement |
| :--- | :--- |
| **`MUST`** | Spend 4 hours writing a deterministic Bash/Python automation pipeline to avoid a 5-minute manual task that might happen twice. |
| **`SHOULD NOT`** | Accept *"this industrial controller doesn't support monitoring"* as an answer. If it serves an HTML page over port 80, it speaks Zabbix now. |
| **`REQUIRED`** | Never trust a single LLM in production when you can force five isolated subagents (`recon → design → implement → verify`) to audit each other's work. |
| **`RECOMMENDED`** | Run 30,000 Monte Carlo simulations before making a statistical claim, then add a disclaimer that your 90% confidence intervals are probably still too narrow. |
| **`FORBIDDEN`** | Shipping 400 MB of `node_modules` for an internal dashboard that `FastAPI + HTMX` can render in 4 milliseconds. |

---

### `$ cat /proc/berndof/toolbox`

```text
LANGUAGES   :: Python (3.13/3.14, asyncio, uv) • TypeScript (Bun / Node) • Bash • PHP • SQL
INFRA / NOC :: Linux • Docker • Zabbix • Caddy / Apache / PHP-FPM • Chisel / IPsec / SSHFS
AI / AGENTS :: OpenCode • Multi-Agent Orchestration • MCP • LLM Gateways • Stream Protocols
DATA / MATH :: Monte Carlo Simulation • Bayesian/Structural Nowcasting • NumPy • Pandas
WEB / AUTO  :: FastAPI • HTMX • WordPress Core/Infra • PostgreSQL / MariaDB • Playwright
```

---

### `$ crontab -l`

```crontab
# m   h    dom mon dow   command
*/5   *    *   *   *     /usr/local/bin/coerce-hardware-into-zabbix --targets=dse855,fusionsolar,radios
0     */6  *   *   *     /opt/scc10/diff-ambientes.sh prod dev --strict-drift-check
15    2    *   *   *     /usr/bin/opencode-orchestrator --mode=over-engineer --max-agents=5
0     22   *   10  0     /usr/bin/python3 nowcast_ensemble.py --simulations=30000 --honest-ci
@reboot                  /bin/rm -rf ./node_modules && echo "Use HTMX instead"
```

---

<details>
<summary><b>🔧 Run System Diagnostics (<code>systemctl status berndof.service</code>)</b></summary>
<br/>

```ini
● berndof.service - Curiosity-Driven Engineering & NOC Daemon
     Loaded: loaded (/etc/systemd/system/berndof.service; enabled; preset: chaotic-good)
     Active: active (running) since 2023-03-26 17:08:45 UTC; 3 years 6 months ago
   Main PID: 1337 (tinkerer)
      Tasks: 42 (limit: ∞)
     Memory: 86% in @gruposcc private repos, 14% chaotic public experiments
        CPU: 100% whenever someone says "that hardware doesn't have an API"

Oct 16 09:30:00 host berndof[1337]: [INFO] Fixed 3-year-old "Hello, Wolrd!" typo in README.md
Oct 16 09:31:12 host berndof[1337]: [OK]   Audited prod <-> dev drift & Chisel PSK tunnels on SCC10 infra
Oct 16 09:32:45 host berndof[1337]: [WARN] Started 30,000 Monte Carlo simulations just to verify a hunch
Oct 16 09:34:19 host berndof[1337]: [OK]   Spawned 5 AI subagents to over-engineer a shell workflow
Oct 16 09:35:01 host berndof[1337]: [INFO] Diesel generator & radio tower telemetry coerced into Zabbix
```

</details>

<details>
<summary><b>🐍 Launch Legacy Arcade Mode (<code>/usr/games/snake --eat-commits</code>)</b></summary>
<br/>

<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/berndof/berndof/output/github-contribution-grid-snake-dark.svg" />
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/berndof/berndof/output/github-contribution-grid-snake.svg" />
    <img alt="github-contribution-grid-snake" src="https://raw.githubusercontent.com/berndof/berndof/output/github-contribution-grid-snake.svg" />
  </picture>
</div>

</details>
