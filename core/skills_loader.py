"""SkillsLoader — 自动扫描 skills/ 目录，注册全部 Skill"""
import json, os, importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(ROOT, "skills")

_registry: dict[str, dict] = {}

def load_all() -> dict:
    """扫描 skills/ → 加载 skill.json → 导入 handler → 返回注册表"""
    global _registry
    _registry = {}
    if not os.path.exists(SKILLS_DIR): return _registry

    for name in os.listdir(SKILLS_DIR):
        skill_dir = os.path.join(SKILLS_DIR, name)
        skill_json = os.path.join(skill_dir, "skill.json")
        if not os.path.exists(skill_json): continue

        with open(skill_json, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        # 加载 handler
        handler = None
        handler_py = os.path.join(skill_dir, "handler.py")
        if os.path.exists(handler_py):
            spec = importlib.util.spec_from_file_location(f"skill_{name}", handler_py)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            handler = getattr(mod, "handle", None)

        _registry[name] = {**cfg, "handler": handler, "dir": skill_dir}
        print(f"[SkillLoader] 已注册: {name} ({cfg.get('display','')})")

    return _registry

def registry() -> dict:
    if not _registry: load_all()
    return _registry

def match(question: str) -> list:
    """匹配最佳 Skill 组合——关键词 + 优先级排序"""
    reg = registry()
    scored = []
    for name, cfg in reg.items():
        score = sum(1 for kw in cfg.get("triggers", []) if kw.lower() in question.lower())
        if score > 0:
            scored.append((score, cfg.get("priority", 5), name, cfg))
    scored.sort(key=lambda x: (-x[0], -x[1]))  # 分高优先
    return [s[2:] for s in scored[:3]]

def execute(question: str, context: str = "") -> list:
    """执行匹配的 Skill"""
    results = []
    for name, cfg in match(question):
        handler = cfg.get("handler")
        if handler:
            try:
                r = handler(question, context)
                if r: results.append({"skill": name, "result": r})
            except: pass
    return results
