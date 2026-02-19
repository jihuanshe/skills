---
name: reflect
description: 'Review and verify code review suggestions. Triggers: reflect review, verify suggestions, check review.'
metadata:
  version: '4'
---

# 审查反思

## 上下文收集

如果用户要求审查 PR / GitHub review 评论，但尚未提供建议列表：

1. 自动检测当前分支的 PR：`gh pr view --json number,url 2>/dev/null`
2. 通过 `gh api repos/{owner}/{repo}/pulls/{number}/comments` 获取 PR review 数据
3. 收集完成后，将建议列表作为输入填入下方 `<context>` 块，继续反思流程

如果用户直接粘贴了建议文本，跳过收集步骤，直接进入反思。

### 审查上下文

```text
$ARGUMENTS
```

## 任务定义

上方建议由审查者通过静态阅读代码和 diff 生成，可能是真实问题，也可能是幻觉。对每条建议深度检索和思考，给出判断，并提出最小修复方案。

## 验证手段

按以下顺序递进验证每条建议，按需深入，不必每条都走完全部步骤。

### 读代码：理解真实上下文

- 阅读 diff 涉及的源文件，向上追溯调用方、向下追踪被调用方，理解完整调用链
- 搜索函数名、变量名、类名在仓库中的所有引用位置，确认影响面
- 对比新旧代码的等价风险：如果建议指出的风险在旧代码中同样存在，则不是新引入的问题
- 如果仓库中有类似的已有实现，对比写法差异来判断建议是否合理
- Amp 增强：`Read` 直接读文件 · `Grep` ripgrep 精确搜索 · `finder` 语义搜索调用链

### 读依赖：获取一手真相

当建议涉及第三方库行为时，不要猜测，去读源码：

- 先定位文件：`python -c "import X; print(X.__file__)"` 获取库的实际安装路径
- 然后直接阅读该路径下的源文件
- 通过 `python -c "import X; help(X.method)"` 或 `inspect.getsource(X.method)` 获取运行时类型签名和实现
- 如果代码依赖其他仓库（SDK、proto 定义、共享库），查看那些仓库的对应代码
- Amp 增强：`Read .venv/...` 直接读 SDK 源码 · `Bash: python -c` 类型内省 · `librarian` 查询 GitHub 上的跨仓库代码

### 查文档：对齐当前版本

- 查询库的官方文档、changelog、migration guide，确认当前版本的行为
- 在 GitHub Issues / Discussions 中搜索相关关键词，看是否有已知问题
- 确保认知与当前（2026 年）对齐，而非依赖训练数据中的过时信息
- Amp 增强：`web_search` + `read_web_page` 实时搜索并阅读网页

### 跑验证：用事实说话

- 运行仓库约定的静态检查（linter、type checker、formatter）
- 优先运行与建议直接相关的最小测试集，而非全量测试
- 当现有测试不覆盖建议场景时，写一个一次性脚本验证假设
- Amp 增强：`Bash` 执行命令

### 问专家：仍不确定时

- 对复杂的跨文件 bug 推理、架构级问题，寻求深度分析
- 如果建议涉及特定领域知识，加载对应的领域专家
- 当有多条独立建议需要验证时，可并行分别验证
- Amp 增强：`oracle` 深度推理 · 加载 Skill（`ty`/`postgres`/`modal` 等）· `Task` 并行子 Agent

## 输出要求

对每条建议，生成以下结构：

```markdown
### 论据

### 推理

### 结论

1. 真实问题
2. 幻觉 / 过度优化
3. 待定（需要更多上下文）

### 严重程度

1. 崩溃 / 严重数据丢失 / 数据损坏
2. 高概率 bug
3. 边缘情况 / 低概率
4. 纯优化

### 建议操作

- 真实问题：提供**最小风险修复**（优先小补丁而非重构），并注明可能的副作用
- 幻觉 / 过度优化：解释为何不需要改动；如果误判源于代码中缺少业务上下文，建议添加澄清注释
- 待定：添加到末尾的"待解答问题"部分；说明需要哪些信息才能得出结论
```

反思完成后，根据结论采取行动：

- **发现真实问题**：询问用户是否修复，或直接提供最小补丁
- **全部为幻觉**：在 PR 上留下汇总评论，解释每条建议的拒绝理由
- **需要解决 review thread**：通过 `gh api repos/{owner}/{repo}/pulls/{number}/reviews` 和 `gh pr review` 管理 review thread
