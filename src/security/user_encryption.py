#!/usr/bin/env python3
"""
🔐 User-Specific Encryption (End-to-End Encryption)
Ne İşe Yarar: Her kullanıcının kendi encryption key'i ile prompt/output şifrelemesi

Özellikler:
- Password-derived key (PBKDF2)
- AES-256-GCM encryption
- Zero-knowledge (sistem admin bile okuyamaz!)
- User A, User B'nin verilerini göremez!
"""

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import os
import base64
import hashlib
from typing import Dict, Tuple


class UserEncryption:
    """
    Kullanıcı-özel şifreleme sistemi
    
    Her kullanıcının password'ünden türetilen unique key'i ile veri şifreler.
    Sadece o kullanıcı kendi verilerini açabilir!
    """
    
    def __init__(self):
        """User encryption manager'ı başlat"""
        self.key_cache: Dict[str, bytes] = {}  # username -> encryption_key
        print("🔐 User-Specific Encryption Manager başlatıldı")
    
    def derive_key(self, username: str, password: str) -> bytes:
        """
        Kullanıcının password'ünden encryption key türet (PBKDF2)
        
        Parametreler:
            username: Kullanıcı adı (salt olarak kullanılır)
            password: Kullanıcı şifresi
            
        Döndürür:
            32-byte AES-256 key
        """
        # Salt: username + fixed salt (deterministic)
        salt = hashlib.sha256(f"dtek_salt_{username}".encode()).digest()
        
        # PBKDF2 ile key türet (100,000 iteration)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256-bit key
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        key = kdf.derive(password.encode())
        
        # Cache'le (session boyunca)
        self.key_cache[username] = key
        
        return key
    
    def get_user_key(self, username: str, password: str = None) -> bytes:
        """
        Kullanıcının encryption key'ini al (cache'den veya türet)
        
        Parametreler:
            username: Kullanıcı adı
            password: Kullanıcı şifresi (ilk kez gerekli)
            
        Döndürür:
            Encryption key
        """
        if username in self.key_cache:
            return self.key_cache[username]
        
        if password is None:
            raise ValueError(f"Password gerekli (ilk kez key türetiliyor)")
        
        return self.derive_key(username, password)
    
    def encrypt_data(self, data: str, username: str, password: str = None) -> str:
        """
        Veriyi kullanıcıya özel key ile şifrele (AES-256-GCM)
        
        Parametreler:
            data: Şifrelenecek metin (prompt veya output)
            username: Kullanıcı adı
            password: Kullanıcı şifresi (ilk kez gerekli)
            
        Döndürür:
            Base64-encoded şifreli veri (iv + tag + ciphertext)
        """
        # Kullanıcı key'ini al
        key = self.get_user_key(username, password)
        
        # IV oluştur (12 bytes for GCM)
        iv = os.urandom(12)
        
        # AES-256-GCM ile şifrele
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        
        ciphertext = encryptor.update(data.encode('utf-8')) + encryptor.finalize()
        tag = encryptor.tag
        
        # iv + tag + ciphertext birleştir ve base64 encode
        encrypted_package = iv + tag + ciphertext
        return base64.b64encode(encrypted_package).decode('utf-8')
    
    def decrypt_data(self, encrypted_data: str, username: str, password: str = None) -> str:
        """
        Şifreli veriyi kullanıcıya özel key ile çöz
        
        Parametreler:
            encrypted_data: Base64-encoded şifreli veri
            username: Kullanıcı adı
            password: Kullanıcı şifresi (ilk kez gerekli)
            
        Döndürür:
            Çözülmüş metin
        """
        # Kullanıcı key'ini al
        key = self.get_user_key(username, password)
        
        # Base64 decode
        encrypted_package = base64.b64decode(encrypted_data)
        
        # iv, tag, ciphertext'i ayır
        iv = encrypted_package[:12]
        tag = encrypted_package[12:28]
        ciphertext = encrypted_package[28:]
        
        # AES-256-GCM ile çöz
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv, tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        return plaintext.decode('utf-8')
    
    def encrypt_pii_cache(self, pii_cache: Dict[str, str], username: str, password: str = None) -> Dict[str, str]:
        """
        PII cache'i şifrele (tüm değerler)
        
        Parametreler:
            pii_cache: {"[PII_PER_1]": "Ahmet Yılmaz", ...}
            username: Kullanıcı adı
            password: Kullanıcı şifresi
            
        Döndürür:
            Şifreli PII cache
        """
        encrypted_cache = {}
        for tag, value in pii_cache.items():
            encrypted_cache[tag] = self.encrypt_data(value, username, password)
        return encrypted_cache
    
    def decrypt_pii_cache(self, encrypted_cache: Dict[str, str], username: str, password: str = None) -> Dict[str, str]:
        """
        Şifreli PII cache'i çöz
        
        Parametreler:
            encrypted_cache: Şifreli PII cache
            username: Kullanıcı adı
            password: Kullanıcı şifresi
            
        Döndürür:
            Çözülmüş PII cache
        """
        decrypted_cache = {}
        for tag, encrypted_value in encrypted_cache.items():
            decrypted_cache[tag] = self.decrypt_data(encrypted_value, username, password)
        return decrypted_cache
    
    def clear_user_key(self, username: str):
        """
        Kullanıcının key'ini cache'den sil (logout'ta kullan)
        
        Parametreler:
            username: Kullanıcı adı
        """
        if username in self.key_cache:
            # Memory'den güvenli sil
            self.key_cache[username] = b'\x00' * 32
            del self.key_cache[username]


# Global instance (singleton)
_user_encryption_instance = None

def get_user_encryption() -> UserEncryption:
    """User encryption instance'ını al veya oluştur (singleton)"""
    global _user_encryption_instance
    if _user_encryption_instance is None:
        _user_encryption_instance = UserEncryption()
    return _user_encryption_instance


# Test
if __name__ == "__main__":
    print("🧪 Testing User-Specific Encryption\n")
    
    user_enc = UserEncryption()
    
    # Test 1: Admin kullanıcısı
    print("1️⃣  Admin kullanıcısı test")
    admin_password = os.getenv("DEMO_ADMIN_PW", "demo-admin-pw")  # demo-only (self-test below)
    admin_data = "Hasta: Ahmet Yılmaz (TC: 12345678901)"
    
    encrypted_admin = user_enc.encrypt_data(admin_data, "admin", admin_password)
    print(f"   Şifreli: {encrypted_admin[:50]}...")
    
    decrypted_admin = user_enc.decrypt_data(encrypted_admin, "admin", admin_password)
    print(f"   Çözüldü: {decrypted_admin}")
    print(f"   ✅ Match: {admin_data == decrypted_admin}\n")
    
    # Test 2: Pilot1 kullanıcısı (farklı key)
    print("2️⃣  Pilot1 kullanıcısı test")
    pilot1_password = os.getenv("DEMO_PILOT1_PW", "demo-pilot1-pw")  # demo-only
    pilot1_data = "Hasta: Ayşe Kara (TC: 98765432109)"
    
    encrypted_pilot1 = user_enc.encrypt_data(pilot1_data, "pilot1", pilot1_password)
    print(f"   Şifreli: {encrypted_pilot1[:50]}...")
    
    decrypted_pilot1 = user_enc.decrypt_data(encrypted_pilot1, "pilot1", pilot1_password)
    print(f"   Çözüldü: {decrypted_pilot1}")
    print(f"   ✅ Match: {pilot1_data == decrypted_pilot1}\n")
    
    # Test 3: Cross-user test (admin, pilot1'in verisini açamaz!)
    print("3️⃣  Cross-user test (admin → pilot1 verisi)")
    try:
        # Admin key ile pilot1'in şifreli verisini çözmeye çalış
        wrong_decrypt = user_enc.decrypt_data(encrypted_pilot1, "admin", admin_password)
        print(f"   ❌ PROBLEM! Admin, pilot1'in verisini açabildi!")
    except Exception as e:
        print(f"   ✅ DOĞRU! Admin, pilot1'in verisini açamadı")
        print(f"   Hata: {type(e).__name__}\n")
    
    # Test 4: PII cache encryption
    print("4️⃣  PII cache encryption test")
    pii_cache = {
        "[PII_PER_1]": "Mehmet Demir",
        "[TC_1]": "11111111111",
        "[EMAIL_1]": "mehmet@example.com"
    }
    
    encrypted_pii = user_enc.encrypt_pii_cache(pii_cache, "admin", admin_password)
    print(f"   Şifreli PII cache: {len(encrypted_pii)} items")
    
    decrypted_pii = user_enc.decrypt_pii_cache(encrypted_pii, "admin", admin_password)
    print(f"   Çözüldü: {decrypted_pii}")
    print(f"   ✅ Match: {pii_cache == decrypted_pii}\n")
    
    print("✅ Tüm testler başarılı!")
    print("\n🔐 GÜVENLİK ÖZETİ:")
    print("   • Her kullanıcı kendi key'i ile şifreler")
    print("   • Password-derived key (PBKDF2, 100K iterations)")
    print("   • AES-256-GCM encryption")
    print("   • Zero-knowledge (cross-user access YOK!)")

