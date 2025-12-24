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

# UPDATED: Return data in the format frontend expects
@router.get("/history")
async def get_history(
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == current_user).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    analyses = db.query(Analysis).filter(Analysis.user_id == user.id).order_by(Analysis.created_at.desc()).all()
    
    # Format the response to match what frontend expects
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
                "detection_summary": json.loads(analysis.detection_summary) if isinstance(analysis.detection_summary, str) else analysis.detection_summary
            }
            for analysis in analyses
        ]
    }

# DELETE endpoint
@router.delete("/history/{analysis_id}")
async def delete_analysis(
    analysis_id: int,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a specific analysis by ID"""
    
    # Get the user
    user = db.query(User).filter(User.username == current_user).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Find the analysis
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == user.id  # Ensure user owns this analysis
    ).first()
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found or you don't have permission to delete it")
    
    # Delete the analysis
    db.delete(analysis)
    db.commit()
    
    print(f"✅ Deleted analysis {analysis_id} for user {current_user}")
    
    return {"message": "Analysis deleted successfully", "id": analysis_id}