"""Web Security Skill — SQL注入/XSS/SSRF 分析"""
def handle(question: str, context: str = "") -> str:
    # 检测注入特征
    indicators = ["'", '"', "OR 1=1", "UNION SELECT", "--", "<script>", "alert(", "document.cookie", "SSRF"]
    found = [i for i in indicators if i.lower() in question.lower() or i.lower() in context.lower()]
    return f"[WebSecurity] 检测特征: {', '.join(found)}" if found else "[WebSecurity] 未检测到明显攻击特征"
