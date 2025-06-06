from sqlalchemy import Column, Enum, Float, String, Integer, DateTime
from datetime import datetime
from sqlalchemy.orm import relationship
from api.db import Base
from api.utils.enums import IndustryEnum, InterestEnum  

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    id = Column(String(64), unique=True, nullable=False)        
    password = Column(String(128), nullable=False)
    name = Column(String(100), nullable=False) 
    industry = Column(Enum(IndustryEnum, name="industry_enum"))
    scale = Column(Integer, nullable=False)
    interests = Column(Enum(InterestEnum, name="interest_enum"))
    budget_size = Column(Float, nullable=False)
    created_date = Column(DateTime, default=datetime.utcnow)
    modified_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    reports = relationship("UserReport", back_populates="user")
    recommended_agents = relationship("RecommendedAgent", back_populates="user")