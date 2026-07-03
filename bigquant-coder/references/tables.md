# BigQuant DAI 数据表字段参考

## cn_stock_prefactors — 股票日线因子表

最常用的股票数据表，包含价格、估值、财务、技术指标等。

### 基础价格字段

| 字段 | 说明 |
|------|------|
| `date` | 交易日期 |
| `instrument` | 股票代码（如 `000001.SZ`） |
| `open` | 开盘价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `close` | 收盘价（前复权） |
| `volume` | 成交量 |
| `amount` | 成交额 |
| `adjust_factor` | 复权因子 |
| `change_ratio` | 涨跌幅 |
| `turn` | 换手率 |

### 估值字段

| 字段 | 说明 |
|------|------|
| `pe_ttm` | 市盈率（TTM） |
| `pb` | 市净率 |
| `ps_ttm` | 市销率（TTM） |
| `pcf_ttm` | 市现率（TTM） |
| `total_market_cap` | 总市值 |
| `float_market_cap` | 流通市值 |

### 财务字段

| 字段 | 说明 |
|------|------|
| `roe` | 净资产收益率 |
| `roa` | 资产收益率 |
| `net_profit_margin` | 净利润率 |
| `gross_profit_margin` | 毛利率 |
| `research_and_development_expense_ttm` | 研发费用（TTM） |
| `revenue_ttm` | 营业收入（TTM） |
| `net_profit_ttm` | 净利润（TTM） |

### 状态字段

| 字段 | 说明 |
|------|------|
| `st_status` | ST状态（0=正常，1=ST，2=*ST） |
| `suspended` | 停牌状态（0=正常，1=停牌） |
| `list_days` | 上市天数 |

### 指数成分字段

| 字段 | 说明 |
|------|------|
| `is_hs300` | 是否沪深300成分（0/1） |
| `is_zz500` | 是否中证500成分（0/1） |
| `is_zz1000` | 是否中证1000成分（0/1） |

### 行业字段

| 字段 | 说明 |
|------|------|
| `sw2021_level1` | 申万2021一级行业（文本，如 `'银行'`） |
| `sw2021_level2` | 申万2021二级行业 |
| `list_sector` | 上市板块（1=上交所主板, 2=深交所主板, 3=创业板） |

### 申万一级行业指数字段

每只股票所属申万一级行业的指数行情，随日线数据同步更新，可直接用于行业动量、轮动类策略。

| 字段 | 类型 | 说明 |
|------|------|------|
| `sw_level1_name` | VARCHAR | 申万一级行业名称（2021版），如 `'银行'` |
| `sw_level_index_code` | VARCHAR | 申万一级行业指数代码，如 `'801780.SI'` |
| `sw_level1_close` | DOUBLE | 所属申万一级行业指数收盘价 |
| `sw_level1_open` | DOUBLE | 所属申万一级行业指数开盘价 |
| `sw_level1_high` | DOUBLE | 所属申万一级行业指数最高价 |
| `sw_level1_low` | DOUBLE | 所属申万一级行业指数最低价 |
| `sw_level1_volume` | DOUBLE | 所属申万一级行业指数成交量 |
| `sw_level1_amount` | DOUBLE | 所属申万一级行业指数成交额 |
| `sw_level1_turn` | DOUBLE | 所属申万一级行业指数换手率 |

**典型用法：行业动量因子**

```sql
-- 行业近20日动量（用于行业轮动或行业中性化）
SELECT date, instrument,
    sw_level1_name,
    sw_level1_close / m_lag(sw_level1_close, 20) - 1 AS industry_momentum_20d
FROM cn_stock_prefactors
WHERE st_status = 0 AND suspended = 0
QUALIFY COLUMNS(*) IS NOT NULL
ORDER BY date, industry_momentum_20d DESC
```

---

## cn_stock_bar1d — 股票日线 K 线

| 字段 | 说明 |
|------|------|
| `date` | 交易日期 |
| `instrument` | 股票代码 |
| `open` | 开盘价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `close` | 收盘价 |
| `volume` | 成交量 |
| `amount` | 成交额 |

---

## cn_fund_bar1d — ETF/基金日线 K 线

| 字段 | 说明 |
|------|------|
| `date` | 交易日期 |
| `instrument` | ETF代码（如 `510050.SH`） |
| `open` | 开盘价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `close` | 收盘价 |
| `volume` | 成交量 |
| `amount` | 成交额 |

---

## cn_fund_bar1m — ETF/基金 1 分钟 K 线

| 字段 | 说明 |
|------|------|
| `date` | 时间戳（`YYYY-MM-DD HH:MM:SS`） |
| `instrument` | ETF代码 |
| `open` | 开盘价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `close` | 收盘价 |
| `volume` | 成交量 |

**注意：** 此表无需 filters，但建议用 WHERE + LIMIT 控制数据量。

---

## cn_option_basic_info — 期权合约基本信息

| 字段 | 说明 |
|------|------|
| `instrument` | 期权合约代码（如 `10011413.SHO`） |
| `underlying` | 标的代码（如 `510050.SH`） |
| `strike_price` | 行权价 |
| `option_type` | 期权类型（`C`=认购，`P`=认沽） |
| `list_date` | 上市日期 |
| `delist_date` | 到期日 |
| `multiplier` | 合约乘数（通常为10000） |
| `exercise_type` | 行权方式（`E`=欧式） |

---

## cn_option_bar1m — 期权 1 分钟 K 线

| 字段 | 说明 |
|------|------|
| `date` | 时间戳 |
| `instrument` | 期权合约代码 |
| `open` | 开盘价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `close` | 收盘价 |
| `volume` | 成交量 |
| `open_interest` | 持仓量 |

---

## cn_future_bar1d — 期货日线 K 线

| 字段 | 说明 |
|------|------|
| `date` | 交易日期 |
| `instrument` | 期货合约代码（如 `IF2501.CFE`） |
| `open` | 开盘价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `close` | 收盘价 |
| `volume` | 成交量 |
| `open_interest` | 持仓量 |
| `settle` | 结算价 |

---

## cn_future_basic_info — 期货合约基本信息

| 字段 | 说明 |
|------|------|
| `instrument` | 合约代码 |
| `product` | 品种代码（如 `IF`、`IC`、`IM`） |
| `list_date` | 上市日期 |
| `delist_date` | 到期日 |
| `multiplier` | 合约乘数 |
| `exchange` | 交易所 |

---

## cn_stock_index_bar1d — 指数日线 K 线

| 字段 | 说明 |
|------|------|
| `date` | 交易日期 |
| `instrument` | 指数代码（如 `000300.SH`、`000852.HIX`） |
| `open` | 开盘价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `close` | 收盘价 |
| `volume` | 成交量 |

---

## 常用指数代码

| 代码 | 名称 |
|------|------|
| `000300.SH` | 沪深300 |
| `000905.SH` | 中证500 |
| `000852.HIX` | 中证1000 |
| `000001.SH` | 上证指数 |
| `399001.SZ` | 深证成指 |

## 常用 ETF 代码

| 代码 | 名称 |
|------|------|
| `510050.SH` | 50ETF |
| `510300.SH` | 300ETF（华泰） |
| `159919.SZ` | 300ETF（嘉实） |
| `588000.SH` | 科创50ETF |
| `159915.SZ` | 创业板ETF |
