# test-ai-integration.ps1 - Test rapide de l'intégration

Write-Host "🧪 Test de l'intégration Agent IA" -ForegroundColor Cyan

# Test 1: Vérifier l'API principale
Write-Host "`n1. Test API Solver..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/" -Method GET
    Write-Host "  ✓ API Solver: OK" -ForegroundColor Green
} catch {
    Write-Host "  ❌ API Solver: Non accessible" -ForegroundColor Red
}

# Test 2: Vérifier l'agent IA
Write-Host "`n2. Test Agent IA..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:5001/health" -Method GET
    Write-Host "  ✓ Agent IA: OK" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Agent IA: Non accessible" -ForegroundColor Red
}

# Test 3: Test de parsing
Write-Host "`n3. Test parsing langage naturel..." -ForegroundColor Yellow
$body = @{
    text = "Le professeur Cohen ne peut pas enseigner le vendredi"
    language = "fr"
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "http://localhost:5001/api/ai/constraints/natural" `
        -Method POST -Body $body -ContentType "application/json"
    Write-Host "  ✓ Parsing: OK" -ForegroundColor Green
    Write-Host "  Confiance: $($response.confidence)" -ForegroundColor Gray
} catch {
    Write-Host "  ❌ Parsing: Erreur - $_" -ForegroundColor Red
}

Write-Host "`n✅ Test terminé" -ForegroundColor Green
