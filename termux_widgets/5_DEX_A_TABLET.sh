#!/bin/bash
echo "============================================="
echo "   S24 ULTRA: MODO ENGAÑO DEX A TABLET"
echo "============================================="

echo "[1/3] Configurando Engaño (Fuerza Escritorio)..."
adb shell settings put global force_desktop_mode_on_external_displays 1

echo "[2/3] Despertando Receptor en la Tablet..."
# Intentamos despertar el modo receptor de la tablet vía IP
adb -s 192.168.0.11:5555 shell am broadcast -a com.samsung.android.smartmirroring.action.SECOND_SCREEN

echo "[3/3] Abriendo Smart View en S24 Ultra..."
am start -n com.samsung.android.smartmirroring/.settings.SettingsActivity

echo "---------------------------------------------"
echo "¡LISTO! Selecciona tu Tablet en la lista que ves."
echo "Si no aparece, revisa que la Tablet esté en el mismo WiFi."
echo "---------------------------------------------"
