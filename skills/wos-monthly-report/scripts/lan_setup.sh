#!/usr/bin/env bash
# 把 WSL 的 8080 暴露到局域网，让别人（手机/评委电脑）能扫码访问门户。
# 需要管理员权限：请由桌面「开启手机访问.bat」提权调用，不要在普通窗口直接跑。
# 日志写到 workspace/portal/lan_setup.log，跑完可查看结果。
set -u
W="${WOS_WORKDIR:-$HOME/wos-work}"
LOG="$W/portal/lan_setup.log"
mkdir -p "$W/portal"
exec > >(tee -a "$LOG") 2>&1

PS=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
NETSH=/mnt/c/Windows/System32/netsh.exe
echo "=== $(date '+%F %T') 配置局域网访问 ==="

# 1) 检查服务是否在跑（不在跑只提示，由「启动门户.bat」负责起服务）
if ss -ltn 2>/dev/null | grep -q ":8080 "; then
  echo "服务已在监听 8080"
else
  echo "⚠️ 8080 未监听：请先双击桌面「启动门户.bat」启动门户服务，再重跑本配置。"
fi

# 2) 取当前 WSL IP 与 Windows 局域网 IP
WSL_IP=$(hostname -I | awk '{print $1}')
WIN_IP=$("$PS" -NoProfile -Command "(Get-NetIPConfiguration | Where-Object {\$_.IPv4DefaultGateway -ne \$null -and \$_.InterfaceAlias -notmatch 'WSL|vEthernet|Loopback'} | Select-Object -First 1).IPv4Address.IPAddress" 2>/dev/null | tr -d '\r' | head -1)
[ -z "${WIN_IP:-}" ] && WIN_IP="${WIN_IP:-$(hostname -I | awk '{print $1}')}"
echo "WSL IP = $WSL_IP | Windows 局域网 IP = $WIN_IP"

# 3) 端口转发 + 防火墙放行（需要管理员，本脚本应由提权窗口调用）
"$NETSH" interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=8080 >/dev/null 2>&1
"$NETSH" interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8080 connectaddress="$WSL_IP" connectport=8080 2>&1
"$NETSH" advfirewall firewall delete rule name="Portal 8080" >/dev/null 2>&1
"$NETSH" advfirewall firewall add rule name="Portal 8080" dir=in action=allow protocol=TCP localport=8080 2>&1
echo "--- 当前端口转发规则 ---"
"$NETSH" interface portproxy show v4tov4 2>&1

# 4) 用局域网地址重新生成二维码与页面
PORTAL_URL="http://${WIN_IP}:8080/portal/" python3 "$W/build_portal.py" | tail -2

# 5) 从 Windows 侧自测（宿主经端口转发访问自己的局域网地址）
CODE=$("$PS" -NoProfile -Command "try{(Invoke-WebRequest 'http://${WIN_IP}:8080/portal/' -UseBasicParsing -TimeoutSec 6).StatusCode}catch{'FAIL '+\$_.Exception.Message}" 2>/dev/null | tr -d '\r')
echo "Windows 侧自测 http://${WIN_IP}:8080/portal/ -> ${CODE}"
echo
echo "手机（连同一个 WiFi）扫码或直接打开：http://${WIN_IP}:8080/portal/"
echo "注意：WSL 的 IP 每次重启会变，变了请再双击一次「开启手机访问.bat」。"
sleep 5
