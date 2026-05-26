# 股票选股策略模式库

## 模式一：单因子排名

最简单的选股模式，计算单一因子后排名取 top-N。

```python
from bigquant import bigtrader, dai

def initialize(context: bigtrader.IContext):
    context.set_commission(bigtrader.PerOrder(
        buy_cost=0.0003, sell_cost=0.0013, min_cost=5
    ))

    stock_num = 50
    rebalance_days = 10

    sql = f"""
    SELECT
        date,
        instrument,
        close / m_lag(close, 20) - 1 AS factor,
        1.0 / {stock_num} AS weight
    FROM cn_stock_prefactors
    WHERE list_sector IN (1, 2, 3)
      AND st_status = 0
      AND suspended = 0
      AND list_days > 252
    QUALIFY factor > 0
    ORDER BY date, factor DESC
    LIMIT {stock_num} BY date
    """

    df = dai.query(sql, filters={
        "date": [
            context.add_trading_days(context.start_date, -50),
            context.end_date
        ]
    }).df()

    df = bigtrader.TradingDaysRebalance(
        rebalance_days, context=context
    ).select_rebalance_data(df)

    context.data = df

performance = bigtrader.run(
    market=bigtrader.Market.CN_STOCK,
    frequency=bigtrader.Frequency.DAILY,
    start_date="2021-01-01",
    end_date="2026-05-01",
    capital_base=1000000,
    initialize=initialize,
    handle_data=bigtrader.HandleDataLib.handle_data_weight_based,
)
```

---

## 模式二：双因子/多因子合成

多个因子分别排名后加权合成。

```python
from bigquant import bigtrader, dai

def initialize(context: bigtrader.IContext):
    context.set_commission(bigtrader.PerOrder(
        buy_cost=0.0003, sell_cost=0.0013, min_cost=5
    ))

    stock_num = 50
    rebalance_days = 10

    sql = f"""
    WITH raw AS (
        SELECT
            date,
            instrument,
            c_pct_rank(1.0 / m_avg(amount, 10)) AS rank1,
            c_pct_rank(close / m_lag(close, 20) - 1) AS rank2
        FROM cn_stock_prefactors
        WHERE list_sector IN (1, 2, 3)
          AND st_status = 0
          AND suspended = 0
          AND list_days > 252
        QUALIFY COLUMNS(*) IS NOT NULL
    )
    SELECT
        date,
        instrument,
        (rank1 + rank2) AS composite,
        1.0 / {stock_num} AS weight
    FROM raw
    ORDER BY date, composite DESC
    LIMIT {stock_num} BY date
    """

    df = dai.query(sql, filters={
        "date": [
            context.add_trading_days(context.start_date, -50),
            context.end_date
        ]
    }).df()

    df = bigtrader.TradingDaysRebalance(
        rebalance_days, context=context
    ).select_rebalance_data(df)

    context.data = df

performance = bigtrader.run(
    market=bigtrader.Market.CN_STOCK,
    frequency=bigtrader.Frequency.DAILY,
    start_date="2021-01-01",
    end_date="2026-05-01",
    capital_base=1000000,
    initialize=initialize,
    handle_data=bigtrader.HandleDataLib.handle_data_weight_based,
)
```

---

## 模式三：条件筛选 + 因子排名

先用基本面条件筛选股票池，再用因子排名。

```python
from bigquant import bigtrader, dai

def initialize(context: bigtrader.IContext):
    context.set_commission(bigtrader.PerOrder(
        buy_cost=0.0003, sell_cost=0.0013, min_cost=5
    ))

    stock_num = 30
    rebalance_days = 63  # 季度调仓

    sql = f"""
    WITH filtered AS (
        SELECT
            date,
            instrument,
            fcff_ttm / total_market_cap AS fcf_yield,
            roe_avg_ttm,
            m_avg(amount, 125) AS avg_amount_6m
        FROM cn_stock_prefactors
        WHERE st_status = 0
          AND suspended = 0
          AND list_days > 252
          AND pe_ttm > 0 AND pe_ttm < 100
          AND pb > 0
          AND roe_avg_ttm > 0.08
          AND fcff_ttm > 0
        QUALIFY COLUMNS(*) IS NOT NULL
    ),
    ranked AS (
        SELECT
            date,
            instrument,
            fcf_yield,
            c_pct_rank(avg_amount_6m) AS liquidity_rank
        FROM filtered
        WHERE liquidity_rank >= 0.3
    )
    SELECT
        date,
        instrument,
        1.0 / {stock_num} AS weight
    FROM ranked
    ORDER BY date, fcf_yield DESC
    LIMIT {stock_num} BY date
    """

    df = dai.query(sql, filters={
        "date": [
            context.add_trading_days(context.start_date, -200),
            context.end_date
        ]
    }).df()

    df = bigtrader.TradingDaysRebalance(
        rebalance_days, context=context
    ).select_rebalance_data(df)

    context.data = df

performance = bigtrader.run(
    market=bigtrader.Market.CN_STOCK,
    frequency=bigtrader.Frequency.DAILY,
    start_date="2021-01-01",
    end_date="2026-05-01",
    capital_base=1000000,
    initialize=initialize,
    handle_data=bigtrader.HandleDataLib.handle_data_weight_based,
)
```

---

## 模式四：行业中性选股

在每个行业内分别排名，避免行业集中。

```python
sql = f"""
WITH raw AS (
    SELECT
        date,
        instrument,
        sw2021_level1 AS industry,
        close / m_lag(close, 20) - 1 AS momentum,
        c_group_pct_rank(close / m_lag(close, 20) - 1, GROUP BY sw2021_level1) AS industry_rank
    FROM cn_stock_prefactors
    WHERE list_sector IN (1, 2, 3)
      AND st_status = 0
      AND suspended = 0
      AND list_days > 252
    QUALIFY COLUMNS(*) IS NOT NULL
)
SELECT
    date,
    instrument,
    1.0 / {stock_num} AS weight
FROM raw
WHERE industry_rank >= 0.8
ORDER BY date, industry_rank DESC
LIMIT {stock_num} BY date
"""
```

---

## 模式五：因子加权组合（非等权）

按因子值分配权重，而非等权。

```python
sql = """
WITH raw AS (
    SELECT
        date,
        instrument,
        fcff_ttm / total_market_cap AS fcf_yield
    FROM cn_stock_prefactors
    WHERE st_status = 0 AND suspended = 0 AND list_days > 252
      AND fcff_ttm > 0 AND total_market_cap > 0
    QUALIFY COLUMNS(*) IS NOT NULL
    ORDER BY date, fcf_yield DESC
    LIMIT 50 BY date
)
SELECT
    date,
    instrument,
    fcf_yield / SUM(fcf_yield) OVER (PARTITION BY date) AS weight
FROM raw
"""
```

---

## 模式六：自定义 handle_data（海龟/趋势跟踪）

需要逐日判断信号的策略，使用自定义 handle_data。

```python
from bigquant import bigtrader, dai

def initialize(context: bigtrader.IContext):
    context.set_commission(bigtrader.PerOrder(
        buy_cost=0.0003, sell_cost=0.0013, min_cost=5
    ))
    context.max_positions = 10
    context.entry_window = 20
    context.exit_window = 10

    # handle_data 在当日K线收盘后运行，当日 close 已确定，订单在次日开盘撮合
    # close = 当日收盘价，upper/lower = 前一日的通道边界（lag(1) 排除当日 high/low）
    sql = """
    SELECT
        date,
        instrument,
        close,
        m_lag(m_max(high, 20), 1) AS upper,
        m_lag(m_min(low, 10), 1) AS lower
    FROM cn_stock_prefactors
    WHERE list_sector IN (1, 2, 3)
      AND st_status = 0
      AND suspended = 0
      AND list_days > 252
      AND m_avg(amount, 20) > 50000000
    QUALIFY COLUMNS(*) IS NOT NULL
    """

    df = dai.query(sql, filters={
        "date": [
            context.add_trading_days(context.start_date, -50),
            context.end_date
        ]
    }).df()
    context.signal_data = df

def handle_data(context: bigtrader.IContext, data: bigtrader.IBarData):
    today = data.current_dt.strftime('%Y-%m-%d')
    today_data = context.signal_data[context.signal_data['date'] == today]

    if today_data.empty:
        return

    positions = context.get_account_positions()

    # 止损：当日收盘跌破下轨 → 次日卖出
    for inst in list(positions.keys()):
        row = today_data[today_data['instrument'] == inst]
        if not row.empty and row.iloc[0]['close'] < row.iloc[0]['lower']:
            context.order_target_percent(inst, 0)
            context.logger.info(f"止损卖出 {inst}")

    # 入场：当日收盘突破上轨 → 次日买入
    positions = context.get_account_positions()
    if len(positions) < context.max_positions:
        breakout = today_data[today_data['close'] > today_data['upper']]
        breakout = breakout.sort_values('close', ascending=False)
        for _, row in breakout.iterrows():
            if row['instrument'] not in positions:
                weight = 1.0 / context.max_positions
                context.order_target_percent(row['instrument'], weight)
                positions = context.get_account_positions()
                if len(positions) >= context.max_positions:
                    break

performance = bigtrader.run(
    market=bigtrader.Market.CN_STOCK,
    frequency=bigtrader.Frequency.DAILY,
    start_date="2021-01-01",
    end_date="2026-05-01",
    capital_base=1000000,
    initialize=initialize,
    handle_data=handle_data,
)
```

---

## 常见错误与解决

| 错误 | 原因 | 解决 |
|------|------|------|
| `PermissionException` | 大表未使用 filters | 添加 `filters={"date": [...]}` |
| 窗口函数返回 NULL | 缓冲期不足 | 增大 `add_trading_days` 的偏移量 |
| `c_pct_rank` 全为 NULL | 与 `m_avg` 在同一 CTE 层 | 分两层 CTE |
| 选股数量为 0 | QUALIFY 条件过严 | 放宽条件或检查因子分布 |
| 回测无交易 | df 为空或列名不对 | 确保 df 含 date, instrument, weight 列 |
| Kernel OOM 崩溃 | Python端 groupby().rank() 或 .apply(lambda) | 改用 SQL ORDER BY + groupby().head() |
| `rebalance_period` TypeError | 传给了 bigtrader.run() | 改用 TradingDaysRebalance |

---

## 模式七：质量红利筛选（实战验证，夏普>1）

最简洁高效的基本面选股模式：严格WHERE条件筛选 + 单因子排序 + groupby().head()。
无需CTE、无需Python端排名，内存友好。

```python
from bigquant import bigtrader, dai
import pandas as pd
import numpy as np

def initialize(context: bigtrader.IContext):
    context.set_commission(bigtrader.PerOrder(
        buy_cost=0.0003, sell_cost=0.0013, min_cost=5
    ))

    stock_num = 15
    rebalance_days = 10

    sql = """
    SELECT
        date,
        instrument,
        dividend_yield_ratio
    FROM cn_stock_prefactors
    WHERE
        is_zz1000 = 1
        AND list_sector IN (1, 2)
        AND st_status = 0
        AND suspended = 0
        AND list_days > 252
        AND amount > 100000000
        AND roe_avg_lf_consec_min_3y > 0.06
        AND roe_avg_ttm_yoy > 0
        AND dividend_yield_ratio > 0.03
        AND debt_to_asset_lf < 0.6
        AND pe_ttm > 3 AND pe_ttm < 30
        AND net_profit_to_parent_shareholders_ttm_yoy > 0
    ORDER BY date, dividend_yield_ratio DESC
    """

    df = dai.query(
        sql,
        filters={"date": [context.start_date, context.end_date]},
    ).df()

    df = df.groupby('date', group_keys=False).head(stock_num)

    # 动态等权：候选不足 stock_num 时权重仍归一
    df['weight'] = df.groupby('date')['instrument'].transform('count')
    df['weight'] = 1.0 / df['weight']
    df = df[['date', 'instrument', 'weight']]

    df = bigtrader.TradingDaysRebalance(
        rebalance_days, context=context
    ).select_rebalance_data(df)

    context.data = df

performance = bigtrader.run(
    market=bigtrader.Market.CN_STOCK,
    frequency=bigtrader.Frequency.DAILY,
    start_date='2021-01-01',
    end_date='2025-12-31',
    capital_base=1000000,
    initialize=initialize,
    handle_data=bigtrader.HandleDataLib.handle_data_weight_based,
)
# 回测结果：年化16.65%，夏普1.04，最大回撤-14.93%
```

**核心思路**：用多个WHERE条件构建高质量候选池（ROE稳定+成长+低负债+合理估值），然后用单一强因子（股息率）排序选股。这种模式比复杂的多因子合成更稳健，且完全避免了Python端的内存问题。
