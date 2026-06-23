#!/data/data/com.termux/files/usr/bin/bash
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
PROOT=/data/data/com.termux/files/usr/bin/proot-distro
LOGDIR=/data/data/com.termux/files/home

ngrok_url() {
    "$PROOT" login debian -- /bin/bash -c '
        for P in 4042 4040; do
            U=$(/usr/bin/python3 -c "import json; d=json.load(open(\"/dev/stdin\")); t=d.get(\"tunnels\",[]); print(t[0][\"public_url\"] if t else \"\")" <<< "$(/usr/bin/curl -s --max-time 3 http://127.0.0.1:$P/api/tunnels 2>/dev/null)" 2>/dev/null)
            if [ -n "$U" ]; then echo "$U"; break; fi
        done
    ' 2>/dev/null
}

check() {
    FLASK_HTTP=$("$PROOT" login debian -- /usr/bin/curl -s -o /dev/null -w "%{http_code}" --max-time 2 http://127.0.0.1:8080/ 2>/dev/null)
    NGROK_URL=$(ngrok_url)
}
check

clear
echo "=========================================="
echo "         TikTok Uploader Stack"
echo "=========================================="
echo ""
[ "$FLASK_HTTP" = "200" ] && echo "  Flask:  RUNNING" || echo "  Flask:  STOPPED"
[ -n "$NGROK_URL" ] && echo "  ngrok:  $NGROK_URL" || echo "  ngrok:  STOPPED"
echo ""
echo "  [1] Start"
echo "  [2] Stop"
echo "  [3] Logs"
echo "  [4] Exit"
echo ""
echo -n "  Choose: "
read opt
case "$opt" in
    1)
        echo ""; echo "  Cleaning lock..."
        "$PROOT" login debian -- /bin/rm -f /root/tiktok_daemon.lock 2>/dev/null
        echo "  Stopping old daemon..."
        pkill -f "proot.*daemon" 2>/dev/null; sleep 2
        echo "  Starting daemon..."
        setsid "$PROOT" login debian -- /bin/bash /root/tiktok_daemon.sh > /dev/null 2>&1 &
        echo -n "  Waiting"
        for i in 1 2 3 4 5 6 7 8 9 10 11 12; do sleep 1; echo -n "."; done
        echo ""; echo ""; check
        [ "$FLASK_HTTP" = "200" ] && echo "  Flask: RUNNING" || echo "  Flask: NOT READY"
        [ -n "$NGROK_URL" ] && echo "  ngrok: $NGROK_URL" || echo "  ngrok: still starting"
        ;;
    2)
        echo ""; echo "  Stopping..."
        pkill -f "proot.*daemon" 2>/dev/null
        "$PROOT" login debian -- /usr/bin/fuser -k 8080/tcp 4040/tcp 4042/tcp 2>/dev/null
        sleep 2; echo "  Stopped"
        ;;
    3)
        echo ""; echo "  -- Daemon log --"
        "$PROOT" login debian -- /usr/bin/tail -10 /root/tiktok_daemon.log 2>/dev/null || echo "  (empty)"
        echo ""; echo "  -- ngrok log (last 3) --"
        "$PROOT" login debian -- /usr/bin/tail -3 /root/ngrok.log 2>/dev/null || echo "  (empty)"
        ;;
    4) exit 0 ;;
esac
echo ""; echo "  Press ENTER to close"; read dummy
