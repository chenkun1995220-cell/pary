# 全分支终审修复报告

## 范围与提交

- 分支：`codex/action-policy-propagation`
- 终审基线：`a9edcb0`
- 修复提交：`7b69c21dfb6d5043b9f745f8ab707ba4ac39688e`（`fix: harden action policy validation`）
- 写入边界：仅修改共享行动策略契约、提交前复核、三份指定测试，并新增本报告。
- 未修改模型、抓取逻辑、正式产物或业务文档。

## TDD 红灯证据

先新增全部回归测试，保持生产代码不变，然后运行：

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_action_policy_contract tests.test_pre_submit_review tests.test_weekly_conclusion_report
```

原始结果摘要：

```text
Ran 237 tests in 8.794s
FAILED (failures=8, errors=4)
```

失败与 findings 对应如下：

- `1.5`、`1.9` 被 `int(value)` 截断为 `1`，共享解析测试失败。
- `float("inf")`、`float("-inf")` 和 `1e309` 触发 `OverflowError: cannot convert float infinity to integer`。
- 非规范但原先可被 `int()` 接受的 `" 1 "`、`"1_0"` 未被拒绝。
- automation_check 的 `True`、`1.5`、`1.9` 仍返回 `ready`；无穷值触发未捕获异常。
- 一致性六项映射中的 `True` 通过原生 `True == 1` 比较，未产生 `weekly_artifact_consistency_action_policy_contract_invalid`。
- weekly_action_items 缺少版本且携带旧行动的独立回归在红灯批次中已通过，确认现有结论层门禁正确，本轮补齐专门护栏即可。

## 最小修复

- `action_policy_contract.py`：拒绝 bool、非整数 float、无穷/溢出值、非 ASCII 或非规范整数字符串；保留整数、整数值 float 和明确带符号整数字符串；捕获 `TypeError`、`ValueError`、`OverflowError`。
- `pre_submit_review.py`：automation_check 改为复用 `_action_policy_version_reasons()`；解析为 `None` 精确归类 missing，成功解析但非当前版本归类 mismatch。
- `pre_submit_review.py`：一致性六项版本映射逐项调用共享 `action_policy_version()`，阻断 `True == 1` 及小数绕过。
- `tests/test_weekly_conclusion_report.py`：覆盖 weekly_action_items 缺少 `action_policy_version` 且含旧行动时，状态为 `needs_attention`、顶层版本为 `None`、仅保留 `review_inputs`。

## 绿灯验证

1. 指定覆盖模块：

   ```powershell
   & 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_action_policy_contract tests.test_pre_submit_review tests.test_weekly_conclusion_report
   ```

   结果：`Ran 237 tests in 8.864s`，`OK`。

2. 完整相关套件（原 360 项加本轮 6 个新测试）：

   ```powershell
   & 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_action_policy_contract tests.test_automation_self_analysis tests.test_weekly_action_items tests.test_weekly_ops_check tests.test_weekly_conclusion_report tests.test_weekly_delivery_check tests.test_weekly_artifact_consistency tests.test_pre_submit_review
   ```

   结果：`Ran 366 tests in 10.495s`，`OK`。

3. 全量测试：

   ```powershell
   & 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
   ```

   结果：`Ran 980 tests in 33.460s`，`OK`。

4. 静态编译：

   ```powershell
   & 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile action_policy_contract.py automation_self_analysis.py weekly_action_items.py weekly_ops_check.py weekly_conclusion_report.py weekly_delivery_check.py weekly_artifact_consistency.py pre_submit_review.py
   ```

   结果：退出码 `0`，无输出。

5. 空白错误检查：`git diff --check` 与 `git diff --cached --check` 均退出码 `0`；仅出现 Git 的 LF/CRLF 行尾转换提示，无空白错误。

## 自审

- findings 1：共享解析器边界、异常捕获及兼容行为均有直接单元测试。
- findings 2：automation_check 的 missing/mismatch 精确分类和一致性六项映射均有端到端 pre-submit 回归；输出状态明确为 `needs_attention`。
- findings 3：缺版本 weekly_action_items 不复用旧行动，断言覆盖状态、顶层版本、警告和最终行动列表。
- 改动未扩展到通用 `_int_value` 的其他业务字段，避免无关行为变化。
- 整数值 float（如 `1.0`）继续接受，因为 finding 明确要求拒绝“非整数 float”；字符串只接受无空白、无分隔符、ASCII 数字及可选前导正负号。
- `git diff --name-only` 在修复提交前仅包含五个允许的代码/测试文件；报告为唯一后续新增文件。

## 变更文件

- `action_policy_contract.py`
- `pre_submit_review.py`
- `tests/test_action_policy_contract.py`
- `tests/test_pre_submit_review.py`
- `tests/test_weekly_conclusion_report.py`
- `.superpowers/sdd/final-review-fix-report.md`
