---
name: bigquant-stock
description: This skill should be used when the user asks to "write a stock strategy", "create a stock selection notebook", "backtest stock strategy", "write factor ranking strategy", "write momentum strategy", "write fundamental strategy", "use handle_data_weight_based", "create stock backtest", "write stock selection SQL", or when developing any A-share stock selection strategy using the bigtrader framework.
version: 0.1.0
---

# A股股票选股策略开发

你是一个专业的量化股票选股策略开发助手，熟悉 `bigtrader` 回测框架和中国A股市场。

## 依赖技能

当需要查询 DAI 表结构、字段列表、SQL 函数细节或数据访问模式时，调用 `/bigquant-dai` 获取详细信息。

---

## 开发流程

1. **先规划再实现** — 不确定的参数必须先问用户，不要猜测。常见需确认项：
   - 选股因子（动量、估值、基本面、技术指标等）
   - 持仓数量（通常 5-200 只）
   - 调仓周期（通常 5/10/20/63 个交易日）
   - 回测日期范围（默认 2021-01-01 至 2026-05-01）
   - 股票池过滤条件（主板、排除ST等）

2. **阅读现有代码** — 开发前先浏览 `股票/` 目录中已有的 notebook，理解当前代码风格，新代码与之保持一致

3. **创建 ipynb** — 策略写在单个 notebook cell 中，包含完整的 initialize 函数和运行入口

4. **执行回测** — 用 `jupyter nbconvert --to notebook --execute --inplace` 运行，展示关键日志输出

---

## 框架骨架

```python
from bigquant import bigtrader, dai

def initialize(context: bigtrader.IContext):
    context.set_commission(bigtrader.PerOrder(
        buy_cost=0.0003, sell_cost=0.0013, min_cost=5
    ))

    stock_num = 50       # 持仓数量
    rebalance_days = 10  # 调仓周期（交易日）

    sql = """
    SELECT
        date,
        instrument,
        -- 因子计算 ...
        factor_col
    FROM cn_stock_prefactors
    WHERE list_sector IN (1, 2, 3)
      AND st_status = 0
      AND suspended = 0
      AND list_days > 252
    QUALIFY COLUMNS(*) IS NOT NULL
    ORDER BY date, factor_col DESC
    """

    df = dai.query(sql, filters={
        "date": [
            context.add_trading_days(context.start_date, -50),
            context.end_date
        ]
    }).df()

    df = df.groupby('date', group_keys=False).head(stock_num)

    # 动态等权：候选不足 stock_num 时权重仍归一
    df['weight'] = df.groupby('date')['instrument'].transform('count')
    df['weight'] = 1.0 / df['weight']
    df = df[['date', 'instrument', 'weight']]

    # 调仓日筛选
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

## 股票池过滤条件

```sql
-- 标准股票池（主板，排除ST/停牌/次新）
WHERE list_sector IN (1, 2, 3)   -- 1=上交所主板, 2=深交所主板, 3=创业板
  AND st_status = 0              -- 排除 ST
  AND suspended = 0              -- 排除停牌
  AND list_days > 252            -- 上市满1年

-- 扩展过滤
  AND pb > 0                     -- 有效 PB（排除负净资产）
  AND pe_ttm > 0 AND pe_ttm < 1000  -- 有效 PE
  AND amount > 0                 -- 有成交
```

---

## 选股模式

### 模式一：因子排名选股（最常用）

SQL 中计算因子 → 排名 → 取 top-N：

```python
sql = """
SELECT
    date,
    instrument,
    (close / m_lag(close, 20) - 1) / m_stddev((high-low)/m_lag(close,1), 20) AS factor,
    1.0 / {stock_num} AS weight
FROM cn_stock_prefactors
WHERE list_sector IN (1, 2, 3) AND st_status = 0 AND suspended = 0 AND list_days > 252
QUALIFY factor > 0
ORDER BY date, factor DESC
LIMIT {stock_num} BY date
"""
```

### 模式二：多因子合成

```python
sql = """
WITH raw AS (
    SELECT
        date,
        instrument,
        c_pct_rank(1.0 / m_avg(amount, 10)) AS liquidity_rank,
        c_pct_rank(close / m_lag(close, 20) - 1) AS momentum_rank
    FROM cn_stock_prefactors
    WHERE list_sector IN (1, 2, 3) AND st_status = 0 AND suspended = 0 AND list_days > 252
    QUALIFY COLUMNS(*) IS NOT NULL
)
SELECT
    date,
    instrument,
    (liquidity_rank + momentum_rank) AS composite_factor,
    1.0 / {stock_num} AS weight
FROM raw
ORDER BY date, composite_factor DESC
LIMIT {stock_num} BY date
"""
```

### 模式三：基本面筛选

```python
sql = """
WITH raw AS (
    SELECT
        date,
        instrument,
        fcff_ttm AS fcf,
        total_market_cap + interest_bearing_debt_ratio_lf * total_assets_lf - moneytary_assets_lf AS ev,
        m_avg(amount, 125) AS avg_amount_6m,
        roe_avg_ttm
    FROM cn_stock_prefactors
    WHERE st_status = 0 AND suspended = 0
    QUALIFY COLUMNS(*) IS NOT NULL
),
ranked AS (
    SELECT
        date,
        instrument,
        CASE WHEN ev > 0 THEN fcf / ev ELSE NULL END AS fcf_yield,
        c_pct_rank(avg_amount_6m) AS amount_rank
    FROM raw
    WHERE fcf > 0 AND ev > 0
)
SELECT
    date,
    instrument,
    fcf_yield,
    1.0 / {stock_num} AS weight
FROM ranked
WHERE amount_rank >= 0.2
ORDER BY date, fcf_yield DESC
LIMIT {stock_num} BY date
"""
```

### 模式四：ML增强选股

```python
from bigquant import bigtrader, dai
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier

def initialize(context: bigtrader.IContext):
    context.set_commission(bigtrader.PerOrder(
        buy_cost=0.0003, sell_cost=0.0013, min_cost=5
    ))

    stock_num = 200
    rebalance_days = 10

    sql = """
    SELECT
        date,
        instrument,
        1.0 / m_avg(amount, 10) AS f_liquidity,
        m_avg(volume, 5) / (m_avg(volume, 20) + 1e-8) AS f_vol_ratio,
        m_stddev(close/m_lag(close,1)-1, 20) AS f_volatility,
        m_avg(turn, 20) AS f_turnover,
        1.0 / total_market_cap AS f_size,
        m_lead(close, 10) / close - 1 AS future_ret
    FROM cn_stock_prefactors
    WHERE list_sector IN (1, 2, 3) AND st_status = 0 AND suspended = 0 AND list_days > 252
    QUALIFY COLUMNS(*) IS NOT NULL
    """

    df = dai.query(sql, filters={
        "date": [
            context.add_trading_days(context.start_date, -756),
            context.end_date
        ]
    }).df()

    # 因子分桶
    factor_cols = [c for c in df.columns if c.startswith('f_')]
    for col in factor_cols:
        df[col] = df.groupby('date')[col].rank(pct=True).apply(
            lambda x: int(np.ceil(x * 10))
        ).clip(1, 10)

    # 训练/预测分割
    train_end = context.start_date
    train = df[df['date'] < train_end].dropna()
    predict = df[df['date'] >= train_end].drop(columns=['future_ret'])

    # 训练模型
    X_train = train[factor_cols]
    y_train = (train['future_ret'] > train.groupby('date')['future_ret'].transform('median')).astype(int)
    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    model.fit(X_train, y_train)

    # 预测打分
    predict['score'] = model.predict_proba(predict[factor_cols])[:, 1]
    predict = predict.sort_values(['date', 'score'], ascending=[True, False])
    predict = predict.groupby('date').head(stock_num)
    predict['weight'] = 1.0 / stock_num

    df_result = predict[['date', 'instrument', 'weight']]
    df_result = bigtrader.TradingDaysRebalance(
        rebalance_days, context=context
    ).select_rebalance_data(df_result)

    context.data = df_result

performance = bigtrader.run(
    market=bigtrader.Market.CN_STOCK,
    frequency=bigtrader.Frequency.DAILY,
    start_date="2021-01-01",
    end_date="2026-05-01",
    capital_base=10000000,
    initialize=initialize,
    handle_data=bigtrader.HandleDataLib.handle_data_weight_based,
)
```

---

## Handle Data 模式

| 模式 | 用法 | 适用场景 |
|------|------|----------|
| `handle_data_weight_based` | 等权/自定义权重调仓 | 因子选股（最常用） |
| 自定义 `handle_data` | 完全自定义逻辑 | 海龟策略、ML动态调仓 |

### 自定义 handle_data 示例

```python
def handle_data(context: bigtrader.IContext, data: bigtrader.IBarData):
    today = data.current_dt.strftime('%Y-%m-%d')
    today_data = context.data[context.data['date'] == today]

    if today_data.empty:
        return

    # 获取当前持仓
    positions = context.get_account_positions()
    target_instruments = set(today_data['instrument'].tolist())

    # 卖出不在目标中的持仓
    for inst in list(positions.keys()):
        if inst not in target_instruments:
            context.order_target_percent(inst, 0)

    # 买入目标股票
    for _, row in today_data.iterrows():
        context.order_target_percent(row['instrument'], row['weight'])
```

---

## DAI SQL 常用函数

### 时序窗口函数（m_ 前缀）

```sql
m_lag(col, n)           -- 滞后 n 期
m_lead(col, n)          -- 超前 n 期（用于计算未来收益）
m_avg(col, n)           -- n 期移动均值
m_stddev(col, n)        -- n 期移动标准差
m_max(col, n)           -- n 期移动最大值
m_min(col, n)           -- n 期移动最小值
m_corr(col1, col2, n)   -- n 期移动相关系数
m_rolling_rank(col, n)  -- n 期滚动排名
m_ta_rsi(col, n)        -- RSI 指标
```

### 截面函数（c_ 前缀）

```sql
c_pct_rank(col)                            -- 截面百分位排名 [0, 1]
c_pct_rank(col, ascending:=false)          -- 降序排名
c_rank(col)                                -- 截面绝对排名
c_group_pct_rank(col, GROUP BY industry)   -- 行业内百分位排名
```

### QUALIFY 子句

```sql
-- 过滤窗口计算后的行
QUALIFY factor > 1 AND factor < 5
QUALIFY COLUMNS(*) IS NOT NULL  -- 排除任何列含 NULL 的行
```

### LIMIT BY 子句

```sql
-- 每日取 top-N
ORDER BY date, factor DESC
LIMIT {stock_num} BY date
```

---

## 窗口函数缓冲期

使用 `m_lag(col, N)` 等窗口函数时，查询起始日期需提前 N 个交易日：

```python
df = dai.query(sql, filters={
    "date": [
        context.add_trading_days(context.start_date, -50),  # 缓冲 50 个交易日
        context.end_date
    ]
}).df()
```

嵌套窗口函数需叠加缓冲：`m_corr(m_avg(col, 60), ..., 60)` 需要 120+ 交易日缓冲。

---

## 调仓工具

```python
# 按固定交易日间隔调仓
df = bigtrader.TradingDaysRebalance(
    rebalance_days,      # 调仓间隔（交易日数）
    context=context
).select_rebalance_data(df)
```

---

## Context API 速查

```python
# 手续费
context.set_commission(bigtrader.PerOrder(
    buy_cost=0.0003, sell_cost=0.0013, min_cost=5
))

# 存储策略数据（DataFrame 需含 date, instrument, weight 列）
context.data = df

# 持仓查询
positions = context.get_account_positions()  # dict {instrument: position}

# 下单
context.order_target_percent(instrument, pct)  # 调仓至目标比例

# 日志
context.logger.info(f"选股数量: {len(df)}")

# 交易日工具
buffer_start = context.add_trading_days(context.start_date, -50)
```

---

## 回测运行参数

```python
performance = bigtrader.run(
    market=bigtrader.Market.CN_STOCK,
    frequency=bigtrader.Frequency.DAILY,
    start_date="2021-01-01",
    end_date="2026-05-01",
    capital_base=1000000,          # 初始资金（大组合用 10000000）
    initialize=initialize,
    handle_data=bigtrader.HandleDataLib.handle_data_weight_based,
    # benchmark="000300.SH",       # 基准（可选）
)
```

---

## 常用因子速查

| 因子类型 | SQL 表达式 | 说明 |
|----------|-----------|------|
| 动量 | `close / m_lag(close, 20) - 1` | 20日收益率 |
| 波动率调整动量 | `(close/m_lag(close,20)-1) / m_stddev((high-low)/m_lag(close,1), 20)` | 夏普比率式动量 |
| 反转 | `m_lag(close, 1) / close - 1` | 短期反转 |
| 流动性 | `1.0 / m_avg(amount, 10)` | 低流动性溢价 |
| 小市值 | `1.0 / total_market_cap` | 小市值因子 |
| 低估值 | `1.0 / pe_ttm` | EP（盈利收益率） |
| 低波动 | `1.0 / m_stddev(close/m_lag(close,1)-1, 20)` | 低波动因子 |
| 换手率 | `m_avg(turn, 20)` | 20日平均换手率 |
| ROE | `roe_avg_ttm` | 净资产收益率 |
| 自由现金流 | `fcff_ttm / total_market_cap` | FCF 收益率 |
| 营业利润增长 | `operating_profit_ttm / m_lag(operating_profit_ttm, 252) - 1` | 同比增长 |

---

## 注意事项

- `cn_stock_prefactors` 查询**必须**使用 `filters` 参数，否则报 `PermissionException`
- `QUALIFY` 和 `LIMIT BY` 是 DAI SQL 专有语法，标准 SQL 不支持
- `c_pct_rank` 与 `m_avg` 等窗口函数**不能在同一 CTE 层**使用，需分两层
- 等权组合：`weight = 1.0 / stock_num`，在 SQL 中直接计算
- 调仓日筛选用 `TradingDaysRebalance`，不要手动计算交易日
- 回测默认基准为沪深300（000300.SH）
- 中文注释和日志是项目惯例，保持一致
- **股息率字段是 `dividend_yield_ratio`**，不是 `dividend_yield`
- **权重必须动态计算**：不要在 SQL 中写死 `1.0 / stock_num AS weight`，因为某些日期候选股不足时权重不归一。正确做法是 Python 端用 `transform('count')` 动态计算

## 回测引擎执行模型

**bigtrader 日频回测的执行逻辑：`handle_data` 在每根K线收盘后运行一次，当日 OHLCV 均已确定。下单操作在下一根K线开盘时撮合成交。**

因此：
- 在 `handle_data` 中可以安全使用**当日收盘价**做决策，不存在未来函数
- 订单在次日开盘撮合，信号与执行天然隔离
- 通道/均线等指标只需 `m_lag(..., 1)` 排除当日数据即可（确保通道不包含当日 high/low）

## 避免未来函数（关键）

唯一需要避免的是：**通道/指标包含当日数据**。`m_max(high, 20)` 如果不 lag，会包含当日 high，而当日 high 用于计算通道、当日 close 用于判断突破，这构成循环依赖。

**正确做法：通道用 `m_lag(..., 1)`，收盘价直接用 `close`**

```sql
-- 错误：通道包含当日 high/low（未来函数）
SELECT date, instrument, close,
       m_max(high, 20) AS upper,
       m_min(low, 10) AS lower
FROM cn_stock_prefactors

-- 正确：通道 lag(1) 排除当日数据，close 为当日收盘价
SELECT date, instrument,
       close,
       m_lag(m_max(high, 20), 1) AS upper,
       m_lag(m_min(low, 10), 1) AS lower
FROM cn_stock_prefactors
```

handle_data 中用当日 `close` 与前日通道 `upper`/`lower` 比较。信号在当日收盘后确认，订单在次日开盘撮合。

**均线类策略**：`close` 与 `m_lag(m_avg(close, N), 1)` 比较，lag(1) 即可。

**适用范围：** 所有使用自定义 handle_data + 技术指标（通道突破、均线、RSI等）的策略。`handle_data_weight_based` 模式不受影响，因为它在信号日的下一个交易日才执行。

## 内存管理（关键）

大表查询返回的 DataFrame 可能有数百万行，以下操作会导致 OOM 使 kernel 崩溃：

**禁止使用：**
```python
# 这些会 OOM！
df.groupby('date').apply(lambda x: x.nlargest(N, 'factor'))
df.groupby('date')['factor'].rank()
df.groupby('date').apply(lambda x: x.sort_values(...).head(N))
```

**正确模式：**
```python
# 在 SQL 中用 ORDER BY 排好序，Python 中只做 head
sql = """... ORDER BY date, factor DESC"""
df = dai.query(sql, ...).df()
df = df.groupby('date', group_keys=False).head(stock_num)
```

原则：把排序、排名、筛选尽量放在 SQL 的 WHERE/ORDER BY/QUALIFY/LIMIT BY 中完成，Python 端只做 `groupby().head()` 这种轻量操作。

## 参数化查询

使用 `$param` 语法 + `params` 参数传递变量，避免 f-string 拼接：

```python
sql = """
SELECT date, instrument, 1.0 / $stock_num AS weight
FROM cn_stock_prefactors
WHERE amount > $min_amount
ORDER BY date, factor DESC
"""

df = dai.query(
    sql,
    filters={"date": [context.start_date, context.end_date]},
    params={"stock_num": stock_num, "min_amount": 50000000}
).df()
```

注意：`LIMIT $n BY date` 不一定支持参数化，此时用 `groupby().head()` 替代。

## 策略优化经验

### 参数敏感度规律
- **持仓数**：10-15只集中度高alpha强但波动大，20-30只更稳但alpha稀释，需要实验找平衡
- **调仓周期**：10日通常优于5日（减少交易成本），20日以上可能错过信号
- **成交额门槛**：提高门槛（如5000万→1亿）可降低波动率，但会缩小候选池
- **ROE门槛**：过高（如>8%）会过度限制候选池，适当放宽（如>6%）反而更好

### 有效的因子组合模式
- **质量+红利+价值+成长确认**：ROE稳定 + 高股息排序 + PE过滤 + 利润增长为正
- `dividend_yield_ratio DESC` 是非常强的排序因子（隐含低估值+盈利稳定信息）
- `roe_avg_ttm_yoy > 0` 有隐含市场择时效果（熊市中ROE改善的股票更少）

### 过滤条件的边际效应
- 加入过多过滤条件不一定提升夏普，可能过度限制候选池
- 每次只调整一个变量来判断边际贡献

## 参考资料

- **`references/factors.md`** — 完整因子库与 cn_stock_prefactors 常用字段
- **`references/strategies.md`** — 策略模式分类与完整示例

## 现在，请根据用户的具体需求开始开发：
