"""蓝队监测 Skill — 日志分析 / 入侵检测 / 应急响应"""
import re


def handle(question: str, context: str = "") -> str:
    """根据问题类型返回对应的蓝队操作指南"""
    q = (question + " " + context).lower()

    # 日志分析
    if _match(q, ["日志", "log", "分析日志", "access.log", "auth.log", "syslog", "windows事件"]):
        return _log_analysis(q)

    # 入侵检测
    if _match(q, ["入侵", "入侵检测", "webshell", "后门", "木马", "异常进程", "可疑连接",
                   "检测", "排查"]):
        return _intrusion_detection(q)

    # 应急响应
    if _match(q, ["应急", "响应", "incident", "处置", "被黑了", "被入侵", "勒索", "挖矿",
                   "数据泄露"]):
        return _incident_response(q)

    # 流量分析
    if _match(q, ["流量", "pcap", "wireshark", "tcpdump", "网络", "抓包"]):
        return _traffic_analysis()

    # 威胁狩猎
    if _match(q, ["狩猎", "threat hunt", "威胁", "ioc", "指标"]):
        return _threat_hunting()

    # 默认
    return _default_guide()


def _match(text: str, keywords: list) -> bool:
    return any(kw in text for kw in keywords)


def _log_analysis(q: str) -> str:
    guide = "[蓝队] 日志分析要点：\n"
    guide += "1. 异常时间: 非工作时间的登录/操作\n"
    guide += "2. 高频失败: 同一IP短时间内大量 401/403\n"
    guide += "3. 异常 UA: 非浏览器 User-Agent (curl/wget/python)\n"
    guide += "4. 路径扫描: /admin /wp-admin /.env /.git 等探测\n"
    guide += "5. SQLi 特征: 参数中含 ' OR 1=1 / UNION SELECT\n"
    guide += "\n常用命令：\n"
    guide += "- grep '404\|403\|500' access.log | cut -d' ' -f1 | sort | uniq -c | sort -rn\n"
    guide += "- grep 'select\|union\|sleep' access.log  # SQLi 探测\n"
    guide += "- last -f /var/log/auth.log | grep 'Failed'  # SSH 爆破"
    return guide


def _intrusion_detection(q: str) -> str:
    guide = "[蓝队] 入侵检测清单：\n"
    guide += "进程排查:\n"
    guide += "  ps auxf | grep -E 'nc|bash -i|/dev/tcp|python -c|wget.*sh'\n"
    guide += "  lsof -i -P -n | grep ESTABLISHED  # 异常外联\n"
    guide += "\n持久化检查:\n"
    guide += "  crontab -l | grep -v '^#'\n"
    guide += "  cat /etc/rc.local\n"
    guide += "  systemctl list-units --state=running | grep -v '^●'\n"
    guide += "\nWebshell检测:\n"
    guide += "  find /var/www -name '*.php' -mtime -3  # 最近3天修改\n"
    guide += "  grep -r 'eval\|base64_decode\|system\|exec' /var/www  # 危险函数"
    return guide


def _incident_response(q: str) -> str:
    guide = "[蓝队] 应急响应流程：\n"
    guide += "P0 (正在被攻击):\n"
    guide += "  1. 隔离: iptables -A INPUT -s ATTACKER_IP -j DROP\n"
    guide += "  2. 止损: 断开受影响服务网络 / 停止服务\n"
    guide += "  3. 取证: tcpdump -i eth0 -w incident.pcap\n"
    guide += "\nP1 (确认入侵):\n"
    guide += "  1. 保留现场: 不重启/不删文件/不覆盖日志\n"
    guide += "  2. 取证收集: 内存dump + 磁盘镜像 + 日志备份\n"
    guide += "  3. 分析入口: 检查 Web 日志/SSH 日志/数据库日志\n"
    guide += "\nP2 (事后复盘):\n"
    guide += "  1. 攻击路径还原: 入口 → 提权 → 横向移动 → 持久化\n"
    guide += "  2. 修复加固: 补丁 + 配置 + 最小权限\n"
    guide += "  3. 检测规则: Sigma 规则 → SIEM 告警"
    return guide


def _traffic_analysis() -> str:
    guide = "[蓝队] 流量分析要点：\n"
    guide += "tcpdump 常用:\n"
    guide += "  tcpdump -i eth0 -w capture.pcap port not 22\n"
    guide += "  tcpdump -r capture.pcap 'tcp[tcpflags] & tcp-syn != 0'  # SYN扫描\n"
    guide += "\ntshark 常用:\n"
    guide += "  tshark -r capture.pcap -Y 'http.request' -T fields -e http.host -e http.request.uri\n"
    guide += "  tshark -r capture.pcap -Y 'dns' -T fields -e dns.qry.name | sort -u\n"
    guide += "\n关注指标:\n"
    guide += "  - DNS 隧道: 异常长域名 / 高频 TXT 查询\n"
    guide += "  - C2 心跳: 固定间隔的短连接\n"
    guide += "  - 数据外传: 出站流量突增 / 非标准端口"
    return guide


def _threat_hunting() -> str:
    guide = "[蓝队] 威胁狩猎框架：\n"
    guide += "1. 假设驱动: 攻击者可能已通过 XX 方式进入\n"
    guide += "2. IOC 搜索: IP / Domain / Hash / 注册表键\n"
    guide += "3. TTP 分析: 基于 MITRE ATT&CK 映射\n"
    guide += "4. 异常基线: 统计偏离正常行为的事件\n"
    guide += "\n数据源: EDR > 进程日志 > DNS日志 > 网络流 > 认证日志"
    return guide


def _default_guide() -> str:
    return (
        "[蓝队] 安全运营方向：\n"
        "1. 日志分析 — 从 Web/系统/安全日志中发现异常\n"
        "2. 入侵检测 — 进程/文件/网络/持久化 四维排查\n"
        "3. 流量分析 — pcap/wireshark/tshark 协议分析\n"
        "4. 应急响应 — P0隔离→P1取证→P2复盘\n"
        "5. 威胁狩猎 — IOC驱动 + TTP分析\n"
        "6. Sigma规则 — 检测规则编写与 SIEM 集成"
    )
