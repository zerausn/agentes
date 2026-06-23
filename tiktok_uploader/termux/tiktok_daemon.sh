#!/usr/bin/bash
LOG=/root/tiktok_daemon.log
LOCK=/root/tiktok_daemon.lock

if [ -f "$LOCK" ]; then
    LOCK_PID=$(cat "$LOCK" 2>/dev/null)
    if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then exit 0; fi
fi
echo $$ > "$LOCK"
echo "=== Daemon starting at $(date) ===" >> "$LOG"

fuser -k 8080/tcp 2>/dev/null
fuser -k 4040/tcp 4042/tcp 2>/dev/null
sleep 2

echo "Starting Flask..." >> "$LOG"
python3 -u /root/agentes/tiktok_uploader/app.py &>/root/flask.log &
sleep 2

for i in 1 2 3 4 5; do
    if curl -s -o /dev/null --max-time 2 http://127.0.0.1:8080/ 2>/dev/null; then
        echo "Flask ready after ${i}s" >> "$LOG"; break
    fi
    sleep 1
done

echo "Starting ngrok..." >> "$LOG"
ngrok http 127.0.0.1:8080 --log=stdout &>/root/ngrok.log &
sleep 3

NGROK_URL=
for i in 1 2 3 4 5 6 7 8 9 10; do
    for PORT in 4042 4040; do
        URL=$(python3 -c 'import json,sys; d=json.load(sys.stdin); t=d.get("tunnels",[]); print(t[0]["public_url"] if t else "")' 2>/dev/null < <(curl -s --max-time 3 http://127.0.0.1:$PORT/api/tunnels 2>/dev/null))
        if [ -n "$URL" ]; then
            echo "ngrok URL: $URL (port $PORT)" >> "$LOG"
            NGROK_URL="$URL"; break 2
        fi
    done
    sleep 2
done
[ -z "$NGROK_URL" ] && echo "ngrok: no URL after 20s" >> "$LOG"

while true; do
    FLASK_OK=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://127.0.0.1:8080/ 2>/dev/null)
    if [ "$FLASK_OK" != "200" ]; then
        echo "Flask down at $(date) (HTTP $FLASK_OK), restarting..." >> "$LOG"
        fuser -k 8080/tcp 2>/dev/null
        python3 -u /root/agentes/tiktok_uploader/app.py &>/root/flask.log &
        sleep 3
    fi

    NGROK_OK=
    for PORT in 4042 4040; do
        NGROK_OK=$(python3 -c 'import json,sys; d=json.load(sys.stdin); t=d.get("tunnels",[]); print(t[0]["public_url"] if t else "")' 2>/dev/null < <(curl -s --max-time 3 http://127.0.0.1:$PORT/api/tunnels 2>/dev/null))
        [ -n "$NGROK_OK" ] && break
    done
    if [ -z "$NGROK_OK" ]; then
        echo "ngrok down at $(date), restarting..." >> "$LOG"
        fuser -k 4040/tcp 4042/tcp 2>/dev/null
        ngrok http 127.0.0.1:8080 --log=stdout &>/root/ngrok.log &
    fi

    sleep 30
done
