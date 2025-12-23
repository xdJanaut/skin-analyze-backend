import os
import requests
from typing import Dict, Any

ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY")
ROBOFLOW_MODEL = os.getenv("ROBOFLOW_MODEL")
ROBOFLOW_VERSION = os.getenv("ROBOFLOW_VERSION", "1")
def analyze_image(image_path: str) -> Dict[str, Any]:
    """
    Send image to Roboflow for acne detection
    Return the raw API response
    """
    print(f"🔍 Analyzing image: {image_path}")
    print(f"📦 Using model: {ROBOFLOW_MODEL}/{ROBOFLOW_VERSION}")

    url = f"https://detect.roboflow.com/{ROBOFLOW_MODEL}/{ROBOFLOW_VERSION}"
    
    params = {
        "api_key": ROBOFLOW_API_KEY,
        "confidence": 10,
        "overlap": 30
        }
    
    with open(image_path, "rb") as image_file:
        response = requests.post(url, params=params, files={"file": image_file})
    
    print(f"🌐 Calling Roboflow API: {url}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"📊 Full Roboflow Response: {result}")  # This line should be there
        print(f"📊 Predictions found: {len(result.get('predictions', []))}")
        return result
    else:
        print(f"❌ Error: {response.text}")
        raise Exception(f"Roboflow API error: {response.status_code} - {response.text}")
    
