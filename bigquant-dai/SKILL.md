---
name: bigquant-dai
description: This skill should be used when the user asks to "query data with dai", "write a dai query", "use dai.query", "query stock data", "query option data", "query ETF data", "query futures data", "query factor data", "write SQL for bigquant", "use cn_stock_prefactors", "use cn_fund_bar1m", "use cn_option_bar1m", or when writing any data access code using the BigQuant DAI library.
version: 0.1.0
---

# BigQuant DAI 数据查询

BigQuant DAI 是平台专有的 SQL 数据访问层，通过 `dai.query(sql, filters={...})` 接口查询金融数据，返回结果可转为 pandas DataFrame 或 Polars DataFrame。

## 核心用法

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

## filters 参数（必须）

大表查询**必须**使用 `filters` 参数，否则报 `PermissionException`。

```python
# 按日期范围（最常用）
filters={"date": ["2020-01-01", "2023-12-31"]}

# 单日
filters={"date": ["2023-12-31", "2023-12-31"]}

# 多字段
filters={"date": ["2023-01-01", "2023-12-31"], "instrument": ["000001.SZ", "000100.SZ"]}
```

**必须使用 filters 的大表：**

| 表名 | 内容 |
|------|------|
| `cn_stock_prefactors` | 股票日线因子（最常用） |
| `cn_stock_bar1d` | 股票日线 K 线 |
| `cn_stock_status` | 股票状态 |
| `cn_stock_valuation` | 估值数据 |
| `cn_stock_factors` | 因子数据 |

**小表（无需 filters）：**

| 表名 | 内容 |
|------|------|
| `cn_option_basic_info` | 期权合约基本信息 |
| `cn_future_basic_info` | 期货合约基本信息 |

**注意：** WHERE 子句中写了日期条件不等于 filters，两者都要写。

## 常用数据表速查

### 股票数据

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
```

### ETF / 基金数据

```python
# ETF 日线
sql = "SELECT date, instrument, open, high, low, close, volume FROM cn_fund_bar1d"
df = dai.query(sql, filters={"date": [start_date, end_date]}).df()

# ETF 1 分钟（高频，无需 filters）
sql = f"""
SELECT date, open, high, low, close, volume
FROM cn_fund_bar1m
WHERE instrument='{etf_symbol}'
  AND date >= '{start_dt}' AND date <= '{end_dt}'
ORDER BY date
"""
df = dai.query(sql).df()
```

### 期权数据

```python
# 期权 1 分钟 K 线（无需 filters）
sql = f"""
SELECT date, instrument, open, high, low, close, volume
FROM cn_option_bar1m
WHERE instrument='{option_symbol}'
ORDER BY date DESC LIMIT 100
"""
df = dai.query(sql).df()

# 期权合约基本信息（无需 filters）
sql = """
SELECT instrument, underlying, strike_price, option_type,
       list_date, delist_date, multiplier
FROM cn_option_basic_info
WHERE underlying = '510050.SH'
"""
df = dai.query(sql).df()
```

### 期货数据

```python
# 期货日线
sql = "SELECT date, instrument, open, high, low, close, volume FROM cn_future_bar1d"
df = dai.query(sql, filters={"date": [start_date, end_date]}).df()

# 期货合约信息（无需 filters）
sql = "SELECT instrument, delist_date FROM cn_future_basic_info WHERE product='IF'"
df = dai.query(sql).df()
```

## DAI SQL 专有函数

### 截面函数（c_ 前缀）

截面函数对同一时间点的所有股票做横截面计算。

```sql
-- 基础统计
c_avg(col)                 -- 截面均值
c_count(col)               -- 截面非空个数
c_sum(col)                 -- 截面求和
c_std(col)                 -- 截面标准差
c_var(col)                 -- 截面方差
c_median(col)              -- 截面中位数
c_mad(col)                 -- 截面绝对中位差

-- 排名和分位数
c_rank(col)                -- 截面排名
c_pct_rank(col)            -- 截面百分数排名（0~1）
c_quantile_cont(col, 0.5)  -- 插值分位数
c_quantile_disc(col, 0.5)  -- 最近确切分位数

-- 标准化和归一化
c_normalize(col)           -- Z-score 标准化
c_zscore(col)              -- Z-score 标准化（同上）
c_scale(col)               -- 缩放
c_min_max_scalar(col)      -- 最小最大缩放

-- 分组操作
c_group_avg(col, GROUP BY industry)      -- 分组均值
c_group_pct_rank(col, GROUP BY industry) -- 分组百分数排名
c_group_std(col, GROUP BY industry)      -- 分组标准差

-- 中性化
c_indneutralize(col, industry)           -- 行业中性化
c_neutralize(col, industry, market_cap)  -- 行业市值中性化
c_ols2d_resid(y, x)                      -- 二元线性回归残差
c_regr_residual(y, x)                    -- 线性回归残差
```

### 时序窗口函数（m_ 前缀）

时序函数按 instrument 分组，在时间维度上做滚动计算。

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

-- 偏移和变化（常用于计算收益率、同比增长等）
m_lag(col, n)              -- 向下偏移 n 行（历史值）
m_lead(col, n)             -- 向上偏移 n 行（未来值）
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
m_regr_slope(y, x, n)     -- n 期回归斜率
m_regr_intercept(y, x, n) -- n 期回归截距
m_regr_r2(y, x, n)        -- n 期决定系数 R²

-- 排名和分位数
m_rank(col, n)             -- n 期时序排名
m_pct_rank(col, n)         -- n 期时序百分数排名
m_quantile_cont(col, n, q) -- n 期时序分位数
m_rolling_rank(col, n)     -- n 期滚动排名

-- 技术指标（m_ta_ 前缀）
m_ta_rsi(col, n)                        -- RSI 指标
m_ta_macd_dif(col, fast, slow, signal)  -- MACD DIF
m_ta_kdj_k(high, low, close, n)         -- KDJ K 值
m_ta_atr(high, low, close, n)           -- ATR 平均真实波幅
m_ta_cci(high, low, close, n)           -- CCI 商品通道指数
m_ta_obv(close, volume)                 -- OBV 平衡成交量
```

### 其他

```sql
QUALIFY COLUMNS(*) IS NOT NULL   -- 过滤任意列含 NULL 的行
all_quantile_cont(col, 0.5)      -- 分位数
```

## 常用 WHERE 过滤条件

```sql
-- 股票质量过滤
WHERE st_status = 0          -- 排除 ST
  AND suspended = 0          -- 排除停牌
  AND pb > 0                 -- 有效 PB
  AND pe_ttm > 0 AND pe_ttm < 1000  -- 有效 PE

-- 指数成分
WHERE is_zz500 = 1           -- 中证500成分
WHERE is_hs300 = 1           -- 沪深300成分

-- 行业
WHERE sw2021_level1 = '银行'
```

## 窗口函数缓冲期

使用 `m_lag(col, N)` 等窗口函数时，查询起始日期需提前 N 个交易日，否则早期数据为 NULL：

```python
# 使用 bigtrader 的交易日工具
buffer_start = context.add_trading_days(context.start_date, -50)

# 或手动计算（约 1.5 倍日历日）
from datetime import datetime, timedelta
buffer_start = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=75)).strftime('%Y-%m-%d')
```

**嵌套窗口函数的缓冲期叠加：** `m_CORR(m_AVG(col, N), ..., N)` 需要 2N 个交易日缓冲（内层 m_AVG 的 N 期 + 外层 m_CORR 的 N 期）。例如 N=60 时需约 180 个日历日：

```python
# N=60 的嵌套窗口，需要 ~180 天缓冲
buffer_start = (start_dt - timedelta(days=180)).strftime('%Y-%m-%d')
```

**CTE 内窗口函数的缓冲期：** `filters` 的日期范围决定了窗口函数能看到的历史数据，CTE 不会自动扩展缓冲期。缓冲期不足时，窗口函数在 CTE 内部同样返回 NULL，被 `QUALIFY COLUMNS(*) IS NOT NULL` 过滤后结果为空表。解决方法是在 `filters` 起始日期上加足够的缓冲，查询后再用 Python 过滤掉缓冲期数据：

```python
# 查询时加缓冲
df = dai.query(sql, filters={'date': [buffer_start, end_date]}).pl()
# 返回后过滤掉缓冲期
df = df.filter(pl.col('date') >= actual_start_date)
```

**`c_pct_rank` 与窗口函数不能在同一 CTE 层：** 在 CTE 内部同时使用 `c_pct_rank`（截面函数）和 `m_avg`/`m_corr`（时序窗口函数）会导致窗口函数返回全 NULL。正确做法是分两层：第一层 CTE 只做时序特征，第二层 CTE 或外层 SELECT 再做截面函数：

```sql
-- 正确：时序特征在第一层，截面函数在第二层
WITH ts_features AS (
    SELECT date, instrument,
        m_avg(close, 20) / close  ma_close_20
    FROM cn_stock_prefactors
    QUALIFY COLUMNS(*) IS NOT NULL
)
SELECT date, instrument,
    ma_close_20,
    c_pct_rank(ma_close_20)  cross_ma_close_20
FROM ts_features

-- 错误：同一层混用会导致窗口函数返回 NULL
WITH features AS (
    SELECT date, instrument,
        m_avg(close, 20) / close  ma_close_20,
        c_pct_rank(ma_close_20)  cross_ma_close_20  -- 导致 ma_close_20 全为 NULL
    FROM cn_stock_prefactors
)
```

## 完整示例

### 因子选股查询

```python
from bigquant import dai

start_date = '2020-01-01'
end_date   = '2023-12-31'

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

### 策略内实时查询（bigtrader handle_data）

```python
def handle_data(context, data):
    current_dt = str(data.current_dt)[:19]  # 'YYYY-MM-DD HH:MM:SS'

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

### 期权到期日查询

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

## 注意事项

- 日期格式必须为 `YYYY-MM-DD`，不能用 `YYYY/MM/DD`
- filters 中的日期范围与 SQL WHERE 中的日期条件**都要写**，两者不能互相替代
- 极少数情况需全表扫描时用 `full_db_scan=True`，但非常慢，避免使用
- 高频策略中查询 1 分钟数据时，注意 `LIMIT` 控制返回行数，避免数据量过大

## 参考资料

- **`references/tables.md`** — 所有数据表字段详细说明
- **`references/sql-patterns.md`** — 完整 SQL 模式库（因子、选股、期权、期货）
- **`references/get_table_schema.py`** — 动态获取任意表的字段描述（当 tables.md 未收录某表时使用）
