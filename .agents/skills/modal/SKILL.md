---
name: modal
description: 'Deploy, test, and debug serverless apps with Modal. Triggers: modal, modal deploy, modal serve, modal app, modal run, serverless, spawn_map, latency, tunnel, e2e test modal.'
metadata:
  version: '28'
---

# Modal

Modal 把 Python 函数变成云端容器。写一个函数，声明它需要什么（CPU、GPU、依赖、密钥），Modal 负责打包、调度、缩扩容。

五个原语撑起整个系统：

- **App**：部署单元，包含一组 Function/Cls。一个 `.py` 文件通常对应一个 App。
- **Function**：执行单元。`@app.function()` 装饰一个普通函数，声明硬件和依赖。
- **Cls**：有状态的执行单元。`@app.cls()` 装饰一个类，`@modal.enter()` 加载模型，`@modal.method()` 处理请求。
- **Image**：容器镜像。链式构建：`modal.Image.debian_slim().uv_pip_install("torch")`。
- **Secret**：密钥注入。`modal.Secret.from_name("my-secret")` 将键值对注入环境变量。

关键事实：**模块级代码在远端容器也会执行。** 容器启动时重新 import 整个模块来重建依赖图。本地文件系统操作、`git` 命令等必须用 `modal.is_local()` 守卫。

## 查阅

本文档覆盖项目约定和不可自行发现的陷阱。Modal 自身的 API 用法，先查证再作答。

**文档**：概念、用法、完整示例：

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

## 操作闭环

每次 Modal 操作遵循四步：Preflight -> 行动 -> 验证 -> 诊断。不跳步。

### Preflight

任何操作前执行。任一项失败即停止。

```bash
# 确认身份
modal profile current || { echo "BLOCK: 无法获取 profile"; exit 1; }
modal config show | jq -e .token_id || { echo "BLOCK: 无有效 token"; exit 1; }

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

### 行动

三条命令，三种生命周期：

`modal run <file>::<func>`：执行一个函数或 `local_entrypoint`，完成即退。无 web URL。加 `-d` 进入分离模式（本地断连后远端继续运行，但本地进程仍阻塞）。

`modal serve <file>`：启动 web endpoint，热重载，URL 带 `-dev` 后缀。**阻塞终端**（放 tmux）。用于开发调试。

`modal deploy <file>`：持久部署，直到 `modal app stop`。只有定义了 web endpoint（ASGI/WSGI/webhook）的 App 才会输出 `https://...modal.run` URL。加 `--tag` 可标记版本。

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

### 验证

部署后立即验证。区分 web 与 non-web：

```bash
OUT=$(modal deploy <f> 2>&1)
URL=$(printf "%s" "$OUT" | grep -oE 'https://[^ ]+\.modal\.run' | head -1 || true)

if [[ -n "${URL:-}" ]]; then
  # Web app：curl /health，用 --retry 等待冷启动，不用 sleep
  curl --max-time 15 --retry 3 --retry-delay 5 --retry-all-errors -sf "$URL/health" | jq -e '.status == "ok"'
else
  # Non-web app（cron/job/Cls）：确认 app 已注册，检查启动日志
  APP_ID=$(printf "%s" "$OUT" | grep -oE 'ap-[A-Za-z0-9]+' | tail -1 || true)
  [[ -n "${APP_ID:-}" ]] && timeout 30 modal app logs "$APP_ID" 2>&1 | head -100
fi
```

### 诊断

验证失败时，按成本递增排查，不跳级。CLI 输出字段可能随版本变化；若 jq 失败，先 `modal <cmd> --help` 或 `modal <cmd> --json | head` 查看实际结构。

#### 环境：部署到了错误的 env/profile 是最常见的原因

```bash
modal app list --json | jq '.[] | select(.Description | contains("<app>"))'
```

#### 日志：启动失败、依赖缺失、端口冲突都在这里

```bash
# 阻塞命令，放 tmux 或用 timeout
timeout 30 modal app logs <app> 2>&1 | head -100
```

#### 容器：进入运行中的容器检查

```bash
modal container exec <id> -- nvidia-smi
modal container exec <id> -- python -c "import torch; print(torch.cuda.is_available())"
```

#### Shell：在同一 Image 环境中复现问题

```bash
modal shell <file>::<func>
```

#### Debug 日志：最后手段

```bash
MODAL_LOGLEVEL=DEBUG modal run <f>
```

## 阻塞命令

Agent 主流程运行阻塞命令后无法继续工具调用。这是 agent 场景最常见的死因。

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

## 陷阱

以下是不读代码无法发现的问题。每一条都来自真实事故。

### 依赖图不匹配

Modal 容器重新 import 模块重建依赖图。App 声明（哪些 function/cls 被注册、它们的 image/secrets/volumes 等参数）在本地与远端 import 时**必须一致**。`modal.is_local()` 只能用于避免本地副作用（读文件、git），不能让 App 声明两端不同。

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

# ✅ 两端都是 2 deps
if modal.is_local():
    image = build_workspace_image("core")
else:
    image = modal.Image.debian_slim()

@app.function(image=image, secrets=[modal.Secret.from_name("my-secret")])
def f(): ...
```

### `modal.is_local()` 守卫

模块级代码在远端容器也会执行。本地文件系统操作须守卫，`else` 分支须为所有变量提供占位值：

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

### `serialized=True`

Pickle 序列化函数，容器不重新 import。适用于 `modal run` 的工具脚本（如 `clone_secret.py`）。与 `@modal.asgi_app()` / `@modal.wsgi_app()` 组合使用时，序列化/反序列化环节可能失败。Web 服务通过保持依赖图一致解决，不用 `serialized=True`。

### Secret 覆盖 `.env()`

Secret env vars 优先级高于 image `.env()`。如果 Secret 里有 `ENV=dev`，即使部署到 prod 环境，容器仍然看到 `ENV=dev`。

规则：Secret 里**只放密钥**（token、key、password）。配置放 image `.env()` 或运行时从 `MODAL_ENVIRONMENT`（Modal 自动注入）推导。

### 模块级 import

重依赖（`torch`、`transformers`）不放模块顶部。模块级代码在所有环境都会执行，如果某个 import 只存在于特定 Image，远端会 `ImportError`。

- **Function**：import 放函数体内
- **Cls**：import + 模型加载放 `@modal.enter()`（每个容器只执行一次），不要放 `@modal.method()` 里（否则每次请求都重复）

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

项目约定默认环境 `dev`（通过 `modal config set-environment dev` 设置）。部署到 `prod` 显式 `--env prod`。不用 Shebang 硬编码环境。

### Workspace Image

`build_workspace_image(*package_names)` 构建包含本地 workspace package 的 Image。详见 `.agents/skills/modal/tools/workspace_image.py` docstring。

需要额外依赖时，用 `_extract_third_party_deps` + 手动 `uv_pip_install`：

```python
if modal.is_local():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[N] / ".agents/skills/modal/tools"))
    from workspace_image import _extract_third_party_deps, _find_repo_root

    _EXTRA_DEPS = ["fastapi[standard]>=0.115.0"]
    _third_party = _extract_third_party_deps(_find_repo_root() / "pyproject.toml", "core")
    image = (
        modal.Image.debian_slim(python_version="3.13")
        .uv_pip_install(*_third_party, *_EXTRA_DEPS)
        .add_local_python_source("core")  # 必须是 image 链最后一步
    )
else:
    image = modal.Image.debian_slim()
```

### Secret 管理

- Web 服务用 `from_name`，工具脚本可用 `from_local_environ` + `serialized=True`
- 导出/克隆：`.agents/skills/modal/tools/clone_secret.py`（CLI 无 export 命令，该脚本用 diff 方式提取）

### 计费

- `min_containers` 未设置（默认 `None`，等效 scale-to-zero）-> 按请求计费
- `min_containers=1` -> 持续计费，叠加 GPU 尤其危险
- 仅代理远程 API -> `min_containers=0` + 无 GPU

### 代码检查

部署前确认：App 有明确名称（`modal.App("kebab-name")`）、Web endpoint 有 `/health`、GPU 函数有 `gpu=` 声明且启动时自检 `torch.cuda.is_available()`。

## E2E 测试

测试 Modal web 服务用 `modal serve` + curl，不写 pytest。

```bash
# 1. tmux 后台启动
SOCKET="${TMPDIR:-/tmp}/agent-tmux-sockets/agent.sock"
SESSION=modal-serve
tmux -S "$SOCKET" new -d -s "$SESSION" -n serve
PANE=$(tmux -S "$SOCKET" list-panes -t "$SESSION" -F '#{window_index}.#{pane_index}' | head -1)
tmux -S "$SOCKET" send-keys -t "$SESSION:$PANE" -- 'modal serve <file>' Enter

# 2. 等待就绪
.agents/skills/tmux/scripts/wait-for-text.sh -S "$SOCKET" -t "$SESSION:$PANE" -p 'modal.run' -T 120

# 3. 提取 URL 和 App ID
URL=$(tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION:$PANE" -S -50 \
  | grep -oE 'https://[^ ]+\.modal\.run' | head -1)
APP_ID=$(tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION:$PANE" -S -30 \
  | grep -oE 'ap-[A-Za-z0-9]+' | tail -1)

# 4. 流式看 logs
tmux -S "$SOCKET" new-window -t "$SESSION" -n logs
LOGS_PANE=$(tmux -S "$SOCKET" list-panes -t "$SESSION:logs" -F '#{window_index}.#{pane_index}' | head -1)
tmux -S "$SOCKET" send-keys -t "$SESSION:$LOGS_PANE" -- "modal app logs $APP_ID 2>&1" Enter

# 5. 验证
curl --max-time 15 -sf "$URL/health" | jq -e '.status == "ok"'

# 6. 诊断
tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION:$LOGS_PANE" -S -30

# 7. 清理
tmux -S "$SOCKET" kill-session -t "$SESSION"
```

## 并发、延迟与隧道

以下主题本文档不展开，给出入口和关键注意点。详细用法查官方文档：`curl -sf https://modal.com/docs/guide/<topic>.md`

### spawn_map（并发执行）

批量任务用 `f.map(inputs)` 或 `f.starmap(inputs)` 并发执行。注意 `max_containers` 和 `@modal.concurrent(max_inputs=N)` 控制并发上限。失败重试需自行实现。参考：`curl -sf https://modal.com/docs/guide/scale.md`

### latency（冷启动与低延迟）

冷启动是 Modal 最常见的延迟来源。缓解手段：

- `min_containers=1`：保持至少一个热容器（**持续计费，叠加 GPU 尤其危险**）
- `@modal.concurrent(max_inputs=N)`：单容器处理多请求
- Image 层缓存：把变化少的依赖放在 Image 链前面
- 验证时用 `curl --retry`，不用 `sleep`

参考：`curl -sf https://modal.com/docs/guide/cold-start.md`

### tunnel（本地调试网络）

`modal serve` 自动创建隧道暴露 web endpoint。如需从容器内访问外部服务或 VPN 内网，不在 Modal 原生能力内，需通过环境变量传入外部 API 地址。`modal serve` 是阻塞命令，必须放 tmux。

## 模板与参考

- HTTP webhook / API -> `.agents/skills/modal/templates/web_endpoint.py`
- GPU 推理服务 -> `.agents/skills/modal/templates/gpu_service.py`
- 定时任务 -> `.agents/skills/modal/templates/cron_job.py`
- 生产级示例（observability、workspace image、dedup）-> `apps/modal/logfire_feishu_relay/fastapi_app.py`
