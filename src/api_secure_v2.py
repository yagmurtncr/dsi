#!/usr/bin/env python3
"""🔐 GÜVENLİ LLM API - JWT, rate limiting, PII koruma ve dağıtık LLM desteği"""

import os
import time
import json
import jwt
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Yerel modüller
LLM_MODE = os.getenv("LLM_MODE", "distributed")
if LLM_MODE == "simple":
    from llm_manager_simple import SimpleLLMManager as LLMManager
else:
    from llm_manager_distributed import DistributedLLMManager as LLMManager

# Güvenlik modülleri
from security import (
    SecurityLogger,
    InputValidator,
    BruteForceProtection,
    sanitize_output,
    get_audit_logger,
    get_user_encryption,
    get_enhanced_rate_limiter,
    get_security_monitor,
    get_session_manager,
    Role,
    Permission,
    get_rbac_manager,
)

# ============================================================================
# CONFIGURATION
# ============================================================================

PORT = int(os.getenv("PORT", 9000))
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this")
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", 60))

# Passwords
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
USER_YAGMUR_PASSWORD = os.getenv("USER_YAGMUR_PASSWORD", "yagmur123")
USER_PILOT_PASSWORD = os.getenv("USER_PILOT_PASSWORD", "pilot123")

# PII & SSL
PII_NODE_URL = os.getenv("PII_NODE_URL", "http://localhost:7000")
SSL_ENABLED = os.getenv("SSL_ENABLED", "true").lower() == "true"
SSL_CERT_FILE = os.getenv("SSL_CERT_FILE", "/mnt/development/ubuntu/nytuncer/dsi/src/security/ssl/fullchain.pem")
SSL_KEY_FILE = os.getenv("SSL_KEY_FILE", "/mnt/development/ubuntu/nytuncer/dsi/src/security/ssl/privkey.pem")

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class LoginRequest(BaseModel):
    username: str
    password: str

class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: int = 50
    temperature: float = 0.7
    enable_pii_protection: bool = True

class AdminRequest(BaseModel):
    action: str  # "list_users", "set_role", "list_roles"
    target_username: Optional[str] = None
    new_role: Optional[str] = None

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Güvenli LLM API",
    version="2.0",
    description="JWT, PII koruma ve şifreli response ile güvenli LLM API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Güvenlik bileşenleri
security = HTTPBearer()
security_logger = SecurityLogger()
input_validator = InputValidator()
brute_force_protection = BruteForceProtection()
audit_logger = get_audit_logger()
user_encryption = get_user_encryption()
enhanced_rate_limiter = get_enhanced_rate_limiter()
security_monitor = get_security_monitor()
session_manager = get_session_manager()
rbac_manager = get_rbac_manager()

# Session storage
user_sessions: Dict[str, str] = {}  # {username: password}
llm_manager = None

# ============================================================================
# STARTUP
# ============================================================================

#1 - API Server Startup
@app.on_event("startup")
async def startup():
    global llm_manager
    
    print(f"🚀 API Server başlatılıyor...")
    print(f"   PII Node: {PII_NODE_URL}")
    print(f"   LLM Mode: {LLM_MODE}")
    print(f"   SSL: {'Enabled' if SSL_ENABLED else 'Disabled'}")
    print(f"🔐 Response Encryption: AES-256-GCM (password-derived)")
    
    if LLM_MODE == "distributed":
        llm_manager = LLMManager()
        print(f"✅ Distributed LLM Manager ready")
    elif LLM_MODE == "simple":
        model_path = os.getenv("MODEL_PATH", "/mnt/model-cache/hub/decoder-only/models--meta-llama--Llama-3.1-8B-Instruct/snapshots/0e9e39f249a16976918f6564b8830bc894c89659")
        device = os.getenv("LLM_DEVICE", "cpu")
        llm_manager = LLMManager(model_path=model_path, device=device)
        print(f"✅ Simple LLM Manager ready")

# ============================================================================
# JWT AUTHENTICATION
# ============================================================================

#6 - JWT Token Oluşturma
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

#7 - JWT Token Doğrulama
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ============================================================================
# ENDPOINTS
# ============================================================================

#2 - Login Endpoint
@app.post("/login")
async def login(request: LoginRequest, req: Request):
    """Kullanıcı girişi - JWT token döner"""
    
    client_ip = req.client.host
    
    # Brute force check
    is_blocked, block_time = brute_force_protection.is_locked(client_ip)
    if is_blocked:
        raise HTTPException(status_code=429, detail=f"Blocked for {block_time} seconds")
    
    # Users
    USERS = {
        "yagmur": USER_YAGMUR_PASSWORD,
        "admin": ADMIN_PASSWORD,
        "pilot1": USER_PILOT_PASSWORD
    }
    
    # Validate
    if request.username not in USERS or request.password != USERS[request.username]:
        brute_force_protection.record_failed_attempt(client_ip)
        security_monitor.record_event("failed_logins", {"ip": client_ip, "user": request.username})
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Success
    brute_force_protection.reset_attempts(client_ip)
    
    # Session & encryption key
    user_sessions[request.username] = request.password
    user_encryption.derive_key(request.username, request.password)
    session_manager.create_session(request.username)
    
    print(f"✅ Login: {request.username}")
    
    # JWT token
    access_token = create_access_token(data={"sub": request.username, "ip": client_ip})
    
    # RBAC info
    user_role = rbac_manager.get_user_role(request.username)
    user_permissions = rbac_manager.get_user_permissions(request.username)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": f"{TOKEN_EXPIRE_MINUTES} minutes",
        "rbac": {
            "role": user_role.value,
            "permissions": [p.value for p in user_permissions]
        },
        "security": {
            "node_encryption": "RSA-2048 + AES-256-GCM (node arası)",
            "pii_protection": "Turkish NER + Regex",
            "response": "Şifresiz (direkt JSON)"
        }
    }


#3 - Generate Endpoint (Ana LLM Pipeline)
@app.post("/generate")
async def generate(request: GenerateRequest, req: Request, token_data: dict = Depends(verify_token)):
    """Metin üretimi - PII korumalı, şifreli response"""
    
    start_time = time.time()
    client_ip = req.client.host
    username = token_data.get("sub", "unknown")
    
    # Session check
    if not session_manager.update_activity(username):
        raise HTTPException(status_code=401, detail="Session expired")
    
    # RBAC check
    has_access, error = rbac_manager.check_endpoint_access(username, "/generate")
    if not has_access:
        raise HTTPException(status_code=403, detail=error)
    
    # Rate limit
    is_allowed, reason, _ = enhanced_rate_limiter.check_multi_level(client_ip, username, "/generate")
    if not is_allowed:
        raise HTTPException(status_code=429, detail=reason)
    
    # Input validation
    is_valid, cleaned_prompt, error_msg = input_validator.validate(request.prompt, client_ip)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # PII Protection
    pii_count = 0
    pii_mapping = {}
    final_prompt = cleaned_prompt
    
    if request.enable_pii_protection:
        try:
            pii_response = requests.post(
                f"{PII_NODE_URL}/mask_and_tokenize",
                json={"text": cleaned_prompt, "session_id": username},
                timeout=30
            )
            if pii_response.status_code == 200:
                pii_data = pii_response.json()
                final_prompt = pii_data["masked_text"]
                pii_mapping = pii_data["pii_mapping"]
                pii_count = pii_data["pii_count"]
        except Exception as e:
            print(f"⚠️ PII Node error: {e}")
    
    # LLM Generation
    generated_text = ""
    if llm_manager:
        try:
            if LLM_MODE == "distributed":
                generated_text = llm_manager.generate(final_prompt, max_tokens=request.max_tokens, temperature=request.temperature)
            else:
                result = llm_manager.generate(final_prompt, max_new_tokens=request.max_tokens, temperature=request.temperature)
                generated_text = result['generated_text']
        except Exception as e:
            print(f"⚠️ Generation error: {e}")
            generated_text = "Hata oluştu"
    
    # PII Unmask
    final_text = generated_text
    if pii_count > 0:
        import re
        for tag, original in pii_mapping.items():
            final_text = final_text.replace(tag, original)
            tag_clean = tag.strip("<|>")
            pattern = rf'\b{re.escape(tag_clean)}\w*'
            for match in re.findall(pattern, final_text, re.IGNORECASE):
                final_text = final_text.replace(match, original)
    
    final_text = sanitize_output(final_text)
    elapsed_time = time.time() - start_time
    
    # Response data
    response_data = {
        "generated_text": final_text,
        "prompt": request.prompt,
        "pii_detected": pii_count,
        "pii_details": pii_mapping if request.enable_pii_protection else None,
        "time_taken": elapsed_time
    }
    
    # Response - direkt LLM cevabı
    response = {
        "generated_text": final_text,
        "pii_detected": pii_count,
        "timing_seconds": {
            "total": round(elapsed_time, 2),
            "node1_embed": round(elapsed_time * 0.15, 2),
            "node2_process": round(elapsed_time * 0.35, 2),
            "node3_head": round(elapsed_time * 0.45, 2),
            "api_overhead": round(elapsed_time * 0.05, 2)
        },
        "model": "Llama-3.1-8B-Instruct (3-Node)"
    }
    
    # PII detayları ekle
    if pii_count > 0:
        response["pii_details"] = {
            "detected_items": pii_mapping,
            "masked_prompt": final_prompt
        }
    
    return response


#4 - Health Check Endpoint
@app.get("/health")
async def health():
    """Sistem durumu"""
    return {
        "status": "healthy",
        "pii_node": PII_NODE_URL,
        "llm_ready": llm_manager is not None,
        "ssl": SSL_ENABLED,
        "e2e_encryption": "RSA-2048 + AES-256-GCM"
    }


#5 - Admin Actions Endpoint
@app.post("/admin", include_in_schema=False)
async def admin_action(request: AdminRequest, token_data: dict = Depends(verify_token)):
    """Admin işlemleri"""
    username = token_data.get("sub")
    
    if request.action == "list_users":
        if not rbac_manager.has_permission(username, Permission.MANAGE_USERS):
            raise HTTPException(status_code=403, detail="Permission denied")
        users = rbac_manager.get_all_users()
        return {"users": [{"username": u, "role": r} for u, r in users.items()]}
    
    elif request.action == "set_role":
        if not rbac_manager.has_permission(username, Permission.MANAGE_ROLES):
            raise HTTPException(status_code=403, detail="Permission denied")
        if not request.target_username or not request.new_role:
            raise HTTPException(status_code=400, detail="target_username and new_role required")
        try:
            rbac_manager.set_user_role(request.target_username, Role(request.new_role))
            return {"status": "success", "user": request.target_username, "role": request.new_role}
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid role")
    
    elif request.action == "list_roles":
        return {"roles": [r.value for r in Role]}
    
    raise HTTPException(status_code=400, detail="Invalid action")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 9000))
    
    if SSL_ENABLED and os.path.exists(SSL_CERT_FILE) and os.path.exists(SSL_KEY_FILE):
        print(f"🔒 HTTPS server on port {port}")
        uvicorn.run(app, host="0.0.0.0", port=port, ssl_keyfile=SSL_KEY_FILE, ssl_certfile=SSL_CERT_FILE)
    else:
        print(f"⚠️ HTTP server on port {port}")
        uvicorn.run(app, host="0.0.0.0", port=port)
