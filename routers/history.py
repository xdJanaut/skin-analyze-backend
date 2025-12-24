import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal, Analysis, User
from auth import get_current_user
from typing import List

router = APIRouter(prefix="/api", tags=["history"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/history")
async def get_history(
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == current_user).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    analyses = db.query(Analysis).filter(Analysis.user_id == user.id).order_by(Analysis.created_at.desc()).all()
    
    return {
        "history": [
            {
                "id": analysis.id,
                "acne_count": analysis.acne_count,
                "score": analysis.score,
                "severity": analysis.severity,
                "date": analysis.created_at.isoformat(),
                "image_path": analysis.image_path,
                "feedback": analysis.feedback,
                "recommendations": json.loads(analysis.recommendations) if isinstance(analysis.recommendations, str) else analysis.recommendations,
                "detection_summary": json.loads(analysis.detection_summary) if isinstance(analysis.detection_summary, str) else analysis.detection_summary,
                # ADD THIS - return secondary_summary if it exists
                "secondary_summary": json.loads(analysis.secondary_summary) if hasattr(analysis, 'secondary_summary') and isinstance(analysis.secondary_summary, str) else (analysis.secondary_summary if hasattr(analysis, 'secondary_summary') else {})
            }
            for analysis in analyses
        ]
    }

@router.delete("/history/{analysis_id}")
async def delete_analysis(
    analysis_id: int,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a specific analysis by ID"""
    user = db.query(User).filter(User.username == current_user).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == user.id
    ).first()
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found or you don't have permission to delete it")
    
    db.delete(analysis)
    db.commit()
    
    print(f"✅ Deleted analysis {analysis_id} for user {current_user}")
    
    return {"message": "Analysis deleted successfully", "id": analysis_id}