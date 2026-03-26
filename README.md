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

## Skillshare 安装与使用

这个仓库是**公司公共 skills 仓库**——同事通过 `skillshare install` 把它装到自己本地的 source 目录里。每个人的 source 目录是一个独立的 Git repo，里面可以同时放自己的 skill、公司的 skill、社区的 skill，然后 `skillshare sync` 一条命令分发到所有 AI CLI。

### 为什么用 Skillshare

你有 Amp、Claude Code、Codex、OpenClaw……每个 AI CLI 都有自己的 skills 目录。你在一个地方改了，另外几个工具就不知道。手动管理必然失控。

[Skillshare](https://github.com/runkids/skillshare) 用一个 source 目录统一管理，symlink 分发到所有 target：

```text
┌────────────────────────────────────────────────────────┐
│  Source = Git Repo (~/.config/skillshare/skills/)      │
│                                                        │
│  1. Your own skills (committed)                        │
│  ├── my-code-review/                                   │
│  ├── my-deploy-checklist/                              │
│                                                        │
│  2. Vendored (committed + .skillshare-meta.json)       │
│  ├── agent-browser/      <- from vercel-labs           │
│  ├── exe.dev/            <- from boldsoftware          │
│                                                        │
│  3. Dependencies (gitignored, _-prefixed, --track)     │
│  ├── _jihuanshe-skills/  <- this repo, --track         │
│  │   ├── logfire/                                      │
│  │   ├── linear/                                       │
│  │   └── ...21 skills                                  │
│  └── _planetscale-database-skills/                     │
│      ├── mysql/                                        │
│      └── postgres/                                     │
└────────────────────────────────────────────────────────┘
                        │
                   skillshare sync (symlink)
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
   ~/.config/amp/    ~/.codex/     ~/.claude/
     skills/          skills/       skills/
```

一处修改，处处生效。新机器几条命令搞定。install 时自动安全审计。

### 三层 Skill 来源

整个 source 目录本身是一个 Git repo（`--remote` 指向你自己的 skills 仓库，比如 `github.com/<你>/skills`）。三种来源的 skill 共存但管理方式不同：

| 层 | 例子 | Git 状态 | 怎么更新 |
| --- | --- | --- | --- |
| **你自己写的** | `my-code-review/`, `my-deploy-checklist/` | ✅ committed | 你自己 `git push/pull` |
| **Vendored（不带 `--track`）** | `agent-browser/`, `exe.dev/` | ✅ committed + `.skillshare-meta.json` 记录上游 | `skillshare update` 从上游拉，更新后 `git commit` |
| **依赖（`--track`）** | `_jihuanshe-skills/`, `_planetscale-database-skills/` | ❌ gitignored（`_` 前缀） | `skillshare update` 从上游拉，不进 git |

- **Vendored 模式**（`skillshare install <url>`）：skill 代码直接 commit 进你的 repo，相当于 fork。`.skillshare-meta.json` 记录了 `repo_url`、`version`、`tree_hash`，所以 `skillshare update` 依然能追踪上游更新。适合你想自己改、或者保证离线可用的 skill。
- **依赖模式**（`skillshare install <url> --track`）：skill 放在 `_` 前缀目录里，自动 gitignore。就像 `node_modules`——你不 commit 它，但 `skillshare update` 随时能拉最新。适合公司仓库、社区仓库这种你不会改的 skill。

新机器恢复流程：`git clone` 你的 repo → 前两层从 git 恢复 → `skillshare install` 重建第三层 → `skillshare sync` 分发到所有 AI CLI。

**其他优势：**

1. **一处修改，处处生效** — `skillshare sync` 一条命令，所有 AI CLI 拿到一模一样的 skills。symlink 方式连 sync 都不用——改了 source 就是改了所有 target。
2. **新机器 / 云主机几条命令搞定** — curl 装 skillshare → init 配 source → install 公司仓库 → sync。
3. **安全审计** — install 时自动扫描，发现 sudo 提权、hardcoded secrets、网络外泄等风险会报告，CRITICAL 级别直接阻断。

### 第一次配置（macOS，你自己的电脑）

**前置条件：** 已安装 [mise](https://mise.jdx.dev/) 或 Homebrew。

```bash
# 1. 装 skillshare（二选一）
brew install skillshare
# 或
mise use -g github:runkids/skillshare@0.17.11

# 2. 初始化（交互式，会自动检测本地已有的 AI CLI）
skillshare init

# init 会问你：
#   - Source 目录放哪？（默认 ~/.config/skillshare/skills/，回车就行）
#   - 要不要关联 Git remote？（填你自己的 skills 仓库地址）
#   - 检测到哪些 target？（amp, claude, codex... 自动发现，确认就行）
#   - 要不要创建一个示例 skill？（随意）

# 3. 安装公司公共 skills
skillshare install https://github.com/jihuanshe/skills --track

# 4. 同步到所有 AI CLI
skillshare sync
```

> **不想交互？** 一行搞定：
>
> ```bash
> skillshare init --source ~/.config/skillshare/skills --remote https://github.com/<你的用户名>/skills --all-targets --mode merge --subdir . --no-skill
> ```

### 第一次配置（云主机 / exe.dev VM）

```bash
# 1. 装 skillshare
curl -fsSL https://raw.githubusercontent.com/runkids/skillshare/main/install.sh | sh

# 2. 非交互初始化（指定你的个人 skills 仓库为 remote）
skillshare init \
  --source ~/.config/skillshare/skills \
  --remote https://github.com/<你的用户名>/skills \
  --targets codex \
  --mode merge \
  --subdir . \
  --no-skill

# 3. 装公司 skills
skillshare install https://github.com/jihuanshe/skills --track

# 4. 同步
skillshare sync
```

关键参数说明：

| 参数 | 含义 |
| ---- | ---- |
| `--remote <url>` | 关联 Git 仓库，让 source 目录变成 Git repo，支持 push/pull |
| `--targets codex` | 只配一个 target（云主机一般只跑 Codex） |
| `--mode merge` | 合并模式（保留 target 里已有的本地 skill） |
| `--subdir .` | 仓库根目录就是 skills 目录（不用子目录） |
| `--no-skill` | 不创建示例 skill |

### 日常使用

```bash
# 公司仓库有更新？
skillshare update _jihuanshe-skills && skillshare sync

# 更新所有 tracked 仓库
skillshare update --all && skillshare sync

# 看当前状态
skillshare status

# 看有哪些更新可用
skillshare check
```

### ⚠️ 常见坑

1. **install 后忘记 sync** — `skillshare install` 只是把 skills 拉到 source，不会自动分发到各 AI CLI。必须跑 `skillshare sync`。
2. **安全审计拦截** — install 时如果有 HIGH/CRITICAL 发现（比如我们的 github-runners 里有 sudo），audit 报告会告诉你。CRITICAL 级别会阻断安装，用 `--force` 跳过。我们仓库的 HIGH 是预期行为（Runner 管理确实需要 sudo），不用担心。
3. **symlink vs copy** — 默认用 symlink，改 source 就等于改了所有 target。如果某个 AI CLI 不支持 symlink，用 `skillshare target <name> --mode copy`。
4. **Git identity 未配置** — 云主机上 init 时如果没有 git config，skillshare 会用默认值。想 push 的话先配：

   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```

5. **CI/linting 冲突** — 如果你的 skills 仓库有 linter（biome, ruff, typos 等），install 进来的第三方 skill 可能不符合你的 lint 规则。需要在 lint 配置里 exclude 掉带 `.skillshare-meta.json` 的目录。用这个命令找到所有需要排除的目录：

   ```bash
   fd -H -t f '.skillshare-meta.json' -x dirname {} | sed 's|^\./||' | sort -u
   ```

### 实际例子：配好后长什么样

可以参考 [github.com/ipruning/skills](https://github.com/ipruning/skills)，这是一个已经配好的个人 skills 仓库。本地 `~/.config/skillshare/skills/` 目录就是这个 repo 的 clone，结构如下：

```text
~/.config/skillshare/skills/          <- git remote: github.com/ipruning/skills
├── demand-audit-v0/                  <- own skill (committed)
├── demand-audit-v1/                  <- own skill (committed)
├── demand-audit-v2/                  <- own skill (committed)
├── prek/                             <- own skill (committed)
├── vps/                              <- own skill (committed)
├── surge-cli/                        <- own skill (committed)
├── agent-browser/                    <- vendored (from vercel-labs)
├── electron/                         <- vendored (from vercel-labs)
├── exe.dev/                          <- vendored (from boldsoftware)
├── skill-creator/                    <- vendored (from anthropics)
├── skillshare/                       <- vendored (from runkids)
├── stl/                              <- vendored (from stainless-api)
├── _jihuanshe-skills/                <- dependency, --track (gitignored)
│   ├── logfire/
│   ├── linear/
│   ├── modal/
│   └── ...21 skills
├── _planetscale-database-skills/     <- dependency, --track (gitignored)
│   ├── mysql/
│   ├── postgres/
│   └── vitess/
├── .gitignore                        <- skillshare auto-manages _ dirs
├── AGENTS.md
├── README.md
└── pyproject.toml                    <- linter config, excludes vendored dirs
```

`.gitignore` 由 skillshare 自动维护，`_` 前缀的依赖目录自动排除：

```gitignore
# BEGIN SKILLSHARE MANAGED - DO NOT EDIT
_jihuanshe-skills/
_planetscale-database-skills/
# END SKILLSHARE MANAGED
```

`skillshare sync` 后，所有 skill 通过 symlink 分发到各 AI CLI：

```text
~/.config/amp/skills/
├── demand-audit-v0 -> ~/.config/skillshare/skills/demand-audit-v0
├── agent-browser   -> ~/.config/skillshare/skills/agent-browser
├── _jihuanshe-skills__logfire -> ~/.config/skillshare/skills/_jihuanshe-skills/logfire
├── _jihuanshe-skills__linear  -> ~/.config/skillshare/skills/_jihuanshe-skills/linear
└── ...
```

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
