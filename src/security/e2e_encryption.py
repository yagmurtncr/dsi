#!/usr/bin/env python3
"""
🔐 E2E Client-Server Encryption
RSA-2048 + AES-256-GCM ile tam uçtan uca şifreleme

HE-WITH-LLM sistemindeki gibi client-server arası tüm veriyi şifreler.
"""

import os
import base64
import json
import hashlib
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend


class E2EEncryption:
    """
    End-to-End Encryption Manager
    
    Her client için RSA key pair oluşturur ve AES-256-GCM ile veri şifreler.
    """
    
    def __init__(self):
        # Server RSA key pair (startup'ta bir kez oluşturulur)
        self.server_private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        self.server_public_key = self.server_private_key.public_key()
        
        # Client public keys (session bazlı)
        self.client_keys: Dict[str, bytes] = {}  # {session_id: public_key_pem}
        
        # Session AES keys (her istek için yeni)
        self.session_aes_keys: Dict[str, bytes] = {}  # {session_id: aes_key}
        
        print("🔐 E2E Encryption initialized")
        print(f"   Server RSA key generated: 2048-bit")
    
    def get_server_public_key_pem(self) -> str:
        """Server'ın public key'ini PEM formatında döner (client'a gönderilir)"""
        pem = self.server_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return base64.b64encode(pem).decode('utf-8')
    
    def register_client_key(self, session_id: str, client_public_key_pem: str) -> bool:
        """
        Client'ın public key'ini kaydet (key exchange)
        
        Args:
            session_id: Oturum ID'si
            client_public_key_pem: Client'ın RSA public key'i (PEM string veya base64 PEM)
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            from cryptography.hazmat.primitives.serialization import load_pem_public_key
            
            # PEM formatını kontrol et
            key_str = client_public_key_pem.strip()
            
            # Eğer direkt PEM formatındaysa (-----BEGIN ile başlıyorsa)
            if key_str.startswith("-----BEGIN"):
                pem_bytes = key_str.encode('utf-8')
            else:
                # Base64 encoded PEM olarak dene
                try:
                    pem_bytes = base64.b64decode(key_str)
                except:
                    # Belki newline escape'leri vardır (\n → gerçek newline)
                    key_str = key_str.replace("\\n", "\n")
                    pem_bytes = key_str.encode('utf-8')
            
            # Key'i doğrula (parse edilebilir mi?)
            load_pem_public_key(pem_bytes, backend=default_backend())
            
            # Kaydet
            self.client_keys[session_id] = pem_bytes
            print(f"🔑 Client key registered: {session_id}")
            print(f"   📊 Registered keys: {list(self.client_keys.keys())}")
            return True
        
        except Exception as e:
            print(f"❌ Client key registration failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def encrypt_response(self, session_id: str, data: dict) -> dict:
        """
        Response'u client için şifrele (Hybrid Encryption)
        
        1. Rastgele AES-256 key oluştur
        2. Veriyi AES-GCM ile şifrele
        3. AES key'ini client'ın RSA public key'i ile şifrele
        4. Şifreli veri + şifreli AES key döner
        
        Args:
            session_id: Oturum ID'si
            data: Şifrelenecek veri (dict)
        
        Returns:
            dict: Şifrelenmiş response
        """
        try:
            print(f"🔐 encrypt_response called for: {session_id}")
            print(f"   📊 Available keys: {list(self.client_keys.keys())}")
            
            # Client key kontrolü
            if session_id not in self.client_keys:
                print(f"   ⚠️ Client key not found for {session_id}")
                # Client key yoksa plaintext döner (geriye uyumluluk)
                return {
                    "encrypted": False,
                    "data": data
                }
            
            # 1. Rastgele AES-256 key
            aes_key = os.urandom(32)  # 256 bit
            
            # 2. Veriyi JSON'a çevir ve AES-GCM ile şifrele
            plaintext = json.dumps(data, ensure_ascii=False).encode('utf-8')
            
            aesgcm = AESGCM(aes_key)
            nonce = os.urandom(12)  # 96-bit nonce
            ciphertext = aesgcm.encrypt(nonce, plaintext, None)
            
            # 3. AES key'ini client'ın RSA public key'i ile şifrele
            from cryptography.hazmat.primitives.serialization import load_pem_public_key
            client_public_key = load_pem_public_key(
                self.client_keys[session_id],
                backend=default_backend()
            )
            
            encrypted_aes_key = client_public_key.encrypt(
                aes_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # 4. Şifreli response
            return {
                "encrypted": True,
                "encrypted_key": base64.b64encode(encrypted_aes_key).decode('utf-8'),
                "nonce": base64.b64encode(nonce).decode('utf-8'),
                "ciphertext": base64.b64encode(ciphertext).decode('utf-8'),
                "algorithm": "RSA-2048-OAEP + AES-256-GCM"
            }
        
        except Exception as e:
            print(f"⚠️ Encryption failed: {e}")
            # Fallback: plaintext döner
            return {
                "encrypted": False,
                "data": data,
                "encryption_error": str(e)
            }
    
    def decrypt_request(self, encrypted_data: dict) -> Optional[dict]:
        """
        Client'tan gelen şifreli isteği çöz
        
        Args:
            encrypted_data: Şifreli istek
        
        Returns:
            dict: Çözülmüş veri veya None
        """
        try:
            if not encrypted_data.get("encrypted", False):
                return encrypted_data.get("data")
            
            # 1. AES key'ini RSA ile çöz
            encrypted_aes_key = base64.b64decode(encrypted_data["encrypted_key"])
            
            aes_key = self.server_private_key.decrypt(
                encrypted_aes_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # 2. Veriyi AES-GCM ile çöz
            nonce = base64.b64decode(encrypted_data["nonce"])
            ciphertext = base64.b64decode(encrypted_data["ciphertext"])
            
            aesgcm = AESGCM(aes_key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            
            return json.loads(plaintext.decode('utf-8'))
        
        except Exception as e:
            print(f"❌ Decryption failed: {e}")
            return None
    
    def clear_session(self, session_id: str):
        """Session key'lerini temizle"""
        if session_id in self.client_keys:
            del self.client_keys[session_id]
        if session_id in self.session_aes_keys:
            del self.session_aes_keys[session_id]
        print(f"🗑️ E2E session cleared: {session_id}")


class ModelIntegrityChecker:
    """
    🔒 Model Integrity Checker
    
    Model dosyalarının SHA-256 hash'lerini kontrol eder.
    Tampering detection için kullanılır.
    """
    
    def __init__(self, model_path: str = None):
        self.model_path = model_path
        self.expected_hashes: Dict[str, str] = {}
        self.verified = False
        
    def compute_file_hash(self, file_path: str) -> str:
        """Dosyanın SHA-256 hash'ini hesapla"""
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            # 64KB chunk'lar halinde oku (büyük dosyalar için)
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    def generate_manifest(self, model_path: str) -> dict:
        """
        Model dosyaları için hash manifest oluştur
        
        Returns:
            dict: {filename: sha256_hash}
        """
        import glob
        
        manifest = {
            "generated_at": datetime.now().isoformat(),
            "model_path": model_path,
            "files": {}
        }
        
        # Safetensors ve config dosyalarını hash'le
        patterns = ["*.safetensors", "*.json", "*.model", "*.txt"]
        
        for pattern in patterns:
            for file_path in glob.glob(os.path.join(model_path, pattern)):
                filename = os.path.basename(file_path)
                file_hash = self.compute_file_hash(file_path)
                manifest["files"][filename] = {
                    "hash": file_hash,
                    "size": os.path.getsize(file_path)
                }
                print(f"   📄 {filename}: {file_hash[:16]}...")
        
        return manifest
    
    def verify_integrity(self, model_path: str, expected_manifest: dict = None) -> Tuple[bool, list]:
        """
        Model bütünlüğünü doğrula
        
        Args:
            model_path: Model dizini
            expected_manifest: Beklenen hash'ler (yoksa ilk çalıştırmada oluşturulur)
        
        Returns:
            Tuple[bool, list]: (Doğrulama başarılı mı, Değişen dosyalar listesi)
        """
        changed_files = []
        
        if expected_manifest is None:
            # İlk çalıştırma - manifest oluştur ve kaydet
            print("🔒 Generating model integrity manifest...")
            manifest = self.generate_manifest(model_path)
            
            manifest_path = os.path.join(model_path, ".integrity_manifest.json")
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            print(f"✅ Manifest saved: {manifest_path}")
            self.expected_hashes = manifest["files"]
            self.verified = True
            return True, []
        
        # Manifest ile karşılaştır
        print("🔍 Verifying model integrity...")
        
        for filename, info in expected_manifest.get("files", {}).items():
            file_path = os.path.join(model_path, filename)
            
            if not os.path.exists(file_path):
                changed_files.append(f"MISSING: {filename}")
                continue
            
            current_hash = self.compute_file_hash(file_path)
            expected_hash = info["hash"]
            
            if current_hash != expected_hash:
                changed_files.append(f"MODIFIED: {filename}")
                print(f"   ❌ {filename}: HASH MISMATCH!")
            else:
                print(f"   ✅ {filename}: OK")
        
        self.verified = len(changed_files) == 0
        
        if self.verified:
            print("✅ Model integrity verified!")
        else:
            print(f"❌ Model integrity FAILED! {len(changed_files)} files changed")
        
        return self.verified, changed_files


class EnhancedRateLimiter:
    """
    🛡️ Multi-Level Rate Limiter
    
    IP + User + Endpoint bazlı rate limiting
    """
    
    def __init__(self):
        # Rate limit kayıtları
        self.ip_requests: Dict[str, list] = {}      # IP bazlı
        self.user_requests: Dict[str, list] = {}    # User bazlı
        self.endpoint_requests: Dict[str, list] = {}  # Endpoint bazlı
        
        # Limitler (dakika başına) - SIKILAŞTIRILDI!
        self.limits = {
            "ip": {
                "default": 60,      # 60 istek/dk (önceki: 100)
                "login": 3,         # 3 giriş denemesi/dk (önceki: 5) - brute force koruması
                "generate": 20      # 20 inference/dk (önceki: 30)
            },
            "user": {
                "default": 100,     # 100 istek/dk (önceki: 200)
                "generate": 30      # 30 inference/dk (önceki: 50)
            },
            "endpoint": {
                "/login": 500,       # Global login limit (önceki: 1000)
                "/generate": 300,    # Global generate limit (önceki: 500)
                "/health": 10000     # Health check (aynı)
            }
        }
        
        # Window (saniye)
        self.window = 60
    
    def _clean_old_requests(self, requests: list) -> list:
        """Eski istekleri temizle"""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window)
        return [r for r in requests if r > cutoff]
    
    def check_multi_level(
        self, 
        ip: str, 
        user: str, 
        endpoint: str
    ) -> Tuple[bool, str, int]:
        """
        Multi-level rate limit kontrolü
        
        Returns:
            Tuple[bool, str, int]: (İzin var mı, Neden, Kalan limit)
        """
        now = datetime.now()
        
        # 1. IP bazlı kontrol
        ip_key = ip
        if ip_key not in self.ip_requests:
            self.ip_requests[ip_key] = []
        
        self.ip_requests[ip_key] = self._clean_old_requests(self.ip_requests[ip_key])
        
        # Endpoint-specific IP limit
        endpoint_name = endpoint.split("?")[0]  # Query string'i kaldır
        ip_limit = self.limits["ip"].get(endpoint_name.strip("/"), self.limits["ip"]["default"])
        
        if len(self.ip_requests[ip_key]) >= ip_limit:
            return False, f"IP rate limit exceeded ({ip_limit}/min)", 0
        
        # 2. User bazlı kontrol
        if user and user != "unknown":
            if user not in self.user_requests:
                self.user_requests[user] = []
            
            self.user_requests[user] = self._clean_old_requests(self.user_requests[user])
            
            user_limit = self.limits["user"].get(endpoint_name.strip("/"), self.limits["user"]["default"])
            
            if len(self.user_requests[user]) >= user_limit:
                return False, f"User rate limit exceeded ({user_limit}/min)", 0
        
        # 3. Global endpoint limit
        if endpoint_name not in self.endpoint_requests:
            self.endpoint_requests[endpoint_name] = []
        
        self.endpoint_requests[endpoint_name] = self._clean_old_requests(
            self.endpoint_requests[endpoint_name]
        )
        
        endpoint_limit = self.limits["endpoint"].get(endpoint_name, 10000)
        
        if len(self.endpoint_requests[endpoint_name]) >= endpoint_limit:
            return False, f"Global endpoint limit exceeded ({endpoint_limit}/min)", 0
        
        # Tüm kontroller geçti - isteği kaydet
        self.ip_requests[ip_key].append(now)
        
        if user and user != "unknown":
            self.user_requests[user].append(now)
        
        self.endpoint_requests[endpoint_name].append(now)
        
        # Kalan limit hesapla (en düşük olanı döner)
        remaining = min(
            ip_limit - len(self.ip_requests[ip_key]),
            endpoint_limit - len(self.endpoint_requests[endpoint_name])
        )
        
        return True, "OK", remaining


class SessionManager:
    """
    ⏰ Session Timeout Manager
    
    İnaktif oturumları otomatik sonlandırır
    """
    
    def __init__(self, idle_timeout: int = 900, absolute_timeout: int = 3600):
        """
        Args:
            idle_timeout: İnaktivite süresi (saniye) - varsayılan 15 dakika
            absolute_timeout: Mutlak oturum süresi (saniye) - varsayılan 1 saat
        """
        self.idle_timeout = idle_timeout
        self.absolute_timeout = absolute_timeout
        
        # Session tracking: {username: {"created": datetime, "last_activity": datetime}}
        self.sessions: Dict[str, dict] = {}
    
    def create_session(self, username: str) -> dict:
        """Yeni oturum oluştur"""
        now = datetime.now()
        self.sessions[username] = {
            "created": now,
            "last_activity": now,
            "request_count": 0
        }
        return self.sessions[username]
    
    def update_activity(self, username: str) -> bool:
        """
        Kullanıcı aktivitesini güncelle
        
        Returns:
            bool: Oturum hala geçerli mi?
        """
        if username not in self.sessions:
            return False
        
        now = datetime.now()
        session = self.sessions[username]
        
        # 1. Mutlak timeout kontrolü (oturum başlangıcından itibaren)
        if (now - session["created"]).total_seconds() > self.absolute_timeout:
            self.end_session(username)
            return False
        
        # 2. İnaktivite timeout kontrolü (son aktiviteden itibaren)
        if (now - session["last_activity"]).total_seconds() > self.idle_timeout:
            self.end_session(username)
            return False
        
        # Oturum geçerli - aktiviteyi güncelle
        session["last_activity"] = now
        session["request_count"] += 1
        
        return True
    
    def end_session(self, username: str):
        """Oturumu sonlandır"""
        if username in self.sessions:
            del self.sessions[username]
            print(f"⏰ Session ended (timeout): {username}")
    
    def get_session_info(self, username: str) -> Optional[dict]:
        """Oturum bilgisi döner"""
        if username not in self.sessions:
            return None
        
        session = self.sessions[username]
        now = datetime.now()
        
        return {
            "username": username,
            "created": session["created"].isoformat(),
            "last_activity": session["last_activity"].isoformat(),
            "request_count": session["request_count"],
            "idle_remaining": self.idle_timeout - (now - session["last_activity"]).total_seconds(),
            "absolute_remaining": self.absolute_timeout - (now - session["created"]).total_seconds()
        }
    
    def cleanup_expired(self) -> int:
        """Süresi dolmuş oturumları temizle"""
        expired = []
        now = datetime.now()
        
        for username, session in self.sessions.items():
            if (now - session["last_activity"]).total_seconds() > self.idle_timeout:
                expired.append(username)
            elif (now - session["created"]).total_seconds() > self.absolute_timeout:
                expired.append(username)
        
        for username in expired:
            self.end_session(username)
        
        return len(expired)


class SecurityMonitor:
    """
    🚨 Security Monitoring & Alerts
    
    Real-time güvenlik izleme ve alert sistemi
    """
    
    def __init__(self):
        self.alerts: list = []
        self.metrics = {
            "failed_logins": 0,
            "rate_limit_hits": 0,
            "suspicious_requests": 0,
            "encryption_failures": 0,
            "session_timeouts": 0  # 🆕 Session timeout tracking
        }
        self.alert_thresholds = {
            "failed_logins": 5,         # 5 başarısız giriş → alert (sıkılaştırıldı!)
            "rate_limit_hits": 20,      # 20 rate limit → alert (sıkılaştırıldı!)
            "suspicious_requests": 3,   # 3 şüpheli istek → alert (sıkılaştırıldı!)
        }
    
    def record_event(self, event_type: str, details: dict = None):
        """Güvenlik olayı kaydet"""
        if event_type in self.metrics:
            self.metrics[event_type] += 1
            
            # Threshold kontrolü
            if self.metrics[event_type] >= self.alert_thresholds.get(event_type, float('inf')):
                self._create_alert(event_type, details)
    
    def _create_alert(self, event_type: str, details: dict = None):
        """Alert oluştur"""
        alert = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "severity": self._get_severity(event_type),
            "details": details or {},
            "message": self._get_alert_message(event_type)
        }
        
        self.alerts.append(alert)
        
        # Console'a yazdır
        severity = alert["severity"]
        emoji = "🔴" if severity == "HIGH" else "🟠" if severity == "MEDIUM" else "🟡"
        print(f"{emoji} SECURITY ALERT [{severity}]: {alert['message']}")
        
        # Metrikleri sıfırla
        self.metrics[event_type] = 0
    
    def _get_severity(self, event_type: str) -> str:
        """Alert severity belirle"""
        high_severity = ["suspicious_requests", "encryption_failures"]
        medium_severity = ["failed_logins"]
        
        if event_type in high_severity:
            return "HIGH"
        elif event_type in medium_severity:
            return "MEDIUM"
        return "LOW"
    
    def _get_alert_message(self, event_type: str) -> str:
        """Alert mesajı oluştur"""
        messages = {
            "failed_logins": "Multiple failed login attempts detected!",
            "rate_limit_hits": "High rate limit activity detected!",
            "suspicious_requests": "Suspicious request pattern detected!",
            "encryption_failures": "Encryption failures detected - possible attack!"
        }
        return messages.get(event_type, f"Security event: {event_type}")
    
    def get_status(self) -> dict:
        """Güvenlik durumu özeti"""
        return {
            "metrics": self.metrics.copy(),
            "recent_alerts": self.alerts[-10:],  # Son 10 alert
            "alert_count": len(self.alerts),
            "status": "CRITICAL" if any(a["severity"] == "HIGH" for a in self.alerts[-5:]) else "OK"
        }
    
    def clear_alerts(self):
        """Alert'leri temizle"""
        self.alerts.clear()
        print("🧹 Security alerts cleared")


class RequestSigner:
    """
    ✍️ Request Signing (HMAC-SHA256)
    
    İstek bütünlüğünü doğrular - tampering protection
    """
    
    def __init__(self, secret_key: str = None):
        import hmac as hmac_module
        self.hmac = hmac_module
        self.secret_key = (secret_key or os.getenv("HMAC_SECRET", "your-hmac-secret-key-change-this")).encode()
    
    def sign_request(self, data: str, timestamp: str = None) -> str:
        """
        İsteği imzala
        
        Args:
            data: İmzalanacak veri (genellikle request body)
            timestamp: Unix timestamp (replay attack koruması)
        
        Returns:
            str: HMAC-SHA256 imza (hex)
        """
        if timestamp is None:
            timestamp = str(int(datetime.now().timestamp()))
        
        # Veriyi timestamp ile birleştir
        message = f"{timestamp}:{data}".encode()
        
        # HMAC-SHA256 hesapla
        signature = self.hmac.new(
            self.secret_key,
            message,
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def verify_signature(
        self, 
        data: str, 
        signature: str, 
        timestamp: str,
        max_age: int = 300  # 5 dakika
    ) -> Tuple[bool, str]:
        """
        İmzayı doğrula
        
        Args:
            data: Doğrulanacak veri
            signature: Client'ın gönderdiği imza
            timestamp: Client'ın gönderdiği timestamp
            max_age: Maksimum timestamp yaşı (saniye) - replay attack koruması
        
        Returns:
            Tuple[bool, str]: (Geçerli mi, Hata mesajı)
        """
        try:
            # 1. Timestamp yaşı kontrolü (replay attack koruması)
            request_time = int(timestamp)
            now = int(datetime.now().timestamp())
            
            if abs(now - request_time) > max_age:
                return False, f"Request expired (max {max_age}s)"
            
            # 2. İmzayı hesapla ve karşılaştır
            expected_signature = self.sign_request(data, timestamp)
            
            # Timing-safe comparison (timing attack koruması)
            if self.hmac.compare_digest(signature, expected_signature):
                return True, "OK"
            else:
                return False, "Invalid signature"
        
        except ValueError:
            return False, "Invalid timestamp format"
        except Exception as e:
            return False, f"Verification error: {e}"
    
    def get_signature_headers(self, data: str) -> dict:
        """
        İmza için gerekli header'ları döner (client kullanımı için)
        
        Returns:
            dict: {"X-Timestamp": "...", "X-Signature": "..."}
        """
        timestamp = str(int(datetime.now().timestamp()))
        signature = self.sign_request(data, timestamp)
        
        return {
            "X-Timestamp": timestamp,
            "X-Signature": signature
        }


# Singleton instances
_e2e_encryption = None
_model_checker = None
_enhanced_rate_limiter = None
_security_monitor = None
_session_manager = None
_request_signer = None


def get_e2e_encryption() -> E2EEncryption:
    global _e2e_encryption
    if _e2e_encryption is None:
        _e2e_encryption = E2EEncryption()
    return _e2e_encryption


def get_model_checker() -> ModelIntegrityChecker:
    global _model_checker
    if _model_checker is None:
        _model_checker = ModelIntegrityChecker()
    return _model_checker


def get_enhanced_rate_limiter() -> EnhancedRateLimiter:
    global _enhanced_rate_limiter
    if _enhanced_rate_limiter is None:
        _enhanced_rate_limiter = EnhancedRateLimiter()
    return _enhanced_rate_limiter


def get_security_monitor() -> SecurityMonitor:
    global _security_monitor
    if _security_monitor is None:
        _security_monitor = SecurityMonitor()
    return _security_monitor


def get_session_manager() -> SessionManager:
    """Session Manager singleton"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(
            idle_timeout=900,      # 15 dakika inaktivite
            absolute_timeout=3600  # 1 saat mutlak süre
        )
    return _session_manager


def get_request_signer() -> RequestSigner:
    """Request Signer singleton"""
    global _request_signer
    if _request_signer is None:
        _request_signer = RequestSigner()
    return _request_signer

