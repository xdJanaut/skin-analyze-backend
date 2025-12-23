from pathlib import Path
from dotenv import load_dotenv
import os
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from database import SessionLocal, User, Analysis, Base, engine  # ADDED: Analysis
from auth import hash_password, verify_password, create_access_token, get_current_user
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json

from database import Base, engine

# Create all tables on startup
print("🔧 Creating database tables...")
Base.metadata.create_all(bind=engine)
print("✅ Database tables ready!")

class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
print("ROBOFLOW_API_KEY loaded?", bool(os.getenv("ROBOFLOW_API_KEY")))

app = FastAPI()

from routers import analysis  

os.makedirs("annotated", exist_ok=True)
app.mount("/annotated", StaticFiles(directory="annotated"), name="annotated")
app.include_router(analysis.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "SkinAnalyze Backend API is running."}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/register")
async def register(user: UserRegister, db: Session = Depends(get_db)):
    # Check if username exists
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Check if email exists
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash the password
    try:
        hashed_pwd = hash_password(user.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Create new user
    new_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_pwd
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"message": "User registered successfully", "username": user.username}

@app.post("/login")
async def login(user: UserLogin, db: Session = Depends(get_db)):
    # Find user
    db_user = db.query(User).filter(User.username == user.username).first()
    
    # Verify password
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Create token
    access_token = create_access_token(data={"sub": db_user.username})
    
    # Return token
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "username": db_user.username
    }

@app.get("/history")
async def get_analysis_history(
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all analysis history for the logged-in user.
    Returns analyses sorted by date (newest first).
    """
    # Get user
    user = db.query(User).filter(User.username == current_user).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get all analyses for this user, sorted by date
    analyses = db.query(Analysis).filter(
        Analysis.user_id == user.id
    ).order_by(Analysis.created_at.desc()).all()
    
    # Format results
    history = []
    for analysis in analyses:
        history.append({
            "id": analysis.id,
            "acne_count": analysis.acne_count,
            "severity": analysis.severity,
            "score": analysis.score,
            "date": analysis.created_at.isoformat(),
            "notes": analysis.notes,
            "image_path": analysis.image_path,
            "detection_summary": json.loads(analysis.detection_summary) if analysis.detection_summary else {},
            "feedback": analysis.feedback,
            "recommendations": json.loads(analysis.recommendations) if analysis.recommendations else []
        })
    
    return {
        "username": current_user,
        "total_analyses": len(history),
        "history": history
    }
# ============================================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)