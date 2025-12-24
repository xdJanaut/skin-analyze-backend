import os
import requests
from typing import Dict, Any

def analyze_image(image_path: str) -> Dict[str, Any]:
    """Primary acne detection model"""
    # ✅ Read env vars at runtime (after load_dotenv has run)
    api_key = os.getenv("ROBOFLOW_API_KEY")
    model = os.getenv("ROBOFLOW_MODEL")
    version = os.getenv("ROBOFLOW_VERSION", "1")
    
    if not api_key:
        raise RuntimeError("ROBOFLOW_API_KEY is missing (check your .env and load_dotenv).")
    if not model:
        raise RuntimeError("ROBOFLOW_MODEL is missing (check your .env and load_dotenv).")
    
    print(f"🔍 Analyzing image: {image_path}")
    print(f"📦 Using model: {model}/{version}")
    
    url = f"https://detect.roboflow.com/{model}/{version}"
    params = {
        "api_key": api_key,
        "confidence": 10,
        "overlap": 30
    }
    
    with open(image_path, "rb") as image_file:
        response = requests.post(url, params=params, files={"file": image_file})
    
    print(f"🌐 Calling Roboflow API: {url}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"📊 Predictions found: {len(result.get('predictions', []))}")
        return result
    
    print(f"❌ Error: {response.text}")
    raise Exception(f"Roboflow API error: {response.status_code} - {response.text}")


def analyze_secondary(image_path: str) -> Dict[str, Any]:
    """Secondary skin condition detection model (acne-melasma-rosacea)"""
    api_key = os.getenv("ROBOFLOW_API_KEY")
    
    # Hardcoded since you have the exact model ID
    secondary_model = "acne-melasma-rosacea"
    secondary_version = "1"
    
    if not api_key:
        raise RuntimeError("ROBOFLOW_API_KEY is missing.")
    
    print(f"🔬 Running secondary analysis: {image_path}")
    print(f"📦 Using secondary model: {secondary_model}/{secondary_version}")
    
    url = f"https://detect.roboflow.com/{secondary_model}/{secondary_version}"
    params = {
        "api_key": api_key,
        "confidence": 10,
        "overlap": 30
    }
    
    with open(image_path, "rb") as image_file:
        response = requests.post(url, params=params, files={"file": image_file})
    
    print(f"🌐 Calling Secondary Roboflow API: {url}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"📊 Secondary predictions found: {len(result.get('predictions', []))}")
        return result
    
    print(f"❌ Secondary model error: {response.text}")
    raise Exception(f"Secondary Roboflow API error: {response.status_code} - {response.text}")