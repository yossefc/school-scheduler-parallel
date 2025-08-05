# parsers.py
def natural_language_parser(text):
    text_lower = text.lower()
    
    # Détection du type
    constraint_type = "custom"
    if "disponible" in text_lower or "availability" in text_lower:
        constraint_type = "teacher_availability"
    elif "vendredi" in text_lower:
        constraint_type = "friday_constraint"
    elif "consecutive" in text_lower or "consécutives" in text_lower:
        constraint_type = "consecutive_hours_limit"
    
    # Extraction d'entité
    entity = None
    words = text.split()
    for i, word in enumerate(words):
        if word.lower() in ["professeur", "prof", "teacher"] and i + 1 < len(words):
            entity = words[i + 1]
            break
    
    return {
        "type": constraint_type,
        "entity": entity,
        "original_text": text
    }
