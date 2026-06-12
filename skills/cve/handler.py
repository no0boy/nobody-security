"""CVE Skill — 漏洞查询与风险评估"""
import re
import json
import urllib.request
import ssl


def handle(question: str, context: str = "") -> str:
    """从问题中提取 CVE 编号，返回漏洞摘要与修复建议"""
    cve_id = _extract_cve(question)
    if not cve_id:
        return _search_by_keyword(question)

    # 尝试从 NVD 获取信息
    info = _fetch_cve(cve_id)
    if info:
        return f"[CVE] {cve_id}\n{info}"

    return _cve_reference(cve_id)


def _extract_cve(text: str) -> str:
    """提取 CVE 编号"""
    m = re.search(r'CVE-\d{4}-\d{4,}', text, re.IGNORECASE)
    return m.group(0).upper() if m else ""


def _fetch_cve(cve_id: str) -> str:
    """从 NVD API 获取 CVE 信息"""
    try:
        ctx = ssl.create_default_context()
        url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
        req = urllib.request.Request(url, headers={"User-Agent": "Nobody/3.0"})
        resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        data = json.loads(resp.read().decode())

        vulns = data.get("vulnerabilities", [])
        if not vulns:
            return ""

        cve = vulns[0].get("cve", {})
        desc = cve.get("descriptions", [{}])
        desc_text = next((d["value"] for d in desc if d.get("lang") == "en"), "")

        metrics = cve.get("metrics", {})
        cvss_v31 = metrics.get("cvssMetricV31", [{}])
        severity = cvss_v31[0].get("cvssData", {}).get("baseSeverity", "Unknown")
        score = cvss_v31[0].get("cvssData", {}).get("baseScore", "?")

        lines = [
            f"描述: {desc_text[:300]}",
            f"严重度: {severity} (CVSS {score})",
            f"详情: https://nvd.nist.gov/vuln/detail/{cve_id}",
        ]
        return "\n".join(lines)

    except Exception:
        return ""


def _cve_reference(cve_id: str) -> str:
    """CVE 速查参考"""
    year = cve_id.split("-")[1] if "-" in cve_id else ""
    return (
        f"[CVE] {cve_id}\n"
        f"严重度与影响请参考：\n"
        f"- NVD: https://nvd.nist.gov/vuln/detail/{cve_id}\n"
        f"- MITRE: https://cve.mitre.org/cgi-bin/cvename.cgi?name={cve_id}\n"
        f"- CVEDetails: https://www.cvedetails.com/cve/{cve_id}/\n"
        f"\n建议:\n"
        f"1. 检查受影响版本是否匹配\n"
        f"2. 优先查看厂商公告获取补丁\n"
        f"3. 评估 CVSS 向量中攻击复杂度与权限要求"
    )


def _search_by_keyword(question: str) -> str:
    """关键词导向的漏洞搜索建议"""
    q = question.lower()
    topics = {
        "log4j": "CVE-2021-44228 (Log4Shell) — CVSS 10.0, JNDI 注入, 影响 Log4j 2.0-2.14.1",
        "spring4shell": "CVE-2022-22965 — Spring Framework RCE, JDK 9+, Tomcat 部署",
        "heartbleed": "CVE-2014-0160 — OpenSSL 心跳信息泄露, 1.0.1-1.0.1f",
        "eternalblue": "CVE-2017-0144 — MS17-010 SMBv1 RCE, WannaCry 利用",
        "shellshock": "CVE-2014-6271 — Bash 环境变量注入",
        "dirty pipe": "CVE-2022-0847 — Linux 内核 5.8+ 本地提权",
        "follina": "CVE-2022-30190 — MSDT RCE, Office 文档触发",
        "proxyshell": "CVE-2021-34473 — Exchange Server RCE",
        "proxylogon": "CVE-2021-26855 — Exchange Server SSRF",
    }
    for keyword, info in topics.items():
        if keyword in q:
            return f"[CVE] {info}"
    return ""
