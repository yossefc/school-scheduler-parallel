# Script PowerShell pour tester les optimisations du solver OR-Tools
# Usage: .\test_solver_optimisations.ps1

Write-Host "🚀 Test des optimisations OR-Tools pour School Scheduler" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green

# Vérifier que Python est disponible
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Python n'est pas trouvé dans le PATH" -ForegroundColor Red
    exit 1
}

# Vérifier que le service PostgreSQL est démarré
Write-Host "📋 Vérification des services..." -ForegroundColor Yellow

try {
    # Démarrer les services Docker si nécessaire
    Write-Host "🐳 Démarrage des services Docker..." -ForegroundColor Yellow
    docker-compose up -d postgres redis

    # Attendre que PostgreSQL soit prêt
    Write-Host "⏳ Attente de PostgreSQL..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10

    # Vérifier la connexion à la base
    Write-Host "🔍 Test de connexion à la base de données..." -ForegroundColor Yellow
    $testConnection = docker-compose exec -T postgres psql -h localhost -U admin -d school_scheduler -c "SELECT 1;" 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Impossible de se connecter à la base de données" -ForegroundColor Red
        Write-Host $testConnection -ForegroundColor Red
        exit 1
    }
    
    Write-Host "✅ Base de données accessible" -ForegroundColor Green
    
} catch {
    Write-Host "❌ Erreur lors du démarrage des services: $_" -ForegroundColor Red
    exit 1
}

# Installer les dépendances Python si nécessaire
Write-Host "📦 Vérification des dépendances Python..." -ForegroundColor Yellow

$requirements = @(
    "ortools",
    "psycopg2-binary"
)

foreach ($package in $requirements) {
    try {
        python -c "import $($package.Replace('-', '_'))" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "📦 Installation de $package..." -ForegroundColor Yellow
            pip install $package
        }
    } catch {
        Write-Host "📦 Installation de $package..." -ForegroundColor Yellow
        pip install $package
    }
}

Write-Host "✅ Dépendances vérifiées" -ForegroundColor Green

# Exécuter les tests
Write-Host ""
Write-Host "🧪 LANCEMENT DES TESTS D'OPTIMISATION" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

try {
    python test_optimized_solver.py
    $testResult = $LASTEXITCODE
    
    Write-Host ""
    if ($testResult -eq 0) {
        Write-Host "🎉 TESTS RÉUSSIS! Le solver optimisé fonctionne correctement." -ForegroundColor Green
        Write-Host "✅ Optimisations OR-Tools validées:" -ForegroundColor Green
        Write-Host "   - Élimination des trous dans les plannings" -ForegroundColor Green
        Write-Host "   - Compacité maximale des emplois du temps" -ForegroundColor Green
        Write-Host "   - Équilibrage hebdomadaire amélioré" -ForegroundColor Green
        Write-Host "   - Non-superposition garantie" -ForegroundColor Green
    } else {
        Write-Host "⚠️ TESTS PARTIELLEMENT RÉUSSIS ou ÉCHOUÉS" -ForegroundColor Yellow
        Write-Host "Consultez les logs ci-dessus pour plus de détails." -ForegroundColor Yellow
    }
    
    # Afficher les instructions pour utiliser le solver optimisé
    Write-Host ""
    Write-Host "💡 UTILISATION DU SOLVER OPTIMISÉ:" -ForegroundColor Cyan
    Write-Host "Pour utiliser le solver optimisé dans votre application:" -ForegroundColor White
    Write-Host "1. Utilisez la classe ScheduleSolverWithConstraints" -ForegroundColor White
    Write-Host "2. Appelez solve() avec un time_limit approprié (600s recommandé)" -ForegroundColor White
    Write-Host "3. Le solver optimisera automatiquement pour:" -ForegroundColor White
    Write-Host "   - Compacité maximale (élimination des trous)" -ForegroundColor White
    Write-Host "   - Équilibrage hebdomadaire" -ForegroundColor White
    Write-Host "   - Non-superposition stricte" -ForegroundColor White
    
} catch {
    Write-Host "❌ Erreur lors de l'exécution des tests: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "🏁 Tests terminés." -ForegroundColor Green
exit $testResult