# Nobody — AI Security Partner

> no0boy 的安全搭档。你学什么，它学什么。你变强，它变强。

---

## 定位

**不是聊天机器人，不是 Demo，不是一次性项目。**

是一个会思考、会规划、会调用工具、会长期学习、会主动协助你的安全智能体。

---

## 架构全景

```
                        ┌──────────────┐
                        │   🧠 大脑     │
                        │   Nobody     │
                        │              │
                        │  人格：直接犀利 │
                        │  记忆：你是谁   │
                        │  知识：你教过什么│
                        └──────┬───────┘
                               │
             思考 → 规划 → 决定调哪个技能
                               │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
      ┌────┴────┐       ┌──────┴──────┐       ┌───┴───┐
      │ 自然对话 │       │  技能系统    │       │ 知识库 │
      │ (Chat)  │       │  (Skills)   │       │ (RAG) │
      └─────────┘       └──────┬──────┘       └───────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
       ┌────┴────┐      ┌──────┴──────┐    ┌──────┴──────┐
       │ SQL注入  │      │  Burp分析   │    │  报告生成    │
       └─────────┘      └─────────────┘    └─────────────┘
```

---

## 目录结构（配置驱动）

```
ai助手/
├── brain.py              ← 核心引擎（不动）
├── persona.json          ← 改这个 = 改人格
├── provider.json         ← 改这个 = 换模型
│
├── agents/               ← 放一个json = 注册一个Agent
│   ├── threat_hunter.json    威胁研判
│   ├── log_analyst.json      日志分析
│   ├── vuln_researcher.json  漏洞研究
│   ├── incident_response.json 应急处置
│   ├── compliance_audit.json 合规审计
│   └── threat_intel.json    威胁情报
│
├── skills/               ← 放一个json = 注册一个技能
│   ├── sql_injection.json
│   ├── xss.json
│   ├── cve_lookup.json
│   ├── burp_parser.json
│   ├── nmap_analyzer.json
│   ├── report_generator.json
│   └── ...（持续新增）
│
├── knowledge/            ← 丢文件进去 = 自动索引
│   ├── notes/            你的笔记
│   ├── writeups/         你的靶场记录
│   ├── cheatsheets/      速查表
│   ├── payloads/         收藏的Payload
│   └── cve_reports/      CVE分析报告
│
├── memory/               ← 长期记忆存储
│   ├── learning.json     你学了什么、什么时候
│   ├── preference.json   你喜欢什么风格
│   └── experience.json   你的经验积累
│
├── frontend/             ← 前端界面
│   ├── login.html
│   ├── index.html        聊天页
│   └── admin.html        管理后台
│
├── api/                  ← API路由
│   ├── chat.py
│   ├── auth.py
│   └── webhook.py
│
├── Dockerfile
└── README.md
```

---

## 大脑与模型解耦

```
大脑（Nobody）= 人格 + 记忆 + 知识 + 技能
    ↓ 调用
模型提供者（Provider）
    ├── Qwen      ← 现在用
    ├── Claude    ← 可切换
    ├── DeepSeek  ← 可切换
    └── Ollama    ← 本地模型
```

**换模型只改 provider.json，不碰大脑。**

---

## 三层记忆

| 层级 | 存什么 | 例子 |
|------|--------|------|
| 身份记忆(Identity) | 你是谁 | "no0boy，红队方向，大三，偏好直接风格" |
| 学习记忆(Learning) | 学习轨迹 | "2025.6.10 学了SQL注入，6.12 学了XSS" |
| 经验记忆(Experience) | 实战积累 | "上次这个Payload对IIS没用，用报错注入" |
| 偏好记忆(Preference) | 交互习惯 | "回答详细一点 / 简洁一点 / 只给Payload" |

---

## 技能系统

每个技能 = 一个 JSON 文件，丢进 `skills/` 即注册：

```json
{
  "name": "sql_injection",
  "display": "SQL注入分析",
  "category": "hacker",
  "triggers": ["SQL注入", "sqli", "报错注入", "盲注"],
  "tools": ["sqli_detect", "sqli_exploit", "sqli_payload"],
  "knowledge": ["sql_injection_guide.md", "sqli_cheatsheet.md"]
}
```

**加新技能不动核心代码。**

---

## 演进路线

```
v1.0 → 安全问答 Agent    复用校园框架，换安全知识库
v1.1 → 安全 Router       意图分类 + 严重度评估(P0/P1/P2)
v1.2 → 技能系统          插件化加载，配置驱动
v1.3 → 三层记忆          Persona + 学习记录 + 经验积累
v1.4 → 主动规划          不等问，主动提醒和建议
v2.0 → 伙伴模式          你教它学，公开知识库
```

---

## Agent 决策流程

Nobody 不是问什么答什么。它的内部流程是：

```
感知 → 思考 → 规划 → 推理 → 决策 → 执行
(Sense→Think→Plan→Reason→Decide→Act)
```

收到一个问题后：
1. Think：这是什么类型的安全问题？
2. Plan：需要哪几个技能配合？
3. Reason：分析已有信息，够不够？还要查什么？
4. Decide：最终怎么回答？要不要主动追问？
5. Act：调 Skill/Tool/RAG → 生成回答

---

## 项目宪法

> 1. 不推倒现有架构，渐进式演进。
> 2. 整个系统只有一个 Brain，与具体模型解耦。
> 3. 所有能力通过 Skill/Plugin 注册，不写死在核心代码。
> 4. 不允许为了实现新功能破坏整体架构。
> 5. 不允许出现高耦合设计。
> 6. 任何重大架构调整必须先说明理由并征求确认。
> 7. 知识自动索引，丢文件即入库。
> 8. 记忆长期保留，换模型不丢记忆。
> 9. 小步迭代，每版本只加一个核心能力。
> 10. 保持架构清晰、稳定、可长期维护。

---

## 技能分类（Plugin First）

所有能力都是 Skill，放在 `skills/` 下：

```
skills/
├── hacker/              ← 攻击技能
│   ├── sql_injection.json
│   ├── xss.json
│   ├── ssrf.json
│   ├── xxe.json
│   ├── rce.json
│   ├── file_upload.json
│   └── ...
│
├── red_team/            ← 红队技能
│   ├── nmap.json
│   ├── bloodhound.json
│   ├── ad_attack.json
│   └── ...
│
├── blue_team/           ← 蓝队技能
│   ├── log_analysis.json
│   ├── sigma_rules.json
│   ├── yara_rules.json
│   └── ...
│
├── tools/               ← 工具技能
│   ├── cve_lookup.json
│   ├── burp_parser.json
│   ├── ioc_analyzer.json
│   └── report_generator.json
│
├── learning/            ← 学习技能
│   ├── study_planner.json
│   ├── knowledge_check.json
│   └── review_reminder.json
│
└── linux/               ← 系统技能
    ├── privilege_escalation.json
    ├── bash_scripting.json
    └── ...
```

**加新技能：新建 JSON → 丢进对应文件夹 → Nobody 自动识别。**

---

## 核心原则

- 配置驱动，不写死
- 技能插件化，加能力不改核心
- 大脑与模型解耦，换模型只改一行
- 知识自动索引，丢文件即入库
- 长期演进，每阶段一个能力

---

## 当前版本

**v1.0** — 基于校园AI平台框架的安全问答 Agent，6个安全Agent，OWASP/CVE知识库。

即将开始。
