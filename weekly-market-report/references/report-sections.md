# Report Sections Reference

The HTML report contains these main sections. Each requires both JSON data (automatic) and narrative updates (manual).

## 1. Header Section

**Location**: Top of report
**Manual updates needed**:
- Report title date
- Week date range
- Headline theme (e.g., "小盘股狂飙：IWM领涨+4.18%")

```html
<h1>📈 QuantMind 本周市场周报</h1>
<div class="report-meta">
    <strong>报告日期：{{ report_date }}</strong>
    <span>数据周期：{{ week_start }} 至 {{ week_end }}</span>
</div>
<h3>🚀 [HEADLINE THEME - MANUAL UPDATE]</h3>
```

## 2. Market Summary (一、市场概况)

**What to update**: Key bullet points summarizing the week

```html
<div class="market-summary">
    <h3>📊 本周市场要点</h3>
    <ul>
        <li><strong>大盘走势</strong>：[SPY performance + context]</li>
        <li><strong>风格轮动</strong>：[IWM vs QQQ comparison]</li>
        <li><strong>板块分化</strong>：[Top/bottom sectors]</li>
        <li><strong>个股亮点</strong>：[Notable movers]</li>
    </ul>
</div>
```

## 3. Sector Performance (二、板块表现)

**Mostly automatic** via Jinja2 loops
**Manual updates**: Commentary on why sectors moved

## 4. Stock Analysis (三、重点个股)

**Data**: Automatic from JSON
**Manual updates**: Individual stock narratives, especially for big movers

Example narrative pattern:
```html
<div style="background: #e8f5e9;">  <!-- Green for positive -->
    <strong>✅ AMZN +8.10%</strong>：AWS加速增长，云计算需求强劲
</div>
<div style="background: #ffebee;">  <!-- Red for negative -->
    <strong>❌ AMD -11.76%</strong>：AI芯片竞争加剧，市场担忧份额流失
</div>
```

## 5. Crypto Section (五、加密货币)

**Manual updates needed**:
- BTC/ETH/SOL specific commentary
- Key support/resistance levels
- Catalyst discussion

## 6. Strategy Section (七、投资策略)

**Fully manual** - Investment recommendations

Subsections:
- 当前策略总结
- 仓位建议
- 具体操作点位

## 7. Outlook Section (八、下周展望)

**Manual updates needed**:
- Key events (CPI, earnings, etc.)
- Economic calendar
- Risk factors

```html
<h2>八、下周展望与关键事件</h2>
<ul>
    <li><strong>周三（1/15）</strong>：CPI消费者物价指数</li>
    <li><strong>周四（1/16）</strong>：零售销售数据</li>
    ...
</ul>
```

## 8. Roadmap Table (完整操作路线图)

**Critical manual updates**:
- "当前" row: Current date and SPY price
- Future timeline adjustments
- Key buy/sell points

```html
<tr style="background: #e3f2fd; border-left: 3px solid #1976d2;">
    <td><strong>🔵 当前：2026年1月10日</strong></td>
    <td>风格轮动，CPI等待期</td>
    <td>SPY $694，上升楔形</td>
    <td><strong>55-65%</strong></td>
    <td>策略建议...</td>
</tr>
```

## 9. Core Summary (核心观点总结)

**Manual update**: Final summary paragraph

Located at bottom of strategy section:
```html
<p style="background: linear-gradient(...);">
    <strong>💎 核心观点总结</strong>：本周SPY $XXX（+X.XX%），
    [week summary]。[key insight]。[forward outlook]。
</p>
```

## Color Coding Convention

| Color | Use Case | Background |
|-------|----------|------------|
| Green | Positive/Bullish | `#e8f5e9` |
| Red | Negative/Bearish | `#ffebee` |
| Orange | Neutral/Caution | `#fff3e0` |
| Blue | Current/Highlight | `#e3f2fd` |

## Common Patterns

### Adding External Analysis

When user provides insights from videos/research:

```html
<div style="background: rgba(255, 255, 255, 0.1); padding: 15px; margin: 15px 0; border-radius: 6px; border: 2px solid rgba(255, 152, 0, 0.5);">
    <h4 style="color: #ffeb3b; margin-top: 0;">📊 [SECTION TITLE]</h4>
    <ul>
        <li><strong>[Point 1]</strong>：[Details]</li>
        <li><strong>[Point 2]</strong>：[Details]</li>
    </ul>
</div>
```

### Stock Rating Table

```html
<table class="data-table" style="font-size: 13px;">
    <tr style="background: #e8f5e9;"><td>✅ GOOGL</td><td>看多 - 技术面强势</td></tr>
    <tr style="background: #fff3e0;"><td>⚖️ NVDA</td><td>谨慎 - 头肩顶风险</td></tr>
    <tr style="background: #ffcdd2;"><td>❌ TSLA</td><td>看空 - 预期-10%</td></tr>
</table>
```
