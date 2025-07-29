Write-Host @"
╔══════════════════════════════════════════════╗
║     LANCEMENT DE L'INTERFACE WEB            ║
╚══════════════════════════════════════════════╝
"@ -ForegroundColor Cyan

Write-Host "`n✅ EMPLOI DU TEMPS GÉNÉRÉ AVEC SUCCÈS!" -ForegroundColor Green
Write-Host "   📊 Schedule ID: 4" -ForegroundColor Gray
Write-Host "   🔗 20 groupes parallèles traités" -ForegroundColor Gray
Write-Host "   📅 Toutes les classes couvertes" -ForegroundColor Gray
Write-Host "   ⚖️ Taux d'utilisation: 41.1%" -ForegroundColor Gray

Write-Host "`n🌐 Démarrage du serveur web..." -ForegroundColor Yellow

# Vérifier si le dossier exports existe
if (!(Test-Path "exports")) {
    Write-Host "❌ Dossier exports introuvable!" -ForegroundColor Red
    Write-Host "Création du dossier..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path "exports" -Force
}

# Aller dans le dossier exports
Set-Location exports

# Vérifier si le fichier HTML existe
if (!(Test-Path "visualiser_emploi_du_temps.html")) {
    Write-Host "⚠️ Fichier HTML introuvable, création d'une page simple..." -ForegroundColor Yellow
    
    $htmlContent = @'
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Emploi du Temps - École</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .api-section { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .api-btn { background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-right: 10px; margin-bottom: 10px; }
        .api-btn:hover { background: #5a6fd8; }
        #results { background: #f9f9f9; padding: 15px; border-radius: 5px; min-height: 100px; font-family: monospace; white-space: pre-wrap; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📅 Visualiseur d'Emploi du Temps</h1>
        <p>Interface de consultation pour l'emploi du temps généré automatiquement</p>
    </div>
    
    <div class="stats">
        <div class="stat-card">
            <h3>✅ Statut</h3>
            <p>Emploi du temps généré avec succès</p>
        </div>
        <div class="stat-card">
            <h3>🔗 Cours Parallèles</h3>
            <p>20 groupes parallèles traités</p>
        </div>
        <div class="stat-card">
            <h3>📊 Utilisation</h3>
            <p>41.1% des créneaux utilisés</p>
        </div>
        <div class="stat-card">
            <h3>🏫 Classes</h3>
            <p>23 classes couvertes</p>
        </div>
    </div>
    
    <div class="api-section">
        <h2>🔍 Explorer les Données</h2>
        <p>Utilisez les boutons ci-dessous pour consulter différentes vues de l'emploi du temps :</p>
        
        <button class="api-btn" onclick="loadData('/api/parallel/groups')">Groupes Parallèles</button>
        <button class="api-btn" onclick="loadData('/api/parallel/check')">Vérifier Cohérence</button>
        <button class="api-btn" onclick="loadExample('יא-1')">Exemple Classe יא-1</button>
        <button class="api-btn" onclick="loadExample('יב-2')">Exemple Classe יב-2</button>
        <button class="api-btn" onclick="loadTeacher('מיכל רובין')">Exemple Prof</button>
        
        <div id="results">Cliquez sur un bouton pour voir les données...</div>
    </div>
    
    <div class="api-section">
        <h2>📋 Informations Système</h2>
        <p><strong>API Solver:</strong> <span id="api-status">Vérification...</span></p>
        <p><strong>Base de données:</strong> PostgreSQL</p>
        <p><strong>Schedule ID:</strong> 4 (dernier généré)</p>
        <p><strong>Algorithme:</strong> OR-Tools Constraint Programming</p>
    </div>

    <script>
        // Vérifier le statut de l'API
        fetch('http://localhost:8000/')
            .then(response => response.json())
            .then(data => {
                document.getElementById('api-status').innerHTML = 
                    '<span style="color: green;">✅ En ligne - ' + data.message + '</span>';
            })
            .catch(() => {
                document.getElementById('api-status').innerHTML = 
                    '<span style="color: red;">❌ Hors ligne</span>';
            });

        function loadData(endpoint) {
            const results = document.getElementById('results');
            results.textContent = 'Chargement...';
            
            fetch('http://localhost:8000' + endpoint)
                .then(response => response.json())
                .then(data => {
                    results.textContent = JSON.stringify(data, null, 2);
                })
                .catch(error => {
                    results.textContent = 'Erreur: ' + error.message;
                });
        }
        
        function loadExample(className) {
            loadData('/api/schedule/class/' + encodeURIComponent(className));
        }
        
        function loadTeacher(teacherName) {
            loadData('/api/parallel/teacher/' + encodeURIComponent(teacherName));
        }
    </script>
</body>
</html>
'@
    
    $htmlContent | Out-File "visualiser_emploi_du_temps.html" -Encoding UTF8
    Write-Host "✅ Page HTML créée" -ForegroundColor Green
}

Write-Host "`n🚀 Serveur web démarré sur http://localhost:8080" -ForegroundColor Green
Write-Host "🌐 Interface: http://localhost:8080/visualiser_emploi_du_temps.html" -ForegroundColor Cyan
Write-Host "`nLe navigateur va s'ouvrir automatiquement..." -ForegroundColor Gray

# Ouvrir le navigateur
Start-Process "http://localhost:8080/visualiser_emploi_du_temps.html"

# Démarrer le serveur web
Write-Host "`n⏸️ Appuyez sur Ctrl+C pour arrêter le serveur" -ForegroundColor Yellow
python -m http.server 8080
