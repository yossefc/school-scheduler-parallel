# start-ai-agent.ps1 - Demarrage de l'agent IA pour School Scheduler

param(
    [switch]$Build,
    [switch]$Init,
    [switch]$Monitoring,
    [switch]$Detached
)

Write-Host @"
================================================================
           SCHOOL SCHEDULER AI AGENT                           
                                                              
  Assistant IA pour la gestion d'emplois du temps             
================================================================
"@ -ForegroundColor Cyan

# Verifier les prerequis
Write-Host "`nVerification des prerequis..." -ForegroundColor Yellow

# Docker
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker n'est pas installe!" -ForegroundColor Red
    Write-Host "Veuillez installer Docker Desktop: https://www.docker.com/products/docker-desktop" -ForegroundColor Gray
    exit 1
}

# Docker Compose
if (!(Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    Write-Host "Docker Compose n'est pas installe!" -ForegroundColor Red
    exit 1
}

Write-Host "Prerequis OK" -ForegroundColor Green

# Verifier le fichier .env
if (!(Test-Path ".env")) {
    Write-Host "`nFichier .env introuvable, creation depuis .env.example..." -ForegroundColor Yellow
    
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host ".env cree - IMPORTANT: Ajoutez vos cles API!" -ForegroundColor Green
        
        # Ouvrir le fichier pour edition
        $openFile = Read-Host "Voulez-vous editer le fichier .env maintenant? (O/N)"
        if ($openFile -eq "O" -or $openFile -eq "o") {
            notepad .env
            Write-Host "Appuyez sur une touche quand vous avez fini d'editer..." -ForegroundColor Gray
            $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        }
    } else {
        Write-Host ".env.example introuvable!" -ForegroundColor Red
        exit 1
    }
}

# Charger les variables d'environnement
Write-Host "`nChargement de la configuration..." -ForegroundColor Yellow
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^#].+?)=(.+)$') {
        $key = $matches[1].Trim()
        $value = $matches[2].Trim()
        [System.Environment]::SetEnvironmentVariable($key, $value, [System.EnvironmentVariableTarget]::Process)
    }
}

# Verifier les cles API
$openaiKey = [System.Environment]::GetEnvironmentVariable("OPENAI_API_KEY")
$anthropicKey = [System.Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY")

if (!$openaiKey -or $openaiKey -eq "sk-...") {
    Write-Host "OPENAI_API_KEY non configuree - GPT-4o sera desactive" -ForegroundColor Yellow
}

if (!$anthropicKey -or $anthropicKey -eq "claude-...") {
    Write-Host "ANTHROPIC_API_KEY non configuree - Claude sera desactive" -ForegroundColor Yellow
}

# S'assurer que le reseau existe
Write-Host "`nVerification du reseau Docker..." -ForegroundColor Yellow
$networkExists = docker network ls --format "{{.Name}}" | Select-String -Pattern "^school_network$"
if (!$networkExists) {
    Write-Host "Creation du reseau school_network..." -ForegroundColor Gray
    docker network create school_network
}

# Build si demande
if ($Build) {
    Write-Host "`nConstruction des images Docker..." -ForegroundColor Yellow
    docker-compose -f docker-compose.yml -f docker-compose.ai.yml build
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Erreur lors de la construction!" -ForegroundColor Red
        exit 1
    }
}

# Demarrer les services
Write-Host "`nDemarrage des services..." -ForegroundColor Yellow

$composeFiles = @("-f", "docker-compose.yml", "-f", "docker-compose.ai.yml")
$services = @("postgres", "redis", "ai_agent")

if ($Monitoring) {
    $services += @("prometheus", "grafana")
    Write-Host "Monitoring active (Prometheus + Grafana)" -ForegroundColor Cyan
}

$upCommand = @("up")
if ($Detached) {
    $upCommand += "-d"
}

if ($Init) {
    # Demarrer avec initialisation des donnees
    $env:INIT_DATA = "true"
}

# Demarrer les services
docker-compose $composeFiles $upCommand $services

if ($LASTEXITCODE -eq 0 -and $Detached) {
    Write-Host "`nServices demarres avec succes!" -ForegroundColor Green
    Write-Host "`nURLs d'acces:" -ForegroundColor Cyan
    Write-Host "  - API Solver: http://localhost:8000" -ForegroundColor Gray
    Write-Host "  - Agent IA WebSocket: http://localhost:5001" -ForegroundColor Gray
    Write-Host "  - Interface React: http://localhost:3001" -ForegroundColor Gray
    
    if ($Monitoring) {
        Write-Host "  - Prometheus: http://localhost:9090" -ForegroundColor Gray
        Write-Host "  - Grafana: http://localhost:3002 (admin/admin)" -ForegroundColor Gray
    }
    
    Write-Host "`nTest de l'agent IA..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:5001/health" -Method GET
        Write-Host "Agent IA operationnel!" -ForegroundColor Green
    } catch {
        Write-Host "L'agent IA n'est pas encore pret, reessayez dans quelques secondes" -ForegroundColor Yellow
    }
    
    Write-Host "`nCommandes utiles:" -ForegroundColor Cyan
    Write-Host "  - Logs AI: docker logs -f school_ai_agent" -ForegroundColor Gray
    Write-Host "  - Arreter: docker-compose -f docker-compose.yml -f docker-compose.ai.yml down" -ForegroundColor Gray
    Write-Host "  - Restart: docker-compose -f docker-compose.yml -f docker-compose.ai.yml restart ai_agent" -ForegroundColor Gray
    
    # Ouvrir l'interface si demande
    $openBrowser = Read-Host "`nVoulez-vous ouvrir l'interface dans le navigateur? (O/N)"
    if ($openBrowser -eq "O" -or $openBrowser -eq "o") {
        Start-Process "http://localhost:3001"
    }
}

# Afficher l'aide
if (!$Detached) {
    Write-Host "`nPour arreter les services, appuyez sur Ctrl+C" -ForegroundColor Yellow
}

Write-Host "`nDemarrage termine!" -ForegroundColor Green 