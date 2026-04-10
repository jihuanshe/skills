---
name: github-runners
description: "Manage GitHub Actions self-hosted runners: deploy, remove, check status, and troubleshoot. Triggers: runner, self-hosted, GitHub actions runner, CI runner, setup runner, remove runner."
metadata:
  version: '1'
---

# GitHub Actions Self-Hosted Runners

在同一台机器上批量部署、删除、诊断 GitHub Actions self-hosted runner。

## 脚本位置

- **部署**: `scripts/setup-runners.sh`
- **删除**: `scripts/remove-runners.sh`

执行时使用 skill 目录下的脚本：`bash scripts/<script>.sh`

## 快速参考

### 部署 Runner

> **必须用 `sudo` 执行**，脚本内部需要写入 runner 用户 home 目录、安装 systemd 服务等，缺少 root 权限会静默失败。

```bash
sudo bash scripts/setup-runners.sh \
  -t <REG_TOKEN> \
  -o <ORG> \
  -n <COUNT>        # 数量，默认 4，上限 50
  -l <LABEL>        # 自定义 label，默认主机名
  -g <GROUP>        # runner group，默认 "Default"
  -p <PREFIX>       # 名称前缀，默认同 label
  -u <USER>         # Linux 用户，默认 "actions"
```

### 删除 Runner

```bash
bash scripts/remove-runners.sh \
  -t <REMOVE_TOKEN> \
  -o <ORG> \
  -n <COUNT>        # 数量，默认 10
  -u <USER>         # Linux 用户，默认 "actions"
```

### Token 获取

```bash
# Registration token（部署用）
gh api -X POST /orgs/<ORG>/actions/runners/registration-token --jq .token

# Remove token（删除用）
gh api -X POST /orgs/<ORG>/actions/runners/remove-token --jq .token
```

Token 有效期 1 小时，过期需重新获取。需要 org admin 权限。

## 架构

每个 runner 实例是独立目录，共享同一个 Linux 用户：

```text
~<USER>/
├── actions-runner-linux-x64-<VER>.tar.gz   # 共享安装包
├── actions-runner-1/                        # runner 实例 1
│   ├── .runner                              # 注册标记
│   ├── _work/                               # 工作目录
│   └── svc.sh                               # systemd 管理
├── actions-runner-2/
└── ...
```

每个实例注册为独立 systemd 服务：`actions.runner.<ORG>.<PREFIX>-<N>.service`

## Workflow 使用

```yaml
runs-on: [self-hosted, <LABEL>]
```

## 资源限制：共享池方案

多个 runner 共享一台机器时，**不要给每个 runner 单独设硬上限**（平均切片会浪费资源），而是用一个**父 slice** 控制总量，单体不设限。

### 创建父 slice

```ini
# /etc/systemd/system/gharunners.slice
[Unit]
Description=GitHub Actions runner shared pool

[Slice]
CPUQuota=<CORES*100>%   # 例：16 核 → 1600%
MemoryHigh=<约 MAX 的 85%> # 软阈值，提前触发内存回收
MemoryMax=<上限>          # 硬上限，例：128G
MemorySwapMax=0           # 禁止 swap 扩张
```

> `MemoryHigh` + `MemoryMax` 配合使用比单独 `MemoryMax` 更平滑——先压后兜底。

### 用 drop-in 统一覆盖全部 runner

**不要手改 GitHub 生成的主 unit 文件**，保持原状，用 drop-in 接管运行时行为。这样 runner 升级/重装不会冲突，回滚也只需删 drop-in 文件：

```ini
# /etc/systemd/system/actions.runner.<ORG>.<PREFIX>-.service.d/80-pool.conf
[Service]
Slice=gharunners.slice
KillMode=control-group
```

然后重载：

```bash
sudo systemctl daemon-reload
# 逐个重启（或批量）
for i in $(seq 1 <COUNT>); do
  sudo systemctl restart actions.runner.<ORG>.<PREFIX>-$i.service
done
```

### 验证是否真正生效

配置和运行时可能不一致，**必须同时检查**：

```bash
# 1. 配置层面
systemctl show actions.runner.<ORG>.<PREFIX>-1.service -p Slice

# 2. 运行时 cgroup（这才是真相）
systemctl show actions.runner.<ORG>.<PREFIX>-1.service -p ControlGroup

# 3. 内核层 cgroup 文件（最终确认）
cat /sys/fs/cgroup/gharunners.slice/cpu.max
cat /sys/fs/cgroup/gharunners.slice/memory.max
cat /sys/fs/cgroup/gharunners.slice/memory.high
```

如果 `Slice=` 已改但 `ControlGroup` 没变，尝试：

```bash
sudo systemctl daemon-reexec   # 让 systemd 重新整理运行时状态
sudo systemctl restart actions.runner.<ORG>.<PREFIX>-1.service
```

### 踩坑经验

#### `KillMode=process` 是大坑

GitHub runner 默认生成的 service 里有 `KillMode=process`，这会导致：

- 停服务时只杀主进程，子进程残留在旧 cgroup
- 之后改 `Slice=` 重启，运行时 cgroup 可能粘在旧位置
- 出现"配置已改、运行没变"的幻觉

**务必用 drop-in 覆盖为 `KillMode=control-group`**。

#### Runner 是 system service，不属于 `user.slice`

即使 runner 用 `User=actions` 运行，它挂在 systemd system manager 下，默认属于 `system.slice`，不是 `user-<UID>.slice`。直接限制 `user-<UID>.slice` 不会影响这些 runner。

#### Slice 名字不要带 `-`

带 `-` 的 slice 名（如 `actions-runners.slice`）会被 systemd 解读为层级结构，产生中间层目录，排查时更绕。用不含 `-` 的名字（如 `gharunners.slice`）更干净。

#### 旧 slice / cgroup 可能残留

删掉配置文件后，运行时可能仍存在旧的 systemd unit 和 `/sys/fs/cgroup/` 残余目录。检查要分两层：磁盘（配置文件）和运行时（`systemctl list-units`、cgroup 目录）。

#### `systemctl cat` 是排查利器

它能看到主 unit 文件 + 所有 drop-in 覆盖文件 + 最终合并来源，对排查"磁盘内容"和"运行时行为"不一致非常关键。

### 方案局限

共享 slice 方案解决的是**宿主机保护**（不让 runner 把机器打爆），但不解决：

- Job 之间的互相拖慢（CPU / 内存 / IO 竞争）
- 环境隔离
- 按机器容量动态接单

长期可考虑：**ephemeral runner** / **Actions Runner Controller (ARC)** / **容器化 runner**。

## 诊断流程

### 1. 查看 Runner 状态

```bash
systemctl list-units --type=service | grep actions.runner
```

### 2. 查看单个 Runner 日志

```bash
# systemd 日志
journalctl -u actions.runner.<ORG>.<NAME>.service -n 50 --no-pager

# runner 自身日志
tail -100 ~<USER>/actions-runner-<N>/_diag/Runner_*.log
```

### 3. 常见问题

| 症状 | 原因 | 解决 |
| ------ | ------ | ------ |
| runner offline | 服务未启动或崩溃 | `systemctl restart actions.runner.<ORG>.<NAME>.service` |
| token 过期 | registration token 有效期 1 小时 | 重新获取 token |
| 注册失败 | 用户无权限或目录已存在 | 先 `remove-runners.sh` 清理再重试 |
| 下载后静默退出 | 未用 `sudo` 执行，无权写入 runner 用户目录 | 加 `sudo` 重新执行 |
| runner group 不存在 | `-g` 指定的 group 未在 GitHub 预先创建 | 先到 Org Settings → Actions → Runner groups 创建 |
| 磁盘满 | `_work/` 积累过多构建产物 | 清理 `_work/` 或配置 workflow 清理步骤 |
| `Slice=` 改了但 cgroup 没变 | `KillMode=process` 导致子进程残留旧 cgroup | drop-in 覆盖 `KillMode=control-group`，必要时 `daemon-reexec` |
| runner 吃满整机资源 | 无资源上限 | 配置共享 slice 方案（见上方"资源限制"章节） |

### 4. 批量管理

```bash
# 停止全部
for i in $(seq 1 <COUNT>); do
  sudo systemctl stop actions.runner.<ORG>.<PREFIX>-$i.service
done

# 启动全部
for i in $(seq 1 <COUNT>); do
  sudo systemctl start actions.runner.<ORG>.<PREFIX>-$i.service
done

# 重启全部
for i in $(seq 1 <COUNT>); do
  sudo systemctl restart actions.runner.<ORG>.<PREFIX>-$i.service
done
```

## 前置条件

- Linux 服务器（脚本使用 systemd）
- `sudo` 权限
- 目标 Linux 用户已创建（`sudo useradd -m -s /bin/bash actions`）
- `gh` CLI 已登录（获取 token）或从网页复制 token
- 网络可访问 `github.com`

## 注意事项

- **必须用 `sudo` 执行脚本**，否则写入 runner 用户目录和安装 systemd 服务会静默失败
- 脚本需要在目标 Linux 服务器上执行，不能在 macOS 本地运行
- 脚本会交互确认配置，需要 TTY
- 已存在 `.runner` 文件的实例会被跳过，需先 remove 再重建
- runner 版本自动检测最新，回退默认 `2.332.0`
- `-g` 指定的 runner group 必须预先在 GitHub Org Settings 中创建，脚本不会自动创建
