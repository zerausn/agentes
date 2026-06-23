#!/data/data/com.termux/files/usr/bin/bash
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
LOG=/data/data/com.termux/files/home/tiktok_stack.log
PROOT=/data/data/com.termux/files/usr/bin/proot-distro
echo "=== Boot: $(date) ===" >> "$LOG"
pkill -f "proot.*daemon" 2>/dev/null; sleep 1
rm -f /data/data/com.termux/files/home/tiktok_daemon.lock 2>/dev/null
setsid "$PROOT" login debian -- /bin/bash /root/tiktok_daemon.sh > /dev/null 2>&1 &
echo "Daemon PID: $!" >> "$LOG"
sleep 20
FLASK=$("$PROOT" login debian -- /usr/bin/curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://127.0.0.1:8080/ 2>/dev/null)
NGROK_URL=$("$PROOT" login debian -- /bin/bash -c 'for P in 4042 4040; do U=$(/usr/bin/python3 -c "import json; d=json.load(open(\"/dev/stdin\")); t=d.get(\"tunnels\",[]); print(t[0][\"public_url\"] if t else \"\")" <<< "$(/usr/bin/curl -s --max-time 3 http://127.0.0.1:$P/api/tunnels 2>/dev/null)" 2>/dev/null); if [ -n "$U" ]; then echo "$U"; break; fi; done' 2>/dev/null)
[ "$FLASK" = "200" ] && echo "Flask: OK" >> "$LOG" || echo "Flask: HTTP $FLASK" >> "$LOG"
[ -n "$NGROK_URL" ] && echo "ngrok: $NGROK_URL" >> "$LOG" || echo "ngrok: starting..." >> "$LOG"
echo "=== Boot done ===" >> "$LOG"
