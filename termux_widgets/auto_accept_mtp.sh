#!/bin/bash
# auto_accept_mtp.sh
# Script independiente para auto-aceptar el diálogo MTP en Samsung
# Útil cuando conectas el Note 9 al S24 o cualquier otro dispositivo
# Ejecutar desde Termux o PC después de establecer ADB

set -euo pipefail

ADB="${ADB:-adb}"
SERIAL="${1:-}"
TIMEOUT="${2:-30}"
INTERVAL="${3:-2}"

# Detectar dispositivo si no se especificó serial
if [ -z "$SERIAL" ]; then
    # Buscar dispositivos conectados localmente (USB)
    SERIAL=$($ADB devices | awk '/\tdevice$/{print $1; exit}')
fi

if [ -z "$SERIAL" ]; then
    # Intentar conectar a Note 9 por WiFi (IPs conocidas)
    echo "Buscando Note 9 por WiFi..."
    for IP in 10.134.128.236 10.120.132.81 10.61.147.81; do
        result=$($ADB connect "$IP:5555" 2>&1)
        if echo "$result" | grep -qi "connected"; then
            SERIAL="$IP:5555"
            echo "Conectado a Note 9 en $SERIAL"
            break
        fi
    done
fi

if [ -z "$SERIAL" ]; then
    echo "No se detectó ningún dispositivo ADB."
    echo "Uso: $0 [serial] [timeout_segundos] [intervalo_segundos]"
    exit 1
fi

echo "Monitoreando diálogo MTP en dispositivo: $SERIAL"
echo "Timeout: ${TIMEOUT}s | Intervalo: ${INTERVAL}s"
echo "Presiona Ctrl+C para detener."

end=$((SECONDS + TIMEOUT))

while [ $SECONDS -lt $end ]; do
    # Obtener la actividad en primer plano
    top=$($ADB -s "$SERIAL" shell dumpsys window windows 2>/dev/null | grep -i "mtp\|MtpApplication" | head -1)

    if echo "$top" | grep -qi "mtpapplication"; then
        echo "$(date '+%H:%M:%S') - Diálogo MTP detectado, aceptando..."

        # Opción 1: Tap directo en coordenadas del botón Permitir
        $ADB -s "$SERIAL" shell "input tap 520 1300" 2>/dev/null || true
        sleep 1

        # Opción 2: Usar uiautomator como respaldo
        $ADB -s "$SERIAL" shell uiautomator dump /dev/stdout 2>/dev/null | grep -qi "Permitir" && {
            $ADB -s "$SERIAL" shell "input tap 520 1300" 2>/dev/null || true
        }

        echo "$(date '+%H:%M:%S') - Aceptado. Verificando..."
        sleep 2

        # Verificar si el diálogo se cerró
        if ! $ADB -s "$SERIAL" shell dumpsys window windows 2>/dev/null | grep -qi "mtpapplication"; then
            echo "$(date '+%H:%M:%S') - Diálogo cerrado correctamente."
            exit 0
        fi
    fi

    sleep "$INTERVAL"
done

echo "Timeout alcanzado sin detectar diálogo MTP."
exit 1
