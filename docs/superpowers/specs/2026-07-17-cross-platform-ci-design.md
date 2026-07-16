# 跨平台持续集成设计

## 背景

项目当前在 Windows 本机运行完整单元测试。历史文件并发保护已经增加 Windows `msvcrt` 与 POSIX `fcntl` 两条实现路径，但 POSIX 路径只能通过模拟测试和静态复核验证。仓库尚无 GitHub Actions，因此推送或合并后不会自动检查跨平台回归。

## 目标

新增最小化 GitHub Actions 工作流：Windows 运行仓库全量单元测试，Ubuntu 运行 POSIX 文件锁与工作流契约聚焦测试。工作流只验证代码，不访问市场数据、不运行三市场周任务、不重新评分，也不修改任何正式模型或运行产物。

## 方案

新增 `.github/workflows/test.yml`，采用单个测试作业和按平台区分测试范围的矩阵：

- `windows-latest / full`
- `ubuntu-latest / posix`

每个矩阵任务固定使用 Python 3.12，安装 `requirements.txt` 与 `requirements-dev.txt` 后运行语法检查。Windows 任务设置 UTF-8 环境并提供本机 Codex Python 绝对路径兼容层，然后运行 `python -m unittest discover -s tests`；Ubuntu 任务运行：

```text
python -m unittest tests.test_one_week_forecast_shadow_disposition tests.test_cross_platform_ci_workflow
```

Ubuntu 不执行 Windows PowerShell 包装脚本测试。首次远端全量试运行已证明这些测试依赖 `powershell.exe`、Windows 路径分隔符和本机 Python 绝对路径；把约 60 个包装脚本迁移为跨平台实现属于独立后续项目，不在本轮 CI 优化中混入。

工作流由以下事件触发：

- 向 `main` 分支推送；
- 针对 `main` 分支创建或更新拉取请求；
- 手动触发 `workflow_dispatch`。

同一分支存在更新运行时，取消该分支尚未完成的旧运行，减少重复消耗。工作流设置 `contents: read`，不授予写仓库、发布、部署或密钥读取权限。

## 数据与模型边界

工作流不得调用 `scripts/run_us_universe_weekly.ps1`、`scripts/run_cn_weekly.ps1`、`scripts/run_hk_weekly.ps1` 或任何市场抓取入口。测试必须使用仓库内测试夹具和临时目录，不得把 `outputs` 运行产物作为成功前提，也不得写回候选池、估值结果、模型参数或自动化历史。

依赖安装只读取 `requirements.txt`。工作流不配置 `SEC_USER_AGENT`、行情 API 凭据或其他生产密钥，从环境层面阻止误触生产数据链路。

## 失败处理

- Windows 全量测试或 Ubuntu 聚焦测试任一失败，整个工作流失败。
- Windows 通过但 Ubuntu 失败时，不允许把 POSIX 锁失败归类为可忽略；应读取当前运行日志并定位差异。
- 不在工作流中自动重试测试、自动修改代码或降低测试范围。
- 第三方依赖安装故障保留为明确失败，不使用旧测试结果替代本次运行。

## 测试与验收

实施前先增加一个工作流契约测试，读取 YAML 并验证：

- 触发目标只包含 `main`、拉取请求和手动触发；
- 矩阵同时包含 `windows-latest/full` 与 `ubuntu-latest/posix`；
- 权限为只读；
- 使用 Python 3.12；
- 包含依赖安装、语法检查、Windows 全量 `unittest` 与 Ubuntu POSIX 聚焦测试；
- 不包含三个市场周任务、评分入口、密钥或写权限。

契约测试必须先因工作流缺失而失败，再新增最小工作流使其通过。测试范围调整也必须先让契约失败，再修改工作流转绿。随后运行完整本地测试、YAML 解析检查和 `git diff --check`。推送功能分支后，以 GitHub Actions 的 Windows 全量任务与 Ubuntu POSIX 聚焦任务均成功作为最终验收；如果远端任务失败，读取当前运行日志并修复，不以本地通过代替远端结论。

## 非目标

- 不增加行情抓取或周任务调度；
- 不自动发布报告或产物；
- 不修改候选评分、估值、预测或影子分类逻辑；
- 不引入测试覆盖率门槛、代码格式化工具或依赖升级；
- 不在本轮迁移 Windows PowerShell 包装脚本；
- 不解决强制终止或断电时的多文件崩溃原子性。
