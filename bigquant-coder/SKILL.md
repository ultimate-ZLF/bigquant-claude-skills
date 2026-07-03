---
name: bigquant-coder
description: This skill should be used when the user asks to write any BigQuant strategy or query — including "write a stock strategy", "create a stock selection notebook", "backtest stock strategy", "write factor ranking strategy", "write momentum strategy", "write fundamental strategy", "write an option strategy", "create an ETF option strategy", "backtest option strategy", "write covered call strategy", "write put selling strategy", "write delta hedging", "use bigtrader for options", "query data with dai", "write a dai query", "use dai.query", "query stock data", "query option data", "query ETF data", "query futures data", "write SQL for bigquant", "use cn_stock_prefactors", "use cn_fund_bar1m", "use cn_option_bar1m", or when developing any strategy or data query using the bigtrader/DAI framework.
version: 1.0.3
---

# BigQuant 量化开发助手

你是一个专业的量化策略开发助手，熟悉 `bigtrader` 回测框架、DAI 数据访问层和中国金融市场（A股、ETF期权、期货）。

本 skill 覆盖四个领域，按需查阅对应章节：

- **[DAI 数据查询](#dai-数据查询)** — `dai.query()`、表结构、SQL 函数、filters
- **[股票选股策略](#股票选股策略)** — `cn_stock_prefactors`、因子、`handle_data_weight_based`
- **[期权策略](#期权策略)** — ETF期权、`buy_open/sell_close`、`handle_order`、持仓查询
- **[期货 CTA 策略](#期货-cta-策略)** — 状态机模式、`CN_FUTURE`、`PerContract`

---

## 开发通则

1. **先规划再实现** — 不确定的参数先问用户，不要猜测
2. **阅读现有代码** — 开发前先浏览对应目录已有 notebook，保持风格一致
3. **创建 ipynb** — 策略写在单个 notebook cell 中，包含完整函数和运行入口
4. **执行回测** — 用 `jupyter nbconvert --to notebook --execute --inplace` 运行
5. **分钟级策略两条铁律**（适用于股票、ETF、期货、期权所有资产类别）：
   - **`initialize` 中用 `dai.query()` 预加载历史 K 线**，填充策略所需的滚动窗口初始值；不能依赖 `handle_data` 从零累积，否则回测启动后需等待 N 根 bar 才能出信号
   - **`before_trading_start` 中调用 `context.subscribe_bar(instruments)` 订阅行情**，分钟级回测不自动推送 bar，不订阅则 `handle_data` 收不到数据

---

## DAI 数据查询

BigQuant DAI 是平台专有的 SQL 数据访问层，通过 `dai.query(sql, filters={...})` 接口查询金融数据。

### 核心用法

```python
from bigquant import dai

df = dai.query(
    sql,
    filters={"date": ["2020-01-01", "2023-12-31"]}
).df()
```

**三种输出格式：**

```python
.df()      # pandas DataFrame（最常用）
.pl()      # Polars DataFrame（大数据量时更快）
.arrow()   # Arrow 格式
```

### filters 参数（必须）

大表查询**必须**使用 `filters` 参数，否则报 `PermissionException`。

```python
# 按日期范围（最常用）
filters={"date": ["2020-01-01", "2023-12-31"]}

# 单日
filters={"date": ["2023-12-31", "2023-12-31"]}

# 多字段
filters={"date": ["2023-01-01", "2023-12-31"], "instrument": ["000001.SZ", "000100.SZ"]}
```

**注意：** WHERE 子句中写了日期条件不等于 filters，两者都要写。

**必须使用 filters 的大表：**

| 表名 | 内容 |
|------|------|
| `cn_stock_prefactors` | 股票日线因子（最常用） |
| `cn_stock_bar1d` | 股票日线 K 线 |
| `cn_stock_status` | 股票状态 |
| `cn_stock_valuation` | 估值数据 |
| `cn_stock_factors` | 因子数据 |
| `cn_future_bar1m` | 期货 1 分钟 K 线 |
| `cn_fund_bar1m` | ETF/基金 1 分钟 K 线 |
| `cn_option_bar1m` | 期权 1 分钟 K 线 |

**小表（无需 filters）：**

| 表名 | 内容 |
|------|------|
| `cn_option_basic_info` | 期权合约基本信息 |
| `cn_future_basic_info` | 期货合约基本信息 |
| `cn_future_dominant` | 期货主力合约换月记录 |

### 常用数据表速查

```python
# 股票日线因子（含价格、估值、财务、技术指标）
sql = """
SELECT date, instrument, close, open, high, low, volume,
       pe_ttm, pb, roe, st_status, suspended
FROM cn_stock_prefactors
WHERE st_status = 0 AND suspended = 0
ORDER BY date, instrument
"""
df = dai.query(sql, filters={"date": [start_date, end_date]}).df()

# 股票日线 K 线
sql = "SELECT date, instrument, open, high, low, close, volume FROM cn_stock_bar1d"
df = dai.query(sql, filters={"date": [start_date, end_date]}).df()

# 指数日线
sql = "SELECT date, instrument, close FROM cn_stock_index_bar1d WHERE instrument='000300.SH'"
df = dai.query(sql, filters={"date": [start_date, end_date]}).df()

# ETF 日线
sql = "SELECT date, instrument, open, high, low, close, volume FROM cn_fund_bar1d"
df = dai.query(sql, filters={"date": [start_date, end_date]}).df()

# ETF/基金 1 分钟（需要 filters）
sql = f"""
SELECT date, open, high, low, close, volume
FROM cn_fund_bar1m
WHERE instrument='{etf_symbol}'
ORDER BY date
"""
df = dai.query(sql, filters={"date": [start_date, end_date]}).df()

# 期权合约基本信息（无需 filters）
sql = """
SELECT instrument, underlying, strike_price, option_type,
       list_date, delist_date, multiplier
FROM cn_option_basic_info
WHERE underlying = '510050.SH'
"""
df = dai.query(sql).df()

# 期权 1 分钟 K 线（需要 filters）
sql = f"""
SELECT date, instrument, open, high, low, close, volume
FROM cn_option_bar1m
WHERE instrument='{option_symbol}'
ORDER BY date
"""
df = dai.query(sql, filters={"date": [start_date, end_date]}).df()

# 期货日线
sql = "SELECT date, instrument, open, high, low, close, volume FROM cn_future_bar1d"
df = dai.query(sql, filters={"date": [start_date, end_date]}).df()

# 期货 1 分钟 K 线（需要 filters，含 trading_day 整数字段和 open_interest）
sql = f"""
SELECT date, instrument, trading_day, open, high, low, close, volume, amount, open_interest, product_code
FROM cn_future_bar1m
WHERE instrument='{instrument}'
ORDER BY date
"""
df = dai.query(sql, filters={"date": [start_date, end_date]}).df()

# 期货主力合约换月记录（无需 filters）
# instrument: 主力连续代码，如 jm8888.DCE；dominant: 实际合约，如 jm2609.DCE；product_code: 品种，如 jm
sql = "SELECT date, instrument, dominant, product_code FROM cn_future_dominant"
df = dai.query(sql).pl()
# 筛选某品种，过滤连续重复行（只保留换月时间点）：
# df.filter(pl.col('product_code')=='jm').filter(pl.col('dominant')!=pl.col('dominant').shift(1))

# 期货合约信息（无需 filters）
sql = "SELECT instrument, delist_date FROM cn_future_basic_info WHERE product='IF'"
df = dai.query(sql).df()
```

### DAI SQL 专有函数

#### 截面函数（c_ 前缀）

```sql
-- 基础统计
c_avg(col)                                      -- 截面均值
c_count(col)                                    -- 截面非空个数
c_sum(col)                                      -- 截面求和
c_std(col)                                      -- 截面标准差
c_var(col)                                      -- 截面方差
c_median(col)                                   -- 截面中位数
c_mad(col)                                      -- 截面绝对中位差

-- 排名和分位数
c_rank(col)                                     -- 截面绝对排名
c_pct_rank(col)                                 -- 截面百分位排名 [0, 1]
c_pct_rank(col, ascending:=false)               -- 降序排名
c_quantile_cont(col, 0.5)                       -- 插值分位数
c_quantile_disc(col, 0.5)                       -- 最近确切分位数

-- 标准化和归一化
c_normalize(col)                                -- Z-score 标准化
c_zscore(col)                                   -- Z-score 标准化（同 c_normalize）
c_scale(col)                                    -- 缩放
c_min_max_scalar(col)                           -- 最小最大缩放

-- 分组操作
c_group_avg(col, GROUP BY industry)             -- 分组均值
c_group_pct_rank(col, GROUP BY industry)        -- 行业内百分位排名
c_group_std(col, GROUP BY industry)             -- 分组标准差

-- 中性化
c_indneutralize(col, industry)                  -- 行业中性化
c_neutralize(col, industry, market_cap)         -- 行业市值中性化
c_ols2d_resid(y, x)                             -- 二元线性回归残差
c_regr_residual(y, x)                           -- 线性回归残差
```

#### 时序窗口函数（m_ 前缀）

```sql
-- 基础统计
m_avg(col, n)              -- n 期移动均值
m_sum(col, n)              -- n 期移动求和
m_max(col, n)              -- n 期移动最大值
m_min(col, n)              -- n 期移动最小值
m_count(col, n)            -- n 期移动计数
m_stddev(col, n)           -- n 期移动标准差
m_variance(col, n)         -- n 期移动方差
m_median(col, n)           -- n 期移动中位数

-- 偏移和变化
m_lag(col, n)              -- 向下偏移 n 行（历史值）
m_lead(col, n)             -- 向上偏移 n 行（未来值，用于计算未来收益）
m_shift(col, n)            -- 双向偏移（正=lag，负=lead）
m_delta(col, n)            -- 差值：col - m_lag(col, n)

-- 累计计算
m_cumsum(col)              -- 累计和
m_cumprod(col)             -- 累计乘积
m_cummax(col)              -- 累计最大值
m_cummin(col)              -- 累计最小值

-- 相关性和回归
m_corr(col1, col2, n)      -- n 期移动相关系数
m_covar_pop(col1, col2, n) -- n 期总体协方差
m_covar_samp(col1, col2, n)-- n 期样本协方差
m_regr_slope(y, x, n)      -- n 期回归斜率
m_regr_intercept(y, x, n)  -- n 期回归截距
m_regr_r2(y, x, n)         -- n 期决定系数 R²

-- 排名和分位数
m_pct_rank(col, n)         -- n 期时序百分数排名
m_rolling_rank(col, n)     -- n 期滚动排名
m_quantile_cont(col, n, q) -- n 期时序分位数

-- 技术指标（m_ta_ 前缀）
m_ta_rsi(col, n)                        -- RSI 指标
m_ta_macd_dif(col, fast, slow, signal)  -- MACD DIF
m_ta_kdj_k(high, low, close, n)         -- KDJ K 值
m_ta_atr(high, low, close, n)           -- ATR 平均真实波幅
m_ta_cci(high, low, close, n)           -- CCI 商品通道指数
m_ta_obv(close, volume)                 -- OBV 平衡成交量
```

#### 特殊子句及其他

```sql
QUALIFY factor > 1 AND factor < 5        -- 过滤窗口计算后的行
QUALIFY COLUMNS(*) IS NOT NULL           -- 排除任何列含 NULL 的行
ORDER BY date, factor DESC
LIMIT {n} BY date                        -- 每日取 top-N（DAI 专有语法）
all_quantile_cont(col, 0.5)              -- 全局分位数
```

### 窗口函数缓冲期

使用 `m_lag(col, N)` 时，查询起始日期需提前 N 个交易日：

```python
# 使用 bigtrader 的交易日工具
df = dai.query(sql, filters={
    "date": [
        context.add_trading_days(context.start_date, -50),  # 缓冲 50 个交易日
        context.end_date
    ]
}).df()

# 或手动计算（约 1.5 倍日历日）
from datetime import datetime, timedelta
buffer_start = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=75)).strftime('%Y-%m-%d')
```

**嵌套窗口函数的缓冲期叠加：** `m_corr(m_avg(col, N), ..., N)` 需要 2N 个交易日缓冲。例如 N=60 时需约 180 个日历日：

```python
# N=60 的嵌套窗口，需要 ~180 天缓冲
buffer_start = (start_dt - timedelta(days=180)).strftime('%Y-%m-%d')
```

**CTE 内窗口函数的缓冲期陷阱：** `filters` 的日期范围决定了窗口函数能看到的历史数据，CTE 不会自动扩展缓冲期。缓冲期不足时，窗口函数在 CTE 内部同样返回 NULL，被 `QUALIFY COLUMNS(*) IS NOT NULL` 过滤后结果为空表。解决方法是在 `filters` 起始日期上加足够的缓冲，查询后再用 Python 过滤掉缓冲期数据：

```python
# 查询时加缓冲
df = dai.query(sql, filters={'date': [buffer_start, end_date]}).pl()
# 返回后过滤掉缓冲期
df = df.filter(pl.col('date') >= actual_start_date)
```

**`c_pct_rank` 与时序窗口函数不能在同一 CTE 层：** 分两层，第一层做时序特征，第二层做截面函数：

```sql
WITH ts_features AS (
    SELECT date, instrument,
        m_avg(close, 20) / close AS ma_close_20
    FROM cn_stock_prefactors
    QUALIFY COLUMNS(*) IS NOT NULL
)
SELECT date, instrument,
    ma_close_20,
    c_pct_rank(ma_close_20) AS cross_ma_close_20
FROM ts_features
```

### 参数化查询

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

### 用户自定义函数（UDF）

DAI 支持通过 `dai.DaiUDF` 将 Python 函数注册为 SQL 算子，用于内置函数无法表达的自定义逻辑（如对聚合后的列表做逐元素计算）。

```python
import dai

# 带类型声明的 UDF（推荐，类型声明帮助 DAI 做参数校验和序列化）
def calculate_factor(instrument: str, prices: list) -> float:
    """计算因子：平均价格 / 最后价格"""
    if not prices:
        return None

    avg_price = sum(prices) / len(prices)
    last_price = prices[-1]

    if last_price == 0:   # 避免除零错误
        return None

    return avg_price / last_price

df = dai.query(
    """
    WITH grouped_data AS (
        SELECT
            date::DATE::DATETIME AS date,
            instrument,
            ARRAY_AGG(close ORDER BY date) AS price_list
        FROM bigalpha_2026_stock_bar1m
        GROUP BY date::DATE, instrument
    )
    SELECT
        date,
        instrument,
        calculate_factor(instrument, price_list) AS factor
    FROM grouped_data
    ORDER BY date, instrument
    """,
    filters={"date": ["2023-01-01 00:00:00", "2023-02-01 23:59:59"]},
    compression=True,
    udf_list=[
        dai.DaiUDF(
            name="calculate_factor",
            function=calculate_factor,
        )
    ]
).df()
```

**要点：**

- UDF 函数名需与 SQL 中调用的算子名一致，通过 `udf_list` 传入 `dai.query()`
- 函数参数/返回值建议加类型声明（如 `str`, `list`, `float`），便于 DAI 校验
- 常与 `ARRAY_AGG(... ORDER BY date)` 搭配，将时间序列聚合为 list 后传入 UDF 做逐组计算
- UDF 在 DAI 引擎侧执行，逐行调用，数据量大时性能低于原生 SQL 窗口函数（`m_*`/`c_*`），仅在内置函数无法表达时使用
- 大表查询仍需按 `filters` 规则传日期范围，UDF 不能绕过该限制

### 常用表字段参考

详细字段列表见 **`references/tables.md`**，动态查询用 **`references/get_table_schema.py`**。

**常用指数代码：** `000300.SH` 沪深300、`000905.SH` 中证500、`000852.HIX` 中证1000

**常用 ETF 代码：** `510050.SH` 50ETF、`510300.SH` 300ETF、`588000.SH` 科创50ETF、`159919.SZ` 300ETF（嘉实）、`159915.SZ` 创业板ETF

### 常用 WHERE 过滤条件

```sql
-- 股票质量过滤
WHERE st_status = 0          -- 排除 ST
  AND suspended = 0          -- 排除停牌
  AND pb > 0                 -- 有效 PB
  AND pe_ttm > 0 AND pe_ttm < 1000  -- 有效 PE

-- 指数成分
WHERE is_zz500 = 1           -- 中证500成分
WHERE is_hs300 = 1           -- 沪深300成分

-- 行业（文本字段）
WHERE sw2021_level1 = '银行'

-- 按行业指数动量过滤（sw_level1_* 为所属申万一级行业指数行情）
-- sw_level1_name, sw_level_index_code, sw_level1_close/open/high/low/volume/amount/turn
WHERE sw_level1_close / m_lag(sw_level1_close, 20) - 1 > 0   -- 行业近20日上涨
```

### DAI 完整示例

**因子选股查询：**

```python
from bigquant import dai

sql = """
SELECT
    date,
    instrument,
    m_avg(close / m_lag(close, 1) - 1, 20) /
    (m_stddev(close / m_lag(close, 1) - 1, 20) + 1e-8) AS factor
FROM cn_stock_prefactors
WHERE st_status = 0
  AND suspended = 0
ORDER BY date, instrument
"""
df = dai.query(sql, filters={"date": [start_date, end_date]}).df()
```

**策略内实时查询（handle_data 中）：**

```python
def handle_data(context, data):
    current_dt = str(data.current_dt)[:19]  # 'YYYY-MM-DD HH:MM:SS'，截取前19位

    sql = f"""
    SELECT date, close, high, low
    FROM cn_fund_bar1m
    WHERE instrument='{context.etf_symbol}'
      AND date <= '{current_dt}'
    ORDER BY date DESC
    LIMIT 20
    """
    df = dai.query(sql).df()
    close_list = df['close'].tolist()
```

**期权到期日查询：**

```python
sql = """
SELECT instrument, delist_date
FROM cn_option_basic_info
WHERE underlying = '510050.SH'
  AND delist_date >= CURRENT_DATE
ORDER BY delist_date
"""
option_info = dai.query(sql).df()
```

### DAI 注意事项

- 日期格式必须为 `YYYY-MM-DD`，不能用 `YYYY/MM/DD`
- `filters` 中的日期范围与 SQL `WHERE` 中的日期条件**都要写**，两者不能互相替代
- 极少数情况需全表扫描时用 `full_db_scan=True`，但非常慢，避免使用
- 高频策略中查询 1 分钟数据时，注意用 `LIMIT` 控制返回行数，避免数据量过大

---

## 股票选股策略

### 回测框架骨架

```python
from bigquant import bigtrader, dai

def initialize(context: bigtrader.IContext):
    context.set_commission(bigtrader.PerOrder(
        buy_cost=0.0003, sell_cost=0.0013, min_cost=5
    ))

    stock_num = 50
    rebalance_days = 10

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

### 股票池标准过滤

```sql
WHERE list_sector IN (1, 2, 3)   -- 1=上交所主板, 2=深交所主板, 3=创业板
  AND st_status = 0              -- 排除 ST
  AND suspended = 0              -- 排除停牌
  AND list_days > 252            -- 上市满1年
  AND pb > 0                     -- 有效 PB（排除负净资产）
  AND pe_ttm > 0 AND pe_ttm < 1000
  AND amount > 0
```

### 选股模式

**模式一：单因子排名**（SQL 排序 → `groupby().head()`）

```sql
SELECT date, instrument,
    close / m_lag(close, 20) - 1 AS factor
FROM cn_stock_prefactors
WHERE list_sector IN (1, 2, 3) AND st_status = 0 AND suspended = 0 AND list_days > 252
QUALIFY factor > 0
ORDER BY date, factor DESC
```

**模式二：多因子合成**（截面排名加权）

```sql
WITH raw AS (
    SELECT date, instrument,
        c_pct_rank(1.0 / m_avg(amount, 10)) AS liquidity_rank,
        c_pct_rank(close / m_lag(close, 20) - 1) AS momentum_rank
    FROM cn_stock_prefactors
    WHERE list_sector IN (1, 2, 3) AND st_status = 0 AND suspended = 0 AND list_days > 252
    QUALIFY COLUMNS(*) IS NOT NULL
)
SELECT date, instrument,
    (liquidity_rank + momentum_rank) AS composite_factor
FROM raw
ORDER BY date, composite_factor DESC
```

**模式三：基本面筛选 + 单因子排序**（推荐，内存友好，实战夏普 > 1）

```sql
SELECT date, instrument, dividend_yield_ratio
FROM cn_stock_prefactors
WHERE is_zz1000 = 1
  AND list_sector IN (1, 2)
  AND st_status = 0 AND suspended = 0 AND list_days > 252
  AND amount > 100000000
  AND roe_avg_lf_consec_min_3y > 0.06
  AND roe_avg_ttm_yoy > 0
  AND dividend_yield_ratio > 0.03
  AND debt_to_asset_lf < 0.6
  AND pe_ttm > 3 AND pe_ttm < 30
  AND net_profit_to_parent_shareholders_ttm_yoy > 0
ORDER BY date, dividend_yield_ratio DESC
```

**模式三B：EV/FCF 收益率筛选**（多层 CTE + 流动性过滤）

```sql
WITH raw AS (
    SELECT
        date,
        instrument,
        fcff_ttm AS fcf,
        total_market_cap + interest_bearing_debt_ratio_lf * total_assets_lf
            - moneytary_assets_lf AS ev,
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
    fcf_yield
FROM ranked
WHERE amount_rank >= 0.2
ORDER BY date, fcf_yield DESC
```

**模式四：行业中性选股**

```sql
WITH raw AS (
    SELECT date, instrument,
        c_group_pct_rank(close / m_lag(close, 20) - 1, GROUP BY sw2021_level1) AS industry_rank
    FROM cn_stock_prefactors
    WHERE list_sector IN (1, 2, 3) AND st_status = 0 AND suspended = 0 AND list_days > 252
    QUALIFY COLUMNS(*) IS NOT NULL
)
SELECT date, instrument
FROM raw
WHERE industry_rank >= 0.8
ORDER BY date, industry_rank DESC
```

**模式五：ML 增强选股**（RandomForest 完整流程）

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

    # 因子分桶（10分位）
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

### Handle Data 模式

| 模式 | 用法 | 适用场景 |
|------|------|----------|
| `handle_data_weight_based` | 等权/自定义权重调仓 | 因子选股（最常用） |
| 自定义 `handle_data` | 完全自定义逻辑 | 通道突破、趋势跟踪 |

自定义 handle_data：

```python
def handle_data(context: bigtrader.IContext, data: bigtrader.IBarData):
    today = data.current_dt.strftime('%Y-%m-%d')
    today_data = context.data[context.data['date'] == today]
    if today_data.empty:
        return
    positions = context.get_account_positions()
    target_instruments = set(today_data['instrument'].tolist())
    for inst in list(positions.keys()):
        if inst not in target_instruments:
            context.order_target_percent(inst, 0)
    for _, row in today_data.iterrows():
        context.order_target_percent(row['instrument'], row['weight'])
```

### 避免未来函数（关键）

**执行模型：** `handle_data` 在每根K线收盘后运行，当日 OHLCV 已确定，订单在次日开盘撮合。

```sql
-- 错误：通道包含当日 high/low（未来函数）
SELECT date, instrument, close,
       m_max(high, 20) AS upper

-- 正确：通道 lag(1) 排除当日，close 为当日收盘
SELECT date, instrument, close,
       m_lag(m_max(high, 20), 1) AS upper,
       m_lag(m_min(low, 10), 1) AS lower
```

均线：`close` 与 `m_lag(m_avg(close, N), 1)` 比较。`handle_data_weight_based` 模式不受影响（信号日的下一交易日执行）。

### 内存管理（关键）

```python
# 禁止！会 OOM
df.groupby('date').apply(lambda x: x.nlargest(N, 'factor'))
df.groupby('date')['factor'].rank()

# 正确：SQL 排好序，Python 只做 head
sql = """... ORDER BY date, factor DESC"""
df = dai.query(sql, ...).df()
df = df.groupby('date', group_keys=False).head(stock_num)
```

### 常用因子速查

| 因子类型 | SQL 表达式 |
|----------|-----------|
| 动量 20日 | `close / m_lag(close, 20) - 1` |
| 波动率调整动量 | `(close/m_lag(close,20)-1) / m_stddev((high-low)/m_lag(close,1), 20)` |
| 短期反转 | `m_lag(close, 1) / close - 1` |
| 低流动性 | `1.0 / m_avg(amount, 10)` |
| 小市值 | `1.0 / total_market_cap` |
| EP（盈利收益率） | `1.0 / pe_ttm` |
| 低波动 | `1.0 / m_stddev(close/m_lag(close,1)-1, 20)` |
| 换手率 | `m_avg(turn, 20)` |
| ROE | `roe_avg_ttm` |
| FCF 收益率 | `fcff_ttm / total_market_cap` |
| 营业利润增长 | `operating_profit_ttm / m_lag(operating_profit_ttm, 252) - 1` |
| 行业动量 20日 | `sw_level1_close / m_lag(sw_level1_close, 20) - 1` |
| 行业换手率 | `sw_level1_turn` |
| 股息率（注意字段名） | `dividend_yield_ratio` |

### 策略优化经验

- **持仓数**：10-15只集中度高 alpha 强但波动大，20-30只更稳
- **调仓周期**：10日通常优于5日，20日以上可能错过信号
- **成交额门槛**：提高门槛（如5000万→1亿）可降低波动，但会缩小候选池
- **ROE门槛**：过高（如>8%）会过度限制候选池，适当放宽（如>6%）反而更好
- **`dividend_yield_ratio DESC`** 是非常强的排序因子（隐含低估值+盈利稳定）
- **`roe_avg_ttm_yoy > 0`** 有隐含市场择时效果（熊市中ROE改善的股票更少）
- 加入过多过滤条件不一定提升夏普，可能过度限制候选池
- 每次只调整一个变量判断边际贡献

### 回测运行参数

```python
performance = bigtrader.run(
    market=bigtrader.Market.CN_STOCK,
    frequency=bigtrader.Frequency.DAILY,
    start_date="2021-01-01",
    end_date="2026-05-01",
    capital_base=1000000,
    initialize=initialize,
    handle_data=bigtrader.HandleDataLib.handle_data_weight_based,
    # benchmark="000300.SH",  # 可选
)
performance.get_stats()  # 返回 DataFrame：年化收益、夏普、最大回撤、alpha、beta 等
```

### 注意事项（股票）

- `cn_stock_prefactors` 查询**必须**使用 `filters`，否则报 `PermissionException`
- `QUALIFY` 和 `LIMIT BY` 是 DAI SQL 专有语法，标准 SQL 不支持
- `c_pct_rank` 与 `m_avg` 等窗口函数**不能在同一 CTE 层**
- **权重必须动态计算**：用 `transform('count')` 而非 SQL 中写死 `1.0/stock_num`（候选不足时权重不归一）
- 调仓日筛选用 `TradingDaysRebalance`，不要手动计算交易日
- 股息率字段是 `dividend_yield_ratio`，不是 `dividend_yield`

---

## 期权策略

### 回测框架骨架

```python
from bigquant import bigtrader
import math

def _safe_price(data, instrument):
    """安全读取当前价格（过滤 None/NaN/负值）"""
    try:
        raw = data.current(instrument, 'close')
        if raw is None:
            return None
        val = float(raw)
        if math.isnan(val) or val <= 0:
            return None
        return val
    except Exception:
        return None

def initialize(context: bigtrader.IContext):
    context.set_commission(bigtrader.PerOrder(
        buy_cost=0.0003, sell_cost=0.0013, min_cost=5
    ))
    # 初始化 context 状态变量

def before_trading_start(context: bigtrader.IContext, data: bigtrader.IBarData):
    # 每天重置日内状态，订阅当日合约（含持仓合约）
    pass

def handle_data(context: bigtrader.IContext, data: bigtrader.IBarData):
    # 策略逻辑（所有交易必须在此执行）
    pass

def handle_order(context: bigtrader.IContext, order):
    # 委托状态变更回调（可选，需报撤单管理时必须传入）
    pass

Q = bigtrader.run(
    market=bigtrader.Market.CN_STOCK_OPTION,
    frequency=bigtrader.Frequency.MINUTE,
    instruments=["标的代码.SH"],   # 只传 ETF 标的代码，必须向用户确认
    benchmark=None,
    start_date='YYYY-MM-DD',
    end_date='YYYY-MM-DD',
    capital_base=500000,
    initialize=initialize,
    before_trading_start=before_trading_start,
    handle_data=handle_data,
    handle_order=handle_order,    # 可选
)
```

### 下单接口

**期权专用四向接口**（推荐，方向明确）：

```python
context.buy_open(symbol, qty)                           # 买入开仓（做多）
context.buy_open(symbol, qty, limit_price=price*1.002)  # 限价买入开仓
context.sell_close(symbol, qty)                         # 卖出平仓（平多头）
context.sell_open(symbol, qty)                          # 卖出开仓（卖出期权）
context.buy_close(symbol, qty)                          # 买入平仓（平空头）
```

**返回值为 int，< 0 表示失败：**

```python
ret = context.buy_open(symbol, qty)
if ret < 0:
    context.logger.error(f"买入开仓失败: {context.get_error_msg(ret)}")
else:
    order_key = context.get_last_order_key()
    # 注意：实盘中 order_key 异步返回，应通过 handle_order 获取可靠的 key
```

**通用接口（系统自动判断开平方向）：**

```python
context.order(symbol, volume)              # 正数=买，负数=卖；volume 为张数
context.order_value(symbol, value)         # 按金额下单（如 10000 元）
context.order_percent(symbol, percent)     # 按账户百分比下单（如 0.1 = 10%）
context.order_target(symbol, target_qty)   # 调仓至目标持仓量
context.order_target_value(symbol, value)  # 调仓至目标持仓市值
context.order_target_percent(symbol, pct)  # 调仓至目标仓位比例
```

> `order_target*` 系列在期权账户行为未充分验证，优先用明确的四向接口。

**委托管理：**

```python
context.cancel_order(order_key)
context.cancel_all()
context.cancel_all(symbol)
open_orders = context.get_open_orders(symbol)
all_orders  = context.get_orders(symbol)
trades      = context.get_trades(symbol)
context.exercise(symbol, qty)  # 行权
```

### handle_order 委托回报回调

`handle_order` 在委托状态变更时触发，实盘报撤单管理**必须**通过它实现。

**回测中已验证的触发序列：**

| 委托类型 | handle_order 触发序列 |
|---------|----------------------|
| 市价单（五档即成剩撤） | `NOTPLACE(10) → ALLTRADED(2)` |
| 限价单（正常成交） | `NOTPLACE(10) → NOTTRADED(0) → ALLTRADED(2)` |
| 限价单（主动撤单） | `NOTPLACE(10) → NOTTRADED(0) → CANCELLED(4)` |
| 大单部分成交 | `NOTPLACE(10) → NOTTRADED(0) → PARTTRADED(1) → ALLTRADED(2)` |

**收盘自动撤不触发 `handle_order`**，需在 `before_trading_start` 中主动清理。

**`order_status` 枚举（完整）：**

| 值 | 枚举名 | 含义 | 回测观测 |
|----|--------|------|----------|
| 0 | `NOTTRADED` | 未成交（已确认，尚未成交） | 限价单有此状态，市价单跳过 |
| 1 | `PARTTRADED` | 部分成交 | 大单流动性不足时，`filled_qty` 反映已成交量 |
| 2 | `ALLTRADED` | 全部成交 | `status_msg='AllTraded'` |
| 3 | `PARTCANCELLED` | 部分撤单 | 未实测 |
| 4 | `CANCELLED` | 全部撤单 | `status_msg='Cancelled'`，主动撤或部分成交后撤 |
| 5 | `REJECTED` | 废单 | 回测中极端高价下单直接返回负错误码，不触发此状态 |
| 6 | `UNKNOWN` | 未知 | — |
| 10 | `NOTPLACE` | 未报（等待交易所确认） | `status_msg=''`，`order_sysid` 为空；回测首次触发 |
| 11 | `PLACING` | 正报 | — |
| 12 | `PENDINGPLACE` | 待报 | — |
| 15 | `PARTPENDINGPLACE` | 部分待撤 | — |
| 16 | `PENDINGCANCEL` | 待撤销 | — |

```python
from bigquant.bigtrader import OrderStatus
# 可用枚举：NOTTRADED PARTTRADED ALLTRADED PARTCANCELLED CANCELLED
#           REJECTED UNKNOWN NOTPLACE PLACING PENDINGPLACE
#           PARTPENDINGPLACE PENDINGCANCEL 等
```

`order_type` 字段：`0` = 限价单，`U` = 市价单（五档即成剩撤）。

### 推荐的报撤单管理模式

```python
def initialize(context):
    context.user_store.init_once(pending=None)

def handle_data(context, data):
    if context.user_store['pending'] is not None:
        return                       # 有在途委托时跳过
    if 信号触发:
        price = _safe_price(data, symbol)
        if price:
            ret = context.buy_open(symbol, qty, limit_price=price * 1.002)
            if ret >= 0:
                context.user_store['pending'] = {
                    'key': context.get_last_order_key(),
                    'symbol': symbol, 'qty': qty,
                    'placed_bar': data.current_dt, 'retry': 0,
                }

def handle_order(context, order):
    from bigquant.bigtrader import OrderStatus
    pending = context.user_store['pending']
    if pending is None or order.order_key != pending['key']:
        return

    status = order.order_status
    if status == OrderStatus.REJECTED:
        context.logger.warning(f"废单: {order.status_msg}")
        context.user_store['pending'] = None

    elif status == OrderStatus.ALLTRADED:
        context.logger.info(f"成交 {order.instrument} {order.filled_qty} 张")
        context.user_store['pending'] = None

    elif status == OrderStatus.CANCELLED:
        filled = order.filled_qty
        remaining = pending['qty'] - filled
        if remaining > 0 and pending['retry'] < 3:
            price = context.get_last_price(pending['symbol'])
            if price and price > 0:
                ret = context.buy_open(pending['symbol'], remaining,
                                       limit_price=price * 1.002)
                if ret >= 0:
                    pending['key'] = context.get_last_order_key()
                    pending['qty'] = remaining
                    pending['retry'] += 1
                    return
        context.user_store['pending'] = None

def before_trading_start(context, data):
    if context.user_store['pending'] is not None:
        context.logger.warning("盘前发现未完成委托（收盘自动撤），已清除")
        context.user_store['pending'] = None
```

**职责分工：** `handle_data` 只做信号判断和触发下单；`handle_order` 负责全部委托状态管理。

**追单必须先撤后补**：直接追加新单会导致旧单后续成交时超买，正确流程为 `cancel_order(key)` → 在 CANCELLED 回调中补单。

### 委托生命周期规则（关键）

- `order_key` 在第一次触发（NOTPLACE）时即有值，回测中格式为 `'N_0_0'`，**N 全局递增跨天不重置**
- NOTPLACE 阶段 `order_sysid=''`；NOTTRADED/ALLTRADED 阶段 `order_sysid` 有值（整数字符串）
- `cancel_order` 在下一个 bar 开始前生效，CANCELLED 回调在该 bar 的 `handle_data` 之前触发
- `handle_order` 中可以安全调用 `get_orders`/`get_open_orders`，数据已是最新状态
- `handle_order` 中可以下单，新单会立即触发新的 `handle_order` 回调（注意避免递归）
- 同一合约可重复下单，底层独立处理每个订单
- 判断全部成交：`status == OrderStatus.ALLTRADED`
- 判断撤单：`status == OrderStatus.CANCELLED`（含部分成交后撤，此时 `filled_qty > 0`）
- 判断部分成交：`status == OrderStatus.PARTTRADED`（`filled_qty` 为当前已成交量）
- **收盘自动撤不触发 `handle_order`**：日终未成交限价单被系统撤销时无任何回调，委托在 `get_open_orders` 中直接消失
- **`before_trading_start` 中 `get_open_orders`/`get_orders` 返回空**：收盘自动撤后，第二天 BTS 中两个接口均返回空列表，前一天委托完全不可见，盘前清理只需重置状态变量
- **废单（REJECTED）在回测中的行为**：极端价格（如 `limit_price=99999`）下单时，回测直接返回负错误码（如 `-114`），**不触发 `handle_order`**，不产生委托；`sell_close` 无持仓时，回测不校验持仓，会正常成交
- **实盘 order_key 异步返回**：回测中下单后 `get_last_order_key()` 立即可用；实盘存在网络延迟，`handle_data` 中检测不到 order_key **不代表未下单**，切勿据此重复下单，应通过 `handle_order` 回调管理委托

### handle_trade 成交回报回调

`handle_trade(context, trade)` 在每笔成交时触发，与 `handle_order` 的 `ALLTRADED` 回调同一事件，时序上 `handle_order` 先触发，`handle_trade` 后触发。

**回测中已验证的字段**（2026-05-22 市价单实测）：

```python
trade.trade_id      # str: 成交编号（含空格，如 '     1'），全局递增
trade.order_key     # str: 对应委托的 order_key（如 '1_0_0'）
trade.instrument    # str: 合约代码
trade.direction     # str: '1'-买, '2'-卖（注意是字符串，与 order.direction 的 int 不同）
trade.offset_flag   # str: '0'-开仓, '1'-平仓（同上，字符串）
trade.trade_time    # int: 成交时间 (HHMMSSmmm)
trade.trade_date    # int: 成交日期 (YYYYmmdd)
trade.trading_day   # str: 交易日（字符串格式 'YYYYmmdd'，与 order.trading_day 的 int 不同）
trade.account_id    # str: 账户ID（如 'bktopt'）
trade.exchangeid    # int: 交易所ID
trade.order_sysid   # str: 系统报单编号
```

**`trade_qty` 和 `trade_price` 在回测中不存在**（`getattr` 返回 `'N/A'`），获取成交量/价需通过 `handle_order` 的 `order.filled_qty` 和 `order.order_price`，或查询 `context.get_trades(symbol)`。

**`direction` 和 `offset_flag` 类型差异：**

| 字段 | `order` 对象 | `trade` 对象 |
|------|-------------|-------------|
| `direction` | int（`1` 或 `2`） | str（`'1'` 或 `'2'`） |
| `offset_flag` | int（`0` 或 `1`） | str（`'0'` 或 `'1'`） |
| `trading_day` | int（如 `20260522`） | str（如 `'20260522'`） |

比较时注意类型，建议用 `str(trade.direction) == '1'`。

**使用 `getattr` 保护访问**（字段可能因版本变化）：

```python
def handle_trade(context, trade):
    fields = [
        'trade_id', 'order_key', 'instrument', 'direction', 'offset_flag',
        'trade_qty', 'trade_price', 'trade_time', 'trade_date', 'trading_day',
        'account_id', 'exchangeid', 'order_sysid',
    ]
    parts = ['[handle_trade]']
    for f in fields:
        parts.append(f'{f}={getattr(trade, f, "N/A")!r}')
    context.logger.info(' '.join(parts))
```

### OrderData 字段（handle_order 的 order 参数结构）

```python
order.account_id       # str: 资金账户
order.instrument       # str: 内部代码
order.exchangeid       # ExchangeID: 交易所ID
order.trading_code     # str: 交易代码
order.direction        # Direction: '1'-BUY, '2'-SELL（int）
order.offset_flag      # OffsetFlag: '0'-OPEN, '1'-CLOSE, '2'-CLOSETODAY（int）
order.order_type       # OrderType: '0'-限价, 'U'-市价五档即成剩撤
order.order_qty        # int: 委托数量
order.filled_qty       # int: 已成交数量
order.order_price      # float: 委托价格（含滑点后的实际委托价）
order.order_status     # OrderStatus: 委托状态
order.order_sysid      # str: 系统报单编号（NOTPLACE 阶段为空）
order.order_key        # str: 本地唯一标识，回测格式 'N_0_0'，NOTPLACE 阶段即有值
order.insert_date      # int: 报单日期 (YYYYmmdd)
order.order_time       # int: 报单时间 (HHMMSSmmm)
order.trading_day      # int: 交易日 (YYYYmmdd)
order.status_msg       # str: 报单状态消息（如 'AllTraded', 'Cancelled', ''）
```

### 持仓与账户查询

```python
# ETF期权持仓（不指定方向 → PyPosition 复合对象）
pos = context.get_position(symbol)
if pos:
    # 多头信息
    pos.long_qty()            # 多头总数量
    pos.long_avail_qty()      # 多头可平数量
    pos.long_today_qty()      # 多头今仓
    pos.long_cost_price()     # 多头成本价
    pos.long_open_price()     # 多头开仓价
    pos.long_margin()         # 多头保证金
    pos.long_value()          # 多头市值

    # 空头信息
    pos.short_qty()           # 空头总数量
    pos.short_avail_qty()     # 空头可平数量
    pos.short_today_qty()     # 空头今仓
    pos.short_cost_price()    # 空头成本价
    pos.short_open_price()    # 空头开仓价
    pos.short_margin()        # 空头保证金
    pos.short_value()         # 空头市值

    # 通用
    pos.get_net_qty()         # 净持仓（多空抵消后）
    pos.get_last_price()      # 最新价
    pos.get_market_value()    # 总市值
    pos.get_margin()          # 总保证金
    pos.instrument            # 合约代码
    pos.multiplier            # 合约乘数

    # 获取单方向 PyPositionData 对象
    long_data = pos.long_position_data()
    short_data = pos.short_position_data()

# 指定方向（期货/期货期权必须指定）
# PosiDirection 在 bigtrader 中未定义，用 get_long/short_positions() 代替
long_pos  = context.get_long_positions().get(symbol)
short_pos = context.get_short_positions().get(symbol)
if long_pos:
    long_pos.current_qty
    long_pos.avail_qty
    long_pos.cost_price

# 全部持仓
context.get_positions()        # dict {symbol: PyPositionData}
context.get_long_positions()   # dict {symbol: PyPositionData}，仅多头
context.get_short_positions()  # dict {symbol: PyPositionData}，仅空头

# 账户资金
available_cash  = context.get_available_cash()    # 可下单可用资金
total_balance   = context.get_balance()           # 总资金（可用 + 冻结）
portfolio_value = context.get_portfolio_value()

fund = context.get_trading_account()
fund.balance            # 总资金
fund.available          # 可用资金
fund.frozen_cash        # 冻结资金
fund.portfolio_value    # 总资产
fund.total_market_value # 总市值
fund.total_margin       # 总保证金
fund.positions_pnl      # 持仓盈亏

# 计算总资产（用于仓位比例）
total_asset = available_cash + sum(abs(p.market_value) for p in context.get_positions().values())
```

### 合约查询

```python
# 单个合约详情
contract = context.get_contract('合约代码.SHO')
contract.strike_price; contract.option_cp; contract.multiplier

# 某标的所有期权合约
contracts = context.get_option_contracts('标的代码.SH')

# 查询某月份所有行权价
strikes = context.get_option_strike_prices('标的代码.SH', YYYYMM)  # YYYYmm 格式整数

# 平值合约
from bigquant.bigtrader import OptionCP
atm = context.get_atm_option_contract('标的代码.SH', YYYYMM, current_price, OptionCP.CALL)
if atm:
    symbol = atm.instrument
```

### 行情订阅

```python
# 每天在 before_trading_start 中订阅
context.subscribe_bar([symbol], '1m')    # 订阅 1 分钟 K 线
context.subscribe_bar([symbol], '5m')    # 订阅 5 分钟 K 线

from bigquant.bigtrader import SubscribeFlag
context.subscribe([symbol])                                                    # 默认订阅
context.subscribe([symbol], SubscribeFlag.L2Snapshot)                          # Level2 快照
context.subscribe([symbol], SubscribeFlag.L2Snapshot | SubscribeFlag.L2Trade)  # 多标志位用 |

context.unsubscribe([symbol])            # 取消订阅

tick = context.current_tick(symbol)
if tick:
    bid1 = tick.bid_price1; ask1 = tick.ask_price1
```

**注意：`data.history()` 在期权回测中不可用，**用 `dai.query()` 查历史数据：

```python
current_dt = str(data.current_dt)[:10]
sql = f"""
SELECT date, close FROM cn_fund_bar1d
WHERE instrument='{etf_symbol}' AND date <= '{current_dt}'
ORDER BY date DESC LIMIT 81
"""
df = dai.query(sql, filters={"date": ["2025-01-01", current_dt]}).df()
```

### 回测配置

```python
# 手续费（ETF期权推荐值）
context.set_commission(bigtrader.PerOrder(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))

# 期货手续费（PerContract cost tuple: (开仓费率, 平仓费率, 平今费率)，<0.1 按金额，否则按手数）
context.set_commission(futures_commission=bigtrader.PerContract(
    cost={"品种代码": (开仓费率, 平仓费率, 平今费率)}
))

# 保证金比例
context.set_margin_ratio("品种代码", 0.12)

# 滑点（slippage_type=1 固定值，slippage_type=2 百分比）
context.set_slippage_value(slippage_type=2, slippage_value=0.001)

# 多账户（ETF期权 + 股票）
context.add_account(bigtrader.AccountType.STOCK, capital_base=500000)
# 注意：期货+期货期权 或 股指期权 只需一个期货账号，不需要 add_account
```

### 枚举类型

```python
from bigquant.bigtrader import (
    Market, Frequency, AccountType,
    Direction, OffsetFlag, OrderType, OrderStatus,
    OptionCP, SubscribeFlag,
    PerOrder, PerContract,
)
```

| 枚举 | 常量 | 说明 |
|------|------|------|
| Market | CN_STOCK_OPTION | ETF期权 |
| Market | CN_FUTURE_OPTION | 期货期权（含股指期权） |
| Frequency | DAILY / MINUTE / MINUTE5 | 日频 / 1分钟 / 5分钟 |
| OptionCP | CALL / PUT | 认购 / 认沽 |

**交易所代码后缀：**

| 市场 | 后缀 | 示例 |
|------|------|------|
| 上交所 ETF期权 | .SHO | 10011413.SHO |
| 深交所 ETF期权 | .SZO | 90000001.SZO |
| 中金所期权/期货 | .CFE | IO2501-C-4300.CFE |
| 上交所股票/ETF | .SH | 510050.SH |
| 深交所股票/ETF | .SZ | 159919.SZ |

### user_store 持久化

```python
# 初始化（init_once 保证模拟盘跨日重启不覆盖）
context.user_store.init_once(my_var=0, flag=False)

context.user_store['my_var'] = 1
val = context.user_store.get('flag', False)
```

### Black-Scholes（内联）

```python
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq

def bs_price(S, K, T, r, sigma, option_type='call'):
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    if option_type == 'call':
        return S*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2)
    return K*np.exp(-r*T)*norm.cdf(-d2) - S*norm.cdf(-d1)

def bs_iv(option_price, S, K, T, r=0.02, option_type='call'):
    try:
        return brentq(lambda s: bs_price(S,K,T,r,s,option_type) - option_price, 1e-6, 10.0)
    except Exception:
        return None

def bs_delta(S, K, T, r=0.02, sigma=0.20, option_type='call'):
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    return float(norm.cdf(d1)) if option_type == 'call' else float(norm.cdf(d1) - 1)
```

### Context API 速查

```python
hm = (data.current_dt.hour, data.current_dt.minute)
if hm == (9, 35): ...

today = context.get_trading_day()   # 'YYYYmmdd'
context.logger.info("...")
context.logger.warning("...")
context.logger.error("...")
context.logger.debug(context.get_error_msg(ret))  # 下单失败时打印错误详情
context.record_log('INFO', f'开仓 {symbol} {qty} 张')  # 图表标记
```

| 属性 | 说明 |
|------|------|
| `context.instruments` | 策略标的列表 |
| `context.portfolio.cash` | 可用资金 |
| `context.user_store` | 跨 bar 持久化字典 |
| `context.data` | 自定义数据（因子/预测等） |

### 注意事项（期权）

- `instruments` 只传 ETF 标的代码（如 `["588000.SH"]`），不传期权交易代码
- **所有交易操作必须在 `handle_data` 中执行**，`before_trading_start` 只做状态判断和订阅，不下单；如需在 BTS 发现平仓条件，设置标志位由 `handle_data` 执行
- `get_balance()` 返回总资金（可用+冻结）；计算仓位比例用 `get_available_cash() + 持仓市值`
- 期货/期货期权查询持仓必须按方向：`context.get_long_positions().get(symbol)` / `context.get_short_positions().get(symbol)`（`PosiDirection` 在 bigtrader 中未定义）
- `buy_open/sell_open/buy_close/sell_close` 的 `order_qty` 应为正数，接口本身已包含方向
- 期货+期货期权 或 股指期权 只需一个期货账号（`market=Market.CN_FUTURE_OPTION`），不需要 `add_account`
- 不要在回调中阻塞等待，底层事件队列在回调返回后才处理下一个事件

---

## 期货 CTA 策略

### 状态机模式

期货 CTA 推荐用 `enum.Enum` 显式管理持仓状态，避免靠查询持仓来推断方向。

```python
from bigquant import bigtrader
from enum import Enum

class S(Enum):
    IDLE = 'idle'
    LONG = 'long'
    SHORT = 'short'

def initialize(context: bigtrader.IContext):
    context.security = context.instruments[0]
    context.set_commission(futures_commission=bigtrader.PerContract(
        cost={"rb": (2, 2, 1), "IF": (0.000023, 0.00015, 0.000023)}
    ))
    context.set_margin_ratio("IF", 0.15)
    context.set_slippage_value(slippage_type=2, slippage_value=0.001)
    context.state = S.IDLE

def handle_data(context: bigtrader.IContext, data: bigtrader.IBarData):
    last_price = data.current(context.security, 'close')
    # 替换为实际信号逻辑
    direction = 'long' if last_price / data.current(context.security, 'pre_close') >= 1 else 'short'

    # 外部持仓变动时同步状态（如强平）
    if context.security not in context.portfolio.positions:
        context.state = S.IDLE

    while True:
        if context.state == S.IDLE:
            if direction == 'long':
                rv = context.buy_open(context.security, 5, limit_price=last_price * 1.01)
                if rv >= 0:
                    context.state = S.LONG
                return

        if context.state == S.LONG:
            if direction == 'long':
                return  # 持有
            rv = context.sell_close(context.security, 5, limit_price=last_price * 0.99)
            if rv < 0:
                return  # 平仓失败，下一 bar 重试
            context.state = S.IDLE
            # 不 return，继续循环在同一 bar 开空头

        if context.state == S.SHORT:
            if direction == 'short':
                return  # 持有
            rv = context.buy_close(context.security, 5, limit_price=last_price * 1.01)
            if rv < 0:
                return  # 平仓失败，下一 bar 重试
            context.state = S.IDLE
            # 不 return，继续循环在同一 bar 开多头
```

**`while True` 的作用**：平仓成功后 `state = S.IDLE`，不 `return`，循环继续落入下一个 `if` 块，在**同一 bar 内**完成"平旧开新"翻转。平仓失败则 `return`，下一个 bar 重试。

**期货回测入口：**

```python
performance = bigtrader.run(
    market=bigtrader.Market.CN_FUTURE,
    frequency=bigtrader.Frequency.DAILY,
    instruments=['jm2609.DCE'],   # 具体合约代码，需向用户确认
    capital_base=100000,
    benchmark="000300.SH",
    initialize=initialize,
    before_trading_start=before_trading_start,
    handle_data=handle_data,
    handle_trade=handle_trade,   # 可选
)
```

完整可运行示例见 `references/strategies.md` 模式八。

### 分钟频率策略：历史数据预加载 + 行情订阅

适用于**所有资产类别**（期货、ETF、股票、期权）的分钟/小时频率策略。

#### initialize：用 dai 预加载历史 K 线

分钟频率策略的滚动窗口（均线、通道、ATR 等）需要 N 根历史 bar 才能计算第一个信号。必须在 `initialize` 中预查询并填充，不能依赖 `handle_data` 从零累积——否则回测启动后需等待 N×BAR_SIZE 分钟才能出第一个信号，造成信号空窗。

**通用预加载模式（适用于任意资产、任意目标周期）：**

```python
from bigquant import bigtrader, dai
from collections import deque
from datetime import datetime, timedelta

# 参数
BAR_SIZE = 60    # 目标聚合周期（分钟）
N = 20           # 滚动窗口长度（根聚合 bar）

# 每个交易日的分钟 bar 数（不同资产不同，此处为估算值，用于计算缓冲天数）
MINUTES_PER_DAY = {
    'future':  480,   # 期货（含夜盘，约 6.5~8 小时）
    'etf':     240,   # ETF（4 小时）
    'stock':   240,   # 股票（4 小时）
    'option':  240,   # 期权（4 小时）
}

def initialize(context: bigtrader.IContext):
    instrument = context.instruments[0]

    # 所需历史分钟数 = N × BAR_SIZE，乘以 1.5 冗余应对节假日
    minutes_per_day = MINUTES_PER_DAY['future']  # 按实际资产类型选择
    buffer_days = int(N * BAR_SIZE / minutes_per_day * 1.5) + 5
    buffer_start = (
        datetime.strptime(context.start_date, '%Y-%m-%d') - timedelta(days=buffer_days)
    ).strftime('%Y-%m-%d')

    # 查询对应资产的 1 分钟 K 线（各资产替换对应表名）
    # 期货：cn_future_bar1m；ETF：cn_fund_bar1m；期权：cn_option_bar1m
    sql = f"""
    SELECT date, open, high, low, close
    FROM cn_future_bar1m
    WHERE instrument='{instrument}'
    ORDER BY date
    """
    hist = dai.query(sql, filters={"date": [buffer_start, context.start_date]}).df()

    # 按顺序聚合为 BAR_SIZE 分钟 bar，过滤不完整的边界组
    hist = hist.sort_values('date').reset_index(drop=True)
    hist['bar_idx'] = hist.index // BAR_SIZE
    bar_counts = hist.groupby('bar_idx').size()
    complete_idx = bar_counts[bar_counts == BAR_SIZE].index
    agg = hist[hist['bar_idx'].isin(complete_idx)].groupby('bar_idx').agg(
        open=('open', 'first'), high=('high', 'max'),
        low=('low', 'min'),   close=('close', 'last'),
    ).tail(N)

    # 填充滚动窗口
    context.bar_high  = deque(agg['high'].tolist(),  maxlen=N)
    context.bar_low   = deque(agg['low'].tolist(),   maxlen=N)
    context.bar_close = deque(agg['close'].tolist(), maxlen=N)

    context.logger.info(f"预加载完成：{len(context.bar_high)}/{N} 根 {BAR_SIZE}分钟 bar")

    # 1分钟聚合计数（运行期 handle_data 使用）
    context.bar_min_count = 0
    context.agg_open = context.agg_high = context.agg_low = context.agg_close = None
```

#### before_trading_start：订阅行情

分钟频率策略**必须**在 `before_trading_start` 中订阅行情，否则 `handle_data` 收不到 bar 数据。每日开盘前重新订阅（应对换月等合约变化），同时重置跨日聚合状态。

```python
def before_trading_start(context: bigtrader.IContext, data: bigtrader.IBarData):
    # 订阅所有策略标的的 1 分钟 bar
    context.subscribe_bar(context.instruments, '1m')

    # 重置聚合状态，防止跨日 bar 拼接
    context.bar_min_count = 0
    context.agg_open = context.agg_high = context.agg_low = context.agg_close = None
```

**跨日重置的必要性：** 日盘最后一根 1 分钟 bar 到次日夜盘/日盘开盘之间有间隔，若不重置计数器，两个交易日的 bar 会被拼入同一个聚合 bar，导致 OHLC 错误。

### 注意事项（期货）

- `instruments` 传具体合约代码（如 `jm2609.DCE`），不是品种代码
- 期货持仓查询必须按方向：`context.get_long_positions().get(symbol)` / `context.get_short_positions().get(symbol)`（`PosiDirection` 在 bigtrader 中未定义）
- `context.portfolio.positions` 可直接检查合约是否在持仓中，不需要指定方向
- `set_commission` 的 `cost` tuple `< 0.1` 时按金额（元/手），否则按手数（元/手）
- `slippage_type=2` 为百分比滑点，`slippage_type=1` 为固定价格滑点
- **分钟/小时频率策略必须在 `initialize` 中用 `dai.query()` 预加载历史 K 线**，填充滚动窗口；在 `handle_data` 里从零累积会导致回测初期大量无效等待期

---

## 参考资料

- **`references/tables.md`** — 所有数据表字段详细说明
- **`references/sql-patterns.md`** — 完整 SQL 模式库（因子、选股、期权、期货）
- **`references/factors.md`** — 完整因子库与 cn_stock_prefactors 常用字段
- **`references/strategies.md`** — 策略模式分类与完整示例（含 ML 增强选股、期货 CTA 状态机）
- **`references/get_table_schema.py`** — 动态获取任意表的字段描述
