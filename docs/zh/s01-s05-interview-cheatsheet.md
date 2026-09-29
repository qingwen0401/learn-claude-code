# Agent 开发面试最小记忆模板（s01-s05）

## 总纲：模型决策，Harness 执行

面试先说清边界：LLM 只负责选择下一步（回答或调用工具）；Harness 负责校验、执行工具，把结果追加回消息历史。五章是在同一个循环上逐层增加能力：

`用户输入 -> LLM -> tool_use -> 策略/钩子 -> 工具执行 -> tool_result -> LLM`。

## s01 Agent Loop

**一句话**：用 `while` 把工具结果持续喂回模型，直到 `stop_reason != "tool_use"`。

**最小伪代码**：

```python
while True:
    response = llm(messages, tools)
    messages += assistant(response.content)
    if response.stop_reason != "tool_use":
        break
    results = [execute(block) for block in response.content if block.type == "tool_use"]
    messages += user(tool_results(results))
```

**面试关键词**：消息历史、tool_use/tool_result、停止条件、模型决策与执行器解耦。

**追问回答**：为什么不能只调用一次？因为工具输出是模型下一轮推理的观测；不回填就无法多步闭环。风险是死循环、超时、输出过大，应增加轮数/时间/token 上限。

## s02 Tool Use

**一句话**：循环不变，新增工具 schema、实现函数和 `TOOL_HANDLERS` 分发表。

**最小伪代码**：

```python
TOOLS = [schema("read_file"), schema("write_file")]
TOOL_HANDLERS = {"read_file": run_read, "write_file": run_write}
handler = TOOL_HANDLERS.get(block.name)
output = handler(**block.input) if handler else "Unknown tool"
```

**面试关键词**：声明与实现分离、按名称分发、参数 schema、统一错误结果、路径沙箱。

**追问回答**：`safe_path` 用 `resolve()` 后检查 `is_relative_to(WORKDIR)`，防止 `../` 越界；工具扩展只需增加 schema、handler、映射。

## s03 Permission

**一句话**：在执行工具前加入三道门：硬拒绝、规则匹配、用户审批。

**最小伪代码**：

```python
if deny_list(command):
    deny()
reason = match_rules(tool, args)
if reason and ask_user(tool, args, reason) == "deny":
    deny()
execute()
```

**面试关键词**：默认拒绝、策略与执行分离、危险操作审批、拒绝也要返回 tool_result。

**追问回答**：硬拒绝不能被用户绕过；上下文风险可询问；审批应记录审计信息。生产环境还要考虑命令解析、竞态、权限身份和非交互模式。

## s04 Hooks

**一句话**：把横切逻辑挂到生命周期事件，让主循环保持稳定。

**事件模板**：`UserPromptSubmit -> PreToolUse -> execute -> PostToolUse -> Stop`。

**最小伪代码**：

```python
def register_hook(event, callback): HOOKS[event].append(callback)
def trigger_hooks(event, *args):
    for cb in HOOKS[event]:
        result = cb(*args)
        if result is not None: return result
```

**面试关键词**：可插拔、阻断信号、日志/权限/审计/输出检查、回调顺序。

**追问回答**：Pre hook 可阻止执行，Post hook 只能观察或处理结果，Stop hook 可阻止结束并要求继续；生产实现应隔离异常、定义超时和事件契约。

## s05 TodoWrite

**一句话**：给模型一个结构化计划状态，减少长任务中的目标漂移。

**状态机**：`pending -> in_progress -> completed`；同一时刻最多一个 `in_progress`。

**最小伪代码**：

```python
todos = parse_json_or_literal(input)
validate(list <= 20, content, status, one_in_progress)
TODO.items = todos
return render(todos)
```

**调用逻辑**：`todo_write` 只管理计划，不执行工作；每轮记录是否调用它，连续三轮未更新就注入 `<reminder>`。

**面试关键词**：结构化状态、输入校验、原子替换、模型可见反馈、提醒机制。

**追问回答**：TODO 不是工作流引擎，真正执行仍由其他工具完成；生产环境应持久化、支持并发/幂等、限制提醒噪声，并校验模型声称的完成状态。

## 30 秒串讲

“我会先实现 s01 的消息闭环；s02 把工具声明和 handler 用 dispatch map 解耦，并做路径沙箱；s03 在执行前加 deny/rule/approval 三层权限；s04 把权限、日志、审计抽成生命周期 hooks；s05 用受约束的 TODO 状态帮助模型管理长任务，并在多轮不更新时提醒。核心原则是模型负责决策，Harness 负责安全执行和状态反馈。”

