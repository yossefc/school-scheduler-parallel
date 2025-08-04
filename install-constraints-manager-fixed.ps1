# ================================================================
# Script d'installation du Gestionnaire de Contraintes - VERSION CORRIGEE
# ================================================================

param(
    [switch]$Install,
    [switch]$Start,
    [switch]$Reset,
    [switch]$Status,
    [switch]$Clean,
    [string]$DatabasePath = "school_scheduler"
)

# Configuration
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$PROJECT_ROOT = $SCRIPT_DIR
$API_PORT = 5001
$WEB_PORT = 3001

function Write-Banner {
    Write-Host ""
    Write-Host "🎯 ============================================= 🎯" -ForegroundColor Cyan
    Write-Host "   GESTIONNAIRE DE CONTRAINTES - SCHOOL SCHEDULER" -ForegroundColor Yellow
    Write-Host "🎯 ============================================= 🎯" -ForegroundColor Cyan
    Write-Host ""
}

function Test-Prerequisites {
    Write-Host "🔍 Verification des prerequis..." -ForegroundColor Yellow
    
    $missing = @()
    
    # Python
    try {
        $pythonVersion = python --version 2>$null
        if ($pythonVersion -match "Python (\d+)\.(\d+)") {
            $major = [int]$matches[1]
            $minor = [int]$matches[2]
            if ($major -ge 3 -and $minor -ge 8) {
                Write-Host "✅ Python $pythonVersion" -ForegroundColor Green
            } else {
                $missing += "Python 3.8+ (trouve: $pythonVersion)"
            }
        } else {
            $missing += "Python 3.8+"
        }
    } catch {
        $missing += "Python 3.8+"
    }
    
    # PostgreSQL
    try {
        $pgVersion = psql --version 2>$null
        if ($pgVersion) {
            Write-Host "✅ PostgreSQL detecte" -ForegroundColor Green
        } else {
            $missing += "PostgreSQL"
        }
    } catch {
        Write-Host "⚠️ PostgreSQL non detecte (peut etre sur Docker)" -ForegroundColor Yellow
    }
    
    if ($missing.Count -gt 0) {
        Write-Host "❌ Prerequis manquants:" -ForegroundColor Red
        $missing | ForEach-Object { Write-Host "   - $_" -ForegroundColor Red }
        return $false
    }
    
    Write-Host "✅ Tous les prerequis sont satisfaits!" -ForegroundColor Green
    return $true
}

function Install-System {
    Write-Host "📦 Installation du systeme..." -ForegroundColor Yellow
    
    # Creer les repertoires necessaires
    $dirs = @("scheduler_ai", "database", "logs")
    foreach ($dir in $dirs) {
        if (!(Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
            Write-Host "📁 Cree: $dir" -ForegroundColor Green
        }
    }
    
    # Verifier si frontend/public existe
    if (Test-Path "frontend/public") {
        Write-Host "✅ Structure frontend detectee!" -ForegroundColor Green
    } else {
        Write-Host "⚠️ Dossier frontend/public non trouve - creation..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Path "frontend/public" -Force | Out-Null
    }
    
    Write-Host "📄 Fichiers a copier manuellement:" -ForegroundColor Yellow
    Write-Host "   1. constraints_manager.html -> frontend/public/" -ForegroundColor Cyan
    Write-Host "   2. constraints_management_api.py -> scheduler_ai/" -ForegroundColor Cyan
    Write-Host "   3. reset_all_constraints.sql -> database/" -ForegroundColor Cyan
    
    # Installer les dependances Python minimales
    Write-Host "📦 Installation des dependances Python..." -ForegroundColor Yellow
    try {
        pip install flask flask-cors psycopg2-binary requests
        Write-Host "✅ Dependances installees" -ForegroundColor Green
    } catch {
        Write-Host "⚠️ Erreur installation Python - installez manuellement:" -ForegroundColor Yellow
        Write-Host "   pip install flask flask-cors psycopg2-binary" -ForegroundColor Cyan
    }
    
    Write-Host "🎉 Installation terminee!" -ForegroundColor Green
}

function Reset-Database {
    Write-Host "🧹 Nettoyage de la base de donnees..." -ForegroundColor Yellow
    
    $confirmation = Read-Host "⚠️ ATTENTION: Cela va supprimer TOUTES les contraintes. Continuer? (oui/non)"
    if ($confirmation -ne "oui") {
        Write-Host "❌ Operation annulee" -ForegroundColor Red
        return
    }
    
    # Executer le script SQL de reset
    if (Test-Path "database/reset_all_constraints.sql") {
        try {
            if ($env:DATABASE_URL) {
                psql $env:DATABASE_URL -f "database/reset_all_constraints.sql"
            } else {
                psql -d $DatabasePath -f "database/reset_all_constraints.sql"
            }
            Write-Host "✅ Base de donnees nettoyee!" -ForegroundColor Green
        } catch {
            Write-Host "❌ Erreur lors du nettoyage: $_" -ForegroundColor Red
            Write-Host "💡 Essayez de lancer le script SQL manuellement" -ForegroundColor Yellow
        }
    } else {
        Write-Host "❌ Script SQL non trouve dans database/" -ForegroundColor Red
        Write-Host "💡 Copiez reset_all_constraints.sql dans le dossier database/" -ForegroundColor Yellow
    }
}

function Start-Services {
    Write-Host "🚀 Demarrage des services..." -ForegroundColor Yellow
    
    # Verifier que les fichiers existent
    if (!(Test-Path "scheduler_ai/constraints_management_api.py")) {
        Write-Host "❌ API non trouvee. Copiez constraints_management_api.py dans scheduler_ai/" -ForegroundColor Red
        return
    }
    
    if (!(Test-Path "frontend/public/constraints_manager.html")) {
        Write-Host "❌ Interface non trouvee. Copiez constraints_manager.html dans frontend/public/" -ForegroundColor Red
        return
    }
    
    # Demarrer l'API Flask
    Write-Host "🔧 Demarrage de l'API sur le port $API_PORT..." -ForegroundColor Yellow
    
    $apiJob = Start-Job -ScriptBlock {
        param($apiPort, $projectRoot)
        cd $projectRoot
        python "scheduler_ai/constraints_management_api.py"
    } -ArgumentList $API_PORT, $PROJECT_ROOT
    
    Start-Sleep 3
    
    # Tester l'API
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$API_PORT/api/constraints/list" -TimeoutSec 5 -ErrorAction Stop
        Write-Host "✅ API demarree avec succes!" -ForegroundColor Green
    } catch {
        Write-Host "⚠️ API en cours de demarrage..." -ForegroundColor Yellow
    }
    
    # Serveur web pour l'interface
    Write-Host "🌐 Demarrage du serveur web sur le port $WEB_PORT..." -ForegroundColor Yellow
    
    $webJob = Start-Job -ScriptBlock {
        param($port, $webDir)
        cd $webDir
        python -m http.server $port
    } -ArgumentList $WEB_PORT, "$PROJECT_ROOT/frontend/public"
    
    Start-Sleep 2
    Write-Host "✅ Serveur web demarre!" -ForegroundColor Green
    
    # Afficher les URLs
    Write-Host ""
    Write-Host "📋 SERVICES ACTIFS:" -ForegroundColor Cyan
    Write-Host "   🎯 Interface Web: http://localhost:$WEB_PORT/constraints_manager.html" -ForegroundColor Green
    Write-Host "   🔧 API Backend:   http://localhost:$API_PORT/api/constraints/list" -ForegroundColor Green
    Write-Host ""
    Write-Host "💡 Pour arreter les services: Get-Job | Stop-Job" -ForegroundColor Yellow
    
    # Ouvrir le navigateur
    $openBrowser = Read-Host "🌐 Ouvrir l'interface dans le navigateur? (oui/non)"
    if ($openBrowser -eq "oui") {
        Start-Process "http://localhost:$WEB_PORT/constraints_manager.html"
    }
}

function Show-Status {
    Write-Host "📊 Etat du systeme:" -ForegroundColor Cyan
    
    # Verifier les jobs en cours
    $jobs = Get-Job
    if ($jobs) {
        Write-Host "🔧 Services en cours d'execution:" -ForegroundColor Yellow
        $jobs | ForEach-Object {
            $status = if ($_.State -eq "Running") { "✅" } else { "❌" }
            Write-Host "   $status $($_.Name) - $($_.State)"
        }
    } else {
        Write-Host "⚠️ Aucun service en cours d'execution" -ForegroundColor Yellow
    }
    
    # Tester les connexions
    Write-Host ""
    Write-Host "🌐 Test des connexions:" -ForegroundColor Yellow
    
    # API
    try {
        $apiResponse = Invoke-WebRequest -Uri "http://localhost:$API_PORT/api/constraints/list" -TimeoutSec 3 -ErrorAction Stop
        Write-Host "   ✅ API (port $API_PORT) - OK" -ForegroundColor Green
    } catch {
        Write-Host "   ❌ API (port $API_PORT) - Inaccessible" -ForegroundColor Red
    }
    
    # Interface web
    try {
        $webResponse = Invoke-WebRequest -Uri "http://localhost:$WEB_PORT" -TimeoutSec 3 -ErrorAction Stop
        Write-Host "   ✅ Interface Web (port $WEB_PORT) - OK" -ForegroundColor Green
    } catch {
        Write-Host "   ❌ Interface Web (port $WEB_PORT) - Inaccessible" -ForegroundColor Red
    }
    
    # Base de donnees
    try {
        if ($env:DATABASE_URL) {
            $dbTest = psql $env:DATABASE_URL -c "SELECT COUNT(*) FROM constraints;" 2>$null
        } else {
            $dbTest = psql -d $DatabasePath -c "SELECT COUNT(*) FROM constraints;" 2>$null
        }
        
        if ($dbTest) {
            Write-Host "   ✅ Base de donnees - OK" -ForegroundColor Green
        } else {
            Write-Host "   ❌ Base de donnees - Inaccessible" -ForegroundColor Red
        }
    } catch {
        Write-Host "   ❌ Base de donnees - Erreur de connexion" -ForegroundColor Red
    }
}

function Clean-System {
    Write-Host "🧹 Nettoyage du systeme..." -ForegroundColor Yellow
    
    # Arreter les services
    Get-Job | Stop-Job
    Get-Job | Remove-Job
    
    # Nettoyer les logs
    if (Test-Path "logs") {
        Remove-Item "logs/*.log" -Force -ErrorAction SilentlyContinue
        Write-Host "✅ Logs nettoyes" -ForegroundColor Green
    }
    
    # Nettoyer les fichiers temporaires
    Remove-Item "*.pyc" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item "__pycache__" -Recurse -Force -ErrorAction SilentlyContinue
    
    Write-Host "✅ Nettoyage termine!" -ForegroundColor Green
}

function Show-Help {
    Write-Host "📖 UTILISATION:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  .\install-constraints-manager-fixed.ps1 -Install    # Installation complete" -ForegroundColor Yellow
    Write-Host "  .\install-constraints-manager-fixed.ps1 -Start      # Demarrer les services" -ForegroundColor Yellow
    Write-Host "  .\install-constraints-manager-fixed.ps1 -Status     # Voir l'etat du systeme" -ForegroundColor Yellow
    Write-Host "  .\install-constraints-manager-fixed.ps1 -Reset      # Nettoyer la base de donnees" -ForegroundColor Yellow
    Write-Host "  .\install-constraints-manager-fixed.ps1 -Clean      # Nettoyer les fichiers temporaires" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "📋 WORKFLOW RECOMMANDE:" -ForegroundColor Cyan
    Write-Host "  1. Copier les 3 fichiers dans les bons dossiers" -ForegroundColor Green
    Write-Host "  2. .\install-constraints-manager-fixed.ps1 -Install" -ForegroundColor Green
    Write-Host "  3. .\install-constraints-manager-fixed.ps1 -Reset" -ForegroundColor Green
    Write-Host "  4. .\install-constraints-manager-fixed.ps1 -Start" -ForegroundColor Green
    Write-Host "  5. Ouvrir http://localhost:3001/constraints_manager.html" -ForegroundColor Green
    Write-Host ""
    Write-Host "📁 FICHIERS A COPIER:" -ForegroundColor Yellow
    Write-Host "   constraints_manager.html -> frontend/public/" -ForegroundColor Cyan
    Write-Host "   constraints_management_api.py -> scheduler_ai/" -ForegroundColor Cyan
    Write-Host "   reset_all_constraints.sql -> database/" -ForegroundColor Cyan
}

# ================================================================
# EXECUTION PRINCIPALE
# ================================================================

Write-Banner

if (-not $Install -and -not $Start -and -not $Reset -and -not $Status -and -not $Clean) {
    Show-Help
    exit
}

if (-not (Test-Prerequisites)) {
    exit 1
}

if ($Install) {
    Install-System
}

if ($Reset) {
    Reset-Database
}

if ($Start) {
    Start-Services
}

if ($Status) {
    Show-Status
}

if ($Clean) {
    Clean-System
}

Write-Host ""
Write-Host "🎉 Operation terminee!" -ForegroundColor Green
Write-Host "💡 Utilisez -Status pour voir l'etat du systeme" -ForegroundColor Yellow
Write-Host ""