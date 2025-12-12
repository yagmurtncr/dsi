#!/usr/bin/env python3
"""
🔐 PII Node Server - Standalone PII Detection ve Masking Service
"""

# GPU kullanmadan CPU'da çalıştır (import'tan ÖNCE!)
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''

import argparse
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from pii_manager import PIIManager

app = FastAPI(title="PII Node", version="1.0")

# Global PII manager
pii_manager = None

class MaskRequest(BaseModel):
    text: str
    session_id: str = "default"

class MaskResponse(BaseModel):
    masked_text: str
    pii_mapping: dict
    pii_count: int

class UnmaskRequest(BaseModel):
    text: str
    session_id: str = "default"

class UnmaskResponse(BaseModel):
    unmasked_text: str

#11 - PII Node Startup
@app.on_event("startup")
async def startup():
    """PII Manager'ı başlat"""
    global pii_manager
    print("🔐 PII Node başlatılıyor (CPU mode)...")
    pii_manager = PIIManager()
    print("✅ PII Node hazır!")

#12 - PII Maskeleme Endpoint
@app.post("/mask", response_model=MaskResponse)
async def mask_pii(request: MaskRequest):
    """Text'teki PII'ları maskele"""
    if pii_manager is None:
        raise HTTPException(status_code=503, detail="PII Manager not ready")
    
    masked_text, pii_mapping = pii_manager.detect_and_mask(
        request.text,
        session_id=request.session_id
    )
    
    return MaskResponse(
        masked_text=masked_text,
        pii_mapping=pii_mapping,
        pii_count=len(pii_mapping)
    )

#13 - PII Unmask Endpoint
@app.post("/unmask", response_model=UnmaskResponse)
async def unmask_pii(request: UnmaskRequest):
    """Maskelenmiş text'i geri yükle"""
    if pii_manager is None:
        raise HTTPException(status_code=503, detail="PII Manager not ready")
    
    unmasked_text = pii_manager.unmask(
        request.text,
        session_id=request.session_id
    )
    
    return UnmaskResponse(unmasked_text=unmasked_text)

#14 - PII Mask & Tokenize Endpoint (API tarafından çağrılır)
@app.post("/mask_and_tokenize")
async def mask_and_tokenize(request: MaskRequest):
    """API uyumluluğu için - mask ile aynı"""
    if pii_manager is None:
        raise HTTPException(status_code=503, detail="PII Manager not ready")
    
    masked_text, pii_mapping = pii_manager.detect_and_mask(
        request.text,
        session_id=request.session_id
    )
    
    return {
        "masked_text": masked_text,
        "pii_mapping": pii_mapping,
        "pii_count": len(pii_mapping)
    }

#15 - PII Node Health Check
@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "pii_manager_ready": pii_manager is not None
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7000)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()
    
    uvicorn.run(app, host=args.host, port=args.port)

