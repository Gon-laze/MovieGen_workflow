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

## 2026-03-19 Round 17

### 改动

- 增强 `moviegen/providers.py`
  - 为 `Kling` 和 `Vidu` 增加 `build_request()`
  - 增加 mock/live 双模式
  - 约定环境变量：
    - `MOVIEGEN_KLING_SUBMIT_URL`
    - `MOVIEGEN_KLING_TOKEN`
    - `MOVIEGEN_VIDU_SUBMIT_URL`
    - `MOVIEGEN_VIDU_TOKEN`
- 为 `execution` 增加：
  - `request_timeout_sec`
  - `save_provider_requests`
- 新增 `moviegen doctor`
- `generate` 阶段新增 `provider_requests` 落盘

### 效果

- 当前真实 provider 默认路线已明确以 `Kling` 为主
- `Vidu` 作为可选替换项保留
- 即使还没打到线上 API，我们也已经能看到未来 live submit 的请求结构

### 问题

- 由于官方 API 细节尚未完全固化，当前 live submit 仍是保守实现
- `request_timeout_sec` 目前还没有真正传递到 adapter 超时参数中

### 下一步

- 跑一轮新的 `all --dry-run`
- 验证 `provider_requests.json`
- 若需要，再把 `request_timeout_sec` 真正接入 adapter

## 2026-03-19 Round 18

### 改动

- 运行 `moviegen doctor`
- 运行新的 `all --dry-run`
- 复核 `provider_requests.json` 与 `generate_summary`

### 效果

- `doctor` 已能显示：
  - `Kling` 为默认主 provider
  - `Vidu` 为默认可选替换项
  - 当前环境变量是否已配置
- 最新 provider 请求验证基线：
  - `run_20260319_152023_f9c4c04a`
- `workspace/jobs/run_20260319_152023_f9c4c04a__provider_requests.json` 已成功落盘
- `generate_summary` 已包含 `provider_requests`

### 问题

- `seedance_2_0` 目前仍走 generic request body
- 真实 live submit 仍未启用，因为环境变量尚未配置

### 下一步

- 若继续接真实平台，优先细化 `Kling` 的 live request payload
- 若继续本地闭环，优先增强 `AI Judge`

## 2026-03-19 Round 18

### 改动

- 运行 `moviegen doctor`
- 运行新的 `all --dry-run`
- 验证：
  - `provider_requests.json`
  - `generate_summary`
  - `candidate_clips`
  - `judge_scores`

### 效果

- 当前 `doctor` 已能明确显示：
  - `Kling` 为默认主 provider
  - `Vidu` 为默认可选替换项
  - 相关环境变量是否就绪
- 最新全链路 provider 验证基线：
  - `run_20260319_152023_f9c4c04a`
- 已确认 `generate_summary` 中包含：
  - `provider_requests`
  - 每个请求的 `mode / status / request / response / error`
- 已确认 `workspace/jobs/run_20260319_152023_f9c4c04a__provider_requests.json` 成功落盘

### 问题

- 当前 request body 仍偏保守，只能视作“统一外发载荷草案”
- `seedance_2_0` 暂时仍走 generic provider request 结构

### 下一步

- 若继续接真实平台，优先把 `Kling` 的 live submit 细化到真实字段映射
- 若继续增强本地闭环，优先提升 `AI Judge` 的判定质量

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

## 2026-03-19 Round 17

### 改动

- 补强 `generate` 的 `Kling-first` live 提交流程
  - 以 `shot_id` 聚合 `generation_jobs`
  - live 模式下按 `submission_strategy` 生成提交尝试序列
  - 默认主提交通道为 `Kling`，可选替换通道为 `Vidu`
- 为 live 提交补上状态回写
  - `generation_jobs.status` 现在会回写为 `submitted / not_configured / unsupported_provider / suppressed_by_strategy` 等真实状态
  - `external_job_id` 会在成功提交时回写到数据库
- 修正 `judge` 的候选读取范围
  - `candidate` 文件名改为带 `run_id`
  - `judge` 只读取当前 run 的候选，而不是扫全局 `workspace/candidates`
- 修正 live 提交后的 judge 行为
  - 只有 `ready / ready_for_judge` 候选会进入 heuristic judge
  - `provider_submission_receipt` 类型不会被误判为可评审成片
- 修正 provider 适配解析
  - `kling_3_0` 固定走 `KlingAdapter`
  - `vidu_q3` 固定走 `ViduAdapter`
  - 其他 provider 在 live 模式下明确返回 `unsupported_provider`，不再伪装成可提交成功
- 补充 run summary
  - 输出 `execution_primary_provider / execution_optional_provider / execution_live_mode / execution_submission_strategy`

### 验证

- 运行 `python -m compileall moviegen`
- 运行默认 dry-run：
  - `python -m moviegen.cli run config/project.example.yaml --stage all --dry-run`
  - run_id: `run_20260319_215425_91db3ff8`
- 运行临时 live 配置 dry-run：
  - `python -m moviegen.cli run tmp/project.live.test.yaml --stage all --dry-run`
  - run_id: `run_20260319_215436_846266c4`
- 检查：
  - `workspace/reports/run_20260319_215425_91db3ff8__generate_summary.json`
  - `workspace/review/run_20260319_215425_91db3ff8__judge_scores.json`
  - `workspace/reports/run_20260319_215436_846266c4__generate_summary.json`
  - `workspace/review/run_20260319_215436_846266c4__judge_scores.json`
  - `python -m moviegen.cli status --run-id run_20260319_215436_846266c4`

### 效果

- 默认 dry-run 仍保持最小闭环：
  - `prompt_packets -> generation_jobs -> mock candidates -> judge_scores`
- live 模式在未配置 `MOVIEGEN_KLING_SUBMIT_URL / MOVIEGEN_KLING_TOKEN` 时会稳定返回：
  - `not_configured`
  - 且不会生成可进入 judge 的伪候选
- 本轮 live 验证中，数据库里的 `generation_jobs` 已出现预期状态：
  - rank1 job: `not_configured`
  - 其余未执行 job: `suppressed_by_strategy`
- `judge` 现在按 run 隔离，不会再误扫历史 run 的候选文件

### 问题

- 当前 live 提交只做到“提交请求 + 回写状态 + 生成提交回执”，尚未实现：
  - provider polling
  - result download
  - 真正视频文件落盘后的 judge
- `primary_only` 策略下，A 档非 `Kling` 路由镜头仍会被重映射到 `Kling`
  - 这能保证主通道统一
  - 但不等于 provider-specific prompt 已完全针对 `Kling` 重编译

### 下一步

- 接 `Kling` 的 polling / fetch-result 最小闭环
- 把 `provider_submission_receipt -> downloaded candidate clip` 串起来
- 再让 `judge` 在拿到真实媒体后恢复评分

## 2026-03-19 Round 18

### 改动

- 为 `Kling-first` provider 补上最小 `submit -> poll -> download` 闭环
  - `ProviderAdapter` 现在支持 `poll()` 与 `download()`
  - `KlingAdapter / ViduAdapter` 增加 `POLL_URL_TEMPLATE` 轮询能力
  - 下载结果会落到 `workspace/downloads/`
- 扩展 `execution` 配置
  - `poll_after_submit`
  - `poll_max_attempts`
  - `poll_interval_sec`
- 扩展 `doctor`
  - 检查 `MOVIEGEN_KLING_POLL_URL_TEMPLATE`
  - 检查 `MOVIEGEN_VIDU_POLL_URL_TEMPLATE`
- 强化 `generate`
  - live 模式下在成功 submit 后执行 polling
  - polling 完成后尝试下载媒体文件
  - 下载成功时生成 `candidate_media` artifact，并把候选状态提升到 `ready_for_judge`
  - `provider_requests` 现在带 `phase=submit|poll|download`
- 修正本地回环请求
  - 对 `127.0.0.1 / localhost` 显式绕过系统代理，避免本地 fake provider 被代理链污染成 `HTTP 502`
- 修正 `generation_jobs` 回写
  - attempted job 会把实际执行 provider 回写到数据库
  - 使 `downloaded / processing / provider_failed` 等状态与真实执行 provider 对齐
- 调整 `judge` 文案
  - 改为 `Computed heuristic judge scores for judge-ready candidates.`

### 验证

- 运行 `python -m compileall moviegen`
- 使用本地 fake provider 服务验证 live 闭环
  - `tmp/fake_provider_server.py`
  - `tmp/project.live.mockserver.yaml`
- 先验证 fake provider 自身：
  - `Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8765/submit'`
- 再运行 live dry-run：
  - `python -m moviegen.cli run tmp/project.live.mockserver.yaml --stage all --dry-run`
  - 最终验证 run_id: `run_20260319_221852_ce5e326c`
- 检查：
  - `workspace/reports/run_20260319_221852_ce5e326c__generate_summary.json`
  - `workspace/review/run_20260319_221852_ce5e326c__judge_scores.json`
  - `workspace/downloads/`
  - `generation_jobs` SQLite 状态回写

### 效果

- 这轮 live 闭环已真实跑通：
  - `submit -> poll -> download -> ready_for_judge -> judge`
- `run_20260319_221852_ce5e326c` 的关键结果：
  - `candidate_count = 3`
  - `ready_candidate_count = 3`
  - `provider_request_status_counts = { submitted: 3, completed: 3, downloaded: 3 }`
- `workspace/downloads/` 已真实落盘 3 个媒体文件
- `judge` 已对 3 个 `ready_for_judge` 候选生成 heuristic 分数
- SQLite 中已确认 attempted job 的实际 provider 与状态回写正确：
  - `kling_3_0 + downloaded`
  - 未实际执行的备选 job 保持 `not_attempted_after_success`

### 问题

- 当前还是“最小 provider 闭环”，并非完整生产链：
  - 没有 provider webhook / 长轮询
  - 没有失败重试退避
  - 没有真实媒体内容分析 judge
- 当一个原计划 `seedance_2_0` job 被重映射到 `Kling` 执行时，数据库中的该 job 现在会记录为实际执行 provider
  - 这更利于运行态排障
  - 但如果后面要同时保留“计划 provider”和“执行 provider”，还需要单独加字段

### 下一步

- 为 `generate` 增加真正的 `retry / backoff / fallback to Vidu`
- 为 live candidate 增加更细的 `media_probe` 与基础媒体校验
- 再决定是否把 `post` 从 placeholder 提升为真实后处理入口

## 2026-03-19 Round 19

### 改动

- 为 live 提交增加最小重试能力
  - `submit_with_retries()`
  - `download_with_retries()`
  - 当前复用 `workflow.max_api_retries` 作为 submit/download 最大尝试次数
- 为下载产物增加最小 `media_probe`
  - 收集 `path / exists / file_size_bytes / suffix / sha256`
  - 若本机可用 `ffprobe`，则进一步读取 `duration / width / height / codec_name / stream_count`
  - probe 结果写入 `.probe.json` 并登记为 `candidate_media_probe` artifact
- 完整打通 `Kling -> Vidu` live 回退链路
  - 示例配置 `config/project.example.yaml` 改为 `primary_with_optional_fallback`
  - 当 `Kling` 未配置或提交失败时，可自动尝试 `Vidu`
- 修正 job 状态回写
  - attempted job 会把实际执行 provider/provider_model 覆盖写回 `generation_jobs`
  - 避免“计划 provider”和“实际执行 provider”混淆运行态排障
- 修正本地 fake provider 验证环境
  - 保持 `127.0.0.1 / localhost` 绕过系统代理
  - 使 fake provider 的 submit/poll/download 验证稳定可复现

### 验证

- 运行 `python -m compileall moviegen`
- 使用 fake provider 验证 `Kling` 成功闭环：
  - run_id: `run_20260319_221852_ce5e326c`
- 使用 fake provider 验证 `Kling -> Vidu` fallback 闭环：
  - `MOVIEGEN_KLING_*` 置空
  - `MOVIEGEN_VIDU_*` 指向 fake provider
  - run_id: `run_20260319_222428_a4c2afbf`
- 检查：
  - `workspace/reports/run_20260319_221852_ce5e326c__generate_summary.json`
  - `workspace/review/run_20260319_221852_ce5e326c__judge_scores.json`
  - `workspace/reports/run_20260319_222428_a4c2afbf__generate_summary.json`
  - `workspace/review/run_20260319_222428_a4c2afbf__judge_scores.json`
  - SQLite `generation_jobs` 实际 provider / status 回写

### 效果

- `Kling` 成功链路已稳定为：
  - `submit -> poll -> download -> media_probe -> ready_for_judge -> judge`
- `Kling -> Vidu` 回退链路也已跑通：
  - 当 `Kling` 未配置时，系统会自动切到 `Vidu`
  - fallback run `run_20260319_222428_a4c2afbf` 中，3 个镜头都由 `vidu_q3` 下载成功并进入 judge
- fallback run 的关键结果：
  - `candidate_count = 3`
  - `ready_candidate_count = 3`
  - `provider_request_status_counts` 覆盖了 `not_configured / submitted / completed / downloaded`
- 每个下载候选现在都带：
  - `media_artifact_path`
  - `media_probe`
  - `.probe.json` artifact

### 问题

- `media_probe` 当前仍是“最小探测”，尚未形成真正的媒体质量门控
  - 在没有 `ffprobe` 的机器上，只能退化到文件级元数据
- 当前 fallback 是“provider 级补位”，还不是“prompt/compiler 级重编译后再补位”
  - 现在是沿用当前 packet 并重映射 provider
  - 后面如果做更强 provider-specific 控制，最好在 fallback 时重编译 prompt packet

### 下一步

- 给 live `generate` 增加 `provider-specific fallback reason` 与更清晰的 attempt summary
- 给下载后的 candidate 增加基础 `media_gate`
  - 例如大小异常、探测失败、无视频流时自动标记为 review/regenerate
- 再决定是否把 `post` 从 placeholder 提升为真实后处理入口

## 2026-03-19 Round 20

### 改动

- 为 live 执行补上 `attempt_summaries`
  - 每个 `shot_id` 现在都会输出：
    - `planned_provider_chain`
    - `attempted_providers`
    - `fallback_used`
    - `fallback_trigger_reason`
    - `final_provider`
    - `final_status`
    - `judge_ready`
    - `media_gate_status`
  - 每次 attempt 也会记录 `submit_status / poll_status / download_status / final_candidate_status`
- 为 live 候选补上基础 `media_gate`
  - `evaluate_media_gate()` 根据 `media_probe` 给出 `pass / warn / fail`
  - `judge_eligible = false` 时，候选状态写为 `media_gate_failed`
  - `judge_eligible = true` 时，候选状态写为 `ready_for_judge`
- 为下载媒体新增 `candidate_media_gate` artifact
  - `*.gate.json` 会和 `*.probe.json` 一起落盘
- 为 `generate_summary` 增加统计
  - `media_gate_status_counts`
  - `gated_out_candidate_count`
  - `attempt_summaries`
- 调整 `generate` 文案
  - 当所有媒体都被 gate 挡掉时，会明确写出“downloaded but gated out before judge”

### 验证

- 运行 `python -m compileall moviegen`
- 用空文件直接验证 `media_gate fail`：
  - `tmp/empty_media.mp4`
  - 结果：`status=fail`, `judge_eligible=false`, `reason=empty_media_file`
- 继续验证 `Kling -> Vidu` fallback：
  - run_id: `run_20260319_222858_6c8be5f2`
- 检查：
  - `workspace/reports/run_20260319_222858_6c8be5f2__generate_summary.json`
  - `workspace/review/run_20260319_222858_6c8be5f2__judge_scores.json`

### 效果

- `attempt_summaries` 已真实落盘，并能解释 fallback 原因
  - 例如：`fallback_trigger_reason = kling_3_0:not_configured`
- fallback run 中，3 个镜头都显示：
  - 第 1 次尝试：`kling_3_0 -> not_configured`
  - 第 2 次尝试：`vidu_q3 -> submitted/completed/downloaded`
- 当前 fake provider 下载文件会被 `media_gate` 标成：
  - `status = warn`
  - `judge_eligible = true`
  - warning 包含 `ffprobe_unavailable`、`tiny_media_file`
- 空文件 case 则会被 `media_gate` 直接拦住，不进入 judge

### 问题

- `media_gate` 现在仍是规则式门控，不是基于真实视频内容理解的质量判定
- 当前 fallback 说明已经足够排障，但还没有更细的 provider-specific cost/latency 归因

### 下一步

- 把 `media_gate` 的 fail/warn 结果接到 `route_back_stage` 或 `review` 决策上
- 给 `attempt_summaries` 增加成本、耗时和重试次数
- 再决定是否把 `post` 提升为真实阶段

## 2026-03-19 Round 21

### 改动

- 把 `media_gate` 真正接入 judge 决策层
  - `media_gate = warn` 时：
    - 候选仍可进入 judge
    - 若原本可通过或需人工复审，统一降级为 `decision=review`
    - `route_back_stage=review`
  - `media_gate = fail` 时：
    - 不再跳过候选，而是直接生成 hard-fail judge entry
    - `decision=regenerate_same_provider`
    - `route_back_stage=generate`
    - `hard_fail_reasons` 写入 `media_gate:*`
- 为 judge entry 增加 gate 解释字段
  - `media_gate_status`
  - `decision_reasons`
- 为 judge summary 增加统计
  - `heuristic_scored_count`
  - `media_gate_blocked_count`
  - `media_gate_warn_review_count`
- 为 generate summary 增加更清晰的 gate 后结果说明
  - 如果全部媒体都被 gate 挡住，会明确写出 `gated out before judge`

### 验证

- 运行 `python -m compileall moviegen`
- 正常小文件链路验证：
  - run_id: `run_20260319_223318_ee373951`
  - fake provider 输出小文件，触发 `media_gate=warn`
- 空文件链路验证：
  - fake provider 设置 `FAKE_PROVIDER_EMPTY_MEDIA=1`
  - run_id: `run_20260319_223356_a9224729`
  - 触发 `media_gate=fail`
- 检查：
  - 两个 run 的 `generate_summary`
  - 两个 run 的 `judge_scores`

### 效果

- `warn -> review` 已真实生效
  - `run_20260319_223318_ee373951` 中 3 个候选全部：
    - `decision=review`
    - `route_back_stage=review`
    - `decision_reasons` 含 `media_gate_warn`
- `fail -> generate` 已真实生效
  - `run_20260319_223356_a9224729` 中 3 个候选全部：
    - `hard_fail=true`
    - `decision=regenerate_same_provider`
    - `route_back_stage=generate`
    - `hard_fail_reasons` 含 `media_gate:empty_media_file`
- `attempt_summaries` 继续有效
  - 可同时解释 provider fallback 与 media gate 最终结果

### 问题

- 当前 `review` 仍是 placeholder stage，虽然决策已能回流到 `review`，但 review 阶段本身还没有真实处理逻辑
- `media_gate` 仍主要依赖文件级规则；在无 `ffprobe` 的机器上，警告会偏保守

### 下一步

- 把 `review` 从 placeholder 提升为真实阶段，至少能汇总 `media_gate_warn` 候选
- 或者把 `route_back_stage=generate/review` 真正接到 `resume` / 再执行策略里

## 2026-03-19 Round 22

### 改动

- 把 `review` 从 placeholder 提升为真实阶段
  - 读取 `judge_scores`
  - 生成 `review_summary`
  - 输出三类队列：
    - `review_candidates`
    - `regenerate_candidates`
    - `approved_candidates`
- 将 `review` 与 human gate 打通
  - gate 名称固定为 `gate_3_review`
  - 有 review 候选时：`status=waiting`
  - 只有 regenerate/approved 时：`status=approved`
  - gate payload 会写入三类 candidate ids
- `review_summary` 现在包含：
  - candidate 基本信息
  - `decision / route_back_stage / hard_fail / decision_reasons / media_gate_status`
  - 候选当前状态与媒体路径

### 验证

- 运行 `python -m compileall moviegen`
- 正常小文件链路：
  - run_id: `run_20260319_223709_0f28a433`
  - 触发 `warn -> review`
- 空文件链路：
  - run_id: `run_20260319_223746_006af55e`
  - 触发 `fail -> regenerate`
- 检查：
  - `workspace/review/run_20260319_223709_0f28a433__review_summary.json`
  - `workspace/review/run_20260319_223746_006af55e__review_summary.json`
  - `python -m moviegen.cli status --run-id ...` 中的 `gates`

### 效果

- `warn -> review queue` 已真实落地
  - `run_20260319_223709_0f28a433` 中：
    - `review_candidates = 3`
    - `gate_3_review.status = waiting`
    - `decision_summary = 3 candidates require manual review.`
- `fail -> regenerate queue` 也已真实落地
  - `run_20260319_223746_006af55e` 中：
    - `regenerate_candidates = 3`
    - `gate_3_review.status = approved`
    - 无需人工 review，但 regenerate 队列已明确输出
- `status --run-id` 现在能把真实 review gate 一并展示出来

### 问题

- `review` 目前仍是“汇总与排队”阶段，还没有真正处理人工审核动作本身
- `resume` 还没有消费 `review_summary` 或 `gate_3_review` 去做自动再执行

### 下一步

- 把 `resume` / 再执行策略接到 `review_summary` 和 `route_back_stage`
- 或者把 `gate --approve/--reject` 的结果进一步驱动后续 stage

## 2026-03-19 Round 23

### 改动

- 为 `execute_run()` 补上 `force_stage` 真实语义
  - 当 `stage=all` 且 `force_stage=plan` 时，会从 `plan` 继续跑到 `report`
- 把 `resume` 从 scaffold 提升为真实续跑入口
  - 若 `gate_3_review` 仍是 `waiting`：明确阻塞并返回 gate 信息
  - 若 gate 已决策：
    - 读取 `review_summary`
    - 合并 `review_candidates / regenerate_candidates / gate reject ids`
    - 生成 `resume_plan.json`
    - 生成过滤后的 `resume_shot_specs.yaml`
    - 生成新的 `resume_project.yaml`
    - 自动拉起 follow-up run，并从 `plan` 开始续跑
- 为原始 run 补充 resume 相关 artifact
  - `resume_plan`
  - `resume_shot_specs`
  - `resume_project_file`
- 修正 `gate` 命令细节
  - 当未显式传入 `decision_summary` 或 `reviewer` 时，保留已有 gate 信息，不再清空

### 验证

- 运行 `python -m compileall moviegen`
- 验证 waiting gate 会阻塞 resume：
  - `python -m moviegen.cli resume --run-id run_20260319_223709_0f28a433 --dry-run`
- 之后对该 gate 执行 approve/reject：
  - approve: `candidate_0735f189f361,candidate_d1efd26aa5a0`
  - reject: `candidate_615a5ff275ee`
- 再运行 resume：
  - source run: `run_20260319_223709_0f28a433`
  - follow-up run: `run_20260319_225604_8c89c386`
- 检查：
  - `workspace/review/run_20260319_223709_0f28a433__resume_plan.json`
  - `workspace/review/run_20260319_225604_8c89c386__review_summary.json`
  - `python -m moviegen.cli status --run-id run_20260319_225604_8c89c386`

### 效果

- `resume` 现在不再只是提示语，而是能真实执行“按 review/gate 结果继续跑”
- waiting gate 场景：
  - 会明确返回 `review gate is still waiting`
  - 不会误启动 follow-up run
- gate 已决策场景：
  - 会把被 reject 的 candidate 对应 shot 过滤出来
  - 本轮验证中只续跑了 `SHOT_001`
  - follow-up run `run_20260319_225604_8c89c386` 已真实从 `plan -> report` 跑完
- `gate` 命令保留摘要修复也已验证：
  - `decision_summary` 在后续 approve 时仍能保留原值 `1 candidates require manual review.`

### 问题

- 当前 `resume` 仍是“shot 级 rerun”，不是更细的 packet/job 级 rerun
- `follow-up run` 仍会重新走 `generate/judge/review`，但还不会消费 `approved_candidates` 去推进到 `post/assemble`

### 下一步

- 让 `resume` 对 `approved_candidates` 和 `approved gate` 也能继续向后推进
- 或者把 `post` 从 placeholder 提升为真正的后处理/交付前阶段

## 2026-03-19 Round 24

### 改动

- 把 `post` 从 placeholder 提升为真实阶段
  - 支持两种输入来源：
    - 当前 run 的 `review_summary`
    - `planning.approved_candidates_file`
  - 输出真实 `post_summary`
  - 区分：
    - `post_candidates`
    - `blocked_candidates`
- 扩展 `resume`
  - 现在会同时处理两类 follow-up：
    - `rerun_followup_run`：给 rejected / regenerate 的 shot 继续从 `plan` 开始跑
    - `post_followup_run`：给 approved candidates 直接从 `post` 开始跑
- 为 `resume` 生成新的 post 输入文件
  - `approved_candidates.yaml`
  - 其中包含：
    - `source_run_id`
    - `source_review_gate`
    - `approved_candidates`
- `stage_post` 现在会把 `source_review_gate` 带进 `post_summary`

### 验证

- 运行 `python -m compileall moviegen`
- 使用已审批的 source run 继续验证：
  - source run: `run_20260319_223709_0f28a433`
- 运行：
  - `python -m moviegen.cli resume --run-id run_20260319_223709_0f28a433 --dry-run`
- 结果得到两条 follow-up：
  - `rerun_followup_run = run_20260319_230219_3df22c20`
  - `post_followup_run = run_20260319_230220_6f88ecdd`
- 检查：
  - `workspace/post/run_20260319_230220_6f88ecdd__post_summary.json`
  - `workspace/review/run_20260319_230220_6f88ecdd__approved_candidates.yaml`
  - `status --run-id` 两条 follow-up run

### 效果

- `resume` 不再只会“重跑被拒镜头”，现在也会“推进已批准候选到 post”
- 在本轮验证中：
  - `rerun_followup_run` 只续跑了 `SHOT_001`
  - `post_followup_run` 成功把 2 个 approved candidates 直接送进 `post`
- `post_summary` 已真实包含：
  - 2 个 `post_candidates`
  - 来源 `source_review_gate`
  - 每个 approved candidate 的媒体路径、provider、media_gate_status、score

### 问题

- `post` 现在还是“后处理前的排队与汇总”阶段，还没有执行真实超分、补帧、口型、调色等处理
- `source_review_gate` 是否保留原 `decision_summary`，取决于历史 gate 数据本身；旧 gate 若已被清空摘要，当前只能如实透传 null

### 下一步

- 把 `post` 提升为真正的后处理入口
- 或者把 `approved_candidates` 继续送入 `assemble`，形成最小交付链路

## 2026-03-19 Round 25

### 改动

- 把 `assemble` 从 placeholder 提升为真实阶段
  - 消费 `post_summary`
  - 输出三类真实产物：
    - `timeline_manifest.json`
    - `delivery_manifest.json`
    - `assembly_summary.json`
- `assemble` 现在会整理：
  - `timeline_items`
  - `delivery_items`
  - `blocked_items`
- 对每个可交付候选生成稳定交付文件名
  - 形式：`001__SHOT_ID__candidate_id.ext`
- 对缺失媒体的候选会进入 `blocked_items`
  - 便于后续交付前排障

### 验证

- 运行 `python -m compileall moviegen`
- 直接使用现有 post project 继续验证：
  - `python -m moviegen.cli run workspace/review/run_20260319_230220_6f88ecdd__post_project.yaml --stage all --force-stage post --dry-run`
  - run_id: `run_20260319_230940_377a6d2c`
- 检查：
  - `workspace/assemble/run_20260319_230940_377a6d2c__timeline_manifest.json`
  - `workspace/assemble/run_20260319_230940_377a6d2c__delivery_manifest.json`
  - `workspace/assemble/run_20260319_230940_377a6d2c__assembly_summary.json`
  - `status --run-id run_20260319_230940_377a6d2c`

### 效果

- `post -> assemble -> report` 最小交付链已跑通
- `run_20260319_230940_377a6d2c` 中：
  - `timeline_items = 2`
  - `delivery_items = 2`
  - `blocked_items = 0`
- `delivery_manifest` 已真实包含：
  - source post summary
  - source review gate
  - 每个交付项的稳定文件名、来源媒体路径、provider、score
- `assembly_summary` 已真实包含：
  - 时间线排序后的候选列表
  - 可交付项列表
  - 被阻塞项列表

### 问题

- `assemble` 现在还是 manifest 层，不会真正复制或导出交付文件到独立 release 目录
- `report` 仍是 placeholder；虽然 run summary 已经存在，但还没有单独的“交付报告”阶段逻辑

### 下一步

- 给 `assemble` 增加真正的 release/export 目录产物
- 或者把 `report` 从 placeholder 提升为真实交付报告阶段

## 2026-03-19 Round 26

### 改动

- 把 `report` 从 placeholder 提升为真实阶段
  - 消费 `assemble` 产物
  - 输出：
    - `delivery_report.json`
    - `delivery_report.md`
- `report` 现在会整合：
  - `post_summary`
  - `assembly_summary`
  - `delivery_manifest`
  - `timeline_manifest`
  - 当前 run 的 gate 状态
- 报告内容现在包含：
  - deliverable 数量
  - blocked item 数量
  - timeline 数量
  - `next_actions`
  - 每个 deliverable 的文件名、shot、provider、score、gate 状态
- Markdown 报告也同步生成，便于人工快速浏览

### 验证

- 运行 `python -m compileall moviegen`
- 使用现有 post project 继续验证：
  - `python -m moviegen.cli run workspace/review/run_20260319_230220_6f88ecdd__post_project.yaml --stage all --force-stage post --dry-run`
  - run_id: `run_20260319_231237_75acc19b`
- 检查：
  - `workspace/reports/run_20260319_231237_75acc19b__delivery_report.json`
  - `workspace/reports/run_20260319_231237_75acc19b__delivery_report.md`
  - `status --run-id run_20260319_231237_75acc19b`

### 效果

- `post -> assemble -> report` 最小交付链已真实闭合
- `run_20260319_231237_75acc19b` 中：
  - `deliverables = 2`
  - `blocked_items = 0`
  - `timeline_items = 2`
- `delivery_report.json` 已真实包含：
  - source post summary / assembly summary / delivery manifest / timeline manifest
  - source review gate
  - deliverables 列表
  - next actions
- `delivery_report.md` 已真实生成可读摘要，便于快速人工检查

### 问题

- `report` 现在仍是“交付报告与汇总”层，不会真正输出 release 目录或复制媒体文件
- 旧 gate 若历史上已丢失 `decision_summary`，当前报告只能如实显示 null

### 下一步

- 给 `assemble` 或 `report` 增加真实 `release/export` 目录
- 或者继续把 `post` 提升为真实媒体后处理阶段

## 2026-03-19 Round 27

### 改动

- 为 `report` 增加真实 `release/export` 输出
  - 导出目录：`workspace/release/<run_id>/`
  - 结构包括：
    - `media/`
    - `docs/`
    - `release_manifest.json`
- `report` 现在会：
  - 复制每个 deliverable 的媒体文件到 `release/media/`
  - 复制关键文档到 `release/docs/`
    - `delivery_report.json`
    - `delivery_report.md`
    - `assembly_summary.json`
    - `delivery_manifest.json`
    - `timeline_manifest.json`
    - `post_summary.json`
- 生成真实 `release_manifest.json`
  - 记录 exported media、copied docs、blocked items
- `delivery_report.json` 现在也会包含：
  - `release_export.release_dir`
  - `exported_media_count`
  - `copied_docs_count`
  - `release_manifest_path`
- `delivery_report.md` 同步补充 `Release Export` 小节

### 验证

- 运行 `python -m compileall moviegen`
- 使用现有 post project 继续验证：
  - `python -m moviegen.cli run workspace/review/run_20260319_230220_6f88ecdd__post_project.yaml --stage all --force-stage post --dry-run`
  - run_id: `run_20260319_232422_3fa0771f`
- 检查：
  - `workspace/reports/run_20260319_232422_3fa0771f__delivery_report.json`
  - `workspace/release/run_20260319_232422_3fa0771f/release_manifest.json`
  - `Get-ChildItem -Recurse workspace/release/run_20260319_232422_3fa0771f`
  - `status --run-id run_20260319_232422_3fa0771f`

### 效果

- 现在 `post -> assemble -> report -> release/export` 最小交付链已真实闭合
- `run_20260319_232422_3fa0771f` 中：
  - `exported_media_count = 2`
  - `copied_docs_count = 6`
  - `blocked_items_count = 0`
- release 目录已真实包含：
  - 2 个媒体文件副本
  - 6 份关键文档副本
  - `release_manifest.json`
- `delivery_report` 的 `next_actions` 现在会直接指向 release 目录，便于交付检查

### 问题

- 当前 export 是“复制式 release”，还不是更复杂的发布机制
  - 没有压缩包
  - 没有 checksum 清单分发格式
  - 没有正式的版本号语义
- 媒体文件当前按 manifest 中的稳定文件名导出，但还没有做冲突检测之外的更强 release 规范

### 下一步

- 如果继续推进，最自然的是给 release 目录增加 zip/export 包
- 或者补真正的 versioned delivery manifest / checksum 清单

## 2026-03-19 Round 28

### 改动

- 为 `report -> release/export` 再补两类正式交付产物
  - `workspace/release/<run_id>.zip`
  - `workspace/release/<run_id>__checksums.json`
- checksum 清单现在会覆盖整个 release 目录内的文件
  - `media/`
  - `docs/`
  - `release_manifest.json`
- `delivery_report.json` 现在新增：
  - `release_export.checksums_manifest_path`
  - `release_export.zip_path`
  - `release_export.zip_sha256`
- `delivery_report.md` 也新增 `Release Export` 信息：
  - release 目录
  - checksum 清单
  - zip 包路径
  - zip SHA256
- `status --run-id` 中的 artifact 现在也会包含：
  - `release_checksums`
  - `release_zip_archive`

### 验证

- 运行 `python -m compileall moviegen`
- 使用现有 post project 再跑一轮：
  - `python -m moviegen.cli run workspace/review/run_20260319_230220_6f88ecdd__post_project.yaml --stage all --force-stage post --dry-run`
  - run_id: `run_20260319_232659_bcdbb059`
- 检查：
  - `workspace/reports/run_20260319_232659_bcdbb059__delivery_report.json`
  - `workspace/release/run_20260319_232659_bcdbb059__checksums.json`
  - `workspace/release/run_20260319_232659_bcdbb059.zip`
  - `status --run-id run_20260319_232659_bcdbb059`

### 效果

- 现在 release/export 已形成完整三件套：
  - release 目录
  - checksum 清单
  - zip 包
- `run_20260319_232659_bcdbb059` 中：
  - `exported_media_count = 2`
  - `copied_docs_count = 6`
  - `zip_sha256 = 51b85ecd9e5259fe837467e4e1abcf4d86a01434338bcdf432180c739967a79e`
- `release_checksums.json` 已真实列出 release 目录下每个文件的 sha256 和大小
- `delivery_report.json` 的 `next_actions` 现在会直接指向：
  - release 目录
  - checksum 清单
  - zip 包

### 问题

- 当前 zip/export 还是单机本地交付形式，没有版本号策略和多版本保留规则
- checksum 清单目前是 JSON，不是更常见的 `.sha256` 文本格式；如果后续要给外部流水线消费，可能还需要追加一种文本输出

### 下一步

- 如果继续推进，最自然的是给 release 再补：
  - `.sha256` 文本校验文件
  - versioned release naming
  - 或真正的 post-processing 阶段

## 2026-03-19 Round 29

### 改动

- 为 release/export 增加版本化命名
  - 规则：`<project_id>__vNNN__<run_id>`
  - 当前按 `workspace/release/` 下已有同项目 release 自动递增版本号
- 增加 `.sha256` 文本校验文件
  - 路径：`workspace/release/<release_name>.sha256`
  - 内容格式：`<sha256> *<relative_path>`
- 扩展 `delivery_report.json`
  - 新增：
    - `release_export.release_name`
    - `release_export.release_version`
    - `release_export.checksums_text_path`
- 扩展 `delivery_report.md`
  - `Release Export` 小节新增：
    - release name
    - release version
    - checksum text path
- zip 包现在也按 versioned release name 命名

### 验证

- 运行 `python -m compileall moviegen`
- 再跑一轮 post -> report：
  - `python -m moviegen.cli run workspace/review/run_20260319_230220_6f88ecdd__post_project.yaml --stage all --force-stage post --dry-run`
  - run_id: `run_20260319_232940_54e9c3f3`
- 检查：
  - `workspace/reports/run_20260319_232940_54e9c3f3__delivery_report.json`
  - `workspace/release/moviegen_scifi_001__v001__run_20260319_232940_54e9c3f3.sha256`
  - `workspace/release/moviegen_scifi_001__v001__run_20260319_232940_54e9c3f3.zip`
  - `status --run-id run_20260319_232940_54e9c3f3`

### 效果

- release/export 现在形成更完整的交付集合：
  - versioned release dir
  - release manifest
  - JSON checksums manifest
  - `.sha256` 文本校验文件
  - zip 包
- `run_20260319_232940_54e9c3f3` 中：
  - `release_name = moviegen_scifi_001__v001__run_20260319_232940_54e9c3f3`
  - `release_version = v001`
  - `zip_sha256 = 865272b74a34a83c33473222e965648382cb7f3818762f1c9389ae9cc4f48bc8`
- `.sha256` 文本已经真实列出 release 目录内每个文件的 sha256
- `delivery_report.next_actions` 现在会同时指向：
  - versioned release dir
  - checksums json
  - checksums text
  - zip 包

### 问题

- 当前版本号是基于本地 release 目录扫描递增，适合单机工作流，但还不是跨机器共享的版本源
- `.sha256` 文本当前只覆盖 release 目录内容，不额外列 zip 本身；如果后续交付端有需要，可以再补 zip 的单独校验文件

### 下一步

- 如果继续推进，最自然的是再补一个 `zip.sha256` 单文件
- 或者开始进入真正的 `post` 媒体后处理实现
