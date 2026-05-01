$Host.UI.RawUI.WindowTitle = "Agente YouTube (Sube videos a YT)"

$BASE_DIR = "C:\Users\ZN-\Documents\Antigravity\agentes"
$VENV_PYTHON = "C:\Users\ZN-\Documents\Antigravity\.venv\Scripts\python.exe"

Write-Host "==========================================================" -ForegroundColor Red
Write-Host " INICIANDO AGENTE DIARIO: SUBE VIDEOS A YOUTUBE " -ForegroundColor Red
Write-Host "==========================================================" -ForegroundColor Red

Set-Location $BASE_DIR

while ($true) {
    $currentTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "`n[$currentTime] --- INICIANDO NUEVO CICLO DIARIO (YOUTUBE) ---" -ForegroundColor Green

    Write-Host "Paso 1: Limpiando tu carpeta externa (Moviendo videos ya subidos)..." -ForegroundColor Yellow
    & $VENV_PYTHON "youtube_uploader\periodic_mover.py" --run-once

    Write-Host "Paso 1.5: Purgando memoria vieja para garantizar escaneo limpio y orden por peso..." -ForegroundColor Yellow
    Remove-Item -Path "youtube_uploader\scanned_videos.json" -ErrorAction SilentlyContinue

    Write-Host "Paso 2: Escaneando en busca de nuevos videos..." -ForegroundColor Yellow
    & $VENV_PYTHON "youtube_uploader\video_scanner.py"

    Write-Host "Paso 3: Lanzando el archivo que sube videos a YouTube (Borradores)..." -ForegroundColor Yellow
    & $VENV_PYTHON "youtube_uploader\uploader.py"

    Write-Host "Paso 4: Recreando el calendario de YouTube para shorts y para videos..." -ForegroundColor Yellow
    & $VENV_PYTHON "youtube_uploader\schedule_drafts.py"

    $currentTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "`n[$currentTime] --- CICLO TERMINADO: ESPERANDO 24 HORAS PARA BUSCAR MAS VIDEOS ---" -ForegroundColor Green
    
    # 86400 segundos = 24 horas
    Start-Sleep -Seconds 86400
}
