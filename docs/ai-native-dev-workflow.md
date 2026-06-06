# AI-native 研发工作流

本仓库使用 Linear 承载任务意图，使用 GitHub 承载代码、PR 和 CI，使用 Codex 等 coding agent 辅助实现。目标不是让人退出研发流程，而是让每个任务都变成 agent 可读取、可执行、可验证、可复盘的工作单元，同时由人继续负责产品判断、架构取舍、安全边界和最终上线责任。

## 系统流转

1. 任务从 Linear issue 开始，issue 必须写清目标、上下文、验收标准、约束和验证方式。
2. 当 issue 信息足够完整时，进入 `待 Agent 处理`。
3. Codex 或其他 coding agent 先读取 issue、仓库指令、代码、文档和相关日志，再输出实现计划。
4. 对非平凡或有风险的改动，人类 owner 先确认计划，再允许 agent 执行。
5. Agent 在独立 branch、worktree、sandbox 或 Dev Container 中工作。
6. Agent 运行有针对性的验证，并创建 GitHub draft PR。
7. AI review 先检查明显缺陷、遗漏测试、不安全假设和 PR 证据完整性。
8. Human review 决定架构是否合理、业务语义是否正确、安全风险是否可接受、是否可以合并、何时发布以及如何回滚。
9. 可复用经验要回写到 `AGENTS.md`、本指南、测试、PR 模板、skills 或 runbook。

## Linear 队列

试点默认状态链：

```text
待 Agent 处理 -> Agent 执行中 -> AI 评审 -> 人工评审 -> 预览验证 -> 待合并 -> Done
```

状态含义：

- `待 Agent 处理`：issue 已经具备足够上下文，可以交给 agent 计划或执行。
- `Agent 执行中`：agent 正在探索、编辑或验证。
- `AI 评审`：自动化或 agent review 正在检查 PR。
- `人工评审`：人类 owner 正在审查关键决策、风险和证据。
- `预览验证`：需要 preview、浏览器、部署或运行时验证。
- `待合并`：人工评审已通过，PR 等待最终 merge。
- `Done`：任务已合并或以其他方式完成，并且证据已记录。

## 人的职责

人负责意图、优先级、取舍和生产责任。

- 定义目标、非目标、验收标准和风险容忍度。
- 确认跨模块、安全、数据、发布相关或影响较大的改动计划。
- 审查架构一致性、业务正确性、安全性和长期可维护性。
- 决定是否 merge、何时发布、如何灰度、如何回滚以及后续范围。
- 把重复失败沉淀为仓库指令、测试或 runbook。

## Agent 的职责

Agent 负责可重复执行和证据收集。

- 编辑前先读取 Linear issue 和仓库指导。
- 对非平凡任务先输出简洁计划。
- 按 issue 范围和既有项目模式做小而清晰的改动。
- 运行有针对性的验证，并报告准确命令和结果。
- 创建 draft PR，并完整填写 PR 模板。
- 主动暴露阻塞、跳过的检查和需要人工判断的问题。

## 开发环境

使用能证明改动正确性的最轻环境：

- Dev Container：适合依赖敏感或 onboarding 敏感的任务。当前配置固定 Python 3.11、uv、Node 22 和仓库所需系统依赖。
- Worktree 或 branch：适合并行 agent 任务和保持 diff 清晰。
- Sandbox 或 remote VM：适合需要隔离凭证、副作用或本地状态的任务。
- CI：最终 merge gate。agent 的本地验证有价值，但 CI 才是合并前的共享事实来源。

不要把密钥写进 Dev Container、PR body、Linear issue、测试 fixture 或提交的配置文件。需要凭证时使用有作用域的环境变量或 secret manager。

## Pull Request 要求

每个 PR 都应该包含：

- Linear issue 链接。
- 计划摘要。
- 行为、文档、流程或测试改动说明。
- 验证证据。
- 使用的环境。
- 风险和跳过的检查。
- 人工审查重点。
- 是否有规则沉淀。

Agent 创建的 PR 默认保持 draft，直到人类 owner 判断可以进入常规 review 或 merge。

## 加速策略

为了减少每个任务的固定成本，优先使用这些机制：

- 把耗时但确定性的安装步骤放入 Dev Container 的 `onCreateCommand` 或 `updateContentCommand`，让 Codespaces prebuild 可以缓存。
- `postCreateCommand` 只保留轻量检查，例如 `python --version`、`node --version`、`uv --version`。
- 对文档和模板改动使用静态验证，不跑完整测试套件。
- 对代码改动先跑 targeted tests，再交给 CI 做完整 gate。
- 认证、Codespaces scope、Docker runtime 这类一次性环境准备应前置完成，避免每个任务重复阻塞。

## 反馈闭环

当 review、CI、preview 或生产反馈暴露出可复用规则时，更新下面的 durable surfaces：

- `AGENTS.md`：agent 面向的仓库规则。
- `.github/PULL_REQUEST_TEMPLATE.md`：PR 证据要求。
- 测试：不应回归的行为。
- docs 或 runbooks：操作流程。
- skills：可重复的多步骤工作流。

只有当下一轮 agent 能从这次经验中受益时，任务才算真正沉淀完成。
