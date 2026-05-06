# Ecosistema Linux-ARM64 (Termux/Proot)
Este módulo contiene la configuración optimizada para entornos de escritorio Debian y Parrot OS en dispositivos ARM64 (Samsung S24 Ultra y Tab A9+).

## Componentes
- **scripts/**: Lanzadores maestros con fix de DBus, SHM y Cursor.
- **docs/**: Plan de implementación y guía de estabilización técnica.

## Mejoras Implementadas
- Aceleración GPU via Zink/Turnip.
- Gestión de bus de sesión con `dbus-run-session`.
- Saneamiento de librerías para evitar conflictos ELF.
- Desactivación de bloqueo automático de pantalla.
