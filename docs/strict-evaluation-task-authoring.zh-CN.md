# AI Agent 严格评测任务编写规范

本文档定义 AgentArena Local 的严格评测任务编写标准。目标不是复刻 SWE-bench 的 Docker/harness，而是吸收成熟项目的核心设计，形成一个轻量、本地、可复现、可审计的评测任务体系。

## 参考项目与借鉴点

| 项目 | 借鉴点 | 在 AgentArena Local 中的落地方式 |
| --- | --- | --- |
| SWE-bench / SWE-agent 生态 | 真实 GitHub issue、resolved 判定、公开实验日志、轨迹记录 | 使用真实仓库任务、`baseline` + `fail_to_pass` + `pass_to_pass` 判定 resolved，保存 stdout/stderr/diff/result |
| mini-swe-agent | 极简 harness、线性历史、`subprocess.run`、本地环境优先 | 保持本地命令执行和 Git worktree，不引入重型运行时 |
| vexp-swe-bench | agent-agnostic harness、JSONL 结果、resume、成本/耗时/unique wins | 后续 suite 层采用 JSONL 追加结果、断点续跑、agent 胜场统计 |
| OpenHands benchmarks | 多 benchmark 统一管线、标准化任务目录、批量执行 | 定义标准任务包目录和 suite 配置，但不强制容器化 |
| Aider benchmark | pass@k、多次尝试、well-formed、语法错误、超时、成本、commit hash/dirty 状态 | 记录 pass@k、syntax_error、timeout、dirty_repo_before_run、commit_hash、duration |
| Terminal-Bench | instruction、验证脚本、oracle solution、最终状态验证 | 每个严格任务必须有明确 instruction、验证命令、可选 oracle patch/solution，并评估最终仓库状态 |

## 核心原则

1. **本地轻量**：默认只依赖 Git worktree 和本地命令，不要求 Docker、WSL2 或远程执行。
2. **任务可复现**：任务必须能从一个明确的 Git commit 或本地 repo 状态重复运行。
3. **最终状态验证**：评分看 agent 修改后的仓库状态，而不是只看回答文本。
4. **先证明任务有效**：`baseline` 必须能证明原始状态确实失败或缺功能。
5. **修复与回归分离**：`fail_to_pass` 验证修复，`pass_to_pass` 验证旧能力未破坏。
6. **隐藏测试有权重**：没有 hidden 只能说明公开测试通过，不能证明泛化能力。
7. **轨迹可审计**：每次运行必须保存命令、日志、diff、分数拆解和失败原因。
8. **agent-agnostic**：任务不能依赖某个 agent 的特殊提示格式或私有工具。
9. **防刷分**：禁止修改评测器、任务定义、隐藏测试、报告生成器来获得高分。
10. **分数必须拉开差距**：resolved 只是合格线，测试质量、隐藏测试、回归、diff 质量决定高分。

## 推荐任务包结构

```text
benchmarks/<task-id>/
  task.yaml
  README.md
  repo/
  hidden_tests/
  verifier/
    verify.py
    check_integrity.py
  oracle/
    solution.patch
    notes.md
  metadata.json
```

当前 AgentArena Local 已支持直接引用本地 repo 或当前仓库路径；任务包结构是推荐规范，不强制所有目录都存在。

### 文件职责

| 文件或目录 | 必需 | 用途 |
| --- | --- | --- |
| `task.yaml` | 是 | 任务配置、命令组、约束、评分元数据 |
| `README.md` | 建议 | 给人类评审看的任务说明、风险、期望行为 |
| `repo/` | 可选 | 自包含任务仓库；也可以指向外部本地 Git 仓库 |
| `hidden_tests/` | 建议 | 不暴露给 agent 的边界测试或补充验证 |
| `verifier/verify.py` | 建议 | 最终状态验证入口，用于组合多个检查 |
| `verifier/check_integrity.py` | 建议 | 校验测试、任务定义、隐藏文件未被修改 |
| `oracle/solution.patch` | 建议 | 至少一种正确解，便于任务作者验证任务可解 |
| `metadata.json` | 建议 | 难度、领域、语言、来源 issue、作者、评审状态 |

## 严格 task.yaml 模板

```yaml
id: python-debug-login-strict
title: Fix login validation without breaking invalid-login behavior
type: debug
repo: ./repo

description: >
  The login function rejects valid credentials because stored passwords may
  contain leading or trailing whitespace.

instructions: >
  Fix the login validation bug with the smallest reasonable code change.
  Preserve the public function name and keep invalid login behavior unchanged.

success_criteria:
  - Valid credentials authenticate after trimming stored password whitespace.
  - Invalid passwords and unknown users are still rejected.
  - Public function names remain unchanged.
  - The solution is not hard-coded to the visible test data.

setup:
  commands:
    - name: install
      command: pip install -e ".[dev]"
      timeout_seconds: 180

baseline:
  commands:
    - name: bug-repro-before
      command: pytest tests/test_login_bug.py::test_valid_password_with_storage_whitespace
      timeout_seconds: 120

fail_to_pass:
  commands:
    - name: bug-repro-after
      command: pytest tests/test_login_bug.py::test_valid_password_with_storage_whitespace
      timeout_seconds: 120

pass_to_pass:
  commands:
    - name: existing-login-behavior
      command: pytest tests/test_login_regression.py
      timeout_seconds: 120

hidden:
  commands:
    - name: hidden-login-edges
      command: pytest hidden_tests/test_login_edges.py
      timeout_seconds: 120

test:
  commands:
    - name: public-suite
      command: pytest tests
      timeout_seconds: 120

constraints:
  - kind: max_files_changed
    value: "3"
    description: Keep the fix local to login logic and tests.
  - kind: max_diff_lines
    value: "120"
    description: Avoid broad refactors for a narrow bug.
  - kind: forbidden_files
    value:
      - task.yaml
      - hidden_tests/**
      - verifier/**

expected_files_may_change:
  - src/**
  - tests/**

feature_checks:
  required_patterns:
    - strip
  forbidden_patterns:
    - "alice.*secret"
    - "if username =="

metadata:
  source: local
  language: python
  difficulty: easy
  category: debug
  evaluator_version: strict-v1
  estimated_minutes: 10
```

## 命令组设计规则

### baseline

1. 必须在 agent 修改前运行。
2. 应该只覆盖任务要修复的缺陷或缺失功能。
3. 正常情况下应该失败；如果通过，说明任务无效。
4. 不应包含全部测试套件，避免因为 unrelated failure 误判任务无效。
5. baseline 失败原因必须与任务描述一致。
6. baseline 命令必须 deterministic。
7. baseline 不能依赖外部网络。
8. baseline 不应写入持久状态，除非 setup 会清理。
9. baseline 日志必须足够定位原始失败。
10. baseline 不配置时，任务仍可运行，但最高可信度下降。

### fail_to_pass

1. 必须覆盖 baseline 中复现的缺陷。
2. 修复后应全部通过。
3. 多个 fail-to-pass 测试应覆盖不同修复面。
4. 不应与 pass-to-pass 混在同一个命令里。
5. 不应允许跳过、xfail、修改测试来通过。
6. 应覆盖至少一个边界输入。
7. 应避免只验证返回码，不验证行为。
8. 测试失败时分数最高 60。
9. 通过 fail-to-pass 只代表“修到核心 bug”，不是满分。
10. fail_to_pass 通过率应进入 JSONL 和报告。

### pass_to_pass

1. 验证原有功能没有被破坏。
2. 至少包含一个与修复代码同模块相关的旧行为。
3. 对公共 API、CLI、HTTP 接口应保留兼容测试。
4. 不应过度宽泛到运行巨大无关套件。
5. 失败时最高 70。
6. 应记录具体失败命令和日志。
7. 应防止 agent 用删除旧测试换取通过。
8. 对跨模块改动，应覆盖调用方行为。
9. 对数据迁移类任务，应覆盖旧数据读取。
10. pass_to_pass 通过率用于区分“修好但破坏旧功能”的 agent。

### hidden

1. 用于公开测试之外的边界和泛化验证。
2. hidden 不应暴露给 agent 的 prompt。
3. hidden 文件应被 forbidden_files 保护。
4. hidden 失败时最高 80。
5. 未配置 hidden 时最高 85。
6. hidden 应覆盖特判风险最高的输入。
7. hidden 应包含至少一个非样例数据。
8. hidden 不应依赖随机数，除非固定 seed。
9. hidden 日志可以保存，但任务开始前不得进入 agent 工作提示。
10. hidden 通过是进入高分段的必要条件。

## 评分分层

严格模式下，分数分为三段：

| 分数段 | 含义 |
| --- | --- |
| 0-30 | 没有有效改动、任务无效、严重绕评测或 agent 崩溃 |
| 31-60 | 尝试修复但核心 fail-to-pass 未过 |
| 61-70 | 核心修复部分有效，但回归失败或约束明显不合格 |
| 71-80 | resolved 或接近 resolved，但缺 hidden、缺测试改动或质量不足 |
| 81-90 | resolved，hidden 或测试质量较好，但仍有覆盖/质量缺口 |
| 91-100 | resolved + hidden + pass_to_pass + 测试改动 + 小 diff + 无违规 |

当前自动评分建议：

| 项目 | 分值 |
| --- | ---: |
| fail_to_pass | 30 |
| pass_to_pass | 15 |
| hidden | 15 |
| feature_completeness | 10 |
| constraints_passed | 8 |
| diff_quality | 7 |
| test_changes | 10 |
| time_efficiency | 3 |
| task_validity | 2 |
| violations | 扣分 |

硬性封顶：

| 条件 | 最高分 |
| --- | ---: |
| baseline 原本已经通过 | 40 |
| fail_to_pass 失败 | 60 |
| pass_to_pass 失败 | 70 |
| hidden 失败 | 80 |
| 未配置 hidden | 85 |
| 未新增或修改测试 | 80 |
| 无有效改动 | 30 |
| 未 resolved | 85 |
| 修改任务定义、hidden、verifier | 20 |
| 删除关键测试 | 20 |

## 失败原因枚举

建议 result.json 和 JSONL 至少支持这些失败原因：

```text
setup_failed
baseline_invalid
agent_runtime_error
agent_timeout
no_code_changed
fail_to_pass_failed
pass_to_pass_failed
hidden_failed
test_failed
modified_task_definition
modified_hidden_tests
modified_verifier
modified_forbidden_file
removed_tests
syntax_error
lint_error
type_error
diff_too_large
too_many_files_changed
forbidden_pattern_found
unexpected_file_changed
dirty_repo_before_run
non_deterministic_result
```

## 防刷分规则

1. `task.yaml`、`hidden_tests/**`、`verifier/**` 默认 forbidden。
2. 运行前记录这些文件 hash。
3. 运行后重新计算 hash，不一致则触发 `modified_verifier` 或 `modified_hidden_tests`。
4. 禁止删除公开测试。
5. 禁止把测试改成 skip/xfail。
6. 禁止修改评分器或 runner 来提高当前任务分数。
7. 禁止依赖网络下载未知资源。
8. 禁止读取隐藏测试内容后写特判。
9. 禁止硬编码测试数据。
10. 禁止把本地绝对路径写进实现逻辑。

## 轨迹与结果记录

每次 agent/task/try 应保存：

```text
result.json
stdout.log
stderr.log
test.log
diff.patch
commands.json
trajectory.jsonl
summary.md
```

### result.json 必备字段

```json
{
  "run_id": "20260522_120000_python-debug-login",
  "agent": "codex",
  "task": {
    "id": "python-debug-login",
    "type": "debug",
    "repo": "C:/repo",
    "base_commit": "abc123"
  },
  "try_index": 1,
  "resolved": true,
  "score": 80,
  "score_breakdown": {},
  "strict": {
    "enabled": true,
    "baseline_passed": false,
    "task_valid": true,
    "fail_to_pass_passed": true,
    "pass_to_pass_passed": true,
    "hidden_passed": null
  },
  "failures": [],
  "warnings": [],
  "duration_seconds": 90.2,
  "cost_usd": null,
  "token_usage": null,
  "commit": {
    "base": "abc123",
    "dirty_before_run": false
  },
  "diff": {
    "changed_files": ["src/login.py"],
    "total_diff_lines": 12
  }
}
```

### JSONL suite 结果

借鉴 vexp-swe-bench，suite 模式应该追加写入：

```text
.agentarena/results/<suite-id>.jsonl
```

每行一个 agent/task/try 结果，便于：

- resume 时跳过已完成样本。
- 统计 pass@k。
- 统计 unique wins。
- 统计平均耗时和成本。
- 生成排行榜。

## 多次尝试与排行榜

借鉴 Aider benchmark，suite 报告应包括：

| 指标 | 说明 |
| --- | --- |
| pass@1 | 第一次尝试 resolved 的任务比例 |
| pass@k | k 次内任意一次 resolved 的任务比例 |
| avg_score | 平均分 |
| median_score | 中位数 |
| resolved_count | resolved 任务数 |
| unique_wins | 只有该 agent resolved、其他 agent 未 resolved 的任务数 |
| avg_duration | 平均耗时 |
| timeout_count | 超时次数 |
| syntax_error_count | 语法错误次数 |
| malformed_output_count | 输出格式不合格次数 |
| dirty_run_count | 运行前 repo 脏状态次数 |
| total_cost_usd | 总成本，无法获取时为 null |

## 任务作者检查清单

提交一个严格任务前，必须逐项确认：

1. 任务来自真实工程问题或真实工程风格需求。
2. instruction 清晰，但不泄露实现答案。
3. baseline 在原始状态下失败。
4. oracle solution 能让 fail_to_pass、pass_to_pass、hidden 全部通过。
5. fail_to_pass 只覆盖任务核心缺陷，不混入无关失败。
6. pass_to_pass 覆盖至少一个旧行为。
7. hidden 覆盖公开测试没有覆盖的边界。
8. constraints 能阻止大范围无关改动。
9. forbidden_files 覆盖 task、hidden、verifier。
10. feature_checks 能阻止明显特判或空实现。
11. 测试不依赖真实网络或本机私有状态。
12. 命令在干净 worktree 中可重复执行。
13. 失败日志足够诊断。
14. 难度、语言、领域、预计耗时已写入 metadata。
15. README 或 notes 说明任务设计意图和评分重点。

## 好任务与坏任务

好任务：

- 原始失败明确。
- 修复后可自动验证。
- 有回归保护。
- 有隐藏边界。
- 有 oracle solution。
- 修改范围可控。
- 不需要重环境。
- 不靠猜测评分。
- 不泄露隐藏测试。
- 对多个 agent 有区分度。

坏任务：

- 只要求“优化一下”“改好看一点”。
- 测试只断言不报错。
- baseline 本来就通过。
- 修复必须靠外部服务。
- 隐藏测试和公开测试完全重复。
- 任务说明泄露具体代码改法。
- 允许修改 verifier。
- 没有 pass_to_pass。
- 所有 agent 都能一行改满分。
- 失败时无法判断原因。

## 推荐落地顺序

1. 完善现有 `task.yaml` 严格字段。
2. 给每个示例任务补 baseline/fail_to_pass/pass_to_pass。
3. 给至少一半任务补 hidden。
4. 增加 verifier hash 检查。
5. 增加 JSONL suite runner。
6. 增加 resume。
7. 增加 pass@k。
8. 增加 unique wins。
9. 增加成本/耗时统计。
10. 增加任务包模板生成命令。

