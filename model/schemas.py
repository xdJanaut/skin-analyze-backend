from pydantic import BaseModel
from typing import List, Optional
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

