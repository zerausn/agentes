#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

TERMUX_HOME="/data/data/com.termux/files/home"
PREFIX="/data/data/com.termux/files/usr"
PROOT="$PREFIX/bin/proot-distro"
REPO_DIR="$TERMUX_HOME/agentes"
BOOT_DIR="$TERMUX_HOME/.termux/boot"
SHORTCUTS_DIR="$TERMUX_HOME/.shortcuts"
ENV_FILE="$TERMUX_HOME/.agentes_termux_env"
DEVICE_PROFILE="${1:-generic}"
INSTALL_DEBIAN_DEPS="${AGENTES_INSTALL_DEBIAN_DEPS:-1}"

if [ ! -d "$REPO_DIR" ]; then
  echo "ERROR: no existe $REPO_DIR"
  exit 1
fi

if [ ! -x "$PROOT" ]; then
  echo "ERROR: proot-distro no encontrado en $PROOT"
  exit 1
fi

mkdir -p "$BOOT_DIR" "$SHORTCUTS_DIR"

case "$DEVICE_PROFILE" in
  note9)
    cat > "$ENV_FILE" <<'EOF'
export AGENTES_DEVICE_NAME="Note9"
export AGENTES_FFMPEG_PRESET=medium
export AGENTES_FFMPEG_CRF=20
export AGENTES_FFMPEG_AUDIO_BITRATE=160k
export AGENTES_SYNC_SEARCH_LIMIT=5000
export AGENTES_SYNC_SLEEP_SECONDS=8
export AGENTES_YTDLP_CONCURRENT_FRAGMENTS=1
EOF
    ;;
  s24)
    cat > "$ENV_FILE" <<'EOF'
export AGENTES_DEVICE_NAME="S24"
export AGENTES_SYNC_SEARCH_LIMIT=5000
export AGENTES_YTDLP_CONCURRENT_FRAGMENTS=1
EOF
    ;;
  vivo)
    cat > "$ENV_FILE" <<'EOF'
export AGENTES_DEVICE_NAME="Vivo"
export AGENTES_SYNC_SEARCH_LIMIT=5000
export AGENTES_YTDLP_CONCURRENT_FRAGMENTS=1
EOF
    ;;
  *)
    cat > "$ENV_FILE" <<'EOF'
export AGENTES_SYNC_SEARCH_LIMIT=5000
export AGENTES_YTDLP_CONCURRENT_FRAGMENTS=1
EOF
    ;;
esac
chmod 600 "$ENV_FILE"

cat > "$BOOT_DIR/start_sshd.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
export HOME=/data/data/com.termux/files/home
export PREFIX=/data/data/com.termux/files/usr
export PATH=$PREFIX/bin:/bin:/system/bin:/system/xbin
LOG="$HOME/.termux/boot/start_sshd.log"

mkdir -p "$HOME/.termux/boot" "$HOME/.shortcuts"

{
  echo "==== $(date '+%F %T') start_sshd ===="
  if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock || true
  fi
  ssh-keygen -A || true
  if ! ps -A | grep -q '[s]shd'; then
    sshd
  fi
  ip -f inet addr show wlan0 2>/dev/null | sed -n 's/.*inet \([0-9.]*\)\/.*/ip=\1/p' | head -n 1
  ps -A | grep sshd || true
} >> "$LOG" 2>&1

exit 0
EOF

cat > "$SHORTCUTS_DIR/Arrancar_SSH.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
export HOME=/data/data/com.termux/files/home
export PREFIX=/data/data/com.termux/files/usr
export PATH=$PREFIX/bin:/bin:/system/bin:/system/xbin

sh "$HOME/.termux/boot/start_sshd.sh"
echo "user=$(whoami)"
ip -f inet addr show wlan0 2>/dev/null | sed -n 's/.*inet \([0-9.]*\)\/.*/ip=\1/p' | head -n 1
ps -A | grep sshd || true
EOF

cat > "$SHORTCUTS_DIR/Estado_Remoto.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
export HOME=/data/data/com.termux/files/home
export PREFIX=/data/data/com.termux/files/usr
export PATH=$PREFIX/bin:/bin:/system/bin:/system/xbin

echo "date=$(date '+%F %T')"
echo "user=$(whoami)"
ip -f inet addr show wlan0 2>/dev/null | sed -n 's/.*inet \([0-9.]*\)\/.*/ip=\1/p' | head -n 1
ps -A | grep sshd || true
ls -l "$HOME/.ssh/authorized_keys" 2>/dev/null || true
tail -n 10 "$HOME/.termux/boot/start_sshd.log" 2>/dev/null || true
EOF

cat > "$SHORTCUTS_DIR/sincronizar_yt_a_fb.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
TERMUX_HOME="/data/data/com.termux/files/home"
LAUNCHER="$TERMUX_HOME/agentes/scripts/linux/sincronizar_yt_a_fb_termux.sh"
exec "$LAUNCHER"
EOF

cat > "$SHORTCUTS_DIR/vigia_meta.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
TERMUX_HOME="/data/data/com.termux/files/home"
LAUNCHER="$TERMUX_HOME/agentes/scripts/linux/vigia_meta_widget.sh"
if [ ! -f "$LAUNCHER" ]; then
  echo "[ERROR] no existe $LAUNCHER"
  echo "        Corre primero 0_RENOVAR_REPO para actualizar el repo."
  exit 1
fi
exec bash "$LAUNCHER" "$@"
EOF

cat > "$SHORTCUTS_DIR/Monitorear_Temperaturas.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"

echo "THERMAL SNAPSHOT"
echo "================"
if command -v termux-battery-status >/dev/null 2>&1; then
  battery_temp=$(termux-battery-status | grep -i temperature | awk '{print $2}' | sed 's/,//')
  echo "battery_c=${battery_temp:-unknown}"
fi
for tz in /sys/class/thermal/thermal_zone*; do
  type=$(cat "$tz/type" 2>/dev/null || true)
  temp=$(cat "$tz/temp" 2>/dev/null || true)
  if [ -n "$temp" ]; then
    if [ "$temp" -gt 1000 ] 2>/dev/null; then
      temp=$(("$temp" / 1000))
    fi
    echo "${type:-unknown}=${temp}C"
  fi
done | grep -Ei 'cpu|gpu|battery|tsens|quiet|skin' | head -n 12
echo "================"
read -r -p "Enter para cerrar..."
EOF

cat > "$SHORTCUTS_DIR/Monitor_Logs.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
TERMUX_HOME="/data/data/com.termux/files/home"
YT_LOG="$TERMUX_HOME/agentes/youtube_uploader/youtube_to_fb_sync.log"
META_LOG="$TERMUX_HOME/agentes/meta_uploader/fb_to_ig_vigia.log"

echo "YOUTUBE LOG"
echo "==========="
tail -n 40 "$YT_LOG" 2>/dev/null || echo "sin log de youtube"
echo
echo "META LOG"
echo "========"
tail -n 40 "$META_LOG" 2>/dev/null || echo "sin log de meta"
echo
read -r -p "Enter para cerrar..."
EOF

# --- Widget 0: PIPELINE COMPLETO ---
cat > "$SHORTCUTS_DIR/0_PIPELINE_COMPLETO.sh" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
exec bash "/data/data/com.termux/files/home/agentes/scripts/linux/pipeline_completo_termux.sh"
EOF

# --- Widget 0: RENOVAR REPO ---
cat > "$SHORTCUTS_DIR/0_RENOVAR_REPO.sh" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
exec bash "/data/data/com.termux/files/home/agentes/scripts/linux/renovar_repo_termux.sh"
EOF

# --- Widget 1: CORTAR TEASERS ---
cat > "$SHORTCUTS_DIR/1_CORTAR_TEASERS.sh" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
exec bash "/data/data/com.termux/files/home/agentes/scripts/linux/cortar_teasers_termux.sh"
EOF

# --- Widget 2: SUBIR CRUDOS YT ---
cat > "$SHORTCUTS_DIR/2_SUBIR_CRUDOS_YT.sh" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
exec bash "/data/data/com.termux/files/home/agentes/scripts/linux/subir_crudos_yt_termux.sh"
EOF

# --- Widget 3: SUBIR TEASERS YT ---
cat > "$SHORTCUTS_DIR/3_SUBIR_TEASERS_YT.sh" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
exec bash "/data/data/com.termux/files/home/agentes/scripts/linux/subir_teasers_termux.sh"
EOF

# --- Widget 4: VIGIA FACEBOOK ---
cat > "$SHORTCUTS_DIR/4_VIGIA_FACEBOOK.sh" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
exec bash "/data/data/com.termux/files/home/agentes/scripts/linux/vigia_facebook_termux.sh"
EOF

# --- Widget 5: BAJAR YOUTUBE SIN LÍMITE ---
cat > "$SHORTCUTS_DIR/5_BAJAR_YOUTUBE_SIN_LIMITE.sh" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
# 5_BAJAR_YOUTUBE_SIN_LIMITE — Widget puente hacia el descargador sin límite de fecha
# Termux Shortcut: ~/.shortcuts/5_BAJAR_YOUTUBE_SIN_LIMITE.sh
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
exec bash "/data/data/com.termux/files/home/agentes/scripts/linux/bajar_youtube_sin_limite_termux.sh"
EOF

# --- Widget: LIMPIAR CRUDOS ---
cat > "$SHORTCUTS_DIR/LIMPIAR_CRUDOS.sh" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
exec bash "/data/data/com.termux/files/home/agentes/scripts/linux/limpiar_crudos_incompletos_termux.sh"
EOF

chmod +x \
  "$REPO_DIR/scripts/linux/bootstrap_termux_arm64.sh" \
  "$REPO_DIR/scripts/linux/sincronizar_yt_a_fb.sh" \
  "$REPO_DIR/scripts/linux/sincronizar_yt_a_fb_termux.sh" \
  "$REPO_DIR/scripts/linux/vigia_meta.sh" \
  "$REPO_DIR/scripts/linux/vigia_meta_termux.sh" \
  "$REPO_DIR/scripts/linux/vigia_meta_widget.sh" \
  "$REPO_DIR/scripts/linux/pipeline_completo_termux.sh" \
  "$REPO_DIR/scripts/linux/renovar_repo_termux.sh" \
  "$REPO_DIR/scripts/linux/cortar_teasers_termux.sh" \
  "$REPO_DIR/scripts/linux/subir_crudos_yt_termux.sh" \
  "$REPO_DIR/scripts/linux/subir_teasers_termux.sh" \
  "$REPO_DIR/scripts/linux/vigia_facebook_termux.sh" \
  "$REPO_DIR/scripts/linux/limpiar_crudos_incompletos_termux.sh" \
  "$REPO_DIR/scripts/linux/5_BAJAR_YOUTUBE_SIN_LIMITE.sh" \
  "$REPO_DIR/scripts/linux/bajar_youtube_sin_limite_termux.sh" \
  "$BOOT_DIR/start_sshd.sh" \
  "$SHORTCUTS_DIR/Arrancar_SSH.sh" \
  "$SHORTCUTS_DIR/Estado_Remoto.sh" \
  "$SHORTCUTS_DIR/sincronizar_yt_a_fb.sh" \
  "$SHORTCUTS_DIR/vigia_meta.sh" \
  "$SHORTCUTS_DIR/Monitorear_Temperaturas.sh" \
  "$SHORTCUTS_DIR/Monitor_Logs.sh" \
  "$SHORTCUTS_DIR/0_PIPELINE_COMPLETO.sh" \
  "$SHORTCUTS_DIR/0_RENOVAR_REPO.sh" \
  "$SHORTCUTS_DIR/1_CORTAR_TEASERS.sh" \
  "$SHORTCUTS_DIR/2_SUBIR_CRUDOS_YT.sh" \
  "$SHORTCUTS_DIR/3_SUBIR_TEASERS_YT.sh" \
  "$SHORTCUTS_DIR/4_VIGIA_FACEBOOK.sh" \
  "$SHORTCUTS_DIR/5_BAJAR_YOUTUBE_SIN_LIMITE.sh" \
  "$SHORTCUTS_DIR/LIMPIAR_CRUDOS.sh"

mkdir -p "$REPO_DIR/youtube_uploader/downloads" "$REPO_DIR/meta_uploader"

if [ ! -f "$REPO_DIR/youtube_uploader/history.json" ] && [ -f "$REPO_DIR/youtube_uploader/sync_history.json" ]; then
  cp "$REPO_DIR/youtube_uploader/sync_history.json" "$REPO_DIR/youtube_uploader/history.json"
fi

source "$(dirname "$0")/_proot_bind.sh"
"$PROOT" login debian "${PROOT_BIND_ARGS[@]}" -- /bin/sh -lc \
  "mkdir -p /root && ln -sfn /data/data/com.termux/files/home/agentes /root/agentes"

if [ "$INSTALL_DEBIAN_DEPS" = "1" ]; then
  "$PROOT" login debian "${PROOT_BIND_ARGS[@]}" -- /bin/bash -lc '
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 no existe dentro de Debian"
  exit 1
fi

if ! command -v pip3 >/dev/null 2>&1; then
  echo "ERROR: pip3 no existe dentro de Debian"
  exit 1
fi

python3 -m pip install --break-system-packages yt-dlp
python3 -m pip install --break-system-packages \
  -r /root/agentes/youtube_uploader/requirements.txt \
  -r /root/agentes/meta_uploader/requirements.txt
'
fi

echo "Bootstrap Termux ARM64 listo para perfil: $DEVICE_PROFILE"
echo "Repo: $REPO_DIR"
echo "Env: $ENV_FILE"
echo "Install Debian deps: $INSTALL_DEBIAN_DEPS"
