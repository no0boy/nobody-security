"""扫描探测 Skill — Nmap / 端口 / 指纹 / 目录 / 漏洞扫描"""


def handle(question: str, context: str = "") -> str:
    q = (question + " " + context).lower()

    # Nmap 扫描
    if _match(q, ["nmap", "端口扫描", "扫描命令", "-sS", "-sV", "-sC", "-A",
                   "masscan", "扫描器"]):
        return _nmap_guide(q)

    # 端口参考
    if _match(q, ["端口", "port", "常见端口", "3306", "6379", "3389", "22端口",
                   "服务端口", "默认端口"]):
        return _port_reference()

    # 指纹识别
    if _match(q, ["指纹", "fingerprint", "whatweb", "wappalyzer", "CMS",
                   "中间件", "框架", "服务版本"]):
        return _fingerprint_guide()

    # 子域名/目录
    if _match(q, ["子域名", "subdomain", "域名", "DNS", "目录扫描",
                   "dirb", "gobuster", "dirsearch", "旁站", "C段"]):
        return _domain_dir_guide()

    # 漏洞扫描/评估
    if _match(q, ["漏洞扫描", "nessus", "openvas", "awvs", "脆弱性",
                   "评估", "渗透测试流程", "报告", "基线"]):
        return _vuln_scan_guide()

    # 默认速查
    return _quick_ref()


def _match(text: str, keywords: list) -> bool:
    return any(kw.lower() in text for kw in keywords)


def _nmap_guide(q: str) -> str:
    return """[扫描] Nmap 命令速查：

## 基础扫描
```
nmap 192.168.1.1                    # 默认扫描（1000常用端口）
nmap -p 1-65535 192.168.1.1         # 全端口
nmap -p 80,443,8080 192.168.1.1     # 指定端口
nmap -sV 192.168.1.1                # 服务版本探测
nmap -O 192.168.1.1                 # OS 指纹识别
nmap -sC 192.168.1.1                # 默认脚本扫描
nmap -A 192.168.1.1                 # 全部（版本+OS+脚本+traceroute）
```

## 扫描方式
```
nmap -sS 192.168.1.1                # SYN半开扫描（最常用，快）
nmap -sT 192.168.1.1                # TCP全连接扫描（慢但准确）
nmap -sU -p 53,161 192.168.1.1      # UDP扫描
nmap -Pn 192.168.1.1                # 跳过主机发现（主机禁ping时）
```

## 常用脚本
```
nmap --script=vuln 192.168.1.1      # 漏洞检测
nmap --script=http-enum 192.168.1.1  # Web目录枚举
nmap --script=smb-enum-shares 192.168.1.1  # SMB共享枚举
nmap --script=ssl-enum-ciphers 192.168.1.1 # SSL密码套件
```

## 存活扫描
```
nmap -sn 192.168.1.0/24             # Ping扫描存活主机
nmap -sP 192.168.1.0/24             # 同上
nmap -T4 -F 192.168.1.0/24          # 快速扫描 C段（-T4 加速，-F 100端口）
```"""


def _port_reference() -> str:
    return """[扫描] 常见端口速查表：

| 端口 | 服务 | 关注点 |
|------|------|--------|
| 21 | FTP | 匿名登录、弱口令 |
| 22 | SSH | 弱口令、版本漏洞 |
| 23 | Telnet | 明文传输、弱口令 |
| 25 | SMTP | 邮件伪造 |
| 53 | DNS | 域传送漏洞 |
| 80/443 | HTTP/HTTPS | Web漏洞、CMS识别 |
| 135/139/445 | RPC/SMB | MS17-010、共享枚举 |
| 1433 | MSSQL | 弱口令、命令执行 |
| 1521 | Oracle | 弱口令、注入 |
| 3306 | MySQL | 弱口令、提权 |
| 3389 | RDP | 弱口令、BlueKeep(CVE-2019-0708) |
| 5432 | PostgreSQL | 弱口令 |
| 6379 | Redis | 未授权访问 |
| 7001/7002 | Weblogic | 反序列化漏洞 |
| 8080/8089 | Tomcat/Jenkins | 弱口令、war上传 |
| 8443 | HTTPS管理 | 弱口令 |
| 9200/9300 | Elasticsearch | 未授权访问 |
| 11211 | Memcached | 未授权访问 |
| 27017 | MongoDB | 未授权访问 |"""


def _fingerprint_guide() -> str:
    return """[扫描] Web 指纹识别：

## whatweb
```
whatweb http://target.com
whatweb -a 3 http://target.com        # 激进模式
whatweb --log-json=result.json http://target.com
```

## Wappalyzer
浏览器插件：Chrome搜索 Wappalyzer 安装
自动识别：CMS、框架、分析工具、CDN

## 手动识别
```
# 响应头
curl -I http://target.com | grep -iE "server|x-powered-by"

# Robots.txt
curl http://target.com/robots.txt

# 默认路径探测
/admin /wp-admin /phpmyadmin /manager/html

# favicon hash 匹配
curl http://target.com/favicon.ico | md5sum
# 对比 https://faviconhash.com 查 CMS
```

## 常见 CMS 识别
| CMS | 特征 |
|-----|------|
| WordPress | /wp-content/ /wp-admin/ /wp-login.php |
| Drupal | /sites/default/ /user/login |
| Joomla | /administrator/ /components/ |
| ThinkPHP | /index.php?s=/ 路径模式 |
| Shiro | cookie 中有 rememberMe=deleteMe |"""


def _domain_dir_guide() -> str:
    return """[扫描] 信息收集：

## 子域名发现
```
# 证书透明度
curl -s "https://crt.sh/?q=%25.target.com&output=json" | jq -r '.[].name_value' | sort -u

# 爆破
gobuster dns -d target.com -w subdomains.txt

# 在线
https://subdomainfinder.c99.nl
```

## 目录扫描
```
gobuster dir -u http://target.com -w common.txt -x php,asp,jsp,html
dirsearch -u http://target.com -e php,asp,jsp
dirb http://target.com /usr/share/wordlists/dirb/common.txt

# 关注找到的页面
.git/  .env  .svn/  backup/  upload/  admin/  test/
phpinfo.php  config.php.bak  robots.txt  sitemap.xml
```

## C段 / 旁站
```
# 同 IP 其他站点
https://dnsdumpster.com
https://site.ip138.com/target.com

# C段扫描
nmap -sn 192.168.1.0/24 -oG - | grep Up | cut -d' ' -f2
```"""


def _vuln_scan_guide() -> str:
    return """[扫描] 漏洞扫描与评估：

## 驻场扫描流程
```
1. 资产清单确认 → 哪些 IP/域名 在范围内？
2. 主机存活扫描 → nmap -sn
3. 端口扫描 → nmap -sV -sC -p-
4. 漏洞扫描 → Nessus/OpenVAS/AWVS
5. 漏洞验证 → 手工 + SQLMap/Burp
6. 报告输出 → 漏洞等级/修复建议/复现步骤
```

## Nessus 基础
```
# 启动
systemctl start nessusd

# 访问 https://localhost:8834
# 新建 Scan → Basic Network Scan → 输入目标 IP
# 跑完后导出 HTML/PDF 报告
```

## OpenVAS (开源替代)
```
gvm-cli tls --hostname localhost --port 9390 \\
  --username admin --password xxx socket --xml \\
  "<create_task><name>Scan</name><target id='xxx'/></create_task>"
```

## 报告关注点
| 等级 | 含义 | 处理 |
|------|------|------|
| Critical | 可远程getshell | 立即修复 |
| High | 可获取敏感信息/提权 | 24h内 |
| Medium | 需配合其他漏洞利用 | 计划修复 |
| Low | 信息泄露 | 记录跟踪 |

## 驻场笔试常考
- Nmap 常用参数：-sS -sV -sC -O -p- -Pn 各什么意思？
- 如何判断扫描结果中的漏洞是真还是误报？
- 端口 445/3306/6379/3389 开了分别有什么风险？"""


def _quick_ref() -> str:
    return """[扫描] 速查卡：

## 三步开局
```
nmap -sn 192.168.1.0/24                    # 1. 找活主机
nmap -sV -sC -p- 192.168.1.x               # 2. 扫全端口
whatweb http://192.168.1.x                  # 3. Web指纹
```

## 渗透测试流程（驻场面）
```
信息收集 → 漏洞扫描 → 漏洞验证 → 漏洞利用 → 权限维持 → 报告
```

## 驻场必会工具
- Nmap 端口扫描
- Nessus/OpenVAS 漏洞扫描
- whatweb 指纹识别
- gobuster/dirsearch 目录爆破
- Burp Suite Web测试
- SQLMap 注入自动化"""
