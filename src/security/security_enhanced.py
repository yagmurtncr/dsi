"""
🔒 Gelişmiş Güvenlik Modülü
Ne İşe Yarar: Güvenlik logları, IP bazlı rate limiting, brute force koruması sağlar
"""

import re
import logging
from html import escape
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple
import os


class SecurityLogger:
    """Güvenlik olaylarını log dosyasına kaydeder (failed login, rate limit, XSS/SQL injection girişimleri)"""
    
    #1
    def __init__(self, log_file: str = None):
        if log_file is None:
            log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, "security.log")
        
        self.logger = logging.getLogger("security")
        self.logger.setLevel(logging.INFO)
        
        # File handler
        handler = logging.FileHandler(log_file)
        handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        self.logger.addHandler(handler)
        
        # Console handler
        console = logging.StreamHandler()
        console.setLevel(logging.WARNING)
        self.logger.addHandler(console)
    
    #2
    def log_failed_login(self, ip: str, username: str):
        """Başarısız login denemelerini loglar"""
        self.logger.warning(f"Failed login: IP={ip}, User={username}")
    
    #3
    def log_successful_login(self, ip: str, username: str):
        """Başarılı login'leri loglar"""
        self.logger.info(f"Successful login: IP={ip}, User={username}")
    
    #4
    def log_rate_limit_exceeded(self, ip: str, endpoint: str):
        """Rate limit aşımlarını loglar"""
        self.logger.warning(f"Rate limit exceeded: IP={ip}, Endpoint={endpoint}")
    
    #5
    def log_suspicious_input(self, ip: str, pattern: str, prompt: str):
        """Şüpheli input'ları loglar (XSS, SQL injection vb.)"""
        self.logger.error(
            f"Suspicious input detected: IP={ip}, Pattern={pattern}, "
            f"Prompt={prompt[:50]}..."
        )
    
    #6
    def log_brute_force_lockout(self, ip: str, minutes: int):
        """Brute force saldırıları sonucu lockout'ları loglar"""
        self.logger.error(f"Brute force lockout: IP={ip}, Duration={minutes}min")
    
    #7
    def log_successful_generation(self, ip: str, tokens: int, time: float):
        """Başarılı text generation'ları loglar"""
        self.logger.info(
            f"Generation success: IP={ip}, Tokens={tokens}, Time={time:.2f}s"
        )


class InputValidator:
    """Kullanıcı input'larını XSS, SQL injection ve prompt injection'a karşı doğrular"""
    
    # Tehlikeli pattern'ler (XSS, SQL injection vb.)
    DANGEROUS_PATTERNS = [
        (r'<script[^>]*>', 'XSS_SCRIPT'),
        (r'javascript:', 'XSS_JAVASCRIPT'),
        (r'on\w+\s*=', 'XSS_EVENT'),
        (r'<iframe[^>]*>', 'XSS_IFRAME'),
        (r'eval\s*\(', 'CODE_EVAL'),
        (r'exec\s*\(', 'CODE_EXEC'),
        (r'SELECT\s+.*\s+FROM', 'SQL_SELECT'),
        (r'DROP\s+TABLE', 'SQL_DROP'),
        (r'UNION\s+SELECT', 'SQL_UNION'),
        (r'DELETE\s+FROM', 'SQL_DELETE'),
        (r'INSERT\s+INTO', 'SQL_INSERT'),
        (r'UPDATE\s+.*\s+SET', 'SQL_UPDATE'),
        (r';.*--', 'SQL_COMMENT'),
    ]
    
    #8
    def __init__(self, security_logger: SecurityLogger = None):
        self.security_logger = security_logger
    
    #9
    def validate(self, text: str, client_ip: str = None) -> Tuple[bool, str, str]:
        """Input text'i güvenlik tehditlerine karşı kontrol eder ve temizler"""
        if not text or len(text.strip()) == 0:
            return False, "", "Boş prompt gönderilemez"
        
        # Tehlikeli pattern kontrolü
        for pattern, threat_type in self.DANGEROUS_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if self.security_logger and client_ip:
                    self.security_logger.log_suspicious_input(
                        client_ip, threat_type, text
                    )
                return False, "", f"Güvenlik tehdidi tespit edildi: {threat_type}"
        
        # HTML escape (temel XSS koruması)
        cleaned = escape(text)
        
        return True, cleaned, ""


class RateLimiter:
    """IP bazlı rate limiting (sliding window algorithm ile)"""
    
    #10
    def __init__(
        self,
        max_requests: int = 20,
        window_seconds: int = 60,
        security_logger: SecurityLogger = None
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[datetime]] = defaultdict(list)
        self.security_logger = security_logger
    
    #11
    def check_rate_limit(self,client_ip: str,endpoint: str = "unknown") -> Tuple[bool, int]:
        """Rate limit kontrolü yapar (sliding window ile) -> Varsayılan: 20 istek / 60 saniye"""
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)
        
        # Clean old requests
        self.requests[client_ip] = [
            ts for ts in self.requests[client_ip]
            if ts > window_start
        ]
        
        current_count = len(self.requests[client_ip])
        
        if current_count >= self.max_requests:
            if self.security_logger:
                self.security_logger.log_rate_limit_exceeded(client_ip, endpoint)
            return False, 0
        
        # Yeni isteği kaydet
        self.requests[client_ip].append(now)
        remaining = self.max_requests - (current_count + 1)
        return True, remaining
    
    #12
    def cleanup_old_entries(self):
        """Eski kayıtları temizler (memory leak önlemi)"""
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds * 2)
        
        for ip in list(self.requests.keys()):
            self.requests[ip] = [
                ts for ts in self.requests[ip]
                if ts > window_start
            ]
            if not self.requests[ip]:
                del self.requests[ip]


class BruteForceProtection:
    """Brute force saldırılarına karşı koruma (5 başarısız deneme → 15 dakika lockout)"""
    
    #13
    def __init__(
        self,
        max_attempts: int = 5,
        lockout_minutes: int = 15,
        security_logger: SecurityLogger = None
    ):
        self.max_attempts = max_attempts
        self.lockout_minutes = lockout_minutes
        self.failed_attempts: Dict[str, List[datetime]] = defaultdict(list)
        self.locked_ips: Dict[str, datetime] = {}
        self.security_logger = security_logger
    
    #14
    def is_locked(self, ip: str) -> Tuple[bool, int]:
        """IP'nin lockout durumunu kontrol eder"""
        if ip in self.locked_ips:
            lockout_until = self.locked_ips[ip]
            if datetime.now() < lockout_until:
                remaining = int(
                    (lockout_until - datetime.now()).total_seconds() / 60
                )
                return True, remaining
            else:
                # Lockout süresi doldu, temizle
                del self.locked_ips[ip]
                self.failed_attempts[ip] = []
        
        return False, 0
    
    #15
    def record_failed_attempt(self, ip: str) -> Tuple[bool, int]:
        """Başarısız login denemesini kaydeder (5 deneme → 15 dakika lockout)"""
        now = datetime.now()
        window_start = now - timedelta(minutes=self.lockout_minutes)
        
        # Eski denemeleri temizle
        self.failed_attempts[ip] = [
            ts for ts in self.failed_attempts[ip]
            if ts > window_start
        ]
        
        # Yeni denemeyi ekle
        self.failed_attempts[ip].append(now)
        
        # Kilitleme kontrolü
        if len(self.failed_attempts[ip]) >= self.max_attempts:
            lockout_until = now + timedelta(minutes=self.lockout_minutes)
            self.locked_ips[ip] = lockout_until
            
            if self.security_logger:
                self.security_logger.log_brute_force_lockout(
                    ip, self.lockout_minutes
                )
            
            return True, self.lockout_minutes
        
        remaining = self.max_attempts - len(self.failed_attempts[ip])
        return False, remaining
    
    #16
    def reset_attempts(self, ip: str):
        """Başarılı login sonrası başarısız denemeleri sıfırlar"""
        if ip in self.failed_attempts:
            del self.failed_attempts[ip]
        if ip in self.locked_ips:
            del self.locked_ips[ip]


# Global instance'lar (API başlangıcında initialize edilecek)
security_logger = SecurityLogger()
input_validator = InputValidator(security_logger)
rate_limiter = None  # Config'den initialize edilecek
brute_force_protection = None  # Config'den initialize edilecek


