from database import SessionLocal, Analysis

def determine_severity_from_score(score: int) -> str:
    if score >= 85:
        return "clear"
    elif score >= 70:
        return "mild"
    elif score >= 50:
        return "moderate"
    else:
        return "severe"

db = SessionLocal()

# Get all analyses
analyses = db.query(Analysis).all()

print(f"Found {len(analyses)} analyses to check")

for analysis in analyses:
    old_severity = analysis.severity
    correct_severity = determine_severity_from_score(analysis.score)
    
    if old_severity != correct_severity:
        print(f"Fixing Analysis {analysis.id}: score={analysis.score}, {old_severity} → {correct_severity}")
        analysis.severity = correct_severity

# Save changes
db.commit()
print("✅ All severities updated!")

db.close()