@echo off
REM fix_encoding_quick.bat - Script de correction rapide pour Windows
REM Sauvegardez ce fichier et executez-le dans votre dossier projet

echo ========================================
echo   CORRECTION RAPIDE DES PROBLEMES
echo ========================================
echo.

REM Verifier que Python est installe
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERREUR] Python n'est pas installe ou pas dans le PATH
    echo Installez Python depuis python.org
    pause
    exit /b 1
)

echo [OK] Python detecte
echo.

REM Definir l'encodage UTF-8
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo Configuration de l'encodage UTF-8...
echo.

REM Creer un script Python simple pour corriger l'encodage
echo Creation du script de correction...
(
echo import os
echo import sys
echo import codecs
echo.
echo print("Correction de l'encodage en cours..."^)
echo.
echo def fix_file(filepath^):
echo     try:
echo         # Essayer differents encodages
echo         encodings = ['utf-8', 'cp1252', 'iso-8859-1', 'utf-16']
echo         content = None
echo         
echo         for enc in encodings:
echo             try:
echo                 with open(filepath, 'r', encoding=enc^) as f:
echo                     content = f.read(^)
echo                 break
echo             except:
echo                 continue
echo         
echo         if content:
echo             # Remplacer les caracteres problematiques
echo             content = content.replace('?', 'e'^)
echo             content = content.replace('\x0a', '\n'^)
echo             content = content.replace('\x5cn', '\n'^)
echo             
echo             # Sauvegarder en UTF-8
echo             with open(filepath, 'w', encoding='utf-8'^) as f:
echo                 f.write(content^)
echo             print(f"  [OK] {filepath}"^)
echo         else:
echo             print(f"  [ERREUR] Impossible de lire {filepath}"^)
echo     except Exception as e:
echo         print(f"  [ERREUR] {filepath}: {e}"^)
echo.
echo # Corriger les fichiers principaux
echo files_to_fix = [
echo     "solver/solver_engine.py",
echo     "scheduler_ai/agent.py",
echo     "scheduler_ai/api.py"
echo ]
echo.
echo for file in files_to_fix:
echo     if os.path.exists(file^):
echo         fix_file(file^)
echo     else:
echo         print(f"  [SKIP] {file} n'existe pas"^)
echo.
echo print("\nCorrection terminee!"^)
) > fix_encoding_temp.py

echo.
echo Execution du script de correction...
echo.
python fix_encoding_temp.py

echo.
echo Nettoyage...
del fix_encoding_temp.py

echo.
echo ========================================
echo   TEST DE VERIFICATION
echo ========================================
echo.

REM Creer un test simple
(
echo import sys
echo print(f"Encodage systeme: {sys.getdefaultencoding()}"^)
echo print(f"Test accents: e a c"^)
echo try:
echo     import psycopg2
echo     print("[OK] psycopg2 importe"^)
echo except:
echo     print("[ERREUR] psycopg2 non installe"^)
echo try:
echo     from ortools.sat.python import cp_model
echo     print("[OK] OR-Tools importe"^)
echo except:
echo     print("[ERREUR] OR-Tools non installe"^)
) > test_imports.py

python test_imports.py
del test_imports.py

echo.
echo ========================================
echo   ETAPES SUIVANTES
echo ========================================
echo.
echo 1. Si des erreurs persistent, ouvrez les fichiers dans VSCode
echo 2. Verifiez que l'encodage est UTF-8 (en bas a droite)
echo 3. Installez les dependances manquantes:
echo    pip install psycopg2-binary ortools flask
echo.
echo 4. Executez le script de verification complet:
echo    python verify_system.py
echo.

pause