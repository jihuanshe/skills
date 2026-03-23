---
name: github-runners
description: "Manage GitHub Actions self-hosted runners: deploy, remove, check status, and troubleshoot. Triggers: runner, self-hosted, github actions runner, CI runner, setup runner, remove runner."
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

```
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
|------|------|------|
| runner offline | 服务未启动或崩溃 | `systemctl restart actions.runner.<ORG>.<NAME>.service` |
| token 过期 | registration token 有效期 1 小时 | 重新获取 token |
| 注册失败 | 用户无权限或目录已存在 | 先 `remove-runners.sh` 清理再重试 |
| 下载后静默退出 | 未用 `sudo` 执行，无权写入 runner 用户目录 | 加 `sudo` 重新执行 |
| runner group 不存在 | `-g` 指定的 group 未在 GitHub 预先创建 | 先到 Org Settings → Actions → Runner groups 创建 |
| 磁盘满 | `_work/` 积累过多构建产物 | 清理 `_work/` 或配置 workflow 清理步骤 |

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
