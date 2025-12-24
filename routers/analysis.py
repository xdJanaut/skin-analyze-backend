from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pathlib import Path
import shutil
from datetime import datetime
from model.schemas import AnalysisResponse, AcneDetection
from services.roboflow import analyze_image, analyze_secondary
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

# Classes to exclude from detection
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
    base_score = 95
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
    return max(30, min(95, int(final_score)))

def calculate_secondary_score(detection_summary: dict, avg_confidence: float) -> int:
    """Calculate score for secondary skin conditions (melasma, rosacea)"""
    base_score = 95
    total_penalty = 0
    
    secondary_weights = {
        'acne': 6,
        'Acne': 6,
        'melasma': 7,
        'Melasma': 7,
        'rosacea': 8,
        'Rosacea': 8,
    }
    
    for condition_type, count in detection_summary.items():
        weight = secondary_weights.get(condition_type, 5)
        
        if count <= 2:
            penalty = count * weight
        elif count <= 5:
            penalty = (2 * weight) + ((count - 2) * (weight * 1.2))
        else:
            penalty = (2 * weight) + (3 * weight * 1.2) + ((count - 5) * (weight * 1.0))
        
        total_penalty += penalty
    
    total_penalty = min(total_penalty, 70)
    final_score = base_score - total_penalty
    
    print(f"🔢 Secondary score calculation: base={base_score}, penalty={total_penalty}, final={final_score}")
    
    return max(30, min(95, int(final_score)))

def combine_scores(primary_score: int, primary_summary: dict, secondary_score: int, secondary_summary: dict) -> int:
    """
    Smart merge: Only apply penalties for conditions that the primary model didn't detect
    This prevents double-penalization when both models detect the same issues
    """
    combined = primary_score
    
    secondary_weights = {
        'acne': 6,
        'Acne': 6,
        'melasma': 7,
        'Melasma': 7,
        'rosacea': 8,
        'Rosacea': 8,
    }
    
    has_primary_acne = any(
        key in primary_summary 
        for key in ['Acne', 'Pimples', 'papular', 'cystic', 'purulent', 'conglobata']
    )
    
    additional_penalty = 0
    unique_conditions = []
    
    print(f"🔍 Smart merge analysis:")
    print(f"   Primary detected acne: {has_primary_acne}")
    print(f"   Primary summary: {primary_summary}")
    print(f"   Secondary summary: {secondary_summary}")
    
    for condition_type, count in secondary_summary.items():
        condition_lower = condition_type.lower()
        is_acne_condition = condition_lower in ['acne'] or condition_type in ['Acne']
        
        if is_acne_condition and has_primary_acne:
            print(f"   ⏭️  Skipping {condition_type} (already detected by primary)")
            continue
        
        weight = secondary_weights.get(condition_type, 5)
        
        if count <= 2:
            penalty = count * weight
        elif count <= 5:
            penalty = (2 * weight) + ((count - 2) * (weight * 1.2))
        else:
            penalty = (2 * weight) + (3 * weight * 1.2) + ((count - 5) * (weight * 1.0))
        
        additional_penalty += penalty
        unique_conditions.append(f"{count}x {condition_type}")
        print(f"   ➕ Adding penalty for {condition_type}: {penalty} (unique condition)")
    
    combined = primary_score - int(additional_penalty)
    combined = max(30, min(95, combined))
    
    print(f"🔢 Smart merge result:")
    print(f"   Primary score: {primary_score}")
    print(f"   Unique secondary conditions: {', '.join(unique_conditions) if unique_conditions else 'None'}")
    print(f"   Additional penalty: {int(additional_penalty)}")
    print(f"   Combined score: {combined}")
    
    return combined

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
    
    if total_concerns == 0:
        severity = "clear"
    elif total_concerns <= 5:
        severity = "mild"
    elif total_concerns <= 15:
        severity = "moderate"
    else:
        severity = "severe"

    return severity, feedback, recommendations

def determine_severity_from_score(score: int) -> str:
    """Determine severity based on skin health score"""
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
        
        # PRIMARY ANALYSIS
        print(f"=" * 60)
        print(f"🔬 STARTING PRIMARY ANALYSIS")
        print(f"=" * 60)
        
        roboflow_result = analyze_image(str(file_path))
        
        filtered_predictions = [
            pred for pred in roboflow_result.get("predictions", [])
            if pred.get("class", "").lower() not in EXCLUDED_CLASSES
        ]
        
        print(f"🔍 Filtered out {len(roboflow_result.get('predictions', [])) - len(filtered_predictions)} freckle detections")
        
        detections = []
        total_confidence = 0
        detection_summary = {}
        
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
        
        print(f"📊 Primary detection breakdown: {detection_summary}")
        
        skin_score = calculate_skin_score_multi(detection_summary, avg_confidence)
        _, feedback, recommendations = generate_feedback_multi(detection_summary, avg_confidence)
        severity = determine_severity_from_score(skin_score)
        
        print(f"✅ Primary analysis complete: {total_concerns} total concerns, score: {skin_score}/100")
        
        # SECONDARY ANALYSIS
        secondary_triggered = False
        secondary_detections = None
        secondary_summary = None
        secondary_score = None
        combined_score = None
        
        all_detections_for_image = []
        model_sources = []
        
        for pred in filtered_predictions:
            all_detections_for_image.append(pred)
            model_sources.append('primary')
        
        print(f"=" * 60)
        print(f"🔬 RUNNING SECONDARY ANALYSIS")
        print(f"=" * 60)
        secondary_triggered = True
        
        try:
            secondary_result = analyze_secondary(str(file_path))
            secondary_predictions = secondary_result.get("predictions", [])
            
            print(f"🔍 Secondary model returned {len(secondary_predictions)} predictions")
            
            secondary_detections = []
            secondary_summary = {}
            secondary_total_confidence = 0
            
            for prediction in secondary_predictions:
                class_name = prediction.get("class", "unknown")
                confidence = prediction.get("confidence", 0)
                print(f"  - Detected: {class_name} (confidence: {confidence:.2f})")
                
                detection = AcneDetection(
                    x=prediction["x"],
                    y=prediction["y"],
                    width=prediction["width"],
                    height=prediction["height"],
                    confidence=prediction["confidence"],
                    class_name=class_name
                )
                secondary_detections.append(detection)
                secondary_total_confidence += prediction["confidence"]
                secondary_summary[class_name] = secondary_summary.get(class_name, 0) + 1
                
                all_detections_for_image.append(prediction)
                model_sources.append('secondary')
            
            print(f"📊 Secondary detection summary: {secondary_summary}")
            
            secondary_avg_confidence = (
                secondary_total_confidence / len(secondary_predictions) 
                if secondary_predictions else 0
            )
            
            secondary_score = calculate_secondary_score(secondary_summary, secondary_avg_confidence)
            combined_score = combine_scores(skin_score, detection_summary, secondary_score, secondary_summary)
            
            print(f"📊 Secondary analysis - Conditions: {len(secondary_predictions)}, Score: {secondary_score}/100")
            print(f"🎯 Combined score: {combined_score}/100")
            print(f"=" * 60)
            
            # Update feedback if secondary found issues
            if secondary_summary:
                secondary_concerns = ", ".join([
                    f"{count} {condition.replace('_', ' ').title()}"
                    for condition, count in secondary_summary.items()
                ])
                
                if not detection_summary or len(detection_summary) == 0:
                    total_secondary = sum(secondary_summary.values())
                    if total_secondary <= 5:
                        feedback = f"Analysis detected: {secondary_concerns}. This is considered mild."
                    elif total_secondary <= 15:
                        feedback = f"Analysis detected: {secondary_concerns}. This is considered moderate."
                    else:
                        feedback = f"Analysis detected: {secondary_concerns}. This is considered severe."
                else:
                    if feedback.endswith("!"):
                        feedback = f"{feedback[:-1]}. Additional analysis detected: {secondary_concerns}."
                    else:
                        feedback = f"{feedback} Additional analysis detected: {secondary_concerns}."
                        
        except Exception as e:
            print(f"⚠️ Secondary analysis failed: {str(e)}")
            print(f"=" * 60)
        
        annotated_filename = f"annotated_{datetime.now().timestamp()}{file_path.suffix}"
        annotated_path = ANNOTATED_DIR / annotated_filename
        
        draw_detections(
            str(file_path), 
            all_detections_for_image, 
            str(annotated_path),
            model_sources=model_sources
        )
        
        print(f"📸 Annotated image saved: {annotated_path}")
        
        # CHANGED: Calculate final score AND final severity based on combined score
        final_score_for_db = combined_score if combined_score is not None else skin_score
        final_severity = determine_severity_from_score(final_score_for_db)
        print(f"💾 Final score for database: {final_score_for_db}")
        print(f"💾 Final severity for database: {final_severity}")
        
        if current_user:
            try:
                user = db.query(User).filter(User.username == current_user).first()
                if user:
                    new_analysis = Analysis(
                        user_id=user.id,
                        acne_count=total_concerns,
                        severity=final_severity,  # CHANGED: Use final_severity based on combined score
                        score=final_score_for_db,
                        image_path=f"/annotated/{annotated_filename}",
                        created_at=datetime.now(),
                        detection_summary=json.dumps(detection_summary),
                        secondary_summary= json.dumps(secondary_summary) if secondary_summary else None,
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
            annotated_image_url=f"/annotated/{annotated_filename}",
            secondary_analysis_triggered=secondary_triggered,
            secondary_detections=secondary_detections,
            secondary_summary=secondary_summary,
            secondary_score=secondary_score,
            combined_score=combined_score
        )
    
    except Exception as e:
        print(f"❌ Error during analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    
    finally:
        if file_path.exists():
            file_path.unlink()
            print(f"🗑️ Cleaned up temporary file")