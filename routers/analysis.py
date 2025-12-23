from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pathlib import Path
import shutil
from datetime import datetime
from model.schemas import AnalysisResponse, AcneDetection
from services.roboflow import analyze_image 
from PIL import Image
import pillow_heif
from services.image_processor import draw_detections
from sqlalchemy.orm import Session
from database import SessionLocal, User, Analysis
from auth import get_current_user_optional
from typing import Optional
import json

ANNOTATED_DIR = Path("annotated")
ANNOTATED_DIR.mkdir(exist_ok=True)

pillow_heif.register_heif_opener()

router = APIRouter(prefix= "/api", tags= ["analysis"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# ADD THIS: Classes to exclude from detection
EXCLUDED_CLASSES = {'freckles', 'freckle', 'Freckles', 'Freckle'}

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def generate_feedback(acne_count: int, avg_confidence: float):
    if acne_count == 0:
        severity = "clear"
        feedback = "Great news! No acne detected. Your skin looks clear!"
        recommendations = [
            "Maintain your current skincare routine",
            "Continue using sunscreen daily",
            "Stay hydrated and get enough sleep"
        ]
    elif acne_count <= 5:
        severity = "mild"
        feedback = f"You have {acne_count} acne spot(s) detected. This is considered mild acne."
        recommendations = [
            "Use a gentle cleanser twice daily",
            "Apply a spot treatment with benzoyl peroxide or salicylic acid",
            "Avoid touching your face throughout the day",
            "Change pillowcases regularly"
        ]
    elif acne_count <= 15:
        severity = "moderate"
        feedback = f"You have {acne_count} acne spots detected. This is moderate acne."
        recommendations = [
            "Use a cleanser with salicylic acid or benzoyl peroxide",
            "Consider adding a retinoid to your nighttime routine",
            "Avoid heavy, oily products",
            "If no improvement in 6-8 weeks, consult a dermatologist"
        ]
    else:
        severity = "severe"
        feedback = f"You have {acne_count} acne spots detected. This is considered severe acne."
        recommendations = [
            "We recommend consulting a dermatologist soon",
            "Prescription treatments may be necessary",
            "Avoid picking or squeezing acne",
            "Use non-comedogenic (won't clog pores) products only",
            "Consider dietary factors (dairy, high-glycemic foods)"
        ]
    
    return severity, feedback, recommendations

def calculate_skin_score_multi(detection_summary: dict, avg_confidence: float) -> int:
    base_score = 100
    total_penalty = 0
    
    severity_weights = {
        'cystic': 8,
        'purulent': 7,
        'Acne': 6,
        'conglobata': 8,
        'Pimples': 5,
        'papular': 5,
        'whitehead': 4,
        'blackhead': 4,
        'acne_scars': 4,
        'keloid': 5,
        'folliculitis': 3,
        'milium': 2,
        'crystalline': 2,
        'flat_wart': 3,
        'syringoma': 2,
        'sebo-crystan-conglo': 5,
    }
    
    for condition_type, count in detection_summary.items():
        weight = severity_weights.get(condition_type, 4)
        
        if count <= 2:
            penalty = count * weight
        elif count <= 5:
            penalty = (2 * weight) + ((count - 2) * (weight * 1.2))
        elif count <= 10:
            penalty = (2 * weight) + (3 * weight * 1.2) + ((count - 5) * (weight * 1.0))
        else:
            penalty = (2 * weight) + (3 * weight * 1.2) + (5 * weight) + ((count - 10) * (weight * 0.8))
        
        total_penalty += penalty
    
    total_penalty = min(total_penalty, 70)
    final_score = base_score - total_penalty
    return max(30, min(100, int(final_score)))

def generate_feedback_multi(detection_summary: dict, avg_confidence: float):
    total_concerns = sum(detection_summary.values())
    
    if total_concerns == 0:
        return "clear", "Great news! No skin concerns detected. Your skin looks healthy!", [
            "Maintain your current skincare routine",
            "Continue using sunscreen daily (SPF 30+)",
            "Stay hydrated and get adequate sleep",
            "Cleanse gently twice daily"
        ]
    
    concerns = []
    for condition_type, count in detection_summary.items():
        readable_name = condition_type.replace('_', ' ').title()
        concerns.append(f"{count} {readable_name}")
    
    concern_text = ", ".join(concerns)
    feedback = f"Analysis detected: {concern_text}."
    
    recommendations = []
    seen_recommendations = set()
    
    if any(key in detection_summary for key in ['cystic', 'purulent', 'Acne', 'conglobata', 'Pimples']):
        recs = [
            "Use a gentle cleanser with salicylic acid (2%) or benzoyl peroxide (2.5-5%)",
            "Apply spot treatment to active breakouts",
            "Avoid touching or picking at your face",
            "Change pillowcases regularly"
        ]
        for rec in recs:
            if rec not in seen_recommendations:
                recommendations.append(rec)
                seen_recommendations.add(rec)
    
    if any(key in detection_summary for key in ['cystic', 'purulent', 'conglobata']):
        if detection_summary.get('cystic', 0) + detection_summary.get('purulent', 0) > 3:
            rec = "Consider consulting a dermatologist for prescription treatments (this may require professional care)"
            if rec not in seen_recommendations:
                recommendations.append(rec)
                seen_recommendations.add(rec)
    
    if 'blackhead' in detection_summary:
        recs = [
            "Use a BHA (salicylic acid) exfoliant 2-3 times per week",
            "Try oil cleansing to help dissolve sebum",
            "Consider professional extractions for stubborn blackheads"
        ]
        for rec in recs:
            if rec not in seen_recommendations:
                recommendations.append(rec)
                seen_recommendations.add(rec)
    
    if 'whitehead' in detection_summary:
        recs = [
            "Use products with salicylic acid to unclog pores",
            "Avoid heavy, pore-clogging moisturizers",
            "Don't squeeze whiteheads - let them heal naturally"
        ]
        for rec in recs:
            if rec not in seen_recommendations:
                recommendations.append(rec)
                seen_recommendations.add(rec)
    
    if 'acne_scars' in detection_summary:
        recs = [
            "Apply vitamin C serum to help fade scarring",
            "Use products with niacinamide for skin repair",
            "Always wear SPF 30+ to prevent darkening of scars",
            "Consider professional treatments (microneedling, laser) for severe scarring"
        ]
        for rec in recs:
            if rec not in seen_recommendations:
                recommendations.append(rec)
                seen_recommendations.add(rec)
    
    if 'milium' in detection_summary:
        rec = "Milia may require professional extraction - avoid trying to remove them yourself"
        if rec not in seen_recommendations:
            recommendations.append(rec)
            seen_recommendations.add(rec)
    
    if len(recommendations) < 3:
        general_recs = [
            "Maintain a consistent skincare routine",
            "Avoid harsh scrubbing or over-exfoliation",
            "Keep hair and hands away from your face"
        ]
        for rec in general_recs:
            if rec not in seen_recommendations and len(recommendations) < 5:
                recommendations.append(rec)
                seen_recommendations.add(rec)
    
    return feedback, recommendations

def determine_severity_from_score(score: int) -> str:
    """
    Determine severity based on skin health score
    """
    if score >= 85:
        return "clear"
    elif score >= 70:
        return "mild"
    elif score >= 50:
        return "moderate"
    else:
        return "severe"

def convert_heic_to_jpg(heic_path: Path) -> Path:
    try:
        print(f"🔄 Converting HEIC to JPG: {heic_path}")
        image = Image.open(heic_path)
        jpg_path = heic_path.with_suffix('.jpg')
        image.convert('RGB').save(jpg_path, 'JPEG', quality=95)
        heic_path.unlink()
        print(f"✅ Converted to: {jpg_path}")
        return jpg_path
    except Exception as e:
        print(f"❌ HEIC conversion failed: {str(e)}")
        raise HTTPException(status_code=400, detail="Failed to process HEIC image")

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_face(
    file: UploadFile = File(...),
    current_user: Optional[str] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    allowed_types = ["image/jpeg", "image/png", "image/heic", "image/heif", "image/webp"]
    if file.content_type not in allowed_types and not file.filename.lower().endswith(('.heic', '.heif')):
        raise HTTPException(status_code=400, detail="File must be an image (JPG, PNG, HEIC, WebP)")
    
    file_path = UPLOAD_DIR / f"{datetime.now().timestamp()}_{file.filename}"
    
    try:
        contents = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(contents)
        
        print(f"📁 File saved to: {file_path}")
        
        if file.filename.lower().endswith(('.heic', '.heif')):
            file_path = convert_heic_to_jpg(file_path)
        
        roboflow_result = analyze_image(str(file_path))
        
        # MODIFIED: Filter out freckles from predictions
        filtered_predictions = [
            pred for pred in roboflow_result.get("predictions", [])
            if pred.get("class", "").lower() not in EXCLUDED_CLASSES
        ]
        
        print(f"🔍 Filtered out {len(roboflow_result.get('predictions', [])) - len(filtered_predictions)} freckle detections")
        
        annotated_filename = f"annotated_{datetime.now().timestamp()}{file_path.suffix}"
        annotated_path = ANNOTATED_DIR / annotated_filename

        # MODIFIED: Use filtered predictions for annotation
        draw_detections(str(file_path), filtered_predictions, str(annotated_path))
        print(f"📸 Annotated image saved: {annotated_path}")
        
        detections = []
        total_confidence = 0
        detection_summary = {}
        
        # MODIFIED: Process only filtered predictions
        for prediction in filtered_predictions:
            class_name = prediction.get("class", "unknown")
            detection = AcneDetection(
                x=prediction["x"],
                y=prediction["y"],
                width=prediction["width"],
                height=prediction["height"],
                confidence=prediction["confidence"],
                class_name=class_name
            )
            detections.append(detection)
            total_confidence += prediction["confidence"]
            detection_summary[class_name] = detection_summary.get(class_name, 0) + 1
        
        total_concerns = len(detections)
        avg_confidence = total_confidence / total_concerns if total_concerns > 0 else 0
        print(f"📊 Detection breakdown: {detection_summary}")
        
        skin_score = calculate_skin_score_multi(detection_summary, avg_confidence)
        feedback, recommendations = generate_feedback_multi(detection_summary, avg_confidence)
        severity = determine_severity_from_score(skin_score)
        print(f"✅ Analysis complete: {total_concerns} total concerns, score: {skin_score}/100")
        
        if current_user:
            try:
                user = db.query(User).filter(User.username == current_user).first()
                if user:
                    new_analysis = Analysis(
                        user_id=user.id,
                        acne_count=total_concerns,
                        severity=severity,
                        score=skin_score,
                        image_path=f"/annotated/{annotated_filename}",
                        created_at=datetime.now(),
                        detection_summary=json.dumps(detection_summary),
                        feedback=feedback,
                        recommendations=json.dumps(recommendations),
                    )
                    db.add(new_analysis)
                    db.commit()
                    db.refresh(new_analysis)
                    print(f"💾 Analysis saved to history for user: {current_user}")
            except Exception as e:
                print(f"⚠️ Failed to save analysis to database: {str(e)}")
        else:
            print(f"👤 Anonymous user - analysis not saved to history")
        
        return AnalysisResponse(
            acne_count=total_concerns,
            skin_score=skin_score,
            average_confidence=avg_confidence,
            detections=detections,
            detection_summary=detection_summary,
            feedback=feedback,
            severity=severity,
            recommendations=recommendations,
            timestamp=datetime.now(),
            annotated_image_url=f"/annotated/{annotated_filename}"
        )
    
    except Exception as e:
        print(f"❌ Error during analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    
    finally:
        if file_path.exists():
            file_path.unlink()
            print(f"🗑️ Cleaned up temporary file")