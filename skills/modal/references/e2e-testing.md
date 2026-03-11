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
