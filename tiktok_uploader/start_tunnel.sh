#!/bin/bash
# Start Flask
cd /home/zerausn/Documents/Antigravity/agentes/tiktok_uploader
pkill -f "python3.*app.py" 2>/dev/null
python3 -u app.py > /tmp/flask.log 2>&1 &
sleep 2

# Start localhost.run tunnel and capture URL
python3 -c "
import subprocess, signal, os, sys, re
signal.signal(signal.SIGHUP, signal.SIG_IGN)
proc = subprocess.Popen(
    ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
     '-R', '80:localhost:8080', 'nokey@localhost.run'],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, preexec_fn=os.setpgrp)
url = None
for line in proc.stdout:
    m = re.search(r'https://[a-z0-9]+\.lhr\.life', line)
    if m:
        url = m.group(0)
        print('TUNNEL_URL=' + url)
        sys.stdout.flush()
        with open('/tmp/tunnel_url.txt', 'w') as f:
            f.write(url)
        break
proc.wait()
" > /tmp/tunnel_startup.log 2>&1
