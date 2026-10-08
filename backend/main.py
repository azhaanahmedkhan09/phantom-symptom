from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
import base64
import json
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend" / "index.html"

app = FastAPI(title="Phantom Symptom", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return FileResponse(FRONTEND)

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/analyze")
async def analyze_crop(
    image: UploadFile = File(...),
    crop: str = Form(...),
    symptoms: str = Form(""),
    temperature: float = Form(...),
    humidity: float = Form(...),
    soil_moisture: float = Form(...),
    api_key: str = Form(...),
):
    if not api_key.strip():
        return {"success": False, "error": "Gemini API key is missing."}

    image_bytes = await image.read()
    if not image_bytes:
        return {"success": False, "error": "The uploaded image is empty."}
    if len(image_bytes) > 12 * 1024 * 1024:
        return {"success": False, "error": "Please use an image smaller than 12 MB."}

    mime_type = image.content_type or "image/jpeg"
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    prompt = f"""
You are Phantom Symptom, a multimodal agricultural decision-support AI.

The key idea is a PHANTOM SYMPTOM: the same visible symptom can have different causes.
Do not jump to one disease from the image alone. Compare the image, farmer description,
and environmental conditions and rank plausible causes.

Crop: {crop}
Farmer symptoms: {symptoms or 'Not provided'}
Temperature: {temperature} °C
Humidity: {humidity} %
Soil moisture: {soil_moisture} %

Consider disease, nutrient deficiency, water stress, heat/environmental stress, pest damage,
and other plausible causes.

Return ONLY valid JSON with exactly these keys:
{{
  "diagnosis": [
    {{"cause": "Most likely cause", "confidence": 70}},
    {{"cause": "Second possible cause", "confidence": 20}},
    {{"cause": "Third possible cause", "confidence": 10}}
  ],
  "explanation": "Brief evidence-based explanation using image, symptoms and environment.",
  "recommendation": "Safe practical next steps and what evidence should be checked next."
}}

Confidence values must be numbers from 0 to 100 and should sum to approximately 100.
This is decision support, not a guaranteed diagnosis. Avoid unsafe pesticide instructions.
"""

    body = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": image_base64}}
            ]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    models = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-2.5-flash"]
    last_error = "Unknown Gemini API error"

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key.strip(),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                result = json.loads(response.read().decode("utf-8"))
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            text = text.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(text)
            if not isinstance(parsed.get("diagnosis"), list) or not parsed["diagnosis"]:
                raise ValueError("Gemini returned an invalid diagnosis format.")
            return {
                "success": True,
                "diagnosis": parsed["diagnosis"],
                "explanation": parsed.get("explanation", "No explanation returned."),
                "recommendation": parsed.get("recommendation", "No recommendation returned."),
                "model": model,
            }
        except urllib.error.HTTPError as e:
            details = e.read().decode("utf-8", errors="replace")
            last_error = f"{model}: HTTP {e.code} - {details[:1000]}"
            if e.code in (400, 401, 403, 404):
                continue
        except Exception as e:
            last_error = f"{model}: {e}"
            continue

    return {
        "success": False,
        "error": "Gemini could not analyze the image.",
        "details": last_error,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
