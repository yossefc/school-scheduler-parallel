"""Modèles SQLAlchemy pour la persistance"""
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, Boolean, DateTime, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from typing import Dict, Any
import os

# Base déclarative SQLAlchemy pure
Base = declarative_base()

# Configuration de la base de données
DATABASE_URL = os.environ.get(
    'DATABASE_URL', 
    'postgresql://admin:school123@postgres:5432/school_scheduler'
)

# Engine et session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Constraint(Base):
    """Table des contraintes - adaptée au schéma existant"""
    __tablename__ = 'constraints'
    
    # Colonnes existantes dans la DB
    constraint_id = Column('constraint_id', Integer, primary_key=True)
    constraint_type = Column('constraint_type', String(50), nullable=False)
    entity_type = Column('entity_type', String(50))
    entity_name = Column('entity_name', String(100))
    constraint_data = Column('constraint_data', JSON, nullable=False)
    priority = Column('priority', Integer, default=1)
    is_active = Column('is_active', Boolean, default=True)
    created_at = Column('created_at', DateTime, default=datetime.utcnow)
    
    # Propriétés calculées pour compatibilité avec le code existant
    @property
    def id(self):
        return self.constraint_id
    
    @property
    def type(self):
        return self.constraint_type
    
    @property
    def entity(self):
        # Combiner entity_type et entity_name si nécessaire
        if self.entity_name:
            return self.entity_name
        return self.entity_type or ""
    
    @property
    def data(self):
        return self.constraint_data or {}
    
    @property
    def constraint_metadata(self):
        return self.constraint_data.get('metadata', {}) if self.constraint_data else {}
    
    @property
    def original_text(self):
        return self.constraint_data.get('original_text') if self.constraint_data else None
    
    @property
    def confidence(self):
        return self.constraint_data.get('confidence') if self.constraint_data else None
    
    @property
    def created_by(self):
        return self.constraint_data.get('created_by') if self.constraint_data else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            'id': self.id,
            'type': self.type,
            'entity': self.entity,
            'data': self.data,
            'priority': self.priority,
            'constraint_metadata': self.constraint_metadata,
            'original_text': self.original_text,
            'confidence': self.confidence,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by,
            'is_active': self.is_active
        }

# Fonctions utilitaires pour compatibilité
def get_db_session():
    """Retourne une session de base de données"""
    return SessionLocal()

def create_tables():
    """Crée toutes les tables"""
    Base.metadata.create_all(bind=engine)