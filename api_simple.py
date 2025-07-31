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
        "service": "scheduler-ai-simple",
        "version": "1.0-working"
    })

@app.route('/api/ai/constraints/natural', methods=['POST'])
def parse_natural():
    try:
        data = request.json
        text = data.get('text', '').lower()
        
        # Parsing simple sans LLM
        constraint = {"type": "custom", "entity": "unknown", "data": {}}
        
        # Détection professeur
        prof_match = re.search(r'professeur\s+(\w+)|(\w+)\s+ne\s+peut', text)
        if prof_match:
            prof = prof_match.group(1) or prof_match.group(2)
            constraint["entity"] = prof.capitalize()
            constraint["type"] = "teacher_availability"
        
        # Détection jour
        if "vendredi" in text:
            constraint["data"]["unavailable_days"] = [5]
        elif "lundi" in text:
            constraint["data"]["unavailable_days"] = [1]
            
        result = {
            "original_text": data.get('text', ''),
            "parsed_constraint": constraint,
            "confidence": 0.8 if constraint["type"] != "custom" else 0.3,
            "summary": f"Contrainte détectée pour {constraint['entity']}"
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/ai/test', methods=['GET', 'POST'])  
def test():
    return jsonify({"message": "Agent IA simple fonctionne!", "method": request.method})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
