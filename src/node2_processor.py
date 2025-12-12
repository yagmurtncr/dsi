#!/usr/bin/env python3
"""
🔐 NODE 2: İŞLEMCİ KATMANI (Katman 11-21)

GÜVENLİK:
- Sadece orta transformer katmanları (11-21)
- Embedding kodu YOK (Node 1'e özel)
- LM head kodu YOK (Node 3'e özel)
- Node 1'den şifreli hidden state'ler alır
- Node 3'e şifreli hidden state'ler iletir
"""

import os
import json
import socket
import secrets
import hashlib
import threading
import torch
from transformers import AutoConfig, AutoModelForCausalLM
from dataclasses import dataclass
from typing import Optional

# Kriptografi modülleri
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend

# Güvenli bellek yönetimi ve şifreleme
from security import SecureMemoryManager, SecureGPUMemory, NodeCrypto

# 🚀 Hızlı Binary Serialization
try:
    from security import prepare_for_json, restore_from_json
    USE_TENSOR_JSON = True
except ImportError:
    USE_TENSOR_JSON = False

# 🆕 GPU Memory Secure Cleanup
import gc

# Performance optimization
try:
    from performance_config import apply_performance_optimizations
    apply_performance_optimizations()
except ImportError:
    pass


@dataclass
class Node2Config:
    """Node 2 yapılandırması - Port, device, katman aralığı ve IP beyaz listesi"""
    node_id: int = 2
    layer_start: int = 11
    layer_end: int = 21
    port: int = 9081
    device: str = "cpu"
    model_path: str = ""  # Model yolu
    next_node_host: str = "127.0.0.1"
    next_node_port: int = 9082
    allowed_ips: list = None  # IP beyaz listesi


class EncryptionManager:
    """Node 2 şifreleme yöneticisi - RSA-2048 + AES-256 hibrit şifreleme"""
    
    #49 - Node 2 Encryption Manager Başlatma
    def __init__(self):
        print("🔐 Node 2 Encryption Manager...")
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()
        self.session_key = secrets.token_bytes(32)  # AES-256 oturum anahtarı
        print("   ✅ RSA-2048 + AES-256 initialized")


class Node2Processor:
    """
    Node 2: Orta Katmanlar (11-21)
    
    YAPILANLAR:
    - Node 1'den hidden state'ler al
    - Katman 11-21'den geçir
    - Şifrele ve Node 3'e gönder
    
    YAPILMAYANLAR:
    - Embedding kodu yok
    - LM head yok
    - Girdi prompt'larını görmez (sadece hidden state'ler)
    - Çıktı token'ları üretmez
    """
    
    #41 - Node 2 Processor Başlatma
    def __init__(self, config: Node2Config, model_path: str):
        self.config = config
        self.model_path = model_path
        self.encryption = EncryptionManager()
        self.secure_mem = SecureMemoryManager(node_id=2)
        self.node_crypto = NodeCrypto(node_id=2)  # 🆕 Inter-node encryption
        if config.device.startswith("cuda"):
            self.secure_gpu = SecureGPUMemory(node_id=2, device=config.device)
        else:
            self.secure_gpu = None
        self.model_loaded = False
        self.server_socket = None
        self.running = False
        
        # 🚀 BAĞLANTI HAVUZU: Node 3'e kalıcı socket bağlantısı
        self._node3_socket = None
        self._node3_socket_lock = threading.Lock()
        
        # Güvenlik: IP beyaz listesi
        self.allowed_ips = config.allowed_ips or ["127.0.0.1", "::1"]
        
        print(f"🚀 Node 2 Processor initialized")
        print(f"   Layers: {config.layer_start}-{config.layer_end}")
        print(f"   Port: {config.port}")
        print(f"   Device: {config.device}")
        print(f"   Allowed IPs: {self.allowed_ips}")
        print(f"   Memory: Secure cleanup enabled")
        print(f"   ⚠️  EMBEDDING ve LM HEAD erişimi YOK!")
    
    #42 - Model Yükleme (Layer 11-21)
    def load_model(self):
        """
        ⚡ EFFICIENT Model yükleme - Sadece layers 11-21!
        """
        if self.model_loaded:
            return
        
        print(f"📥 Loading Node 2 model (layers 11-21 ONLY)...")
        print(f"   ⚡ EFFICIENT MODE: Only loading required layers!")
        
        try:
            # ⚡ EFFICIENT: Sadece gerekli layer'ları yükle
            from efficient_model_loader import EfficientLayerLoader
            
            dtype = torch.float32 if self.config.device == "cpu" else torch.float16
            loader = EfficientLayerLoader(self.model_path, self.config.device)
            
            # Config'i sakla (forward için gerekli)
            self.config_model = loader.config
            
            # Memory tahmini
            estimated_mem = loader.estimate_memory(
                self.config.layer_start, 
                self.config.layer_end
            )
            print(f"   📊 Estimated memory: {estimated_mem:.2f} GB")
            
            # Sadece layer 11-21 yükle
            self.layers, _, _, _ = loader.create_partial_model(
                layer_start=self.config.layer_start,
                layer_end=self.config.layer_end,
                include_embed=False,
                include_lm_head=False,
                dtype=dtype
            )
            
            # Rotary embedding oluştur
            from transformers.models.llama.modeling_llama import LlamaRotaryEmbedding
            self.rotary_emb = LlamaRotaryEmbedding(config=loader.config)
            
            # Cihaza taşı
            print(f"   🔄 Moving to {self.config.device}...")
            self.rotary_emb = self.rotary_emb.to(self.config.device)
            for layer in self.layers:
                layer.to(self.config.device)
            print(f"   ✅ All layers on {self.config.device}")
            
            self.model_checksum = "EFFICIENT_LOAD_MODE"
            self.model_loaded = True
            
            print(f"✅ Node 2 model ready!")
            print(f"   ⚡ Memory efficient: ~{estimated_mem:.1f}GB (vs 16GB full model)")
            print(f"   ⚠️  Embedding yüklenmedi (Node 1'e özel)")
            print(f"   ⚠️  LM head yüklenmedi (Node 3'e özel)")
            
        except Exception as e:
            print(f"❌ FATAL ERROR in load_model(): {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _compute_model_checksum(self) -> str:
        """
        Model checksum hesapla (SHA-256) - Model bütünlük kontrolü
        
        Not: Sadece config.json ve model.safetensors.index.json hash'lenir (hız için)
        """
        import hashlib
        from pathlib import Path
        
        hasher = hashlib.sha256()
        model_dir = Path(self.config.model_path)
        
        # Kritik dosyaları hash'le
        critical_files = ['config.json', 'model.safetensors.index.json', 'tokenizer_config.json']
        
        for filename in critical_files:
            file_path = model_dir / filename
            if file_path.exists():
                with open(file_path, 'rb') as f:
                    while chunk := f.read(8192):
                        hasher.update(chunk)
        
        # Layer range'i de dahil et (her node farklı layer'lar kullanıyor)
        hasher.update(f"node2_layers{self.config.layer_start}-{self.config.layer_end}".encode())
        
        return hasher.hexdigest()
    
    #43 - Forward Pass (Layer 11-21)
    def forward_layers(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """
        İleri geçiş - Katman 11-21'den geçirir
        
        Parametreler:
            hidden_states: Node 1'den gelen [batch, seq_len, hidden_size]
            
        Döndürür:
            hidden_states: Node 3'e gönderilecek [batch, seq_len, hidden_size]
        """
        with torch.no_grad():
            # ⚠️ Dtype conversion: Node 1 CPU'da float32 gönderebilir
            target_dtype = torch.float16 if self.config.device != "cpu" else torch.float32
            hidden_states = hidden_states.to(dtype=target_dtype)
            
            batch_size, seq_length, _ = hidden_states.shape
            
            # Pozisyon embedding'leri
            position_ids = torch.arange(0, seq_length, dtype=torch.long, device=self.config.device)
            position_ids = position_ids.unsqueeze(0).expand(batch_size, -1)
            
            cache_position = torch.arange(0, seq_length, dtype=torch.long, device=self.config.device)
            
            # RoPE (cos, sin) hesapla - transformers 4.42+ için gerekli
            position_embeddings = self.rotary_emb(hidden_states, position_ids)
            
            # Katman 11-21'den geçir
            for layer in self.layers:
                layer_output = layer(
                    hidden_states,
                    position_ids=position_ids,
                    position_embeddings=position_embeddings,
                    use_cache=False
                )
                # Layer çıktısı direkt tensor (tuple DEĞİL!)
                hidden_states = layer_output if isinstance(layer_output, torch.Tensor) else layer_output[0]
            
            return hidden_states
    
    #44 - Node 3 ile Key Exchange
    def exchange_keys_with_node3(self):
        """
        🆕 Node 3 ile public key alışverişi yap (startup'ta bir kez)
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.config.next_node_host, self.config.next_node_port))
            
            # Public key gönder
            my_public_key = self.node_crypto.get_public_key_bytes()
            key_exchange = {
                'type': 'key_exchange',
                'node_id': 2,
                'public_key': my_public_key.decode('utf-8')
            }
            
            request_bytes = json.dumps(key_exchange).encode('utf-8')
            sock.sendall(len(request_bytes).to_bytes(4, 'big'))
            sock.sendall(request_bytes)
            
            # Node 3'ün public key'ini al
            response_length_bytes = sock.recv(4)
            response_length = int.from_bytes(response_length_bytes, 'big')
            
            response_data = b''
            while len(response_data) < response_length:
                chunk = sock.recv(min(response_length - len(response_data), 4096))
                if not chunk:
                    break
                response_data += chunk
            
            sock.close()
            
            response = json.loads(response_data.decode('utf-8'))
            if response.get('status') == 'success':
                node3_public_key = response['public_key'].encode('utf-8')
                self.node_crypto.add_peer_public_key(3, node3_public_key)
                print(f"   ✅ Node 3 public key alındı")
            
        except Exception as e:
            print(f"   ⚠️ Key exchange failed (fallback to plaintext): {e}")
    
    #45 - Node 3'e Şifreli Hidden States Gönderme
    def send_to_node3(self, hidden_states: torch.Tensor) -> dict:
        """Hidden state'leri şifrele ve Node 3'e gönder (🚀 OPTİMİZE: oturum anahtarı önbelleği)"""
        try:
            # 🔐 LAZY KEY EXCHANGE: İlk çağrıda key exchange yap
            if 3 not in self.node_crypto.peer_public_keys:
                import sys
                print("🔑 Lazy key exchange: Node 3 key'i yok, şimdi exchange yapılıyor...", flush=True)
                sys.stdout.flush()
                try:
                    self.exchange_keys_with_node3()
                    if 3 in self.node_crypto.peer_public_keys:
                        print("   ✅ Key exchange başarılı!", flush=True)
                        sys.stdout.flush()
                    else:
                        print("   ⚠️  Key exchange başarısız, plaintext fallback", flush=True)
                        sys.stdout.flush()
                except Exception as e:
                    print(f"   ⚠️  Key exchange hatası: {e}", flush=True)
                    sys.stdout.flush()
            
            # 🚀 TENSOR JSON: Tensor'ları JSON-uyumlu formata çevir
            data = {
                'type': 'forward_head',
                'node_id': 2
            }
            
            # Tensor'ı JSON-uyumlu hale getir
            if USE_TENSOR_JSON:
                data['hidden_states'] = prepare_for_json({'t': hidden_states.cpu()})['t']
            else:
                data['hidden_states'] = hidden_states.cpu().tolist()
            
            # 🔐 Şifrele - 🚀 Oturum anahtarı ile hızlı!
            import sys
            if 3 in self.node_crypto.peer_public_keys:
                request_bytes = self.node_crypto.encrypt_for_peer(data, peer_node_id=3)
                encrypted = True
                if self.node_crypto.session_key_usage.get(3, 0) <= 1:
                    print("🔐 Oturum anahtarı oluşturuldu (RSA+AES)", flush=True)
            else:
                request_bytes = json.dumps(data).encode('utf-8')
                encrypted = False
                print("⚠️  Data sent as PLAINTEXT (no peer key)", flush=True)
                sys.stdout.flush()
            
            # Node 3'e gönder (her seferinde yeni socket)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(600)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # Nagle kapalı (hız için)
            sock.connect((self.config.next_node_host, self.config.next_node_port))
            
            sock.sendall(len(request_bytes).to_bytes(4, 'big'))
            sock.sendall(request_bytes)
            
            response_length_bytes = sock.recv(4)
            response_length = int.from_bytes(response_length_bytes, 'big')
            
            response_data = b''
            while len(response_data) < response_length:
                chunk = sock.recv(min(response_length - len(response_data), 65536))
                if not chunk:
                    break
                response_data += chunk
            
            sock.close()
            
            # 🚀 Şifreli yanıtı çöz
            if encrypted and 3 in self.node_crypto.peer_public_keys:
                response = self.node_crypto.decrypt_from_peer(response_data)
            else:
                response = json.loads(response_data.decode('utf-8'))
            
            return response
            
        except Exception as e:
            print(f"❌ Node 3 communication failed: {e}")
            return {'status': 'error', 'error': str(e)}
    
    #46 - Client Request Handler (Node 1'den)
    def handle_client(self, client_socket: socket.socket, client_addr):
        """Node 1'den gelen isteği işle"""
        try:
            # Güvenlik: IP beyaz liste kontrolü
            client_ip = client_addr[0]
            if client_ip not in self.allowed_ips:
                print(f"🚫 Unauthorized IP: {client_ip}")
                client_socket.close()
                return
            
            print(f"✅ Authorized connection from {client_ip}")
            
            # İstek al
            length_bytes = client_socket.recv(4)
            if not length_bytes:
                return
            
            data_length = int.from_bytes(length_bytes, 'big')
            data = b''
            while len(data) < data_length:
                chunk = client_socket.recv(min(data_length - len(data), 4096))
                if not chunk:
                    break
                data += chunk
            
            # 🆕 Şifreli veriyi çöz (eğer şifreliyse)
            try:
                request = self.node_crypto.decrypt_from_peer(data)
                encrypted_request = True
                print("🔓 Data decrypted successfully")
            except Exception as decrypt_err:
                # Fallback: Plaintext
                print(f"⚠️ Decrypt failed: {decrypt_err}, trying plaintext...")
                try:
                    request = json.loads(data.decode('utf-8'))
                    print("📝 Plaintext parse OK")
                    encrypted_request = False
                except Exception as json_err:
                    print(f"❌ Parse failed: {json_err}")
                    print(f"   Data preview: {data[:100]}...")
                    raise
            
            # Key exchange isteği mi?
            if request.get('type') == 'key_exchange':
                print(f"🔑 Key exchange request from Node {request.get('node_id')}")
                
                # Peer'in public key'ini kaydet
                peer_id = request.get('node_id')
                peer_public_key = request.get('public_key').encode('utf-8')
                self.node_crypto.add_peer_public_key(peer_id, peer_public_key)
                
                # Kendi public key'imizi döndür
                response = {
                    'status': 'success',
                    'public_key': self.node_crypto.get_public_key_bytes().decode('utf-8')
                }
                response_bytes = json.dumps(response).encode('utf-8')
                client_socket.sendall(len(response_bytes).to_bytes(4, 'big'))
                client_socket.sendall(response_bytes)
                return
            
            # Gerekirse modeli yükle
            if not self.model_loaded:
                self.load_model()
            
            # 🔒 Güvenlik: Key exchange yapılmadan forward request kabul etme
            if 1 not in self.node_crypto.peer_public_keys:
                print(f"⚠️ Node 1 key'i henüz yok, forward request reddediliyor...")
                error_response = {'status': 'error', 'error': 'Key exchange not completed'}
                error_bytes = json.dumps(error_response).encode('utf-8')
                client_socket.sendall(len(error_bytes).to_bytes(4, 'big'))
                client_socket.sendall(error_bytes)
                return
            
            # Node 1'den hidden state'leri al
            # 🚀 Tensor JSON format: dict ise restore et
            if 'hidden_states' not in request:
                print(f"❌ 'hidden_states' key bulunamadı! Request type: {request.get('type', 'N/A')}")
                print(f"   Request keys: {list(request.keys())}")
                raise KeyError('hidden_states')
            
            hs = request['hidden_states']
            if isinstance(hs, torch.Tensor):
                hidden_states = hs
            elif isinstance(hs, dict) and hs.get('_tensor'):
                # JSON-encoded tensor
                from security import json_to_tensor
                hidden_states = json_to_tensor(hs)
            else:
                hidden_states = torch.tensor(hs)
            
            # Model'in dtype'ına çevir (GPU'da float16)
            if self.config.device.startswith('cuda'):
                hidden_states = hidden_states.to(dtype=torch.float16)
            
            hidden_states = hidden_states.to(self.config.device)
            
            # Node 2'den geçir
            hidden_states = self.forward_layers(hidden_states)
            
            # Node 3'e gönder
            response = self.send_to_node3(hidden_states)
            
            # 🆕 Yanıtı şifrele (eğer peer key varsa)
            if encrypted_request and 1 in self.node_crypto.peer_public_keys:
                response_bytes = self.node_crypto.encrypt_for_peer(response, peer_node_id=1)
            else:
                response_bytes = json.dumps(response).encode('utf-8')
            
            client_socket.sendall(len(response_bytes).to_bytes(4, 'big'))
            client_socket.sendall(response_bytes)
            
        except Exception as e:
            print(f"❌ Request handling failed: {e}")
        finally:
            # 🔐 SECURE MEMORY CLEANUP - Her request sonrası
            try:
                # Hidden states referansını temizle
                if 'hidden_states' in locals() and hidden_states is not None:
                    if hasattr(self, 'secure_mem'):
                        self.secure_mem.secure_delete(hidden_states, verbose=False)
                    del hidden_states
                
                # GPU cache temizle
                if torch.cuda.is_available() and 'cuda' in self.config.device:
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
                
                # Garbage collection
                gc.collect()
                
            except Exception as cleanup_error:
                pass  # Cleanup hatasını sessizce geç
            
            client_socket.close()
    
    #47 - Server Başlatma (Socket Listen)
    def start_server(self):
        """Node 2 sunucusunu başlat"""
        print(f"🌐 Node 2 server starting (Port {self.config.port})...")
        
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('0.0.0.0', self.config.port))
        self.server_socket.listen(5)
        self.running = True
        
        print(f"✅ Node 2 listening on 0.0.0.0:{self.config.port}")
        
        # 🆕 CRITICAL: Key exchange with Node 3 (async, with retry)
        import time
        def attempt_key_exchange():
            for attempt in range(3):
                time.sleep(3)  # Node 3 başlamasını bekle
                try:
                    self.exchange_keys_with_node3()
                    print(f"🔐 ✅ Key exchange with Node 3 successful!")
                    return
                except Exception as e:
                    print(f"   ⚠️  Key exchange attempt {attempt+1}/3 failed: {e}")
            print(f"   ⚠️  Key exchange failed, falling back to plaintext")
        
        # Background thread'de key exchange yap
        threading.Thread(target=attempt_key_exchange, daemon=True).start()
        
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, addr)
                )
                thread.daemon = True
                thread.start()
            except Exception as e:
                if self.running:
                    print(f"❌ Accept error: {e}")
    
    #48 - Server Durdurma
    def stop(self):
        """Node 2 sunucusunu durdur"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Node 2: Processor (Layers 11-21)')
    parser.add_argument('--port', type=int, default=9081)
    parser.add_argument('--device', type=str, default='cpu')
    parser.add_argument('--model-path', type=str, required=True)
    parser.add_argument('--next-port', type=int, default=9082)
    
    args = parser.parse_args()
    
    config = Node2Config(
        port=args.port,
        device=args.device,
        model_path=args.model_path,
        next_node_port=args.next_port
    )
    
    node = Node2Processor(config, args.model_path)
    
    try:
        node.load_model()
        node.start_server()
    except KeyboardInterrupt:
        print("\n⚠️ Stopping Node 2...")
        node.stop()

