import json
from urllib.request import urlopen

BASE = "http://localhost:8000"

def get_json(path: str):
    with urlopen(BASE + path) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    last = get_json("/api/last_schedule_info")
    print("last_schedule_info:", json.dumps(last, ensure_ascii=False))

    data = get_json("/api/schedule_entries?version=latest")
    time_slots = data.get("time_slots", [])
    entries = data.get("entries", [])
    meta = data.get("meta", {})
    print("meta:", json.dumps(meta, ensure_ascii=False))
    print("total_entries:", len(entries))

    # Chercher doublons pour classe ז-3 le mardi (day=2) à la première heure (slot_index min du mardi)
    target_class_variants = {"ז-3", "ז3", "ז־3", "ז–3"}

    # Trouver l'index de la première heure du mardi dans time_slots
    tuesday_slots = [ts for ts in time_slots if ts.get("day") == 2]
    tuesday_slots_sorted = sorted(tuesday_slots, key=lambda x: x.get("index", 0))
    first_idx = tuesday_slots_sorted[0]["index"] if tuesday_slots_sorted else 0

    conflicts = []
    for name in target_class_variants:
        cell = [e for e in entries if e.get("class_name") == name and e.get("day") == 2 and e.get("slot_index") == first_idx]
        if cell:
            conflicts.append({"class": name, "items": cell})

    print("tuesday_first_hour_index:", first_idx)
    print("conflicts_found:", json.dumps(conflicts, ensure_ascii=False))

    # Détecter trous par classe: compter motifs 1-0-1 par jour
    gaps = []
    classes = sorted({e.get("class_name") for e in entries if e.get("class_name")})
    days = sorted({ts.get("day") for ts in time_slots})
    for cls in classes:
        for d in days:
            day_slots = sorted([ts for ts in time_slots if ts.get("day") == d], key=lambda x: x.get("index", 0))
            if not day_slots:
                continue
            occupied = {e.get("slot_index") for e in entries if e.get("class_name") == cls and e.get("day") == d}
            vec = [1 if ts.get("index") in occupied else 0 for ts in day_slots]
            if sum(vec) <= 1:
                continue
            for i in range(len(vec) - 2):
                if vec[i] == 1 and vec[i+1] == 0 and vec[i+2] == 1:
                    gaps.append({"class": cls, "day": d, "start_slot": day_slots[i]["index"]})
                    break
    print("zero_gap_violations:", json.dumps(gaps, ensure_ascii=False))

if __name__ == "__main__":
    main()




