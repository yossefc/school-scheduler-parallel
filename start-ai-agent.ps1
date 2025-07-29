# start-ai-agent.ps1 - Démarrage de l'agent IA pour School Scheduler

param(
    [switch]$Build,
    [switch]$Init,
    [switch]$Monitoring,
    [switch]$Detached
)

Write-Host @"
╔══════════════════════════════════════════════════════════╗
║           🤖 SCHOOL SCHEDULER AI AGENT 🤖                ║
║                                                          ║
║  Assistant IA pour la gestion d'emplois du temps         ║
╚══════════════════════════════════════════════════════════╝
"@ -ForegroundColor Cyan

# Vérifier les prérequis
Write-Host "`n📋 Vérification des prérequis..." -ForegroundColor Yellow

# Docker
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker n'est pas installé!" -ForegroundColor Red
    Write-Host "Veuillez installer Docker Desktop: https://www.docker.com/products/docker-desktop" -ForegroundColor Gray
    exit 1
}

# Docker Compose
if (!(Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker Compose n'est pas installé!" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Prérequis OK" -ForegroundColor Green

# Vérifier le fichier .env
if (!(Test-Path ".env")) {
    Write-Host "`n⚠️  Fichier .env introuvable, création depuis .env.example..." -ForegroundColor Yellow
    
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "✅ .env créé - IMPORTANT: Ajoutez vos clés API!" -ForegroundColor Green
        
        # Ouvrir le fichier pour édition
        $openFile = Read-Host "Voulez-vous éditer le fichier .env maintenant? (O/N)"
        if ($openFile -eq "O" -or $openFile -eq "o") {
            notepad .env
            Write-Host "Appuyez sur une touche quand vous avez fini d'éditer..." -ForegroundColor Gray
            $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        }
    } else {
        Write-Host "❌ .env.example introuvable!" -ForegroundColor Red
        exit 1
    }
}

# Charger les variables d'environnement
Write-Host "`n🔐 Chargement de la configuration..." -ForegroundColor Yellow
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^#].+?)=(.+)$') {
        $key = $matches[1].Trim()
        $value = $matches[2].Trim()
        [System.Environment]::SetEnvironmentVariable($key, $value, [System.EnvironmentVariableTarget]::Process)
    }
}

# Vérifier les clés API
$openaiKey = [System.Environment]::GetEnvironmentVariable("OPENAI_API_KEY")
$anthropicKey = [System.Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY")

if (!$openaiKey -or $openaiKey -eq "sk-...") {
    Write-Host "⚠️  OPENAI_API_KEY non configurée - GPT-4o sera désactivé" -ForegroundColor Yellow
}

if (!$anthropicKey -or $anthropicKey -eq "claude-...") {
    Write-Host "⚠️  ANTHROPIC_API_KEY non configurée - Claude sera désactivé" -ForegroundColor Yellow
}

# S'assurer que le réseau existe
Write-Host "`n🌐 Vérification du réseau Docker..." -ForegroundColor Yellow
$networkExists = docker network ls --format "{{.Name}}" | Select-String -Pattern "^school_network$"
if (!$networkExists) {
    Write-Host "Création du réseau school_network..." -ForegroundColor Gray
    docker network create school_network
}

# Build si demandé
if ($Build) {
    Write-Host "`n🔨 Construction des images Docker..." -ForegroundColor Yellow
    docker-compose -f docker-compose.yml -f docker-compose.ai.yml build
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Erreur lors de la construction!" -ForegroundColor Red
        exit 1
    }
}

# Démarrer les services
Write-Host "`n🚀 Démarrage des services..." -ForegroundColor Yellow

$composeFiles = @("-f", "docker-compose.yml", "-f", "docker-compose.ai.yml")
$services = @("postgres", "redis", "ai_agent")

if ($Monitoring) {
    $services += @("prometheus", "grafana")
    Write-Host "📊 Monitoring activé (Prometheus + Grafana)" -ForegroundColor Cyan
}

$upCommand = @("up")
if ($Detached) {
    $upCommand += "-d"
}

if ($Init) {
    # Démarrer avec initialisation des données
    $env:INIT_DATA = "true"
}

# Démarrer les services
docker-compose $composeFiles $upCommand $services

if ($LASTEXITCODE -eq 0 -and $Detached) {
    Write-Host "`n✅ Services démarrés avec succès!" -ForegroundColor Green
    Write-Host "`n📍 URLs d'accès:" -ForegroundColor Cyan
    Write-Host "  - API Solver: http://localhost:8000" -ForegroundColor Gray
    Write-Host "  - Agent IA WebSocket: http://localhost:5001" -ForegroundColor Gray
    Write-Host "  - Interface React: http://localhost:3001" -ForegroundColor Gray
    
    if ($Monitoring) {
        Write-Host "  - Prometheus: http://localhost:9090" -ForegroundColor Gray
        Write-Host "  - Grafana: http://localhost:3002 (admin/admin)" -ForegroundColor Gray
    }
    
    Write-Host "`n🧪 Test de l'agent IA..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:5001/health" -Method GET
        Write-Host "✅ Agent IA opérationnel!" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  L'agent IA n'est pas encore prêt, réessayez dans quelques secondes" -ForegroundColor Yellow
    }
    
    Write-Host "`n💡 Commandes utiles:" -ForegroundColor Cyan
    Write-Host "  - Logs AI: docker logs -f school_ai_agent" -ForegroundColor Gray
    Write-Host "  - Arrêter: docker-compose -f docker-compose.yml -f docker-compose.ai.yml down" -ForegroundColor Gray
    Write-Host "  - Restart: docker-compose -f docker-compose.yml -f docker-compose.ai.yml restart ai_agent" -ForegroundColor Gray
    
    # Ouvrir l'interface si demandé
    $openBrowser = Read-Host "`nVoulez-vous ouvrir l'interface dans le navigateur? (O/N)"
    if ($openBrowser -eq "O" -or $openBrowser -eq "o") {
        Start-Process "http://localhost:3001"
    }
}

# Afficher l'aide
if (!$Detached) {
    Write-Host "`n📌 Pour arrêter les services, appuyez sur Ctrl+C" -ForegroundColor Yellow
}

Write-Host "`n🎉 Démarrage terminé!" -ForegroundColor Green