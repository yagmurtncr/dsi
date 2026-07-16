# 🔐 D-TEK: Distributed Secure LLM

<div align="center">

![Version](https://img.shields.io/badge/version-3.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![Security](https://img.shields.io/badge/security-9.4%2F10-brightgreen.svg)

**3 node'a dağıtılmış, şifreli, PII korumalı LLM sistemi**

</div>

## 🎯 Nedir?

Model katmanları 3 farklı node'a bölünmüş, güvenli LLM sistemi. Hiçbir node tek başına model çalıştıramaz. Tüm iletişim şifreli, PII verileri otomatik maskelenir.

## ✨ Özellikler

- ✅ **3 Node Distributed** → Model parçalanmış, tek node çalışmaz
- ✅ **Multi-Layer Encryption** → TLS + RSA-2048 + AES-256-GCM
- ✅ **PII Protection** → TC, Telefon, Email, IBAN otomatik maskeleme
- ✅ **JWT Authentication** → Güvenli kimlik doğrulama
- ✅ **RBAC** → Rol bazlı erişim kontrolü
- ✅ **Rate Limiting** → DDoS koruması
- ✅ **Audit Logging** → KVKK/GDPR uyumlu

## 🏗️ Mimari

```mermaid
flowchart TB
    Client["👤 Client<br/>(Swagger / cURL / SDK)"] -->|"HTTPS/TLS 1.3 + JWT"| API

    subgraph API["🔒 API Server (:9000)"]
        direction LR
        AUTH["JWT Auth"] --> RL["Rate limit (20/dk)"] --> IV["Input validation<br/>(XSS / SQLi)"] --> RBAC["RBAC"]
        ENC["🔐 Response encryption<br/>(AES-256-GCM)"]
    end

    API --> PII["🛡️ PII Node (:7000)<br/>Turkish NER + regex<br/>(TC / tel / e-posta / IBAN)<br/>mask · unmask"]
    API --> LLM

    subgraph LLM["🧠 Distributed LLM · RSA+AES between nodes"]
        direction LR
        N1["Node 1 (:8001)<br/>tokenizer · embedding<br/>layers 0–10"] --> N2["Node 2 (:8002)<br/>layers 11–21"] --> N3["Node 3 (:8003)<br/>layers 22–31 · LM head"]
    end
```

## 🔐 Güvenlik

| # | Katman | Teknoloji | Açıklama |
|---|--------|-----------|----------|
| 1 | **Transport** | HTTPS/TLS 1.3 | Client↔API şifreli iletişim |
| 2 | **Authentication** | JWT (HS256) | 60 dakika geçerli token |
| 3 | **Rate Limiting** | 20 req/dk | DDoS koruması |
| 4 | **Input Validation** | Regex + Sanitization | XSS, SQLi, Prompt Injection |
| 5 | **Response Encryption** | AES-256-GCM | Şifreli response |
| 6 | **Node↔Node Crypto** | RSA-2048 + AES-256 | Hidden states şifreli |
| 7 | **PII Protection** | NER + Regex | TC, Tel, Email, IBAN |
| 8 | **RBAC** | Role-based | admin, user, pilot, readonly |
| 9 | **Session Management** | Timeout | 60 dk inaktivite |
| 10 | **Audit Logging** | SHA-256 | KVKK/GDPR uyumlu log |

**Güvenlik Skoru: 9.4/10** ✅

## 📦 Kurulum

```bash
# 1. Clone
git clone https://github.com/nytuncer/dsi.git
cd dsi

# 2. Dependencies
pip install -r requirements.txt

# 3. Environment
cp .env.example .env
nano .env  # Düzenle

# 4. SSL
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -nodes \
  -keyout certs/key.pem -out certs/cert.pem -days 365

# 5. Model (Hugging Face)
huggingface-cli download meta-llama/Llama-3.1-8B-Instruct \
  --local-dir models/llama-3.1-8b-instruct
```

## 🚀 Başlatma

```bash
# Node'ları başlat (4 terminal)
python3 src/node1_embedder.py
python3 src/node2_processor.py
python3 src/node3_head.py
python3 src/pii_node_server.py

# API başlat (5. terminal)
python3 src/api_secure_v2.py

# Test
./test_manual.sh
```

**Swagger UI:** https://localhost:9000/docs  
**Login:** yagmur / yagmur123

## 📡 API

```bash
# Login
curl -sk -X POST https://localhost:9000/login \
  -d '{"username":"yagmur","password":"yagmur123"}'

# Generate
curl -sk -X POST https://localhost:9000/generate \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"prompt":"Merhaba","max_tokens":50}'
```

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/login` | POST | JWT token al |
| `/generate` | POST | Text generation |
| `/health` | GET | Sistem durumu |

## 📁 Yapı

```
src/
├── api_secure_v2.py           # API Server
├── node1_embedder.py          # Node 1 (Layer 0-10)
├── node2_processor.py         # Node 2 (Layer 11-21)
├── node3_head.py              # Node 3 (Layer 22-31)
├── pii_node_server.py         # PII Detection
└── security/                  # Güvenlik modülleri
```

## 📚 Dokümantasyon

- [D-TEK Pipeline](D-TEK_PIPELINE.md) - Detaylı sistem pipeline'ı
- [Güvenlik Raporu](GUVENLIK_RAPORU.md) - Kapsamlı güvenlik analizi

## 👤 Yazar

**Nur Yağmur Tuncer**

## 📄 Lisans

MIT License
