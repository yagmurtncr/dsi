# 🔐 D-TEK Güvenlik Raporu

**Versiyon:** 3.0 | **Tarih:** Aralık 2025

---

## 📋 Özet

D-TEK, 3 node'a dağıtılmış güvenli LLM inference sistemidir.

| Özellik | Değer |
|---------|-------|
| Model | Llama-3.1-8B-Instruct |
| Dağılım | 3 Node |
| Şifreleme | RSA-2048 + AES-256-GCM |

---

## 🔐 Şifreleme Katmanları

```
┌─────────────────────────────────────────────────────────────────┐
│  KATMAN                    DURUM         ALGORİTMA              │
├─────────────────────────────────────────────────────────────────┤
│  Transport (HTTPS)         ✅ AKTİF      TLS 1.3               │
│  API Response              ✅ AKTİF      AES-256-GCM           │
│  Node↔Node                 ✅ AKTİF      RSA-2048 + AES-256    │
│  PII Masking               ✅ AKTİF      Turkish NER + Regex   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Mimari

```
┌──────────────────────────────────────────────────────────────┐
│                     CLIENT                                   │
│                        │                                     │
│                        │ HTTPS + JWT                         │
│                        ▼                                     │
│              ┌─────────────────┐                            │
│              │   API (9000)    │                            │
│              │  • JWT Auth     │                            │
│              │  • Rate Limit   │                            │
│              │  • Encryption   │                            │
│              └────────┬────────┘                            │
│                       │                                      │
│         ┌─────────────┼─────────────┐                       │
│         ▼             ▼             ▼                        │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│   │ Node 1   │  │ Node 2   │  │ Node 3   │                  │
│   │ 8001     │→→│ 8002     │→→│ 8003     │                  │
│   │ Layer0-10│  │ Layer11-21│  │ Layer22-31│                 │
│   └──────────┘  └──────────┘  └──────────┘                  │
│         │             │             │                        │
│         └─────────────┴─────────────┘                       │
│              RSA+AES Encrypted                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 🛡️ Güvenlik Özellikleri

### 1. Authentication
- JWT (HS256, 60 dk expiry)
- Brute force protection
- Rate limiting (20 req/dk)

### 2. Encryption
- **Transport:** TLS 1.3
- **Response:** AES-256-GCM (password-derived)
- **Node↔Node:** RSA-2048 + AES-256-GCM

### 3. PII Protection
- Turkish NER model
- Regex (TC, Tel, Email, IBAN)
- Maskeleme + Unmask

### 4. Access Control
- RBAC (admin, user, pilot, readonly)
- Permission-based endpoints
- Session management

---

## 📊 Güvenlik Skoru

| Katman | Skor |
|--------|------|
| Transport | 10/10 |
| Authentication | 9/10 |
| Encryption | 9/10 |
| Node Isolation | 10/10 |
| PII Protection | 9/10 |
| **GENEL** | **9.4/10** |

---

## 🔒 Tehdit Modeli

| Tehdit | Durum | Çözüm |
|--------|-------|-------|
| Network Sniffing | ✅ | HTTPS + RSA+AES |
| MITM | ✅ | TLS + Key exchange |
| Node Compromise | ✅ | Layer split (1/3 model) |
| Response Leak | ✅ | AES-256-GCM |
| PII Exposure | ✅ | NER + Regex masking |
| Brute Force | ✅ | Rate limit + lockout |

---

## 📁 Güvenlik Dosyaları

```
src/security/
├── node_crypto.py      # Node↔Node RSA+AES
├── user_encryption.py  # Password-derived AES
├── e2e_encryption.py   # Session + Rate limit + Monitor
├── rbac.py             # Role-Based Access Control
├── validators.py       # Input validation (XSS, SQLi)
├── audit_logger.py     # KVKK/GDPR audit log
├── secure_memory.py    # Memory cleanup
└── secure_gpu_memory.py # GPU memory cleanup
```

---

**Son Güncelleme:** Aralık 2025
