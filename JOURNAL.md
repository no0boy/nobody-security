# Nobody 开发日志

---

## 🎯 Master 学习路线（驻场安全方向）

> 目标：应聘驻场安全工程师
> Nobody 角色：记录进度、提供参考、主动回顾、陪伴成长

### 第一阶段：Web 漏洞基础（第 1-4 周）
| 平台 | 内容 | 对应 Nobody Skill |
|------|------|-------------------|
| TryHackMe | DVWA 房间 → SQL 注入、XSS、文件上传、命令注入 | web_security |
| TryHackMe | OWASP Top 10 房间 | web_security |
| TryHackMe | Burp Suite 基础房间 | web_security |

**目标**：四个漏洞能从手工探测到拿到 shell，每个漏洞用自己的话讲清楚原理 → 检测 → 防御

### 第二阶段：Linux 安全 + 蓝队基础（第 5-8 周）
| 平台 | 内容 | 对应 Nobody Skill |
|------|------|-------------------|
| TryHackMe | Linux 提权房间 | linux |
| TryHackMe | 日志分析 / SOC 基础房间 | blue_team |
| 本地 WSL | 搭 Metasploitable，练 SUID/cron/SSH 后门检测 | linux |

**目标**：能排查一份 auth.log，能识别常见持久化后门

### 第三阶段：内网 + 域攻防（第 9-12 周）
| 平台 | 内容 | 对应 Nobody Skill |
|------|------|-------------------|
| 本地虚拟机 | 搭 Windows Server + AD 域控 | — |
| TryHackMe | Active Directory 基础 | — |
| HackTheBox | 简单的 Windows 靶机 | — |

**此时必须搭本地**：线上平台模拟不了真实域环境

### 第四阶段：综合实战 + 面试准备（第 13-16 周）
| 平台 | 内容 |
|------|------|
| HackTheBox | 中等难度靶机，独立完成全链路 |
| 自己 | 整理 Timeline，回顾 Nobody 记录的所有学习 |
| 自己 | 做 3 套驻场面试真题，用 Nobody 模拟面试 |

### 日常习惯
- 每次打完一个靶场 → 点 Nobody 的 ➕ 记下来
- 每周日打开 Nobody「时间线」看一周学了什么
- Nobody 的 Skill 不是背答案，是**你的参考资料库**

---

### 背景
Nobody 从「安全领域 Q&A 引擎 + 手动记忆本」重构为「长期 AI 伙伴（Continuous Growth）」。

### 核心决策

#### ADR-001: 不 Fine-tune，用 Context Assembly 实现成长
- **决策**：Nobody 不训练模型。通过每轮对话前动态组装上下文来实现「记住 Master」。
- **替代方案**：Fine-tune → 否决，成本高、不可解释、难迭代。
- **影响**：所有「成长」逻辑都在上下文组装层，不涉及模型权重。

#### ADR-002: 上下文分层注入 + Token 预算，非全量注入
- **决策**：8 层上下文分为三个 Tier：
  - Tier 1（绝对注入）：核心身份摘要 + 偏好摘要，< 500 chars
  - Tier 2（语义检索）：Memory / Experience / Builtin 中与当前问题相关的 top-3
  - Tier 3（按需注入）：Project 上下文仅在匹配时加载
- **替代方案**：全量注入 8 层 → 否决，浪费上下文窗口，分散 LLM 注意力。
- **影响**：需要 Token 预算管理器，每个 chunk 注入前检查预算。

#### ADR-003: 一张 events 表替代 Memory/Experience/Timeline 三表拆分
- **决策**：统一事件流 `events` 表，Memory / Experience / Timeline 是查询视图，不是存储实体。
- **替代方案**：三张独立表 → 否决，写入复杂度高，跨类型查询需要 UNION，数据一致性风险。
- **Schema**：type CHECK IN ('memory','learning','research','achievement','note','decision')
- **影响**：所有写入走 `Journal.add()` 唯一入口。

#### ADR-004: Memory Evaluator 改为离线批量模式
- **决策**：不做每轮 LLM 评估。改为：静默日志（自动追加 7 天 TTL）+ 每日/每会话离线反思 → 下次对话开头批量汇报。
- **替代方案**：每轮后 LLM 评估 → 否决，延迟 + 确认疲劳。
- **影响**：Evaluator 是后台任务，不阻塞对话流水线。

#### ADR-005: 三层架构 api/ → core/ → store/
- **决策**：
  - `api/` — HTTP 路由，按资源拆分（conversation / memory / profile / project / journal）
  - `core/` — 业务逻辑，不碰 HTTP
  - `store/` — 数据访问，SQLite 连接管理 + schema 迁移
  - `services/` — 外部服务封装（embedding / LLM）
- **影响**：依赖方向单向：api → core → store。core 可独立测试。

### 审查发现的技术债

1. `services/hybrid_search.py` 引用不存在的 `import config` — 死代码
2. SQLite 连接每次操作都 connect/close — 需要请求级连接复用
3. `sys.path.insert` 散落 5 个文件 — 改用 `python -m` 启动
4. `brain.py` 的 `_llm` 是模块级全局单例，无 lazy re-init
5. `core/planner.py` 的 ROADMAP 硬编码 — 将被 Journal 替代
6. `core/memory.py` 的 `learn()` 函数用硬编码关键词匹配 — 将被 Journal 替代

### 实施顺序

### v3.0 已实施（2026-06-12）

| 任务 | 状态 |
|------|------|
| 修 hybrid_search.py import 错误 | ✅ |
| 建 store/database.py（统一连接管理） | ✅ |
| 建 events 表 + core/journal.py | ✅ |
| 实现 core/context.py（分层注入 + Token 预算） | ✅ |
| 重构 brain.py → talk() | ✅ |
| 拆分 api/chat.py → conversation/journal/profile | ✅ |
| core/profile.py（Master 身份 + 偏好） | ✅ |
| 安全加固：全端点限流 + 软删除 | ✅ |
| 游客零成本：缓存→RAG 直出 | ✅ |
| 前端 6→3 面板（对话/时间线/我） | ✅ |
| 我面板：技能树 + 目标管理 | ✅ |
| Skill 深化：web_security / cve / blue_team / linux | ✅ |

### 待实施

| 优先级 | 任务 |
|--------|------|
| 🟢 v3.1 | 离线 Evaluator |
| 🟢 v3.x | 前端渐进优化 |
| ⚪ | 清理死代码（planner/learn/训练面板） |

### 产品定位

Nobody 不是聊天机器人。Nobody 是一个拥有 Builtin（基础知识）、Identity（人格与偏好）、Memory（长期记忆）、Journal（共同成长日志）、Project（项目经验）、Skill Tree（能力树）的长期 AI 伙伴。所有架构设计围绕「陪伴成长（Growing Together）」展开。
