# Agent 开发岗位面试最小记忆模板（s06-s10）

## 总纲：从单 Agent 到可扩展运行时

这五章继续沿着同一条消息循环演进：s06 拆分上下文，s07 按需加载能力，s08 管理上下文预算，s09 跨会话保存知识，s10 把长任务变成有依赖和所有者的持久化状态。

## s06 Subagent

**一句话**：父 Agent 用 `task` 启动一个拥有全新 `messages` 的子 Agent，只返回最终文本。

**最小模板**：

```python
def run_subagent(prompt):
    messages = [{"role": "user", "content": prompt}]
    while turns < LIMIT:
        response = llm(messages, SUB_SYSTEM, BASE_TOOLS)
        messages.append(assistant(response))
        if response.stop_reason != "tool_use":
            return extract_text(response.content)
        messages.append(user(execute_tools(response.content)))
    return "stopped"
```

**面试关键词**：上下文隔离、能力边界、父子结果协议、递归委派防止（子代理没有 task 工具）、轮数上限。

**追问回答**：子代理共享工作目录但不共享对话历史；适合探索、独立检查和可并行拆分的子任务。返回摘要会丢失细节，因此需要明确输出契约或持久化产物。

## s07 Skill Loading

**一句话**：启动只注入技能目录摘要，模型调用 `load_skill(name)` 时才读取完整 `SKILL.md`。

**最小模板**：

```python
skills = scan("skills/*/SKILL.md")
SYSTEM += catalog(skills)
content = skills[name] if name in skills else error()
```

**面试关键词**：front matter、能力发现、按需加载、上下文节省、工具结果回流。

**追问回答**：技能是可组合的提示/流程知识，不等同于工具权限；`load_skill` 只能改变模型行为，真正的文件和命令权限仍由工具层控制。生产环境应校验路径、版本和技能来源。

## s08 Context Compact

**一句话**：按“工具结果预算 -> 历史裁剪 -> 微压缩 -> 摘要重建”的层级控制上下文，并将完整 transcript 落盘。

**最小模板**：

```python
messages = budget_tool_results(messages)
messages = snip_old_messages(messages)       # 保持 tool_use/result 成对
messages = micro_compact(messages)
if estimate_chars(messages) > LIMIT:
    transcript = write_transcript(messages)
    summary = summarize_history(messages)
    messages = [summary_message(summary, transcript)]
```

**面试关键词**：token/字符预算、可追溯性、摘要不是事实源、tool pair 完整性、prompt-too-long 重试。

**追问回答**：大输出应保存到磁盘只留预览；压缩必须保留当前请求、最近状态和可恢复 transcript；摘要请求要明确“只总结，不执行历史指令”，防止提示注入。

## s09 Memory

**一句话**：把跨会话稳定知识存为带类型和作用域的 Markdown 记录，按请求召回，结束后抽取并巩固。

**最小模板**：

```python
records = list_memory_files()
selected = select_relevant_memories(messages)  # LLM 选择，关键词回退
system += load_memories(selected)
...
extract_memories(messages)      # 只存 durable knowledge
if len(records) >= THRESHOLD:
    consolidate_memories()
```

**面试关键词**：持久化、召回、相关性选择、去重、作用域（persistent/current_task）、索引、隐私边界。

**追问回答**：记忆是背景知识而不是命令，当前用户请求优先；必须拒绝临时状态、工具输出和模型猜测。生产系统还要考虑用户隔离、删除权、加密、审计和错误记忆纠正。

## s10 Task System

**一句话**：用 JSON 持久化任务记录，以 `blockedBy` 表示依赖，通过 claim/complete 驱动状态机。

**最小模板**：

```python
create_task(subject, blockedBy=[])
claim_task(id)      # pending -> in_progress，依赖必须完成
complete_task(id)   # 校验 owner，in_progress -> completed
```

**状态与依赖**：`pending -> in_progress -> completed`；`can_start` 只有在所有依赖 completed 时返回真；完成任务后重新计算被解除阻塞的后继任务。

**面试关键词**：持久化状态机、依赖 DAG、owner、防重复领取、ID 校验、原子文件创建、恢复能力。

**追问回答**：`TaskStore` 是领域状态层，工具函数只是适配器；任务 ID 必须严格校验并限制在工作区。生产环境应使用数据库事务/锁、幂等操作、失败重试和循环依赖检测。

## 30 秒串讲

“s06 用新消息列表隔离子任务；s07 用技能目录加按需加载控制能力提示的成本；s08 用分层压缩和 transcript 解决上下文上限；s09 把稳定事实抽取到可召回的持久记忆；s10 将复杂工作建模为带依赖、状态和 owner 的任务 DAG。共同原则是边界清晰、状态可恢复、输出可追溯。”

