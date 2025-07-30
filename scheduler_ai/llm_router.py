"""
scheduler_ai/llm_router.py - Routeur intelligent pour choisir entre GPT-4o et Claude Opus
"""
import os
import json
import logging
import tiktoken
from typing import Dict, Any, List, Optional, Literal
from dataclasses import dataclass
from enum import Enum
import re

import openai
import anthropic
import httpx

logger = logging.getLogger(__name__)

class TaskComplexity(Enum):
    """Niveau de complexité de la tâche"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

@dataclass
class LLMResponse:
    """Structure de réponse LLM"""
    content: str
    model_used: str
    tokens_used: int
    confidence: float
    metadata: Dict[str, Any]

class LLMRouter:
    """Routeur intelligent pour sélectionner le bon modèle LLM"""
    
    def __init__(self):
        # Configuration des clients avec support proxy via httpx
        
        # Configuration du proxy via httpx si nécessaire
        proxy_url = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
        http_client = httpx.Client(proxies=proxy_url) if proxy_url else None
        
        try:
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key and api_key != "sk-...":
                self.openai_client = openai.OpenAI(
                    api_key=api_key,
                    http_client=http_client
                )
            else:
                self.openai_client = None
                logger.warning("OpenAI API key not configured")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            self.openai_client = None
            
        try:
            api_key = os.environ.get("ANTHROPIC_API_KEY") 
            if api_key and api_key != "claude-...":
                self.anthropic_client = anthropic.Anthropic(
                    api_key=api_key,
                    http_client=http_client
                )
            else:
                self.anthropic_client = None
                logger.warning("Anthropic API key not configured")
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {e}")
            self.anthropic_client = None
        
        # Tokenizer pour compter les tokens
        try:
            self.encoding = tiktoken.encoding_for_model("gpt-4")
        except:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        
        # Cache des patterns de contraintes
        self.constraint_patterns = self._load_constraint_patterns()
    
    def _load_constraint_patterns(self) -> Dict[str, Dict]:
        """Charge les patterns de reconnaissance des contraintes"""
        return {
            "teacher_availability": {
                "patterns": [
                    r"(.+) (?:ne peut pas|n'est pas disponible|absent) (?:le |les )?(.+)",
                    r"(.+) (?:לא יכול|לא זמין) (?:ב)?(.+)",
                ],
                "complexity": TaskComplexity.LOW
            },
            "time_preference": {
                "patterns": [
                    r"(?:les cours de |cours de )?(.+) (?:doivent être|uniquement) (?:le |en )?(.+)",
                    r"(.+) (?:רק|צריך להיות) (?:ב)?(.+)",
                ],
                "complexity": TaskComplexity.MEDIUM
            },
            "parallel_teaching": {
                "patterns": [
                    r"(.+) (?:et|avec) (.+) (?:enseignent ensemble|en parallèle)",
                    r"(.+) (?:ו)?(.+) (?:מלמדים ביחד|במקביל)",
                ],
                "complexity": TaskComplexity.HIGH
            },
            "complex_scheduling": {
                "keywords": ["réorganiser", "optimiser", "plusieurs classes", "trimestre entier"],
                "complexity": TaskComplexity.VERY_HIGH
            }
        }
    
    def choose_model(self, task_type: str, tokens: int, complexity: Optional[TaskComplexity] = None) -> str:
        """Choisit le modèle approprié selon la tâche"""
        # Si aucun client n'est configuré, retourner une erreur
        if not self.openai_client and not self.anthropic_client:
            return "none"
        
        if not complexity:
            complexity = self._estimate_complexity(task_type, tokens)
        
        # Logique simplifiée si un seul client est disponible
        if self.openai_client and not self.anthropic_client:
            return "openai/gpt-4o"
        elif self.anthropic_client and not self.openai_client:
            return "anthropic/claude-4-opus"
        
        # Logique normale si les deux sont disponibles
        if tokens > 100_000 or complexity == TaskComplexity.VERY_HIGH:
            return "anthropic/claude-4-opus"
        elif tokens > 30_000 and complexity == TaskComplexity.HIGH:
            return "hybrid"
        else:
            return "openai/gpt-4o"
    
    def _estimate_complexity(self, task_type: str, tokens: int) -> TaskComplexity:
        """Estime la complexité d'une tâche"""
        if task_type == "deep_reasoning" or tokens > 50_000:
            return TaskComplexity.VERY_HIGH
        elif task_type in ["parallel_scheduling", "conflict_resolution"]:
            return TaskComplexity.HIGH
        elif task_type in ["constraint_parsing", "simple_modification"]:
            return TaskComplexity.MEDIUM
        else:
            return TaskComplexity.LOW
    
    def parse_natural_language(self, text: str, language: Literal["fr", "he"] = "fr") -> Dict[str, Any]:
        """Parse une contrainte en langage naturel"""
        # Si aucun LLM n'est disponible, faire un parsing basique
        if not self.openai_client and not self.anthropic_client:
            return self._basic_parse(text)
        
        # Compter les tokens
        tokens = len(self.encoding.encode(text))
        
        # Détecter le type de contrainte
        constraint_type = self._detect_constraint_type(text)
        complexity = self.constraint_patterns.get(constraint_type, {}).get(
            "complexity", TaskComplexity.MEDIUM
        )
        
        # Choisir le modèle
        model = self.choose_model("constraint_parsing", tokens, complexity)
        
        if model == "none":
            return self._basic_parse(text)
        
        # Construire le prompt
        prompt = self._build_parsing_prompt(text, language, constraint_type)
        
        # Appeler le LLM
        try:
            if model.startswith("openai") and self.openai_client:
                response = self._call_openai(prompt, model="gpt-4o")
            elif self.anthropic_client:
                response = self._call_anthropic(prompt, model="claude-4-opus-20240514")
            else:
                return self._basic_parse(text)
            
            # Parser la réponse
            parsed = self._parse_llm_response(response.content)
            parsed["confidence"] = self._calculate_confidence(parsed, text)
            
            return parsed
        except Exception as e:
            logger.error(f"Error in parse_natural_language: {e}")
            return self._basic_parse(text)
    
    def _basic_parse(self, text: str) -> Dict[str, Any]:
        """Parsing basique sans LLM"""
        constraint_type = self._detect_constraint_type(text)
        
        # Extraire des entités basiques
        words = text.split()
        entity = "unknown"
        
        # Chercher des noms propres (mots avec majuscule)
        for word in words:
            if word and word[0].isupper() and word not in ["Le", "La", "Les"]:
                entity = word
                break
        
        return {
            "constraint": {
                "type": constraint_type if constraint_type != "unknown" else "custom",
                "entity": entity,
                "data": {"text": text},
                "priority": 3
            },
            "confidence": 0.3,
            "summary": f"Contrainte détectée: {text[:50]}...",
            "alternatives": []
        }
    
    def _detect_constraint_type(self, text: str) -> str:
        """Détecte le type de contrainte depuis le texte"""
        text_lower = text.lower()
        
        for constraint_type, config in self.constraint_patterns.items():
            # Vérifier les patterns regex
            if "patterns" in config:
                for pattern in config["patterns"]:
                    if re.search(pattern, text_lower):
                        return constraint_type
            
            # Vérifier les mots-clés
            if "keywords" in config:
                if any(keyword in text_lower for keyword in config["keywords"]):
                    return constraint_type
        
        return "unknown"
    
    def _build_parsing_prompt(self, text: str, language: str, constraint_type: str) -> str:
        """Construit le prompt pour parser une contrainte"""
        return f"""Tu es un expert en planification scolaire. Parse cette contrainte en langage naturel :

Texte : "{text}"
Langue : {language}
Type détecté : {constraint_type}

Retourne un JSON avec :
{{
    "constraint": {{
        "type": "string",
        "entity": "string", 
        "data": {{}},
        "priority": 0-5
    }},
    "summary": "résumé en français",
    "alternatives": []  // si ambiguïté
}}

Contexte : système scolaire israélien, semaine dimanche-vendredi."""
    
    def answer_question(self, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Répond à une question générale sur l'emploi du temps"""
        # Si pas de LLM, réponse basique
        if not self.openai_client and not self.anthropic_client:
            return {
                "answer": "Désolé, je ne peux pas répondre sans connexion à un service IA.",
                "model_used": "none",
                "references": []
            }
        
        # Enrichir le contexte
        enriched_context = self._enrich_context(context)
        tokens = len(self.encoding.encode(json.dumps(enriched_context)))
        
        # Choisir le modèle
        model = self.choose_model("question_answering", tokens)
        
        if model == "none":
            return {
                "answer": "Service IA non disponible.",
                "model_used": "none",
                "references": []
            }
        
        # Construire le prompt
        prompt = f"""Tu es l'assistant IA du système de planification scolaire.

Contexte :
{json.dumps(enriched_context, indent=2, ensure_ascii=False)}

Question : {question}

Réponds de manière claire et pédagogique. Si la question concerne des modifications, propose des actions concrètes."""
        
        # Appeler le LLM approprié
        try:
            if model.startswith("openai") and self.openai_client:
                response = self._call_openai(prompt)
            elif self.anthropic_client:
                response = self._call_anthropic(prompt)
            else:
                return {
                    "answer": "Service IA temporairement indisponible.",
                    "model_used": "none",
                    "references": []
                }
            
            return {
                "answer": response.content,
                "model_used": response.model_used,
                "references": self._extract_references(response.content)
            }
        except Exception as e:
            logger.error(f"Error in answer_question: {e}")
            return {
                "answer": f"Erreur: {str(e)}",
                "model_used": "error",
                "references": []
            }
    
    def _call_openai(self, prompt: str, model: str = "gpt-4o", **kwargs) -> LLMResponse:
        """Appelle l'API OpenAI"""
        if not self.openai_client:
            raise Exception("OpenAI client not initialized")
            
        try:
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Tu es un expert en planification scolaire."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                **kwargs
            )
            
            return LLMResponse(
                content=response.choices[0].message.content,
                model_used=model,
                tokens_used=response.usage.total_tokens,
                confidence=0.9,
                metadata={"finish_reason": response.choices[0].finish_reason}
            )
            
        except Exception as e:
            logger.error(f"Erreur OpenAI: {e}")
            raise
    
    def _call_anthropic(self, prompt: str, model: str = "claude-4-opus-20240514", **kwargs) -> LLMResponse:
        """Appelle l'API Anthropic"""
        if not self.anthropic_client:
            raise Exception("Anthropic client not initialized")
            
        try:
            response = self.anthropic_client.messages.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
                temperature=0.3,
                **kwargs
            )
            
            # Extraire le texte de la réponse
            content = response.content[0].text if response.content else ""
            
            return LLMResponse(
                content=content,
                model_used=model,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                confidence=0.95,
                metadata={"stop_reason": response.stop_reason}
            )
            
        except Exception as e:
            logger.error(f"Erreur Anthropic: {e}")
            raise
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse la réponse JSON du LLM"""
        try:
            # Extraire le JSON de la réponse
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                # Fallback : parser manuellement
                return self._manual_parse(response)
        except json.JSONDecodeError:
            logger.warning("Impossible de parser le JSON, fallback manuel")
            return self._manual_parse(response)
    
    def _manual_parse(self, response: str) -> Dict[str, Any]:
        """Parse manuel si le JSON échoue"""
        # Extraire les informations clés avec des regex
        constraint = {
            "type": "unknown",
            "entity": "unknown",
            "data": {},
            "priority": 3
        }
        
        # Chercher le type
        type_match = re.search(r'"type"\s*:\s*"([^"]+)"', response)
        if type_match:
            constraint["type"] = type_match.group(1)
        
        # Chercher l'entité
        entity_match = re.search(r'"entity"\s*:\s*"([^"]+)"', response)
        if entity_match:
            constraint["entity"] = entity_match.group(1)
        
        return {
            "constraint": constraint,
            "summary": "Contrainte extraite du texte",
            "alternatives": []
        }
    
    def _calculate_confidence(self, parsed: Dict, original_text: str) -> float:
        """Calcule le score de confiance du parsing"""
        confidence = 0.5
        
        # Vérifier la complétude
        if all(k in parsed["constraint"] for k in ["type", "entity", "data"]):
            confidence += 0.2
        
        # Vérifier la cohérence du type
        detected_type = self._detect_constraint_type(original_text)
        if detected_type != "unknown" and parsed["constraint"]["type"] == detected_type:
            confidence += 0.2
        
        # Vérifier si des alternatives sont proposées
        if not parsed.get("alternatives"):
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _enrich_context(self, context: Dict) -> Dict[str, Any]:
        """Enrichit le contexte avec des informations supplémentaires"""
        enriched = context.copy()
        
        # Ajouter des métadonnées système
        enriched["system"] = {
            "current_week": "2024-W45",
            "school_type": "college_lycee_israelien",
            "constraints_count": context.get("constraints_count", 0),
            "last_generation_score": context.get("last_score", 85)
        }
        
        return enriched
    
    def _extract_references(self, text: str) -> List[str]:
        """Extrait les références mentionnées dans la réponse"""
        references = []
        
        # Chercher les mentions de classes
        class_refs = re.findall(r'classe\s+(\S+)', text, re.IGNORECASE)
        references.extend([f"class:{ref}" for ref in class_refs])
        
        # Chercher les mentions de professeurs
        prof_refs = re.findall(r'(?:professeur|prof\.?)\s+(\S+)', text, re.IGNORECASE)
        references.extend([f"teacher:{ref}" for ref in prof_refs])
        
        return list(set(references))  # Éliminer les doublons
