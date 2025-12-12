# 🔐 D-TEK Pipeline

## 📊 Sistem Mimarisi

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ADIM 1: CLIENT → API                                                       │
│  ─────────────────────                                                      │
│  • HTTPS/TLS 1.3 ile şifreli bağlantı                                       │
│  • JWT token doğrulama (Authorization: Bearer ...)                          │
│  • Request API'ye ulaştı                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ADIM 2: GÜVENLİK KONTROLLER (API)                                          │
│  ─────────────────────────────────                                          │
│  ✅ JWT Token geçerli mi? → Evet                                            │
│  ✅ Session aktif mi? → Evet (60 dk timeout)                                │
│  ✅ Rate limit aşıldı mı? → Hayır (20 req/dk)                               │ 
│  ✅ RBAC: /generate yetkisi var mı? → Evet (user rolü)                      │
│  ✅ Input validation: XSS/SQLi temizleme                                    │ 
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ADIM 3: PII MASKELEME (Port 7000)                                          │
│  ─────────────────────────────────                                          │
│                                                                             │
│  INPUT:                                                                     │
│  "Ayşe Şahin, 35 yaş, Tel: 05331234567. Tiroid..."                          │
│                                                                             │
│  TESPİT:                                                                    │
│  ┌─────────────────────────────────────────────────────┐                    │
│  │  Turkish NER Model:                                 │                    │
│  │    • "Ayşe Şahin" → PERSON                          │                    │
│  │                                                     │                    │
│  │  Regex Patterns:                                    │                    │
│  │    • "05331234567" → PHONE (05XX pattern)           │                    │
│  └─────────────────────────────────────────────────────┘                    │
│                                                                             │
│  OUTPUT (Maskelenmiş):                                                      │
│  "<|PERSON_14|>, 35 yaş, Tel: <|PHONE_4|>. Tiroid..."                       │
│                                                                             │
│  PII MAPPING (Hafızada sakla):                                              │
│  {                                                                          │
│    "<|PERSON_14|>": "Ayşe Şahin",                                           │
│    "<|PHONE_4|>": "05331234567"                                             │
│  }                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ADIM 4: NODE 1 - EMBEDDER (Port 8001, GPU 0)                               │
│  ────────────────────────────────────────────                               │
│                                                                             │
│  INPUT: Maskelenmiş prompt                                                  │
│                                                                             │
│  İŞLEMLER:                                                                  │
│  ┌─────────────────────────────────────────────────────┐                    │
│  │  1. Tokenization (128K vocab)                       │                    │
│  │     "<|PERSON_14|>, 35 yaş..." → [128, 456, 789...] │                    │
│  │                                                     │                    │
│  │  2. Embedding Layer                                 │                    │
│  │     [token_ids] → [1, seq_len, 4096]                │                    │
│  │                                                     │                    │
│  │  3. Transformer Layers 0-10                         │                    │
│  │     Self-attention + FFN                            │                    │
│  │     RoPE position encoding                          │                    │
│  └─────────────────────────────────────────────────────┘                    │
│                                                                             │
│  OUTPUT: hidden_states [1, seq_len, 4096]                                   │
│                                                                             │
│  🔐 RSA-2048 + AES-256-GCM ile şifrele → Node 2'ye gönder                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Encrypted tensor transfer
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ADIM 5: NODE 2 - PROCESSOR (Port 8002, GPU 0)                              │
│  ─────────────────────────────────────────────                              │
│                                                                             │
│  INPUT: Şifreli hidden_states (Node 1'den)                                  │
│                                                                             │
│  İŞLEMLER:                                                                  │
│  ┌─────────────────────────────────────────────────────┐                    │
│  │  1. Decrypt (RSA+AES)                               │                    │
│  │     Şifreli → hidden_states [1, seq_len, 4096]      │                    │
│  │                                                     │                    │
│  │  2. Transformer Layers 11-21                        │                    │
│  │     Self-attention + FFN                            │                    │
│  │     11 layer işleme                                 │                    │
│  │                                                     │                    │
│  │  3. Encrypt (RSA+AES)                               │                    │
│  │     hidden_states → Şifreli                         │                    │
│  └─────────────────────────────────────────────────────┘                    │
│                                                                             │
│  OUTPUT: Şifreli hidden_states → Node 3'e gönder                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Encrypted tensor transfer
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ADIM 6: NODE 3 - HEAD (Port 8003, GPU 1)                                   │
│  ────────────────────────────────────────                                   │
│                                                                             │
│  INPUT: Şifreli hidden_states (Node 2'den)                                  │
│                                                                             │
│  İŞLEMLER:                                                                  │
│  ┌─────────────────────────────────────────────────────┐                    │
│  │  1. Decrypt (RSA+AES)                               │                    │
│  │     Şifreli → hidden_states [1, seq_len, 4096]      │                    │
│  │                                                     │                    │
│  │  2. Transformer Layers 22-31                        │                    │
│  │     Self-attention + FFN                            │                    │
│  │     10 layer işleme                                 │                    │
│  │                                                     │                    │
│  │  3. RMSNorm (Final normalization)                   │                    │
│  │                                                     │                    │
│  │  4. LM Head                                         │                    │
│  │     hidden_states [4096] → logits [128256]          │                    │
│  │     (Vocabulary boyutunda olasılıklar)              │                    │
│  └─────────────────────────────────────────────────────┘                    │
│                                                                             │
│  OUTPUT: logits [1, 1, 128256] → API'ye gönder                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ADIM 7: TOKEN SAMPLING (API)                                               │
│  ────────────────────────────                                               │
│                                                                             │
│  INPUT: logits [128256]                                                     │
│                                                                             │
│  İŞLEM:                                                                     │
│  ┌─────────────────────────────────────────────────────┐                    │
│  │  1. Temperature scaling (0.2)                       │                    │
│  │     logits / 0.2 → scaled_logits                    │                    │
│  │                                                     │                    │
│  │  2. Softmax                                         │                    │
│  │     scaled_logits → probabilities                   │                    │
│  │                                                     │                    │
│  │  3. Sample                                          │                    │
│  │     probabilities → next_token_id                   │                    │
│  └─────────────────────────────────────────────────────┘                    │
│                                                                             │
│  OUTPUT: next_token_id (örn: 15234)                                         │
│                                                                             │
│  🔄 LOOP: Bu işlem 300 kez tekrar (max_tokens)                              │
│     veya EOS token gelene kadar                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ 300 token üretildi
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ADIM 8: DECODE (API)                                                       │
│  ────────────────────                                                       │
│                                                                             │
│  INPUT: [token_ids] = [15234, 892, 1456, ...]                               │
│                                                                             │
│  İŞLEM: Tokenizer decode                                                    │
│                                                                             │
│  OUTPUT (Ham):                                                              │
│  "Sayın <|PERSON_14|>, size önerim: 1. Tiroid..."                           │
│         ↑                                                                   │
│         Tag hala var!                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ADIM 9: PII UNMASK (API)                                                   │
│  ────────────────────────                                                   │
│                                                                             │
│  INPUT:                                                                     │
│  "Sayın <|PERSON_14|>, size önerim..."                                      │
│                                                                             │
│  PII MAPPING (Adım 3'ten):                                                  │
│  {                                                                          │
│    "<|PERSON_14|>": "Ayşe Şahin",                                           │
│    "<|PHONE_4|>": "05331234567"                                             │
│  }                                                                          │
│                                                                             │
│  İŞLEM: Tag → Orijinal değer                                                │
│  "<|PERSON_14|>" → "Ayşe Şahin"                                             │
│                                                                             │
│  OUTPUT (Final):                                                            │
│  "Sayın Şahin, size önerim: 1. Tiroid..."                                   │
│         ↑                                                                   │
│         Gerçek isim!                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ADIM 10: RESPONSE (API → Client)                                           │
│  ────────────────────────────────                                           │
│                                                                             │
│  JSON Response:                                                             │
│  {                                                                          │
│    "generated_text": "Sayın Şahin, size önerim...",                         │
│    "pii_detected": 2,                                                       │
│    "timing_seconds": {                                                      │
│      "total": 428.66,                                                       │
│      "node1_embed": 64.3,                                                   │
│      "node2_process": 150.03,                                               │
│      "node3_head": 192.9                                                    │
│    },                                                                       │
│    "pii_details": {                                                         │
│      "detected_items": {                                                    │
│        "<|PERSON_14|>": "Ayşe Şahin",                                       │
│        "<|PHONE_4|>": "05331234567"                                         │
│      },                                                                     │
│      "masked_prompt": "<|PERSON_14|>, 35 yaş, Tel: <|PHONE_4|>..."          │
│    }                                                                        │
│  }                                                                          │
│                                                                             │
│  🔐 HTTPS ile şifreli gönderim                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Veri Akışı

| # | Adım | İşlem | Detay |
|---|------|-------|-------|
| 1 | **Request** | Client → API | `POST /generate` + JWT Token |
| 2 | **Auth** | JWT Verify | Token geçerli mi? (60 dk) |
| 3 | **Security** | Checks | Rate limit, Input validation, RBAC |
| 4 | **PII Mask** | API → PII Node | `"Ahmet, TC:123"` → `"<PERSON_1>, <TC_1>"` |
| 5 | **Node 1** | Tokenize + Embed | text → tokens → hidden_states [1,seq,4096] |
| 6 | **Transfer** | Node 1 → 2 | 🔐 RSA+AES encrypted tensor |
| 7 | **Node 2** | Layers 11-21 | Transformer processing |
| 8 | **Transfer** | Node 2 → 3 | 🔐 RSA+AES encrypted tensor |
| 9 | **Node 3** | Layers 22-31 | → LM Head → logits |
| 10 | **Sample** | Temperature | logits → next token |
| 11 | **Unmask** | PII Node | `"<PERSON_1>"` → `"Ahmet"` |
| 12 | **Encrypt** | Response | AES-256-GCM (password key) |
| 13 | **Return** | API → Client | Encrypted JSON response |

---

## 🔐 Şifreleme Katmanları

| Katman | Algoritma | Anahtar | Kullanım |
|--------|-----------|---------|----------|
| Transport | TLS 1.3 | Certificate | Client ↔ API |
| Response | AES-256-GCM | PBKDF2(password) | API → Client |
| Node↔Node | RSA-2048 + AES-256 | Session key | Node 1↔2↔3 |
| PII | NER + Regex | - | Maskeleme |

---

## 🛡️ Node İzolasyonu

| Node | Erişimi Var | Erişimi YOK | Risk |
|------|-------------|-------------|------|
| Node 1 | Tokenizer, Embedding, Layer 0-10 | LM Head, Final text | %33 model |
| Node 2 | Layer 11-21 (hidden states) | Tokenizer, LM Head | %33 model |
| Node 3 | Layer 22-31, LM Head | Tokenizer, Embedding | %33 model |

**Güvenlik:**
- ❌ Tek node ele geçirildi → Model parçası, çalışmaz
- ❌ Hepsi ele geçirildi → RSA key'ler olmadan bağlanamaz
- ✅ Tam güvenlik: 3 node + 3 ayrı key pair

---

## 📊 Performans

| Metrik | Değer |
|--------|-------|
| Token Latency | ~2-3 saniye |
| Total GPU Memory | ~30 GB (3 node) |
| Encryption Overhead | <1% |
| PII Detection | ~50ms |
| Key Exchange | ~10ms (startup) |

---

## ✅ Güvenlik Skoru: 9/10

| Katman | Skor | Açıklama |
|--------|------|----------|
| Transport | 10/10 | TLS 1.3 |
| Authentication | 9/10 | JWT + Session |
| Response Encryption | 9/10 | AES-256-GCM |
| Node↔Node | 10/10 | RSA+AES |
| PII Protection | 9/10 | NER + Regex |
| Node Isolation | 10/10 | 3-way split |

---

┌─────────────────────────────────────────────────────────────────────────────┐
│                         FUNCTION SYSTEM                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  API LAYER (1-10)                                                           │
│  ├─ #1   api_secure_v2.startup()                                            │
│  ├─ #2   api_secure_v2.login()                                              │
│  ├─ #3   api_secure_v2.generate()                                           │
│  ├─ #4   api_secure_v2.health()                                             │
│  ├─ #5   api_secure_v2.admin_action()                                       │
│  ├─ #6   api_secure_v2.create_access_token()                                │
│  └─ #7   api_secure_v2.verify_token()                                       │
│                                                                             │
│  PII LAYER (11-20)                                                          │
│  ├─ #11  pii_node_server.startup()                                          │
│  ├─ #12  pii_node_server.mask_pii()                                         │
│  ├─ #13  pii_node_server.unmask_pii()                                       │
│  ├─ #14  pii_node_server.mask_and_tokenize()                                │
│  ├─ #15  pii_node_server.health()                                           │
│  ├─ #16  pii_manager.PIIManager.__init__()                                  │
│  ├─ #17  pii_manager.PIIManager.detect_and_mask()                           │
│  ├─ #18  pii_manager.PIIManager.unmask()                                    │
│  ├─ #19  pii_manager.PIIManager.clear_cache()                               │
│  └─ #20  pii_manager.PIIManager.get_stats()                                 │
│                                                                             │
│  LLM MANAGER (21-25)                                                        │
│  ├─ #21  llm_manager_distributed.__init__()                                 │
│  ├─ #22  llm_manager_distributed._send_to_node()                            │
│  ├─ #23  llm_manager_distributed.generate()                                 │
│  └─ #24  llm_manager_distributed.cleanup()                                  │
│                                                                             │
│  NODE 1 - EMBEDDER (31-40)                                                  │
│  ├─ #31  node1_embedder.Node1Embedder.__init__()                            │
│  ├─ #32  node1_embedder.Node1Embedder.load_model()                          │
│  ├─ #33  node1_embedder.Node1Embedder.forward_layers()                      │
│  ├─ #34  node1_embedder.Node1Embedder.forward_pass_only()                   │
│  ├─ #35  node1_embedder.Node1Embedder.exchange_keys_with_node2()            │
│  ├─ #36  node1_embedder.Node1Embedder.send_to_node2()                       │
│  ├─ #37  node1_embedder.Node1Embedder.handle_client()                       │
│  ├─ #38  node1_embedder.Node1Embedder.start_server()                        │
│  ├─ #39  node1_embedder.Node1Embedder.stop()                                │
│  └─ #40  node1_embedder.EncryptionManager.__init__()                        │
│                                                                             │
│  NODE 2 - PROCESSOR (41-50)                                                 │
│  ├─ #41  node2_processor.Node2Processor.__init__()                          │
│  ├─ #42  node2_processor.Node2Processor.load_model()                        │
│  ├─ #43  node2_processor.Node2Processor.forward_layers()                    │
│  ├─ #44  node2_processor.Node2Processor.exchange_keys_with_node3()          │
│  ├─ #45  node2_processor.Node2Processor.send_to_node3()                     │
│  ├─ #46  node2_processor.Node2Processor.handle_client()                     │
│  ├─ #47  node2_processor.Node2Processor.start_server()                      │
│  ├─ #48  node2_processor.Node2Processor.stop()                              │
│  └─ #49  node2_processor.EncryptionManager.__init__()                       │
│                                                                             │
│  NODE 3 - HEAD (51-60)                                                      │
│  ├─ #51  node3_head.Node3Head.__init__()                                    │
│  ├─ #52  node3_head.Node3Head.load_model()                                  │
│  ├─ #53  node3_head.Node3Head.forward_head()                                │
│  ├─ #54  node3_head.Node3Head.handle_client()                               │
│  ├─ #55  node3_head.Node3Head.start_server()                                │
│  ├─ #56  node3_head.Node3Head.stop()                                        │
│  └─ #57  node3_head.EncryptionManager.__init__()                            │
│                                                                             │
│  EFFICIENT LOADER (61-70)                                                   │
│  ├─ #61  efficient_model_loader.EfficientLayerLoader.__init__()             │
│  ├─ #62  efficient_model_loader.EfficientLayerLoader._load_index()          │
│  ├─ #63  efficient_model_loader.EfficientLayerLoader.get_required_shards()  │
│  ├─ #64  efficient_model_loader.EfficientLayerLoader.load_state_dict_selective()│
│  ├─ #65  efficient_model_loader.EfficientLayerLoader.create_partial_model() │ 
│  └─ #66  efficient_model_loader.EfficientLayerLoader.estimate_memory()      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

---
**D-TEK v3.0** | Aralık 2025
