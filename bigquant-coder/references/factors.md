# cn_stock_prefactors 常用字段与因子库

## 价格与成交量字段

| 字段 | 说明 |
|------|------|
| `date` | 交易日期 |
| `instrument` | 股票代码（如 000001.SZ） |
| `open` | 开盘价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `close` | 收盘价（前复权） |
| `volume` | 成交量（股） |
| `amount` | 成交额（元） |
| `turn` | 换手率 |
| `total_market_cap` | 总市值 |
| `circulating_market_cap` | 流通市值 |

## 状态与分类字段

| 字段 | 说明 | 常用值 |
|------|------|--------|
| `st_status` | ST状态 | 0=正常 |
| `suspended` | 停牌状态 | 0=正常 |
| `list_sector` | 上市板块 | 1=上交所主板, 2=深交所主板, 3=创业板 |
| `list_days` | 上市天数 | >252 排除次新 |
| `sw2021_level1` | 申万一级行业代码 | 如 801780=银行 |
| `is_hs300` | 沪深300成分 | 1=是 |
| `is_zz500` | 中证500成分 | 1=是 |
| `is_zz1000` | 中证1000成分 | 1=是 |

## 估值字段

| 字段 | 说明 |
|------|------|
| `pe_ttm` | 市盈率（TTM） |
| `pb` | 市净率 |
| `ps_ttm` | 市销率（TTM） |
| `pcf_ttm` | 市现率（TTM） |
| `dividend_yield_ratio` | 股息率（注意：不是 `dividend_yield`） |

## 财务字段（TTM）

| 字段 | 说明 |
|------|------|
| `roe_avg_ttm` | 净资产收益率（加权平均，TTM） |
| `roe_avg_ttm_yoy` | ROE同比增速 |
| `roe_avg_deduct_ttm_yoy` | 扣非ROE同比增速 |
| `roe_avg_lf_consec_min_3y` | ROE连续3年最小值（质量筛选利器） |
| `roa_avg_ttm` | 总资产收益率（TTM，加权平均） |
| `roa_ttm` | 总资产收益率（TTM） |
| `operating_profit_ttm` | 营业利润（TTM） |
| `net_profit_ttm` | 净利润（TTM） |
| `net_profit_to_parent_shareholders_ttm_yoy` | 归母净利润同比增速 |
| `net_profit_lf_cagr_3` | 净利润3年复合增长率 |
| `total_operating_revenue_ttm_yoy` | 营业收入同比增速 |
| `total_profit_to_operating_revenue_ttm_yoy` | 总利润/营收同比 |
| `revenue_ttm` | 营业收入（TTM） |
| `fcff_ttm` | 自由现金流（TTM） |
| `net_cffoa_ttm` | 经营活动现金流净额（TTM） |
| `net_cffoa_lf` | 经营活动现金流净额（最新报告期） |
| `gross_profit_margin_ttm` | 毛利率（TTM） |
| `net_profit_margin_ttm` | 净利率（TTM） |

## 资产负债表字段（最新报告期 _lf）

| 字段 | 说明 |
|------|------|
| `debt_to_asset_lf` | 资产负债率 |
| `total_assets_lf` | 总资产 |
| `total_liabilities_lf` | 总负债 |
| `moneytary_assets_lf` | 货币资金 |
| `interest_bearing_debt_ratio_lf` | 有息负债率 |
| `float_market_cap` | 流通市值（单位：万元） |

## 资产负债表字段（最新报告期 _lf）

| 字段 | 说明 |
|------|------|
| `total_assets_lf` | 总资产 |
| `total_liabilities_lf` | 总负债 |
| `moneytary_assets_lf` | 货币资金 |
| `interest_bearing_debt_ratio_lf` | 有息负债率 |

## 技术指标字段

| 字段 | 说明 |
|------|------|
| `ma5` / `ma10` / `ma20` / `ma60` | 移动均线 |
| `macd_dif` / `macd_dea` / `macd_hist` | MACD |
| `rsi_6` / `rsi_12` / `rsi_24` | RSI |

---

## 因子构造模式

### 动量类

```sql
-- 20日动量
close / m_lag(close, 20) - 1

-- 波动率调整动量（夏普比率式）
(close / m_lag(close, 20) - 1) / m_stddev((high-low)/m_lag(close,1), 20)

-- 60日动量（排除最近5日，避免短期反转）
m_lag(close, 5) / m_lag(close, 60) - 1

-- 加速动量（短期动量 - 长期动量）
(close / m_lag(close, 5) - 1) - (close / m_lag(close, 20) - 1)
```

### 估值类

```sql
-- EP（盈利收益率，PE倒数）
1.0 / pe_ttm

-- BP（账面市值比，PB倒数）
1.0 / pb

-- FCF收益率
fcff_ttm / total_market_cap

-- 企业价值收益率
fcff_ttm / (total_market_cap + interest_bearing_debt_ratio_lf * total_assets_lf - moneytary_assets_lf)
```

### 质量类

```sql
-- ROE
roe_avg_ttm

-- ROE稳定性（越低越稳定）
m_stddev(roe_avg_ttm, 60)

-- 毛利率
gross_profit_margin_ttm

-- 现金流质量（经营现金流/营业利润）
net_cffoa_ttm / (operating_profit_ttm + 1e-8)
```

### 规模类

```sql
-- 小市值因子
1.0 / total_market_cap

-- 对数市值（用于中性化）
ln(total_market_cap)
```

### 流动性类

```sql
-- 低流动性溢价（成交额倒数）
1.0 / m_avg(amount, 10)

-- 换手率
m_avg(turn, 20)

-- Amihud 非流动性
m_avg(ABS(close/m_lag(close,1)-1) / (amount + 1e-8), 20)
```

### 波动率类

```sql
-- 低波动因子
1.0 / m_stddev(close/m_lag(close,1)-1, 20)

-- 特质波动率（需先计算残差）
m_stddev(close/m_lag(close,1)-1, 60)

-- 振幅
m_avg((high - low) / m_lag(close, 1), 20)
```

### 成长类

```sql
-- 营业利润同比增长
operating_profit_ttm / m_lag(operating_profit_ttm, 252) - 1

-- 营收同比增长
revenue_ttm / m_lag(revenue_ttm, 252) - 1

-- ROE 环比改善
roe_avg_ttm - m_lag(roe_avg_ttm, 63)
```

### 技术类

```sql
-- 均线偏离度
close / m_avg(close, 20) - 1

-- 成交量比率
m_avg(volume, 5) / (m_avg(volume, 20) + 1e-8)

-- RSI
m_ta_rsi(close, 14)
```
