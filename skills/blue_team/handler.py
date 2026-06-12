"""蓝队监测 Skill — SOC 运营流程"""
def handle(question: str, context: str = "") -> str:
    return """[蓝队监测] 安全运营标准工作流：
1. 资产发现 → 确认监控范围
2. 日志采集 → SIEM汇聚（Splunk/ELK）
3. 规则告警 → Sigma/YARA检测
4. 告警研判 → 确认误报/真实威胁
5. 事件响应 → 分级处置(P0/P1/P2)
6. 溯源取证 → 分析攻击路径
7. 复盘报告 → 改进防御策略"""
