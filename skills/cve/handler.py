"""CVE Skill — 漏洞查询"""
def handle(question: str, context: str = "") -> str:
    cve_patterns = ["CVE-", "cve-"]
    for p in cve_patterns:
        idx = question.find(p)
        if idx >= 0:
            cve_id = question[idx:idx+14].split()[0].rstrip(".,;")
            return f"[CVE] 查询: {cve_id}"
    return ""
