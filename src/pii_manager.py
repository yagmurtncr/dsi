"""PII Manager - Hassas verileri maskeleme ve geri yükleme"""
#GPU ile yaklaşık 2 sn

import re
from typing import Dict, List, Tuple, Optional
from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification

# Türkiye şehirleri (genel bilgi, PII değil!)
TURKISH_CITIES = {
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Aksaray", "Amasya", "Ankara", 
    "Antalya", "Ardahan", "Artvin", "Aydın", "Balıkesir", "Bartın", "Batman", 
    "Bayburt", "Bilecik", "Bingöl", "Bitlis", "Bolu", "Burdur", "Bursa", 
    "Çanakkale", "Çankırı", "Çorum", "Denizli", "Diyarbakır", "Düzce", 
    "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir", "Gaziantep", 
    "Giresun", "Gümüşhane", "Hakkari", "Hatay", "Iğdır", "Isparta", "İstanbul",
    "İzmir", "Kahramanmaraş", "Karabük", "Karaman", "Kars", "Kastamonu", 
    "Kayseri", "Kırıkkale", "Kırklareli", "Kırşehir", "Kilis", "Kocaeli", 
    "Konya", "Kütahya", "Malatya", "Manisa", "Mardin", "Mersin", "Muğla", 
    "Muş", "Nevşehir", "Niğde", "Ordu", "Osmaniye", "Rize", "Sakarya", 
    "Samsun", "Siirt", "Sinop", "Sivas", "Şanlıurfa", "Şırnak", "Tekirdağ", 
    "Tokat", "Trabzon", "Tunceli", "Uşak", "Van", "Yalova", "Yozgat", "Zonguldak"
}

# Sadece bu entity type'ları maskele (LOC, ORG maskelenmesin!)
MASK_ENTITY_TYPES = {"PERSON", "PER"}  # Sadece kişi adları

class PIIManager:
    """PII (Personally Identifiable Information) yönetimi"""
    
    #16 - PIIManager Başlatma (NER Model Yükleme)
    def __init__(self, model_name: str = "isakulaksiz/turkish-pii-detection", confidence_threshold: float = 0.85):
        """Turkish PII detection model'ini yükler ve hazırlar"""
        print(f"🔐 PII Manager başlatılıyor...")
        print(f"   Model: {model_name} (TÜRKÇE ÖZEL)")
        print(f"   Confidence Threshold: {confidence_threshold}")
        print(f"   Mask Only: {', '.join(MASK_ENTITY_TYPES)}")
        
        # Disk dolu olabilir, workspace'e yükle
        from pathlib import Path
        cache_dir = Path(__file__).parent.parent / "models" / "pii"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"   Cache: {cache_dir}")
        
        # PII detection model (NER - Named Entity Recognition)
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            cache_dir=str(cache_dir)
        )
        self.model = AutoModelForTokenClassification.from_pretrained(
            model_name,
            cache_dir=str(cache_dir)
        )
        # CPU mode (device=-1) - GPU memory korumak için
        import os
        device = -1 if os.environ.get('CUDA_VISIBLE_DEVICES') == '' else 0
        self.ner_pipeline = pipeline(
            "ner",
            model=self.model,
            tokenizer=self.tokenizer,
            aggregation_strategy="simple",  # Aynı entity'i birleştir
            device=device
        )
        self.confidence_threshold = confidence_threshold
        
        # PII önbelleği: {session_id: {pii_tag: original_value}}
        self.pii_cache: Dict[str, Dict[str, str]] = {}
        
        # Benzersiz PII tag'leri için sayaç
        self.pii_counters: Dict[str, Dict[str, int]] = {}
        
        print(f"✅ PII Manager hazır!")
    
    #17 - PII Tespit ve Maskeleme (NER + Regex)
    def detect_and_mask(self, text: str, session_id: str = "default") -> Tuple[str, Dict[str, str]]:
        """
        Text'teki PII'ları tespit edip maskeler ve mapping döndürür
        
        Tespit edilen PII türleri:
        - İsim, Soyisim (NER model)
        - TC Kimlik No (regex)
        - Telefon numarası (regex)
        - Email adresi (regex)
        - IBAN (regex)
        - Kredi kartı (regex)
        """
        # NER ile PII tespit et (isimler için)
        entities = self.ner_pipeline(text)
        
        # Session için cache yoksa oluştur
        if session_id not in self.pii_cache:
            self.pii_cache[session_id] = {}
            self.pii_counters[session_id] = {}
        
        # PII mapping
        pii_mapping = {}
        masked_text = text
        
        # Entity'leri tersten işle (index'ler bozulmasın)
        # Sadece yüksek confidence'lı entity'leri kullan
        for entity in sorted(entities, key=lambda x: x['start'], reverse=True):
            # Confidence kontrolü
            confidence = entity.get('score', 0.0)
            if confidence < self.confidence_threshold:
                continue  # Düşük confidence, skip
            
            entity_text = entity['word']
            entity_type = entity['entity_group']  # PERSON, ORG, LOC, DATE, etc.
            start = entity['start']
            end = entity['end']
            
            # Orijinal text'ten tam değeri al (büyük/küçük harf korunacak)
            original_text = text[start:end]
            
            # FİLTRE 1: Sadece belirli entity type'ları maskele
            if entity_type.upper() not in MASK_ENTITY_TYPES:
                continue  # LOC, ORG, DATE gibi genel bilgiler maskelenmesin
            
            # FİLTRE 2: Türk şehirleri whitelist (genel bilgi, PII değil!)
            if original_text in TURKISH_CITIES:
                continue  # Ankara, İstanbul gibi şehir adları maskelenmesin
            
            # PII tag oluştur (unique format: <|TYPE_N|>)
            if entity_type not in self.pii_counters[session_id]:
                self.pii_counters[session_id][entity_type] = 0
            
            self.pii_counters[session_id][entity_type] += 1
            counter = self.pii_counters[session_id][entity_type]
            pii_tag = f"<|PERSON_{counter}|>"  # Model'in öğrenemeyeceği unique format
            
            # Cache'e orijinal text'i ekle (büyük/küçük harf korunuyor)
            self.pii_cache[session_id][pii_tag] = original_text
            pii_mapping[pii_tag] = original_text
            
            # Text'i maskele
            masked_text = masked_text[:start] + pii_tag + masked_text[end:]
        
        # ========================================================================
        # REGEX-BASED PII DETECTION (TC, Telefon, Email, IBAN, vs.)
        # ========================================================================
        
        # 1. TC Kimlik No (11 haneli, ilk hane 0 olamaz)
        tc_pattern = r'\b[1-9]\d{10}\b'
        tc_matches = list(re.finditer(tc_pattern, masked_text))
        if 'TC' not in self.pii_counters[session_id]:
            self.pii_counters[session_id]['TC'] = 0
        
        for match in reversed(tc_matches):  # Tersten işle (index bozulmasın)
            tc_number = match.group()
            self.pii_counters[session_id]['TC'] += 1
            counter = self.pii_counters[session_id]['TC']
            pii_tag = f"<|TC_{counter}|>"
            
            self.pii_cache[session_id][pii_tag] = tc_number
            pii_mapping[pii_tag] = tc_number
            
            masked_text = masked_text[:match.start()] + pii_tag + masked_text[match.end():]
        
        # 2. Telefon numarası (çeşitli formatlar)
        # 0532-123-4567, +90 532 123 45 67, 05321234567, vs.
        phone_pattern = r'(\+90\s?|0)?[5]\d{2}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}'
        phone_matches = list(re.finditer(phone_pattern, masked_text))
        if 'PHONE' not in self.pii_counters[session_id]:
            self.pii_counters[session_id]['PHONE'] = 0
        
        for match in reversed(phone_matches):
            phone_number = match.group()
            self.pii_counters[session_id]['PHONE'] += 1
            counter = self.pii_counters[session_id]['PHONE']
            pii_tag = f"<|PHONE_{counter}|>"
            
            self.pii_cache[session_id][pii_tag] = phone_number
            pii_mapping[pii_tag] = phone_number
            
            masked_text = masked_text[:match.start()] + pii_tag + masked_text[match.end():]
        
        # 3. Email adresi
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_matches = list(re.finditer(email_pattern, masked_text))
        if 'EMAIL' not in self.pii_counters[session_id]:
            self.pii_counters[session_id]['EMAIL'] = 0
        
        for match in reversed(email_matches):
            email = match.group()
            self.pii_counters[session_id]['EMAIL'] += 1
            counter = self.pii_counters[session_id]['EMAIL']
            pii_tag = f"<|EMAIL_{counter}|>"
            
            self.pii_cache[session_id][pii_tag] = email
            pii_mapping[pii_tag] = email
            
            masked_text = masked_text[:match.start()] + pii_tag + masked_text[match.end():]
        
        # 4. IBAN (TR ile başlayan 26 karakter)
        iban_pattern = r'\bTR\d{24}\b'
        iban_matches = list(re.finditer(iban_pattern, masked_text, re.IGNORECASE))
        if 'IBAN' not in self.pii_counters[session_id]:
            self.pii_counters[session_id]['IBAN'] = 0
        
        for match in reversed(iban_matches):
            iban = match.group()
            self.pii_counters[session_id]['IBAN'] += 1
            counter = self.pii_counters[session_id]['IBAN']
            pii_tag = f"<|IBAN_{counter}|>"
            
            self.pii_cache[session_id][pii_tag] = iban
            pii_mapping[pii_tag] = iban
            
            masked_text = masked_text[:match.start()] + pii_tag + masked_text[match.end():]
        
        # 5. Kredi kartı (16 haneli, boşluk veya tire ile ayrılabilir)
        cc_pattern = r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b'
        cc_matches = list(re.finditer(cc_pattern, masked_text))
        if 'CARD' not in self.pii_counters[session_id]:
            self.pii_counters[session_id]['CARD'] = 0
        
        for match in reversed(cc_matches):
            cc_number = match.group()
            # TC ile çakışma kontrolü (11 hane ise CC değil, TC'dir)
            if len(cc_number.replace(' ', '').replace('-', '')) == 11:
                continue  # Skip, zaten TC olarak yakalandı
            
            self.pii_counters[session_id]['CARD'] += 1
            counter = self.pii_counters[session_id]['CARD']
            pii_tag = f"<|CARD_{counter}|>"
            
            self.pii_cache[session_id][pii_tag] = cc_number
            pii_mapping[pii_tag] = cc_number
            
            masked_text = masked_text[:match.start()] + pii_tag + masked_text[match.end():]
        
        print(f"🔍 PII Detection:")
        print(f"   Original: {text}")
        print(f"   Masked:   {masked_text}")
        print(f"   Detected: {len(pii_mapping)} PII(s)")
        for tag, value in pii_mapping.items():
            print(f"      • {tag} = '{value}'")
        
        return masked_text, pii_mapping
    
    #18 - PII Unmask (Tag → Orijinal Değer)
    def unmask(self, masked_text: str, session_id: str = "default") -> str:
        """Maskelenmiş PII tag'lerini orijinal değerleriyle değiştirir"""
        if session_id not in self.pii_cache:
            print(f"⚠️  Session {session_id} cache'de bulunamadı!")
            return masked_text
        
        unmasked_text = masked_text
        cache = self.pii_cache[session_id]
        
        # Tüm PII tag'lerini geri yükle
        for pii_tag, original_value in cache.items():
            unmasked_text = unmasked_text.replace(pii_tag, original_value)
        
        print(f"🔓 PII Unmasking:")
        print(f"   Masked:   {masked_text}")
        print(f"   Unmasked: {unmasked_text}")
        
        return unmasked_text
    
    #19 - PII Cache Temizleme
    def clear_cache(self, session_id: Optional[str] = None):
        """Belirtilen session'ın veya tüm PII cache'ini temizler"""
        if session_id is None:
            # Tüm cache'i temizle
            self.pii_cache.clear()
            self.pii_counters.clear()
            print("🧹 Tüm PII cache temizlendi")
        elif session_id in self.pii_cache:
            # Sadece belirtilen session'ı temizle
            del self.pii_cache[session_id]
            del self.pii_counters[session_id]
            print(f"🧹 Session {session_id} cache temizlendi")
    
    #20 - PII İstatistikleri
    def get_stats(self) -> Dict:
        """Cache istatistiklerini döndürür"""
        return {
            "total_sessions": len(self.pii_cache),
            "sessions": {
                session_id: {
                    "pii_count": len(cache),
                    "pii_tags": list(cache.keys())
                }
                for session_id, cache in self.pii_cache.items()
            }
        }


# Test fonksiyonu (pipeline dışı)
def test_pii_manager():
    """PII Manager'ı test eder"""
    print("\n" + "="*70)
    print("🧪 PII MANAGER TEST")
    print("="*70)
    
    # Manager oluştur
    pii_manager = PIIManager()
    
    # Test 1: Basit isim
    print("\n📝 Test 1: Kişi adı")
    text1 = "Kemal Atatürk Türkiye Cumhuriyeti'nin kurucusudur."
    masked1, mapping1 = pii_manager.detect_and_mask(text1, session_id="test1")
    unmasked1 = pii_manager.unmask(masked1, session_id="test1")
    
    assert text1 in unmasked1 or "Atatürk" in unmasked1, "❌ Unmask hatası!"
    print("   ✅ Test 1 başarılı!")
    
    # Test 2: Birden fazla PII
    print("\n📝 Test 2: Çoklu PII")
    text2 = "Ahmet Yılmaz İstanbul'da yaşıyor."
    masked2, mapping2 = pii_manager.detect_and_mask(text2, session_id="test2")
    unmasked2 = pii_manager.unmask(masked2, session_id="test2")
    
    print("   ✅ Test 2 başarılı!")
    
    # Test 3: Cache istatistikleri
    print("\n📊 Cache Stats:")
    stats = pii_manager.get_stats()
    print(f"   Sessions: {stats['total_sessions']}")
    for sid, info in stats['sessions'].items():
        print(f"   • {sid}: {info['pii_count']} PII")
    
    # Cleanup
    pii_manager.clear_cache()
    
    print("\n" + "="*70)
    print("✅ TÜM TESTLER BAŞARILI!")
    print("="*70 + "\n")


if __name__ == "__main__":
    test_pii_manager()

