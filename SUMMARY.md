# Summary

## Overview

**Learn Claude Code -- Harness Engineering for Real Agents** is a 0-to-1 harness engineering course. Its central thesis: **agency comes from the model, not the surrounding code.** An agent product = Model (the intelligence, trained via gradient updates) + Harness (the environment that gives the model tools, knowledge, observation, action interfaces, and permissions).

### Key Ideas

- **Agency is trained, not coded** — proven by historical milestones: DeepMind DQN (Atari, 2013), OpenAI Five (Dota 2, 2019), AlphaStar (StarCraft II, 2019), Tencent Jueyu (Honor of Kings, 2019), and LLM coding agents (2024-2025).
- **What an agent is NOT** — drag-and-drop workflow builders, no-code "AI Agent" platforms, and prompt-chain orchestration libraries are just "shell scripts with grandiose pretensions." You cannot brute-force intelligence with procedural glue code.
- **Two meanings of "building an agent"** — (1) training a model, or (2) building a harness (the focus of this repo). The model decides; the harness executes.
- **Harness = Tools + Knowledge + Observation + Action Interfaces + Permissions**
- **Why Claude Code** — the most elegant agent harness because it doesn't try to be the agent; it gives the model tools and gets out of the way. The agent loop is constant; tools, knowledge, and permissions change.

### Core Agent Pattern

```
User --> messages[] --> LLM --> response
                             stop_reason == "tool_use"?
                              yes -> execute tools, append results, loop
                              no  -> return text
```

### Repository Layout

- **Current track (canonical): root-level `s01_agent_loop` through `s17_goal_loop`** — each chapter has an English README, Chinese/Japanese translations, runnable `code.py`, and diagrams where needed.
- **Legacy track (transition only): `docs/` and `agents/`** — older 12-lesson version; chapter numbers do not map 1:1 to the current track, so tracks should not be mixed.

### The 17 Progressive Lessons

| # | Chapter | Topic | Motto / Key Concept |
|---|---|---|---|
| s01 | Agent Loop | one loop + bash | "One loop & Bash is all you need" |
| s02 | Tool Use | dispatch map | "Adding a tool means adding one handler" |
| s03 | Permission | `PermissionRule` | "Set boundaries first, then grant freedom" |
| s04 | Hooks | `PreToolUse` / `PostToolUse` | "Hook around the loop, never rewrite the loop" |
| s05 | TodoWrite | plan-then-execute | "An agent without a plan drifts" |
| s06 | Subagent | fresh `messages[]` | context isolation; final text returns as one tool result |
| s07 | Skill Loading | `SkillLoader` | "Load knowledge on demand, not upfront" |
| s08 | Context Compact | 4-step compaction | "Context always fills up -- have a way to make room" |
| s09 | Memory | selection/extraction/consolidation | "Remember what matters, forget what doesn't" |
| s10 | Task System | `blockedBy` / disk persistence | "Big goals break into small tasks, ordered, persisted" |
| s11 | Background Tasks | threaded execution | "Slow ops go background, agent keeps thinking" |
| s12 | Cron Scheduler | time-triggered | "Fire on schedule, no human kick needed" |
| s13 | Agent Teams | teammates / task claims / worktrees | "Too big for one agent -- let teammates divide the work" |
| s14 | MCP Plugin | external tool pool | "Not enough capability? Plug in more via MCP" |
| s15 | Integrated Harness | one loop, many mechanisms | "Many mechanisms, one loop" |
| s16 | Workflow Runtime | resumable journals | "When the orchestration shape is fixed, put it in code" |
| s17 | Goal Loop | goal gate / evaluation | "A goal decides when the loop may stop" |

**Learning path:** act (s01-s04) → handle complex work (s05-s08) → remember across sessions (s09) → run long tasks (s10-s12) → collaborate (s13) → extend and assemble (s07, s14, s15) → orchestrate and close goals (s16, s17).

### Quick Start

```sh
git clone https://github.com/shareAI-lab/learn-claude-code
cd learn-claude-code
pip install -r requirements.txt
cp .env.example .env   # configure ANTHROPIC_API_KEY

python s01_agent_loop/code.py        # start here
python s08_context_compact/code.py   # context compaction (complex)
python s17_goal_loop/code.py         # endpoint chapter
```

Optional web platform: `cd web && npm install && npm run dev` → http://localhost:3000

### Related Projects / What's Next

- **Kode Agent CLI** — `npm i -g @shareai-lab/kode`; open-source coding agent CLI with skill/LSP support, Windows-compatible, works with GLM/MiniMax/DeepSeek.
- **Kode Agent SDK** — embed agent capabilities in backends, browser extensions, embedded devices.
- **claw0** — sister teaching repo for always-on assistants: `claw agent = agent core + heartbeat + cron + IM chat + memory + soul` (see OpenClaw).

### License

MIT

---

## requirements.txt

Three runtime dependencies (used across the course's runnable `code.py` examples):

| Package | Minimum Version | Purpose |
|---|---|---|
| `anthropic` | >= 0.25.0 | Claude API client — drives the agent loop / LLM calls |
| `python-dotenv` | >= 1.0.0 | Loads `ANTHROPIC_API_KEY` and other config from `.env` |
| `pyyaml` | >= 6.0 | YAML parsing (skills, task files, configs) |
