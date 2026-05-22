#!/data/data/com.termux/files/usr/bin/sh
export HOME=/data/data/com.termux/files/home
export PREFIX=/data/data/com.termux/files/usr
export PATH=$PREFIX/bin:/bin:/system/bin:/system/xbin

sh "$HOME/.termux/boot/start_sshd.sh"
echo "user=$(whoami)"
ip -f inet addr show wlan0 2>/dev/null | sed -n 's/.*inet \([0-9.]*\)\/.*/ip=\1/p' | head -n 1
ps -A | grep sshd || true
