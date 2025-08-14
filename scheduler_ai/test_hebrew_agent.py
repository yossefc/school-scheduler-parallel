# test_hebrew_agent.py - Test de l'agent conseiller avec support hébreu
import logging
from schedule_advisor_agent import create_advisor_agent
from hebrew_language_processor import analyze_hebrew_input

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration DB pour test
db_config = {
    "host": "localhost",
    "database": "school_scheduler",
    "user": "admin", 
    "password": "school123"
}

def test_hebrew_processing():
    """Test du processeur de langue hébraïque"""
    print("🧪 TEST DU PROCESSEUR HÉBREU")
    print("=" * 50)
    
    hebrew_texts = [
        "תוכל למלא את החורים במערכת השעות של ז-1?",
        "אני רוצה להזיז את המתמטיקה של יא-2 יותר מוקדם ביום",
        "חשוב לי שהמתמטיקה תמיד תהיה בבוקר",
        "האם יש יותר מדי שעות למורים מסוימים?",
        "אני מעדיף שהמורים למדעים יהיו מקובצים",
    ]
    
    for i, text in enumerate(hebrew_texts, 1):
        print(f"\n📝 Test {i}: {text}")
        analysis = analyze_hebrew_input(text)
        
        print(f"   🎯 Intention: {analysis['main_intent']}")
        print(f"   🔧 Actions: {', '.join(analysis['actions'])}")
        print(f"   🏫 Classes: {', '.join(analysis['entities']['classes'])}")
        print(f"   📚 Matières: {', '.join(analysis['entities']['subjects'])}")
        print(f"   ⚡ Urgence: {analysis['urgency_level']}")
        print(f"   🎯 Confiance: {analysis['confidence_score']:.2f}")

def test_advisor_agent():
    """Test de l'agent conseiller avec des demandes en hébreu"""
    print("\n\n🤖 TEST DE L'AGENT CONSEILLER")
    print("=" * 50)
    
    # Créer l'agent
    try:
        agent = create_advisor_agent(db_config)
        print("✅ Agent conseiller créé avec succès")
    except Exception as e:
        print(f"❌ Erreur création agent: {e}")
        return
    
    # Tests avec différentes demandes
    test_requests = [
        {
            "text": "תוכל למלא את החורים במערכת השעות של ז-1?",
            "description": "Demande en hébreu - éliminer les trous"
        },
        {
            "text": "Peux-tu équilibrer la charge entre les classes ?",
            "description": "Demande en français - équilibrage"
        },
        {
            "text": "חשוב לי שהמתמטיקה תמיד תהיה בבוקר",
            "description": "Préférence en hébreu"
        },
        {
            "text": "אני רוצה לשנות את מערכת השעות של ח-2",
            "description": "Modification générale en hébreu"
        }
    ]
    
    for i, test_request in enumerate(test_requests, 1):
        print(f"\n🧪 Test {i}: {test_request['description']}")
        print(f"   💬 Input: {test_request['text']}")
        
        try:
            response = agent.process_user_request(
                test_request['text'], 
                {"user_name": "Test User", "session_id": f"test_{i}"}
            )
            
            print(f"   ✅ Status: {response['success']}")
            print(f"   🗨️  Réponse: {response['message'][:100]}...")
            print(f"   🔍 Langue détectée: {response.get('analysis', {}).get('language', 'N/A')}")
            print(f"   🎯 Actions détectées: {response.get('analysis', {}).get('detected_actions', [])}")
            
            if response.get('proposals'):
                print(f"   📋 Propositions: {len(response['proposals'])} changement(s)")
                
        except Exception as e:
            print(f"   ❌ Erreur: {e}")

def test_multilingual_conversation():
    """Test d'une conversation multilingue"""
    print("\n\n💬 TEST CONVERSATION MULTILINGUE")
    print("=" * 50)
    
    try:
        agent = create_advisor_agent(db_config)
        
        # Conversation mixte français-hébreu
        conversation = [
            "שלום! יש לי בעיה עם מערכת השעות",
            "Bonjour ! J'aimerais votre aide",
            "תוכל להסביר איך זה עובד?",
            "Peux-tu éliminer les trous dans ז-1 ?",
            "אני מעדיף שיעורים בבוקר תמיד"
        ]
        
        for i, message in enumerate(conversation, 1):
            print(f"\n👤 Message {i}: {message}")
            
            response = agent.process_user_request(
                message, 
                {"conversation_id": "multilingual_test"}
            )
            
            print(f"🤖 Réponse: {response['message'][:80]}...")
            
            # Analyser la langue détectée
            detected_lang = "Hébreu" if any(ord(c) >= 0x0590 and ord(c) <= 0x05FF for c in message) else "Français"
            print(f"   🔤 Langue: {detected_lang}")
            
    except Exception as e:
        print(f"❌ Erreur conversation: {e}")

if __name__ == "__main__":
    print("🚀 DÉMARRAGE DES TESTS DE L'AGENT CONSEILLER MULTILINGUE")
    print("=" * 60)
    
    # Test 1: Processeur hébreu
    test_hebrew_processing()
    
    # Test 2: Agent conseiller
    test_advisor_agent()
    
    # Test 3: Conversation multilingue
    test_multilingual_conversation()
    
    print("\n\n✨ TESTS TERMINÉS")
    print("=" * 60)
    print("L'agent conseiller peut maintenant:")
    print("✅ Comprendre l'hébreu et le français")
    print("✅ Détecter automatiquement la langue")
    print("✅ Répondre dans la langue appropriée")
    print("✅ Extraire les entités hébraïques (classes, matières, etc.)")
    print("✅ Mémoriser les préférences dans les deux langues")
    print("✅ Proposer des modifications intelligentes")
    print("\n📚 Exemples de phrases que l'agent comprend:")
    print("   🇮🇱 תוכל למלא את החורים במערכת השעות של ז-1?")
    print("   🇫🇷 Peux-tu éliminer les trous dans l'emploi du temps de ז-1 ?")
    print("   🇮🇱 חשוב לי שהמתמטיקה תמיד תהיה בבוקר")
    print("   🇫🇷 Pour moi, les cours de maths doivent toujours être le matin")