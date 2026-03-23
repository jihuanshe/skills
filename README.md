# Skills

## 设计哲学：阿兹海默症实习生

用 LLM，特别是像 Amp 这样的工具时，要把它当成「阿兹海默症的实习生」。你每天早上招了个新实习生，这小伙子看起来很聪明，但他头一天的东西全忘了，每天都是「土拨鼠之日」--醒来都是崭新一天。

这样的实习生怎么用？你不能指望他记住任何隐含信息。他的工作记忆只有你当场给他的 SOP，还有他面前这台电脑。用好他，你得给一份清晰到不能再清晰的 SOP，告诉他「第一步干啥，第二步干啥」，然后再把电脑摆好，把工具链配齐。电脑也就是 LLM 强化学习的反馈环境，也可能是代码库中的命令行或者单测。

啪，你把昨天的事情告诉他，把动作的 SOP（比如 CLAUDE.md 或者 Cursor Rules）放在桌上，然后对他说：「你就照着这个干」。SOP 里有电脑怎么用，命令行怎么敲。因为他没有记忆，他就只能按照你这个流程、用你给他的工具执行命令。

这个实习生还有个奇葩特点：他虽然不记事儿，但他写报告写得特别长，动不动几千字，而且很会来事情。如果管 10 个这样的实习生，你验收任务都会疲于奔命。有两个解题思路：

1. **拆解任务为弱验证任务**--你用 0.2 倍的时间验证 10 个实习生的结果，就能横向 Scale。
2. **升级大脑和 Onboarding**--给他看日志的工具，给他开发体验很好的工具链，让他能自主工作更久不翻车。

所以，让模型做的所有事情，最好都是**幂等的、可复现的**。无论什么时候拿来一份 SOP 或一个代码仓库，这个实习生「现学现卖」，每次得到的结果都大概率一致。这样你不但容易审计，也好调试，坏了大不了重新跑一遍就完事儿了。用这种方式你就把它的「阿兹海默症」特性变成了优势：每天工作完，随时可以把这个实习生「扔掉」，明天再招一个新的。而你的知识全部沉淀在了 SOP、脚本、代码库这些东西里，而不是靠它记在脑子里。

> 先别想着「模型会不会记住什么」，它什么都记不住。你要想着的就是，我怎么提供给它一个好的工作环境，让它当天的表现最好。

**这个仓库就是那堆 SOP。** 21 个技能平铺存放，每个文件夹是一个独立 Skill，包含 SKILL.md（SOP）和可选的 scripts/templates（电脑上的工具）。不做分类嵌套--分类以多种视角记录在下方，作为理解这些 skill 的索引。

## 技能清单

| Skill | 一句话 |
| ------- | -------- |
| amp-skill-smoke | 冒烟测试 SKILL.md 是否自洽 |
| amp-thread-digest | 从 Amp Thread 中萃取知识 |
| amp-todo | 执行代码中的 AMPDO 注释 |
| fasthtml | 用 FastHTML + MonsterUI 写 Web |
| feishu | 飞书 Webhook 通知 |
| github-runners | 管理 GHA 自托管 Runner |
| linear | 查询和分析 Linear Issue |
| linear-plan | 为 Linear Issue 制定实施方案 |
| logfire | 查询/调试 Logfire traces |
| modal | Modal 无服务器部署 |
| openai | OpenAI Responses API 类型安全调用 |
| pr-comments | 拉取并分诊 PR Review 反馈 |
| pr-open | 创建或更新 GitHub PR |
| ralph | Oracle 深度推理 + 交叉验证 |
| reflect | 审查反思：验证 code review 建议 |
| signoz | 生成 SigNoz Dashboard JSON |
| tigris | S3 兼容全球对象存储 |
| tmux | 控制 tmux 会话做交互式操作 |
| turbopuffer | 向量 + 全文搜索 |
| ty | 修 ty 类型错误、探索 SDK 类型 |
| uv | Python 包/项目管理 |

## 分类范式

一维分类永远有妥协。以下记录了 4 种不同视角来理解这 21 个 skill，各有侧重。

### 范式 A：工作阶段

实习生一天的工作流循环：`think -> build -> run -> watch -> ship -> amp` 是怎么流动的？

| 阶段 | 含义 | Skills |
| ------ | ------ | -------- |
| **think** | 推理与验证 | ralph, reflect |
| **build** | 写代码用的工具和知识 | uv, ty, tmux, fasthtml, openai |
| **run** | 让服务跑起来 | modal, github-runners, turbopuffer, tigris |
| **watch** | 看发生了什么 | logfire, signoz |
| **ship** | 交付与协调 | linear, linear-plan, pr-open, pr-comments, feishu |
| **amp** | 自我进化 | amp-skill-smoke, amp-thread-digest, amp-todo |

### 范式 B：信息拓扑

真相住在哪里？本地能 grep 到，还是必须连出去？

| 位置 | 真相在哪 | Skills |
| ------ | --------- | -------- |
| **self** | agent 自己的推理过程 | ralph, reflect, amp-skill-smoke, amp-thread-digest, amp-todo |
| **local** | 本地文件系统 | uv, ty, tmux |
| **doc** | 外部文档/规范（构建时消费） | fasthtml, openai, tigris |
| **state** | 远端有活着的服务/状态 | modal, github-runners, turbopuffer, logfire, signoz |
| **sync** | 双向协调通道 | linear, linear-plan, pr-open, pr-comments, feishu |

### 范式 C：交互模式

Agent 加载这个 skill 后，做的动作本质是什么？

| 模式 | 怎么交互 | Skills |
| ------ | --------- | -------- |
| **reason** | 纯思考，不产生 I/O | ralph, reflect |
| **refer** | 查文档/规范，然后写代码 | fasthtml, openai, uv, ty, tigris |
| **operate** | 执行命令，管理进程/容器 | modal, github-runners, tmux |
| **query** | 从外部拉数据看 | logfire, signoz, turbopuffer |
| **coordinate** | 双向同步：拉上下文 + 推状态 | linear, linear-plan, pr-open, pr-comments, feishu |
| **meta** | 改进 agent 自身 | amp-skill-smoke, amp-thread-digest, amp-todo |

### 范式 D：四象限

最简分类：agent 戴的是哪顶帽子？

| 角色 | 干什么 | Skills |
| ------ | -------- | -------- |
| **think** | 架构师：想清楚再动手 | ralph, reflect, amp-skill-smoke, amp-thread-digest, amp-todo |
| **make** | 开发者：写代码 | uv, ty, tmux, fasthtml, openai |
| **ops** | 运维：管外部服务 | modal, github-runners, turbopuffer, tigris, logfire, signoz |
| **ship** | PM：交付协调 | linear, linear-plan, pr-open, pr-comments, feishu |
