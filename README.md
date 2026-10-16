```console
$ finger berndof
Login: berndof                          Name: Bernardo
Directory: /home/berndof                Shell: /bin/zsh
Location: Florianópolis, BR (UTC-3)     Mail: /dev/null
Plan:
  broadcast infra, portals & network plumbing at @gruposcc (scc10) by day.
  agent orchestration, stubborn hardware & statistical rabbit holes by night.
  no fixed job title — i just like poking at systems until they work.
```

```mermaid
flowchart LR
    A["weird problem appears"] --> B{"ready-made stack exists?"}
    B -->|no| C["sniff packets / html & write python + bash"]
    B -->|yes| D{"uses react or >50MB of node_modules?"}
    D -->|yes| E["pretend it doesn't exist"] --> C
    D -->|no| F{"needs a web UI?"}
    F -->|yes| G["fastapi + htmx + zero bundlers"]
    F -->|no| H["daemon + cron + raw sql"]
    C & G & H --> I["runs on a toaster (12MB RAM)"]
```

<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/berndof/berndof/output/noc-telemetry-dark.svg" />
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/berndof/berndof/output/noc-telemetry-light.svg" />
    <img alt="btop / tmux telemetry monitor" src="https://raw.githubusercontent.com/berndof/berndof/output/noc-telemetry-dark.svg" width="100%" />
  </picture>
</div>

<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/berndof/berndof/output/github-contribution-grid-snake-dark.svg" />
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/berndof/berndof/output/github-contribution-grid-snake.svg" />
    <img alt="contribution-grid-snake" src="https://raw.githubusercontent.com/berndof/berndof/output/github-contribution-grid-snake.svg" width="100%" />
  </picture>
</div>
