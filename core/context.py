"""
上下文组装引擎 — Continuous Growth 的核心

三层注入模型:
  Tier 1: 绝对注入   (每次对话都在，严格控制长度)
  Tier 2: 语义检索   (与当前问题相关的 top-N)
  Tier 3: 按需注入   (仅在匹配时加载)

带 Token 预算管理，防止上下文溢出。
"""

from dataclasses import dataclass, field
from core.persona import name as persona_name, tone
from core.profile import Profile, Preference
from core.journal import Journal


# ── Token 预算 ──

@dataclass
class TokenBudget:
    """上下文 Token 预算管理器"""
    max_tokens: int = 1500        # 系统提示词上限
    used: int = 0

    def can_add(self, tokens: int) -> bool:
        return self.used + tokens <= self.max_tokens

    def spend(self, tokens: int):
        self.used += tokens

    def remaining(self) -> int:
        return max(0, self.max_tokens - self.used)


def estimate_tokens(text: str) -> int:
    """
    粗略估算 token 数。
    中文: ~1.5 字符/token
    英文: ~4 字符/token
    取保守估计: len(text) // 2
    """
    return max(1, len(text) // 2)


# ── 上下文组装 ──

@dataclass
class AssembledContext:
    """组装结果"""
    system_prompt: str
    sources: list[dict] = field(default_factory=list)
    debug: dict = field(default_factory=dict)


def assemble(
    question: str,
    user_id: str = "master",
    project_id: str = "",
    severity: str = "INFO",
) -> AssembledContext:
    """
    核心入口：为当前对话组装完整上下文。

    返回 AssembledContext，其中 system_prompt 可直接注入 LLM。
    """
    budget = TokenBudget()
    parts = []
    sources = []
    debug = {}

    # ── Tier 1: 绝对注入 ──
    _inject_identity(parts, budget, debug)
    _inject_preferences(parts, budget, debug)
    _inject_tone(parts, budget, severity, debug)

    # ── Tier 2: 语义检索（与 question 相关） ──
    _inject_knowledge(question, parts, budget, sources, debug)
    _inject_memories(question, parts, budget, sources, debug)
    _inject_experiences(question, parts, budget, sources, debug)

    # ── Tier 3: 按需注入 ──
    if project_id:
        _inject_project(project_id, parts, budget, debug)

    # ── 组装 SYSTEM PROMPT ──
    system_prompt = "\n\n".join(parts) if parts else "你是 Nobody，no0boy 的安全搭档。"

    return AssembledContext(
        system_prompt=system_prompt,
        sources=sources,
        debug={**debug, "budget_used": budget.used, "budget_max": budget.max_tokens},
    )


# ── 各层注入函数 ──

def _inject_identity(parts: list, budget: TokenBudget, debug: dict):
    """注入 Nobody 人格 + Master 身份摘要"""
    name = persona_name()
    identity = Profile.identity_summary()

    text = f"你是 {name}，no0boy 的安全搭档。\n{identity}" if identity else \
           f"你是 {name}，no0boy 的安全搭档。你与 Master 长期相处，日益熟悉。"

    tokens = estimate_tokens(text)
    if budget.can_add(tokens):
        parts.append(text)
        budget.spend(tokens)
        debug["identity"] = f"{tokens}t"


def _inject_preferences(parts: list, budget: TokenBudget, debug: dict):
    """注入 Master 偏好摘要"""
    summary = Preference.summary()
    if not summary:
        return
    text = f"回复时请注意：{summary}"
    tokens = estimate_tokens(text)
    if budget.can_add(tokens):
        parts.append(text)
        budget.spend(tokens)
        debug["preferences"] = f"{tokens}t"


def _inject_tone(parts: list, budget: TokenBudget, severity: str, debug: dict):
    """注入语气要求"""
    tone_text = tone(severity)
    if not tone_text:
        return
    text = f"语气：{tone_text}"
    tokens = estimate_tokens(text)
    if budget.can_add(tokens):
        parts.append(text)
        budget.spend(tokens)
        debug["tone"] = f"{tokens}t"


def _inject_knowledge(question: str, parts: list, budget: TokenBudget,
                       sources: list, debug: dict):
    """Tier 2: 从 Builtin 知识库检索相关片段"""
    try:
        from core.rag import search as rag_search
        chunks = rag_search(question)
        if chunks:
            text = f"参考知识：\n{chunks[:800]}"
            tokens = estimate_tokens(text)
            if budget.can_add(tokens):
                parts.append(text)
                budget.spend(tokens)
                sources.append({"type": "builtin", "preview": chunks[:200]})
                debug["builtin"] = f"{tokens}t"
    except Exception:
        debug["builtin"] = "skip"


def _inject_memories(question: str, parts: list, budget: TokenBudget,
                      sources: list, debug: dict):
    """Tier 2: 从长期记忆中语义检索相关条目"""
    try:
        memories = Journal.memories(limit=10)
        if not memories:
            debug["memory"] = "empty"
            return

        # 简易关键词过滤（后续换语义搜索）
        q_lower = question.lower()
        relevant = []
        for m in memories:
            score = sum(
                1 for kw in q_lower.split()
                if kw in m["summary"].lower() or kw in m.get("detail", "").lower()
            )
            if score > 0 or len(memories) <= 3:
                relevant.append((score, m))

        relevant.sort(key=lambda x: -x[0])
        top = [r[1] for r in relevant[:3]]

        if top:
            lines = ["相关记忆："]
            for item in top:
                lines.append(f"- {item['summary']}")
            text = "\n".join(lines)
            tokens = estimate_tokens(text)
            if budget.can_add(tokens):
                parts.append(text)
                budget.spend(tokens)
                sources.append({"type": "memory", "count": len(top)})
                debug["memory"] = f"{len(top)} items, {tokens}t"
    except Exception:
        debug["memory"] = "skip"


def _inject_experiences(question: str, parts: list, budget: TokenBudget,
                         sources: list, debug: dict):
    """Tier 2: 从经验日志中检索最近相关条目"""
    try:
        exps = Journal.experiences(days=30, limit=10)
        if not exps:
            debug["experience"] = "empty"
            return

        # 简易关键词过滤
        q_lower = question.lower()
        relevant = [e for e in exps if any(
            kw in e["summary"].lower() for kw in q_lower.split()
        )]

        recent = relevant[:3] if relevant else exps[:2]

        if recent:
            lines = ["最近经历："]
            for item in recent:
                date = item["created_at"][:10]
                lines.append(f"- [{date}] {item['summary']}")
            text = "\n".join(lines)
            tokens = estimate_tokens(text)
            if budget.can_add(tokens):
                parts.append(text)
                budget.spend(tokens)
                sources.append({"type": "experience", "count": len(recent)})
                debug["experience"] = f"{len(recent)} items, {tokens}t"
    except Exception:
        debug["experience"] = "skip"


def _inject_project(project_id: str, parts: list, budget: TokenBudget, debug: dict):
    """Tier 3: 按需注入项目上下文"""
    try:
        events = Journal.query(project_id=project_id, limit=10)
        if not events:
            return

        lines = [f"项目 [{project_id}] 最近动态："]
        for evt in events[:5]:
            lines.append(f"- {evt['summary']}")
        text = "\n".join(lines)
        tokens = estimate_tokens(text)
        if budget.can_add(tokens):
            parts.append(text)
            budget.spend(tokens)
            debug["project"] = f"{len(events[:5])} events, {tokens}t"
    except Exception:
        debug["project"] = "skip"
