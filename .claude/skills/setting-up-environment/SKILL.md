---
name: setting-up-environment
description: "`Linux` Initialize development environment with mise and uv. Triggers: first-time setup, CI/CD init, missing mise/uv."
---

# Setup 环境初始化

在 Linux 环境中自动安装 mise 并初始化开发环境。

## 适用平台

**Linux only**：需要 curl 和 git。

**macOS 用户**：无需此脚本，直接在仓库根目录运行：

```bash
brew install mise
mise trust --yes && mise install
mise exec python@3.13 -- uv sync --frozen
```

## 使用场景

- 首次在新 Linux 机器上配置开发环境
- CI/CD 环境初始化

## 运行

从 skill 目录执行：

```bash
bash scripts/setup.sh
```

## 脚本功能

1. 检测操作系统（仅支持 Linux）
2. 验证 git 和 curl 是否可用
3. 安装 mise 到 `/usr/local/bin/mise`
4. 信任 mise 配置
5. 运行 `mise install` 安装工具链
6. 运行 `uv sync --frozen` 同步依赖
7. 运行 `prek install --overwrite` 安装 pre-commit hooks
