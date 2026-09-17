#!/bin/bash
# reparar_adb_vivo.sh — Repara ADB del Vivo V2058 tras apagado/reinicio
# Repo: agentes/scripts/linux/reparar_adb_vivo.sh (rama linux)
# Desktop mirror: ~/Desktop/vivo/Reparar_ADB_Vivo.sh
# Uso: bash ~/Desktop/vivo/Reparar_ADB_Vivo.sh  (o doble clic) | bash agentes/scripts/linux/reparar_adb_vivo.sh
# Requiere: Vivo V2058 conectado por USB (SERIAL=34237840310037S), adb 34.0.5+ en PC
# Doc: MOBILE_MIGRATION.md#3-primer-enganche-por-adb + docs/DECISIONS.md#2026-09-16
set -euo pipefail

SERIAL="34237840310037S"
LOOPBACK="127.0.0.1:5555"
GREEN='\033[0;32m'; YEL='\033[0;33m'; RED='\033[0;31m'; NC='\033[0m'

info()  { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YEL}[AVISO]${NC} $*"; }
fail()  { echo -e "${RED}[ERROR]${NC} $*"; }

echo "=============================================="
echo "  Reparar ADB Vivo V2058 — $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="
echo ""

# 1. Verificar USB
if ! adb devices -l 2>&1 | grep -q "$SERIAL.*device"; then
  fail "Vivo no detectado por USB ($SERIAL)."
  echo "  Conecta el cable USB y autoriza depuración si pide permiso."
  adb devices -l
  exit 1
fi
info "Vivo detectado por USB: $SERIAL"

# 2. Activar adbd TCP (se borra en cada apagado)
echo ""
echo "[1/3] Activando adbd TCP en 5555..."
if adb -s "$SERIAL" tcpip 5555 2>&1 | grep -q "restarting in TCP mode"; then
  info "tcpip 5555 enviado"
else
  warn "tcpip respuesta inesperada, continúo..."
  adb -s "$SERIAL" tcpip 5555 2>&1 || true
fi
sleep 3
PORT=$(adb -s "$SERIAL" shell getprop service.adb.tcp.port 2>&1 | tr -d '\r')
if [ "$PORT" = "5555" ]; then info "service.adb.tcp.port=5555"; else warn "port=$PORT (esperado 5555)"; fi

# 3. Conectar loopback interno (Termux necesita TMPDIR/PREFIX)
echo ""
echo "[2/3] Conectando loopback interno 127.0.0.1:5555..."
adb -s "$SERIAL" shell "run-as com.termux sh -c 'export PREFIX=/data/data/com.termux/files/usr; export TMPDIR=\$PREFIX/tmp; export HOME=/data/data/com.termux/files/home; export PATH=/system/bin:/system/xbin:\$PREFIX/bin; mkdir -p \$TMPDIR; adb connect $LOOPBACK 2>&1'" 2>&1 | sed 's/^/  /'
sleep 2

# 4. Verificar
echo ""
echo "[3/3] Verificando..."
DEVICES=$(adb -s "$SERIAL" shell "run-as com.termux sh -c 'export PREFIX=/data/data/com.termux/files/usr; export TMPDIR=\$PREFIX/tmp; export PATH=/system/bin:/system/xbin:\$PREFIX/bin; adb devices 2>&1'" 2>&1)
echo "$DEVICES" | sed 's/^/  /'
if echo "$DEVICES" | grep -q "127.0.0.1:5555.*device"; then
  info "Loopback conectado: 127.0.0.1:5555 device"
else
  fail "Loopback NO aparece. Reintenta o revisa cable."
  exit 1
fi

ADB_OK=$(adb -s "$SERIAL" shell "run-as com.termux sh -c 'export PREFIX=/data/data/com.termux/files/usr; export TMPDIR=\$PREFIX/tmp; export PATH=/system/bin:/system/xbin:\$PREFIX/bin; adb -s $LOOPBACK shell echo ADB_OK 2>&1'" 2>&1 | tr -d '\r')
if echo "$ADB_OK" | grep -q "ADB_OK"; then info "Shell loopback OK (ADB_OK)"; else warn "Shell loopback no respondió ADB_OK: $ADB_OK"; fi

WM=$(adb -s "$SERIAL" shell "run-as com.termux sh -c 'export PREFIX=/data/data/com.termux/files/usr; export TMPDIR=\$PREFIX/tmp; export PATH=/system/bin:/system/xbin:\$PREFIX/bin; adb -s $LOOPBACK shell \"wm size 2>&1\" 2>&1'" 2>&1 | grep -i "Physical size" | tr -d '\r')
[ -n "$WM" ] && info "$WM" || warn "No se pudo leer wm size"

# Estado vigía
echo ""
echo "--- Estado vigía TikTok ---"
adb -s "$SERIAL" shell "ps -A 2>&1 | grep -i tiktok | head -n 5; echo ---TERMUX---; run-as com.termux sh -c 'ps -ef 2>&1 | grep -E \"vigia|tiktok\" | grep -v grep' 2>&1 | head -n 5" 2>&1 | sed 's/^/  /'
PEND=$(adb -s "$SERIAL" shell "ls '/sdcard/Antigravity/subidos a tiktok/' 2>&1 | wc -l" 2>&1 | tr -d '\r')
echo "  Pendientes /sdcard/Antigravity/subidos a tiktok/: $PEND"
adb -s "$SERIAL" shell "tail -n 8 /sdcard/Antigravity/widget_logs/6_SUBIR_TIKTOK_SHIRABYOSHI_180.log 2>&1 | tail -n 8" 2>&1 | sed 's/^/  /'

echo ""
echo "=============================================="
info "ADB reparado. Si el vigía está muerto (ps vacío),"
echo "  relánzalo desde el widget: 6_SUBIR_TIKTOK_SHIRABYOSHI_180"
echo "=============================================="
