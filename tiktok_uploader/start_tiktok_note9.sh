#!/bin/bash
# Start TikTok Uploader stack on Note9 (SM-X210)
# Dependencies: Termux with tmux, proot-distro with Debian
# Debian needs: python3, ngrok, tmux
#
# Usage: ssh note9 "bash ~/start_tiktok_stack.sh"

REPO_DIR=/root/agentes/tiktok_uploader
TERMUX_BOOT_SCRIPT=~/.termux/boot/start_tiktok.sh

# Kill existing tmux sessions
tmux kill-session -t tiktok 2>/dev/null

# Start Flask in tmux (inside Debian proot)
tmux new-session -d -s tiktok -n flask \
  "proot-distro login debian -- bash -c 'cd $REPO_DIR && source venv/bin/activate && python3 -u app.py'"

sleep 3

# Start ngrok in tmux (inside Debian proot)
tmux new-window -t tiktok -n ngrok \
  "proot-distro login debian -- bash -c 'ngrok http 127.0.0.1:8080 --log=stdout'"

sleep 8

# Get ngrok URL via local API
NGROK_URL=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | grep -oP '"public_url":"https://[^"]+' | head -1 | cut -d'"' -f4)

echo "=== TikTok Stack Status ==="
curl -s -o /dev/null -w "Flask local: %{http_code}\n" http://127.0.0.1:8080/
echo "ngrok URL: $NGROK_URL"
echo "tmux sessions:"
tmux ls
echo ""
echo "To attach: tmux attach -t tiktok"
echo "To view ngrok web UI: http://127.0.0.1:4040"
