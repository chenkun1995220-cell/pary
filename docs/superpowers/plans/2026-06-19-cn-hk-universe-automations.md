# A股港股股票池与独立自动化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 接入沪深300、恒生综合大型股和中型股官方成分股，生成统一公司层，并把美股、A股、港股拆分为三个独立 Codex 周任务。

**Architecture:** 市场原始来源和缓存分开，标准输出字段统一。A股读取中证指数公司官方 `000300cons.xls`；港股读取恒生指数公司 `sizeindexes/constituents.do` JSON 中的 HSLI 与 HSMI；三个市场拥有独立脚本、输出目录和自动任务。

**Tech Stack:** Python 3、pandas、xlrd、CSV/JSON、PowerShell、unittest、Codex cron automation

---

### Task 1: 沪深300与港股成分解析

**Files:**
- Create: `regional_universe.py`
- Create: `tests/test_regional_universe.py`
- Create: `requirements.txt`

- [ ] **Step 1: 写失败测试**

```python
def test_normalize_csi300_records_builds_exchange_ticker():
    rows = normalize_csi300_records([{"成分券代码": "600000", "成分券名称": "浦发银行"}])
    assert rows[0]["ticker"] == "600000.SH"

def test_parse_hk_size_payload_combines_large_and_mid_without_duplicates():
    rows = parse_hk_size_payload(payload)
    assert {row["index_name"] for row in rows} == {"HSLI", "HSMI"}
```

- [ ] **Step 2: 运行测试并确认模块缺失**

Run: `python -m unittest tests.test_regional_universe -v`

- [ ] **Step 3: 实现标准字段和两个来源解析器**

```python
OUTPUT_FIELDS = ["market", "ticker", "raw_ticker", "company_name", "industry", "index_name", "currency", "exchange", "enabled"]
```

- [ ] **Step 4: 运行测试并确认通过**

Run: `python -m unittest tests.test_regional_universe -v`

### Task 2: 安全校验与最后有效缓存

**Files:**
- Modify: `regional_universe.py`
- Modify: `tests/test_regional_universe.py`

- [ ] **Step 1: 写失败测试覆盖A股280至320行、港股200至450行、重复代码、缓存回退和无缓存失败**

```python
def test_refresh_market_falls_back_to_valid_cache():
    result = refresh_market_universe("CN", output, cache, failing_fetcher, parser)
    assert result["status"] == "cache_fallback"
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m unittest tests.test_regional_universe -v`

- [ ] **Step 3: 使用临时文件原子替换CSV、源文件和元数据**

缓存路径分别为 `data/cache/csi300` 与 `data/cache/hk_large_mid`。

- [ ] **Step 4: 运行测试并确认通过**

Run: `python -m unittest tests.test_regional_universe -v`

### Task 3: 市场独立运行脚本

**Files:**
- Create: `scripts/run_cn_weekly.ps1`
- Create: `scripts/run_hk_weekly.ps1`
- Create: `tests/test_regional_weekly_scripts.py`
- Modify: `docs/美股每周自动运行说明.md`

- [ ] **Step 1: 写失败测试，要求DryRun不写文件并打印市场、输出和缓存路径**

```python
def test_cn_weekly_dry_run_is_side_effect_free():
    result = run_script("run_cn_weekly.ps1", "-DryRun")
    assert result.returncode == 0
```

- [ ] **Step 2: 运行测试并确认脚本不存在**

Run: `python -m unittest tests.test_regional_weekly_scripts -v`

- [ ] **Step 3: 实现A股和港股刷新、中文摘要和日志**

```powershell
& $Python -B regional_universe.py --market CN --output $Companies --cache-dir $CacheDir
```

- [ ] **Step 4: 运行测试和PowerShell语法检查**

Run: `python -m unittest tests.test_regional_weekly_scripts -v`

### Task 4: 三个独立Codex自动任务

**Files:**
- Update through Codex automation API: 美股、A股、港股三个任务

- [ ] **Step 1: 将现有美股任务保留为周日14:05**
- [ ] **Step 2: 创建A股任务为周日14:25**
- [ ] **Step 3: 创建港股任务为周日14:45**
- [ ] **Step 4: 核验三个任务均为ACTIVE、工作区正确、脚本互不混用**

错开20分钟用于减少网络和本机资源竞争。A股和港股任务在财务适配器完成前只报告股票池刷新与数据准备状态，不输出虚假候选结论。

### Task 5: 真实刷新与回归

**Files:**
- Create at runtime: `data/cache/csi300/*`
- Create at runtime: `data/cache/hk_large_mid/*`
- Create at runtime: `data/samples/cn_universe_companies.csv`
- Create at runtime: `data/samples/hk_universe_companies.csv`

- [ ] **Step 1: 安装并锁定 `xlrd>=2.0.1,<3`**
- [ ] **Step 2: 运行完整测试集和Python编译**
- [ ] **Step 3: 真实刷新两个市场并核对数量、唯一代码和缓存状态**
- [ ] **Step 4: 读取三个Codex任务配置完成最终核验**
