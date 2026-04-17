$Host.UI.RawUI.WindowTitle = "Agente Meta (Sube videos a Meta)"

$BASE_DIR = "C:\Users\ZN-\Documents\Antigravity\agentes"
$VENV_PYTHON = "C:\Users\ZN-\Documents\Antigravity\.venv\Scripts\python.exe"
$TARGET_DIR = "C:\Users\ZN-\Documents\ADM\Carpeta 1\videos subidos exitosamente"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " INICIANDO AGENTE DIARIO: SUBE VIDEOS A META " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

Set-Location $BASE_DIR

Write-Host "Paso 1: Reconciliando (Limpiando duplicados alojados en la nube)..." -ForegroundColor Yellow
& $VENV_PYTHON "meta_uploader\reconcile_meta_cloud.py"

Write-Host "Paso 2: Clasificando nuevos videos (Directorio Externo de ADM)..." -ForegroundColor Yellow
& $VENV_PYTHON "meta_uploader\classify_meta_videos.py" $TARGET_DIR

Write-Host "Paso 3: Lanzando Motor de Cascada Infinito (07:00 / 18:30) [PW]..." -ForegroundColor Cyan
$env:META_ENABLE_UPLOAD=1
& $VENV_PYTHON "meta_uploader\run_jornada1_supervisor.py" --days 28 --max-live-days 28 --rebuild-plan --restart-delay-seconds 10 --max-restarts 9999
