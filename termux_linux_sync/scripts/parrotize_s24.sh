#!/bin/bash
echo "[PARROT] Iniciando transformación de Debian..."
export DEBIAN_FRONTEND=noninteractive
apt update && apt install -y gnupg wget curl
# Añadir repo Parrot LTS (para Debian Trixie/Testing)
wget -qO - https://deb.parrot.sh/parrot/keyring.gpg | gpg --dearmor -o /etc/apt/trusted.gpg.d/parrot.gpg
echo "deb https://deb.parrot.sh/parrot/ rolling main contrib non-free" > /etc/apt/sources.list.d/parrot.list
apt update
echo "[PARROT] Instalando núcleo Parrot (core y herramientas base)..."
apt install -y parrot-core parrot-menu mate-desktop-environment
echo "[PARROT] Transformación completada."
