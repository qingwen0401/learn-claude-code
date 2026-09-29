# Agent 开发岗位面试最小记忆模板（s16-s17）

## 总纲：从运行时编排到目标驱动

s16 把多个 Agent 调用组织成可恢复、有预算、有日志的 workflow；s17 在 AgentSession 外增加显式目标、评估器和停止决策，让循环知道“何时算完成”。

## s16 Workflow Runtime

**一句话**：用 `run_id + journal + lock` 管住一次 workflow，用 `ExecutionState` 统一 agent、parallel、pipeline、预算和嵌套 workflow，并支持断点恢复。

**最小模板**：

```python
run_id = reserve_run_id(meta)
with workflow_run_lock(run_id):
    journal = WorkflowJournal(run_id, resume=True)
    state = ExecutionState(task, journal, runner, budget, args)
    result = await state.workflow(name, args)
    journal.close()

async def workflow(name, args):
    value = await agent(prompt, schema=Schema)
    checked = await parallel([lambda: agent(p) for p in items])
    return await pipeline(checked, stage_a, stage_b)
```

**必须记住**：`WorkflowJournal` 让已完成步骤可缓存/恢复；`SimpleJsonSchema` 校验结构化输出；`Budget` 和 `ExecutionLimits` 限制 token、嵌套深度与 Agent 数；`workflow_run_lock` 防止同一 run 并发写状态。

**面试关键词**：run identity、幂等恢复、journal/cache、结构化输出、预算传播、并行扇出、pipeline、嵌套 workflow、执行上限、事件日志。

**追问回答**：为什么恢复不能只重放全部步骤？昂贵或有副作用的步骤应从 journal 读取缓存，未完成步骤才重跑。为什么并行仍需共享预算？否则每个分支都以为拥有完整额度，整体成本和资源上限会失控。

## s17 Goal Loop

**一句话**：用户设置目标后，每轮 AgentSession 提交查询，`PromptGoalEvaluator` 评估进展，`GoalController` 记录目标历史并决定继续、暂停、完成或清除。

**最小模板**：

```python
controller.set_goal("测试通过并生成报告")
while True:
    result = await session.submit(user_text)
    decision = await controller.evaluate_after_turn(
        messages=session.messages,
        active_request=user_text,
    )
    if decision.stop:
        break
```

**必须记住**：目标状态与对话历史分开保存；评估结果要结构化（progress/decision/reason）；`restore` 可恢复目标状态；权限、日志、大输出处理仍走 session hooks，不因目标循环而绕过工具边界。

**面试关键词**：goal state、目标评估、停止条件、progress、budget guard、历史记录、恢复、hook 复用、反复循环防护、人机可解释性。

**追问回答**：为什么不能只看模型最后一句话判断完成？最后一句可能是自然语言承诺，不能稳定表达是否满足目标；应让 evaluator 输出结构化判断，并结合 token/turn 上限。如何防止目标循环失控？设置最大轮数/预算、记录每次决策，遇到无进展或错误时转为 stop/pause 并向用户说明原因。

## 30 秒串讲

“s16 把 Agent 调用提升为可恢复 workflow：run 有身份、步骤有 journal、执行有预算和锁；s17 再增加目标控制层，用结构化 evaluator 判断进展和停止。两章共同强调幂等恢复、资源上限、状态可解释，以及复用既有权限和工具边界。”
