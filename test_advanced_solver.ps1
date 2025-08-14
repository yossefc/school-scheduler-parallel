# test_advanced_solver.ps1 - Script de test du nouveau solver pédagogique

Write-Host "=== TEST DU SOLVER PÉDAGOGIQUE AVANCÉ ===" -ForegroundColor Cyan
Write-Host ""

# Vérifier que Docker est en cours d'exécution
Write-Host "1. Vérification de Docker..." -ForegroundColor Yellow
$dockerStatus = docker ps 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker n'est pas en cours d'exécution!" -ForegroundColor Red
    Write-Host "Veuillez démarrer Docker Desktop et réessayer." -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ Docker est actif" -ForegroundColor Green

# Vérifier que les conteneurs sont en cours d'exécution
Write-Host ""
Write-Host "2. Vérification des conteneurs..." -ForegroundColor Yellow
$containers = docker ps --format "table {{.Names}}\t{{.Status}}" | Select-String -Pattern "school-scheduler"

if ($containers.Count -lt 2) {
    Write-Host "⚠️  Tous les conteneurs ne sont pas actifs" -ForegroundColor Yellow
    Write-Host "Démarrage des conteneurs..." -ForegroundColor Cyan
    docker-compose up -d
    Start-Sleep -Seconds 10
}
Write-Host "✅ Conteneurs actifs" -ForegroundColor Green

# Test 1 : Vérifier l'état de l'API
Write-Host ""
Write-Host "3. Test de l'API solver..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/" -Method GET
    Write-Host "✅ API solver accessible" -ForegroundColor Green
    Write-Host "   Version: $($response.version)" -ForegroundColor Gray
} catch {
    Write-Host "❌ Erreur API: $_" -ForegroundColor Red
    exit 1
}

# Test 2 : Vérifier le statut des modules avancés
Write-Host ""
Write-Host "4. Vérification des modules avancés..." -ForegroundColor Yellow
try {
    $advancedStatus = Invoke-RestMethod -Uri "http://localhost:8000/api/advanced/status" -Method GET
    if ($advancedStatus.modules_available) {
        Write-Host "✅ Modules avancés disponibles" -ForegroundColor Green
        Write-Host "   Ready: $($advancedStatus.ready)" -ForegroundColor Gray
    } else {
        Write-Host "⚠️  Modules avancés non disponibles" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ Erreur vérification modules: $_" -ForegroundColor Red
}

# Test 3 : Vérifier les données dans la DB
Write-Host ""
Write-Host "5. Vérification des données..." -ForegroundColor Yellow
try {
    # Vérifier les time_slots pour le dimanche
    $query = @"
SELECT day_of_week, COUNT(*) as slot_count 
FROM time_slots 
WHERE is_active = true AND is_break = false 
GROUP BY day_of_week 
ORDER BY day_of_week
"@
    
    $result = docker exec school-scheduler-postgres-1 psql -U admin -d school_scheduler -c "$query" -t 2>$null
    Write-Host "✅ Distribution des créneaux par jour:" -ForegroundColor Green
    
    $lines = $result -split "`n" | Where-Object { $_.Trim() -ne "" }
    $days = @("Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi")
    
    foreach ($line in $lines) {
        if ($line -match "(\d+)\s*\|\s*(\d+)") {
            $dayNum = [int]$matches[1]
            $count = $matches[2]
            if ($dayNum -ge 0 -and $dayNum -lt 7) {
                Write-Host "   $($days[$dayNum]): $count créneaux" -ForegroundColor Gray
            }
        }
    }
    
    # Vérifier les groupes parallèles
    $parallelQuery = "SELECT COUNT(*) FROM parallel_groups"
    $parallelCount = docker exec school-scheduler-postgres-1 psql -U admin -d school_scheduler -c "$parallelQuery" -t 2>$null
    $parallelCount = ($parallelCount -split "`n" | Where-Object { $_.Trim() -match "^\d+$" } | Select-Object -First 1).Trim()
    Write-Host "   Groupes parallèles: $parallelCount" -ForegroundColor Gray
    
} catch {
    Write-Host "⚠️  Erreur accès DB: $_" -ForegroundColor Yellow
}

# Test 4 : Générer un emploi du temps avec le mode avancé
Write-Host ""
Write-Host "6. Test de génération avec optimisation avancée..." -ForegroundColor Yellow
Write-Host "   Cela peut prendre quelques minutes..." -ForegroundColor Gray

$payload = @{
    time_limit = 300
    advanced = $true
    minimize_gaps = $true
    friday_short = $true
    limit_consecutive = $true
    avoid_late_hard = $true
} | ConvertTo-Json

try {
    $startTime = Get-Date
    $response = Invoke-RestMethod -Uri "http://localhost:8000/generate_schedule" `
                                 -Method POST `
                                 -Body $payload `
                                 -ContentType "application/json" `
                                 -TimeoutSec 360
    
    $duration = (Get-Date) - $startTime
    
    if ($response.success) {
        Write-Host "✅ Emploi du temps généré avec succès!" -ForegroundColor Green
        Write-Host "   Schedule ID: $($response.schedule_id)" -ForegroundColor Gray
        Write-Host "   Durée: $($duration.TotalSeconds.ToString('F1'))s" -ForegroundColor Gray
        Write-Host "   Mode: $(if($response.advanced){'Avancé'}else{'Standard'})" -ForegroundColor Gray
        Write-Host "   Entrées: $($response.total_entries)" -ForegroundColor Gray
        
        if ($response.quality_score) {
            Write-Host "   Score qualité: $($response.quality_score)/100" -ForegroundColor Gray
        }
        
        if ($response.features_applied) {
            Write-Host "   Fonctionnalités appliquées:" -ForegroundColor Gray
            $response.features_applied.PSObject.Properties | ForEach-Object {
                if ($_.Value -eq $true) {
                    Write-Host "     ✓ $($_.Name)" -ForegroundColor Green
                }
            }
        }
        
        # Vérifier la distribution par jour
        Write-Host ""
        Write-Host "7. Analyse de la distribution..." -ForegroundColor Yellow
        
        $scheduleId = $response.schedule_id
        $analysisQuery = @"
SELECT 
    day_of_week,
    COUNT(*) as entries,
    COUNT(DISTINCT class_name) as classes,
    COUNT(DISTINCT teacher_name) as teachers
FROM schedule_entries 
WHERE schedule_id = $scheduleId
GROUP BY day_of_week
ORDER BY day_of_week
"@
        
        $analysis = docker exec school-scheduler-postgres-1 psql -U admin -d school_scheduler -c "$analysisQuery" -t 2>$null
        $lines = $analysis -split "`n" | Where-Object { $_.Trim() -ne "" }
        
        Write-Host "   Distribution des cours:" -ForegroundColor Gray
        foreach ($line in $lines) {
            if ($line -match "(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)") {
                $dayNum = [int]$matches[1]
                $entries = $matches[2]
                $classes = $matches[3]
                $teachers = $matches[4]
                
                if ($dayNum -ge 0 -and $dayNum -lt 7) {
                    $dayName = $days[$dayNum]
                    Write-Host "     $dayName : $entries cours, $classes classes, $teachers profs" -ForegroundColor Gray
                    
                    # Vérifier spécifiquement le dimanche
                    if ($dayNum -eq 0 -and [int]$entries -eq 0) {
                        Write-Host "     ⚠️  ATTENTION: Aucun cours le dimanche!" -ForegroundColor Yellow
                    }
                }
            }
        }
        
        # Vérifier les cours parallèles
        Write-Host ""
        Write-Host "8. Vérification de la synchronisation parallèle..." -ForegroundColor Yellow
        
        $parallelCheckQuery = @"
SELECT 
    COUNT(DISTINCT CONCAT(day_of_week, '-', period_number)) as unique_slots,
    COUNT(*) as total_entries,
    group_id
FROM schedule_entries 
WHERE schedule_id = $scheduleId 
  AND is_parallel_group = true 
  AND group_id IS NOT NULL
GROUP BY group_id
HAVING COUNT(*) > 1
"@
        
        $parallelCheck = docker exec school-scheduler-postgres-1 psql -U admin -d school_scheduler -c "$parallelCheckQuery" -t 2>$null
        $parallelLines = $parallelCheck -split "`n" | Where-Object { $_.Trim() -ne "" -and $_ -match "\d" }
        
        if ($parallelLines.Count -gt 0) {
            Write-Host "   Groupes parallèles synchronisés:" -ForegroundColor Gray
            foreach ($line in $parallelLines) {
                if ($line -match "(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)") {
                    $uniqueSlots = $matches[1]
                    $totalEntries = $matches[2]
                    $groupId = $matches[3]
                    
                    if ($uniqueSlots -eq "1" -and [int]$totalEntries -gt 1) {
                        Write-Host "     ✅ Groupe $groupId : $totalEntries cours au même créneau" -ForegroundColor Green
                    } else {
                        Write-Host "     ❌ Groupe $groupId : $totalEntries cours sur $uniqueSlots créneaux différents!" -ForegroundColor Red
                    }
                }
            }
        } else {
            Write-Host "   ⚠️  Aucun groupe parallèle trouvé dans l'emploi du temps" -ForegroundColor Yellow
        }
        
    } else {
        Write-Host "❌ Échec de la génération" -ForegroundColor Red
        Write-Host "   Message: $($response.message)" -ForegroundColor Gray
    }
    
} catch {
    Write-Host "❌ Erreur génération: $_" -ForegroundColor Red
    Write-Host "   Détails: $($_.Exception.Message)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "=== FIN DES TESTS ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Pour visualiser l'emploi du temps:" -ForegroundColor Yellow
Write-Host "1. Ouvrir http://localhost:8000/constraints-manager" -ForegroundColor Gray
Write-Host "2. Aller dans l'onglet 'Emploi du temps'" -ForegroundColor Gray
Write-Host "3. Utiliser les filtres par classe ou professeur" -ForegroundColor Gray




