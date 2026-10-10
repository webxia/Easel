# ADR-005 Hypit 历史测试精准退役与当前 Native 风险映射（2026-10-10）

**范围**：Easel `wc_goal_yYpFxgMopd9MlccK`，CUT5；维护主线 `easel-studio`。这是代码/测试替代关系的验收附件，不能替代 `docs/02_CURRENT_STATE.md` 的当前状态，也不代表真实付费 Hypit Build/E2E 已通过。

## 原件与精确退役边界

- 原源码是 Git `bb01aede668462dce706eeecd8a7737033c25854:tests/test_hypit_integration.py`，SHA-256 `8d0daae461ec11265a3c6600487a3e555acdc16344069ff52e3ea432bc05ae58`，从该固定 Git Blob 可原样恢复；无须删除任何实际历史 Creation/Attempt、原始证据或成本账本。
- 旧模块原先 **49 collected，24 PASS / 25 FAIL**。失败对应 **20 个旧测试函数（含 2 个完整 Lifecycle 参数化、4 个 Price 参数化、2 个 Quality 参数化，共 25 个测试用例）**。它们依赖已被 ADR-005 禁用的过渡字符串 SVRun Writer、部分/空 pin、旧 Quality profile 或允许 Legacy 自动继续执行。允许它们成功需要重新启用已删除的路径，属于不应再维持的执行假设。
- **退役规则**：只移除下表这 20 个明确识别的旧执行假设测试函数，不批量 skip/xfail、不修改其它仍有风险价值的旧测试函数。新代码用真实 Creation/Handoff、Planning、Material Need/Rights/Readiness、Native Authoring/Check、Output/Review/Content Library 内部模块运行，外部 Hypit CLI/Provider 使用确定性 fixture；全部受测例应具备实际 PASS 后才能生效。
- **关键决策**：旧 `test_hypit_integration.py` 应保留其原已通过的 **24 个软件检查**（包含原 handoff hash、Browser Operator 鉴权、Hypit CLI 凭证隔离、Material attribution、Narration/BGM、Quality、冷恢复等）。并非删除整个测试文件或把失败视为成功。

## 旧失败用例逐函数 → 当前原生有效风险测试

| 原测试函数（每行精确一个退役单位） | 参数化用例数 | 对应仍在运行的新版保护 |
|---|---:|---|
| `test_normalizes_only_unambiguous_single_timeline_clock_reference` | 1 | `test_native_parsers_bind_typed_recipes_run_aliases_and_exact_source`、`test_native_source_rejects_ambiguous_or_out_of_profile_input`；旧文本就地正规化 Writer 不再存在 |
| `test_timeline_clock_normalization_preserves_verbatim_caption_newlines` | 1 | `test_native_revision_protects_typed_dependencies_and_all_text`、`test_native_narration_and_music_share_actual_graph_and_preserve_unicode`；保留真实 Unicode/字节与 AST 绑定 |
| `test_authoring_is_runtime_independent_and_static_check_only` | 1 | `test_native_authoring_owner_publishes_one_checked_candidate_and_replays_read_only`、`test_native_authoring_actual_installed_hypit_static_check_without_build`、`test_managed_native_authoring_promotion_io_reclaims_original_stage_without_agent` |
| `test_complete_lifecycle_requires_review_before_selection` | 2 | `test_native_review_and_selection_are_output_bound_and_never_auto_publish`、`test_native_review_retraction_revokes_selected_output_and_keeps_export_evidence`、`test_native_multi_attempt_selection_cleanup_retries_after_archive_symlink_and_io`、`test_native_rights_constraints_survive_export_to_manual_publication` |
| `test_material_audio_policy_requires_audio_stream_at_export` | 1 | `test_native_export_requires_real_audio_track_in_encoded_mp4`（实际本地 MP4/ffprobe；非假元数据），`test_native_published_source_reaches_real_quality_delta_owner` |
| `test_pricing_keeps_aggregate_unknown_and_persists_contract_fingerprint` | 4 | `test_native_pricing_unknown_is_not_an_implicit_spend_cap` 的 **4** 个明确 Price 对象（含假 total、缺 groups、有 provider 和 requestCount=0），校验报价/Plan SHA 和零费用拒绝 |
| `test_zero_cost_commission_uses_real_contract_and_revalidates_before_build` | 1 | `test_verified_native_commission_requires_explicit_frozen_confirmation`、`test_native_commission_revocation_blocks_build_before_external_effect`（5 种批准后撤销）、`test_native_commission_approval_cas_rechecks_latest_creation_confirmation`（锁内竞态），同时保留实际确认 API |
| `test_pricing_change_after_approval_blocks_build` | 1 | `test_native_changed_pricing_revokes_prior_cost_approval` |
| `test_plan_change_after_approval_blocks_build` | 1 | `test_native_plan_contract_drift_revokes_approval_without_build` |
| `test_failed_export_keeps_final_absent_and_removes_staging` | 1 | `test_native_export_validation_failure_removes_staged_media_and_leaves_no_receipt` |
| `test_uncertain_build_submission_is_persisted_and_cannot_be_blindly_retried` | 1 | `test_native_unknown_build_failure_is_redacted_and_not_retried`、`test_native_unknown_build_receipt_reconciles_without_resubmitting` |
| `test_two_concurrent_build_requests_only_submit_once` | 1 | `test_native_concurrent_build_clicks_keep_single_submission` |
| `test_fingerprint_change_invalidates_approval_and_blocks_build` | 1 | `test_native_approval_invalidates_on_runtime_bytes_change_before_build`、`test_native_handoff_truth_bytes_tamper_blocks_native_before_build` |
| `test_validate_cannot_reset_submitted_attempt` | 1 | `test_native_submitted_attempt_cannot_revalidate_or_reset_build` |
| `test_uncertain_build_can_reconcile_by_operation_marker` | 1 | `test_native_unknown_build_receipt_reconciles_without_resubmitting` |
| `test_nonzero_status_with_valid_failed_json_is_a_build_failure` | 1 | `test_native_failed_build_status_preserves_structured_local_failure` |
| `test_workspace_handoff_tampering_blocks_build_and_invalidates_approval` | 1 | `test_native_handoff_truth_bytes_tamper_blocks_native_before_build`（Domain 原始 Hash 拒绝）、`test_native_approval_invalidates_on_runtime_bytes_change_before_build` |
| `test_secret_in_cli_stderr_is_redacted_before_persistence` | 1 | `test_native_hypit_subprocess_stderr_secret_redacted_at_error_and_persistence`（实际 subprocess adapter 错误、环境隔离、原件脱敏与幂等重播）；保留旧已通过 CLI env 隔离测试 |
| `test_review_for_output_a_cannot_select_output_b` | 1 | `test_native_review_and_selection_are_output_bound_and_never_auto_publish` |
| `test_output_quality_detects_masking_truncated_voice_and_decoded_black_frames` | 2 | `test_native_audio_quality_measurements_reject_truncation_masking_and_clipping`、`test_native_output_measurement_decodes_black_frames_without_false_voice_loss`、`test_native_published_source_reaches_real_quality_delta_owner`、`tests/test_quality_result_delta.py` 的多轮原始报告与篡改拒绝 |

**边界复核**：Retire 不是迁移历史 Attempt。新版旧协议拒绝仍由 `tests/test_result_protocol_defaults.py` 与 `tests/test_newonly_authoring_boundaries.py` 在外部效果前执行。归档失败、symlink、未知提交、Rights 与 Content Library 仍由真实模块测试保护。

## 实际验收、冻结证据与独立复核边界

- **已执行**：新旧整合当前源码 `wc_job_qM8Yz2eOpg4F7phv`：**450 PASS / 0 FAIL / 492.85 秒**（20 个已列出的有效测试文件，2 条 Starlette/AnyIO 弃用 warning）。旧模块单独 **24 PASS / 0 FAIL**；新增异常报价/真实 CLI stderr 脱敏 **5 PASS**，黑帧与旁白真实 MP4 **1 PASS**，人工 Review 撤销选择 **1 PASS**，并被整合运行覆盖。
- **机器只读映射复核**：原 Git Blob SHA-256 与当前文档一致，旧退役函数数量恰为20，映射表无缺失或多余条目，所有后继测试函数符号真实存在：`MAPPING_AUDIT_PASS=True`。原测试可随时 `git show bb01aede:tests/test_hypit_integration.py` 查看/恢复，不是静默删档。
- **独立 Reviewer 未执行**：Runner `coding_agent_providers: []`、MCP/Plugin 无 Provider，本地无独立模型；不得将 Main 作者的 read-only audit 或本测试结论冒充 Astra。已在 Session 留高优先级 Reviewer TODO `wc_msg_6OXw8ajbrXGmLYlD`（未ACK、未resolve）。明确要求读 `service.py` 的 Creation 原子锁、委托确认 SHA/时间/成本批准与 `SUBMITTING` 事务、并发和失效批准、旧测试退役文件映射，返回 `DECISION=CONTINUE|MODIFY|STOP` 与实际风险/最小修正。
- **阶段事实**：旧 Hypit **测试代码迁移完成且现行测试全绿**；CUT5 **未完成独立 Reviewer 冻结复核**，CUT6 不提交/推送。未运行真实付费 Hypit Build，完整外部 E2E 要求另行授权。
