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

标准测试套件固定为 `benchmark_suite_v1`，不得在同一次 Gate 2 评估中随意变更。  
该套件默认包含 8 个基准镜头，所有候选 provider 必须跑同一套输入：

- `B01_closeup_emotion`
  - 单人近景，微表情、呼吸、细微头部运动
  - 评估重点：面部稳定、细节真实感、微动作自然度
- `B02_dialogue_ots`
  - 双人过肩对话，固定场景，连续反打
  - 评估重点：角色一致性、空间关系、对白镜头语法
- `B03_walk_and_talk`
  - 角色移动中的中景叙事镜头
  - 评估重点：步态稳定、背景连续性、镜头跟随自然度
- `B04_hand_object_interaction`
  - 手与关键道具交互
  - 评估重点：手部结构、接触关系、动作逻辑
- `B05_vertical_rise_establishing`
  - 大场面建立镜头，近地到高空的垂直上升
  - 评估重点：大位移稳定性、透视连贯性、环境一致性
- `B06_reference_consistency`
  - 使用角色/道具/场景参考图的中景镜头
  - 评估重点：参考遵循度、角色/道具复现、风格统一
- `B07_motion_control_stress`
  - 动作迁移或 motion control 压力测试
  - 评估重点：动作可控性、姿态漂移、复杂运动稳定性
- `B08_task_ceiling_stress`
  - 复杂任务压力测试：多镜头叙事、长时序连续性、复杂调度
  - 评估重点：任务上限、长时序组织能力、多镜头逻辑

评分维度固定采用 10 分制，并按以下权重计算 `weighted_total_score`：

- `task_ceiling`：0.25
- `continuity`：0.20
- `motion_stability`：0.15
- `identity_consistency`：0.15
- `instruction_fidelity`：0.10
- `camera_control`：0.10
- `cost_efficiency`：0.05

其中 `task_ceiling` 的定义固定为：

- 面向复杂任务的综合表现，而不是单镜头平均质量
- 包括：多镜头叙事、长时序衔接、角色与场景跨镜头复用、复杂调度不崩坏

Gate 2 的固定判定规则如下：

- `Seedance 2.0` 与 `Kling 3.0 系列` 必须始终进入最高优先级 benchmark 阶段，不允许在运行前被排除
- 若某 provider 的 `weighted_total_score < 7.5`，则不得进入主生产池
- 若某 provider 的 `task_ceiling < 8.0`，则不得作为“主叙事镜头生产第一梯队”
- 若 `Seedance 2.0` 与 `Kling 3.0` 的总分差值 `<= 0.4`，则二者同时保留为第一梯队
- 若其中一方在某个专项维度上领先 `>= 0.8`，则该专项维度对应的镜头标签优先路由给胜者

专项优先判定规则固定如下：

- `Seedance 2.0` 若在 `task_ceiling / continuity / instruction_fidelity` 中任意两项领先，则优先承担：
  - `narrative_multi_shot`
  - `scene_transition`
  - `reference_storytelling`
- `Kling 3.0` 若在 `motion_stability / camera_control / identity_consistency` 中任意两项领先，则优先承担：
  - `motion_control`
  - `action_heavy`
  - `pose_transfer`
  - `element_reference`

`Benchmark Runner` 的产出必须新增以下结构化字段：

- `benchmark_suite_id`
- `provider_scores`
- `provider_rankings`
- `archetype_winners`
- `tier_assignments`
- `routing_recommendation`

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

`Provider Router` 的默认目标不是“平均分配”，而是“按镜头标签把镜头送给最擅长的模型”。  
镜头在进入 router 前必须具备以下最小标签：

- `grade`: `A / B / C`
- `archetype`: 例如 `hero_cinematic`、`narrative_multi_shot`、`motion_control`、`reference_consistency`、`dialogue_native_audio`、`insert_cutaway`
- `needs_native_audio`: `true / false`
- `needs_reference_consistency`: `true / false`
- `needs_motion_control`: `true / false`
- `duration_target_sec`

默认路由矩阵固定如下：

- `hero_cinematic`
  - primary: `veo_3_1`
  - secondary: `veo_3_1_fast`
  - fallback: `runway_gen_4_5`
- `narrative_multi_shot`
  - primary: `seedance_2_0`
  - secondary: `kling_3_0`
  - fallback: `runway_gen_4`
- `reference_storytelling`
  - primary: `seedance_2_0`
  - secondary: `vidu_q3`
  - fallback: `kling_3_0`
- `motion_control`
  - primary: `kling_3_0`
  - secondary: `seedance_2_0`
  - fallback: `runway_gen_4`
- `action_heavy`
  - primary: `kling_3_0`
  - secondary: `runway_gen_4`
  - fallback: `seedance_2_0`
- `dialogue_native_audio`
  - primary: `vidu_q3`
  - secondary: `seedance_2_0`
  - fallback: `kling_3_0`
- `reference_consistency`
  - primary: `vidu_q3`
  - secondary: `kling_3_0`
  - fallback: `seedance_2_0`
- `insert_cutaway`
  - primary: `vidu_q3`
  - secondary: `hailuo_current`
  - fallback: `wan`

第一梯队的强制规则固定如下：

- 所有 `B` 池中带有 `narrative_multi_shot`、`reference_storytelling`、`motion_control`、`action_heavy` 标签的镜头，必须优先尝试 `Seedance 2.0` 或 `Kling 3.0`
- 只有在以下条件之一满足时，才允许把该类镜头直接降到第二梯队：
  - 对应第一梯队 provider 在最近一次 `benchmark_suite_v1` 中专项分数 `< 8.0`
  - 当前 provider 队列超时且预计等待时间超过 `max_queue_wait_min`
  - 当前项目预算已进入 `budget_warning`，且该镜头被标为 `non_hero`

路由优先级冲突时，按以下规则裁决：

- 若镜头同时命中 `narrative_multi_shot` 与 `motion_control`
  - 先比较 Gate 2 中 `task_ceiling` 与 `motion_stability` 的专项胜者
  - 若 `task_ceiling` 差值 `>= 0.8`，给 `Seedance 2.0`
  - 若 `motion_stability` 差值 `>= 0.8`，给 `Kling 3.0`
  - 否则双投：同镜头同时向 `Seedance 2.0` 与 `Kling 3.0` 各提交 1 轮
- 若镜头同时命中 `reference_consistency` 与 `dialogue_native_audio`
  - 先给 `Vidu Q3`
  - 若 Vidu 未过 `JudgeScore` 阈值，再回流到 `Seedance 2.0`

`Provider Router` 的预算控制规则固定如下：

- `A` 池镜头不允许直接路由到 `C` 池 provider
- `B` 池镜头默认最多允许双投 2 个 provider
- `C` 池镜头禁止使用 `veo_3_1`
- 当预算达到 `80%`：
  - `A` 池仍可使用第一梯队
  - `B` 池禁止无条件双投
  - `C` 池强制下沉到低成本 provider
- 当预算达到 `90%`：
  - `A` 池镜头必须人工确认才允许继续使用 `veo_3_1 / runway_gen_4_5`
  - `B` 池镜头默认只保留单投

`Provider Router` 的队列与重试规则固定如下：

- `max_queue_wait_min` 默认设为 `20`
- 任一 provider 在同类镜头上连续失败 `>= 3` 次，则临时熔断 `30` 分钟
- 熔断期间同类镜头自动切换到 secondary
- 若 primary 与 secondary 同时失败，则回流 `compile-prompts`，并给 `PromptCompiler` 加上 `retry_context`

`Provider Router` 的输出必须新增以下结构化字段：

- `selected_provider`
- `provider_rank`
- `route_reason`
- `archetype`
- `fallback_chain`
- `budget_class`
- `queue_policy`

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

`AI Judge` 的目标不是替代导演，而是把“明显不合格的候选镜头”尽早拦在人工看片之前。  
因此评分必须同时输出：

- 数值评分
- 决策标签
- 回流建议
- 硬失败原因

`JudgeScore` 的评分维度固定为 10 分制，默认字段如下：

- `identity_consistency`
- `scene_consistency`
- `instruction_fidelity`
- `motion_stability`
- `camera_language`
- `image_quality`
- `audio_sync`
- `narrative_utility`
- `artifact_penalty`
- `weighted_total_score`

其中 `artifact_penalty` 为惩罚项，取值范围 `0.0 - 3.0`，用于扣减总分。  
`weighted_total_score` 默认计算方式固定为：

- `identity_consistency * 0.18`
- `scene_consistency * 0.14`
- `instruction_fidelity * 0.14`
- `motion_stability * 0.14`
- `camera_language * 0.10`
- `image_quality * 0.12`
- `audio_sync * 0.08`
- `narrative_utility * 0.10`
- 减去 `artifact_penalty`

若镜头未要求原生音频，则 `audio_sync` 不参与加权，剩余权重按比例归一。

硬失败条件固定如下，只要命中任一项，直接标记 `hard_fail=true`：

- 主体身份明显崩坏，无法判定为同一角色
- 关键道具或关键场景锚点消失
- 运动逻辑断裂，出现明显空间穿模或肢体崩坏
- 需要 lip-sync 的镜头但口型严重不匹配
- 帧间闪烁、扭曲、鬼影达到不可用程度
- 出现平台水印、错误字幕、明显 UI 残留

按镜头等级的决策阈值固定如下：

- `A` 池
  - `pass`: `weighted_total_score >= 8.4` 且无硬失败
  - `review`: `7.8 - 8.39`
  - `regenerate`: `< 7.8` 或硬失败
- `B` 池
  - `pass`: `weighted_total_score >= 7.8` 且无硬失败
  - `review`: `7.2 - 7.79`
  - `regenerate`: `< 7.2` 或硬失败
- `C` 池
  - `pass`: `weighted_total_score >= 7.0` 且无硬失败
  - `review`: `6.5 - 6.99`
  - `regenerate`: `< 6.5` 或硬失败

`AI Judge` 的输出决策固定为以下枚举之一：

- `pass`
- `review`
- `regenerate_same_provider`
- `reroute_provider`
- `send_to_post_fix`
- `reject`

默认决策规则如下：

- 若 `hard_fail=true` 且问题属于结构性问题：
  - `reroute_provider`
- 若 `hard_fail=true` 且问题属于局部瑕疵：
  - `regenerate_same_provider`
- 若总分落入 `review` 区间：
  - `review`
- 若总分已过线但仅存在轻微后期问题：
  - `send_to_post_fix`
- 若总分过线且无关键风险：
  - `pass`

问题类型与回流阶段映射固定如下：

- `identity drift` -> `compile-prompts`
- `reference mismatch` -> `compile-prompts`
- `motion collapse` -> `route`
- `camera mismatch` -> `compile-prompts`
- `provider artifact` -> `generate`
- `minor flicker / sharpen / sync issues` -> `post`

`AI Judge` 必须新增以下结构化输出字段：

- `judge_score_id`
- `candidate_clip_id`
- `shot_id`
- `grade`
- `provider`
- `metrics`
- `weighted_total_score`
- `hard_fail`
- `hard_fail_reasons`
- `decision`
- `route_back_stage`
- `judge_model`
- `judge_prompt_version`
- `created_at`

`Gate 3` 的默认筛选规则固定如下：

- 每个 `ShotSpec` 至少保留 `top 2` 候选给人工看
- 若第一名与第二名分差 `< 0.4`，必须双入围
- 若第一名来自第一梯队 provider，而第二名来自第二梯队 provider 且分差 `< 0.2`，也必须双入围
- 若所有候选都未过 `review` 下限，则该镜头不进入 Gate 3，而是自动回流

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

各表的最小职责固定如下：

- `runs`
  - 记录一次完整工作流执行
  - 关键字段：`run_id`、`project_id`、`status`、`started_at`、`finished_at`
- `stage_runs`
  - 记录每个 stage 在某次 `run_id` 下的执行情况
  - 关键字段：`run_id`、`stage_name`、`status`、`attempt`、`started_at`、`finished_at`
- `generation_jobs`
  - 记录所有实际发往 provider 的任务
  - 关键字段：`job_id`、`shot_id`、`provider`、`provider_model`、`status`、`external_job_id`
- `candidate_clips`
  - 记录下载回来的候选片段
  - 关键字段：`candidate_clip_id`、`job_id`、`shot_id`、`provider`、`artifact_path`
- `judge_scores`
  - 记录每个候选片段的评分结果
  - 关键字段：`judge_score_id`、`candidate_clip_id`、`weighted_total_score`、`decision`
- `budget_ledger`
  - 记录预算消耗与冻结额度
  - 关键字段：`run_id`、`provider`、`estimated_cost_usd`、`actual_cost_usd`、`event_type`
- `human_gates`
  - 记录 Gate 1-4 的状态与人工决策
  - 关键字段：`gate_id`、`run_id`、`gate_name`、`status`、`decision_payload`
- `artifacts`
  - 统一索引所有中间产物与最终产物
  - 关键字段：`artifact_id`、`run_id`、`artifact_type`、`artifact_path`、`source_stage`

状态枚举固定如下：

- `runs.status`
  - `created`
  - `running`
  - `paused_for_gate`
  - `failed`
  - `completed`
  - `canceled`
- `stage_runs.status`
  - `pending`
  - `running`
  - `succeeded`
  - `failed`
  - `skipped`
- `generation_jobs.status`
  - `queued`
  - `running`
  - `succeeded`
  - `failed`
  - `timed_out`
  - `canceled`
- `human_gates.status`
  - `waiting`
  - `approved`
  - `rejected`
  - `expired`

状态迁移规则固定如下：

- `runs.created -> runs.running`
  - 在第一阶段真正启动时发生
- `runs.running -> runs.paused_for_gate`
  - 任一 Gate 进入等待人工确认时发生
- `runs.paused_for_gate -> runs.running`
  - Gate 被批准后恢复执行
- `runs.running -> runs.failed`
  - 任一关键 stage 失败且无自动恢复路径时发生
- `runs.running -> runs.completed`
  - 所有目标 stage 成功结束时发生
- `runs.running -> runs.canceled`
  - 用户主动取消或预算硬停时发生

`stage_runs` 的强约束规则固定如下：

- 同一 `run_id + stage_name` 在同一时间最多只能有一个 `running`
- 后续 stage 不得在前序强依赖 stage `failed` 的情况下进入 `running`
- `judge` 不得早于 `generate`
- `route` 不得早于 `compile-prompts`
- `benchmark` 不得在 `Gate 1` 未批准时进入 `succeeded`

`generation_jobs` 的强约束规则固定如下：

- 同一 `packet_id` 在同一 provider 上的并发 job 数默认不超过 `2`
- 同一 `shot_id` 的 `A` 池镜头必须至少保留一条完整 `job -> clip -> judge` 轨迹
- 任一 `generation_job` 在 `succeeded` 前不得写入最终 `actual_cost_usd`

### 6.3.1 状态机约束

工作流状态机固定为“可暂停、可回流、不可跳依赖阶段”：

- `ingest -> analyze -> bibles -> benchmark -> plan -> compile-prompts -> route -> generate -> judge -> review -> post -> assemble -> report`
- 允许的自动回流只有：
  - `judge -> compile-prompts`
  - `judge -> route`
  - `judge -> generate`
  - `judge -> post`
- 不允许直接从 `judge` 回流到 `bibles`
- 若需要修改 `StyleBible / CharacterBible / SceneBible`，必须重新进入 `Gate 1`

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

benchmark:
  suite_id: benchmark_suite_v1
  must_test:
    - seedance_2_0
    - kling_3_0
  optional_test:
    - runway_gen_4
    - vidu_q3
    - hailuo_current
  weights:
    task_ceiling: 0.25
    continuity: 0.20
    motion_stability: 0.15
    identity_consistency: 0.15
    instruction_fidelity: 0.10
    camera_control: 0.10
    cost_efficiency: 0.05
  thresholds:
    minimum_total_score: 7.5
    minimum_task_ceiling_for_tier1: 8.0
    close_margin_keep_both_tier1: 0.4
    clear_win_for_archetype: 0.8

routing:
  max_queue_wait_min: 20
  fuse_after_failures: 3
  fuse_cooldown_min: 30
  route_matrix:
    hero_cinematic: [veo_3_1, veo_3_1_fast, runway_gen_4_5]
    narrative_multi_shot: [seedance_2_0, kling_3_0, runway_gen_4]
    reference_storytelling: [seedance_2_0, vidu_q3, kling_3_0]
    motion_control: [kling_3_0, seedance_2_0, runway_gen_4]
    action_heavy: [kling_3_0, runway_gen_4, seedance_2_0]
    dialogue_native_audio: [vidu_q3, seedance_2_0, kling_3_0]
    reference_consistency: [vidu_q3, kling_3_0, seedance_2_0]
    insert_cutaway: [vidu_q3, hailuo_current, wan]
``` 

### 9.2 `ReferenceAsset / ReferenceManifest / ReferencePack` 字段契约

#### `ReferenceAsset`

`ReferenceAsset` 表示一条最小参考单元，既可以是视频，也可以是图片，也可以是文本注释的抽取片段。

最小字段集合固定如下：

```yaml
reference_asset_id: string
asset_type: video|image|text
source_path: string
derived_from: string|null
language: string|null
duration_sec: float|null
frame_range: [int, int]|null
tags:
  role: style|character|scene|motion|prop|dialogue|camera
  confidence: float
labels: string[]
quality_flags:
  blurry: bool
  watermark: bool
  low_light: bool
  duplicate_suspect: bool
created_at: datetime
```

#### `ReferenceManifest`

`ReferenceManifest` 是 ingest 阶段的索引文件，用于描述“导入了什么”和“它们被初步归类为什么”。

最小字段集合固定如下：

```yaml
manifest_id: string
project_id: string
imported_assets: string[]
failed_assets: string[]
dedup_groups: string[][]
shot_segments: string[]
keyframes: string[]
stats:
  num_videos: int
  num_images: int
  num_text_notes: int
  num_shot_segments: int
  num_keyframes: int
created_at: datetime
```

#### `ReferencePack`

`ReferencePack` 是进入分析和 bible 构建前的标准化产物。

最小字段集合固定如下：

```yaml
reference_pack_id: string
project_id: string
manifest_id: string
style_assets: string[]
character_assets: string[]
scene_assets: string[]
motion_assets: string[]
prop_assets: string[]
dialogue_assets: string[]
excluded_assets: string[]
pack_version: string
created_at: datetime
```

约束规则固定如下：

- 每个 `ReferenceAsset` 只能在 `ReferencePack` 中属于一个主 role
- `excluded_assets` 中的资产不得进入 bible 构建
- `motion_assets` 默认优先来自视频切段，而不是静态图片

### 9.3 `StyleBible / CharacterBible / SceneBible` 字段契约

#### `StyleBible`

```yaml
style_bible_id: string
project_id: string
era_target: string
tone_keywords: string[]
palette_keywords: string[]
texture_keywords: string[]
lens_language: string[]
camera_movement_rules: string[]
negative_style_rules: string[]
hero_reference_assets: string[]
locked: bool
version: string
```

#### `CharacterBible`

```yaml
character_bible_id: string
project_id: string
characters:
  - character_id: string
    display_name: string
    role_type: lead|support|extra
    reference_assets: string[]
    identity_keywords: string[]
    wardrobe_ids: string[]
    prop_ids: string[]
    continuity_rules: string[]
    allow_lora: bool
    allow_face_reference: bool
locked: bool
version: string
```

#### `SceneBible`

```yaml
scene_bible_id: string
project_id: string
locations:
  - location_id: string
    display_name: string
    category: interior|exterior|vehicle|virtual|other
    reference_assets: string[]
    geometry_proxy_type: blender_blockout|panorama_box|depth_proxy|none
    lighting_states: string[]
    continuity_rules: string[]
props:
  - prop_id: string
    display_name: string
    reference_assets: string[]
    continuity_rules: string[]
locked: bool
version: string
```

约束规则固定如下：

- 任一 `CharacterBible` 中的 `character_id` 不得重复
- 任一 `SceneBible` 中的 `location_id / prop_id` 不得重复
- `locked=true` 后，若要修改 bible，必须重新走 `Gate 1`
- `StyleBible.hero_reference_assets` 至少保留 `8-20` 张代表性关键帧或参考图

### 9.4 `ShotSpec` 字段契约

`ShotSpec` 是整条工作流的核心对象，所有后续模块都围绕它展开。  
实现者不得把 `ShotSpec` 简化成只有一句 prompt 的结构。

最小字段集合固定如下：

```yaml
shot_id: string
scene_id: string
sequence_id: string
grade: A|B|C
archetype: hero_cinematic|narrative_multi_shot|reference_storytelling|motion_control|action_heavy|dialogue_native_audio|reference_consistency|insert_cutaway
story_purpose: string
duration_target_sec: int
aspect_ratio: 16:9|9:16|1:1|2.39:1
subject: string
location: string
action: string
camera: string
style: string
needs_native_audio: bool
needs_reference_consistency: bool
needs_motion_control: bool
continuity:
  character_ids: string[]
  wardrobe_ids: string[]
  location_id: string
  prop_ids: string[]
references:
  image_refs: string[]
  video_refs: string[]
  text_refs: string[]
provider_constraints:
  allowed_providers: string[]
  banned_providers: string[]
  preferred_first_tier: bool
post_requirements:
  lip_sync: bool
  interpolation: bool
  upscale: bool
  color_match: bool
budget_class: hero|standard|cheap
```

约束规则固定如下：

- `grade=A` 的镜头必须同时填写 `story_purpose`、`duration_target_sec`、`continuity`
- `archetype` 必须是单值主标签，不允许缺失
- 若 `needs_reference_consistency=true`，则 `references.image_refs` 不得为空
- 若 `needs_motion_control=true`，则 `archetype` 不得为 `insert_cutaway`
- `provider_constraints.allowed_providers` 留空时，默认使用 router 全局矩阵

### 9.5 `PromptPacket` 字段契约

`PromptPacket` 是 `Prompt Compiler` 的输出，代表“同一个 ShotSpec 在某个 provider 上的具体执行形态”。

最小字段集合固定如下：

```yaml
packet_id: string
shot_id: string
provider: string
provider_model: string
prompt_main: string
prompt_blocks:
  subject: string
  location: string
  action: string
  camera: string
  style: string
  continuity: string
  negative_or_avoid: string
  provider_hints: string
negative_prompt: string|null
reference_assets:
  image_refs: string[]
  video_refs: string[]
generation_params:
  duration_sec: int
  aspect_ratio: string
  resolution_tier: standard|hd|pro
  native_audio: bool
  camera_control_mode: none|light|strong
  motion_control_mode: none|pose|video_drive
retry_context:
  retry_count: int
  prior_fail_reasons: string[]
compiler_version: string
```

约束规则固定如下：

- 每个 provider 对同一 `shot_id` 至少允许产出一个 `PromptPacket`
- `provider_model` 必须显式记录，不允许只写 provider 名称
- `retry_context.prior_fail_reasons` 由回流阶段自动补写
- 同一 `shot_id + provider + compiler_version` 组合不得重复生成同一 `packet_id`

### 9.6 `GenerationJob` 与 `JudgeScore` 字段契约

#### `GenerationJob`

```yaml
job_id: string
shot_id: string
packet_id: string
provider: string
provider_model: string
provider_rank: 1|2|3
selected_reason: string
archetype: string
grade: A|B|C
budget_class: hero|standard|cheap
estimated_cost_usd: float
queue_policy: normal|priority|economy
fallback_chain: string[]
status: queued|running|succeeded|failed|canceled|timed_out
external_job_id: string|null
created_at: datetime
updated_at: datetime
```

#### `JudgeScore`

```yaml
judge_score_id: string
candidate_clip_id: string
shot_id: string
provider: string
grade: A|B|C
metrics:
  identity_consistency: float
  scene_consistency: float
  instruction_fidelity: float
  motion_stability: float
  camera_language: float
  image_quality: float
  audio_sync: float|null
  narrative_utility: float
  artifact_penalty: float
weighted_total_score: float
hard_fail: bool
hard_fail_reasons: string[]
decision: pass|review|regenerate_same_provider|reroute_provider|send_to_post_fix|reject
route_back_stage: compile-prompts|route|generate|post|null
judge_model: string
judge_prompt_version: string
created_at: datetime
```

### 9.7 `CandidateClip / Artifact / HumanGateDecision / BudgetLedger` 字段契约

#### `CandidateClip`

`CandidateClip` 表示一个已从 provider 拉回、可供评分与入围的候选视频片段。

```yaml
candidate_clip_id: string
job_id: string
shot_id: string
provider: string
provider_model: string
artifact_path: string
thumbnail_path: string|null
duration_sec: float
resolution: string
has_native_audio: bool
source_type: text2video|image2video|reference2video|motion_control|extend
artifact_hash: string
status: ready|corrupt|missing
created_at: datetime
```

#### `Artifact`

`Artifact` 是所有中间产物和最终产物的统一索引对象，不限于视频。

```yaml
artifact_id: string
run_id: string
artifact_type: raw_video|raw_image|shot_segment|keyframe|reference_pack|bible|prompt_packet|candidate_clip|judge_report|post_clip|sequence|report
artifact_path: string
source_stage: string
source_id: string|null
content_hash: string
file_size_bytes: int
retention_policy: keep|cache|delete_after_run
created_at: datetime
```

#### `HumanGateDecision`

`HumanGateDecision` 用于记录 Gate 1-4 的人工决策。

```yaml
gate_decision_id: string
run_id: string
gate_name: gate_1|gate_2|gate_3|gate_4
status: waiting|approved|rejected|expired
reviewer: string
decision_summary: string
approved_ids: string[]
rejected_ids: string[]
notes: string
created_at: datetime
updated_at: datetime
```

#### `BudgetLedger`

`BudgetLedger` 是预算与成本的唯一事实来源。

```yaml
ledger_id: string
run_id: string
provider: string
job_id: string|null
event_type: reserve|commit|refund|adjust
budget_class: hero|standard|cheap
estimated_cost_usd: float
actual_cost_usd: float|null
currency: USD
notes: string
created_at: datetime
```

约束规则固定如下：

- `CandidateClip.artifact_hash` 相同的片段不得重复写入不同 `candidate_clip_id`
- `Artifact.retention_policy=keep` 的产物不得被自动清理
- `HumanGateDecision.status=approved` 后，必须至少有一个 `approved_ids`
- `BudgetLedger.event_type=commit` 的记录必须与某个 `job_id` 或批次来源绑定

### 9.8 目录产物命名规范与生命周期规则

#### 命名规范

目录与文件命名必须满足“可回溯、可 grep、可排序”三条原则。  
默认命名模板固定如下：

- 原始视频：
  - `workspace/raw_videos/{reference_asset_id}__{source_stem}.mp4`
- 原始图片：
  - `workspace/raw_images/{reference_asset_id}__{source_stem}.png`
- 切镜片段：
  - `workspace/shots/{scene_id}/{shot_id}__segment_{index}.mp4`
- 关键帧：
  - `workspace/keyframes/{shot_id}__kf_{frame_no}.png`
- prompt packet：
  - `workspace/prompts/{shot_id}__{provider}__v{compiler_version}.json`
- 生成候选：
  - `workspace/candidates/{shot_id}/{provider}__rank{provider_rank}__job_{job_id}.mp4`
- 评分结果：
  - `workspace/review/{shot_id}__judge_{judge_score_id}.json`
- 后期结果：
  - `workspace/post/{shot_id}__post_{strategy_id}.mp4`
- 序列装配结果：
  - `workspace/reports/{run_id}__assembly_manifest.json`
  - `workspace/reports/{run_id}__budget_report.json`

禁止行为：

- 禁止使用空格作文件名分隔符
- 禁止只用自然语言句子当作产物文件名
- 禁止不带 `shot_id / provider / job_id` 的候选视频命名

#### 生命周期规则

各类产物的默认保留策略固定如下：

- `raw_videos / raw_images / reference_pack / bibles / judge_reports / final sequence / reports`
  - `retention_policy = keep`
- `shot_segments / keyframes / prompt packets / candidate clips / post clips`
  - `retention_policy = cache`
- 临时下载包、解压中间文件、失败的空文件、过期截图
  - `retention_policy = delete_after_run`

自动清理规则固定如下：

- `delete_after_run` 仅在 `run.status in [completed, failed, canceled]` 后允许清理
- `cache` 类产物默认保留最近 `N=3` 次运行版本
- 若磁盘空间告警，则优先清理 `delete_after_run`，再清理最旧的 `cache`
- `keep` 类产物必须显式人工确认才可删除

回放与复现实验规则固定如下：

- 任何进入 `Gate 3` 的候选必须能通过 `candidate_clip_id` 反查到：
  - `job_id`
  - `packet_id`
  - `shot_id`
  - `provider_model`
  - `judge_score_id`
- 任何进入 `Gate 4` 的序列镜头必须能反查其全部祖先产物链

### 9.9 `Prompt Spec` 示例

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

### 9.10 Provider Adapter 统一接口

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

### 9.11 工作目录建议

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

### 9.12 错误码与失败原因 Taxonomy

系统必须统一使用结构化错误码，禁止仅返回自由文本错误消息。  
错误码格式固定为：

```text
MG_<DOMAIN>_<CODE>
```

其中 `DOMAIN` 只允许取以下值：

- `INGEST`
- `ANALYZE`
- `BIBLE`
- `BENCHMARK`
- `PROMPT`
- `ROUTE`
- `PROVIDER`
- `JUDGE`
- `POST`
- `ASSEMBLY`
- `SYSTEM`

推荐的基础错误码集合固定如下：

| 错误码 | 含义 | 默认动作 |
|---|---|---|
| `MG_INGEST_001` | 输入文件不存在 | 记录失败并跳过单文件 |
| `MG_INGEST_002` | 文件格式不支持 | 记录失败并跳过单文件 |
| `MG_INGEST_003` | 媒体解码失败 | 标记坏文件 |
| `MG_ANALYZE_001` | 参考分析失败 | 回退到粗粒度分析 |
| `MG_BIBLE_001` | Bible 构建不完整 | 阻断后续并等待 Gate 1 |
| `MG_BENCHMARK_001` | 候选 provider 大面积失败 | 重新 benchmark |
| `MG_PROMPT_001` | Prompt 编译失败 | 回流编译器 |
| `MG_ROUTE_001` | 无可用 provider | 暂停并请求人工确认 |
| `MG_PROVIDER_001` | API 提交失败 | 自动重试 |
| `MG_PROVIDER_002` | API 轮询超时 | 切换 fallback |
| `MG_PROVIDER_003` | 产物下载失败 | 单独重试下载 |
| `MG_JUDGE_001` | 评分失败 | 允许重评，不重生成 |
| `MG_JUDGE_002` | 候选硬失败 | 直接回流 |
| `MG_POST_001` | 后期处理失败 | 保留 pre-post 回退 |
| `MG_ASSEMBLY_001` | 序列装配失败 | 不影响已产生产物 |
| `MG_SYSTEM_001` | SQLite 状态冲突 | 终止当前 run |
| `MG_SYSTEM_002` | 磁盘空间不足 | 触发清理策略并暂停 |
| `MG_SYSTEM_003` | 预算硬停 | 阻止新生成任务 |

失败原因分类固定为以下枚举，不允许自由扩散：

- `missing_input`
- `unsupported_format`
- `decode_failure`
- `reference_mismatch`
- `identity_drift`
- `scene_drift`
- `motion_collapse`
- `camera_mismatch`
- `native_audio_mismatch`
- `provider_timeout`
- `provider_queue_overload`
- `provider_output_corrupt`
- `artifact_missing`
- `budget_exceeded`
- `state_conflict`
- `manual_gate_rejected`

错误处理优先级固定如下：

- `fatal`
  - 终止当前 run 或阻断关键 stage
  - 例：`state_conflict`、`budget_exceeded`
- `recoverable`
  - 自动重试或回流
  - 例：`provider_timeout`、`camera_mismatch`
- `skippable`
  - 记录后跳过单文件或单候选
  - 例：`unsupported_format`、`artifact_missing`

### 9.13 日志、审计与可观测性字段

系统必须同时输出三类日志：

- `run log`
  - 面向整次执行
- `stage log`
  - 面向单个阶段
- `job log`
  - 面向单个 provider 任务

所有日志记录必须包含以下基础字段：

```yaml
timestamp: datetime
run_id: string
stage_name: string|null
shot_id: string|null
job_id: string|null
provider: string|null
level: DEBUG|INFO|WARN|ERROR
event_type: string
message: string
error_code: string|null
metadata: object
```

必须额外记录的可观测性指标固定如下：

- `queue_wait_sec`
- `generation_duration_sec`
- `download_duration_sec`
- `judge_duration_sec`
- `post_duration_sec`
- `estimated_cost_usd`
- `actual_cost_usd`
- `retry_count`
- `fallback_depth`
- `artifact_size_bytes`

审计日志的最低要求固定如下：

- 每次 `Gate 1-4` 决策必须留下审计记录
- 每次 provider 路由选择必须留下 `route_reason`
- 每次成本从 `reserve -> commit` 的变化必须留痕
- 每次删除 `cache` 或 `delete_after_run` 产物必须留痕

建议的日志落盘路径固定如下：

```text
workspace/logs/
  runs/{run_id}.jsonl
  stages/{run_id}__{stage_name}.jsonl
  jobs/{job_id}.jsonl
```

指标聚合报表最低要求固定如下：

- 每个 provider 的平均通过率
- 每个 archetype 的平均总分
- 每个 stage 的平均耗时
- 每美元可获得的有效候选数
- 第一梯队 provider 与第二梯队 provider 的命中率对比

### 9.14 CLI 命令参数与返回码约定

CLI 必须统一采用 `Typer` 风格子命令，不允许混用多套风格。  
最小命令集合固定如下：

```text
moviegen run
moviegen resume
moviegen status
moviegen benchmark
moviegen gate
moviegen report
moviegen clean
```

核心命令规范如下：

#### `moviegen run`

```bash
moviegen run project.yaml --stage all --run-id <optional> --force-stage <optional> --dry-run
```

参数约定：

- `project.yaml`
  - 必填
- `--stage`
  - 默认 `all`
  - 允许值：`ingest|analyze|bibles|benchmark|plan|compile-prompts|route|generate|judge|review|post|assemble|report|all`
- `--run-id`
  - 可选；用于恢复或指定一次运行
- `--force-stage`
  - 可选；允许重跑某个已成功阶段
- `--dry-run`
  - 只验证配置与路由，不提交 provider 任务

#### `moviegen resume`

```bash
moviegen resume --run-id <run_id>
```

参数约定：

- `--run-id`
  - 必填；恢复一个已暂停或失败但可恢复的执行

#### `moviegen gate`

```bash
moviegen gate --run-id <run_id> --gate gate_2 --approve ids.json
moviegen gate --run-id <run_id> --gate gate_3 --reject ids.json
```

参数约定：

- `--run-id`
  - 必填
- `--gate`
  - 必填；`gate_1|gate_2|gate_3|gate_4`
- `--approve`
  - 可选；批准的对象清单
- `--reject`
  - 可选；拒绝的对象清单

#### `moviegen clean`

```bash
moviegen clean --run-id <run_id> --scope cache
```

参数约定：

- `--scope`
  - `cache|tmp|all_safe`
- 不允许通过 CLI 直接清理 `keep` 类产物

返回码约定固定如下：

- `0`
  - 成功完成
- `10`
  - 参数错误
- `20`
  - 配置校验失败
- `30`
  - 缺少输入或路径错误
- `40`
  - Gate 等待中，命令正常退出但流程暂停
- `50`
  - provider 层失败
- `60`
  - judge 或 review 阶段失败
- `70`
  - 预算硬停
- `80`
  - 状态机冲突或数据库错误
- `90`
  - 未知系统错误

CLI 输出约定固定如下：

- 面向人类的终端输出保持简短
- 面向机器的结构化结果统一落在：
  - `stdout` 的一行 JSON 摘要
  - `workspace/reports/` 下的完整结果文件

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
