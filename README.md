# BigQuant Claude Code Skills

Claude Code skills for quantitative trading on the BigQuant platform (Chinese A-share markets).

## Skills

| Skill | Description |
|-------|-------------|
| `bigquant-dai` | DAI data query — SQL tables, filters, functions, and patterns |
| `bigquant-option` | ETF options strategy development with bigtrader |
| `bigquant-stock` | Stock selection strategy development with bigtrader |

## Installation

Copy the skill directories into your project's `.claude/skills/` folder:

```bash
cp -r bigquant-dai bigquant-option bigquant-stock /path/to/your/project/.claude/skills/
```

## Usage

These skills are automatically triggered by Claude Code when relevant tasks are detected (e.g., writing DAI queries, developing stock/option strategies).
