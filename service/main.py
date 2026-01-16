import uvicorn
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import shutil
import os
import cv2
import numpy as np
import logging
import sys
from face_service import FaceService
from vector_db import VectorDB
from attendance_logger import log_attendance

# --- Logging Configuration ---
# Create a logger
logger = logging.getLogger("FaceService")
logger.setLevel(logging.INFO)

# Create handlers
file_handler = logging.FileHandler("log.file", mode='a', encoding='utf-8')
console_handler = logging.StreamHandler(sys.stdout)

# Create formatters and add it to handlers
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers to the logger
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

app = FastAPI(title="Face Recognition Service")

# CORS for Mini Program (development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Services
face_service = FaceService()
vector_db = VectorDB()

@app.on_event("startup")
async def startup_event():
    # Initialize InsightFace model
    logger.info("Initializing Face Model...")
    face_service.init_model()
    # Load Vector DB
    logger.info("Loading Vector Database...")
    vector_db.load_db()

    # --- Auto-Ingest Images from 'picture' folder ---
    picture_dir = "picture"
    if os.path.exists(picture_dir):
        logger.info(f"Scanning '{picture_dir}' for employee faces...")
        count = 0
        for filename in os.listdir(picture_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')) and "Zone.Identifier" not in filename:
                file_path = os.path.join(picture_dir, filename)
                user_id = os.path.splitext(filename)[0] # Use 'ldh' from 'ldh.jpg'
                
                try:
                    # Check if already exists (optional, keeping simple for now)
                    # Read image
                    img = cv2.imread(file_path)
                    if img is None:
                        logger.warning(f"Could not read {filename}")
                        continue
                    
                    feature = face_service.get_feature(img)
                    if feature is not None:
                        vector_db.add(user_id, feature)
                        count += 1
                        logger.info(f"Loaded face for: {user_id}")
                    else:
                        logger.warning(f"No face found in {filename}")
                except Exception as e:
                    logger.error(f"Failed to process {filename}: {e}")
        
        if count > 0:
            logger.info(f"Successfully loaded {count} faces from local directory.")
            vector_db.save_db() # Save to persist for future restarts if needed
    else:
        logger.info(f"Directory '{picture_dir}' not found. Skipping local image ingest.")

@app.get("/")
def read_root():
    return {"message": "Face Recognition Backend is Running"}

@app.post("/api/face/verify")
async def verify_face(
    token: str = Form(...),
    address: str = Form("未知位置"), # Default if not provided
    file: UploadFile = File(...)
):
    """
    Simulate the verification process:
    1. Receive image
    2. Extract feature
    3. Search in DB
    4. Return result
    """
    try:
        # Read image
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return {"code": 400, "msg": "Invalid Image"}

        # Extract feature
        feature = face_service.get_feature(img)
        
        if feature is None:
            return {"code": 400, "msg": "No face detected"}

        # Search in DB
        user_id, score = vector_db.search(feature)
        
        # Threshold logic
        threshold = 0.5 # Adjustable
        is_match = score > threshold
        
        final_user_id = user_id if is_match else "Unknown"
        status = "Success" if is_match else "Fail"

        logger.info(f"--- Verification Request ---")
        logger.info(f"  > Address: {address}")
        logger.info(f"  > Max Score: {score:.4f}")
        logger.info(f"  > Matched User: {user_id}")
        logger.info(f"  > Result: {status}")
        
        # Log to CSV
        log_attendance(final_user_id, status, address)

        response_data = {
            "code": 200,
            "isMatch": bool(is_match),
            "userId": user_id if is_match else None,
            "score": float(score),
            "msg": "Success" if is_match else f"未录入或未匹配到 (Score: {score:.2f})",
            "address": address
        }

        logger.info(f"  > Response: {response_data}")
        logger.info(f"----------------------------")

        return response_data

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {"code": 500, "msg": str(e)}

@app.post("/api/face/register")
async def register_face(
    user_id: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Register a user face
    """
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        feature = face_service.get_feature(img)
        if feature is None:
            return {"code": 400, "msg": "No face detected"}
            
        vector_db.add(user_id, feature)
        vector_db.save_db() # Persist
        
        logger.info(f"Registered new face for user: {user_id}")
        return {"code": 200, "msg": "Registered successfully"}
    except Exception as e:
         logger.error(f"Registration Error: {str(e)}")
         return {"code": 500, "msg": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
