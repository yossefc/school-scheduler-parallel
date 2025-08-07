# auto_fix_constraints.py - Script de correction automatique des problèmes

import psycopg2
from psycopg2.extras import RealDictCursor, Json
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration DB
db_config = {
    "host": "localhost",  # ou "localhost" si hors Docker
    "database": "school_scheduler",
    "user": "admin",
    "password": "school123",
    "port": 5432
}

def analyze_and_fix_constraints():
    """Analyse et corrige automatiquement les contraintes problématiques"""
    print("\n" + "="*60)
    print("🔧 ANALYSE ET CORRECTION AUTOMATIQUE DES CONTRAINTES")
    print("="*60)
    
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    fixes_applied = 0
    
    try:
        # 1. ANALYSER LES CONTRAINTES DE DISPONIBILITÉ
        print("\n📋 Analyse des contraintes de disponibilité...")
        
        cur.execute("""
            SELECT * FROM constraints 
            WHERE constraint_type IN ('teacher_availability', 'teacher_unavailable')
            AND is_active = TRUE
        """)
        availability_constraints = cur.fetchall()
        
        print(f"Trouvé {len(availability_constraints)} contraintes de disponibilité")
        
        # Identifier les problèmes
        problematic_constraints = []
        for constraint in availability_constraints:
            data = constraint['constraint_data']
            
            # Parser si c'est une string
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    data = {}
            
            # Vérifier si c'est une contrainte trop restrictive
            if 'unavailable_days' in data and len(data['unavailable_days']) >= 4:
                problematic_constraints.append(constraint)
                print(f"⚠️  {constraint['entity_name']}: {len(data['unavailable_days'])} jours bloqués")
        
        # 2. CORRIGER LES CONTRAINTES PROBLÉMATIQUES
        if problematic_constraints:
            print(f"\n🔧 Correction de {len(problematic_constraints)} contraintes trop restrictives...")
            
            for constraint in problematic_constraints:
                # Convertir en contrainte de disponibilité positive
                data = constraint['constraint_data']
                if isinstance(data, str):
                    data = json.loads(data)
                
                # Si plus de 3 jours bloqués, inverser la logique
                if 'unavailable_days' in data and len(data['unavailable_days']) >= 4:
                    all_days = [0, 1, 2, 3, 4, 5]  # Dimanche à Vendredi
                    available_days = [d for d in all_days if d not in data['unavailable_days']]
                    
                    # Mettre à jour avec les jours disponibles
                    new_data = {
                        'available_days': available_days,
                        'reason': f"Corrigé automatiquement - Disponible {len(available_days)} jours/semaine"
                    }
                    
                    cur.execute("""
                        UPDATE constraints 
                        SET constraint_data = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE constraint_id = %s
                    """, (Json(new_data), constraint['constraint_id']))
                    
                    fixes_applied += 1
                    print(f"✅ Corrigé: {constraint['entity_name']} - maintenant disponible {available_days}")
        
        # 3. AJOUTER LES CONTRAINTES MANQUANTES ESSENTIELLES
        print("\n📋 Vérification des contraintes essentielles...")
        
        # Vérifier si on a une contrainte vendredi court
        cur.execute("""
            SELECT COUNT(*) as count FROM constraints 
            WHERE constraint_type = 'friday_early_end' 
            AND is_active = TRUE
        """)
        friday_count = cur.fetchone()['count']
        
        if friday_count == 0:
            print("⚠️  Contrainte vendredi court manquante - ajout...")
            cur.execute("""
                INSERT INTO constraints 
                (constraint_type, entity_name, priority, constraint_data, is_active, entity_type)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                'friday_early_end', 
                'Global',
                0,  # Priorité maximale
                Json({'last_period': 6, 'applies_to': ['all']}),
                True,
                'global'
            ))
            fixes_applied += 1
            print("✅ Ajouté: Contrainte vendredi court (fin à 13h)")
        
        # 4. DÉSACTIVER LES CONTRAINTES CONFLICTUELLES
        print("\n📋 Recherche de conflits entre contraintes...")
        
        # Détecter les professeurs sur-contraints
        cur.execute("""
            SELECT entity_name, COUNT(*) as constraint_count
            FROM constraints
            WHERE entity_type = 'teacher' 
            AND is_active = TRUE
            GROUP BY entity_name
            HAVING COUNT(*) > 3
        """)
        
        over_constrained = cur.fetchall()
        if over_constrained:
            print(f"⚠️  {len(over_constrained)} professeurs ont trop de contraintes")
            
            for teacher in over_constrained:
                print(f"  - {teacher['entity_name']}: {teacher['constraint_count']} contraintes")
                
                # Garder seulement les 2 contraintes les plus importantes (priorité basse = plus important)
                cur.execute("""
                    UPDATE constraints
                    SET is_active = FALSE
                    WHERE entity_name = %s
                    AND constraint_id NOT IN (
                        SELECT constraint_id FROM constraints
                        WHERE entity_name = %s
                        ORDER BY priority ASC
                        LIMIT 2
                    )
                """, (teacher['entity_name'], teacher['entity_name']))
                
                fixes_applied += 1
        
        # 5. OPTIMISER LES GROUPES PARALLÈLES
        print("\n📋 Vérification des groupes parallèles...")
        
        cur.execute("""
            SELECT pg.*, 
                   COUNT(DISTINCT ptd.teacher_name) as teacher_count
            FROM parallel_groups pg
            LEFT JOIN parallel_teaching_details ptd ON pg.group_id = ptd.group_id
            GROUP BY pg.group_id, pg.subject, pg.grade, pg.teachers
        """)
        
        parallel_groups = cur.fetchall()
        print(f"Trouvé {len(parallel_groups)} groupes parallèles")
        
        for group in parallel_groups:
            if group['teacher_count'] < 2:
                print(f"⚠️  Groupe {group['group_id']} ({group['subject']}) n'a qu'un seul prof")
        
        # Commit des changements
        conn.commit()
        
        # 6. RAPPORT FINAL
        print("\n" + "="*60)
        print("📊 RAPPORT DE CORRECTION")
        print("="*60)
        print(f"✅ {fixes_applied} corrections appliquées")
        
        # Statistiques après correction
        cur.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE is_active = TRUE) as active,
                COUNT(*) FILTER (WHERE is_active = FALSE) as inactive,
                COUNT(*) as total
            FROM constraints
        """)
        stats = cur.fetchone()
        
        print(f"📈 État des contraintes:")
        print(f"   - Actives: {stats['active']}")
        print(f"   - Inactives: {stats['inactive']}")
        print(f"   - Total: {stats['total']}")
        
        # Test de faisabilité
        print("\n🔍 Test de faisabilité rapide...")
        
        cur.execute("SELECT COUNT(*) as count FROM classes")
        num_classes = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) as count FROM time_slots WHERE is_break = FALSE")
        num_slots = cur.fetchone()['count']
        
        cur.execute("SELECT SUM(hours) as total FROM teacher_load WHERE hours > 0")
        total_hours = cur.fetchone()['total'] or 0
        
        available_slots = num_classes * num_slots
        utilization = (total_hours / available_slots * 100) if available_slots > 0 else 0
        
        print(f"   - Classes: {num_classes}")
        print(f"   - Créneaux par semaine: {num_slots}")
        print(f"   - Heures à planifier: {total_hours}")
        print(f"   - Créneaux disponibles: {available_slots}")
        print(f"   - Taux d'utilisation: {utilization:.1f}%")
        
        if utilization > 80:
            print("⚠️  ATTENTION: Taux d'utilisation élevé, la génération peut être difficile")
        else:
            print("✅ Taux d'utilisation raisonnable")
        
        return fixes_applied
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Erreur: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def verify_time_slots():
    """Vérifie que tous les créneaux sont bien définis pour tous les jours"""
    print("\n📅 Vérification des créneaux horaires...")
    
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT day_of_week, COUNT(*) as slot_count
            FROM time_slots
            WHERE is_break = FALSE
            GROUP BY day_of_week
            ORDER BY day_of_week
        """)
        
        slots_by_day = cur.fetchall()
        
        day_names = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi']
        
        missing_days = []
        for day_num in range(6):
            day_data = next((d for d in slots_by_day if d['day_of_week'] == day_num), None)
            
            if day_data:
                print(f"   {day_names[day_num]}: {day_data['slot_count']} créneaux")
            else:
                print(f"   ❌ {day_names[day_num]}: AUCUN créneau!")
                missing_days.append(day_num)
        
        # Si des jours manquent, les créer
        if missing_days:
            print(f"\n🔧 Création des créneaux manquants...")
            
            # Obtenir un modèle depuis un jour existant
            cur.execute("""
                SELECT period_number, start_time, end_time, is_break
                FROM time_slots
                WHERE day_of_week = 0
                ORDER BY period_number
            """)
            template_slots = cur.fetchall()
            
            if template_slots:
                for day in missing_days:
                    for slot in template_slots:
                        # Ajuster pour vendredi (jour 5) - journée courte
                        if day == 5 and slot['period_number'] > 6:
                            continue
                        
                        cur.execute("""
                            INSERT INTO time_slots 
                            (day_of_week, period_number, start_time, end_time, is_break)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT DO NOTHING
                        """, (day, slot['period_number'], slot['start_time'], 
                              slot['end_time'], slot['is_break']))
                
                conn.commit()
                print(f"✅ Créneaux ajoutés pour {len(missing_days)} jours")
        
    finally:
        cur.close()
        conn.close()

def test_minimal_generation():
    """Test avec un sous-ensemble minimal pour vérifier le solver"""
    print("\n🧪 Test de génération minimale...")
    
    from solver.solver_engine import ScheduleSolver  # Utiliser la version corrigée
    
    solver = ScheduleSolver(db_config)
    solver.load_data_from_db()
    
    # Essayer de générer avec un temps court pour tester
    print("   Tentative de génération (30 secondes)...")
    schedule = solver.solve(time_limit=30)
    
    if schedule:
        summary = solver.get_schedule_summary(schedule)
        print(f"✅ Succès! {summary['total_lessons']} créneaux générés")
        print(f"   Jours couverts: {summary['days_used']}")
        print(f"   Par jour: {summary['by_day']}")
        return True
    else:
        print("❌ Échec de génération - vérifier les logs")
        return False

def main():
    """Fonction principale"""
    print("\n🚀 DÉMARRAGE DU DIAGNOSTIC ET CORRECTION AUTOMATIQUE")
    print("="*70)
    
    try:
        # 1. Vérifier les créneaux
        verify_time_slots()
        
        # 2. Analyser et corriger les contraintes
        fixes = analyze_and_fix_constraints()
        
        # 3. Test de génération
        if fixes > 0:
            print("\n💡 Des corrections ont été appliquées.")
            print("   Relancez la génération d'emploi du temps.")
        
        success = test_minimal_generation()
        
        if success:
            print("\n✅ SYSTÈME PRÊT POUR LA GÉNÉRATION COMPLÈTE")
            print("   Recommandations:")
            print("   1. Utilisez un time_limit d'au moins 300 secondes")
            print("   2. Vérifiez que toutes les classes ont des professeurs assignés")
            print("   3. Surveillez les logs pour identifier les problèmes restants")
        else:
            print("\n⚠️  PROBLÈMES PERSISTANTS")
            print("   Actions suggérées:")
            print("   1. Réduire le nombre de contraintes actives")
            print("   2. Vérifier les données de base (professeurs, classes)")
            print("   3. Simplifier temporairement les groupes parallèles")
            
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()