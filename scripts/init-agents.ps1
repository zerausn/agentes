# Script de inicializacion del sistema de agentes
# Ejecutar: .\init-agents.ps1

# Configuracion
$REPO_PATH = "$env:USERPROFILE\Documents\antigravity"
$AGENTES_PATH = "$REPO_PATH\agentes"
$HISTORIAL_PATH = "$AGENTES_PATH\historial"
$CONFIGS_PATH = "$AGENTES_PATH\configs"

Write-Host "=== INICIALIZANDO SISTEMA DE AGENTES ===" -ForegroundColor Cyan

# 1. Verificar estructura de carpetas
Write-Host "`n[1] Creando estructura de carpetas..." -ForegroundColor Yellow

$carpetas = @(
    "$HISTORIAL_PATH\sesiones",
    "$HISTORIAL_PATH\decisiones",
    "$HISTORIAL_PATH\ejecuciones",
    "$HISTORIAL_PATH\logs"
)

foreach ($carpeta in $carpetas) {
    if (Test-Path $carpeta) {
        Write-Host "  OK $carpeta existe" -ForegroundColor Green
    }
    else {
        New-Item -ItemType Directory -Path $carpeta -Force | Out-Null
        Write-Host "  OK $carpeta creada" -ForegroundColor Green
    }
}

# 2. Crear archivo de estado compartido
Write-Host "`n[2] Inicializando estado compartido..." -ForegroundColor Yellow

$estado_inicial = @{
    sesion_id = "init-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    estado = "inicializado"
    timestamp = (Get-Date -AsUTC).ToString('o')
    agentes = @{
        coordinador = @{ status = "ready"; timestamp = $null }
        documentador = @{ status = "ready"; timestamp = $null }
        revisor = @{ status = "ready"; timestamp = $null }
        qa = @{ status = "ready"; timestamp = $null }
        github = @{ status = "ready"; timestamp = $null }
    }
} | ConvertTo-Json -Depth 5

$estado_inicial | Out-File "$HISTORIAL_PATH\estado-actual.json" -Encoding UTF8
Write-Host "  OK archivo de estado creado" -ForegroundColor Green

# 3. Crear archivo de log inicial
Write-Host "`n[3] Inicializando logs..." -ForegroundColor Yellow

$fecha = Get-Date -Format 'yyyyMMdd'
$log_inicial = @"
=== LOG DE INICIALIZACION ===
Fecha: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Ruta: $REPO_PATH
Estado: INICIALIZADO

Carpetas creadas:
- $HISTORIAL_PATH\sesiones
- $HISTORIAL_PATH\decisiones
- $HISTORIAL_PATH\ejecuciones
- $HISTORIAL_PATH\logs

Archivos creados:
- estado-actual.json
- $fecha-sistema.log (este archivo)

Proximas acciones:
1. Revisar PROPUESTA_SISTEMA_AGENTES_COORDINADOS.md
2. Completar checklist de configuracion
3. Ajustar timeouts y parametros
4. Implementar seguridad (credenciales, RBAC)
5. Agregar tests de coordinacion
"@

$log_inicial | Out-File "$HISTORIAL_PATH\logs\$fecha-sistema.log" -Encoding UTF8
Write-Host "  OK logs inicializados" -ForegroundColor Green

# 4. Verificar Git
Write-Host "`n[4] Verificando configuracion de Git..." -ForegroundColor Yellow

$cwd = Get-Location
Set-Location $REPO_PATH

$git_user = git config --local user.name
$git_email = git config --local user.email

if ($git_user -and $git_email) {
    Write-Host ("  OK Git configurado: {0} <{1}>" -f $git_user, $git_email) -ForegroundColor Green
}
else {
    Write-Host "  WARN Git no configurado completamente" -ForegroundColor Yellow
    Write-Host "  Ejecuta:" -ForegroundColor Yellow
    Write-Host "    git config --local user.name 'Tu Nombre'" -ForegroundColor Gray
    Write-Host "    git config --local user.email 'tu@email.com'" -ForegroundColor Gray
}

Set-Location $cwd

# 5. Resumen
Write-Host "`n=== RESUMEN ===" -ForegroundColor Cyan
Write-Host "OK Sistema de Agentes inicializado correctamente" -ForegroundColor Green
Write-Host ""
Write-Host "Estructura creada en: $AGENTES_PATH" -ForegroundColor Cyan
Write-Host "Propuesta revisor: $AGENTES_PATH\PROPUESTA_SISTEMA_AGENTES_COORDINADOS.md" -ForegroundColor Cyan
Write-Host "Checklist: $AGENTES_PATH\CHECKLIST_REVISION.md" -ForegroundColor Cyan
Write-Host ""
Write-Host "PROXIMO PASO:" -ForegroundColor Yellow
Write-Host "1. Abre PROPUESTA_SISTEMA_AGENTES_COORDINADOS.md" -ForegroundColor Gray
Write-Host "2. Envia a agente revisor para validacion" -ForegroundColor Gray
Write-Host "3. Implementa las mejoras sugeridas" -ForegroundColor Gray
Write-Host ""
