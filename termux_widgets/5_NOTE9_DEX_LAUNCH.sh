#!/data/data/com.termux/files/usr/bin/bash
# 5_NOTE9_DEX_LAUNCH.sh v2.0
# Widget para lanzar scrcpy (Note 9) con auto-descubrimiento de IP

TERMUX_BIN="/data/data/com.termux/files/usr/bin"
export PATH="$TERMUX_BIN:$PATH"
NOTE9_SERIAL="29396e8c1e3f7ece"

echo "Buscando Note 9..."

# 1. Buscar ya conectado (USB o WiFi)
TARGET=$($TERMUX_BIN/adb devices | grep -E "\bdevice$" | grep -E "(29396e8c1e3f7ece|[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:)" | head -1 | awk '{print $1}')

# 2. Si no, probar IPs conocidas y escanear subred
if [ -z "$TARGET" ]; then
    echo "Buscando Note 9 por WiFi..."
    # Obtener subred actual
    GW=$($TERMUX_BIN/ip route | grep default | awk '{print $3}' | head -1)
    SUBNET=$(echo "$GW" | awk -F. '{print $1"."$2"."$3"."}')
    [ -z "$SUBNET" ] && SUBNET="10.134.128."
    
    for IP in "${SUBNET}236" "${SUBNET}81" "${SUBNET}171" "${SUBNET}5"; do
        result=$($TERMUX_BIN/adb connect "$IP:5555" 2>&1)
        if echo "$result" | grep -qi "connected"; then
            TARGET="$IP:5555"
            echo "Conectado en $TARGET"
            break
        fi
    done
fi

# 3. Fallback: escaneo rápido con nmap
if [ -z "$TARGET" ] && command -v nmap >/dev/null; then
    echo "Escaneando puertos ADB..."
    PORTS=$($TERMUX_BIN/nmap -p 5555,36000-46000 --open -T5 "$SUBNET"0/24 2>&1 | grep -E "^[0-9]+/tcp.*open" | head -3 | cut -d'/' -f1)
    for p in $PORTS; do
        result=$($TERMUX_BIN/adb connect "$SUBNET$p:5555" 2>&1)
        if echo "$result" | grep -qi "connected"; then
            TARGET="$SUBNET$p:5555"
            break
        fi
    done
fi

if [ -z "$TARGET" ]; then
    echo "Note 9 no encontrado. Conectalo por USB o verifica WiFi."
    exit 1
fi

echo "Note 9 encontrado: $TARGET"
echo "Lanzando DeX..."

# 4. Obtener display virtual (monitor fantasma)
V_ID=$($TERMUX_BIN/scrcpy -s "$TARGET" --list-displays 2>&1 | grep -oP 'display-id=\K[0-9]+' | tail -1)
[ -z "$V_ID" ] && V_ID=6

# 5. Iniciar DeX
nohup $TERMUX_BIN/scrcpy -s "$TARGET" --display-id="$V_ID" --no-audio -f >/dev/null 2>&1 &
echo "DeX lanzado en display $V_ID"
