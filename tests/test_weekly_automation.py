import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class WeeklyAutomationTests(unittest.TestCase):
    def test_weekly_reporting_bundle_is_fail_closed_for_post_check_failures(self):
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertNotIn("if (-not $Strict)", bundle)
        self.assertIn('throw "Step $label failed with exit code $exitCode."', bundle)
        for script_name in (
            "run_us_universe_weekly.ps1",
            "run_cn_weekly.ps1",
            "run_hk_weekly.ps1",
        ):
            script = (PROJECT_ROOT / "scripts" / script_name).read_text(
                encoding="utf-8-sig"
            )
            self.assertNotIn("-IgnorePreSubmitFailure", script)

    def test_weekly_reporting_bundle_stops_after_first_failed_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "scripts"
            scripts.mkdir(parents=True)
            (scripts / "run_self_analysis.ps1").write_text(
                "Write-Error 'intentional failure'\nexit 7\n",
                encoding="utf-8-sig",
            )

            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1"),
                    "-ProjectRoot",
                    str(root),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            output = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn("run_self_analysis", output)
            self.assertIn("Step run_self_analysis failed with exit code 7", output)
            self.assertNotIn("run_data_health_review", output)

    def test_market_weekly_summaries_include_run_start_time(self):
        scripts = [
            PROJECT_ROOT / "scripts" / "run_us_universe_weekly.ps1",
            PROJECT_ROOT / "scripts" / "run_cn_weekly.ps1",
            PROJECT_ROOT / "scripts" / "run_hk_weekly.ps1",
        ]

        for path in scripts:
            script = path.read_text(encoding="utf-8-sig")
            with self.subTest(script=path.name):
                self.assertIn(
                    '$runStartedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"',
                    script,
                )
                self.assertIn('"- Run start time: $runStartedAt"', script)
                self.assertGreater(
                    script.index("$runStartedAt = Get-Date"),
                    script.index("if ($DryRun)"),
                )

    def test_market_weekly_scripts_persist_failure_reason_to_run_log(self):
        scripts = [
            PROJECT_ROOT / "scripts" / "run_us_universe_weekly.ps1",
            PROJECT_ROOT / "scripts" / "run_cn_weekly.ps1",
            PROJECT_ROOT / "scripts" / "run_hk_weekly.ps1",
        ]

        for path in scripts:
            script = path.read_text(encoding="utf-8-sig")
            with self.subTest(script=path.name):
                self.assertIn('$logPath = ""', script)
                self.assertIn("catch {", script)
                self.assertIn('"Pipeline status: failed"', script)
                self.assertIn('"Failure: $($_.Exception.Message)"', script)
                self.assertIn("Add-Content -LiteralPath $logPath", script)

    def test_market_weekly_scripts_reject_constituent_cache_fallback(self):
        expectations = {
            "run_us_universe_weekly.ps1": "US constituent refresh must be online",
            "run_cn_weekly.ps1": "CN constituent refresh must be online",
            "run_hk_weekly.ps1": "HK constituent refresh must be online",
        }

        for script_name, message in expectations.items():
            script = (PROJECT_ROOT / "scripts" / script_name).read_text(
                encoding="utf-8-sig"
            )
            with self.subTest(script=script_name):
                self.assertIn('$refreshMetadata.status -ne "online"', script)
                self.assertIn(message, script)

    def test_market_weekly_scripts_reject_price_history_cache_fallbacks(self):
        for script_name in (
            "run_us_universe_weekly.ps1",
            "run_cn_weekly.ps1",
            "run_hk_weekly.ps1",
        ):
            script = (PROJECT_ROOT / "scripts" / script_name).read_text(
                encoding="utf-8-sig"
            )
            with self.subTest(script=script_name):
                self.assertEqual(script.count("candidate_price_history.py"), 3)
                self.assertEqual(script.count("--fail-on-cache-fallback"), 3)
                self.assertEqual(script.count("--maximum-latest-age-days 8"), 3)

    def test_weekly_delivery_streak_wrapper_and_bundle_tail_order(self):
        wrapper = (
            PROJECT_ROOT / "scripts" / "run_weekly_delivery_streak_review.ps1"
        ).read_text(encoding="utf-8-sig")
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("weekly_delivery_streak_review.py", wrapper)
        self.assertIn("latest_weekly_delivery_streak_review.json", wrapper)
        self.assertIn("weekly_delivery_streak_history.jsonl", wrapper)
        ordered_labels = [
            "run_weekly_artifact_consistency",
            "show_weekly_delivery_history",
            "run_pre_submit_review_for_streak",
            "run_weekly_delivery_streak_review",
            "refresh_medium_term_goal_after_delivery_streak",
            "refresh_model_handoff_after_delivery_streak",
            "run_pre_submit_review_final",
            "show_development_closeout",
        ]
        positions = [bundle.index(f'Label = "{label}"') for label in ordered_labels]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn('Label = "run_medium_term_goal_review"', bundle)
        self.assertNotIn('Label = "run_model_handoff_review"', bundle)

    def test_weekly_bundle_runs_candidate_risk_resolution_after_research_review(self):
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("run_candidate_risk_resolution_review.ps1", bundle)
        self.assertLess(
            bundle.index("run_candidate_risk_priority_research_review.ps1"),
            bundle.index("run_candidate_risk_resolution_review.ps1"),
        )
        self.assertLess(
            bundle.index("run_candidate_risk_resolution_review.ps1"),
            bundle.index("run_forecast_performance_review.ps1"),
        )

    def test_weekly_bundle_excludes_closed_historical_evidence_pipeline(self):
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        closed_steps = [
            "run_membership_evidence_import_plan",
            "run_membership_evidence_supplement_queue",
            "run_membership_evidence_supplement_batch",
            "run_membership_evidence_source_intake_status",
            "run_membership_evidence_import_plan_from_verified_intake",
            "run_sp500_official_export_probe",
            "run_sp500_verified_source_plan",
            "run_membership_evidence_apply_preview",
            "run_membership_evidence_apply_confirmation_status",
            "run_membership_evidence_approved_apply_plan",
        ]
        for step in closed_steps:
            self.assertNotIn(step, bundle)

        self.assertIn("run_sp500_current_membership_sources", bundle)
        self.assertIn("run_backtest_evidence_review", bundle)
        self.assertLess(
            bundle.index("run_weekly_delivery_check.ps1"),
            bundle.index("run_weekly_artifact_consistency.ps1"),
        )
        self.assertLess(
            bundle.index("run_weekly_artifact_consistency.ps1"),
            bundle.index("run_pre_submit_review.ps1"),
        )

    def test_orchestrator_summary_includes_universe_refresh_status(self):
        script = (PROJECT_ROOT / "scripts" / "run_us_universe_weekly.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn('$Quotes = Join-Path $OutputRoot "market_quotes.csv"', script)
        self.assertIn('"-NoQuoteCache"', script)
        self.assertNotIn('data\\samples\\us_universe_quotes.csv', script)
        self.assertIn("Quote snapshot policy: runtime_output_only", script)
        self.assertIn("Quote snapshot file", script)
        self.assertIn("Quote snapshot rows", script)
        self.assertIn("Quote date min", script)
        self.assertIn("Quote date max", script)
        self.assertIn("Quote snapshot sha256", script)
        self.assertIn("sp500_refresh_metadata.json", script)
        self.assertIn("Universe count", script)
        self.assertIn("Constituent refresh status", script)
        self.assertIn("candidate_price_history.py", script)
        self.assertIn("candidate_valuation.py", script)
        self.assertIn("valuation_targets.csv", script)
        self.assertIn("valuation_trend_v1", script)
        self.assertIn("forecast_tracker.py", script)
        self.assertIn("model_audit.py", script)
        self.assertIn("tracking_snapshot.csv", script)
        self.assertIn("forecast_evaluations.csv", script)
        self.assertIn("model_audit.md", script)
        self.assertIn("share_override_audit.md", script)
        self.assertIn("--quote-gaps", script)
        self.assertIn("--data-quality-issues", script)
        self.assertIn("--share-override-audit", script)
        self.assertIn("investment_summary.py", script)
        self.assertIn("latest_investment_summary.md", script)
        self.assertIn('$investmentSummaryPath = Join-Path $OutputRoot "latest_investment_summary.md"', script)
        self.assertIn('$summaryPath = Join-Path $OutputRoot "latest_run_summary.md"', script)
        self.assertNotIn('$investmentSummaryPath = Join-Path $AutomationRoot "latest_investment_summary.md"', script)
        self.assertIn("data_health_history.py", script)
        self.assertIn("data_health_history.csv", script)
        self.assertIn("data_health_history.md", script)
        self.assertIn('--candidates (Join-Path $OutputRoot "forecast_history.csv")', script)

    def test_orchestrator_dry_run_prints_ordered_pipeline_without_writing_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "weekly_output"
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "scripts\\run_us_universe_weekly.ps1",
                    "-SecUserAgent",
                    "Test test@example.com",
                    "-OutputRoot",
                    str(output_root),
                    "-DryRun",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            expected_steps = [
                "1/10 Refresh S&P 500 constituents",
                "2/10 Build US universe",
                "3/10 Fill market quotes",
                "4/10 Run screening",
                "5/10 Generate research packs",
                "6/10 Fetch candidate price history",
                "7/10 Generate valuation targets",
                "8/10 Fetch benchmark history",
                "9/10 Track forecast performance",
                "10/10 Audit forecast model",
                "11/11 Generate investment summary",
            ]
            positions = [output.index(step) for step in expected_steps]
            self.assertEqual(positions, sorted(positions))
            self.assertIn(str(output_root), output)
            self.assertFalse(output_root.exists())

    def test_orchestrator_dry_run_with_post_checks_prints_closure_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "weekly_output"
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "scripts\\run_us_universe_weekly.ps1",
                    "-SecUserAgent",
                    "Test test@example.com",
                    "-OutputRoot",
                    str(output_root),
                    "-RunPostChecks",
                    "-DryRun",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("run_weekly_reporting_bundle.ps1", output)
            self.assertIn("DryRun: no files or network requests were created.", output)
            self.assertFalse(output_root.exists())

    def test_weekly_reporting_bundle_can_use_sp500_official_csv_inbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_file = Path(tmp) / "official_constituents.csv"
            source_file.write_text("Symbol,Security\nABT,Abbott Laboratories\n", encoding="utf-8")

            result = subprocess.run(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "scripts\\run_weekly_reporting_bundle.ps1",
                    "-ProjectRoot",
                    str(PROJECT_ROOT),
                    "-Sp500CurrentMembershipSourceFile",
                    str(source_file),
                    "-DryRun",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("Sp500CurrentMembershipSourceFile: " + str(source_file), output)
            self.assertIn("DryRun: would validate and import S&P 500 current membership source file", output)
            self.assertIn("run_sp500_current_membership_sources", output)
            self.assertIn("check_sp500_current_membership_source_inbox", output)

    def test_weekly_reporting_bundle_checks_sp500_inbox_before_pre_submit(self):
        script = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("check_sp500_current_membership_source_inbox.ps1", script)
        self.assertLess(
            script.index("run_sp500_current_membership_sources.ps1"),
            script.index("check_sp500_current_membership_source_inbox.ps1"),
        )
        self.assertLess(
            script.index("check_sp500_current_membership_source_inbox.ps1"),
            script.index("run_pre_submit_review.ps1"),
        )

    def test_weekly_reporting_bundle_passes_user_agent_to_sp500_source_step(self):
        script = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("[string]$UserAgent = $env:SEC_USER_AGENT", script)
        self.assertIn('"UserAgent: $UserAgent"', script)
        self.assertIn('"-UserAgent",', script)
        self.assertIn("$UserAgent", script)

    def test_task_registration_what_if_prints_schedule_and_orchestrator(self):
        result = subprocess.run(
            [
                "powershell.exe",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "scripts\\register_us_universe_weekly_task.ps1",
                "-TaskName",
                "StockScreeningTest",
                "-DayOfWeek",
                "Saturday",
                "-At",
                "09:00",
                "-SecUserAgent",
                "Test test@example.com",
                "-WhatIf",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            errors="replace",
            capture_output=True,
            timeout=30,
        )

        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("StockScreeningTest", output)
        self.assertIn("Saturday", output)
        self.assertIn("09:00", output)
        self.assertIn("run_us_universe_weekly.ps1", output)

    def test_point_in_time_backtest_script_static_contract(self):
        script = (PROJECT_ROOT / "scripts" / "run_us_point_in_time_backtest.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("historical_sp500.py", script)
        self.assertIn("backtest_membership_inputs.py", script)
        self.assertIn("backtest_sec_cache.py", script)
        self.assertIn("backtest_price_inputs.py", script)
        self.assertIn("us_weekly_replay.py", script)
        self.assertIn("shadow_backtest.py", script)
        self.assertIn("-PilotWeeks 8", script)
        self.assertIn("historical_membership.csv", script)
        self.assertIn("replay_manifest.csv", script)
        self.assertIn("backtest_forecasts.csv", script)
        self.assertIn("backtest_evaluations.csv", script)
        self.assertIn("model_comparison.csv", script)
        self.assertIn("backtest_report.md", script)
        self.assertIn("data_leakage_audit.md", script)
        self.assertIn("checkpoint.json", script)
        self.assertIn("FullRun", script)
        self.assertIn("MaxCompanies", script)
        self.assertIn("PilotWindow", script)
        self.assertIn("--pilot-window", script)
        self.assertIn("--max-companies", script)
        self.assertIn("us_sp500_membership_evidence.csv", script)
        self.assertIn("EvidencePack", script)
        self.assertIn("--evidence-pack", script)
        self.assertIn("us_sp500_current_membership_sources.csv", script)
        self.assertIn("CurrentSourcePack", script)
        self.assertIn("--current-source-pack", script)
        self.assertIn("evidence_pack_newer", script)
        self.assertIn("current_source_pack_newer", script)
        self.assertIn("universe_config_newer", script)
        self.assertIn("membership_newer", script)
        self.assertIn("benchmark_config_newer", script)
        self.assertIn("Test-CsvHasDataRows", script)
        self.assertIn("Length -le 0", script)
        self.assertIn("CIK*.json", script)
        self.assertIn("latest_backtest_summary.md", script)
        self.assertIn("BacktestSummary", script)
        self.assertIn("backtest_membership_evidence_gaps.py", script)
        self.assertIn("latest_membership_evidence_gaps.csv", script)
        self.assertIn("latest_membership_evidence_gaps.md", script)
        self.assertIn("latest_membership_evidence_gaps.json", script)
        self.assertIn("Membership evidence verified", script)
        self.assertIn("Weak evidence rows", script)
        self.assertIn("Evidence status", script)
        self.assertIn("Weak evidence weeks", script)
        self.assertIn("Evidence next action", script)

    def test_point_in_time_backtest_dry_run_prints_ordered_pipeline_without_writing_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "backtest_output"
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "scripts\\run_us_point_in_time_backtest.ps1",
                    "-SecUserAgent",
                    "Test test@example.com",
                    "-OutputRoot",
                    str(output_root),
                    "-PilotWeeks",
                    "8",
                    "-DryRun",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            expected_steps = [
                "1/8 Build historical S&P 500 membership",
                "2/8 Load point-in-time SEC facts",
                "3/8 Prepare historical prices",
                "4/8 Replay weekly screening",
                "5/8 Write replay manifest and checkpoint",
                "6/8 Evaluate backtest forecasts",
                "7/8 Run rolling shadow comparison",
                "8/8 Write backtest report",
            ]
            positions = [output.index(step) for step in expected_steps]
            self.assertEqual(positions, sorted(positions))
            self.assertIn(str(output_root), output)
            self.assertIn("PilotWeeks: 8", output)
            self.assertIn("PilotWindow: latest", output)
            self.assertFalse(output_root.exists())

    def test_point_in_time_backtest_non_dry_run_requires_sec_user_agent_before_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "backtest_output"
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "scripts\\run_us_point_in_time_backtest.ps1",
                    "-OutputRoot",
                    str(output_root),
                    "-PilotWeeks",
                    "8",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            output = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn("SEC_USER_AGENT is required", output)
            self.assertNotIn("Running: 1/8 Build historical S&P 500 membership", output)
            self.assertNotIn("Point-in-time backtest completed", output)

    def test_point_in_time_backtest_docs_describe_run_modes_and_limits(self):
        doc = (PROJECT_ROOT / "docs" / "美股每周自动运行说明.md").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("run_us_point_in_time_backtest.ps1", doc)
        self.assertIn("-PilotWeeks 8", doc)
        self.assertIn("-FullRun", doc)
        self.assertIn("outputs/backtests/us_3y_weekly", doc)
        self.assertIn("outputs/automation/latest_backtest_summary.md", doc)
        self.assertIn("outputs/automation/latest_membership_evidence_gaps.csv", doc)
        self.assertIn("outputs/automation/latest_membership_evidence_gaps.md", doc)
        self.assertIn("outputs/automation/latest_membership_evidence_gaps.json", doc)
        self.assertIn("run_sp500_current_membership_sources.ps1", doc)
        self.assertIn("latest_sp500_current_membership_sources.md", doc)
        self.assertIn("us_sp500_current_membership_sources.csv", doc)
        self.assertIn("run_membership_evidence_apply_preview.ps1", doc)
        self.assertIn("latest_membership_evidence_apply_preview.json", doc)
        self.assertIn("latest_membership_evidence_apply_preview.md", doc)
        self.assertIn("sp500_historical_evidence_policy.json", doc)
        self.assertIn("evidence_ceiling_confirmed", doc)
        self.assertIn("limited_verified_only", doc)
        self.assertIn("maintain_limited_backtest", doc)
        self.assertIn("仅保留为人工调查工具", doc)
        self.assertIn("不再进入每周固定链路", doc)
        self.assertIn("data_leakage_audit.md", doc)
        self.assertIn("us_sp500_membership_evidence.csv", doc)
        self.assertIn("Evidence status", doc)
        self.assertIn("Weak evidence weeks", doc)
        self.assertIn("Evidence next action", doc)
        self.assertIn("effective_date, added_ticker, removed_ticker", doc)
        self.assertIn("S&P Global", doc)
        self.assertIn("inputs/sp500_current_membership/official_constituents.csv", doc)
        self.assertIn("Sp500CurrentMembershipSourceFile", doc)
        self.assertIn("source_file_inbox_size_bytes", doc)
        self.assertIn("source_file_inbox_sha256", doc)
        self.assertIn("source_file_inbox_modified_at", doc)
        self.assertIn("source_file_inbox_size_bytes: 当前值", doc)
        self.assertIn("source_file_inbox_sha256: 当前值或 none", doc)
        self.assertIn("source_file_inbox_modified_at: 当前值或 none", doc)
        self.assertIn("不得自动升级正式模型", doc)

        evidence_doc = (PROJECT_ROOT / "docs" / "回测成分证据补强队列.md").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("evidence_ceiling_confirmed", evidence_doc)
        self.assertIn("limited_verified_only", evidence_doc)
        self.assertIn("membership_evidence_action_required_count=0", evidence_doc)
        self.assertIn("maintain_limited_backtest", evidence_doc)
        self.assertIn("当前成分股交叉校验仍按周运行", evidence_doc)

    def test_self_analysis_docs_describe_summary_entrypoint(self):
        doc = (PROJECT_ROOT / "docs" / "美股每周自动运行说明.md").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("run_self_analysis.ps1", doc)
        self.assertIn("show_automation_check.ps1", doc)
        self.assertIn("audit_codex_automations.ps1", doc)
        self.assertIn("run_weekly_ops_check.ps1", doc)
        self.assertIn("show_weekly_ops_history.ps1", doc)
        self.assertIn("show_weekly_delivery_history.ps1", doc)
        self.assertIn("show_weekly_action_items.ps1", doc)
        self.assertIn("outputs/automation/latest_self_analysis.md", doc)
        self.assertIn("outputs/automation/latest_manual_review_queue.csv", doc)
        self.assertIn("outputs/automation/manual_review_queue_history.csv", doc)
        self.assertIn("outputs/automation/manual_review_repeats.csv", doc)
        self.assertIn("outputs/automation/data_quality_score_history.csv", doc)
        self.assertIn("outputs/automation/latest_self_analysis_manifest.json", doc)
        self.assertIn("outputs/automation/latest_automation_check.json", doc)
        self.assertIn("outputs/automation/latest_weekly_action_items.json", doc)
        self.assertIn("outputs/automation/latest_weekly_action_items.md", doc)
        self.assertIn("outputs/automation/latest_weekly_ops_check.json", doc)
        self.assertIn("outputs/automation/weekly_ops_check_history.jsonl", doc)
        self.assertIn("outputs/automation/latest_weekly_ops_history_summary.json", doc)
        self.assertIn("outputs/automation/latest_weekly_ops_history_report.md", doc)
        self.assertIn("raw_history_count", doc)
        self.assertIn("按 `as_of_date` 取最后一条记录", doc)
        self.assertIn("automation_check_report.py", doc)
        self.assertIn("codex_automation_audit.py", doc)
        self.assertIn("weekly_ops_check.py", doc)
        self.assertIn("weekly_ops_history_report.py", doc)
        self.assertIn("weekly_action_items.py", doc)
        self.assertIn("manifest_schema", doc)
        self.assertIn("manifest_version", doc)
        self.assertIn("review_status", doc)
        self.assertIn("recommended_next_action", doc)
        self.assertIn("automation_status", doc)
        self.assertIn("automation_recommended_action", doc)
        self.assertIn("automation_priority_actions", doc)
        self.assertIn("weekly_ops_history_status", doc)
        self.assertIn("weekly_ops_history_recommended_action", doc)
        self.assertIn("weekly_delivery_history_status", doc)
        self.assertIn("weekly_delivery_history_recommended_action", doc)
        self.assertIn("weekly_delivery_action_items_actual_count", doc)
        self.assertIn("weekly_delivery_action_items_actual_count_delta", doc)
        self.assertIn("weekly_delivery_action_items_actual_count_trend", doc)
        self.assertIn("review_manual_review_backlog", doc)
        self.assertIn("review_delivery_health_issues", doc)
        self.assertIn("reduce_weekly_action_backlog", doc)
        self.assertIn("backlog_reduction_plan", doc)
        self.assertIn("处理人工复核积压", doc)
        self.assertIn("复查最终交付健康提示", doc)
        self.assertIn("每周人工处理清单", doc)
        self.assertIn("weekly_delivery_history_report.py", doc)
        self.assertIn("recurring_health_reasons", doc)
        self.assertIn("latest_action_items_status", doc)
        self.assertIn("latest_action_items_freshness_status", doc)
        self.assertIn("latest_action_items_count", doc)
        self.assertIn("action_items_ready_count", doc)
        self.assertIn("action_items_problem_count", doc)
        self.assertIn("recurring_action_items_issues", doc)
        self.assertIn("manifest 结构校验", doc)
        self.assertIn("三市场摘要均为 `ready`", doc)
        self.assertIn("markets", doc)
        self.assertIn("model_audit_status", doc)
        self.assertIn("model_audit_recommended_action", doc)
        self.assertIn("backtest_status", doc)
        self.assertIn("backtest_recommended_action", doc)
        self.assertIn("health", doc)
        self.assertIn("data_health_status", doc)
        self.assertIn("data_health_recommended_action", doc)
        self.assertIn("data_quality_summary", doc)
        self.assertIn("data_quality_score", doc)
        self.assertIn("data_quality_status", doc)
        self.assertIn("data_quality_history", doc)
        self.assertIn("数据质量评分", doc)
        self.assertIn("数据质量历史", doc)
        self.assertIn("candidate_review_status", doc)
        self.assertIn("candidate_review_recommended_action", doc)
        self.assertIn("as_of_date", doc)
        self.assertIn("历史重复项", doc)
        self.assertIn("自我分析摘要", doc)
        self.assertIn("latest_investment_summary.md", doc)
        self.assertIn("data_health_history.csv", doc)
        self.assertIn("review_category", doc)
        self.assertIn("估值复核分类", doc)
        self.assertIn("non_positive_metric` 不再单独触发 `review_data_health", doc)
        self.assertIn("valuation_review_items.csv", doc)
        self.assertIn("估值复核清单", doc)
        self.assertIn("估值复核样例", doc)
        self.assertIn("人工复核队列", doc)
        self.assertIn("优先级序号", doc)
        self.assertIn("accepted` 和 `rejected` 会从下一次自我分析队列中移除", doc)
        self.assertIn("needs_more_data` 会继续保留在队列中", doc)
        self.assertIn("suggested_decision_status", doc)
        self.assertIn("suggested_decision_note", doc)
        self.assertIn("候选风险说明", doc)
        self.assertIn("候选解释摘要", doc)
        self.assertIn("候选结论质量检查", doc)
        self.assertIn("one_week_expected_direction", doc)
        self.assertIn("one_month_expected_direction", doc)
        self.assertIn("forecast_performance", doc)
        self.assertIn("forecast_performance_status", doc)
        self.assertIn("forecast_performance_recommended_action", doc)
        self.assertIn("1周成熟评估", doc)
        self.assertIn("prediction_unavailable", doc)
        self.assertIn("review_data_quality_score", doc)
        self.assertIn("review_data_quality_trend", doc)
        self.assertIn("review_forecast_performance", doc)
        self.assertIn("方向命中率", doc)
        self.assertIn("平均超额收益", doc)
        self.assertIn("预测后1、4、12、26、52周", doc)
        self.assertIn("1周成熟评估", doc)
        self.assertIn("1个月成熟评估", doc)
        self.assertIn("预测字段缺失未评估", doc)

    def test_weekly_conclusion_report_documented(self):
        doc = (PROJECT_ROOT / "docs" / "美股每周自动运行说明.md").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("scripts\\show_weekly_conclusion.ps1", doc)
        self.assertIn("scripts\\run_weekly_delivery_check.ps1", doc)
        self.assertIn("outputs/automation/latest_weekly_conclusion.md", doc)
        self.assertIn("outputs/automation/latest_weekly_conclusion.json", doc)
        self.assertIn("outputs/automation/latest_weekly_delivery_check.json", doc)
        self.assertIn("outputs/automation/weekly_delivery_check_history.jsonl", doc)
        self.assertIn("outputs/automation/latest_weekly_delivery_history_summary.json", doc)
        self.assertIn("outputs/automation/latest_weekly_delivery_history_report.md", doc)
        self.assertIn("最终交付历史状态", doc)
        self.assertIn("overall_health", doc)
        self.assertIn("data_quality_status", doc)
        self.assertIn("data_quality_score", doc)
        self.assertIn("data_quality_history_status", doc)
        self.assertIn("review_data_quality_score", doc)
        self.assertIn("review_data_quality_trend", doc)
        self.assertIn("data_quality_history:manual_review_needed", doc)
        self.assertIn("forecast_performance_status", doc)
        self.assertIn("forecast_performance", doc)
        self.assertIn("review_forecast_performance", doc)
        self.assertIn("forecast_performance:performance_review_needed", doc)
        self.assertIn("候选行动分层", doc)
        self.assertIn("1周/1个月走势", doc)
        self.assertIn("不改变候选池排序和正式评分模型", doc)
        self.assertIn("action_items_status", doc)
        self.assertIn("action_items_freshness_status", doc)
        self.assertIn("action_items_count", doc)
        self.assertIn("conclusion_signal_status", doc)
        self.assertIn("missing_conclusion_signals", doc)
        self.assertIn("recurring_missing_conclusion_signals", doc)
        self.assertIn("conclusion_signal_problem_count", doc)
        self.assertIn("latest_weekly_action_items.json", doc)
        self.assertIn("latest_weekly_action_items.md", doc)
        self.assertIn("conclusion_health_needs_fix", doc)
        self.assertIn("不重新抓取行情", doc)
        self.assertIn("不构成投资建议", doc)

    def test_self_analysis_script_static_contract(self):
        script = (PROJECT_ROOT / "scripts" / "run_self_analysis.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("automation_self_analysis.py", script)
        self.assertIn("latest_self_analysis.md", script)
        self.assertIn("latest_manual_review_queue.csv", script)
        self.assertIn("manual_review_queue_history.csv", script)
        self.assertIn("manual_review_repeats.csv", script)
        self.assertIn("latest_self_analysis_manifest.json", script)
        self.assertIn("latest_automation_check.json", script)
        self.assertIn("--validate-manifest", script)
        self.assertIn("--require-market-ready", script)
        self.assertIn("manifest validation failed", script)
        self.assertIn("data_health_history", script)
        self.assertIn("latest_investment_summary", script)
        self.assertIn("quote_gaps", script)
        self.assertIn("DryRun", script)

    def test_automation_check_script_static_contract(self):
        script = (PROJECT_ROOT / "scripts" / "show_automation_check.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("automation_check_report.py", script)
        self.assertIn("latest_automation_check.json", script)
        self.assertIn("--check", script)

    def test_codex_automation_audit_script_static_contract(self):
        script = (PROJECT_ROOT / "scripts" / "audit_codex_automations.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("codex_automation_audit.py", script)
        self.assertIn("C:\\Users\\pechen\\.codex\\automations", script)
        self.assertIn("--automation-root", script)

    def test_weekly_ops_check_script_static_contract(self):
        script = (PROJECT_ROOT / "scripts" / "run_weekly_ops_check.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("weekly_ops_check.py", script)
        self.assertIn("latest_automation_check.json", script)
        self.assertIn("latest_weekly_ops_check.json", script)
        self.assertIn("weekly_ops_check_history.jsonl", script)
        self.assertIn("C:\\Users\\pechen\\.codex\\automations", script)
        self.assertIn("--project-root", script)
        self.assertIn("--automation-root", script)
        self.assertIn("--check", script)
        self.assertIn("--output", script)
        self.assertIn("--history", script)
        self.assertIn("MaxAgeDays", script)
        self.assertIn("--max-age-days", script)

    def test_weekly_ops_history_script_static_contract(self):
        script = (PROJECT_ROOT / "scripts" / "show_weekly_ops_history.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("weekly_ops_history_report.py", script)
        self.assertIn("weekly_ops_check_history.jsonl", script)
        self.assertIn("latest_weekly_ops_history_summary.json", script)
        self.assertIn("latest_weekly_ops_history_report.md", script)

    def test_weekly_delivery_history_script_static_contract(self):
        script = (PROJECT_ROOT / "scripts" / "show_weekly_delivery_history.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("weekly_delivery_history_report.py", script)
        self.assertIn("weekly_delivery_check_history.jsonl", script)
        self.assertIn("latest_weekly_delivery_history_summary.json", script)
        self.assertIn("latest_weekly_delivery_history_report.md", script)
        self.assertIn("--history", script)
        self.assertIn("--output", script)
        self.assertIn("--report", script)
        self.assertIn("--window", script)

    def test_weekly_action_items_script_static_contract(self):
        script = (PROJECT_ROOT / "scripts" / "show_weekly_action_items.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("weekly_action_items.py", script)
        self.assertIn("latest_self_analysis_manifest.json", script)
        self.assertIn("latest_weekly_action_items.json", script)
        self.assertIn("latest_weekly_action_items.md", script)
        self.assertIn("--manifest", script)
        self.assertIn("--output", script)
        self.assertIn("--report", script)


    def test_docs_describe_first_one_month_evaluation_contract(self):
        for relative_path in (
            "docs/美股每周自动运行说明.md",
            "docs/提交前复核清单.md",
            "docs/中期目标进度看板.md",
        ):
            doc = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8-sig")
            self.assertIn("latest_first_one_month_forecast_evaluation_review.json", doc)
            self.assertIn("2026-08-03", doc)
            self.assertIn("sample_incomplete", doc)
            self.assertIn("formal_model_conclusion_allowed=false", doc)


if __name__ == "__main__":
    unittest.main()
