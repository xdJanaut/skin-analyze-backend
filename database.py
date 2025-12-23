from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# SQLite database
SQLALCHEMY_DATABASE_URL = "sqlite:///./acne_analyzer.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# User model
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    analyses = relationship("Analysis", back_populates="user")

class Analysis(Base):
    __tablename__ = "analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    acne_count = Column(Integer)
    severity = Column(String)  # "Clear", "Mild", "Moderate", "Severe"
    score = Column(Float)  # 0-100 skin health score
    image_path = Column(String, nullable=True)  # Optional: store image path
    notes = Column(Text, nullable=True)  # Optional: user notes
    created_at = Column(DateTime, default=datetime.utcnow)
    detection_summary = Column(Text, nullable=True)  # JSON string
    feedback = Column(Text, nullable=True)
    recommendations = Column(Text, nullable=True) 
    
    # Relationship to user
    user = relationship("User", back_populates="analyses")


# Create all tables
Base.metadata.create_all(bind=engine)