# JSON Data Schema

The `market_data_janXX.json` file contains all market data needed for report generation.

## Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `report_date` | string | Chinese format: "2026年1月10日" |
| `report_date_iso` | string | ISO format: "2026-01-10" |
| `week_start` | string | Week start in Chinese format |
| `week_start_iso` | string | Week start in ISO format |
| `week_end` | string | Week end in Chinese format |
| `week_end_iso` | string | Week end in ISO format |
| `ytd_reference_date` | string | Dec 31 of previous year |

## Indices Array

```json
{
  "ticker": "SPY",
  "name": "标普500 ETF",
  "close": 694.07,
  "weekly_change": 1.1,
  "ytd_change": 1.78,
  "week_high": 695.31,
  "week_low": 686.38
}
```

**Tickers**: SPY, QQQ, DIA, IWM

## Sectors Array

```json
{
  "ticker": "XLB",
  "sector": "材料 Materials",
  "weekly_return": 4.87,
  "monthly_return": 8.96,
  "ytd_return": 6.42
}
```

**Sorted by**: `weekly_return` descending

**Tickers**: XLB, XLY, IWM, XLI, XLP, XLV, XLF, XLC, XLRE, XLK, XLE, XLU

## Mag7 / Stocks Arrays

Both contain the same stocks but `mag7` includes high/low:

```json
{
  "ticker": "AMZN",
  "name": "亚马逊",
  "close": 247.38,
  "weekly_change": 8.1,
  "ytd_change": 7.17,
  "week_high": 247.86,    // only in mag7
  "week_low": 227.18      // only in mag7
}
```

**Sorted by**: `weekly_change` descending

**Tickers**: NVDA, AAPL, MSFT, GOOGL, META, AMZN, TSLA, LLY, AMD, MU

## Crypto Array

```json
{
  "ticker": "BTC",
  "name": "比特币",
  "close": 90503,
  "weekly_change": -1.08,
  "week_high": 94825,
  "week_low": 89199
}
```

**Tickers**: BTC, ETH, SOL

## Global Markets Array

```json
{
  "region": "日本",
  "index": "日本ETF (EWJ)",
  "weekly_return": 2.74,
  "ytd_return": 4.79
}
```

**Sorted by**: `weekly_return` descending

**Regions**: Japan (EWJ), Hong Kong (EWH), Germany (EWG), UK (EWU), China (FXI)

## Jinja2 Template Usage

Access data in template:

```html
{% for index in indices %}
  <td>{{ index.name }} ({{ index.ticker }})</td>
  <td>${{ "%.2f"|format(index.close) }}</td>
  <td class="{{ 'positive' if index.weekly_change > 0 else 'negative' }}">
    {{ '+' if index.weekly_change > 0 else '' }}{{ index.weekly_change }}%
  </td>
{% endfor %}
```
