"""
🔒 KVKK Audit Logger - Kurcalanmaz Log Sistemi
Ne İşe Yarar: Tüm kullanıcı işlemlerini SHA-256 chain ile güvenli şekilde loglar (KVKK/GDPR uyumlu)

Özellikler:
- SHA-256 chain ile log bütünlüğü (blockchain benzeri)
- Kim, ne zaman, hangi veriyi işledi (KVKK Madde 12)
- Kalıcı dosya kaydı (.jsonl format)
"""

import hashlib
import json
import os
from datetime import datetime
from typing import Dict, Optional, Any
from pathlib import Path
import threading

class AuditLogger:
    """SHA-256 chain ile kurcalanmaz audit logging (blockchain benzeri yapı)"""
    
    def __init__(self, log_dir: str = "/mnt/development/ubuntu/nytuncer/dsi/logs/audit"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Günlük log dosyası
        today = datetime.now().strftime("%Y-%m-%d")
        self.log_file = self.log_dir / f"audit_{today}.jsonl"
        
        # Son log'un hash'i (chain için)
        self.last_hash = self._get_last_hash()
        
        # Thread safety
        self.lock = threading.Lock()
        
        print(f"✅ Audit Logger başlatıldı: {self.log_file}")
    
    def _get_last_hash(self) -> str:
        """Son log entry'nin hash'ini al (chain'i devam ettirmek için)"""
        if not self.log_file.exists():
            # İlk log için genesis hash
            return hashlib.sha256(b"GENESIS_AUDIT_LOG").hexdigest()
        
        try:
            # Son satırı oku
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if lines:
                    last_log = json.loads(lines[-1])
                    return last_log.get('hash', self._genesis_hash())
        except Exception as e:
            print(f"⚠️  Son hash okunamadı: {e}")
        
        return self._genesis_hash()
    
    def _genesis_hash(self) -> str:
        """Genesis hash (zincirin ilk halkası)"""
        return hashlib.sha256(b"GENESIS_AUDIT_LOG").hexdigest()
    
    def _calculate_hash(self, log_entry: Dict) -> str:
        """Log entry + önceki hash ile yeni hash hesapla (blockchain mantığı)"""
        # Önemli alanları al (hash hariç)
        data_to_hash = {
            'timestamp': log_entry['timestamp'],
            'user_id': log_entry['user_id'],
            'action': log_entry['action'],
            'endpoint': log_entry.get('endpoint', ''),
            'pii_detected': log_entry.get('pii_detected', False),
            'previous_hash': self.last_hash #Önceki log'un hash'ini de ekler (blockchain mantığı)
        }
        
        # JSON string'e çevir ve hash'le
        json_str = json.dumps(data_to_hash, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def log(
        self,
        user_id: str,
        action: str,
        endpoint: str = "",
        request_data: Optional[Dict] = None,
        response_status: Optional[int] = None,
        pii_detected: bool = False,
        pii_types: Optional[list] = None,
        ip_address: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Audit log kaydı oluştur
        
        Args:
            user_id: Kullanıcı ID veya 'anonymous'
            action: Yapılan işlem (login, query, delete, etc.)
            endpoint: API endpoint
            request_data: İstek verisi (sanitized)
            response_status: HTTP status code
            pii_detected: PII tespit edildi mi?
            pii_types: Tespit edilen PII türleri ['name', 'email', 'tc']
            ip_address: İstemci IP adresi
            metadata: Ek bilgiler
        
        Returns:
            Log entry hash (doğrulama için)
        """
        with self.lock:
            # Log entry oluştur
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'user_id': user_id,
                'action': action,
                'endpoint': endpoint,
                'request_data_size': len(str(request_data)) if request_data else 0,
                'response_status': response_status,
                'pii_detected': pii_detected,
                'pii_types': pii_types or [],
                'ip_address': ip_address or 'unknown',
                'metadata': metadata or {},
                'previous_hash': self.last_hash
            }
            
            # Hash hesapla
            current_hash = self._calculate_hash(log_entry)
            log_entry['hash'] = current_hash
            
            # Dosyaya yaz
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                
                # Son hash'i güncelle
                self.last_hash = current_hash
                
                return current_hash
            
            except Exception as e:
                print(f"❌ Audit log yazma hatası: {e}")
                return ""
    
    def verify_integrity(self) -> tuple[bool, Optional[int]]:
        """
        Log chain'inin bütünlüğünü doğrula (tüm hash'leri yeniden hesaplar)
        
        Döndürür:
            (geçerli_mi, ilk_bozuk_satır_no)
        """
        if not self.log_file.exists():
            return True, None
        
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            expected_hash = self._genesis_hash()
            
            for idx, line in enumerate(lines, start=1):
                log_entry = json.loads(line)
                
                # Önceki hash kontrolü
                if log_entry['previous_hash'] != expected_hash:
                    print(f"❌ Hash uyuşmazlığı satır {idx}!")
                    print(f"   Beklenen: {expected_hash}")
                    print(f"   Bulunan:  {log_entry['previous_hash']}")
                    return False, idx
                
                # Mevcut hash'i yeniden hesapla
                saved_hash = log_entry['hash']
                temp_last_hash = self.last_hash
                self.last_hash = expected_hash
                calculated_hash = self._calculate_hash(log_entry)
                self.last_hash = temp_last_hash
                
                if calculated_hash != saved_hash:
                    print(f"❌ Hash değiştirilmiş satır {idx}!")
                    return False, idx
                
                expected_hash = saved_hash
            
            print(f"✅ Log chain bütünlüğü doğrulandı ({len(lines)} kayıt)")
            return True, None
        
        except Exception as e:
            print(f"❌ Doğrulama hatası: {e}")
            return False, None
    
    def get_logs(
        self, 
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        pii_only: bool = False
    ) -> list:
        """
        Log kayıtlarını filtrele ve getir
        
        Args:
            start_date: Başlangıç tarihi (ISO format)
            end_date: Bitiş tarihi (ISO format)
            user_id: Kullanıcı filtresi
            action: İşlem filtresi
            pii_only: Sadece PII içeren kayıtlar
        
        Returns:
            Filtrelenmiş log listesi
        """
        if not self.log_file.exists():
            return []
        
        logs = []
        
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    log_entry = json.loads(line)
                    
                    # Filtreler
                    if start_date and log_entry['timestamp'] < start_date:
                        continue
                    if end_date and log_entry['timestamp'] > end_date:
                        continue
                    if user_id and log_entry['user_id'] != user_id:
                        continue
                    if action and log_entry['action'] != action:
                        continue
                    if pii_only and not log_entry['pii_detected']:
                        continue
                    
                    logs.append(log_entry)
            
            return logs
        
        except Exception as e:
            print(f"❌ Log okuma hatası: {e}")
            return []
    
    def get_user_activity(self, user_id: str) -> Dict[str, Any]:
        """Kullanıcının tüm aktivitelerini getir (GDPR export için)"""
        logs = self.get_logs(user_id=user_id)
        
        return {
            'user_id': user_id,
            'total_requests': len(logs),
            'pii_requests': sum(1 for log in logs if log['pii_detected']),
            'first_activity': logs[0]['timestamp'] if logs else None,
            'last_activity': logs[-1]['timestamp'] if logs else None,
            'activities': logs
        }
    
    def delete_user_logs(self, user_id: str) -> int:
        """
        Kullanıcının log kayıtlarını sil (GDPR right to be forgotten)
        
        NOT: Bu işlem log chain'ini bozar! Production'da dikkatli kullan.
        Alternatif: Log'ları anonimleştir (user_id -> 'DELETED_USER_XXX')
        
        Returns:
            Silinen kayıt sayısı
        """
        if not self.log_file.exists():
            return 0
        
        try:
            # Tüm log'ları oku
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Kullanıcıya ait olmayanları sakla
            remaining_logs = []
            deleted_count = 0
            
            for line in lines:
                log_entry = json.loads(line)
                if log_entry['user_id'] == user_id:
                    deleted_count += 1
                else:
                    remaining_logs.append(line)
            
            # Dosyayı yeniden yaz
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.writelines(remaining_logs)
            
            print(f"✅ {deleted_count} log kaydı silindi (user: {user_id})")
            
            # Chain'i yeniden başlat
            self.last_hash = self._get_last_hash()
            
            return deleted_count
        
        except Exception as e:
            print(f"❌ Log silme hatası: {e}")
            return 0


# Singleton instance
_audit_logger_instance = None

def get_audit_logger() -> AuditLogger:
    """Global audit logger instance'ını al"""
    global _audit_logger_instance
    if _audit_logger_instance is None:
        _audit_logger_instance = AuditLogger()
    return _audit_logger_instance


# Test
if __name__ == "__main__":
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("KVKK Audit Logger Test")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    logger = AuditLogger(log_dir="logs/test_audit")
    
    # Test 1: Normal request
    print("\n1️⃣  Normal request log...")
    hash1 = logger.log(
        user_id="user_123",
        action="query",
        endpoint="/api/generate",
        request_data={"prompt": "Merhaba"},
        response_status=200,
        pii_detected=False,
        ip_address="192.168.1.100"
    )
    print(f"   Hash: {hash1[:16]}...")
    
    # Test 2: PII detected request
    print("\n2️⃣  PII içeren request log...")
    hash2 = logger.log(
        user_id="user_456",
        action="query",
        endpoint="/api/generate",
        request_data={"prompt": "Benim adım Ahmet Yılmaz"},
        response_status=200,
        pii_detected=True,
        pii_types=["name"],
        ip_address="192.168.1.101"
    )
    print(f"   Hash: {hash2[:16]}...")
    
    # Test 3: Login
    print("\n3️⃣  Login log...")
    hash3 = logger.log(
        user_id="user_789",
        action="login",
        endpoint="/api/login",
        response_status=200,
        ip_address="192.168.1.102"
    )
    print(f"   Hash: {hash3[:16]}...")
    
    # Test 4: Integrity check
    print("\n4️⃣  Log chain bütünlük kontrolü...")
    is_valid, corrupted_line = logger.verify_integrity()
    
    if is_valid:
        print("   ✅ Log chain bütünlüğü SAĞLAM!")
    else:
        print(f"   ❌ Log chain BOZUK! (Satır: {corrupted_line})")
    
    # Test 5: Query logs
    print("\n5️⃣  PII içeren log kayıtları...")
    pii_logs = logger.get_logs(pii_only=True)
    print(f"   {len(pii_logs)} PII kaydı bulundu")
    
    # Test 6: User activity
    print("\n6️⃣  Kullanıcı aktivitesi (user_456)...")
    activity = logger.get_user_activity("user_456")
    print(f"   Toplam request: {activity['total_requests']}")
    print(f"   PII request: {activity['pii_requests']}")
    
    print("\n✅ Test tamamlandı!")
    print(f"📁 Log dosyası: {logger.log_file}")

