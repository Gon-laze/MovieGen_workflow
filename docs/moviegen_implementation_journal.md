# MovieGen Implementation Journal

## 约定

- 每一轮实现对话都追加记录。
- 每条记录至少包含：`改动`、`效果`、`问题`、`下一步`。
- 本文档面向实现追踪，不替代主规范文档。

## 2026-03-18 Round 01

### 改动

- 创建 `pyproject.toml`
- 创建 `moviegen/__init__.py`
- 创建 `moviegen/models.py`
- 创建 `moviegen/config.py`
- 创建 `moviegen/storage.py`
- 创建 `moviegen/cli.py`
- 创建 `config/project.example.yaml`
- 扩展根目录 `.gitignore`

### 效果

- 项目具备最小 Python 包结构
- 可用 `Typer + Pydantic + SQLite` 运行最小 CLI
- 规范文档中的核心配置块已同步到示例配置

### 问题

- 当前 CLI 仍是 scaffold 级，不包含真实 provider 集成
- journal 尚未记录一次真实运行结果

### 下一步

- 运行一次 `dry-run`
- 记录生成的 `state/`、`workspace/reports/` 与日志产物

## 2026-03-18 Round 02

### 改动

- 执行 `python -m moviegen.cli run config/project.example.yaml --stage all --dry-run`
- 执行 `python -m moviegen.cli status --run-id run_20260318_233144_bae47838`
- 补写主规范文档中的：
  - `CandidateClip / Artifact / HumanGateDecision / BudgetLedger` 契约
  - `错误码 / 失败原因 taxonomy`
  - `日志与可观测性字段`
  - `CLI 参数与返回码约定`

### 效果

- 生成了可复现的 `run_id`：
  - `run_20260318_233144_bae47838`
- 成功创建：
  - `state/moviegen.db`
  - `workspace/reports/run_20260318_233144_bae47838__run_summary.json`
  - `workspace/reports/run_20260318_233144_bae47838__status.txt`
  - `workspace/logs/runs/run_20260318_233144_bae47838.jsonl`
  - `workspace/logs/stages/` 下 13 个阶段日志
- SQLite 中已确认写入：
  - `runs = 1`
  - `stage_runs = 13`
  - `artifacts = 2`
- `moviegen status` 列表模式与按 `run_id` 查询模式都可正常返回 JSON

### 问题

- 当前 CLI 仍为 scaffold 级：
  - 没有真实 provider 提交
  - 没有真实 benchmark 评分
  - 没有真实 judge 打分
- `resume`、`clean` 目前只覆盖最小行为，尚未接入完整状态机与 artifact policy
- 文档已具备实现规格，但代码尚未实现：
  - `Reference Ingest`
  - `Benchmark Runner`
  - `Provider Router`
  - `AI Judge`

### 下一步

- 优先实现 `Reference Ingest` 最小版
- 实现 `Benchmark Runner` 的 `benchmark_suite_v1` 结构化输出
- 实现 `Provider Router` 的基础路由矩阵与 dry-run 解释输出

## 2026-03-18 Round 03

### 改动

- 新增 `moviegen/workflow.py`
- 将 `moviegen.cli.run()` 从纯 scaffold 循环改为实际调用阶段处理器
- 实现最小版：
  - `Reference Ingest`
  - `Reference Analyzer`
  - `Bible Builder`
  - `Benchmark Runner`
  - `Story & Shot Planning`
  - `Prompt Compiler`
  - `Provider Router`
- 对尚未实现的后续阶段统一生成 placeholder 产物

### 效果

- `run --dry-run` 不再只是空壳日志，而会实际生成：
  - `workspace/reference_manifest.json`
  - `workspace/reference_pack.json`
  - `workspace/reports/*analysis_summary.json`
  - `workspace/bibles/*.json`
  - `workspace/reports/*benchmark_report.json`
  - `workspace/reports/*shot_plan.json`
  - `workspace/prompts/*prompt_packets.json`
  - `workspace/reports/*route_plan.json`
- `Benchmark Runner` 现在会把 `Seedance 2.0 / Kling 3.0` 作为第一梯队写入结构化报告
- `Provider Router` 现在会把路由矩阵落成可读取的 JSON 报告

### 问题

- 媒体级能力仍未接入：
  - 真实切镜
  - 真正的关键帧抽取
  - 真正 provider 调用
  - 真正 judge 打分
- `resume` 仍未接入按 stage 恢复逻辑
- `clean` 仍未区分 artifact retention policy

### 下一步

- 先再次运行一轮 `dry-run`，验证新增产物是否稳定落盘
- 然后补 `Reference Ingest` 的真实文件扫描效果到日志
- 之后再实现 `Benchmark Runner` / `Provider Router` 的 richer output 或进入真实 provider 适配层

## 2026-03-18 Round 04

### 改动

- 复跑 `dry-run`，确认 `workflow.py` 阶段处理器真实生效
- 检查 `workspace/reference_manifest.json`
- 修正 `config/project.example.yaml` 中失效的 `text_notes` 路径
- 新建：
  - `input/reference_videos/.gitkeep`
  - `input/reference_images/.gitkeep`
  - `input/notes/README.md`

### 效果

- 确认新增阶段处理器已生成：
  - `reference_manifest.json`
  - `reference_pack.json`
  - `analysis_summary`
  - `bibles`
  - `benchmark_report`
  - `route_plan`
- 确认第二次 `dry-run` 的 `run_id`：
  - `run_20260318_234138_765518f1`

### 问题

- 示例配置原先引用了不存在的 `NewChat-Monica_AI_Chat.pdf`
- 因此本轮 ingest 报告中的 `missing_input` 是真实错误，不是缓存或代码假阳性
- 在修正前，示例项目会导入 `0` 个资产，这不利于后续演示

### 下一步

- 再跑一轮 `dry-run`，确认示例配置至少能导入主规范文档作为文本资产
- 继续把 `Reference Ingest` 从“目录扫描”推进到“更细的标签化与摘要抽取”

## 2026-03-18 Round 05

### 改动

- 修正 `Reference Ingest`：忽略以 `.` 开头的占位文件

### 效果

- `.gitkeep` 不再被记为 `unsupported_format`
- 示例项目的 ingest 结果会更干净，更适合演示和后续测试

### 问题

- 当前 ingest 仍只做到目录扫描、哈希和粗标签
- 还没有真正的切镜、关键帧抽取和内容理解

### 下一步

- 再跑一轮 `dry-run`，确认 `.gitkeep` 不再出现在失败清单

## 2026-03-18 Round 06

### 改动

- 复核 `run_20260318_234513_3d00ce51` 的串行结果，确认：
  - `ingest` 已成功导入 2 个文本资产
  - 不再出现真实缺失路径
- 新增 CLI 命令：
  - `moviegen benchmark`
  - `moviegen gate`
- `status --run-id` 新增 `gates` 输出
- 将 `run` 内部逻辑抽为可复用的 `execute_run()`

### 效果

- 可以单独触发 benchmark 阶段
- 可以把 Gate 决策结构化写入数据库
- 运行态和命令态开始共用一套执行逻辑

### 问题

- `gate` 目前只做数据库写入，尚未真正驱动 paused/resume 状态机
- `benchmark` 仍是 planning-only，不涉及真实 provider 调用

### 下一步

- 先验证新 CLI 子命令是否按预期工作
- 再考虑是否补最小 `pause/resume` 流程

## 2026-03-18 Round 07

### 改动

- 为 `plan` 增加可选输入：
  - `planning.shot_specs_file`
- 新增 `input/shot_specs.example.yaml`
- `route` 阶段现在会基于 `shot_specs` 生成结构化 `GenerationJob` 计划
- `generation_jobs` 会写入 SQLite

### 效果

- `plan -> route` 不再只是空壳说明，而能产出真实的 job planning 结果
- 可以开始验证：
  - `narrative_multi_shot -> seedance_2_0`
  - `motion_control -> kling_3_0`
  - `dialogue_native_audio -> vidu_q3`

### 问题

- 目前 `compile-prompts` 仍然没有按 `shot_specs` 产出逐 provider packet
- `estimated_cost_usd` 仍是占位值

### 下一步

- 跑一轮 `all --dry-run`
- 确认 `shot_plan`、`route_plan`、`generation_jobs` 三份产物一致

## 2026-03-18 Round 07

### 改动

- 为 `Reference Ingest` 新增 `run_id` 级快照：
  - `run_*__reference_manifest.json`
  - `run_*__reference_pack.json`
- 为 `Bible Builder` 新增 `run_id` 级快照：
  - `run_*__style_bible.json`
  - `run_*__character_bible.json`
  - `run_*__scene_bible.json`
- 将 `moviegen report` 从“只输出 run_summary”升级为“聚合 run + stages + gates + report_files”

### 效果

- 多轮运行时，核心 ingest/bible 产物不再只保留最新覆盖版本
- `report` 命令更适合作为实现追踪和运维入口
- 后续每轮对话的留档可直接依赖 `report` 聚合结果

### 问题

- 目前 `workspace/reference_manifest.json` 仍保留“当前最新态”，与 `run_id` 快照并存
- 还没有建立“当前最新态”和“快照态”的清理策略区分

### 下一步

- 再跑一轮 `ingest` 或 `all --dry-run`，验证 snapshot 文件是否正确落盘
- 验证 `moviegen report` 新输出是否包含 stages/gates/report_files

## 2026-03-18 Round 08

### 改动

- 强化 `Reference Ingest`
  - 为文本资产新增 `text_metadata`
  - 提取字符数、行数、预览片段
- 强化 `Reference Analyzer`
  - 新增 `top_terms`
  - 新增 `text_previews`
  - 对文本参考做轻量关键词抽取

### 效果

- `ingest` 不再只是“知道有文本文件”，而是能把文本参考转成后续可用的摘要信息
- `analyze` 现在能给出基础关键词候选，便于后续 bible 和 prompt 工作

### 问题

- 关键词抽取目前仍是规则型，不是语义级摘要
- PDF 正文抽取尚未实现，当前只覆盖可直接读取的文本文件

### 下一步

- 跑一轮 `analyze` 验证 `top_terms` 和 `text_previews`
- 再决定是否为 PDF 接入抽取能力

## 2026-03-18 Round 09

### 改动

- 为 `Reference Analyzer` 增加兼容回退：
  - 若旧版 `reference_manifest.json` 中没有 `text_metadata`
  - 则根据 `source_path` 现场补抽文本预览与关键词

### 效果

- `analyze` 不再强依赖“最新一轮 ingest 产物格式”
- 即使 manifest 是旧版本，也能继续生成 `text_previews` 与 `top_terms`

### 问题

- 当前关键词抽取仍是规则型，中文效果有限
- 还未接入 PDF 正文抽取，因此 PDF 仍只会在存在可读文本时发挥作用

### 下一步

- 再跑一轮 `analyze --dry-run`
- 验证 `top_terms` 与 `text_previews` 是否填充

## 2026-03-19 Round 10

### 改动

- 修复 `storage.py` 与 `workflow.py` 之间的不同步问题
- 为 `generation_jobs` 增加数据库迁移字段：
  - `packet_id`
  - `provider_rank`
  - `selected_reason`
  - `archetype`
  - `grade`
  - `budget_class`
  - `estimated_cost_usd`
  - `queue_policy`
  - `fallback_chain`
- 补全 `compile-prompts`
  - 按 `shot_specs` 生成 provider-specific `PromptPacket`
- 补全 `route`
  - 从 `PromptPacket` 反查 `packet_id`
  - 将路由决策写入 SQLite `generation_jobs`

### 效果

- 最新一轮 `all --dry-run` 的 `run_id`：
  - `run_20260319_000414_e701155c`
- 已确认这三层链路贯通：
  - `shot_specs`
  - `prompt_packets`
  - `generation_jobs`
- SQLite `generation_jobs` 现在已能写入：
  - `packet_id`
  - `provider_rank`
  - `selected_reason`
  - `archetype`

### 问题

- `provider_model` 仍等于 provider key，占位性质较强
- `estimated_cost_usd` 仍为 0.0
- PowerShell 直接打印中文 prompt 时有编码噪音，但 JSON 文件正常

### 下一步

- 若继续实现，优先补最小版 `AI Judge`
- 或者开始接入真实 provider 适配器

## 2026-03-19 Round 12

### 改动

- 验证 `all --dry-run` 对 `run_20260319_000414_e701155c` 的全链路输出
- 验证 `status --run-id` 的 `artifacts` 视图
- 验证 `report --run-id` 的聚合报告
- 验证 `clean --scope cache --run-id run_20260319_000414_e701155c`

### 效果

- 已确认 `shot_specs -> prompt_packets -> generation_jobs` 三层链路贯通
- `status --run-id` 现在能看到完整的：
  - `stages`
  - `gates`
  - `artifacts`
- `report --run-id` 现在能看到：
  - run 元数据
  - stage 状态
  - artifact 清单
  - report_files
- `clean --scope cache` 已成功删除：
  - `prompt_packet`
  - `generation_job_plan`
  两类 cache 产物，并同步删除对应 artifact 行

### 问题

- `status` 列表模式在并行检查时偶尔会比 `run` 返回慢一步，容易出现瞬时“旧状态”读数
- `clean` 目前还不会写单独的清理审计日志

### 下一步

- 若继续本地实现，优先补 `AI Judge` 最小实现
- 若开始接真实平台，优先从 `Vidu` 或 `Kling` 的只读适配器开始

## 2026-03-19 Round 11

### 改动

- 为 `status --run-id` 增加 `artifacts` 视图
- 为 `report --run-id` 增加 `artifacts` 聚合
- 将 `clean` 改为基于 SQLite `artifacts.retention_policy` 清理

### 效果

- `status` 与 `report` 现在都能看到 run 级 artifact 列表
- `clean --scope cache` 不再按目录粗暴删除，而是按 artifact 策略执行

### 问题

- 当前 `clean` 只删除文件与 artifact 行，不记录单独的删除审计事件
- `delete_after_run` 与 `cache` 目前在 `clean` 中同一批处理，后续仍可再细分

### 下一步

- 跑一轮 `status/report/clean` 联动验证
- 然后再决定是先做 `AI Judge`，还是先接一个真实 provider

## 2026-03-19 Round 13

### 改动

- 串行复核 `run_20260319_000414_e701155c`
- 核对：
  - `prompt_packets`
  - `route_plan`
  - SQLite `generation_jobs`
- 确认 `packet_id`、`provider_rank`、`selected_reason`、`archetype` 已贯通

### 效果

- `shot_specs -> prompt_packets -> generation_jobs` 已由文件与数据库双重验证
- `run_20260319_000414_e701155c` 已成为当前可追溯的主基线 run
- `seedance_2_0 / kling_3_0 / vidu_q3` 的最小路由规划已经在真实产物中可见

### 问题

- `provider_model` 仍是 provider key 占位
- `estimated_cost_usd` 仍未接入真实定价映射
- `compile-prompts` 还没有真正做 provider-specific 文法差异化

### 下一步

- 优先补 `AI Judge` 最小实现
- 然后再考虑接入真实 `Kling` provider

## 2026-03-19 Round 14

### 改动

- 定位到 `spec.execution` 缺失的根因
- 为 `moviegen/models.py` 补回 `ExecutionSection`
- 为 `config/project.example.yaml` 补回 `execution` 配置块

### 效果

- `providers.py` 不再依赖不存在的字段
- 真实 provider 默认策略重新与配置层对齐：
  - primary: `kling_3_0`
  - optional: `vidu_q3`

### 问题

- 需要重新跑一轮最新 `all --dry-run` 才能确认 `generate/judge` 新闭环真正生效

### 下一步

- 立刻重跑 `all --dry-run`
- 只检查最新 `run_id` 的 `candidate_clips / judge_scores / judge_report`

## 2026-03-19 Round 16

### 改动

- 实现最小版 `generate`
  - 将 `generation_jobs` 转为 mock `candidate_clips`
- 实现最小版 `judge`
  - 生成启发式 `judge_scores`
- 修复异常后遗留的脏 `running` run
- 验证最新全链路 run：
  - `run_20260319_150534_2ca394ea`

### 效果

- 当前最小闭环已贯通：
  - `shot_specs`
  - `prompt_packets`
  - `generation_jobs`
  - `candidate_clips`
  - `judge_scores`
- `run_20260319_150534_2ca394ea` 已产出：
  - `workspace/candidates/*.json`
  - `workspace/review/run_20260319_150534_2ca394ea__judge_scores.json`
- SQLite 已确认写入：
  - `candidate_clips = 6`
  - `judge_scores = 6`
- 历史脏状态：
  - `run_20260319_150343_7c0fefc4`
  - `run_20260319_150325_e939f7b2`
  已被回填为 `failed`

### 问题

- `generate` 仍未提交真实 provider
- `judge` 仍是启发式评分
- `status --run-id` 默认查看的是指定 run，不会自动跳转到最新一轮

### 下一步

- 若继续本地实现，优先增强 `AI Judge`
- 若开始接真实 provider，优先接 `Kling`，并保留 `Vidu` 为可选替换项

## 2026-03-19 Round 15

### 改动

- 新增 `moviegen/providers.py`
  - 默认主 provider 路线为 `Kling`
  - `Vidu` 保留为可选替换项
- 实现最小版 `generate`
  - 从 `generation_jobs` 生成 mock `CandidateClip`
  - 写入 `candidate_clips`
- 实现最小版 `judge`
  - 按 `provider + archetype + grade` 生成启发式 `JudgeScore`
  - 写入 `judge_scores`
- 为 `execute_run()` 增加异常收口逻辑
- 修复历史遗留 `running` run，回填为 `failed`

### 效果

- 最新全链路基线 `run_id`：
  - `run_20260319_150534_2ca394ea`
- 已确认最小闭环贯通：
  - `shot_specs`
  - `prompt_packets`
  - `generation_jobs`
  - `candidate_clips`
  - `judge_scores`
- `status` 列表中的历史脏 `running` 记录已修正为 `failed`

### 问题

- `generate` 仍为 mock，不会提交真实 provider
- `judge` 仍是启发式，不是多模态评分模型
- `provider_model` 与真实模型版本字符串仍未拆分
- `estimated_cost_usd` 仍未接入真实定价映射

### 下一步

- 若继续本地闭环，优先增强 `AI Judge`
- 若开始接真实平台，优先接 `Kling` 只写适配器，再保留 `Vidu` 为可选替换项

## 2026-03-19 Round 15

### 改动

- 为 `execute_run()` 增加异常收口逻辑
- 发生异常时：
  - 写入失败的 `stage_run`
  - 将 `runs.status` 改为 `failed`
  - 写入 `run_failed` 日志事件

### 效果

- 后续再出现异常时，不会再留下长期卡在 `running` 的脏 run
- 状态面板会更可信，恢复与排障也更清晰

### 问题

- 历史上已经留下的 `running` 脏 run 还需要人工修正一次

### 下一步

- 修正历史遗留的 `running` 记录
- 再跑一轮 `all --dry-run`，确认新的异常收口逻辑不影响正常成功路径
