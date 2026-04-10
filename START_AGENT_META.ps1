$Host.UI.RawUI.WindowTitle = "Agente Meta (Sube videos a Meta)"

$BASE_DIR = "C:\Users\ZN-\Documents\Antigravity\agentes"
$VENV_PYTHON = "C:\Users\ZN-\Documents\Antigravity\.venv\Scripts\python.exe"
$TARGET_DIR = "C:\Users\ZN-\Documents\ADM\Carpeta 1\videos subidos exitosamente"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " INICIANDO AGENTE DIARIO: SUBE VIDEOS A META " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

Set-Location $BASE_DIR

while ($true) {
    $currentTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "`n[$currentTime] --- INICIANDO NUEVO CICLO DIARIO ---" -ForegroundColor Green

    Write-Host "Paso 1: Reconciliando (Limpiando duplicados alojados en la nube)..." -ForegroundColor Yellow
    & $VENV_PYTHON "meta_uploader\reconcile_meta_cloud.py"

    Write-Host "Paso 2: Clasificando nuevos videos (Directorio Externo de ADM)..." -ForegroundColor Yellow
    & $VENV_PYTHON "meta_uploader\classify_meta_videos.py" $TARGET_DIR

    Write-Host "Paso 3: Re-generando calendario de 400 dias..." -ForegroundColor Yellow
    & $VENV_PYTHON "meta_uploader\meta_calendar_generator.py"

    Write-Host "Paso 4: Lanzando Supervisor de Subida a Meta..." -ForegroundColor Yellow
    & $VENV_PYTHON "meta_uploader\schedule_jornada1_supervisor.py" --days 400

    $currentTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "`n[$currentTime] --- CICLO TERMINADO: ESPERANDO 24 HORAS PARA BUSCAR MAS VIDEOS ---" -ForegroundColor Green
    
    # 86400 segundos = 24 horas
    Start-Sleep -Seconds 86400
}
