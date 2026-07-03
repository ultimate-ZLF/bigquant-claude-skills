# BigQuant DAI SQL 模式库

## 因子选股模式

### 单因子查询模板

```python
from bigquant import dai

sql = """
SELECT
    date,
    instrument,
    <factor_expression> AS factor
FROM cn_stock_prefactors
WHERE st_status = 0
  AND suspended = 0
ORDER BY date, instrument
"""

df = dai.query(sql, filters={"date": [start_date, end_date]}).df()
```

### 动量因子

```sql
-- 20日Sharpe动量
SELECT date, instrument,
    m_avg(close / m_lag(close, 1) - 1, 20) /
    (m_stddev(close / m_lag(close, 1) - 1, 20) + 1e-8) AS factor
FROM cn_stock_prefactors
WHERE st_status = 0
ORDER BY date, instrument
```

```sql
-- 60日相对120日超额动量
SELECT date, instrument,
    (close / m_lag(close, 60) - 1) - (close / m_lag(close, 120) - 1) AS factor
FROM cn_stock_prefactors
WHERE st_status = 0
ORDER BY date, instrument
```

```sql
-- RSI 14日
SELECT date, instrument,
    m_ta_rsi(close, 14) AS factor
FROM cn_stock_prefactors
WHERE st_status = 0
ORDER BY date, instrument
```

### 价值因子

```sql
-- 低PB（PB倒数）
SELECT date, instrument,
    CASE WHEN pb > 0 THEN 1.0 / pb ELSE 0 END AS factor
FROM cn_stock_prefactors
WHERE st_status = 0 AND pb > 0
ORDER BY date, instrument
```

```sql
-- 低PE（PE倒数）
SELECT date, instrument,
    CASE WHEN pe_ttm > 0 AND pe_ttm < 1000 THEN 1.0 / pe_ttm ELSE 0 END AS factor
FROM cn_stock_prefactors
WHERE st_status = 0 AND pe_ttm > 0 AND pe_ttm < 1000
ORDER BY date, instrument
```

### 质量因子

```sql
-- ROE
SELECT date, instrument, roe AS factor
FROM cn_stock_prefactors
WHERE st_status = 0 AND roe > 0
ORDER BY date, instrument
```

```sql
-- 研发费用加速度（二阶差分）
SELECT date, instrument,
    (m_lag(research_and_development_expense_ttm, 40)
     - 4 * m_lag(research_and_development_expense_ttm, 20)
     + 3 * research_and_development_expense_ttm) / 40 AS factor
FROM cn_stock_prefactors
WHERE st_status = 0
  AND research_and_development_expense_ttm IS NOT NULL
  AND research_and_development_expense_ttm > 0
ORDER BY date, factor DESC
```

### 技术因子

```sql
-- 20日波动率
SELECT date, instrument,
    m_stddev(close / m_lag(close, 1) - 1, 20) AS factor
FROM cn_stock_prefactors
WHERE st_status = 0
ORDER BY date, instrument
```

```sql
-- MACD DIF
SELECT date, instrument,
    m_ta_macd_dif(close, 12, 26, 9) AS factor
FROM cn_stock_prefactors
WHERE st_status = 0
ORDER BY date, instrument
```

```sql
-- 换手率
SELECT date, instrument,
    volume * close / total_market_cap AS factor
FROM cn_stock_prefactors
WHERE st_status = 0 AND total_market_cap > 0
ORDER BY date, instrument
```

### 行业中性因子

```sql
-- 行业内PB排名
SELECT date, instrument,
    c_group_pct_rank(1.0 / pb, GROUP BY sw2021_level1) AS factor
FROM cn_stock_prefactors
WHERE st_status = 0 AND pb > 0
ORDER BY date, instrument
```

### 组合因子

```sql
-- 价值 + 质量（各50%）
SELECT date, instrument,
    (CASE WHEN pb > 0 THEN 1.0 / pb ELSE 0 END) * 0.5 +
    (CASE WHEN roe > 0 THEN roe ELSE 0 END) * 0.5 AS factor
FROM cn_stock_prefactors
WHERE st_status = 0 AND pb > 0 AND roe > 0
ORDER BY date, instrument
```

---

## 机器学习特征工程模式

```sql
WITH feature_table AS (
    SELECT
        date,
        instrument,
        close                                    AS close_0,
        open                                     AS open_0,
        m_avg(close, 5) / close                  AS ma_close_5,
        m_avg(close, 20) / close                 AS ma_close_20,
        m_stddev(close, 5)                       AS std_close_5,
        m_rolling_rank(close, 5) / 5             AS rank_close_5,
        m_corr(volume, change_ratio + 1, 5)      AS corr_vcr,
        c_pct_rank(turn)                         AS cross_turn,
        c_pct_rank(volume)                       AS cross_volume
    FROM cn_stock_prefactors
    QUALIFY COLUMNS(*) IS NOT NULL
)
SELECT * FROM feature_table
ORDER BY date, instrument
```

```python
df = dai.query(sql, filters={"date": [start_date, end_date]}).pl()
# 用 polars 处理大数据量更高效
df = df.fill_nan(None)
df = df.select(pl.all().forward_fill().over('instrument'))
df = df.fill_null(0)
```

---

## 期权数据查询模式

### 查询当前有效期权合约

```python
sql = f"""
SELECT instrument, underlying, strike_price, option_type, delist_date, multiplier
FROM cn_option_basic_info
WHERE underlying = '{etf_symbol}'
  AND delist_date >= '{today}'
ORDER BY delist_date, strike_price
"""
option_info = dai.query(sql).df()
```

### 按到期月份筛选

```python
sql = f"""
SELECT instrument, strike_price, option_type, delist_date
FROM cn_option_basic_info
WHERE underlying = '{etf_symbol}'
  AND strftime('%Y%m', delist_date) = '{yyyymm}'
ORDER BY strike_price
"""
```

### 策略内实时查询 ETF 1 分钟数据

```python
def handle_data(context, data):
    current_dt = str(data.current_dt)[:19]
    n_bars = 20  # 需要最近 20 根 1 分钟 K 线

    sql = f"""
    SELECT date, close, high, low, volume
    FROM cn_fund_bar1m
    WHERE instrument='{context.etf_symbol}'
      AND date <= '{current_dt}'
    ORDER BY date DESC
    LIMIT {n_bars}
    """
    df = dai.query(sql).df()
    df = df.sort_values('date')  # 转为正序
    close_list = df['close'].tolist()
```

### 期权到期日 JOIN 模式

```sql
SELECT d.date, d.instrument, d.close,
       o.delist_date, o.strike_price, o.option_type
FROM cn_fund_bar1d d
LEFT JOIN cn_option_basic_info o
    ON d.date <= (o.delist_date - INTERVAL '10 days')
    AND o.underlying = d.instrument
WHERE d.instrument = '510050.SH'
ORDER BY d.date
```

---

## 期货数据查询模式

### 查询主力合约

```python
sql = """
SELECT instrument, delist_date
FROM cn_future_basic_info
WHERE product = 'IF'
  AND delist_date >= CURRENT_DATE
ORDER BY delist_date
LIMIT 1
"""
main_contract = dai.query(sql).df()
```

### 期货日线数据

```python
sql = """
SELECT date, instrument, open, high, low, close, volume, open_interest, settle
FROM cn_future_bar1d
WHERE instrument LIKE 'IF%'
ORDER BY date, instrument
"""
df = dai.query(sql, filters={"date": [start_date, end_date]}).df()
```

### 期货到期日 JOIN 模式

```sql
SELECT d.date, d.instrument, d.close,
       f.delist_date
FROM cn_future_bar1d d
LEFT JOIN cn_future_basic_info f
    ON d.instrument = f.instrument
    AND d.date <= (f.delist_date - INTERVAL '5 days')
WHERE d.instrument LIKE 'IF%'
ORDER BY d.date
```

---

## 回测框架内的 DAI 查询模式

### before_trading_start 中批量预取

```python
def initialize(context):
    context.start_date_str = context.start_date  # 'YYYY-MM-DD'
    context.end_date_str   = context.end_date

def before_trading_start(context, data):
    # 只在第一天加载全量数据
    if not hasattr(context, 'factor_df'):
        buffer_start = context.add_trading_days(context.start_date, -50)
        sql = """
        SELECT date, instrument, close, pe_ttm, pb, roe
        FROM cn_stock_prefactors
        WHERE st_status = 0 AND suspended = 0
        ORDER BY date, instrument
        """
        context.factor_df = dai.query(
            sql,
            filters={"date": [buffer_start, context.end_date]}
        ).df()
        context.factor_df['date'] = pd.to_datetime(context.factor_df['date'])
```

### handle_data 中按日期切片

```python
def handle_data(context, data):
    today = pd.Timestamp(data.current_dt.date())
    today_df = context.factor_df[context.factor_df['date'] == today]
    today_df = today_df.sort_values('factor', ascending=False)
    top_stocks = today_df.head(50)['instrument'].tolist()
```

---

## 常见错误与解决

### PermissionException

```
PermissionException: Permission Error: 请在查询表 cn_stock_prefactors 时使用 filters 参数指定分区范围
```

**解决：** 添加 `filters={"date": [start_date, end_date]}`

### 窗口函数返回 NULL

**原因：** 查询起始日期太近，没有足够的历史数据计算窗口。

**解决：** 提前查询起始日期：
```python
buffer_start = context.add_trading_days(start_date, -60)
df = dai.query(sql, filters={"date": [buffer_start, end_date]}).df()
df = df[df['date'] >= start_date]  # 过滤掉缓冲期数据
```

### 日期格式错误

```python
# 错误
filters={"date": ["2020/01/01", "2023/12/31"]}

# 正确
filters={"date": ["2020-01-01", "2023-12-31"]}
```

### 策略内时间戳格式

```python
# data.current_dt 是 datetime 对象，转为字符串时截取前19位
current_dt = str(data.current_dt)[:19]  # '2023-01-05 09:31:00'
```
