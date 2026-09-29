# Agent 开发岗位面试最小记忆模板（s11-s15）

## 总纲：从异步能力到可恢复运行时

这五章逐步解决生产问题：s11 管后台任务，s12 管可靠定时投递，s13 管多 Agent 协作与隔离，s14 管外部工具动态接入，s15 把它们组装成统一宿主运行时。

## s11 Background Tasks

**一句话**：慢 Bash 立即返回任务占位符，后台线程执行并写入状态，主 Agent 每轮收集结果后以 `task_notification` 注入对话。

**最小模板**：

```python
if should_run_background(block.name, block.input):
    task_id = BACKGROUND.start(block)       # 立即返回 placeholder
else:
    return call_tool(block)

while True:
    inject_background_results(messages)      # collect + append notification
    response = llm(messages, tools)
```

**面试关键词**：线程生命周期、共享状态加锁、daemon thread、状态机（running/completed/failed）、结果回灌、主循环轮询、超时和进程组清理。

**追问回答**：为什么不能直接把线程结果写进模型请求？模型请求可能正在进行，统一由主循环注入能保持消息顺序。为什么要保存 `tool_use_id` 和状态？便于把异步结果与原始调用关联，并向模型区分成功和失败。

## s12 Cron Scheduler

**一句话**：cron 任务独立持久化，调度线程把到期任务放入队列，只有模型成功接收后 ack，失败则 restore，避免定时提示丢失。

**最小模板**：

```python
schedule_job(cron, prompt, durable=True)
poll_due_jobs(now)                 # match -> persist pending -> enqueue
jobs = consume_cron_queue()
try:
    inject_scheduled_prompts(jobs)
    call_llm()
    acknowledge_cron_jobs(jobs)    # recurring reset / one-shot delete
except Exception:
    restore_cron_jobs(jobs)         # 下轮重试
```

**面试关键词**：cron 五字段解析、范围/步长校验、durable snapshot、原子写入、pending_delivery、ack/restore、一次性与 recurring、重复触发去重。

**追问回答**：为什么先落盘再入队？进程在入队后崩溃时，持久化的 pending 状态能在启动时恢复。为什么 ack 不能在 consume 时完成？consume 只代表从队列取出，模型调用可能失败，必须把“已收到”作为确认边界。

## s13 Agent Teams

**一句话**：Lead 创建带依赖和 owner 的 Task，Teammate 在线程中用独立消息循环工作，MessageBus 传递事件，plan/shutdown 用带版本的协议请求确认。

**最小模板**：

```python
task = create_task(subject, blockedBy=deps)
claim_task(task.id, owner=name)       # pending -> in_progress + cwd lease
spawn_teammate_thread(name, role, prompt, task.id)

while teammate_alive:
    inbox = BUS.read_inbox(name)
    handle_protocol(inbox)             # plan approval / shutdown
    response = llm(teammate_messages, TEAMMATE_TOOLS)
    execute_tools_after_plan_gate(response)

complete_task(task.id, owner=name)    # owner + gate + assignment 都要匹配
```

**必须记住**：`task_store_lock` 同时保护进程内状态和 JSON 文件；`save_task` 临时文件替换保证原子性；`assignment_cwd` 保证一个 owner 一次只有一个稳定工作目录；worktree 是隔离目录，不是安全沙箱。

**面试关键词**：任务 DAG、claim 幂等、owner lease、Git worktree、文件 mailbox、Condition 唤醒、状态机、request_id、assignment version、fail closed。

**追问回答**：为什么审批要带版本？因为队友完成旧任务后可能领取新任务，旧 plan response 若只按 teammate 名称匹配，会越权打开新工作区。为什么 mailbox 读完删除？它承担事件队列而非历史库，历史应写入任务/协议状态。

## s14 MCP Plugin

**一句话**：连接 MCP server 后发现工具 schema，给名称加 `mcp__server__tool` 前缀，动态合并工具、handler 和 host policy，再进入普通 Agent loop。

**最小模板**：

```python
client = connect_mcp("docs")
tools, handlers = assemble_tool_pool()
response = llm(messages, tools)
for block in response.tool_use:
    execute_tool(block, handlers)      # hook -> policy -> handler -> result
```

**关键边界**：server 描述只能提供能力元数据，不能授予权限；名称规范化后要检查长度和冲突；未知工具、handler 异常都转成模型可理解的错误文本。

**面试关键词**：tools/list、tools/call、动态工具池、命名空间、schema 校验、handler 闭包、host-side authorization、工具发现与权限分离。

**追问回答**：为什么每轮重新组装工具池？连接动作发生在一次工具调用中，下一次模型请求才应该看到新工具。为什么不能信 MCP 的 policy？外部 server 不应决定宿主安全边界，授权必须来自 host 配置并经过统一权限 hook。

## s15 Integrated Harness

**一句话**：每次模型调用前统一注入事件、更新记忆和上下文预算；调用经权限与重试；工具结果、cron 和后台结果都回到同一个消息循环。

**最小模板**：

```python
while True:
    inject_cron_and_background(messages)
    prepare_context(messages, active_request)
    context = update_context(context, messages)
    response = call_llm(messages, context, tools, recovery_state, limit)
    results = execute_tool_blocks(response)
    messages.append(tool_results(results))
```

**恢复链**：429/529 用指数退避和抖动重试；持续过载切 fallback model；prompt-too-long 触发 reactive compact；cron 投递只有 ack 后才清除，失败则 restore；后台线程完成后以 notification 注入。

**权限链**：`PermissionLayer.check` 按 bash、路径、MCP 分流；路径必须在 workdir；异步线程没有 stdin 审批通道时直接拒绝高风险调用。

**面试关键词**：编排循环、上下文预算、transcript、工具结果持久化、幂等 ack、指数退避、fallback、权限边界、可观测性、优雅降级。

**追问回答**：压缩为何不是简单截断？要保留当前请求、tool_use/result 配对和可恢复 transcript；摘要是参考状态而非授权来源。为什么配置独立成 `config.py`？启动时一次性读取环境和限制，避免运行时各模块读取出不一致的模型、路径和预算。

## 30 秒串讲

“s11 用后台线程解耦慢工具，s12 用 durable queue 和 ack/restore 保证定时任务不丢，s13 扩展到带 owner、依赖和协议的协作运行时，s14 把 MCP 能力纳入动态工具池但授权仍由宿主控制，s15 再统一上下文、权限和错误恢复。主线是状态可恢复、边界可验证、失败可重试、能力与授权分离。”
