---
name: tmux
description: 'Control tmux sessions for interactive CLIs. Triggers: tmux, interactive shell, REPL.'
metadata:
  version: '2'
---

# tmux Skill

通过私有 socket + 干净配置使用 tmux 完成交互式工作。私有 socket 隔离 server 生命周期，`-f /dev/null` 隔离用户 tmux 配置。适用于 Linux 和 macOS。

## 快速开始（隔离 socket）

```bash
SOCKET_DIR=${TMPDIR:-/tmp}/agent-tmux-sockets  # Agent socket 统一目录
mkdir -p "$SOCKET_DIR"
SOCKET="$SOCKET_DIR/agent.sock"                # 与用户个人 tmux 隔离
SESSION=agent-python                           # slug 风格命名，不要带空格
tmux -f /dev/null -S "$SOCKET" new -d -s "$SESSION" -n shell
PANE=$(tmux -S "$SOCKET" list-panes -t "$SESSION" -F '#{window_index}.#{pane_index}' | head -1)
tmux -S "$SOCKET" send-keys -t "$SESSION:$PANE" -- 'PYTHON_BASIC_REPL=1 python3 -q' Enter
tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION:$PANE" -S -200  # 查看输出
tmux -S "$SOCKET" kill-session -t "$SESSION"                      # 清理
```

启动会话后告知用户监控命令：

```text
监控此会话：
  tmux -S "$SOCKET" attach -t "$SESSION"

或一次性捕获输出：
  tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION:$PANE" -S -200
```

会话启动后和工具循环结束时各打印一次。

## Socket 约定

- tmux socket 放在 `AGENT_TMUX_SOCKET_DIR`（默认 `${TMPDIR:-/tmp}/agent-tmux-sockets`）下，使用 `tmux -S "$SOCKET"`。先创建目录：`mkdir -p "$AGENT_TMUX_SOCKET_DIR"`。
- 默认 socket 路径：`SOCKET="$AGENT_TMUX_SOCKET_DIR/agent.sock"`。

## 窗格定位与命名

- 目标格式：`{session}:{window}.{pane}`。名称保持简短（如 `agent-py`、`agent-gdb`）。
- 不要硬编码 `:0.0`——`base-index` 可能非零。创建会话后查询实际窗格：

  ```bash
  PANE=$(tmux -S "$SOCKET" list-panes -t "$SESSION" -F '#{window_index}.#{pane_index}' | head -1)
  # 然后使用 "$SESSION:$PANE" 作为目标
  ```

- 始终使用 `-S "$SOCKET"` 以保持在私有 socket 上。如需用户配置，去掉 `-f /dev/null`；否则 `-f /dev/null` 可获得干净配置。
- 检查状态：`tmux -S "$SOCKET" list-sessions`、`tmux -S "$SOCKET" list-panes -a`。

## 查找会话

- 列出当前 socket 上的会话及元数据：`./scripts/find-sessions.sh -S "$SOCKET"`；加 `-q 部分名称` 可过滤。
- 扫描共享目录下的所有 socket：`./scripts/find-sessions.sh --all`（使用 `AGENT_TMUX_SOCKET_DIR` 或 `${TMPDIR:-/tmp}/agent-tmux-sockets`）。

## 安全发送输入

- 优先使用字面发送以避免 shell 拆分：`tmux -S "$SOCKET" send-keys -t target -l -- "$cmd"`
  - 注意：`-l` 关闭 key-name lookup，`Enter` 等键名会被当文字发送。需额外发送回车：

    ```bash
    # 推荐：追加换行符，一次 send-keys 完成
    tmux -S "$SOCKET" send-keys -t "$SESSION:$PANE" -l -- "$cmd"$'\n'
    # 或分两次：先字面内容，再发 Enter 键
    tmux -S "$SOCKET" send-keys -t "$SESSION:$PANE" -l -- "$cmd"
    tmux -S "$SOCKET" send-keys -t "$SESSION:$PANE" Enter
    ```

- 组合内联命令时，使用单引号或 ANSI C 引号避免变量展开：`tmux ... send-keys -t target -- $'python3 -m http.server 8000'`。
- 发送控制键：`tmux ... send-keys -t target C-c`、`C-d`、`C-z`、`Escape` 等。

## 查看输出

- 捕获最近历史（合并行以避免换行伪影）：`tmux -S "$SOCKET" capture-pane -p -J -t target -S -200`。
- 持续监控时，使用下方辅助脚本轮询，而非 `tmux wait-for`（后者不监听窗格输出）。
- 也可临时 attach 观察：`tmux -S "$SOCKET" attach -t "$SESSION"`；按 `Ctrl+b d` 分离。
- 给用户的说明中包含可复制粘贴的监控命令。

## 启动进程

进程相关的特殊规则：

- 调试默认用 lldb。
- Python 交互式 shell 须设置 `PYTHON_BASIC_REPL=1`——非 basic console 会干扰 send-keys。

## 同步 / 等待提示符

- 定时轮询避免竞态。等待 Python 提示符后再发送代码：

  ```bash
  ./scripts/wait-for-text.sh -S "$SOCKET" -t "$SESSION:$PANE" -p '^>>>' -T 15 -l 4000
  ```

- 长时间运行的命令，轮询完成标志文本（`"Type quit to exit"`、`"Program exited"` 等）后再继续。

## 交互式工具配方

- **Python REPL**：`tmux ... send-keys -- 'python3 -q' Enter`；等待 `^>>>`；用 `-l` 发送代码；用 `C-c` 中断。始终配合 `PYTHON_BASIC_REPL`。
- **lldb**：`tmux ... send-keys -- 'lldb ./a.out' Enter`；用 `C-c` 中断；执行 `bt`、`frame variable` 等；通过 `quit` 退出。macOS 默认调试器。
- **gdb**（Linux）：`tmux ... send-keys -- 'gdb --quiet ./a.out' Enter`；禁用分页 `tmux ... send-keys -- 'set pagination off' Enter`；用 `C-c` 中断；通过 `quit` 退出并确认 `y`。
- **其他 TTY 应用**（ipdb、psql、mysql、node、bash）：相同模式——启动程序、轮询提示符、然后发送字面文本和 Enter。

## 清理

- 结束后关闭会话：`tmux -S "$SOCKET" kill-session -t "$SESSION"`。
- 关闭 socket 上的所有会话：`tmux -S "$SOCKET" list-sessions -F '#{session_name}' | while read -r s; do tmux -S "$SOCKET" kill-session -t "$s"; done`。
- 移除私有 socket 上的一切：`tmux -S "$SOCKET" kill-server && rm -f "$SOCKET"`。

## 辅助脚本：wait-for-text.sh

`./scripts/wait-for-text.sh` 在窗格中轮询正则（或固定字符串），带超时。适用于 Linux/macOS 的 bash + tmux + grep。

```bash
./scripts/wait-for-text.sh -S "$SOCKET" -t "$SESSION:$PANE" -p 'pattern' [-F] [-T 20] [-i 0.5] [-l 2000]
```

- `-S`/`--socket` tmux socket 路径（**使用私有 socket 时必填**——遗漏此项是"超时但文本其实已出现"的首要原因）
- `-t`/`--target` 窗格目标（必填）
- `-p`/`--pattern` 匹配的正则（必填）；加 `-F` 使用固定字符串
- `-T` 超时秒数（整数，默认 15）
- `-i` 轮询间隔秒数（默认 0.5）
- `-l` 从窗格搜索的历史行数（整数，默认 1000）
- 首次匹配返回 0，超时返回 1。失败时将最后捕获的文本输出到 stderr 以辅助调试。
