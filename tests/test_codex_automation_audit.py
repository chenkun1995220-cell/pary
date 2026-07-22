import json
import tempfile
import unittest
from pathlib import Path


def write_automation(
    root,
    automation_id,
    name,
    prompt,
    minute,
    model="gpt-5.6-terra",
    kind="cron",
    hour=14,
    target_thread_id="test-thread",
    reasoning_effort="high",
    include_id=True,
    configured_id=None,
    include_version=True,
    version=1,
    include_target=True,
    target_type="project",
    target_project_id="test-project",
    include_cache_guard=True,
    include_fresh_artifact_guard=True,
    include_formal_model_guard=True,
    include_research_only_guard=True,
    include_failure_evidence_guard=True,
    include_network_retry_guard=True,
    include_sec_user_agent=True,
    include_online_first_guard=True,
    include_powershell_entrypoint=True,
):
    path = Path(root) / automation_id / "automation.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    if kind == "cron" and include_cache_guard:
        prompt = f"{prompt}；缓存回退不得视为成功"
    if kind == "cron" and include_fresh_artifact_guard:
        if automation_id == "automation-5":
            prompt = f"{prompt}；不得引用旧结论或旧交付产物"
        else:
            prompt = f"{prompt}；不得把旧产物当作本次结果"
    if kind == "cron" and include_formal_model_guard:
        prompt = f"{prompt}；正式模型不得自动修改"
    if kind == "cron" and include_research_only_guard:
        prompt = f"{prompt}；结果仅供研究"
    if kind == "cron" and include_failure_evidence_guard:
        prompt = f"{prompt}；失败步骤；本次最新日志"
    if kind == "cron" and include_network_retry_guard:
        prompt = f"{prompt}；WinError 10013；完全相同的入口命令；重试一次"
    if kind == "cron" and include_online_first_guard:
        prompt = f"{prompt}；首次执行正式入口；允许网络访问；CodexSandboxOffline"
    if kind == "cron" and include_powershell_entrypoint:
        prompt = f"{prompt}；powershell.exe -NoProfile -ExecutionPolicy Bypass -File"
    if automation_id == "automation" and include_sec_user_agent:
        prompt = f'{prompt} -SecUserAgent "Test test@example.com"'
    lines = []
    if include_version:
        lines.append(f"version = {json.dumps(version)}")
    if include_id:
        lines.append(
            "id = "
            + json.dumps(
                automation_id if configured_id is None else configured_id,
                ensure_ascii=False,
            )
        )
    lines.extend(
        [
            f"kind = {json.dumps(kind)}",
            f"name = {json.dumps(name, ensure_ascii=False)}",
            f"prompt = {json.dumps(prompt, ensure_ascii=False)}",
            'status = "ACTIVE"',
            f'rrule = "FREQ=WEEKLY;INTERVAL=1;BYDAY=SA;BYHOUR={hour};BYMINUTE={minute}"',
        ]
    )
    if kind == "cron":
        lines.extend(
            [
                f'model = "{model}"',
                f'reasoning_effort = "{reasoning_effort}"',
                'execution_environment = "local"',
                'cwds = ["F:\\\\chatgptssd\\\\project2"]',
            ]
        )
        if include_target:
            lines.append(
                "target = { "
                f"type = {json.dumps(target_type)}, "
                f"project_id = {json.dumps(target_project_id)} "
                "}"
            )
    else:
        lines.append(f"target_thread_id = {json.dumps(target_thread_id)}")
    path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8-sig",
    )


def write_acceptance_heartbeat(
    root,
    prompt=None,
    hour=15,
    minute=0,
    include_fresh_artifact_guard=True,
):
    prompt = prompt or (
        "latest_weekly_artifact_consistency.json "
        "latest_extended_shadow_validation_tracker.json "
        "latest_pre_submit_review.json "
        "不要重新运行市场抓取，不要修改正式模型"
    )
    if include_fresh_artifact_guard:
        prompt = f"{prompt}；不得继续引用旧交付"
    write_automation(
        root,
        "automation-2",
        "三市场周交付验收跟进",
        prompt,
        minute,
        kind="heartbeat",
        hour=hour,
    )


class CodexAutomationAuditTests(unittest.TestCase):
    def test_audits_market_crons_and_acceptance_heartbeat_as_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_automation(
                tmp,
                "automation",
                "美股低估公司每周筛选",
                "scripts\\run_us_universe_weekly.ps1 本任务只完成美股周筛，不提前运行三市场统一收口；读取 market_quotes.csv",
                5,
            )
            write_automation(
                tmp,
                "a-300-3",
                "A股沪深300每周筛选",
                "scripts\\run_cn_weekly.ps1 本任务只完成A股周筛，不提前运行三市场统一收口",
                10,
            )
            write_automation(
                tmp,
                "automation-5",
                "港股大中盘每周筛选",
                "scripts\\run_hk_weekly.ps1 -RunPostChecks 调用 scripts\\run_weekly_reporting_bundle.ps1；读取 latest_weekly_artifact_consistency.json、latest_first_one_month_forecast_evaluation_review.json 和 latest_pre_submit_review.json；要求三市场同一自然日",
                30,
                model="gpt-5.6-sol",
            )
            write_acceptance_heartbeat(tmp)

            from codex_automation_audit import audit_automations, render_audit_report

            result = audit_automations(tmp)
            report = render_audit_report(result)

            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["ready_count"], 4)
            self.assertEqual(result["automation_count"], 4)
            self.assertEqual(result["checks"][0]["version"], 1)
            self.assertEqual(result["checks"][2]["id"], "automation-5")
            self.assertEqual(result["checks"][3]["id"], "automation-2")
            self.assertEqual(result["checks"][3]["kind"], "heartbeat")
            self.assertIn("Codex 自动化任务配置审计", report)
            self.assertIn("总体状态：ready", report)
            self.assertIn("automation-5：ready", report)
            self.assertIn("run_weekly_reporting_bundle.ps1", report)
            self.assertIn("latest_weekly_artifact_consistency.json", report)
            self.assertIn("latest_pre_submit_review.json", report)
            self.assertIn("automation-2", report)
            self.assertIn("version: 1", report)
            self.assertIn("latest_extended_shadow_validation_tracker.json", report)
            self.assertIn("周六 15:00", report)
            self.assertEqual(result["checks"][0]["model"], "gpt-5.6-terra")
            self.assertEqual(result["checks"][2]["model"], "gpt-5.6-sol")
            self.assertNotIn("三条任务使用当前支持的 gpt-5.6-terra", report)
            self.assertIn("模型版本允许升级或切换", report)

    def test_audit_requires_a_model_but_does_not_pin_its_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            for automation_id, name, prompt, minute in (
                ("automation", "美股低估公司每周筛选", "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口 market_quotes.csv", 5),
                ("a-300-3", "A股沪深300每周筛选", "scripts\\run_cn_weekly.ps1 不提前运行三市场统一收口", 10),
                ("automation-5", "港股大中盘每周筛选", "scripts\\run_hk_weekly.ps1 -RunPostChecks scripts\\run_weekly_reporting_bundle.ps1 latest_weekly_artifact_consistency.json latest_first_one_month_forecast_evaluation_review.json latest_pre_submit_review.json 同一自然日", 30),
            ):
                write_automation(tmp, automation_id, name, prompt, minute, model="future-compatible-model")
            write_acceptance_heartbeat(tmp)

            from codex_automation_audit import audit_automations

            result = audit_automations(tmp)

            self.assertEqual(result["status"], "ready")

    def test_audit_requires_valid_reasoning_effort_for_market_crons(self):
        for reasoning_effort in ("", "turbo"):
            with self.subTest(reasoning_effort=reasoning_effort), tempfile.TemporaryDirectory() as tmp:
                write_automation(
                    tmp,
                    "automation",
                    "美股低估公司每周筛选",
                    "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口 market_quotes.csv",
                    5,
                    reasoning_effort=reasoning_effort,
                )

                from codex_automation_audit import audit_automations

                result = audit_automations(tmp)
                us_check = result["checks"][0]

                self.assertEqual(us_check["status"], "needs_attention")
                self.assertTrue(
                    any("reasoning_effort" in issue for issue in us_check["issues"])
                )

    def test_audit_requires_valid_project_target_for_market_crons(self):
        cases = (
            ({"include_target": False}, "target.type"),
            ({"target_type": "thread"}, "target.type"),
            ({"target_project_id": "   "}, "target.project_id"),
        )
        for kwargs, expected_issue in cases:
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as tmp:
                write_automation(
                    tmp,
                    "automation",
                    "美股低估公司每周筛选",
                    "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口 market_quotes.csv",
                    5,
                    **kwargs,
                )

                from codex_automation_audit import audit_automations

                result = audit_automations(tmp)
                us_check = result["checks"][0]

                self.assertEqual(us_check["status"], "needs_attention")
                self.assertTrue(
                    any(expected_issue in issue for issue in us_check["issues"])
                )

    def test_audit_requires_matching_string_automation_id(self):
        cases = (
            {"include_id": False},
            {"configured_id": "wrong-id"},
            {"configured_id": 42},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as tmp:
                write_automation(
                    tmp,
                    "automation",
                    "美股低估公司每周筛选",
                    "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口 market_quotes.csv",
                    5,
                    **kwargs,
                )

                from codex_automation_audit import audit_automations

                us_check = audit_automations(tmp)["checks"][0]

                self.assertEqual(us_check["status"], "needs_attention")
                self.assertTrue(
                    any(
                        "id expected automation" in issue
                        for issue in us_check["issues"]
                    )
                )

    def test_audit_requires_supported_integer_automation_version(self):
        cases = (
            {"include_version": False},
            {"version": "1"},
            {"version": True},
            {"version": 2},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as tmp:
                write_automation(
                    tmp,
                    "automation",
                    "美股低估公司每周筛选",
                    "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口 market_quotes.csv",
                    5,
                    **kwargs,
                )

                from codex_automation_audit import audit_automations

                us_check = audit_automations(tmp)["checks"][0]

                self.assertEqual(us_check["status"], "needs_attention")
                self.assertTrue(
                    any(
                        "version expected integer 1" in issue
                        for issue in us_check["issues"]
                    )
                )

    def test_audit_allows_any_nonempty_project_id_and_reports_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_automation(
                tmp,
                "automation",
                "美股低估公司每周筛选",
                "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口 market_quotes.csv",
                5,
                target_project_id="migrated-project",
            )

            from codex_automation_audit import audit_automations, render_audit_report

            result = audit_automations(tmp)
            us_check = result["checks"][0]

            self.assertFalse(
                any("target." in issue for issue in us_check["issues"])
            )
            self.assertEqual(us_check["target_type"], "project")
            self.assertEqual(us_check["target_project_id"], "migrated-project")
            self.assertIn(
                "target: project / migrated-project",
                render_audit_report(result),
            )

    def test_audit_reports_missing_market_cache_fallback_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_automation(
                tmp,
                "automation",
                "美股低估公司每周筛选",
                "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口 market_quotes.csv",
                5,
                include_cache_guard=False,
            )

            from codex_automation_audit import audit_automations

            result = audit_automations(tmp)
            us_check = result["checks"][0]

            self.assertEqual(us_check["status"], "needs_attention")
            self.assertTrue(
                any("缓存回退不得视为成功" in issue for issue in us_check["issues"])
            )

    def test_audit_rejects_pre_submit_relaxation_in_production_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_automation(
                tmp,
                "automation-5",
                "港股大中盘每周筛选",
                "scripts\\run_hk_weekly.ps1 -RunPostChecks -IgnorePreSubmitFailure "
                "scripts\\run_weekly_reporting_bundle.ps1 "
                "latest_weekly_artifact_consistency.json "
                "latest_first_one_month_forecast_evaluation_review.json "
                "latest_pre_submit_review.json 同一自然日",
                30,
            )

            from codex_automation_audit import audit_automations

            result = audit_automations(tmp)
            hk_check = result["checks"][2]

            self.assertEqual(hk_check["status"], "needs_attention")
            self.assertTrue(
                any(
                    "production prompt must not use -IgnorePreSubmitFailure" in issue
                    for issue in hk_check["issues"]
                )
            )

    def test_audit_requires_fresh_artifact_guard_for_each_market_prompt(self):
        cases = (
            (
                "automation",
                "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口 market_quotes.csv",
                5,
                0,
                "不得把旧产物当作本次结果",
            ),
            (
                "a-300-3",
                "scripts\\run_cn_weekly.ps1 不提前运行三市场统一收口",
                10,
                1,
                "不得把旧产物当作本次结果",
            ),
            (
                "automation-5",
                "scripts\\run_hk_weekly.ps1 -RunPostChecks "
                "scripts\\run_weekly_reporting_bundle.ps1 "
                "latest_weekly_artifact_consistency.json "
                "latest_first_one_month_forecast_evaluation_review.json "
                "latest_pre_submit_review.json 同一自然日",
                30,
                2,
                "不得引用旧结论或旧交付产物",
            ),
        )

        for automation_id, prompt, minute, check_index, required_term in cases:
            with self.subTest(automation_id=automation_id), tempfile.TemporaryDirectory() as tmp:
                write_automation(
                    tmp,
                    automation_id,
                    automation_id,
                    prompt,
                    minute,
                    include_fresh_artifact_guard=False,
                )

                from codex_automation_audit import audit_automations

                result = audit_automations(tmp)
                market_check = result["checks"][check_index]

                self.assertEqual(market_check["status"], "needs_attention")
                self.assertTrue(
                    any(required_term in issue for issue in market_check["issues"])
                )

    def test_audit_requires_formal_model_guard_for_each_market_prompt(self):
        cases = (
            (
                "automation",
                "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口 market_quotes.csv",
                5,
                0,
            ),
            (
                "a-300-3",
                "scripts\\run_cn_weekly.ps1 不提前运行三市场统一收口",
                10,
                1,
            ),
            (
                "automation-5",
                "scripts\\run_hk_weekly.ps1 -RunPostChecks "
                "scripts\\run_weekly_reporting_bundle.ps1 "
                "latest_weekly_artifact_consistency.json "
                "latest_first_one_month_forecast_evaluation_review.json "
                "latest_pre_submit_review.json 同一自然日",
                30,
                2,
            ),
        )

        for automation_id, prompt, minute, check_index in cases:
            with self.subTest(automation_id=automation_id), tempfile.TemporaryDirectory() as tmp:
                write_automation(
                    tmp,
                    automation_id,
                    automation_id,
                    prompt,
                    minute,
                    include_formal_model_guard=False,
                )

                from codex_automation_audit import audit_automations

                result = audit_automations(tmp)
                market_check = result["checks"][check_index]

                self.assertEqual(market_check["status"], "needs_attention")
                self.assertTrue(
                    any("正式模型不得自动修改" in issue for issue in market_check["issues"])
                )

    def test_audit_requires_research_only_guard_for_each_market_prompt(self):
        cases = (
            (
                "automation",
                "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口 market_quotes.csv",
                5,
                0,
            ),
            (
                "a-300-3",
                "scripts\\run_cn_weekly.ps1 不提前运行三市场统一收口",
                10,
                1,
            ),
            (
                "automation-5",
                "scripts\\run_hk_weekly.ps1 -RunPostChecks "
                "scripts\\run_weekly_reporting_bundle.ps1 "
                "latest_weekly_artifact_consistency.json "
                "latest_first_one_month_forecast_evaluation_review.json "
                "latest_pre_submit_review.json 同一自然日",
                30,
                2,
            ),
        )

        for automation_id, prompt, minute, check_index in cases:
            with self.subTest(automation_id=automation_id), tempfile.TemporaryDirectory() as tmp:
                write_automation(
                    tmp,
                    automation_id,
                    automation_id,
                    prompt,
                    minute,
                    include_research_only_guard=False,
                )

                from codex_automation_audit import audit_automations

                result = audit_automations(tmp)
                market_check = result["checks"][check_index]

                self.assertEqual(market_check["status"], "needs_attention")
                self.assertTrue(
                    any("结果仅供研究" in issue for issue in market_check["issues"])
                )

    def test_audit_requires_failure_evidence_for_each_market_prompt(self):
        cases = (
            (
                "automation",
                "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口 market_quotes.csv",
                5,
                0,
            ),
            (
                "a-300-3",
                "scripts\\run_cn_weekly.ps1 不提前运行三市场统一收口",
                10,
                1,
            ),
            (
                "automation-5",
                "scripts\\run_hk_weekly.ps1 -RunPostChecks "
                "scripts\\run_weekly_reporting_bundle.ps1 "
                "latest_weekly_artifact_consistency.json "
                "latest_first_one_month_forecast_evaluation_review.json "
                "latest_pre_submit_review.json 同一自然日",
                30,
                2,
            ),
        )

        for automation_id, prompt, minute, check_index in cases:
            with self.subTest(automation_id=automation_id), tempfile.TemporaryDirectory() as tmp:
                write_automation(
                    tmp,
                    automation_id,
                    automation_id,
                    prompt,
                    minute,
                    include_failure_evidence_guard=False,
                )

                from codex_automation_audit import audit_automations

                result = audit_automations(tmp)
                market_check = result["checks"][check_index]

                self.assertEqual(market_check["status"], "needs_attention")
                for required_term in ("失败步骤", "本次最新日志"):
                    self.assertTrue(
                        any(required_term in issue for issue in market_check["issues"])
                    )

    def test_audit_requires_bounded_network_retry_for_each_market_prompt(self):
        cases = (
            (
                "automation",
                "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口 market_quotes.csv",
                5,
                0,
            ),
            (
                "a-300-3",
                "scripts\\run_cn_weekly.ps1 不提前运行三市场统一收口",
                10,
                1,
            ),
            (
                "automation-5",
                "scripts\\run_hk_weekly.ps1 -RunPostChecks "
                "scripts\\run_weekly_reporting_bundle.ps1 "
                "latest_weekly_artifact_consistency.json "
                "latest_first_one_month_forecast_evaluation_review.json "
                "latest_pre_submit_review.json 同一自然日",
                30,
                2,
            ),
        )

        for automation_id, prompt, minute, check_index in cases:
            with self.subTest(automation_id=automation_id), tempfile.TemporaryDirectory() as tmp:
                write_automation(
                    tmp,
                    automation_id,
                    automation_id,
                    prompt,
                    minute,
                    include_network_retry_guard=False,
                )

                from codex_automation_audit import audit_automations

                result = audit_automations(tmp)
                market_check = result["checks"][check_index]

                self.assertEqual(market_check["status"], "needs_attention")
                for required_term in (
                    "WinError 10013",
                    "完全相同的入口命令",
                    "重试一次",
                ):
                    self.assertTrue(
                        any(required_term in issue for issue in market_check["issues"])
                    )

    def test_audit_requires_nonempty_sec_user_agent_for_us_prompt(self):
        prompts = (
            "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口 market_quotes.csv",
            'scripts\\run_us_universe_weekly.ps1 -SecUserAgent "" '
            "不提前运行三市场统一收口 market_quotes.csv",
        )

        for prompt in prompts:
            with self.subTest(prompt=prompt), tempfile.TemporaryDirectory() as tmp:
                write_automation(
                    tmp,
                    "automation",
                    "美股低估公司每周筛选",
                    prompt,
                    5,
                    include_sec_user_agent=False,
                )

                from codex_automation_audit import audit_automations

                result = audit_automations(tmp)
                us_check = result["checks"][0]

                self.assertEqual(us_check["status"], "needs_attention")
                self.assertTrue(
                    any(
                        "non-empty -SecUserAgent" in issue
                        for issue in us_check["issues"]
                    )
                )

    def test_audit_requires_online_first_execution_for_each_market_prompt(self):
        cases = (
            (
                "automation",
                "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口 market_quotes.csv",
                5,
                0,
            ),
            (
                "a-300-3",
                "scripts\\run_cn_weekly.ps1 不提前运行三市场统一收口",
                10,
                1,
            ),
            (
                "automation-5",
                "scripts\\run_hk_weekly.ps1 -RunPostChecks "
                "scripts\\run_weekly_reporting_bundle.ps1 "
                "latest_weekly_artifact_consistency.json "
                "latest_first_one_month_forecast_evaluation_review.json "
                "latest_pre_submit_review.json 同一自然日",
                30,
                2,
            ),
        )

        for automation_id, prompt, minute, check_index in cases:
            with self.subTest(automation_id=automation_id), tempfile.TemporaryDirectory() as tmp:
                write_automation(
                    tmp,
                    automation_id,
                    automation_id,
                    prompt,
                    minute,
                    include_online_first_guard=False,
                )

                from codex_automation_audit import audit_automations

                result = audit_automations(tmp)
                market_check = result["checks"][check_index]

                self.assertEqual(market_check["status"], "needs_attention")
                for required_term in (
                    "首次执行正式入口",
                    "允许网络访问",
                    "CodexSandboxOffline",
                ):
                    self.assertTrue(
                        any(required_term in issue for issue in market_check["issues"])
                    )

    def test_audit_requires_complete_powershell_entrypoint_for_each_market_prompt(self):
        cases = (
            (
                "automation",
                "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口 market_quotes.csv",
                5,
                0,
            ),
            (
                "a-300-3",
                "scripts\\run_cn_weekly.ps1 不提前运行三市场统一收口",
                10,
                1,
            ),
            (
                "automation-5",
                "scripts\\run_hk_weekly.ps1 -RunPostChecks "
                "scripts\\run_weekly_reporting_bundle.ps1 "
                "latest_weekly_artifact_consistency.json "
                "latest_first_one_month_forecast_evaluation_review.json "
                "latest_pre_submit_review.json 同一自然日",
                30,
                2,
            ),
        )

        for automation_id, prompt, minute, check_index in cases:
            with self.subTest(automation_id=automation_id), tempfile.TemporaryDirectory() as tmp:
                write_automation(
                    tmp,
                    automation_id,
                    automation_id,
                    prompt,
                    minute,
                    include_powershell_entrypoint=False,
                )

                from codex_automation_audit import audit_automations

                result = audit_automations(tmp)
                market_check = result["checks"][check_index]

                self.assertEqual(market_check["status"], "needs_attention")
                for required_term in (
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                ):
                    self.assertTrue(
                        any(required_term in issue for issue in market_check["issues"])
                    )

    def test_audit_reports_missing_acceptance_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            for automation_id, name, prompt, minute in (
                ("automation", "US", "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口 market_quotes.csv", 5),
                ("a-300-3", "CN", "scripts\\run_cn_weekly.ps1 不提前运行三市场统一收口", 10),
                ("automation-5", "HK", "scripts\\run_hk_weekly.ps1 -RunPostChecks scripts\\run_weekly_reporting_bundle.ps1 latest_weekly_artifact_consistency.json latest_first_one_month_forecast_evaluation_review.json latest_pre_submit_review.json 同一自然日", 30),
            ):
                write_automation(tmp, automation_id, name, prompt, minute)

            from codex_automation_audit import audit_automations

            result = audit_automations(tmp)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("automation-2", result["missing_automations"])

    def test_audit_requires_fresh_artifact_guard_for_acceptance_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_acceptance_heartbeat(tmp, include_fresh_artifact_guard=False)

            from codex_automation_audit import audit_automations

            result = audit_automations(tmp)
            heartbeat = result["checks"][3]

            self.assertEqual(heartbeat["status"], "needs_attention")
            self.assertTrue(
                any("不得继续引用旧交付" in issue for issue in heartbeat["issues"])
            )

    def test_audit_reports_heartbeat_schedule_and_prompt_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_acceptance_heartbeat(
                tmp,
                prompt=(
                    "latest_weekly_artifact_consistency.json "
                    "latest_pre_submit_review.json "
                    "不要重新运行市场抓取，不要修改正式模型"
                ),
                hour=14,
                minute=55,
            )

            from codex_automation_audit import audit_automations

            result = audit_automations(tmp)
            heartbeat = result["checks"][3]

            self.assertEqual(heartbeat["status"], "needs_attention")
            self.assertTrue(any("BYHOUR=15;BYMINUTE=0" in issue for issue in heartbeat["issues"]))
            self.assertTrue(
                any("latest_extended_shadow_validation_tracker.json" in issue for issue in heartbeat["issues"])
            )

    def test_audit_reports_missing_bundle_and_consistency_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_automation(
                tmp,
                "automation",
                "美股低估公司每周筛选",
                "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口；读取 market_quotes.csv",
                5,
            )
            write_automation(
                tmp,
                "a-300-3",
                "A股沪深300每周筛选",
                "scripts\\run_cn_weekly.ps1 不提前运行三市场统一收口",
                10,
            )
            write_automation(
                tmp,
                "automation-5",
                "港股大中盘每周筛选",
                "scripts\\run_hk_weekly.ps1",
                15,
            )

            from codex_automation_audit import audit_automations, render_audit_report

            result = audit_automations(tmp)
            report = render_audit_report(result)

            self.assertEqual(result["status"], "needs_attention")
            self.assertTrue(
                any(
                    "-RunPostChecks" in issue
                    for issue in result["checks"][2]["issues"]
                )
            )
            self.assertIn("weekly_bundle_contract_missing", report)
            self.assertTrue(
                any(
                    "latest_weekly_artifact_consistency.json" in issue
                    for issue in result["checks"][2]["issues"]
                )
            )

    def test_audit_reports_schedule_and_prompt_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_automation(
                tmp,
                "automation",
                "美股低估公司每周筛选",
                "scripts\\run_us_universe_weekly.ps1",
                6,
            )

            from codex_automation_audit import audit_automations

            result = audit_automations(tmp)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("a-300-3", result["missing_automations"])
            self.assertIn("automation-5", result["missing_automations"])
            self.assertIn("rrule", result["checks"][0]["issues"][0])
            self.assertTrue(any("不提前运行三市场统一收口" in issue for issue in result["checks"][0]["issues"]))

    def test_audit_allows_model_change_but_reports_premature_postchecks(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_automation(
                tmp,
                "automation",
                "美股标普500每周筛选",
                "scripts\\run_us_universe_weekly.ps1 -RunPostChecks 不提前运行三市场统一收口；读取 market_quotes.csv",
                5,
                model="gpt-5.5",
            )

            from codex_automation_audit import audit_automations

            result = audit_automations(tmp)
            issues = result["checks"][0]["issues"]

            self.assertFalse(any("model expected" in issue for issue in issues))
            self.assertTrue(any("must not run -RunPostChecks" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
