---
name: modal
description: 'Deploy, test, and debug serverless apps with Modal. Triggers: modal, modal deploy, modal serve, modal app, modal run, serverless, spawn_map, latency, tunnel, e2e test modal.'
metadata:
  version: '30'
---

# Modal

Modal 把 Python 函数变成云端容器。写一个函数，声明它需要什么（CPU、GPU、依赖、密钥），Modal 负责打包、调度、缩扩容。

## 核心原语

- **App**：部署单元，包含一组 Function/Cls。一个 `.py` 文件通常对应一个 App。
- **Function**：执行单元。`@app.function()` 装饰一个普通函数，声明硬件和依赖。默认应按「可能被重试 / 重跑」的执行语义来设计。
- **Cls**：容器复用与生命周期 hook 的执行单元。`@app.cls()` 装饰一个类，`@modal.enter()` 做一次性初始化，`@modal.method()` 处理请求。`self` 上的状态默认只是容器内缓存，不是 durable state。
- **Image**：容器镜像。链式构建：`modal.Image.debian_slim().uv_pip_install("torch")`。
- **Secret**：密钥注入。`modal.Secret.from_name("my-secret")` 将键值对注入环境变量。
- **Sandbox**：长会话、可复用容器，适合 agent / 不可信代码 / 浏览器 / 代码解释器。普通 CPU Sandbox 默认不受 preemption 影响；GPU Sandbox 可能被抢占。
- **Volume / Dict / Queue**：分别用于文件、KV、消息传递。它们是存储/协调对象，不是业务语义上的「唯一事实来源」；持久业务状态优先放数据库。

## 心智模型：执行语义与生命周期

不要把 Modal 当成传统常驻后端。先区分三类对象：

- **计算原语：Function / Cls / web endpoint**
  - 这是「会执行代码」的地方。
  - 每个 Function 对应一个 autoscaling container pool，默认可 scale-to-zero。
  - `Function` 默认可能被 preempt；容器 crash 时，当前工作会被重新调度；配置了 `retries=` 时会再次尝试；`timeout` 按 **每次 attempt** 单独计时。
  - `web_endpoint` / `fastapi_endpoint` / `asgi_app` / `wsgi_app` 本质上也属于 Function 的 web 暴露形式；HTTP 请求层有 150 秒上限，超出后会返回 303 result URL。
  - **因此：有副作用的代码必须按「可能重跑」设计。默认心智模型是 `at-least-once-ish`，不是 `exactly-once`。**
- **容器复用：Cls 不是持久状态机**
  - `@app.cls()` 的价值主要是容器复用、`@modal.enter()` 初始化、`@modal.exit()` 清理，以及把多个方法放到同一组容器里服务。
  - `Cls` 上的状态默认只是**容器内内存状态**（例如模型、缓存、DB client）。它可能因为扩缩容、重建、抢占、crash 而消失；也可能同时存在多个容器副本。
  - 不要把 `self` 上的数据当成 durable state；业务真相应放到外部数据库/对象存储。
- **交互原语：Sandbox**
  - Sandbox 是长会话、可复用容器，不是一次性 Function 调用。
  - 默认最大生命周期 5 分钟，可配置到 24 小时；可设置 `idle_timeout`。
  - 可通过 `Sandbox.from_id()` / `Sandbox.from_name()` 重新接回运行中的 Sandbox。
  - `detach()` 只是断开本地连接，不等于停止 Sandbox。
  - 普通 Sandbox 默认**不受 preemption 影响**；带 `gpu=` 的 Sandbox 例外，可能被抢占。
  - 适合 agent、代码解释器、浏览器自动化、长会话服务。
- **持久化/协调原语：App / Image / Secret / Volume / Dict / Queue**
  - 它们不是「自己跑业务代码的 worker」。真正会被中断的是访问它们的 Function / Cls / Sandbox。
  - `Volume` 更适合文件、缓存、模型权重、checkpoint；`Dict` 是分布式 KV；`Queue` 适合活动函数之间传递消息，不应当作持久业务真相源。
  - 业务状态优先放外部数据库（例如 Postgres）。

### 设计规则：副作用与幂等

- **纯读 / 纯计算**：允许重跑。
- **有副作用**（写 PG、发邮件、发 webhook、扣费、调用会改变外部状态的 API）：必须幂等。优先使用业务 `operation_id` / idempotency key + 数据库唯一约束 / 状态机事务收口。
- **长任务**：拆成小步并频繁 checkpoint。不要把 `@modal.exit()` 当唯一保存点；它在 preemption 时只有有限 grace period。
- **Web handler**：只做短事务、入队、查状态。长任务优先异步化，不要强依赖同步 HTTP。
- **启用 `@modal.concurrent` 时**：同一容器会并发处理多个 inputs；同步函数使用多线程，代码必须 thread-safe；`self` 上的可变状态要谨慎。
- **`nonpreemptible=True`**：只适用于 CPU `Function` / `Cls`；GPU Function 不支持。它只能去掉「抢占」这一种失败模式，不能替代幂等、重试和 checkpoint 设计。

### 选型决策：Function vs Cls vs Sandbox

- 需要 **短任务 / HTTP 接口 / batch fan-out**：先想 `Function`。
- 需要 **模型常驻 / expensive init / 生命周期 hooks**：先想 `Cls`。
- 需要 **长会话 / 任意命令 / 不可信代码 / agent 工具执行**：先想 `Sandbox`。
- 需要 **持久业务状态**：先想外部数据库，不要先想 `Cls.self` / 本地磁盘 / Queue。

**模块级代码在远端容器也会执行。** 容器启动时重新 import 模块以重建依赖图，本地文件系统操作须用 `modal.is_local()` 守卫。容器内也可以用环境变量 `MODAL_IS_REMOTE=1` 判定远端（调试时比 `modal.is_local()` 更直观）。

## 文档与源码查阅

Modal API 用法先查官方源：

**文档**：

```bash
# 索引，定位目标页面
curl -sf https://modal.com/llms.txt

# Guide / Examples 均支持 .md 后缀
curl -sf https://modal.com/docs/guide/<topic>.md
curl -sf https://modal.com/docs/examples/<example>.md
```

API Reference（`/docs/reference/modal.App` 等）不支持 `.md`，用源码替代。

**源码**：精确 API 签名与实现（App -> app.py, Image -> image.py）：

```bash
# 定位 modal 安装目录（不依赖 .venv 路径或 Python 版本）
python -c 'import modal, pathlib; print(pathlib.Path(modal.__file__).resolve().parent)'
# 然后在该目录下查看 app.py / image.py / cls.py 等
```

## 操作闭环：Preflight → 行动 → 验证 → 诊断

### 1. Preflight

任一项失败即停止。

```bash
# 确认身份
modal profile current || { echo "BLOCK: 无法获取 profile"; exit 1; }
modal config show --redact | jq -e .token_id || { echo "BLOCK: 无有效 token"; exit 1; }

# 确认环境已设置且不是 prod
ENV=$(modal config show 2>/dev/null | jq -r '.environment // "null"')
if [[ "$ENV" == "null" ]]; then
  echo "BLOCK: modal environment 未设置。运行: modal config set-environment dev"; exit 1
fi
if [[ "$ENV" == "prod" ]]; then
  echo "BLOCK: 当前默认环境是 prod。若确实要 prod，所有命令显式带 --env prod"; exit 1
fi
```

失败修复：`modal token new` · `modal profile activate <p>` · `modal config set-environment dev`

### 2. 行动：run / serve / deploy

`modal run <file>::<func>`：执行一个函数或 `local_entrypoint`，完成即退。无 web URL。加 `-d` 进入分离模式（本地断连后远端继续运行，但本地进程仍阻塞）。

`modal serve <file>`：启动 web endpoint，热重载，URL 带 `-dev` 后缀。**阻塞终端**（放 tmux）。用于开发调试。

`modal deploy <file>`：持久部署，直到 `modal app stop`。只有定义了 web endpoint（`asgi_app` / `wsgi_app` / `fastapi_endpoint` / `web_endpoint` / `web_server`）的 App 才会输出 `https://...modal.run` URL。加 `--tag` 可标记版本。

部署命令须对齐 `mise --env` 和 `modal --env`：

```bash
# Dev
mise exec --env dev -- modal deploy --env dev <file>
# Prod（须人工确认）
mise exec --env prod -- modal deploy --env prod <file>
```

URL 从 stdout 获取，不猜：

```bash
modal deploy <f> 2>&1 | grep -oE 'https://[^ ]+\.modal\.run'
```

### 3. 验证：web vs non-web

```bash
OUT=$(modal deploy <f> 2>&1)
URL=$(printf "%s" "$OUT" | grep -oE 'https://[^ ]+\.modal\.run' | head -1 || true)

if [[ -n "${URL:-}" ]]; then
  # Web app：curl /health，用 --retry 等待冷启动，不用 sleep
  curl --max-time 15 --retry 3 --retry-delay 5 --retry-all-errors -sf "$URL/health" | jq -e '.status == "ok"'
else
  # Non-web app（cron/job/Cls）：确认 app 已注册，检查启动日志
  APP_ID=$(printf "%s" "$OUT" | grep -oE 'ap-[A-Za-z0-9]+' | tail -1 || true)
  [[ -n "${APP_ID:-}" ]] && modal app logs "$APP_ID" 2>&1 | head -100 &
  LOGS_PID=$!; ( sleep 30; kill "$LOGS_PID" 2>/dev/null ) &
  wait "$LOGS_PID" 2>/dev/null || true
fi
```

### 4. 诊断：环境 → 日志 → 容器 → Shell → Debug

按成本递增排查。CLI 输出字段随版本变化，jq 失败时先查 `modal <cmd> --help` 或 `--json | head`。

**环境**：部署到了错误的 env/profile 是最常见的原因

```bash
modal app list --json | jq '.[] | select(.Description | contains("<app>"))'
```

**日志**：启动失败、依赖缺失、端口冲突都在这里

```bash
# 阻塞命令，放 tmux 或用后台进程限时
modal app logs <app> 2>&1 | head -100 &
LOGS_PID=$!; ( sleep 30; kill "$LOGS_PID" 2>/dev/null ) &
wait "$LOGS_PID" 2>/dev/null || true
```

**容器**：进入运行中的容器检查

```bash
modal container exec <id> -- nvidia-smi
modal container exec <id> -- python -c "import torch; print(torch.cuda.is_available())"
```

**Shell**：在同一 Image 环境中复现问题

```bash
modal shell <file>::<func>
```

**Debug 日志**：最后手段

```bash
MODAL_LOGLEVEL=DEBUG modal run <f>
```

## 阻塞命令：哪些会挂 Agent

**必须放 tmux**（先加载 tmux skill）：

- `modal serve`：热重载循环，永不退出
- `modal app logs` / `modal container logs`：持续流式输出
- `modal shell`：交互式会话，改用 `modal container exec <id> -- <cmd>`
- `modal deploy --stream-logs`：去掉 `--stream-logs`
- `curl` 无超时：加 `--max-time 10`~`15`

**安全直接运行**：

- `modal deploy`（不带 `--stream-logs`）
- `modal app list` / `modal app stop` / `modal app history`
- `modal container list` / `modal container exec`
- `modal run`（会阻塞到完成，长任务放 tmux）

**`modal run -d` 仅防止本地断连后远端清理，本地进程仍阻塞。长任务始终走 tmux。**

## 常见陷阱

### 依赖图不匹配

容器重新 import 模块重建依赖图，App 声明在本地与远端必须一致。`modal.is_local()` 只用于守卫本地副作用（读文件、git），不能改变 App 声明。

```python
# ❌ 本地 2 deps，远端 1 dep，导致容器报错
if modal.is_local():
    image = build_workspace_image("core")
    _secrets = [modal.Secret.from_local_environ(["TOKEN"])]
else:
    image = modal.Image.debian_slim()
    _secrets = []

@app.function(image=image, secrets=_secrets)
def f(): ...

# ✅ 方案 A：统一用 from_name（推荐，Secret 预先在 dashboard/CLI 创建）
if modal.is_local():
    image = build_workspace_image("core")
else:
    image = modal.Image.debian_slim()

@app.function(image=image, secrets=[modal.Secret.from_name("my-secret")])
def f(): ...

# ✅ 方案 B：本地用 from_dict 转发 shell 变量，远端用 from_name，两端都是 1 个 Secret
if modal.is_local():
    _secret = modal.Secret.from_dict({"TOKEN": os.environ.get("TOKEN", "")})
else:
    _secret = modal.Secret.from_name("my-secret")

@app.function(image=image, secrets=[_secret])
def f(): ...
```

`from_dict` 和 `from_dotenv` 适合本地开发转发环境变量。关键是**两个分支的 secrets 列表长度必须一致**。

### is_local() 守卫

本地文件系统操作须守卫，`else` 分支须为所有变量提供占位值：

```python
# ❌ 远端 NameError
if modal.is_local():
    image = build_workspace_image("core")

# ✅
if modal.is_local():
    image = build_workspace_image("core")
else:
    image = modal.Image.debian_slim()
```

### serialized=True

Pickle 序列化函数，容器不重新 import。适用于 `modal run` 的工具脚本（如 `clone_secret.py`）。与 `@modal.asgi_app()` / `@modal.wsgi_app()` 组合使用时，序列化/反序列化环节可能失败。Web 服务通过保持依赖图一致解决，不用 `serialized=True`。

### Secret 覆盖 `.env()`

Secret env vars 优先级高于 image `.env()`。Secret 里有 `ENV=dev`，即使部署到 prod，容器仍然看到 `ENV=dev`。

Secret 里只放密钥（token、key、password），配置放 image `.env()` 或从 `MODAL_ENVIRONMENT` 推导。

### 模块级 import

重依赖（`torch`、`transformers`）不放模块顶部——模块级代码在所有环境都执行，Image 外的 import 会 `ImportError`。

- **Function**：import 放函数体内
- **Cls**：import 和模型加载放 `@modal.enter()`（每容器一次），不放 `@modal.method()`（每请求重复）

```python
@app.cls(image=image, gpu=GPU)
class Model:
    @modal.enter()
    def load(self):
        import torch  # 重依赖在此 import
        self.device = torch.device("cuda")
```

## 项目约定

### 命名

文件 `snake_case`，Modal 原语 `kebab-case`。两者解耦。

```text
{domain}-{service}[-{variant}]
```

- Domain：可选，消歧用（`eye-`、`webhook-`、`search-`、`mapper-`、`demo-`）
- Service：必填，自解释（`sync-upper-decks`、`crawl-lol-prices`）
- Variant：可选（`-v2`、`-obb`）

```python
MODAL_APP_NAME: str = "decks"
MODAL_SECRET_NAME: str = MODAL_APP_NAME

# App 内资源追加后缀
processed_deck_history = modal.Dict.from_name(f"{MODAL_APP_NAME}-history", create_if_missing=True)
```

`from_name` 远程引用时，第一个参数是 App 名，第二个是类/函数名，须精确匹配：

```python
Service = modal.Cls.from_name("eye-embed-prod-v2", "EmbeddingModel")
```

### 环境

默认环境 `dev`（`modal config set-environment dev`）。`prod` 须显式 `--env prod`。

### Workspace Image

需要挂载本地 workspace package 时，在 `if modal.is_local():` 块内 inline 依赖解析函数，确保单文件自洽。参考实现和 self-test：`workspace_image.py`。

### Secret 管理

- 创建：`modal secret create <name> KEY1=val1 KEY2=val2 --env dev`
- Web 服务用 `from_name`，工具脚本可用 `from_local_environ` + `serialized=True`
- 导出/克隆：`clone_secret.py`（CLI 无 export 命令，该脚本用 diff 方式提取）

### Dict（分布式键值存储）

`modal.Dict.from_name("name", create_if_missing=True)` 创建或引用持久化 Dict。值用 `cloudpickle` 序列化。

限制：单对象 ≤ 100 MiB（建议 < 5 MiB），单次更新 ≤ 10,000 条，**7 天无读写自动过期**。可变值修改后须显式写回（`d[k] = updated_obj`），嵌套赋值 `d["a"]["b"] = v` 不会同步。

多容器可并发读写同一 Dict，但 `d[k] = v` 不是事务性的——无内置锁。需要原子性时自行协调（如 `max_containers=1`）。

### 多 `local_entrypoint`

一个 App 可注册多个 `@app.local_entrypoint()`。若只有一个，`modal run script.py` 自动使用它。多个时须指定：

```bash
modal run script.py::app.trigger   # 调用 trigger()
modal run script.py::app.reset     # 调用 reset()
```

### 计费

- `min_containers` 未设置（默认 `None`，等效 scale-to-zero）-> 按请求计费
- `min_containers=1` -> 持续计费，叠加 GPU 尤其危险
- `min_containers=0` 与 `None` 行为等价（都是 scale-to-zero），仅作意图声明

### 代码检查

部署前确认：App 有明确名称（`modal.App("kebab-name")`）、Web endpoint 有 `/health`、GPU 函数有 `gpu=` 声明且启动时自检 `torch.cuda.is_available()`。

## E2E 测试

测试 Modal web 服务用 `modal serve` + curl，不写 pytest。完整流程见 [e2e-testing.md](e2e-testing.md)。

## 并发、延迟与隧道

spawn_map、冷启动优化、tunnel 用法见 [concurrency-and-tunnels.md](concurrency-and-tunnels.md)。

## 示例

- HTTP webhook / API -> `example_web.py`
- GPU 推理服务 -> `example_gpu.py`
- 定时任务 -> `example_cron.py`
- 生产级示例（observability、workspace image、dedup）-> 参考 Modal 官方 examples
