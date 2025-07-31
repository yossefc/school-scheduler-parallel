from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import re

app = Flask(__name__)
CORS(app)

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "service": "scheduler-ai-improved",
        "version": "1.1"
    })

@app.route('/api/ai/constraints/natural', methods=['POST'])
def parse_natural():
    try:
        data = request.json
        text = data.get('text', '').lower()
        
        constraint = {"type": "custom", "entity": "unknown", "data": {}}
        
        # Détection professeur améliorée (noms composés)
        prof_match = re.search(r'professeur\s+([\w\s]+?)(?:\s+ne|\s+veut|\s*$)', text)
        if prof_match:
            prof_name = prof_match.group(1).strip().title()
            constraint["entity"] = prof_name
        
        # Détection type de contrainte
        if "pas de pause" in text or "sans pause" in text:
            constraint["type"] = "no_gaps_preference"
            constraint["data"]["max_gap_minutes"] = 0
        elif "entre" in text and "cours" in text:
            constraint["type"] = "consecutive_hours_preference"
            constraint["data"]["prefer_consecutive"] = True
        elif "ne peut pas" in text:
            constraint["type"] = "teacher_availability"
            # Détection jour
            if "vendredi" in text:
                constraint["data"]["unavailable_days"] = [5]
            elif "lundi" in text:
                constraint["data"]["unavailable_days"] = [1]
            elif "mardi" in text:
                constraint["data"]["unavailable_days"] = [2]
        
        # Calculer confiance
        confidence = 0.8 if constraint["entity"] != "unknown" and constraint["type"] != "custom" else 0.3
        
        result = {
            "original_text": data.get('text', ''),
            "parsed_constraint": constraint,
            "confidence": confidence,
            "summary": f"Contrainte {constraint['type']} pour {constraint['entity']}"
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
