# BigQuant Claude Code Skills

Claude Code skills for quantitative trading on the BigQuant platform (Chinese A-share markets).

## Skills

| Skill | Description |
|-------|-------------|
| `bigquant-coder` | DAI data queries, stock selection strategies, ETF option strategies, and futures CTA strategies with bigtrader |

## Installation

Copy the skill directory into your project's `.claude/skills/` folder:

```bash
cp -r bigquant-coder /path/to/your/project/.claude/skills/
```

## Usage

This skill is automatically triggered by Claude Code when relevant tasks are detected (e.g., writing DAI queries, developing stock/option/futures strategies).

## Recent Updates

- **bigquant-coder**: Replaces the former `bigquant-dai` / `bigquant-option` / `bigquant-stock` skills with a single combined skill; added DAI UDF (`dai.DaiUDF`) documentation
