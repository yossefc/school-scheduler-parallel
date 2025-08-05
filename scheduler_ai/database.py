# database.py
from sqlalchemy import create_engine, Column, Integer, String, Boolean, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class Constraint(Base):
    __tablename__ = 'constraints'
    
    constraint_id = Column(Integer, primary_key=True)
    constraint_type = Column(String(50))
    entity_name = Column(String(100))
    constraint_data = Column(JSON)
    priority = Column(Integer, default=3)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

def get_db_session():
    engine = create_engine('postgresql://admin:school123@localhost/school_scheduler')
    Session = sessionmaker(bind=engine)
    return Session()

def create_tables():
    # Créer les tables si nécessaire
    pass
