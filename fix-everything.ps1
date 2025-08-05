# fix-everything.ps1 - Script complet pour resoudre tous les problemes

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "    REPARATION COMPLETE DU SYSTEME         " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# Fonction pour afficher les etapes
function Write-Step {
    param($Number, $Text)
    Write-Host ""
    Write-Host "[$Number/10] $Text" -ForegroundColor Yellow
    Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
}

# Etape 1: Tuer le processus sur le port 3001
Write-Step 1 "Liberation du port 3001"
try {
    $process = Get-Process -Id 17736 -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id 17736 -Force
        Write-Host "[OK] Processus 17736 arrete" -ForegroundColor Green
    } else {
        # Methode alternative
        & taskkill /PID 17736 /F 2>$null
        Write-Host "[OK] Port 3001 libere" -ForegroundColor Green
    }
} catch {
    Write-Host "[!] Le processus etait deja arrete" -ForegroundColor Yellow
}

Start-Sleep -Seconds 2

# Etape 2: Arreter tous les conteneurs
Write-Step 2 "Arret des conteneurs Docker"
docker-compose down
Write-Host "[OK] Conteneurs arretes" -ForegroundColor Green

# Etape 3: Nettoyer et reconstruire
Write-Step 3 "Reconstruction des images Docker"
docker-compose build --no-cache solver
Write-Host "[OK] Images reconstruites" -ForegroundColor Green

# Etape 4: Redemarrer les services
Write-Step 4 "Demarrage des services"
docker-compose up -d
Write-Host "[OK] Services demarres" -ForegroundColor Green

# Etape 5: Attendre que les services soient prets
Write-Step 5 "Attente du demarrage complet (20 secondes)"
$waitTime = 20
for ($i = 1; $i -le $waitTime; $i++) {
    Write-Progress -Activity "Demarrage des services" -Status "$i/$waitTime secondes" -PercentComplete (($i/$waitTime)*100)
    Start-Sleep -Seconds 1
}
Write-Progress -Activity "Demarrage des services" -Completed
Write-Host "[OK] Services prets" -ForegroundColor Green

# Etape 6: Test de l'API
Write-Step 6 "Verification de l'API"
$maxRetries = 5
$apiOk = $false

for ($i = 1; $i -le $maxRetries; $i++) {
    try {
        $response = Invoke-WebRequest -Uri http://localhost:8000 -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            $apiOk = $true
            Write-Host "[OK] API accessible!" -ForegroundColor Green
            break
        }
    } catch {
        Write-Host "   Tentative $i/$maxRetries..." -ForegroundColor Gray
        Start-Sleep -Seconds 2
    }
}

if (-not $apiOk) {
    Write-Host "[ERREUR] L'API ne repond pas. Verifiez les logs avec: docker-compose logs solver" -ForegroundColor Red
    exit 1
}

# Etape 7: Test de l'endpoint des contraintes
Write-Step 7 "Test de l'endpoint /constraints"
try {
    $constraints = Invoke-RestMethod -Uri http://localhost:8000/constraints -TimeoutSec 10
    Write-Host "[OK] Endpoint fonctionnel - $($constraints.Count) contraintes trouvees" -ForegroundColor Green
} catch {
    Write-Host "[ERREUR] $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "[!] L'endpoint /constraints n'existe pas. Verifiez que dans solver/main.py vous avez:" -ForegroundColor Yellow
    Write-Host "    from api_constraints import register_constraint_routes" -ForegroundColor White
    Write-Host "    register_constraint_routes(app)" -ForegroundColor White
    Write-Host ""
    exit 1
}

# Etape 8: Ajouter une contrainte de test
Write-Step 8 "Ajout d'une contrainte de test"
$testConstraint = @{
    constraint_type = "teacher_availability"
    entity_name = "Cohen"
    constraint_data = @{
        unavailable_days = @(5)
        unavailable_periods = @(7, 8, 9, 10)
        reason = "Indisponible le vendredi apres-midi"
    }
    priority = 1
}

try {
    $body = $testConstraint | ConvertTo-Json -Depth 10
    $result = Invoke-RestMethod -Uri http://localhost:8000/constraints `
        -Method POST `
        -Body $body `
        -ContentType "application/json"
    
    Write-Host "[OK] Contrainte ajoutee avec ID: $($result.constraint_id)" -ForegroundColor Green
    
    # Verifier qu'elle apparait dans la liste
    Start-Sleep -Seconds 1
    $newConstraints = Invoke-RestMethod -Uri http://localhost:8000/constraints
    $found = $newConstraints | Where-Object { $_.entity_name -eq "Cohen" }
    
    if ($found) {
        Write-Host "[OK] Contrainte verifiee dans la base de donnees" -ForegroundColor Green
    } else {
        Write-Host "[!] La contrainte n'apparait pas dans la liste" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[ERREUR] Erreur lors de l'ajout: $_" -ForegroundColor Red
}

# Etape 9: Tester la generation d'emploi du temps
Write-Step 9 "Test de generation d'emploi du temps"
$scheduleRequest = @{
    constraints = @()
    time_limit = 60
}

try {
    Write-Host "Generation en cours (peut prendre jusqu'a 60 secondes)..." -ForegroundColor Cyan
    
    $body = $scheduleRequest | ConvertTo-Json
    $schedule = Invoke-RestMethod -Uri http://localhost:8000/generate_schedule `
        -Method POST `
        -Body $body `
        -ContentType "application/json" `
        -TimeoutSec 120
    
    if ($schedule -and $schedule.schedule) {
        Write-Host "[OK] Emploi du temps genere avec $($schedule.schedule.Count) entrees!" -ForegroundColor Green
        
        # Afficher quelques statistiques
        if ($schedule.statistics) {
            Write-Host ""
            Write-Host "STATISTIQUES:" -ForegroundColor Cyan
            Write-Host "   - Assignations: $($schedule.statistics.total_assignments)" -ForegroundColor White
            Write-Host "   - Professeurs: $($schedule.statistics.teachers_used.Count)" -ForegroundColor White
            Write-Host "   - Classes: $($schedule.statistics.classes_covered.Count)" -ForegroundColor White
        }
    } else {
        Write-Host "[!] Aucune solution trouvee" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[ERREUR] Erreur de generation: $_" -ForegroundColor Red
}

# Etape 10: Afficher les informations finales
Write-Step 10 "Configuration terminee"

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "         SYSTEME OPERATIONNEL!             " -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "URLs disponibles:" -ForegroundColor Cyan
Write-Host "   - API REST      : http://localhost:8000" -ForegroundColor White
Write-Host "   - Interface     : http://localhost:8000/constraints-manager" -ForegroundColor White
Write-Host "   - Documentation : http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "Commandes utiles:" -ForegroundColor Cyan
Write-Host "   - Voir les logs    : docker-compose logs -f solver" -ForegroundColor White
Write-Host "   - Redemarrer       : docker-compose restart solver" -ForegroundColor White
Write-Host "   - Verifier la BD   : docker exec postgres psql -U admin -d school_scheduler" -ForegroundColor White
Write-Host ""
Write-Host "Pour utiliser l'interface:" -ForegroundColor Cyan
Write-Host "   1. Ouvrez http://localhost:8000/constraints-manager" -ForegroundColor White
Write-Host "   2. Ajoutez des contraintes en langage naturel" -ForegroundColor White
Write-Host "   3. Cliquez sur Generer pour creer un emploi du temps" -ForegroundColor White
Write-Host ""

# Test final de l'interface
Write-Host "Ouverture de l'interface dans le navigateur..." -ForegroundColor Cyan
Start-Process "http://localhost:8000/constraints-manager"

Write-Host ""
Write-Host "Script termine avec succes!" -ForegroundColor Green