import os
import requests
from typing import Dict, Any

def analyze_image(image_path: str) -> Dict[str, Any]:
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
