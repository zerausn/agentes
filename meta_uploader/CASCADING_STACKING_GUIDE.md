# Cascading Stacking Engine v6 (Meta Uploader)

## Visión General
El motor v6 transforma el uploader secuencial tradicional en un sistema de **Matrix Publishing**. En lugar de publicar un solo video por día, el motor realiza barridos (sweeps) sobre la ventana de programación permitida por Meta (28 días) para inyectar contenido en múltiples ráfagas diarias.

## Algoritmo: Barrido Geométrico (Sweep Stacking)
El motor no intenta llenar el calendario linealmente. En su lugar, usa un generador de slots en cascada:

1. **Sweep 1**: Recorre los días 0 al 27 asignando el primer "Golden Slot" (7:00 AM) a cada video disponible.
2. **Sweep 2**: Recorre los días 0 al 27 asignando el segundo "Golden Slot" (6:30 PM).
3. **Persistencia**: Si hay más de 56 videos (2 slots * 28 días), el sistema continúa apilando o espera a que la ventana de Meta se desplace para inyectar más.

## Slots de Oro (Monetización PW)
Hemos fijado dos horarios estratégicos basados en picos de audiencia y retención:
- **07:00:00**: Pico matutino (Global).
- **18:30:00**: Pico tarde/noche (América/Europa).

## Componentes del Sistema

### 1. Supervisor Infinito (`run_jornada1_supervisor.py`)
- Monitorea el calendario (`meta_calendar.json`) cada 10 segundos.
- Si detecta que los slots del día actual están completos, o que el calendario está vacío, dispara una reconstrucción del plan para capturar nuevos videos de la carpeta de ADM.
- Argumentos clave: `--days 28 --max-live-days 28 --rebuild-plan`.

### 2. Runner Dinámico (`run_jornada1_normal.py`)
- Ejecuta las subidas reales integrando Facebook Posts e Instagram Reels.
- Incluye un **Watchdog** de transferencia para detectar y recuperar ráfagas de red detenidas.

## Integración con el Escritorio
El lanzador `Iniciar Agentes Meta y YouTube.bat` (vía `START_AGENT_META.ps1`) actúa como el disparador único que inicializa el entorno, realiza la clasificación de archivos y cede el control al supervisor de cascada.
