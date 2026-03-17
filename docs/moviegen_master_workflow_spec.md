# MovieGen 总说明与工程级 Gen-Workflow 规范

初版研究日期：2026-03-16；搜索复核日期：2026-03-17  
工作目录：`D:\Gits\MovieGen_workflow`  
主参考文件：`NewChat-Monica_AI_Chat.pdf`

## 1. 项目目标、约束与结论摘要

### 1.1 目标

本规范面向一个明确目标：在个人级预算约束下，设计一套能够支撑约 120 分钟真人科幻电影生产的 AIGC 工作流。目标影片的审美与叙事气质应尽量靠近 2000-2015 年间的写实科幻电影，而不是 2024 之后常见的短视频式、过饱和、强炫技、弱连续性的 AI 视频风格。

项目不追求“所有镜头都由单一模型直接生成”，而是追求以下四个结果同时成立：

1. 视觉上能够稳定复用角色、场景、服装、道具和摄影语法。
2. 叙事上能够在 120 分钟尺度内保持连续性与可理解性。
3. 工程上能够批处理、一键执行、断点续跑，并保留必要的人类导演卡点。
4. 预算上总开销控制在个人级别，推荐上限为 `< $800`。

### 1.2 核心约束

- 成片尺度：约 120 分钟。
- 类型：真人感、写实向科幻。
- 预算：推荐总预算 `< $800`。
- 执行环境：单人 Windows 工作站发起，混合云执行。
- 自动化目标：尽可能“一键执行”，但必须保留样片确认、镜头入选、序列锁定、终剪确认四类人工卡点。
- 事实来源策略：对“最新”“价格”“可用性”“版本”这类时效信息，一律以 2026-03-16 当日官方页面、官方价格页、官方发布页为准；中文与英文网页都记录；搜索引擎受限时明确写明阻断情况。

### 1.3 结论摘要

结论可以先压缩成一句话：  
**要在 `< $800` 预算内尽可能做出高质量 120 分钟真人科幻长片，唯一现实方案不是“买最强模型”，而是“把长片拆成可控资产、可控镜头、可控路由、可控评判的混合工作流”。**

因此，本规范的总策略是：

- 不把单一视频模型当成全片总引擎。
- 先做 `Reference Ingest -> Bible -> ShotSpec -> Prompt Compiler -> Provider Router -> Judge -> Human Gate -> Post -> Assembly` 的工程链路。
- 以 `A/B/C` 镜头分级控制预算，而不是平均用力。
- 把 `Reference Ingest` 固定定义为同时支持 `视频 + 图片 + 文本注释` 的一等输入。
- 把提示词系统固定定义为“模块化语义模板 + provider-specific 自动改写编译”，而不是“人工给每个模型手写提示词”。

---

## 2. 对 PDF 关键观点的审查

以下判断基于对 [NewChat-Monica_AI_Chat.pdf](D:/Gits/MovieGen_workflow/NewChat-Monica_AI_Chat.pdf) 的通读。该 PDF 的主线是正确的，但存在明显的时间滞后、若干绝对化判断，以及对 2026 年工具版图的低估。

### 2.1 总体评价

这份 PDF 的最大优点是没有掉入“文生视频一把梭”的误区，而是把问题识别成“资产控制 + 一致性控制 + 后期控制”的系统工程。  
这份 PDF 的最大缺点是把若干 2024-2025 年有效的经验，表述成了 2026 年仍然成立的“唯一解”“工业标准”。

### 2.2 逐条审查

| PDF 观点 | 判断 | 2026-03-16 审查结论 |
|---|---|---|
| 生成 120 分钟长片必须采用混合工作流，不能依赖单一文生视频模型 | 准确 | 这是 PDF 中最正确的判断，仍然成立。 |
| 长片核心难点不在于画面质量，而在于一致性控制 | 准确 | 仍然成立，而且比 2025 年更明显。 |
| 同场景复用应引入 3D/伪 3D 代理场景 | 部分准确 | 成立，但 2026 年不必把“Luma 场景重建”当唯一入口。Blender 白模、全景投影、深度估计、几何代理都可行。 |
| 角色一致性应主要依靠 LoRA | 已过时 | 2026 年 LoRA 仍然有价值，但不再是默认起点。多参考图、角色参考、统一 bible、表演驱动已显著增强，LoRA 更适合作为第二道保险。 |
| Kling / Runway Gen-3 Alpha 是视频主力模型 | 已过时 | 现在应按 `Veo 3.1 / Veo 3.1 Fast / Veo 3 Fast / Runway Gen-4.5 / Gen-4 / Act-Two / Seedance 2.0 / Hailuo 当前系列 / Vidu / Kling` 的组合来重新判断。 |
| Luma 是从视频生成场景 3D 的工业标准工具 | 过度绝对 | Luma 仍有价值，但不应写成唯一高质量闭环。它更适合场景代理、视角参考、多模型对比，而不是全片唯一核心。 |
| 视频直接转高质量、可编辑、可表演的人物 3D 模型仍不可依赖 | 基本准确 | 这一判断仍然成立。公开可用工具离“电影级近景表演 3D 数字人”还有明显距离。 |
| 对话镜头可以采用“先画面、后口型/表演修正” | 准确 | 这一策略在低预算下依旧是最稳路线。 |
| 结构化提示词系统是长片逻辑连贯的必要条件 | 准确 | 但需要升级为“Prompt Spec + Prompt Blocks + Provider Compiler”，而不只是手写结构化提示词。 |

### 2.3 必须纠正的旧结论 -> 新结论

#### 旧结论：`Veo` 以 `Veo 2` 为推荐中心
新结论：  
2026-03-16 官方定价页已经明确列出 `Veo 3.1`、`Veo 3.1 Fast`、`Veo 3`、`Veo 3 Fast`、`Veo 2`。因此推荐中心必须迁移到 `Veo 3.1 / Veo 3.1 Fast / Veo 3 Fast`，`Veo 2` 仅作为兼容和控制型参考。

#### 旧结论：`Runway` 主要看 `Gen-3`
新结论：  
2026-03-16 官方价格页显示 Runway 当前公开产品面向视频生产时，至少应把 `Gen-4.5`、`Gen-4`、`Act-Two` 一并纳入判断。`Gen-3` 不应再作为文档的主叙述对象。

#### 旧结论：`LoRA 是唯一成熟路径`
新结论：  
LoRA 仍然有价值，但应降级为“可选增强器”。默认路径应先依靠 `Reference Ingest + CharacterBible + 统一参考图策略 + provider-specific subject consistency`，只有当跨镜头漂移仍严重时，再给主角补 LoRA。

#### 旧结论：`Luma 是唯一场景闭环`
新结论：  
Luma 是候选场景代理工具之一。对于重复室内场景，`Blender 白模 + 深度/法线代理 + 参考图一致性` 在很多情况下更可控，尤其适合个人创作者。

#### 旧结论：只要换对模型，就能在预算内做 120 分钟
新结论：  
预算内可做，但前提是剧作结构配合工作流。必须收缩为少场景、强对白、有限大场面、可复用空间、可控角色数的片型。

---

## 3. 2026-03-16 工具研究快照

本节所有“事实层”优先使用官方来源。  
对于搜索引擎，采用以下策略：

- `Bing`：用于检索线索，但像 `Veo` 这样的词会被 unrelated sports/brand 结果污染。
- `Baidu`：本环境下多次触发安全验证或网络不给力页，无法稳定获取结果页。
- `Google`：本环境下多次触发验证码，仅能部分使用。

因此，本节 factual layer 最终以官方英文/中文页面为主，搜索引擎只作为附录中的检索说明。

### 3.1 商业视频主力模型矩阵

| 工具/平台 | 2026-03-16 事实层 | 推荐角色 | 自动化适配判断 | 风险 |
|---|---|---|---|---|
| `Veo 3.1 / Veo 3.1 Fast / Veo 3 / Veo 3 Fast / Veo 2` | Google Vertex AI 官方定价页可见；`Veo 3.1`、`Veo 3.1 Fast`、`Veo 3`、`Veo 3 Fast` 与 `Veo 2` 均在当前价格表中出现 | 英雄镜头、关键设定镜头、少量高价值画面 | 强，适合作为正式 provider | 单秒价格高，不能作为全片主池 |
| `Runway Gen-4.5 / Gen-4 / Act-Two` | Runway 官方定价页可见；`Gen-4.5`、`Gen-4`、`Act-Two` 都已进入公开计划描述 | 高一致性画面、角色表演、性能捕捉式补强 | 强，适合作为商业主力 provider | 需严控 credits 消耗 |
| `Seedance 2.0` | ByteDance Seed 官方中英页面可见；存在性明确 | 主叙事镜头生产第一梯队、复杂任务与多镜头叙事候选 | 中到强，能力可纳入路由层 | 公开页面更偏产品展示，自动化可用性需按实际接口再核验 |
| `Kling 3.0 系列` | 受控浏览器复核到官方开发者页明确写有 `API Platform`、`Documentation`、`Pricing`，并写明 `The Kling 3.0 Series Models API Is Now Fully Available` | 主叙事镜头生产第一梯队、常规镜头比稿与高可控任务候选 | 强，可接入且开发者定位明确 | 前台展示与促销价并不等于长期稳定单价，落地前应核对控制台 |
| `Vidu / Vidu Q3` | 官方中文价格页可见当前 `免费 / 标准 8 / 专业 28 / 旗舰 79` 档位；官方 `Reference to Video` 功能页明确支持 `up to 7 reference images`；官方 `Vidu Q3` 页面明确强调 16 秒音视频直出、多语言输出与多人对话 | 中低成本一致性镜头、参考图驱动镜头、叙事型中短镜头 | 强，适合作为 B/C 池候选 | 中文/英文价格页和旧 hydration 价格可能不同，落地前应以当前地区页为准 |
| `Hailuo 当前系列` | 受控浏览器复核到的官方首页当前主推 `MiniMax Hailuo 2.3 / 2.3 Fast`，并显示入门价 `低至 $9.99 / 月`；旧页面数据中仍可见 `Hailuo 02` 痕迹 | 中文创作语境、角色参考、导演式镜头补位 | 中到强，适合补位和比稿 | 当前官网可见主系列与旧隐藏数据并不完全一致，落地前应优先按前台可见版本规划 |
| `Luma` | 官方价格页可见 `Plus $30 / Pro $90 / Ultra $300` | 场景代理、局部镜头试验、比较池 | 中，适合局部接入 | 不应担任全片唯一主干 |
| `Sora` | 受控浏览器复核到的 OpenAI Help Center 页面可直接证实：当前文章仅适用于 `Sora 1 on Web`，`Sora 1 web` 正在被弃用，且官方引导用户转向 `Sora app / Sora for Business` | Web/App 内补位、实验性镜头、产品观察 | 弱，不建议纳入无人值守主链路 | 公开帮助中心更偏产品迁移与使用说明，而非稳定开发者自动化接口 |

### 3.2 重点工具的最新事实摘要

#### 3.2.1 Google Veo

Google Vertex AI 官方定价页当前明确列出以下条目：

- `Veo 3.1`
  - `Video + Audio generation`：720p/1080p，`$0.40/second`
  - `Video + Audio generation`：4k，`$0.60/second`
  - `Video generation`：720p/1080p，`$0.20/second`
  - `Video generation`：4k，`$0.40/second`
- `Veo 3.1 Fast`
  - `Video + Audio generation`：720p/1080p，`$0.15/second`
  - `Video + Audio generation`：4k，`$0.35/second`
  - `Video generation`：720p/1080p，`$0.10/second`
  - `Video generation`：4k，`$0.30/second`
- `Veo 3`
  - `Video + Audio generation`：720p/1080p，`$0.40/second`
  - `Video generation`：720p/1080p，`$0.20/second`
- `Veo 3 Fast`
  - `Video + Audio generation`：720p/1080p，`$0.15/second`
  - `Video + Audio generation`：4k，`$0.35/second`
  - `Video generation`：720p/1080p，`$0.10/second`
  - `Video generation`：4k，`$0.30/second`
- `Veo 2`
  - `Video generation`：720p，`$0.50/second`
  - `Advanced Controls`：720p，`$0.50/second`

直接结论：

- `Veo 2` 已不能作为推荐中心。
- 在预算有限时，`Veo 3 Fast` 比 `Veo 3.1` 更像“可用的高端候选池”。
- `Veo 3.1` 适合极少量英雄镜头，而不适合全片主池。

#### 3.2.2 Runway

Runway 官方价格页当前明确给出：

- 标题层面：`AI Image and Video Pricing from $12/month`
- 计划层面：`Free / Standard / Pro / Unlimited`
- 模型层面：公开写入 `Gen-4.5 (Text to Video)`、`Gen-4 (Image to Video)`、`Act-Two (Performance Capture)`，同时还列有 `Veo 3.1 / Veo 3`

直接结论：

- Runway 当前的价值不只是“生成视频”，更是“生成 + 表演补强 + 多模型聚合入口”。
- 对于你要做的长片，对话与人物表演部分，`Act-Two` 的存在使 Runway 的地位高于 2025 年的单纯生成器。

#### 3.2.3 Seedance 2.0

ByteDance Seed 官方中英文页面都能明确看到 `Seedance 2.0` 的存在。  
虽然公开产品页没有像 Vertex 一样给出完整、结构化、可程序化的价格表，但它已经足以证明：

- 这是当前需要被纳入对比的主流视频模型之一。
- 在文档里不应再把它当“补充工具”，而应视作中文生态下的重要候选。

文档里的处理方式应是：

- 把 `Seedance 2.0` 写进主力矩阵。
- 事实层只写官方页面能证实的内容。
- 对“开放 API 形态、单任务成本、并发与配额细则”标记为“落地前复核项”。

关于“模型表现”这一条线，在 2026-03-17 的受控浏览器深挖中，还可以进一步确认：

- 官方页当前能直接证明的 performance 口径，主要来自其内部 benchmark：`SeedVideoBench-2.0`
- 官方文案明确写到：
  - `Featuring exceptional motion stability`
  - `Model Performance`
  - `Seedance 2.0 is in the leading position in various dimensions across different types of tasks`
- 但在当前直接可读取的第三方基准页中，`Artificial Analysis` 的视频模型比较页前台可见项里，出现的是 `Seedance 1.5 Pro`，而不是 `Seedance 2.0`

这意味着：

- `Seedance 2.0` 的“表现强”目前可以被官方页强力主张，尤其在多模态输入、导演式控制和多镜头叙事组织能力上处于高位
- 虽然其第三方公开 benchmark 透明度仍弱于 `Kling 3.0`，但在“复杂任务 / 多镜头叙事 / 长时序组织”这一维度上，仍应被视为第一梯队候选
- 因此在工程上，`Seedance 2.0` 不应被放入次一级候选池，而应与 `Kling 3.0` 一起进入最高优先级 benchmark 阶段

#### 3.2.4 Kling

在 2026-03-17 的受控浏览器复核中，`https://klingai.com/global/dev` 官方开发页当前直接可见：

- `API Platform`
- `Documentation`
- `Pricing`
- `The Kling 3.0 Series Models API Is Now Fully Available`
- 视频接口能力列举：`Text To Video`、`Image To Video`、`Video Extension`、`Lip Sync`、`Video Effects`、`Elements Reference`
- 图像接口能力列举：`Text To Image`、`Image To Image`
- 智能场景能力列举：`Virtual Try-On`

同时，官方会员计划页当前前台可见：

- `Standard $6.99 / Month`
- `Pro $25.99 / Month`
- `Premier $64.99 / Month`
- `Ultra $127.99 / Month`
- 计划权益中明确出现 `1080p Video Generation`
- 计划权益中明确出现 `Video extension`
- 说明文字明确写到：视频拓展可 `up to a maximum of 3 minutes`

这说明 Kling 已不能只被视作“网页端创作工具”，而应被视为：

- 有正式开发平台入口
- 有官方文档与 pricing 入口
- 有明确版本锚点 `Kling 3.0 Series`
- 可以进入工程化 provider router 的一线候选

关于“模型表现”这一条线，在 2026-03-17 的受控浏览器深挖中，还获得了比 `Seedance 2.0` 更强的第三方支撑：

- `Google` 搜索结果页可直接读到：
  - `Kling VIDEO 3.0 "Motion Control" Feature Upgrade`
  - 其中的精选摘要引用了官方 release note 口径，写到：
    - 相比 `Wan2.2-Animate (Move Mode)`，overall win-rate `404%`
    - 相比 `Runway Act-Two`，overall win-rate `1667%`
    - 相比 `Dreamina Mimic Motion (DreamActor 1.5)`，overall win-rate `343%`
- 受控浏览器直接读取到的 `Artificial Analysis` 视频模型比较页当前可见：
  - `Kling 3.0 1080p (Pro)` 位于当前可见质量 ELO 列表顶部，显示值 `1248`
  - `Kling 3.0 720p (Standard)` 也位于前列，显示值 `1221`
  - 在同一可见页上，`Kling 3.0 1080p (Pro)` 与 `Kling 3.0 720p (Standard)` 还出现在 generation time 与 API price 对比区

这意味着：

- 就“公开可读的第三方表现证据”而言，`Kling 3.0` 当前更强
- 但结合 `Seedance 2.0` 官方对多镜头叙事、导演式控制和多模态引用能力的主张，二者在“任务上限表现”上都应被归为第一梯队
- 在你的工作流中，更合理的写法不再是“二选一谁更高”，而是：`Kling 3.0` 与 `Seedance 2.0` 都应进入最高优先级 benchmark 阶段；其中 `Kling 3.0` 提供更强公开第三方证据，`Seedance 2.0` 提供更强复杂任务与多镜头组织能力假设

#### 3.2.5 Vidu

Vidu 官方价格页可以明确证明：

- 官方中文价格页当前可见 `免费 / 标准版 8 / 专业版 28 / 旗舰版 79` 的月费档位
- 官方 `Reference to Video` 功能页 FAQ 明确写明 `Reference to Video` 支持 `up to 7 reference images`
- 官方中文 `参考生视频` 页面明确写到：可上传 `1-7` 张参考图片或从主体库调用

在 2026-03-17 的受控浏览器复核中，Vidu 官方 `Q3` 页面还直接可见：

- `Vidu Q3，为剧而生`
- `16 秒长视频，一次生成`
- `音视频直出`
- `支持英语、日语、中文的视频输出`
- `支持自然的多角色对话`
- 场景定位明确面向 `漫剧、电影、短剧等专业叙事场景`

直接结论：

- `Vidu` 对“一致性镜头”比对话中的泛泛印象更重要。
- `Vidu` 已不只是“参考图一致性工具”，当前前台主模型 `Q3` 明确在向“叙事型音视频一体化生成”靠拢。
- 如果你的 workflow 强调角色或道具一致性，`Vidu` 应纳入 B 池或 C 池，而不是被忽略。

#### 3.2.6 Hailuo 当前系列

在 2026-03-17 的受控浏览器复核中，Hailuo 当前官网前台可直接看到：

- `MiniMax Hailuo 2.3 / 2.3 Fast`
- 入门价格 `低至 $9.99 / 月`
- `Hailuo AI Agent`

同时，旧页面 hydration 数据和先前抓取结果中仍可看到：

- `Hailuo 02`
- `Subject Reference`
- `Director model`
- `10-second 1080P` 与更高订阅档位的历史痕迹

直接结论：

- 对规划来说，`Hailuo` 仍值得保留在主矩阵中，但版本锚点不应再固化为 `Hailuo 02`。
- 工程设计里更稳妥的写法应是：`Hailuo 当前系列（以 2.3 / 2.3 Fast 为前台可见主版本）`。

#### 3.2.7 Luma

Luma 官方价格页可见：

- `Plus $30/month`
- `Pro $90/month`
- `Ultra $300/month`

直接结论：

- Luma 依然值得保留，但在 `< $800` 约束下，不应做主干预算中心。
- 它更适合作为局部试验、场景代理、补位工具。

#### 3.2.8 Sora

在 2026-03-17 的受控浏览器复核中，OpenAI Help Center 当前能直接证明：

- 当前打开的《Generating videos on Sora》文章只适用于 `Sora 1 on Web`
- 该文明确说明它 **不适用于** `Sora app` 或 `Sora 2 on web`
- 官方明确写明 `Sora 1 web experience` 正在被弃用
- 官方引导用户期待 `Sora for Business`
- 当前这篇官方帮助文还明确写到：在 `Sora Video Editor` 中可生成 `up to 20 seconds` 的视频

同时，《Getting started with the Sora app》帮助文当前直接写到：

- `Sora 2 is available on the Sora iOS app, the Sora 2 Android app, and on sora.com`
- Sora app 定位是“creating short videos with synchronized audio”
- 默认能力描述为：生成 `10-second vertical video (default 9:16) with synchronized audio`
- `Sora 2 Pro` 当前可由 `ChatGPT Pro users on the web` 访问
- 官方说明：`Sora 2` 偏速度与日常创作，`Sora 2 Pro` 偏更高保真和更难镜头

同时，《Using Credits for Flexible Usage in ChatGPT (Free/Go/Plus/Pro) & Sora》帮助文当前直接写到：

- credits 目前可用于 `Codex` 与 `Sora`
- `Sora 2, 10s`：`10 credits`
- `Sora 2, 15s`：`20 credits`
- `Sora 2, 25s (ChatGPT Pro only)`：`30 credits`
- `Sora 2 Pro, Standard Resolution, 10s`：`40 credits`
- `Sora 2 Pro, Standard Resolution, 15s`：`80 credits`
- `Sora 2 Pro, 25s`：`120 credits`
- `Sora 2 Pro, High Resolution, 10s`：`250 credits`
- `Sora 2 Pro, High Resolution, 15s`：`500 credits`
- 帮助文明确写到：`Only available on Sora Web currently`

直接结论：

- Sora 可以写进“研究矩阵”与“补位工具”一栏。
- 但在“工程级一键执行 workflow”里，不应把 Sora 作为首选自动化主 provider。
- 文档中对 Sora 的定位应是：`研究关注 + Web/App 补位 + 不纳入无人值守主链路`。

### 3.3 开源/混合云补位

#### 3.3.1 HunyuanVideo

Tencent Hunyuan 官方 GitHub 仓库当前仍显示：

- `HunyuanVideo` 720x1280x129f 的峰值显存要求约 `60GB`
- 544x960x129f 约 `45GB`
- 建议 `80GB` 级别 GPU 获得更好质量

直接结论：

- 原始 `HunyuanVideo` 不适合作为个人 Windows 工作站的本地主引擎。
- 它适合在少量云 GPU 上做对照测试、离线补位、或作为工程级 fallback。

#### 3.3.2 HunyuanVideo-Avatar

官方仓库当前可见：

- 最低显存可以下探到 `24GB`
- 历史更新记录里明确提到支持单 GPU 低显存运行的方向

直接结论：

- 对“角色参考 + 局部补位”的研究价值高于对“全片主生产”的价值。
- 在你的整体系统里，它更适合被写进 `optional local/cheap experimental backend`。

#### 3.3.3 Wan / ComfyUI

Wan 和 ComfyUI 的价值不是“替代所有商业模型”，而是：

- 给 `C` 池镜头、补帧、修复、再生成提供低成本备份路径
- 在主 provider 排队、涨价或任务失败时提供工程级 fallback

### 3.4 2026-03-16 推荐工具角色分工

在“任务上限表现”这一维度上，本规范当前将 `Kling 3.0 系列` 与 `Seedance 2.0` 同时视为第一梯队。  
区别不再体现在是否进入核心主池，而只体现在“证据来源类型不同”：

- `Kling 3.0`：第三方公开 benchmark 与公开比较页支撑更强
- `Seedance 2.0`：官方内部 benchmark、复杂任务、多镜头叙事与导演式控制主张更强

因此在工程实现上，二者都必须被放在关键位置，而不是把其中一个降级为次一级补位。

| 角色 | 推荐工具 |
|---|---|
| 英雄镜头 | `Veo 3.1`、少量 `Veo 3.1 Fast / Veo 3 Fast`、少量 `Runway Gen-4.5` |
| 对话与人物表演增强 | `Runway Act-Two`、必要时辅以其他平台基底镜头 |
| 主叙事镜头生产第一梯队 | `Seedance 2.0`、`Kling 3.0 系列` |
| 主叙事镜头生产第二梯队 | `Runway Gen-4`、`Vidu Q3`、`Hailuo 当前系列` |
| 一致性参考图驱动镜头 | `Vidu Q3 / Reference to Video`、`Kling 3.0 系列`、`Hailuo 当前系列` |
| 场景代理与局部试验 | `Luma`、`Blender`、深度/法线代理 |
| 低成本开源补位 | `Wan`、`HunyuanVideo-Avatar`、`ComfyUI` |

---

## 4. 预算策略：`<$800` 下的推荐组合、替代组合、不可行组合

### 4.1 预算设计原则

预算控制不是“全部选便宜模型”，而是：

1. 用最贵模型只做最值钱的 5%-10% 镜头。
2. 用中档模型承接 60% 左右的主叙事镜头。
3. 用低成本池承接过场、空镜、界面镜头和局部修复。
4. 用统一的评判、筛选和复用机制压缩返工。

### 4.2 推荐预算组合

#### 方案 A：推荐主方案，兼顾质量与成本

| 项目 | 预算建议 |
|---|---:|
| `Runway` 1-2 个月（Gen-4 / 4.5 / Act-Two） | `$35 - $70` |
| `Veo 3.1 Fast / Veo 3 Fast / Veo 3.1` 英雄镜头池 | `$120 - $180` |
| 中文模型信用池：优先 `Seedance 2.0 + Kling 3.0`，再从 `Vidu Q3 / Hailuo 当前系列` 中补位 | `$180 - $260` |
| `Luma` 小额试验池 | `$0 - $30` |
| 云 GPU：`RunPod` 4090 / A6000 / A100 小时包 | `$50 - $100` |
| LLM、分析、脚本拆镜、文本辅助 | `$50 - $90` |
| 返工和应急预算 | `$120 - $150` |
| **合计** | **约 `$555 - $880`** |

推荐实际控制区间：`$620 - $790`。

#### 方案 B：更保守预算

- 减少 `Veo 3.1` 使用，只保留 `Veo 3 Fast`
- 把更多 B 池镜头下沉给 `Vidu / Hailuo / Kling`
- 明确降低“大场面镜头密度”

可压缩到：`$480 - $650`，但视觉上限会降低。

### 4.3 不可行组合

以下组合不推荐写入主方案：

#### 不可行组合 1：全片主力依赖 Veo 高端档

原因：

- 单秒成本过高
- 英雄镜头级别的价格结构不适合 120 分钟长片
- 返工代价太大

#### 不可行组合 2：全片只靠一个网页端模型

原因：

- 一致性不可控
- API/队列/计划波动风险太大
- 生产工程无法稳定复现

#### 不可行组合 3：完全本地化替代商业模型

原因：

- 2026-03-16 仍然很难在个人硬件上获得兼顾质量、速度和稳定性的全链路体验
- 适合作为补位，不适合作为主干

### 4.4 云 GPU 成本参考

2026-03-16 RunPod 官方价格页可见的示例级别：

- `RTX 4090`：community cloud 约 `0.34`，secure cloud 约 `0.59`
- `RTX A6000`：community cloud 约 `0.33`，secure cloud 约 `0.49`
- `A100 PCIe`：community cloud 约 `1.19`，secure cloud 约 `1.39`

直接结论：

- 你的系统完全没必要长期租 A100。
- 对个人工作流，`4090 / A6000` 是更现实的临时补位选择。

---

## 5. 工程级总架构：模块边界、数据流、状态流、人工卡点

### 5.1 总体架构原则

本系统不是“一个模型接口封装器”，而是一个面向电影生产的 orchestration system。  
主控层固定采用：

- `Python 3.12`
- `Typer CLI`
- `Pydantic`
- `SQLite`
- 本地资产目录
- `asyncio/worker`

理由：

- Python 对多模态 AI、媒体处理、LLM 编排、评分和脚本驱动最顺手。
- CLI 优先可以最小化系统复杂度。
- SQLite 足够支撑单人系统的作业状态、预算 ledger、人工 gate 和失败恢复。

### 5.2 顶层阶段入口

顶层命令固定为：

```bash
moviegen run project.yaml --stage all
```

分阶段入口固定为：

- `ingest`
- `analyze`
- `bibles`
- `benchmark`
- `plan`
- `compile-prompts`
- `route`
- `generate`
- `judge`
- `review`
- `post`
- `assemble`
- `report`

### 5.3 核心数据对象

文档与后续实现统一采用以下对象：

- `ProjectSpec`
- `ReferenceAsset`
- `ReferencePack`
- `ReferenceManifest`
- `StyleBible`
- `SceneBible`
- `CharacterBible`
- `ShotSpec`
- `PromptBlockSet`
- `PromptPacket`
- `GenerationJob`
- `CandidateClip`
- `JudgeScore`
- `BudgetLedger`
- `HumanGateDecision`

### 5.4 模块清单总览

#### 1. `Reference Ingest`

目的：  
读取样本片段、样本图片与文本注释，形成统一参考包。

输入：

- 视频：`mp4 / mov / webm / mkv`
- 图片：`png / jpg / jpeg / webp`
- 文本注释：`pdf / md / txt / csv`

输出：

- `raw_videos/`
- `raw_images/`
- `shots/`
- `keyframes/`
- `style_refs/`
- `motion_refs/`
- `reference_manifest.json`
- `reference_pack.json`

一键入口：

```bash
moviegen run project.yaml --stage ingest
```

自动化范围：

- 视频入库
- 自动切镜
- 自动抽关键帧
- 图像去重
- 文本注释抽取与归档
- 样本初步标签化

人工卡点：

- 可选人工确认“哪些参考属于风格、哪些属于角色、哪些属于动作/运镜”

失败处理：

- 单文件失败不阻断全局 ingest
- 写入失败清单与坏文件日志

#### 2. `Reference Analyzer`

目的：  
从 `ReferencePack` 中提取风格规律、镜头语法、角色表征、场景重复模式。

输入：

- `reference_pack.json`
- `shots/`
- `keyframes/`

输出：

- 风格分析摘要
- 镜头统计
- 场景候选聚类
- 角色候选聚类

一键入口：

```bash
moviegen run project.yaml --stage analyze
```

自动化范围：

- 视觉聚类
- 镜头长度统计
- 运镜类型归纳
- 色彩与明暗风格摘要

人工卡点：

- 无强制 gate，但允许人工修正标签

失败处理：

- 某一子分析失败时回退到较粗粒度摘要，不阻断后续 bible 构建

#### 3. `Bible Builder`

目的：  
把风格、角色、场景、服装、道具与连续性规则固化为 production bible。

输入：

- 分析结果
- 人工确认的参考资产

输出：

- `StyleBible`
- `CharacterBible`
- `SceneBible`

一键入口：

```bash
moviegen run project.yaml --stage bibles
```

自动化范围：

- 自动生成初稿
- 自动抽取统一命名空间
- 自动建立角色/服装/场景 ID

人工卡点：

- **Gate 1：风格圣经与角色/场景 bible 锁定**

失败处理：

- 若 bible 未确认，则后续阶段不得继续

#### 4. `Benchmark Runner`

目的：  
在正式生产前，对候选 provider 跑统一基准测试，锁定真正使用的模型组合。

输入：

- 锁定后的 bibles
- 基准镜头集

输出：

- provider 基准报告
- 评分矩阵
- 推荐路由策略

一键入口：

```bash
moviegen run project.yaml --stage benchmark
```

自动化范围：

- 提交统一测试镜头
- 回收候选结果
- 自动评分与排行

人工卡点：

- **Gate 2：模型基准测试与 provider 组合锁定**

失败处理：

- 若候选 provider 大面积失败，则重新回到 benchmark

#### 5. `Story & Shot Planning`

目的：  
生成剧情拆分、节拍表、镜头表，并将长片拆成工程可执行的镜头任务。

输入：

- 剧本
- bibles

输出：

- `BeatSheet`
- `ShotList`
- `ShotSpec[]`

一键入口：

```bash
moviegen run project.yaml --stage plan
```

自动化范围：

- 节拍拆分
- scene -> shot 拆解
- `A/B/C` 镜头等级分类

人工卡点：

- 无强制 gate，但导演可手动修 ShotSpec

失败处理：

- 若 shot list 违反预算上限，则自动提示重新分级

#### 6. `Prompt Compiler`

目的：  
基于模块化提示词样本与统一语义模板，自动优化并编译为各模型适配的 prompt packets。

输入：

- `ShotSpec`
- `StyleBible`
- `CharacterBible`
- `SceneBible`

输出：

- `PromptBlockSet`
- 每个 provider 对应的 `PromptPacket`

一键入口：

```bash
moviegen run project.yaml --stage compile-prompts
```

自动化范围：

- 从 ShotSpec 生成统一 `Prompt Spec`
- 将提示词拆成模块化 blocks
- 自动补齐缺失字段
- 自动删减对某 provider 无效或有害的描述
- 自动重排词序
- 自动生成 provider-specific 提示词组合片段

提示词模块固定拆分为：

- `subject`
- `location`
- `action`
- `camera`
- `style`
- `continuity`
- `negative_or_avoid`
- `provider_hints`

人工卡点：

- 不设强制 gate，但允许人工查看/微调 packet 样本

失败处理：

- 某 provider 编译失败时，不影响其他 provider packet 的生成

#### 7. `Provider Router`

目的：  
按镜头等级、预算和模型强项分发到不同 API/平台。

输入：

- `ShotSpec`
- `PromptPacket`
- `BudgetLedger`
- provider 基准报告

输出：

- `GenerationJob[]`

一键入口：

```bash
moviegen run project.yaml --stage route
```

自动化范围：

- `A/B/C` 镜头分级路由
- 成本估算
- 并发调度
- fallback provider 指派

人工卡点：

- 无强制 gate

失败处理：

- 预算超阈值时自动降级或暂停等待确认

#### 8. `Generation Adapters`

目的：  
统一 `submit / poll / cancel / download / retry`。

输入：

- `GenerationJob`

输出：

- `CandidateClip`

统一接口要求：

```python
class ProviderAdapter:
    def submit(self, job): ...
    def poll(self, external_job_id): ...
    def download(self, external_job_id): ...
    def cancel(self, external_job_id): ...
    def retry(self, job): ...
```

一键入口：

```bash
moviegen run project.yaml --stage generate
```

自动化范围：

- 任务提交
- 状态轮询
- 下载结果
- 重试与超时

人工卡点：

- 无

失败处理：

- provider 级别失败自动回流 router

#### 9. `AI Judge`

目的：  
用多模态评判做自动打分、自动淘汰、复审分流。

输入：

- `CandidateClip`
- `ShotSpec`
- bibles

输出：

- `JudgeScore`
- 入围/淘汰/复审标记

一键入口：

```bash
moviegen run project.yaml --stage judge
```

自动化范围：

- 一致性评分
- 语义符合度评分
- 运动稳定性评分
- 人脸/服装/场景漂移检测

人工卡点：

- **Gate 3：镜头候选入选**

失败处理：

- 低分镜头自动回流 `compile-prompts -> route -> generate`

#### 10. `Continuity Checker`

目的：  
做人脸、服装、光线、空间和镜头语法连续性预警。

输入：

- 入围候选镜头
- 前后镜头上下文

输出：

- 连续性告警
- 风险报告

一键入口：

```bash
moviegen run project.yaml --stage review
```

自动化范围：

- 同一角色跨镜头漂移检测
- 同一场景空间关系漂移检测
- 光照逻辑预警

人工卡点：

- 可选导演复核

失败处理：

- 高风险镜头强制回流重生成或标记后期修复

#### 11. `Post Stack`

目的：  
执行口型、补帧、超分、调色、字幕、音频合成等后期处理。

输入：

- 入选镜头

输出：

- 后期处理后的可剪辑镜头

一键入口：

```bash
moviegen run project.yaml --stage post
```

自动化范围：

- lip-sync
- frame interpolation
- upscale
- color normalization
- audio assembly

人工卡点：

- 无强制 gate，但允许人工挑选后期策略

失败处理：

- 保留 pre-post 版本可回退

#### 12. `Assembly & Report`

目的：  
输出时间线装配说明、预算消耗、失败统计和可复现报告。

输入：

- 已处理镜头
- 音频与字幕

输出：

- 装配清单
- sequence 包
- 报告文档

一键入口：

```bash
moviegen run project.yaml --stage assemble
moviegen run project.yaml --stage report
```

人工卡点：

- **Gate 4：序列锁定与终剪输出**

失败处理：

- 装配失败不影响已生成镜头和评判历史

### 5.5 人工卡点固定定义

本系统明确保留以下四个强制人工卡点：

1. `Gate 1`：风格圣经与角色/场景 bible 锁定  
2. `Gate 2`：模型基准测试与 provider 组合锁定  
3. `Gate 3`：镜头候选入选  
4. `Gate 4`：序列锁定与终剪输出  

这四个 gate 不应被删除，因为它们不是“低效”，而是整个长片质量的护栏。

---

## 6. “一键执行”工作流：阶段入口、批处理、失败恢复、断点续跑

### 6.1 一键执行的准确定义

“一键执行”在本系统中的定义不是“从脚本到成片完全无人值守”，而是：

- 可以用单命令启动整批任务；
- 系统自动推进各阶段；
- 遇到人工 gate 时暂停；
- 人工确认后从暂停点继续；
- 整个过程中保留作业状态、预算状态和失败上下文。

### 6.2 顶层执行命令

```bash
moviegen run project.yaml --stage all
```

系统内部阶段顺序：

```text
ingest
-> analyze
-> bibles
-> benchmark
-> plan
-> compile-prompts
-> route
-> generate
-> judge
-> review
-> post
-> assemble
-> report
```

### 6.3 状态管理

SQLite 至少记录以下表：

- `runs`
- `stage_runs`
- `generation_jobs`
- `candidate_clips`
- `judge_scores`
- `budget_ledger`
- `human_gates`
- `artifacts`

### 6.4 断点续跑

要求：

- 任一阶段失败后，允许使用同一 `run_id` 恢复。
- 已成功的 stage 不重复执行，除非显式 `--force-stage`.
- 重跑时优先复用已有 artifacts 与评分结果。

### 6.5 retry-rule

文档内必须固定写入：

- API 短时失败：自动重试 `2-3` 次
- provider 队列超时：切换 fallback provider 或暂停
- 下载失败：单独重试下载，不重提生成
- 评分失败：允许重新评判，不重生成

### 6.6 budget stop-rule

文档内必须固定写入：

- 当总预算达到 `80%`：系统进入 `budget warning`
- 当总预算达到 `90%`：A 池镜头必须人工确认后继续
- 当总预算达到 `100%`：自动停止新生成任务，只允许评判、复审与装配

### 6.7 A/B/C 镜头分级执行策略

#### A 池

- 少量英雄镜头
- 允许使用 `Veo 3.1 / Veo 3 Fast / Runway Gen-4.5`
- 必须经过更严格评判与人工筛选

#### B 池

- 常规对白与叙事镜头
- 主力使用 `Seedance 2.0 / Kling 3.0 系列`
- `Runway Gen-4 / Vidu Q3 / Hailuo 当前系列` 作为第二梯队与补位池

#### C 池

- 空镜、过场、界面镜头、补洞镜头
- 允许下沉到更便宜模型或开源补位

---

## 7. 实施路线：`PoC -> 试生产 -> 长片生产`

### 7.1 PoC 阶段

目标：

- 打通一条完整链路，但只覆盖 `3 个场景 + 20 个镜头`

要求：

- 跑通 ingest、bible、prompt compile、route、generate、judge、report
- 验证 `Reference Ingest` 的 `视频 + 图片 + 文本注释` 混合输入
- 验证 provider router 的基础可用性

### 7.2 试生产阶段

目标：

- 生产 `5-10` 分钟高一致性样片

要求：

- 跑通四个 gate
- 跑通 A/B/C 分级
- 跑通断点续跑
- 验证预算 stop-rule

### 7.3 长片生产阶段

目标：

- 进入约 120 分钟的正式长片生产

要求：

- 不再频繁更换 bibles
- 不再频繁更换 provider 组合
- 批处理优先，单镜头精修作为补充

### 7.4 不建议的实施方式

- 先把所有镜头都生成出来再考虑结构
- 先买满所有平台会员再开始测试
- 没有 benchmark 就直接烧长片 production credits

---

## 8. 研究来源附录：官方链接、Bing/Baidu/Google 检索说明、日期戳

### 8.1 官方来源

#### 中文/中英可切换页面

- ByteDance Seed / Seedance 2.0  
  - https://seed.bytedance.com/zh/tech/seedance  
  - https://seed.bytedance.com/en/tech/seedance
- Kling Global  
  - https://app.klingai.com/global
- Vidu Pricing  
  - https://www.vidu.com/zh/pricing  
  - https://www.vidu.com/pricing
- Hailuo AI  
  - https://hailuoai.video

#### 英文官方页面

- Google Vertex AI Generative AI Pricing  
  - https://cloud.google.com/vertex-ai/generative-ai/pricing
- Runway Pricing  
  - https://runwayml.com/pricing/
- Luma Pricing  
  - https://lumalabs.ai/pricing
- RunPod Pricing  
  - https://www.runpod.io/pricing
- OpenAI Help Center / Sora
  - https://help.openai.com/en/articles/9957612-generating-videos-on-sora/
  - https://help.openai.com/en/articles/12642688-using-credits-for-flexible-usage-in-chatgpt-freegopluspro-sora
  - https://help.openai.com/en/articles/12456897-getting-started-with-the-sora-app
- HunyuanVideo  
  - https://github.com/Tencent-Hunyuan/HunyuanVideo
- HunyuanVideo-Avatar  
  - https://github.com/Tencent-Hunyuan/HunyuanVideo-Avatar

### 8.2 搜索引擎检索说明

本节在 2026-03-17 基于新的本地代理节点重新执行了一轮复核。复核的目标不是替代官方来源，而是验证 `Baidu / Google / Bing` 在当前网络条件下是否能为中文与英文事实检索提供稳定结果，以及这些结果是否会改变本规范前文的事实层判断。

#### Bing

在 2026-03-16 的检索中：

- 对 `Veo` 相关关键词，Bing 结果明显混入 unrelated 品牌或体育产品结果。
- 因此 Bing 只保留为“检索路径”而非事实来源。

在 2026-03-17 代理切换后的复核中：

- `Bing` 已可稳定返回结果页，但“结果可用”不等于“结果可靠”。
- 对英文查询 `Veo 3.1 Google Vertex AI pricing`，前几条结果仍被体育摄像机品牌 `Veo` 污染，不能直接作为事实依据。
- 对英文查询 `Runway Gen-4.5 Act-Two pricing`，前几条结果混入大量旧的 `Gen-2` 问答页和二手讨论页，时效性明显不足。
- 对英文查询 `Seedance 2.0 ByteDance`，`Bing` 能在前几条结果中返回 `seed.bytedance.com` 的官方页面，这一项可以作为“搜索引擎找回官方页”的正面案例。
- 结论不变：`Bing` 可以继续保留为检索入口，但不能替代官方页，尤其不能直接用于 `Veo` 和 `Runway` 这种高歧义词条的版本与价格判断。

#### Baidu

在 2026-03-16 的检索中：

- 多次返回安全验证页或“网络不给力”页。
- 因此未将 Baidu 结果用于事实层，只在本附录中记录其受限状态。

在 2026-03-17 代理切换后的复核中：

- `Baidu` 对部分英文查询可以返回正常结果页，例如 `Veo 3.1 Google Vertex AI pricing` 能拿到百度搜索结果页面本身。
- 但对更有价值的定向中文查询，如 `可灵 AI 视频 API 官方`、`Seedance 2.0 字节 官方`、`Vidu 7 张参考图 官方`、`海螺 AI Hailuo 02 10秒 1080P 官方`，仍然大概率跳转到安全验证页。
- 这说明在当前网络条件下，`Baidu` 已经从“几乎不可用”提升为“偶尔可用”，但还远未达到可以稳定承担事实核验入口的程度。
- 结论仍然不变：`Baidu` 可记录为中文检索痕迹来源，但不应作为版本、价格、API 可用性的最终依据。

#### Google

在 2026-03-16 的检索中：

- 多次触发验证码。
- 因此 Google 公开搜索结果仅作为辅助线索，正式引用退回到官方目标页面。

在 2026-03-17 代理切换后的复核中：

- `Google` 对英文查询 `Veo 3.1 Google Vertex AI pricing`、`Runway Gen-4.5 Act-Two pricing` 以及中文查询 `海螺 AI Hailuo 02 10秒 1080P`，均继续返回 `429` 或 `sorry/captcha` 页面。
- 因此当前代理切换并未让 `Google Search` 进入可稳定使用状态。
- 结论不变：`Google` 仍只能作为“尝试过但受限”的英文检索痕迹来源，正式事实层必须继续回退到官方页面。

在 2026-03-17 同日稍后的“受控浏览器 + 人工处理验证”复核中：

- `Google` 的至少两页搜索结果已可被程序直接读取，包括：
  - `Veo 3.1 Google Vertex AI pricing`
  - `Runway Gen-4.5 Act-Two pricing`
- 这些搜索结果页能够稳定把 `Vertex AI Pricing`、`Runway Pricing` 等官方结果推到前列，因此可以作为“搜索层支持官方结论”的证据。
- 但这依然不改变最终原则：搜索结果页只用于确认“官方页是否在前列、市场上有哪些二手说法”，真正的版本、价格和能力结论仍必须回到官方页正文。

#### 受控浏览器补充说明

在 2026-03-17 的受控 Chrome 会话（远程调试端口 `9333`）中，已成功直接读取：

- `Google` 搜索结果页：`Veo 3.1 Google Vertex AI pricing`
- `Google` 搜索结果页：`Runway Gen-4.5 Act-Two pricing`
- `Bing` 搜索结果页：`Veo / Runway / Seedance / Kling / Vidu`
- 官方页正文：`Vertex AI pricing`、`Runway pricing`、`Seedance 2.0`、`Kling dev`、`Vidu pricing`、`Vidu Q3`、`Vidu Reference to Video`、`Hailuo 首页`、`Sora help`

同一受控会话中，`Baidu` 的两页仍停留在 `百度安全验证`，因此本轮深挖并未得到新的百度正文内容。

### 8.2.1 本轮复核对正文结论的影响

2026-03-17 这一轮通过 `Baidu / Google / Bing` 的中文与英文复核，没有发现足以推翻正文工具矩阵的事实性冲突。变化主要发生在“搜索可达性”而非“工具事实层”：

- `Bing`：可访问，但高歧义关键词污染严重。
- `Baidu`：比上一轮略好，但对关键中文查询仍以验证码为主。
- `Google`：仍不可稳定使用。

因此正文中的处理原则继续成立：

- 搜索引擎负责“找路径、看市场信号、做交叉线索”。
- 官方页面负责“落事实、落价格、落版本、落能力”。

### 8.3 日期戳策略

本规范中的“最新”统一指：

- 首版工具采集时间：`2026-03-16`
- 搜索引擎复核时间：`2026-03-17`
- 若后续重新执行本规范中的研究流程，应重新刷新本附录与工具矩阵，不应沿用旧价格与旧版本判断。

---

## 9. 最小配置与接口附录

### 9.1 `project.yaml` 最小字段集合

```yaml
project:
  id: moviegen_scifi_001
  title: My Sci-Fi Feature
  language: zh-CN
  target_runtime_min: 120
  budget_usd_cap: 800

references:
  video_dirs:
    - input/reference_videos
  image_dirs:
    - input/reference_images
  text_notes:
    - NewChat-Monica_AI_Chat.pdf
    - input/notes

style:
  target_era: "2000-2015 realistic sci-fi"
  tone_keywords:
    - restrained
    - cinematic
    - low saturation

providers:
  preferred_a_pool:
    - veo_3_1_fast
    - veo_3_fast
    - veo_3_1
    - runway_gen_4_5
  preferred_b_pool:
    - seedance_2_0
    - kling_3_0
    - runway_gen_4
    - vidu_q3
    - hailuo_current
  preferred_c_pool:
    - vidu_q3
    - hailuo_current
    - wan
    - comfyui

workflow:
  enable_human_gates: true
  max_api_retries: 3
  budget_warning_ratio: 0.8
  budget_hard_stop_ratio: 1.0
```

### 9.2 `Prompt Spec` 示例

```yaml
shot_id: S012
scene_id: SC04
grade: B
subject: 女主角，30岁，疲惫但克制
location: 狭窄金属舱室，冷白顶灯
action: 坐在控制台前，短暂停顿后抬头
camera: 中近景，缓慢推近，轻微手持感
style: 2005-2015写实科幻电影，克制，低饱和
continuity:
  character_id: char_anna_v1
  wardrobe_id: wd_anna_ship_01
  location_id: loc_cabin_A
avoid:
  - 卡通感
  - 夸张表情
  - 过强景深虚化
```

### 9.3 Provider Adapter 统一接口

```python
class ProviderAdapter:
    name: str

    def submit(self, job: "GenerationJob") -> str:
        ...

    def poll(self, external_job_id: str) -> dict:
        ...

    def download(self, external_job_id: str) -> list[str]:
        ...

    def cancel(self, external_job_id: str) -> None:
        ...

    def retry(self, job: "GenerationJob") -> str:
        ...
```

### 9.4 工作目录建议

```text
docs/
  moviegen_master_workflow_spec.md
input/
  reference_videos/
  reference_images/
  notes/
workspace/
  raw_videos/
  raw_images/
  shots/
  keyframes/
  style_refs/
  motion_refs/
  bibles/
  prompts/
  jobs/
  candidates/
  review/
  post/
  reports/
state/
  moviegen.db
config/
  project.yaml
```

---

## 10. 最终执行结论

在 2026-03-16 的工具现实下，这个项目最优路线不是“押注一个最强视频模型”，而是：

- 用 `Reference Ingest` 把样本真正结构化；
- 用 `Bible Builder` 固化风格、角色与场景；
- 用 `Prompt Compiler` 把“语义层镜头意图”自动翻译成多 provider 的可执行 packet；
- 用 `Provider Router` 按镜头等级和预算智能分发；
- 用 `AI Judge + Human Gates` 严格压返工；
- 用 `Post Stack + Assembly` 把 AI 生成片段真正变成电影生产单元。

对于你的目标，这条路线比“继续追某个单模型的最新 demo”更重要，也更接近真正能做出 120 分钟作品的条件。
