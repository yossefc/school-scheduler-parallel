# fuzzy_hebrew_matching.py
class HebrewFuzzyMatcher:
    def __init__(self):
        self.threshold = 0.8
    
    def match(self, str1, str2):
        if not str1 or not str2:
            return 0.0
        s1, s2 = str1.lower().strip(), str2.lower().strip()
        if s1 == s2:
            return 1.0
        if s1 in s2 or s2 in s1:
            return 0.8
        common = sum(1 for c in s1 if c in s2)
        return common / max(len(s1), len(s2))
