from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import re
import requests

app = Flask(__name__)
CORS(app)

SOLVER_URL = 'http://solver:8000'  # URL du solver dans Docker

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "service": "scheduler-ai-connected",
        "version": "2.0"
    })

@app.route('/api/ai/constraints/natural', methods=['POST'])
def parse_and_apply():
    try:
        data = request.json
        text = data.get('text', '').lower()
        
        # 1. Parser la contrainte (comme avant)
        constraint = {"type": "custom", "entity": "unknown", "data": {}}
        
        # Détection professeur
        prof_match = re.search(r'professeur\s+([\w\s]+?)(?:\s+ne|\s+veut|\s*$)', text)
        if prof_match:
            prof_name = prof_match.group(1).strip().title()
            constraint["entity"] = prof_name
        
        # Détection type
        if "pas de pause" in text or "sans pause" in text:
            constraint["type"] = "consecutive_hours_limit"
            constraint["data"] = {
                "max_consecutive": 8,
                "applies_to": constraint["entity"]
            }
        elif "ne peut pas" in text:
            constraint["type"] = "teacher_availability"
            if "vendredi" in text:
                constraint["data"] = {"unavailable_days": [5]}
            elif "lundi" in text:
                constraint["data"] = {"unavailable_days": [1]}
        
        # 2. Appliquer au solver si contrainte valide
        applied = False
        schedule_updated = False
        
        if constraint["type"] != "custom" and constraint["entity"] != "unknown":
            try:
                # Envoyer la contrainte au solver
                solver_payload = {
                    "constraint_type": constraint["type"],
                    "entity_name": constraint["entity"],
                    "constraint_data": constraint["data"],
                    "priority": 2
                }
                
                # Ajouter la contrainte
                constraint_response = requests.post(
                    f"{SOLVER_URL}/api/constraints",
                    json=solver_payload,
                    timeout=10
                )
                
                if constraint_response.status_code == 200:
                    applied = True
                    
                    # Régénérer l'emploi du temps
                    generate_response = requests.post(
                        f"{SOLVER_URL}/generate_schedule",
                        json={"time_limit": 30},
                        timeout=45
                    )
                    
                    if generate_response.status_code == 200:
                        schedule_updated = True
                
            except Exception as e:
                print(f"Erreur solver: {e}")
        
        # 3. Réponse
        confidence = 0.8 if constraint["entity"] != "unknown" else 0.3
        
        result = {
            "original_text": data.get('text', ''),
            "parsed_constraint": constraint,
            "confidence": confidence,
            "applied": applied,
            "schedule_updated": schedule_updated,
            "summary": f"Contrainte {constraint['type']} pour {constraint['entity']}"
        }
        
        if applied and schedule_updated:
            result["message"] = "✅ Contrainte appliquée et emploi du temps mis à jour!"
        elif applied:
            result["message"] = "⚠️ Contrainte ajoutée mais emploi du temps non régénéré"
        else:
            result["message"] = "ℹ️ Contrainte comprise mais non appliquée"
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
