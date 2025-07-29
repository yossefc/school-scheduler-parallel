# fix_sql_error.ps1 - Corriger l'erreur SQL de type dans l'endpoint

Write-Host @"
╔══════════════════════════════════════════════╗
║        CORRECTION DE L'ERREUR SQL            ║
╚══════════════════════════════════════════════╝
"@ -ForegroundColor Cyan

Write-Host "`nErreur détectée: UNION types integer and character varying cannot be matched" -ForegroundColor Yellow
Write-Host "Cela se produit dans la fonction get_schedule_enhanced" -ForegroundColor Gray

# 1. Backup
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupPath = "solver/main_backup_sql_fix_$timestamp.py"
Copy-Item "solver/main.py" $backupPath
Write-Host "✓ Backup créé: $backupPath" -ForegroundColor Green

# 2. Lire le fichier
$content = Get-Content "solver/main.py" -Raw -Encoding UTF8

# 3. Chercher la fonction problématique
if ($content -match "get_schedule_enhanced") {
    Write-Host "`nFonction get_schedule_enhanced trouvée, correction en cours..." -ForegroundColor Yellow
    
    # Remplacer la fonction entière par une version corrigée
    $correctedFunction = @'
@app.get("/api/schedule/{view_type}/{name}")
async def get_schedule_enhanced(view_type: str, name: str):
    """Version corrigée qui affiche correctement les cours parallèles"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Récupérer le dernier schedule_id actif
        cur.execute("""
            SELECT MAX(schedule_id) as latest_id 
            FROM schedules 
            WHERE status = 'active'
        """)
        result = cur.fetchone()
        
        if not result or not result['latest_id']:
            return {"schedule": [], "view_type": view_type, "name": name, "total_lessons": 0}
        
        schedule_id = result['latest_id']
        
        if view_type == "class":
            # Pour une classe, récupérer directement les entrées
            cur.execute("""
                SELECT 
                    se.entry_id,
                    se.teacher_name,
                    se.class_name,
                    se.subject_name,
                    se.day_of_week,
                    se.period_number,
                    se.is_parallel_group,
                    se.group_id
                FROM schedule_entries se
                WHERE se.schedule_id = %s AND se.class_name = %s
                ORDER BY se.day_of_week, se.period_number
            """, (schedule_id, name))
            
        elif view_type == "teacher":
            cur.execute("""
                SELECT 
                    se.entry_id,
                    se.teacher_name,
                    se.class_name,
                    se.subject_name,
                    se.day_of_week,
                    se.period_number,
                    se.is_parallel_group,
                    se.group_id
                FROM schedule_entries se
                WHERE se.schedule_id = %s AND se.teacher_name = %s
                ORDER BY se.day_of_week, se.period_number
            """, (schedule_id, name))
        
        schedule = cur.fetchall()
        
        # Pour les cours parallèles, ajouter tous les professeurs
        for entry in schedule:
            if entry.get("group_id") and view_type == "class":
                # Récupérer tous les professeurs du groupe parallèle
                cur.execute("""
                    SELECT STRING_AGG(DISTINCT teacher_name, ' + ' ORDER BY teacher_name) as teachers
                    FROM schedule_entries
                    WHERE schedule_id = %s
                    AND group_id = %s 
                    AND day_of_week = %s 
                    AND period_number = %s
                """, (schedule_id, entry["group_id"], entry["day_of_week"], entry["period_number"]))
                
                result = cur.fetchone()
                if result and result["teachers"]:
                    entry["teachers"] = result["teachers"]
        
        return {
            "schedule": schedule, 
            "view_type": view_type, 
            "name": name,
            "total_lessons": len(schedule)
        }
        
    except Exception as e:
        logger.error(f"Erreur get_schedule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()
'@

    # Trouver et remplacer la fonction problématique
    # Chercher le début de la fonction
    $startPattern = '@app\.get\("/api/schedule/\{view_type\}/\{name\}"\)\s*\n\s*async def get_schedule_enhanced'
    
    if ($content -match $startPattern) {
        Write-Host "Remplacement de la fonction..." -ForegroundColor Gray
        
        # Trouver la fin de la fonction (prochaine fonction ou fin du fichier)
        $functionStart = $content.IndexOf("@app.get(""/api/schedule/{view_type}/{name}"")")
        
        if ($functionStart -gt -1) {
            # Chercher la prochaine fonction ou la fin
            $nextFunction = $content.IndexOf("@app.", $functionStart + 1)
            $nextDef = $content.IndexOf("`ndef ", $functionStart + 1)
            
            $functionEnd = [Math]::Min(
                $(if ($nextFunction -gt $functionStart) { $nextFunction } else { $content.Length }),
                $(if ($nextDef -gt $functionStart) { $nextDef } else { $content.Length })
            )
            
            # Remplacer la fonction
            $before = $content.Substring(0, $functionStart)
            $after = $content.Substring($functionEnd)
            
            $newContent = $before + $correctedFunction + "`n`n" + $after
            
            # Sauvegarder
            [System.IO.File]::WriteAllText("solver/main.py", $newContent, [System.Text.Encoding]::UTF8)
            Write-Host "✓ Fonction corrigée avec succès" -ForegroundColor Green
        }
    }
} else {
    Write-Host "⚠️ Fonction get_schedule_enhanced non trouvée" -ForegroundColor Yellow
    Write-Host "Ajout de l'endpoint correct..." -ForegroundColor Gray
    
    # Ajouter la fonction avant if __name__
    $insertPoint = $content.LastIndexOf('if __name__')
    if ($insertPoint -eq -1) { $insertPoint = $content.Length }
    
    $newContent = $content.Insert($insertPoint, "`n`n" + $correctedFunction + "`n`n")
    [System.IO.File]::WriteAllText("solver/main.py", $newContent, [System.Text.Encoding]::UTF8)
    Write-Host "✓ Endpoint ajouté" -ForegroundColor Green
}

# 4. Redémarrer le solver
Write-Host "`nRedémarrage du solver..." -ForegroundColor Yellow
docker-compose restart solver

Write-Host "Attente du démarrage (15 secondes)..." -ForegroundColor Gray
Start-Sleep -Seconds 15

# 5. Tester l'endpoint
Write-Host "`nTest de l'endpoint corrigé..." -ForegroundColor Yellow

try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/schedule/class/ז-1" -Method GET
    Write-Host "✓ L'endpoint fonctionne! $($response.total_lessons) leçons trouvées" -ForegroundColor Green
    
    if ($response.schedule.Count -gt 0) {
        Write-Host "  Exemple: $($response.schedule[0].subject_name) le jour $($response.schedule[0].day_of_week)" -ForegroundColor Gray
    }
} catch {
    Write-Host "✗ Erreur: $_" -ForegroundColor Red
}

# 6. Lancer l'interface
Write-Host "`n✅ CORRECTION TERMINÉE !" -ForegroundColor Green
Write-Host "`nPour lancer l'interface web:" -ForegroundColor Cyan
Write-Host "1. cd exports" -ForegroundColor Gray
Write-Host "2. python -m http.server 8080" -ForegroundColor Gray
Write-Host "3. Ouvrir: http://localhost:8080/visualiser_emploi_du_temps.html" -ForegroundColor Gray

Write-Host "`nOu exécutez simplement:" -ForegroundColor Yellow
Write-Host "  .\launch_web.ps1" -ForegroundColor Cyan

# Créer le script de lancement si nécessaire
if (!(Test-Path "launch_web.ps1")) {
    @'
cd exports
Write-Host "Serveur web démarré sur http://localhost:8080" -ForegroundColor Green
Write-Host "Interface: http://localhost:8080/visualiser_emploi_du_temps.html" -ForegroundColor Cyan
Start-Process "http://localhost:8080/visualiser_emploi_du_temps.html"
python -m http.server 8080
'@ | Out-File "launch_web.ps1" -Encoding UTF8
}

Write-Host "`n✓ Script terminé!" -ForegroundColor Green 