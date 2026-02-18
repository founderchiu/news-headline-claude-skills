---
name: weekly-market-report
description: Generate QuantMind weekly market reports. Use when the user asks to create a new weekly market report, update report data, or work on the market summary. Triggers on phrases like "weekly report", "market report", "周报", "market summary", or when working in the weekly market summary project.
version: 1.5.0
last_updated: 2026-02-01
---

# Weekly Market Report Generator

Generate bilingual (Chinese/English) weekly market reports covering US indices, sectors, stocks, crypto, and global markets.

> **Skill Version**: 1.5.0 | **Last Updated**: 2026-02-01 | **Project**: `/Users/tim/quantmind/weekly market summary`

## Table of Contents

| Section | Description |
|---------|-------------|
| [Quick Start](#quick-start-decision-tree) | Decision tree for common tasks |
| [Full Workflow](#full-workflow) | Complete 7-step process |
| [**Data Validation**](#data-validation) | **NEW: Real-time data freshness validation** |
| [Example Walkthrough](#example-workflow-walkthrough) | Real scenario demonstration |
| [Headline Patterns](#headline-patterns) | 5 headline templates |
| [Narrative Guidelines](#narrative-writing-guidelines) | Writing patterns for all sections |
| [Strategy Templates](#strategy-section-templates) | Position & recommendation patterns |
| [Economic Calendar](#economic-calendar) | Events and calendar format |
| [US Market Holidays](#us-market-holidays-2026) | 2026 market closures |
| [Illustrations](#illustration-generation) | Visual asset creation |
| [External Analysis](#adding-external-analysis) | Integrating video/research insights |
| [Quality Checklist](#quality-checklist-before-publishing) | Pre-publish verification |
| [Troubleshooting](#troubleshooting) | Common issues and fixes |
| [Project Structure](#project-structure) | File organization |
| [CLI Reference](#cli-quick-reference) | Command cheat sheet |
| [Jinja2 Reference](#jinja2-template-quick-reference) | Template syntax |
| [Ticker Reference](#ticker-reference-chinese-names) | Chinese name lookups |
| [Search/Replace](#common-searchreplace-patterns) | Regex patterns for updates |

---

## Quick Start Decision Tree

```
What do you need to do?
│
├─► Create NEW report for this week?
│   └─► Go to [Full Workflow](#full-workflow)
│
├─► UPDATE existing report narrative?
│   └─► Go to [Step 4: Update Narrative](#step-4-update-narrative-sections)
│
├─► ADD external analysis (video insights)?
│   └─► Go to [Adding External Analysis](#adding-external-analysis)
│
├─► Generate ILLUSTRATIONS?
│   └─► Go to [Illustration Generation](#illustration-generation)
│
├─► FIX data issues?
│   └─► Go to [Troubleshooting](#troubleshooting)
│
└─► Just VERIFY data?
    └─► Run: `python run_weekly_report.py YYYY-MM-DD --verify`
```

## Pre-Flight Checklist

Before starting, confirm:
- [ ] It's Friday after 4PM ET (market closed)
- [ ] Polygon API key is configured in `automation/config.py`
- [ ] Python venv exists: `"/Users/tim/quantmind/weekly market summary/venv"`
- [ ] Check [US Market Holidays](#us-market-holidays-2026) for closures

---

## Full Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  1. FETCH DATA  →  2. VERIFY  →  2.5 VALIDATE (NEW!)  →         │
│                                                                  │
│  3. COPY TEMPLATE  →  4. UPDATE NARRATIVE  →  5. GENERATE HTML  │
│                                                                  │
│  →  6. EXPORT PDF  →  (Optional) 7. GENERATE ILLUSTRATIONS      │
└─────────────────────────────────────────────────────────────────┘
```

> **NEW in v1.5.0**: Step 2.5 validates data freshness against real-time sources (crypto via CoinGecko, stocks via Yahoo Finance). Run before publishing!

### Step 1: Fetch Market Data

**When**: Friday after 4PM ET market close

**Commands**:
```bash
cd "/Users/tim/quantmind/weekly market summary"
source venv/bin/activate
cd automation
python run_weekly_report.py YYYY-MM-DD  # e.g., 2026-01-24
```

**Output**: `market_data_jan24.json` (in project root)

**What gets fetched**:
| Category | Tickers | Count |
|----------|---------|-------|
| Indices | SPY, QQQ, DIA, IWM | 4 |
| Sectors | XLK, XLV, XLF, XLE, XLI, XLP, XLY, XLU, XLC, XLB, XLRE + IWM (Small Cap) | 12 |
| Stocks | NVDA, AAPL, MSFT, GOOGL, META, AMZN, TSLA, LLY, AMD, MU | 10 |
| Crypto | BTC, ETH, SOL | 3 |
| Global | FXI, EWH, EWU, EWJ, EWG | 5 |

### Step 2: Verify Data

**Command**:
```bash
python run_weekly_report.py YYYY-MM-DD --verify
```

**Verification Checklist**:
- [ ] All tickers have non-zero close prices
- [ ] Weekly changes are within reasonable range (-20% to +20%)
- [ ] No API errors in output
- [ ] Expected counts: 4 indices, 12 sectors (incl. IWM), 10 stocks, 3 crypto, 5 global

**If verification fails**: See [Troubleshooting](#troubleshooting)

### Step 2.5: Validate Data Freshness (NEW!)

**Purpose**: Ensure data is current by comparing against real-time sources.

**Commands**:
```bash
cd "/Users/tim/quantmind/weekly market summary/automation"

# Validate all sections against real-time sources
python validate_data.py ../market_data_jan31.json

# Validate and auto-fix stale prices
python validate_data.py ../market_data_jan31.json --auto-fix

# Validate specific section only
python validate_data.py ../market_data_jan31.json --section crypto
python validate_data.py ../market_data_jan31.json --section stocks
python validate_data.py ../market_data_jan31.json --section indices

# Verbose output with all fetched prices
python validate_data.py ../market_data_jan31.json --verbose
```

**What gets validated**:
| Section | Data Source | Threshold |
|---------|-------------|-----------|
| Crypto (BTC, ETH, SOL) | CoinGecko API | >3% diff triggers alert |
| Indices (SPY, QQQ, DIA, IWM) | Yahoo Finance | >1% diff triggers alert |
| Stocks (Mag7 + tech) | Yahoo Finance | >2% diff triggers alert |
| Sectors | Sanity check | >15% weekly return is extreme |
| Global Markets | Sanity check | >10% weekly return is extreme |

**When to run**:
- **CRITICAL for weekend reports**: Crypto trades 24/7, so Friday close data may be stale by Sunday
- After fetching data, before generating HTML
- If report is >2 days old

**Example output**:
```
============================================================
    QUANTMIND COMPREHENSIVE DATA VALIDATION
    File: market_data_jan31.json
    Section: all
============================================================

📅 Checking date freshness...
  ✅ Report date OK (2026-01-31, 1 days ago)

₿ Validating CRYPTO prices (CoinGecko)...
  ⚠️  Discrepancies found:
    - BTC: JSON $84,121 vs Real $78,243 (7.5% diff)
    - ETH: JSON $2,702 vs Real $2,370 (14.0% diff)

📊 Validating INDICES prices (Yahoo Finance)...
  ✅ Index prices are up to date

💹 Validating STOCK prices (Yahoo Finance)...
  ✅ Stock prices are up to date

🔧 Auto-fixing crypto prices...
  Updated BTC: $84,121 -> $78,243
  Updated ETH: $2,702 -> $2,370

  ✅ Updated market_data_jan31.json
```

### Step 3: Copy Previous Template and Validate Content

> **CRITICAL**: After copying template, always run `validate_report.py` to find stale content!

**Commands**:
```bash
cd "/Users/tim/quantmind/weekly market summary"
# Copy previous template
cp report_generator_jan24.py report_generator_jan31.py

# IMMEDIATELY validate against JSON to find stale content
cd automation
python validate_report.py ../report_generator_jan31.py ../market_data_jan31.json
```

**What gets validated**:
| Issue Type | Description | Example |
|------------|-------------|---------|
| Stale dates | Dates from previous weeks | "1月17日" when report is 1月31日 |
| Wrong direction | Sign mismatch (+/-) | Report says "+3%" but JSON is -7% |
| Stale prices | Price references don't match | "SPY $698" when JSON has $692 |
| Wrong leaders | Wrong sector as leader | "XLB领涨" when XLC is top |
| Stale percentages | Values differ significantly | "+8%" when JSON shows +2% |

**Example output showing issues**:
```
📊 Validating PERCENTAGES...
  ⚠️  Found 238 percentage issue(s):
    - Line 3: MSFT WRONG DIRECTION! Report says +3.00% but JSON is -7.53%
    - Line 210: AMD +0.00% in report vs -7.80% in JSON
    - Line 211: IWM WRONG DIRECTION! Report says +4.00% but JSON is -2.04%

🏢 Validating SECTOR rankings...
  ⚠️  Found 20 sector issue(s):
    - Line 214: 'XLB' mentioned as leader, but XLC is actually top (+2.40%)
```

### Step 4: Update Report Content (formerly Step 3)

**Commands**:
```bash
cd "/Users/tim/quantmind/weekly market summary"
# Find most recent template
ls -la report_generator_*.py | tail -1
# Copy it (adjust filenames)
cp report_generator_jan17.py report_generator_jan24.py
```

**Important**: Always use the most recent generator as your template - it has the latest styling and section structure.

### Step 4: Update Narrative Sections

Edit the new `report_generator_janXX.py`. This is the most critical step.

**Required Updates Checklist**:

| Priority | Section | Location | What to Update |
|----------|---------|----------|----------------|
| HIGH | Report dates | Top of class | `report_date`, week range strings |
| HIGH | Headline theme | `<h3>🚀 ...` | Main market story (see [Headline Patterns](#headline-patterns)) |
| HIGH | Market summary | `market-summary` div | 4 key bullet points |
| MED | Sector analysis | Section 2 | Leaders/laggards commentary |
| MED | Stock analysis | Section 3 | Individual stock narratives |
| MED | Crypto outlook | Section 5 | BTC/ETH/SOL commentary |
| MED | Strategy section | Section 7 | Current recommendations (see [Strategy Templates](#strategy-section-templates)) |
| HIGH | Next week preview | Section 8 | Upcoming events (see [Economic Calendar](#economic-calendar)) |
| HIGH | Roadmap table | "完整操作路线图" | Current position, targets |
| MED | Core summary | "核心观点总结" | Final paragraph |

**Date Format Examples**:
- Chinese: `2026年1月24日`
- Week range: `1月19日-1月24日`
- ISO: `2026-01-24`

### Step 5: Generate HTML

**Commands**:
```bash
cd "/Users/tim/quantmind/weekly market summary"
source venv/bin/activate
python report_generator_jan24.py
```

**Output**: `quantmind-weekly-report-jan-24-2026.html`

**Post-Generation Check**:
- [ ] Open HTML in browser
- [ ] Verify all data tables populated correctly
- [ ] Check narrative sections read well
- [ ] Confirm no placeholder text remains

### Step 6: Export PDF

1. Open HTML in browser (Chrome recommended)
2. Print → Save as PDF
3. **Filename**: `QuantMind 本周市场周报 - 2026年1月24日.pdf`

**PDF Export Settings (Chrome)**:
- Destination: Save as PDF
- Pages: All
- Layout: Portrait
- Paper size: A4
- Margins: Default
- Scale: 100% (or "Fit to page" if content overflows)
- Background graphics: ✅ Enabled (important for colors)

**Common PDF Issues**:
- Tables cut off → Reduce browser zoom to 90% before printing
- Colors missing → Enable "Background graphics" checkbox
- Fonts look wrong → Use Chrome (Firefox may render differently)

---

## Example Workflow Walkthrough

**Scenario**: Creating the Jan 24, 2026 report after market close.

### 1. Fetch Data
```bash
cd "/Users/tim/quantmind/weekly market summary"
source venv/bin/activate
cd automation
python run_weekly_report.py 2026-01-24
```

Output shows:
```
SPY   $698.50  Week: +0.99%  YTD: +2.44%
QQQ   $628.00  Week: +1.08%  YTD: +2.23%
...
✅ Data fetched and verified successfully!
```

### 2. Analyze Key Themes
Looking at the data, identify:
- **Headline story**: SPY approaching $700 milestone
- **Style rotation**: QQQ slightly outperforming IWM (tech leading)
- **Top sector**: XLK +2.1% (tech recovery)
- **Top stock**: NVDA +5.2% (AI momentum)
- **Crypto**: BTC holding above $95k

### 3. Copy and Update Template
```bash
cp report_generator_jan17.py report_generator_jan24.py
```

Key updates to make:
1. Change all `1月17日` → `1月24日`
2. Change week range `1月12日-1月17日` → `1月19日-1月24日`
3. Update headline: `🚀 SPY逼近$700大关：科技股领涨，牛市延续`
4. Update market summary bullets with new data
5. Update "当前" row in roadmap table

### 4. Generate and Review
```bash
python report_generator_jan24.py
open quantmind-weekly-report-jan-24-2026.html
```

Check:
- Tables show correct prices
- Narratives match the data
- No stale dates or prices

### 5. Export PDF
- Print to PDF: `QuantMind 本周市场周报 - 2026年1月24日.pdf`

---

## Headline Patterns

The headline (`<h3>🚀 ...`) should capture the week's dominant theme. Choose from these patterns:

### Single Stock Dominance
When one stock significantly outperforms/underperforms:
```
AMD反转狂飙+15.24%，防御板块走强，加密货币回暖
[STOCK]反转狂飙+X.XX%，[secondary theme]，[tertiary theme]
```

### Style Rotation
When small vs large cap divergence is significant:
```
小盘股狂飙：IWM领涨+4.18%，资金轮动加速
风格轮动：[IWM/QQQ] +X.XX%领涨，[context]
```

### Sector Leadership
When a sector dominates:
```
科技板块回归：XLK +3.5%引领反弹
[Sector]领涨+X.XX%：[brief catalyst]
```

### Market-Wide Move
When broad market moves uniformly:
```
全线上涨：SPY突破$700大关，牛市继续
全线回调：避险情绪升温，等待CPI指引
```

### Mixed/Divergent Week
When no clear trend:
```
多空博弈：指数窄幅震荡，板块分化加剧
震荡整理：SPY横盘，资金观望下周CPI
```

---

## Narrative Writing Guidelines

### Market Summary Pattern (本周市场要点)

Always include these 4 bullet points:
```html
<ul>
    <li><strong>大盘走势</strong>：SPY本周+X.XX%，收于$XXX，[context - trend continuation/reversal/consolidation]</li>
    <li><strong>风格轮动</strong>：[Compare IWM vs QQQ - which style is leading and why]</li>
    <li><strong>板块分化</strong>：[Top sector] +X.XX%领涨，[Bottom sector] -X.XX%垫底，[brief reason]</li>
    <li><strong>个股亮点</strong>：[Notable mover] +X.XX%[reason]，[secondary mover if significant]</li>
</ul>
```

### Stock Narrative Patterns

**Positive performance (+3% or more)**:
```html
<div style="background: #e8f5e9;">
    <strong>✅ [TICKER] +X.XX%</strong>：[catalyst]，[technical note]
</div>
```
Example catalysts: 财报超预期, AI需求强劲, 产品发布利好, 分析师上调评级

**Negative performance (-3% or more)**:
```html
<div style="background: #ffebee;">
    <strong>❌ [TICKER] -X.XX%</strong>：[headwind]，[technical concern]
</div>
```
Example headwinds: 指引不及预期, 竞争加剧, 估值压力, 监管担忧

**Neutral/Mixed (-3% to +3%)**:
```html
<div style="background: #fff3e0;">
    <strong>⚖️ [TICKER] +/-X.XX%</strong>：[context for consolidation]
</div>
```

### Sector Analysis Pattern

Top performers:
```
[Sector]板块本周+X.XX%领涨，主要受益于[catalyst]。
```

Bottom performers:
```
[Sector]板块-X.XX%垫底，压力来自[headwind]。
```

### Crypto Commentary Pattern

```
比特币本周[上涨/下跌]X.XX%至$XX,XXX，[support/resistance level context]。
以太坊[跟随/分化]，+/-X.XX%，[ETH-specific catalyst if any]。
Solana [performance]，生态活跃度[observation]。
```

### Global Markets Commentary Pattern

```
全球市场方面，[top performer region]表现最强，[ETF ticker] +X.XX%，受益于[catalyst]。
[bottom performer region]承压，[ETF ticker] -X.XX%，主要受[headwind]影响。
整体来看，[overall observation about global risk appetite/correlation with US markets]。
```

**Region-specific catalysts**:
- **China (FXI)**: 政策刺激, 经济数据, 地缘政治
- **Hong Kong (EWH)**: 科技股表现, 南向资金, 汇率波动
- **Japan (EWJ)**: 日元走势, 央行政策, 出口数据
- **Germany (EWG)**: 能源价格, 制造业PMI, 欧央行政策
- **UK (EWU)**: 英镑汇率, 通胀数据, 脱欧影响

---

## Strategy Section Templates

### Investment Strategy Summary (投资策略总结)

```html
<p style="margin-top: 15px; padding: 12px; background: rgba(25, 118, 210, 0.1); border-radius: 5px; border-left: 4px solid #1976d2;">
    <strong style="color: #1565c0;">⚠️ 投资策略总结</strong>：<strong>[主策略]</strong>——[详细说明]。建议[具体操作建议]。<strong>[关注重点]</strong>，[时机建议]。
</p>
```

**Example strategies**:
- **配置多样化**: 不要过度集中于科技股，配置1-2家科技领头羊，同时分散到医药、房地产等补涨板块
- **逢低买入**: 关键支撑位$XXX附近考虑加仓
- **获利了结**: 盈利仓位可考虑部分减持锁定利润
- **观望等待**: CPI/FOMC前维持现有仓位，等待数据明朗

### Position Recommendation (仓位建议)

```html
<p style="margin-top: 15px;"><strong>🎯 仓位建议（[时间点]）：</strong></p>
<ul>
    <li><strong>XX-XX% 股票</strong>：[市场状态说明]
        <ul style="margin-top: 5px; font-size: 13px;">
            <li>科技股XX%：[具体建议]</li>
            <li>防御板块XX%：[具体建议]</li>
        </ul>
    </li>
    <li><strong>XX-XX% 现金</strong>：[现金策略]</li>
    <li><strong>XX-XX% 加密货币</strong>：[加密策略]</li>
</ul>
```

**Position guidance by market condition**:
| Market State | Stock % | Cash % | Crypto % |
|--------------|---------|--------|----------|
| Strong Bull | 70-80% | 10-15% | 10-15% |
| Mild Bull | 60-70% | 20-25% | 10-15% |
| Neutral/Uncertain | 50-60% | 30-35% | 10-15% |
| Defensive | 40-50% | 40-45% | 10-15% |
| Bear Market | 30-40% | 50-55% | 5-10% |

### Core Summary (核心观点总结)

```html
<p style="margin-top: 20px; padding: 15px; background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); border-radius: 8px; border-left: 4px solid #1976d2;">
    <strong>💎 核心观点总结</strong>：本周SPY $XXX（+X.XX%），[周度总结一句话]。[关键观察点]。[展望下周/未来]。<strong>[最终建议]</strong>，[具体行动指引]。
</p>
```

---

## Economic Calendar

### Finding Next Week's Events

Check these sources for upcoming market-moving events:
1. Federal Reserve calendar (FOMC meetings, speeches)
2. Bureau of Labor Statistics (CPI, PPI, Jobs)
3. Major earnings (lookup earnings calendars)

### Common Events to Watch

| Event | Typical Day | Market Impact |
|-------|-------------|---------------|
| CPI | ~10th-15th | HIGH - inflation data |
| PPI | Day after CPI | MED - producer prices |
| FOMC Decision | 8 times/year | HIGH - rate decisions |
| Jobs Report | First Friday | HIGH - employment |
| Retail Sales | Mid-month | MED - consumer spending |
| PCE | End of month | HIGH - Fed's preferred inflation |

### Calendar Section Pattern

```html
<h2>八、下周展望与关键事件</h2>
<ul>
    <li><strong>周一（1/20）</strong>：[Event or "马丁·路德·金纪念日，美股休市"]</li>
    <li><strong>周二（1/21）</strong>：[Event]</li>
    <li><strong>周三（1/22）</strong>：[Event]</li>
    <li><strong>周四（1/23）</strong>：[Event or earnings: NFLX, etc.]</li>
    <li><strong>周五（1/24）</strong>：[Event]</li>
</ul>
```

---

## US Market Holidays 2026

| Date | Holiday | Market Status |
|------|---------|---------------|
| Jan 1 (Thu) | New Year's Day | Closed |
| Jan 19 (Mon) | MLK Day | Closed |
| Feb 16 (Mon) | Presidents' Day | Closed |
| Apr 3 (Fri) | Good Friday | Closed |
| May 25 (Mon) | Memorial Day | Closed |
| Jul 3 (Fri) | Independence Day (observed) | Closed |
| Sep 7 (Mon) | Labor Day | Closed |
| Nov 26 (Thu) | Thanksgiving | Closed |
| Nov 27 (Fri) | Day after Thanksgiving | Early close 1PM |
| Dec 25 (Fri) | Christmas | Closed |

**Note**: When holidays fall on weekends, markets close on adjacent Friday/Monday.

---

## Illustration Generation

Create illustrations for key report sections. Store prompts in:
`quantmind-weekly-report-jan-XX-2026/illustrations/prompts/`

### Standard Illustration Set

1. **Market Overview** - `illustration-market-overview.md`
2. **Sector Rotation** - `illustration-sector-rotation.md`
3. **Stock Spotlight** - `illustration-[theme].md` (e.g., semiconductor-reversal)
4. **Mag7 Outlook** - `illustration-mag7-outlook.md`
5. **Crypto** - `illustration-crypto-recovery.md`
6. **Global Markets** - `illustration-global-markets.md`
7. **Next Week** - `illustration-next-week-outlook.md`

### Illustration Prompt Template

```markdown
插图主题: [Theme in Chinese]
风格: elegant (精致优雅) / modern (现代简约) / warm (温暖活力)

视觉构图:
- 主视觉: [Central element description]
- 左侧区域: [Left side elements]
- 右侧区域: [Right side elements]
- 背景: [Background treatment]
- 整体布局: [Layout notes]

配色方案:
- 主色: [Primary color with hex]
- 背景: [Background color with hex]
- 强调色: [Accent colors with hex]

文字内容:
- 中央: "[Main text]"
- 左侧小标: "[Left label]"
- 右侧小标: "[Right label]"

风格要点:
- [Style note 1]
- [Style note 2]
- [Style note 3]
```

### Color Palettes by Style

**Elegant (精致优雅)**:
- Primary: Soft coral `#E8A598`
- Background: Warm cream `#F5F0E6`
- Accents: Gold `#C9A962`, Teal `#5B8A8A`

**Modern (现代简约)**:
- Primary: Deep blue `#1976d2`
- Background: Light gray `#f5f7fa`
- Accents: Orange `#ff9800`, Green `#4caf50`

**Warm (温暖活力)**:
- Primary: Coral red `#c62828`
- Background: Soft white `#fafafa`
- Accents: Gold `#ffc107`, Deep teal `#00796b`

---

## Adding External Analysis

When user provides insights from videos or external research:

**Template for new analysis section**:
```html
<div style="background: rgba(255, 255, 255, 0.1); padding: 15px; margin: 15px 0; border-radius: 6px; border: 2px solid rgba(255, 152, 0, 0.5);">
    <h4 style="color: #ffeb3b; margin-top: 0;">📊 [SECTION TITLE]</h4>
    <ul>
        <li><strong>[Point 1]</strong>：[Details]</li>
        <li><strong>[Point 2]</strong>：[Details]</li>
    </ul>
</div>
```

**Stock Rating Table**:
```html
<table class="data-table" style="font-size: 13px;">
    <tr style="background: #e8f5e9;"><td>✅ GOOGL</td><td>看多 - 技术面强势</td></tr>
    <tr style="background: #fff3e0;"><td>⚖️ NVDA</td><td>谨慎 - 头肩顶风险</td></tr>
    <tr style="background: #ffcdd2;"><td>❌ TSLA</td><td>看空 - 预期-10%</td></tr>
</table>
```

**Color Conventions**:
| Color | Meaning | Background Code |
|-------|---------|-----------------|
| Green | Bullish/Positive | `#e8f5e9` |
| Red | Bearish/Negative | `#ffebee` or `#ffcdd2` |
| Orange | Neutral/Caution | `#fff3e0` |
| Blue | Current/Highlight | `#e3f2fd` |

---

## Quality Checklist Before Publishing

Run through this checklist before finalizing the report:

### Data Accuracy
- [ ] All prices match JSON data file
- [ ] Weekly/YTD percentages calculated correctly
- [ ] Sector rankings match actual performance order
- [ ] Crypto prices are current (weekend movement considered)

### Dates and Timing
- [ ] Report date is correct in title and header
- [ ] Week range is accurate (Monday-Friday)
- [ ] "当前" row in roadmap shows correct date
- [ ] Next week events are for the correct dates
- [ ] No stale dates from previous week's template

### Narrative Consistency
- [ ] Headlines match actual data (top performer is featured)
- [ ] Market summary bullets reflect this week, not last
- [ ] Stock narratives match their actual performance direction
- [ ] Strategy recommendations align with market conditions

### Visual/Formatting
- [ ] Tables render correctly in browser
- [ ] Color coding is consistent (green=up, red=down)
- [ ] No broken HTML or missing closing tags
- [ ] PDF exports cleanly without cut-off content

### Final Review
- [ ] Read through entire report for flow
- [ ] Check for typos in Chinese and English text
- [ ] Verify all external analysis is integrated properly
- [ ] Confirm file naming follows convention

---

## Troubleshooting

### Data Issues

**Problem**: Zero values or missing tickers
```bash
# Re-run fetch for specific date
python run_weekly_report.py 2026-01-24

# If still failing, check API key
cat automation/.env
```

**Problem**: API rate limit errors
- Wait 60 seconds and retry
- Polygon free tier has limits

**Problem**: Wrong week dates in JSON
- Manually edit `market_data_janXX.json`
- Update `week_start`, `week_end`, `report_date` fields

### Template Issues

**Problem**: Stale dates in narrative
Search and replace these patterns:
- Old week range: `1月5日-1月10日` → `1月19日-1月24日`
- Old report date: `2026年1月17日` → `2026年1月24日`
- Old SPY prices in strategy sections

**Problem**: HTML generation errors
```bash
# Check for Python syntax errors
python -m py_compile report_generator_jan24.py

# Check Jinja2 template syntax
python -c "from jinja2 import Template; exec(open('report_generator_jan24.py').read())"
```

### Roadmap Table Update

The roadmap table at "完整操作路线图" requires special attention:

1. Update "当前" (current) row:
```html
<tr style="background: #e3f2fd; border-left: 3px solid #1976d2;">
    <td><strong>🔵 当前：2026年1月24日</strong></td>
    <td>[Current market phase]</td>
    <td>SPY $XXX，[pattern]</td>
    <td><strong>XX-XX%</strong></td>
    <td>[Strategy]</td>
</tr>
```

2. Adjust future timeline entries if market outlook changes
3. Update key buy/sell points based on current prices

---

## Project Structure

```
weekly market summary/
├── automation/
│   ├── config.py              # Ticker definitions, API config
│   ├── data_fetcher.py        # Polygon API client
│   ├── run_weekly_report.py   # Main CLI tool
│   └── .env                   # API keys (not committed)
├── market_data_janXX.json     # Current week's data
├── report_generator_janXX.py  # Current week's template
├── quantmind-weekly-report-*.html  # Generated reports
├── quantmind-weekly-report-jan-XX-2026/
│   └── illustrations/
│       └── prompts/           # Illustration generation prompts
├── archive/                   # Old reports and data
└── venv/                      # Python virtual environment
```

---

## CLI Quick Reference

```bash
# Fetch data for specific date
python run_weekly_report.py 2026-01-24

# Verify existing data
python run_weekly_report.py 2026-01-24 --verify

# Fetch only (no HTML generation prompt)
python run_weekly_report.py 2026-01-24 --fetch-only

# List existing data files
python run_weekly_report.py --list
```

---

## Jinja2 Template Quick Reference

### Accessing Data in Template

```html
<!-- Report metadata -->
{{ report_date }}           <!-- 2026年1月24日 -->
{{ week_start }} - {{ week_end }}

<!-- Looping through indices -->
{% for idx in indices %}
    {{ idx.ticker }}        <!-- SPY -->
    {{ idx.name }}          <!-- 标普500 ETF -->
    ${{ "%.2f"|format(idx.close) }}  <!-- $695.00 -->
    {{ '+' if idx.weekly_change > 0 else '' }}{{ idx.weekly_change }}%
{% endfor %}

<!-- Conditional styling -->
<td class="{{ 'positive' if item.weekly_change > 0 else 'negative' }}">

<!-- Number formatting -->
{{ "%.2f"|format(value) }}      <!-- 2 decimal places -->
{{ "{:,}".format(value|int) }}  <!-- Thousands separator -->
```

### Data Access Paths

| Data | Template Variable | Fields |
|------|------------------|--------|
| Indices | `indices` | ticker, name, close, weekly_change, ytd_change, week_high, week_low |
| Sectors | `sectors` | ticker, sector, weekly_return, monthly_return, ytd_return |
| Stocks | `stocks` or `mag7` | ticker, name, close, weekly_change, ytd_change |
| Crypto | `crypto` | ticker, name, close, weekly_change, week_high, week_low |
| Global | `global_markets` | region, index, weekly_return, ytd_return |

---

## Ticker Reference (Chinese Names)

### Indices
| Ticker | Chinese Name | English Name |
|--------|--------------|--------------|
| SPY | 标普500 ETF | S&P 500 ETF |
| QQQ | 纳指100 ETF | Nasdaq 100 ETF |
| DIA | 道指 ETF | Dow Jones ETF |
| IWM | 罗素2000 ETF | Russell 2000 ETF |

### Sectors
| Ticker | Chinese Name | English Name | Type |
|--------|--------------|--------------|------|
| XLK | 信息技术 | Technology | Cyclical |
| XLV | 医疗保健 | Healthcare | Defensive |
| XLF | 金融 | Financials | Cyclical |
| XLE | 能源 | Energy | Cyclical |
| XLI | 工业 | Industrials | Cyclical |
| XLP | 必需消费 | Consumer Staples | Defensive |
| XLY | 可选消费 | Consumer Discretionary | Cyclical |
| XLU | 公用事业 | Utilities | Defensive |
| XLC | 通讯服务 | Communication Services | Cyclical |
| XLB | 材料 | Materials | Cyclical |
| XLRE | 房地产 | Real Estate | Interest-sensitive |

**Sector Classifications**:
- **Defensive** (XLU, XLP, XLV): Outperform in risk-off environments
- **Cyclical** (XLY, XLI, XLF, XLK, XLE, XLB, XLC): Outperform in risk-on environments
- **Interest-sensitive** (XLRE): Sensitive to rate changes

### Stocks (Mag7 + Key Names)
| Ticker | Chinese Name | Sector |
|--------|--------------|--------|
| NVDA | 英伟达 | AI/Semiconductors |
| AAPL | 苹果 | Consumer Tech |
| MSFT | 微软 | Enterprise Tech |
| GOOGL | 谷歌 | Search/Cloud |
| META | Meta | Social Media |
| AMZN | 亚马逊 | E-commerce/Cloud |
| TSLA | 特斯拉 | EV/Energy |
| LLY | 礼来 | Pharma (GLP-1) |
| AMD | AMD | Semiconductors |
| MU | 美光科技 | Memory |

### Crypto
| Ticker | Chinese Name |
|--------|--------------|
| BTC | 比特币 |
| ETH | 以太坊 |
| SOL | Solana |

### Global Markets
| Ticker | Chinese Name | Region |
|--------|--------------|--------|
| FXI | 中国大盘ETF | China |
| EWH | 香港ETF | Hong Kong |
| EWJ | 日本ETF | Japan |
| EWG | 德国ETF | Germany |
| EWU | 英国ETF | UK |

---

## Common Search/Replace Patterns

When updating templates, use these regex patterns to find and replace stale content:

### Date Updates
```
# Week range (Chinese)
Find: \d+月\d+日-\d+月\d+日
Example: 1月12日-1月17日 → 1月19日-1月24日

# Report date (Chinese)
Find: 2026年\d+月\d+日
Example: 2026年1月17日 → 2026年1月24日

# ISO date
Find: 2026-\d{2}-\d{2}
Example: 2026-01-17 → 2026-01-24
```

### Price Updates
```
# SPY price in text
Find: SPY \$\d+(\.\d+)?
Example: SPY $691.66 → SPY $698.50

# Price with comma (BTC)
Find: \$\d{2},\d{3}
Example: $95,535 → $96,800
```

### Percentage Updates
```
# Weekly change
Find: [+-]\d+\.\d+%
Example: +0.14% → +0.99%

# In narrative
Find: 本周[+-]?\d+\.\d+%
Example: 本周+0.14% → 本周+0.99%
```

### Roadmap "当前" Row
```
Find: 🔵 当前：2026年\d+月\d+日
Replace with current date
```

---

## References

- [references/json-schema.md](references/json-schema.md) - Complete JSON data structure with all fields
- [references/report-sections.md](references/report-sections.md) - Detailed section breakdown with HTML patterns

---

## Changelog

### v1.5.0 (2026-02-01)
- **NEW: Two-Layer Data Validation System**:
  1. `validate_data.py` - Validates JSON against real-time sources (CoinGecko for crypto, Yahoo Finance for stocks/ETFs)
  2. `validate_report.py` - Validates report Python file against JSON (catches stale narrative content)
- **Report Content Validation catches**:
  - Stale dates from previous weeks
  - Wrong price references in narrative
  - **WRONG DIRECTION issues** (e.g., report says +3% but JSON shows -7%)
  - Wrong sector leaders mentioned
  - Stale percentage values
- Added `--auto-fix` flag to automatically update stale prices
- Added `--section` flag to validate specific sections
- Added Step 2.5 to workflow: Validate Data Freshness
- **Critical for template copying** - run before updating narrative!

### v1.4.0 (2026-01-24)
- Added Table of Contents for navigation
- Added Global Markets commentary patterns
- Added complete Ticker Reference tables (Chinese names)
- Added Search/Replace regex patterns
- Added PDF export settings and troubleshooting
- Added version tracking

### v1.3.0
- Added Example Workflow Walkthrough
- Added Strategy Section Templates
- Added US Market Holidays 2026
- Added Quality Checklist

### v1.2.0
- Added Headline Patterns (5 templates)
- Added Narrative Writing Guidelines
- Added Economic Calendar section
- Added Illustration Generation workflow

### v1.1.0
- Added Quick Start Decision Tree
- Added Pre-Flight Checklist
- Expanded Troubleshooting section
- Added CLI Quick Reference

### v1.0.0
- Initial skill with basic workflow
