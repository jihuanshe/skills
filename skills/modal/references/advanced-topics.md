## 并发、延迟与隧道

以下主题本文档不展开，给出入口和关键注意点。详细用法查官方文档：`curl -sf https://modal.com/docs/guide/<topic>.md`

### 并发执行（map / starmap / spawn_map）

批量任务用 `f.map(inputs)` 或 `f.starmap(inputs)` 并发执行。注意 `max_containers` 和 `@modal.concurrent(max_inputs=N)` 控制并发上限。函数级重试可用 `retries=` 参数（`int` 或 `modal.Retries`）配置，默认不重试。参考：`curl -sf https://modal.com/docs/guide/scale.md`

### latency（冷启动与低延迟）

冷启动是 Modal 最常见的延迟来源。缓解手段：

- `min_containers=1`：保持至少一个热容器（**持续计费，叠加 GPU 尤其危险**）
- `@modal.concurrent(max_inputs=N)`：单容器处理多请求
- Image 层缓存：把变化少的依赖放在 Image 链前面
- 验证时用 `curl --retry`，不用 `sleep`

参考：`curl -sf https://modal.com/docs/guide/cold-start.md`

### tunnel（本地调试网络）

`modal serve` 自动创建隧道暴露 web endpoint。如需从容器内访问外部服务或 VPN 内网，不在 Modal 原生能力内，需通过环境变量传入外部 API 地址。`modal serve` 是阻塞命令，必须放 tmux。
