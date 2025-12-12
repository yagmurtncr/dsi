#!/bin/bash

# 🧪 Manuel Test Script - DSI (Distributed Secure Inference)
# Server başladıktan sonra bu script'i çalıştır!

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                                                                      ║"
echo "║            🧪 DSI - DISTRIBUTED SECURE INFERENCE TEST                ║"
echo "║                    3 Node Dağıtık LLM Sistemi                        ║"
echo "║                                                                      ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# Renkler
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Server URL
SERVER_URL="http://localhost:9000"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 ADIM 1: HEALTH CHECK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

HEALTH=$(curl -s $SERVER_URL/health 2>/dev/null)
if [ $? -eq 0 ] && [ ! -z "$HEALTH" ]; then
    echo "$HEALTH" | python3 -m json.tool 2>/dev/null || echo "$HEALTH"
    echo -e "\n${GREEN}✅ API Server çalışıyor!${NC}\n"
else
    echo -e "\n${RED}❌ API Server çalışmıyor! Önce başlat:${NC}"
    echo "   cd /mnt/development/ubuntu/nytuncer/dsi"
    echo "   python3 src/api_secure_v2.py"
    exit 1
fi

# Node durumunu kontrol et
echo -e "${CYAN}📊 Node Durumu:${NC}"
for port in 9080 9081 9082; do
    if lsof -i :$port 2>/dev/null | grep -q LISTEN; then
        case $port in
            9080) echo -e "   Node 1 (Embedder):  ${GREEN}✅ Aktif${NC}" ;;
            9081) echo -e "   Node 2 (Processor): ${GREEN}✅ Aktif${NC}" ;;
            9082) echo -e "   Node 3 (Head):      ${GREEN}✅ Aktif${NC}" ;;
        esac
    else
        case $port in
            9080) echo -e "   Node 1 (Embedder):  ${RED}❌ Kapalı${NC}" ;;
            9081) echo -e "   Node 2 (Processor): ${RED}❌ Kapalı${NC}" ;;
            9082) echo -e "   Node 3 (Head):      ${RED}❌ Kapalı${NC}" ;;
        esac
    fi
done
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔐 ADIM 2: LOGIN - TOKEN AL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo -e "${YELLOW}Username: yagmur${NC}"
echo -e "${YELLOW}Password: yagmur123${NC}"
echo ""

TOKEN_RESPONSE=$(curl -s -X POST $SERVER_URL/login \
  -H "Content-Type: application/json" \
  -d '{"username":"yagmur","password":"yagmur123"}')

echo "$TOKEN_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$TOKEN_RESPONSE"

TOKEN=$(echo $TOKEN_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo -e "\n${RED}❌ Token alınamadı!${NC}"
    exit 1
fi

echo -e "\n${GREEN}✅ Token alındı!${NC}"
echo ""

echo "Devam etmek için Enter'a bas..."
read

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 ADIM 3: TEST ÖRNEKLERİ (5 Gerçek Laboratuvar Vakası)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Decrypt fonksiyonu
decrypt_response() {
    python3 << PYEOF
import sys, json
sys.path.insert(0, 'src')

try:
    data = json.loads('''$1''')
    
    if data.get('encrypted'):
        from security import get_user_encryption
        ue = get_user_encryption()
        ue.derive_key('yagmur', 'yagmur123')
        decrypted = json.loads(ue.decrypt_data(data['ciphertext'], 'yagmur', 'yagmur123'))
        
        text = decrypted.get('generated_text', 'N/A')
        time_taken = decrypted.get('time_taken', 0)
        pii = decrypted.get('pii_detected', 0)
        
        print(f"✅ Response: {text[:300]}...")
        print(f"⏱️  Süre: {time_taken:.1f}s")
        print(f"🎭 PII Tespit: {pii} adet")
        print(f"🔐 E2E Encryption: Aktif")
    elif 'detail' in data:
        print(f"❌ Hata: {data['detail']}")
    else:
        print(f"Response: {data}")
except Exception as e:
    print(f"❌ Parse hatası: {e}")
PYEOF
}

# Test 1: Demir Eksikliği Anemisi
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}TEST 1: Demir Eksikliği Anemisi${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

RESPONSE=$(curl -s -X POST $SERVER_URL/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Zeynep Arslan, 28 yaş, TC: 11223344556. Hemogram: RBC 3.2 (düşük), Hemoglobin 9.8 g/dL (düşük), MCV 68 fL (düşük), Ferritin 8 ng/mL (çok düşük). Tanı ve tedavi öner.",
    "max_tokens": 100,
    "temperature": 0.2,
    "enable_pii_protection": true
  }')

decrypt_response "$RESPONSE"

echo ""
echo "Devam etmek için Enter'a bas..."
read

# Test 2: Kronik Böbrek Hastalığı
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}TEST 2: Kronik Böbrek Hastalığı${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

RESPONSE=$(curl -s -X POST $SERVER_URL/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Ali Yılmaz, 62 yaş, TC: 22334455667, Tel: 05441234567. Böbrek fonksiyon testleri: Kreatinin 3.8 mg/dL (yüksek), eGFR 28 mL/dk/1.73m² (çok düşük), BUN 48 mg/dL (yüksek), Potasyum 5.9 mEq/L (yüksek). Tanı ve tedavi öner.",
    "max_tokens": 100,
    "temperature": 0.2,
    "enable_pii_protection": true
  }')

decrypt_response "$RESPONSE"

echo ""
echo "Devam etmek için Enter'a bas..."
read

# Test 3: Tip 2 Diyabet
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}TEST 3: Tip 2 Diyabet${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

RESPONSE=$(curl -s -X POST $SERVER_URL/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Elif Demir, 45 yaş. HbA1c %7.8 (yüksek), Açlık kan şekeri 156 mg/dL (yüksek). Tanı ve öneriler?",
    "max_tokens": 80,
    "temperature": 0.2,
    "enable_pii_protection": true
  }')

decrypt_response "$RESPONSE"

echo ""
echo "Devam etmek için Enter'a bas..."
read

# Test 4: Hipertansiyon + Dislipidemi
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}TEST 4: Hipertansiyon + Dislipidemi${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

RESPONSE=$(curl -s -X POST $SERVER_URL/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Mehmet Kaya, 58 yaş, TC: 33445566778. Vital bulgular: Tansiyon 165/98 mmHg (yüksek), Kalp hızı 88/dk. Lipid paneli: Total Kolesterol 245 mg/dL (yüksek), LDL 168 mg/dL (yüksek), HDL 38 mg/dL (düşük). Tanı ve tedavi yaklaşımı?",
    "max_tokens": 100,
    "temperature": 0.2,
    "enable_pii_protection": true
  }')

decrypt_response "$RESPONSE"

echo ""
echo "Devam etmek için Enter'a bas..."
read

# Test 5: Hipotiroidizm
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}TEST 5: Hipotiroidizm${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

RESPONSE=$(curl -s -X POST $SERVER_URL/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Ayşe Şahin, 35 yaş, Tel: 05331234567. Tiroid fonksiyon testleri: TSH 8.9 mIU/L (yüksek), Serbest T4 0.7 ng/dL (düşük), Anti-TPO 450 IU/mL (yüksek). Şikayetler: Yorgunluk, kilo alımı, saç dökülmesi. Tanı ve tedavi?",
    "max_tokens": 100,
    "temperature": 0.2,
    "enable_pii_protection": true
  }')

decrypt_response "$RESPONSE"

echo ""
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ TESTLER TAMAMLANDI!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                         📊 DSI ÖZELLİKLERİ                           ║"
echo "╠══════════════════════════════════════════════════════════════════════╣"
echo "║  🔐 E2E Encryption     : AES-256-GCM (Client ↔ Server)               ║"
echo "║  🔒 Inter-Node Crypto  : RSA-2048 + AES-256-GCM                      ║"
echo "║  🎭 PII Masking        : AI NER (isakulaksiz/turkish-pii-detection)  ║"
echo "║  🛡️  RBAC              : admin, user, pilot, readonly                ║"
echo "║  ⚡ Rate Limiting      : IP + User + Endpoint bazlı                  ║"
echo "║  📝 Audit Logging      : Tüm işlemler loglanır                       ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

echo "📊 Daha fazla test için:"
echo "   • Swagger UI: http://localhost:9000/docs"
echo "   • Port Forward: VS Code/Cursor → localhost:9000"
echo "   • HIZLI_BASLANGIC.md'deki örnekleri incele"
echo ""

