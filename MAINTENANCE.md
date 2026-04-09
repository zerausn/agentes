# Guía de Mantenimiento Maestro: Antigravity Video Pipelines

Esta guía centraliza el conocimiento operativo para mantener el sistema de subida automatizada (YouTube & Meta) funcionando al 100%.

## 🏗️ Arquitectura del Sistema

El sistema se compone de tres pilares que deben correr de forma independiente:
1. **YouTube Uploader (`uploader.py`)**: Gestiona la cola de YouTube.
2. **Meta Uploader (`schedule_jornada1_supervisor.py`)**: Gestiona el calendario de 400 días con reintentos automáticos para Facebook e Instagram.
3. **Conserje Automático (`periodic_mover.py`)**: Limpia archivos bloqueados y organiza los videos finalizados cada 10 minutos.

---

## 🕒 Estrategia de Monetización Global

Se han configurado horarios específicos para capturar el pico de audiencia en Estados Unidos y Europa:
*   **YouTube**: **14:00 (Hora Colombia)**. Ideal para capturar el almuerzo en USA y el "Prime Time" en Europa.
*   **Meta**: **18:30 (Hora Colombia)**. Optimizado para CPM alto en las Américas.

---

## 🛠️ Operaciones Comunes

### Cómo Reiniciar el Sistema (Reseteo Maestro)
Si el monitor marca "INACTIVO" o hay errores de "File Locked", ejecuta este comando en PowerShell:
```powershell
# Detiene todo y reinicia una sola instancia limpia
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force; 
Start-Process python -ArgumentList "uploader.py" -WorkingDirectory "C:\Users\ZN-\Documents\Antigravity\agentes\youtube_uploader" -WindowStyle Hidden; 
Start-Process "C:\Users\ZN-\Documents\Antigravity\.venv\Scripts\python.exe" -ArgumentList "C:\Users\ZN-\Documents\Antigravity\agentes\meta_uploader\schedule_jornada1_supervisor.py", "--days", "400" -WorkingDirectory "C:\Users\ZN-\Documents\Antigravity\agentes\meta_uploader" -WindowStyle Hidden; 
Start-Process python -ArgumentList "periodic_mover.py" -WorkingDirectory "C:\Users\ZN-\Documents\Antigravity\agentes\youtube_uploader" -WindowStyle Hidden
```

---

## 🚨 Resolución de Problemas (Troubleshooting)

### 1. YouTube: "Límite de subidas alcanzado"
*   **Síntoma**: El log dice `uploadLimitExceeded`.
*   **Causa**: Has alcanzado el límite diario del canal (ej. 44 videos hoy).
*   **Solución**: No hay arreglo técnico; es un límite de YouTube. El sistema debe descansar 24 horas. 
*   **Tip**: Ejecuta `python schedule_drafts.py` para organizar los videos que ya se subieron.

### 2. Meta: "Inactivo" por Seguridad
*   **Síntoma**: El monitor dice INACTIVO y el log pide `META_ENABLE_UPLOAD=1`.
*   **Solución**: Asegúrate de que el archivo `meta_uploader/.env` tenga la línea `META_ENABLE_UPLOAD=1`. El código ya ha sido parcheado para leer este archivo automáticamente.

### 3. Error WinError 32 (Archivo en uso)
*   **Causa**: Dos procesos intentan mover el mismo video al mismo tiempo.
*   **Solución**: El "Conserje" (`periodic_mover.py`) lo resolverá solo en su siguiente ciclo. No intervengas manualmente a menos que el error persista por más de 1 hora.

---

## 🔐 Seguridad y Configuración
*   **Archivo `.env`**: Contiene los tokens de acceso. **NUNCA** los compartas ni los subas a repositorios públicos.
*   **Calendario**: El archivo `meta_calendar.json` es el cerebro de Meta. Si lo borras, el sistema perderá el rastro de qué videos ya se subieron.
