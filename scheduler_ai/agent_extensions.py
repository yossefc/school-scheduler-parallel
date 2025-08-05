# agent_extensions.py
class ClarificationMiddleware:
    def __init__(self):
        self.pending_clarifications = {}
    
    def process(self, constraint):
        if not constraint.get("entity"):
            return {
                "needs_clarification": True,
                "question": "Pour quelle entité cette contrainte s'applique-t-elle ?"
            }
        return {"needs_clarification": False}

clarification_middleware = ClarificationMiddleware()
