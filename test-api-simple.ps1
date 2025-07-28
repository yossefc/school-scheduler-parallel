# Test API simple - Version fonctionnelle
Write-Host "=== Test API Solver ===" -ForegroundColor Green

$simpleBody = @{
    constraints = @()
    time_limit = 60
    optimize_for = "balance"
}
$jsonBody = $simpleBody | ConvertTo-Json -Depth 2

try {
    Write-Host "Test generation planning..." -ForegroundColor Yellow
    $result = Invoke-RestMethod -Uri "http://localhost:8000/generate_schedule" -Method POST -ContentType "application/json" -Body $jsonBody -TimeoutSec 90
    
    if ($result.status -eq "success") {
        Write-Host "SUCCESS! Planning genere!" -ForegroundColor Green
        Write-Host "Schedule ID: $($result.schedule_id)" -ForegroundColor Cyan
    } else {
        Write-Host "ECHEC: $($result.reason)" -ForegroundColor Red
    }
} catch {
    Write-Host "ERREUR API: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "Test termine." -ForegroundColor Cyan 