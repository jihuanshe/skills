---
name: modal
description: 'Deploy, test, and debug serverless apps with Modal. Triggers: modal, modal deploy, modal serve, modal app, modal run, serverless, spawn_map, latency, tunnel, e2e test modal.'
metadata:
  version: '30'
---

# Modal

Modal 把 Python 函数变成云端容器。写一个函数，声明它需要什么（CPU、GPU、依赖、密钥），Modal 负责打包、调度、缩扩容。

五个原语：

- **App**：部署单元，包含一组 Function/Cls。一个 `.py` 文件通常对应一个 App。
- **Function**：执行单元。`@app.function()` 装饰一个普通函数，声明硬件和依赖。
- **Cls**：有状态的执行单元。`@app.cls()` 装饰一个类，`@modal.enter()` 加载模型，`@modal.method()` 处理请求。
- **Image**：容器镜像。链式构建：`modal.Image.debian_slim().uv_pip_install("torch")`。
- **Secret**：密钥注入。`modal.Secret.from_name("my-secret")` 将键值对注入环境变量。

**模块级代码在远端容器也会执行。** 容器启动时重新 import 模块以重建依赖图，本地文件系统操作须用 `modal.is_local()` 守卫。容器内也可以用环境变量 `MODAL_IS_REMOTE=1` 判定远端（调试时比 `modal.is_local()` 更直观）。

## 查阅

项目约定和不可自行发现的陷阱。Modal API 用法先查官方源：

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

每次操作四步：Preflight → 行动 → 验证 → 诊断。

### Preflight

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

### 行动

三条命令，三种生命周期：

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

### 验证

区分 web 与 non-web：

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

### 诊断

按成本递增排查。CLI 输出字段随版本变化，jq 失败时先查 `modal <cmd> --help` 或 `--json | head`。

#### 环境：部署到了错误的 env/profile 是最常见的原因

```bash
modal app list --json | jq '.[] | select(.Description | contains("<app>"))'
```

#### 日志：启动失败、依赖缺失、端口冲突都在这里

```bash
# 阻塞命令，放 tmux 或用后台进程限时
modal app logs <app> 2>&1 | head -100 &
LOGS_PID=$!; ( sleep 30; kill "$LOGS_PID" 2>/dev/null ) &
wait "$LOGS_PID" 2>/dev/null || true
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

阻塞命令会挂起 Agent 主流程。

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

### `modal.is_local()` 守卫

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

### `serialized=True`

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

`build_workspace_image(*package_names)` 构建含本地 package 的 Image（详见 `tools/workspace_image.py`）。额外依赖用 `_extract_third_party_deps`：

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

- 创建：`modal secret create <name> KEY1=val1 KEY2=val2 --env dev`
- Web 服务用 `from_name`，工具脚本可用 `from_local_environ` + `serialized=True`
- 导出/克隆：`.agents/skills/modal/tools/clone_secret.py`（CLI 无 export 命令，该脚本用 diff 方式提取）

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

测试 Modal web 服务用 `modal serve` + curl，不写 pytest。完整流程见 [references/e2e-testing.md](references/e2e-testing.md)。

## 并发、延迟与隧道

spawn_map、冷启动优化、tunnel 用法见 [references/advanced-topics.md](references/advanced-topics.md)。

## 模板与参考

- HTTP webhook / API -> `.agents/skills/modal/templates/web_endpoint.py`
- GPU 推理服务 -> `.agents/skills/modal/templates/gpu_service.py`
- 定时任务 -> `.agents/skills/modal/templates/cron_job.py`
- 生产级示例（observability、workspace image、dedup）-> 参考 Modal 官方 examples
