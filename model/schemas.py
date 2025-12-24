from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

class AcneDetection(BaseModel):
    x: float
    y: float
    width: float
    height: float
    confidence: float
    class_name: str  

class AnalysisResponse(BaseModel):
    acne_count: int
    skin_score: int
    average_confidence: float
    detections: List[AcneDetection]
    detection_summary: dict  
    feedback: str
    severity: str
    recommendations: List[str]
    timestamp: datetime
    annotated_image_url: str 
    secondary_analysis_triggered: bool = False
    secondary_detections: Optional[List[AcneDetection]] = None
    secondary_summary: Optional[Dict[str, int]] = None
    secondary_score: Optional[int] = None
    combined_score: Optional[int] = None

class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
