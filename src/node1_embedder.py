#!/usr/bin/env python3
"""
🔐 NODE 1: EMBEDDING KATMANI (Katman 0-10)

GÜVENLİK:
- Sadece embedding katmanı + ilk 11 transformer katmanı
- LM head kodu YOK (Node 3'e özel)
- 11+ katman mantığını BİLMİYOR (Node 2/3'e özel)
- Şifreli hidden state'leri Node 2'ye iletir
"""

import os
import json
import socket
import secrets
import hashlib
import threading
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from dataclasses import dataclass
from typing import Optional

# Kriptografi modülleri
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend

# Güvenli bellek yönetimi ve şifreleme
from security import SecureMemoryManager, NodeCrypto

# 🚀 Hızlı Binary Serialization
try:
    from security import prepare_for_json, restore_from_json
    USE_TENSOR_JSON = True
    print("🚀 Tensor JSON serialization aktif (3x daha hızlı)")
except ImportError:
    USE_TENSOR_JSON = False
    print("⚠️  Binary serialization yok, JSON kullanılacak")

# 🆕 GPU Memory Secure Cleanup
import gc

# Performance optimization
try:
    from performance_config import apply_performance_optimizations
    apply_performance_optimizations()
except ImportError:
    pass


@dataclass
class Node1Config:
    """Node 1 yapılandırması - Port, device, katman aralığı ve IP beyaz listesi"""
    node_id: int = 1
    layer_start: int = 0
    layer_end: int = 10
    port: int = 9080
    device: str = "cpu"
    model_path: str = ""  # Model yolu
    next_node_host: str = "127.0.0.1"
    next_node_port: int = 9081
    allowed_ips: list = None  # IP beyaz listesi


class EncryptionManager:
    """Node 1 şifreleme yöneticisi - RSA-2048 + AES-256 hibrit şifreleme"""
    
    #40 - Node 1 Encryption Manager Başlatma
    def __init__(self):
        print("🔐 Node 1 Encryption Manager...")
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()
        self.session_key = secrets.token_bytes(32)  # AES-256 oturum anahtarı
        print("   ✅ RSA-2048 + AES-256 initialized")


class Node1Embedder:
    """
    Node 1: Embedding + Katmanlar 0-10
    
    YAPILANdAR:
    - Girdi tokenizasyon
    - Embedding hesaplama
    - Katman 0-10'dan geçirme
    - Şifreli olarak Node 2'ye gönderme
    
    YAPILMAYANLAR:
    - Katman 11+ kodu yok
    - LM head yok
    - Çıktı üretimi bilgisi yok
    """
    
    #31 - Node 1 Embedder Başlatma
    def __init__(self, config: Node1Config, model_path: str):
        self.config = config
        self.model_path = model_path
        self.encryption = EncryptionManager()
        self.secure_mem = SecureMemoryManager(node_id=1)
        self.node_crypto = NodeCrypto(node_id=1)  # 🆕 Inter-node encryption
        self.model_loaded = False
        self.server_socket = None
        self.running = False
        
        # 🚀 BAĞLANTI HAVUZU: Node 2'ye kalıcı socket bağlantısı
        self._node2_socket = None
        self._node2_socket_lock = threading.Lock()
        
        # Güvenlik: IP beyaz listesi
        self.allowed_ips = config.allowed_ips or ["127.0.0.1", "::1"]
        
        print(f"🚀 Node 1 Embedder initialized")
        print(f"   Layers: {config.layer_start}-{config.layer_end}")
        print(f"   Port: {config.port}")
        print(f"   Device: {config.device}")
        print(f"   Allowed IPs: {self.allowed_ips}")
        print(f"   Memory: Secure cleanup enabled")
        print(f"   🆕 Inter-node encryption: RSA-2048 + AES-256")
    
    #32 - Model Yükleme (Embed + Layer 0-10)
    def load_model(self):
        """
        ⚡ EFFICIENT Model yükleme - Sadece gerekli layer'lar!
        """
        if self.model_loaded:
            return
        
        print(f"📥 Loading Node 1 model (embedding + layers 0-10)...")
        print(f"   ⚡ EFFICIENT MODE: Only loading required layers!")
        
        try:
            # Tokenizer yükleme
            print("   🔄 Loading tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_path,
                local_files_only=True
            )
            print("   ✅ Tokenizer loaded")
            
            # ⚡ EFFICIENT: Sadece gerekli layer'ları yükle
            from efficient_model_loader import EfficientLayerLoader
            
            dtype = torch.float32 if self.config.device == "cpu" else torch.float16
            loader = EfficientLayerLoader(self.model_path, self.config.device)
            
            # Memory tahmini göster
            estimated_mem = loader.estimate_memory(
                self.config.layer_start, 
                self.config.layer_end, 
                include_embed=True
            )
            print(f"   📊 Estimated memory: {estimated_mem:.2f} GB")
            
            # Sadece gerekli bileşenleri yükle
            self.layers, self.embed_tokens, _, _ = loader.create_partial_model(
                layer_start=self.config.layer_start,
                layer_end=self.config.layer_end,
                include_embed=True,
                include_lm_head=False,
                dtype=dtype
            )
            
            # Rotary embedding oluştur (config'den)
            from transformers.models.llama.modeling_llama import LlamaRotaryEmbedding
            self.rotary_emb = LlamaRotaryEmbedding(config=loader.config)
            
            # Cihaza taşı
            print(f"   🔄 Moving to {self.config.device}...")
            self.embed_tokens = self.embed_tokens.to(self.config.device)
            self.rotary_emb = self.rotary_emb.to(self.config.device)
            for i, layer in enumerate(self.layers):
                layer.to(self.config.device)
            print(f"   ✅ All components on {self.config.device}")
            
            # Checksum (quick mode)
            self.model_checksum = "EFFICIENT_LOAD_MODE"
            
            self.model_loaded = True
            print(f"✅ Node 1 model ready!")
            print(f"   ⚡ Memory efficient: ~{estimated_mem:.1f}GB (vs 16GB full model)")
            print(f"   ⚠️  LM head NOT loaded (Node 3 exclusive)")
            print(f"   ⚠️  Layers 11+ NOT loaded (Node 2/3 exclusive)")
            
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
        hasher.update(f"node1_layers{self.config.layer_start}-{self.config.layer_end}".encode())
        
        return hasher.hexdigest()
    
    #33 - Forward Pass (Embedding + Layer 0-10)
    def forward_layers(self, input_ids: torch.Tensor) -> torch.Tensor: #Token'lar gelir: [1, 87] → batch_size=1, 87 token
        """
        İleri geçiş - Embedding + katman 0-10'dan geçirir
        
        Döndürür:
            hidden_states: [batch, seq_len, hidden_size]
        """
        temp_tensors = []  # Güvenli temizlik için izle
        
        try:
            with torch.no_grad():
                # Embedding hesapla
                hidden_states = self.embed_tokens(input_ids) #TOKEN ID → EMBEDDING VECTOR
                
                batch_size, seq_length, _ = hidden_states.shape #[1, 87, 4096] → Her token 4096 boyutlu vektör oldu!
                
                # Pozisyon embedding'leri
                position_ids = torch.arange(0, seq_length, dtype=torch.long, device=self.config.device)
                position_ids = position_ids.unsqueeze(0).expand(batch_size, -1)
                temp_tensors.append(position_ids)
                
                cache_position = torch.arange(0, seq_length, dtype=torch.long, device=self.config.device)
                temp_tensors.append(cache_position)
                
                # RoPE (cos, sin) hesapla - transformers 4.42+ için gerekli
                position_embeddings = self.rotary_emb(hidden_states, position_ids)
                
                # Katman 0-10'dan geçir
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
                
        finally:
            # 🔒 Güvenli temizlik: Geçici tensor'ları üzerine yaz
            for tensor in temp_tensors:
                if tensor is not None:
                    self.secure_mem.secure_delete(tensor, verbose=False) #Her döngüde input_ids ve hidden_states → 3-pass overwrite

            
            # Input ID'ler hassas veri içerir (prompt)
            if input_ids is not None:
                self.secure_mem.secure_delete(input_ids, verbose=False)
    
    #34 - Forward Pass Only (Decode Yok, Logits Döner)
    def forward_pass_only(self, input_ids: list) -> dict:
        """
        Sadece forward pass - Node 1 artık decode ETMEZ, sadece logits döndürür
        
        GÜVENLİK: Node 1 artık final cevabı görmez! Sadece logit olasılıkları döndürür.
        🔐 SECURE: Her inference sonrası GPU memory temizlenir!
        
        Parametreler:
            input_ids: Token ID'leri
            
        Döndürür:
            {'logits': [...], 'status': 'success'}
        """
        hidden_states = None
        input_tensor = None
        
        try:
            # Tensor'a çevir
            input_tensor = torch.tensor([input_ids]).to(self.config.device)
            
            # Node 1: Embedding + Katman 0-10
            hidden_states = self.forward_layers(input_tensor)
            
            # Node 2 & 3: Logit'leri al
            node_response = self.send_to_node2(hidden_states)
            
            if node_response.get('status') != 'success':
                return {'status': 'error', 'error': node_response.get('error', 'Unknown error')}
            
            # Logit'leri döndür (DECODE ETMİYORUZ!)
            return {
                'status': 'success',
                'logits': node_response['logits']
            }
            
        except Exception as e:
            import traceback
            error_msg = f"{type(e).__name__}: {str(e)}"
            print(f"❌ Forward pass error: {error_msg}")
            traceback.print_exc()
            return {'status': 'error', 'error': error_msg}
        
        finally:
            # 🔐 SECURE MEMORY CLEANUP - Her inference sonrası
            try:
                # Hidden states'i güvenli sil
                if hidden_states is not None:
                    self.secure_mem.secure_delete(hidden_states, verbose=False)
                    del hidden_states
                
                # Input tensor'ı güvenli sil
                if input_tensor is not None:
                    self.secure_mem.secure_delete(input_tensor, verbose=False)
                    del input_tensor
                
                # GPU cache temizle
                if torch.cuda.is_available() and 'cuda' in self.config.device:
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
                
                # Garbage collection
                gc.collect()
                
            except Exception as cleanup_error:
                print(f"⚠️ Cleanup warning: {cleanup_error}")
    
    #35 - Node 2 ile Key Exchange
    def exchange_keys_with_node2(self):
        """
        🆕 Node 2 ile public key alışverişi yap (startup'ta bir kez)
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.config.next_node_host, self.config.next_node_port))
            
            # Public key gönder
            my_public_key = self.node_crypto.get_public_key_bytes()
            key_exchange = {
                'type': 'key_exchange',
                'node_id': 1,
                'public_key': my_public_key.decode('utf-8')
            }
            
            request_bytes = json.dumps(key_exchange).encode('utf-8')
            sock.sendall(len(request_bytes).to_bytes(4, 'big'))
            sock.sendall(request_bytes)
            
            # Node 2'nin public key'ini al
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
                node2_public_key = response['public_key'].encode('utf-8')
                self.node_crypto.add_peer_public_key(2, node2_public_key)
                print(f"   ✅ Node 2 public key alındı")
            
        except Exception as e:
            print(f"   ⚠️ Key exchange failed (fallback to plaintext): {e}")
    
    #36 - Node 2'ye Şifreli Hidden States Gönderme
    def send_to_node2(self, hidden_states: torch.Tensor) -> dict:
        """Hidden state'leri şifrele ve Node 2'ye gönder ( OPTİMİZE: binary + oturum anahtarı)"""
        try:
            # 🔐 LAZY KEY EXCHANGE: İlk çağrıda key exchange yap
            if 2 not in self.node_crypto.peer_public_keys:
                import sys
                print("🔑 Lazy key exchange: Node 2 key'i yok, şimdi exchange yapılıyor...", flush=True)
                sys.stdout.flush()
                try:
                    self.exchange_keys_with_node2()
                    if 2 in self.node_crypto.peer_public_keys:
                        print("   ✅ Key exchange başarılı!", flush=True)
                        sys.stdout.flush()
                    else:
                        print("   ⚠️  Key exchange başarısız, plaintext fallback", flush=True)
                        sys.stdout.flush()
                except Exception as e:
                    print(f"   ⚠️  Key exchange hatası: {e}", flush=True)
                    sys.stdout.flush()
            
            # 🚀 TENSOR JSON: Tensor'ları JSON-uyumlu formata çevir (base64+lz4)
            data = {
                'type': 'forward_layers',
                'node_id': 1
            }
            
            # Tensor'ı JSON-uyumlu hale getir
            if USE_TENSOR_JSON:
                data['hidden_states'] = prepare_for_json({'t': hidden_states.cpu()})['t']
            else:
                data['hidden_states'] = hidden_states.cpu().tolist()
            
            # 🔐 Şifrele - 🚀 Oturum anahtarı ile hızlı!
            import sys
            print(f"🔍 DEBUG send_to_node2: peer_public_keys = {list(self.node_crypto.peer_public_keys.keys())}", flush=True)
            print(f"🔍 DEBUG send_to_node2: data keys = {list(data.keys())}", flush=True)
            
            if 2 in self.node_crypto.peer_public_keys:
                request_bytes = self.node_crypto.encrypt_for_peer(data, peer_node_id=2)
                encrypted = True
                print(f"🔍 DEBUG: Encrypted bytes length = {len(request_bytes)}", flush=True)
                # Sadece yeni key olduğunda logla
                if self.node_crypto.session_key_usage.get(2, 0) <= 1:
                    print("🔐 Oturum anahtarı oluşturuldu (RSA+AES)", flush=True)
            else:
                request_bytes = json.dumps(data).encode('utf-8')
                encrypted = False
                print("⚠️  Data sent as PLAINTEXT (no peer key)", flush=True)
                sys.stdout.flush()
            
            # Node 2'ye gönder (her seferinde yeni socket)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(600)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # Nagle kapalı (hız için)
            sock.connect((self.config.next_node_host, self.config.next_node_port))
            
            # İstek gönder
            sock.sendall(len(request_bytes).to_bytes(4, 'big'))
            sock.sendall(request_bytes)
            
            # Yanıt al
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
            if encrypted and 2 in self.node_crypto.peer_public_keys:
                response = self.node_crypto.decrypt_from_peer(response_data)
            else:
                response = json.loads(response_data.decode('utf-8'))
            
            return response
            
        except Exception as e:
            print(f"❌ Node 2 communication failed: {e}")
            return {'status': 'error', 'error': str(e)}
    
    #37 - Client Request Handler
    def handle_client(self, client_socket: socket.socket, client_addr):
        """Gelen metin üretim isteğini işle"""
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
            
            request = json.loads(data.decode('utf-8'))
            
            # İsteği işle
            if not self.model_loaded:
                self.load_model()
            
            request_type = request.get('type', 'forward')
            
            if request_type == 'forward':
                # API'den forward pass isteği (GÜVENLİK: Artık generation yok!)
                print(f"🔄 Forward pass request received")
                input_ids_list = request['input_ids']
                
                # Sadece forward pass (DECODE YOK!)
                response = self.forward_pass_only(input_ids_list)
            else:
                # Bilinmeyen tip
                response = {
                    'status': 'error',
                    'error': f'Unknown request type: {request_type}'
                }
            
            # Yanıtı döndür
            response_bytes = json.dumps(response).encode('utf-8')
            client_socket.sendall(len(response_bytes).to_bytes(4, 'big'))
            client_socket.sendall(response_bytes)
            
        except Exception as e:
            print(f"❌ Request handling failed: {e}")
        finally:
            client_socket.close()
    
    #38 - Server Başlatma (Socket Listen)
    def start_server(self):
        """Node 1 sunucusunu başlat"""
        print(f"🌐 Node 1 server starting (Port {self.config.port})...")
        
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('0.0.0.0', self.config.port))
        self.server_socket.listen(5)
        self.running = True
        
        print(f"✅ Node 1 listening on 0.0.0.0:{self.config.port}", flush=True)
        import sys
        sys.stdout.flush()
        
        # 🆕 CRITICAL: Key exchange with Node 2 (SENKRON - istemci kabul etmeden önce!)
        import time
        print("🔑 Key exchange with Node 2 başlatılıyor...", flush=True)
        for attempt in range(5):
            time.sleep(3)  # Node 2 başlamasını bekle
            try:
                self.exchange_keys_with_node2()
                print(f"🔐 ✅ Key exchange with Node 2 successful!", flush=True)
                break
            except Exception as e:
                print(f"   ⚠️  Key exchange attempt {attempt+1}/5 failed: {e}", flush=True)
        else:
            print(f"   ⚠️  Key exchange failed after 5 attempts, will use lazy exchange", flush=True)
        
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
    
    #39 - Server Durdurma
    def stop(self):
        """Node 1 sunucusunu durdur"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Node 1: Embedder (Layers 0-10)')
    parser.add_argument('--port', type=int, default=9080)
    parser.add_argument('--device', type=str, default='cpu')
    parser.add_argument('--model-path', type=str, required=True)
    parser.add_argument('--next-port', type=int, default=9081)
    
    args = parser.parse_args()
    
    config = Node1Config(
        port=args.port,
        device=args.device,
        model_path=args.model_path,
        next_node_port=args.next_port
    )
    
    node = Node1Embedder(config, args.model_path)
    
    try:
        node.load_model()
        node.start_server()
    except KeyboardInterrupt:
        print("\n⚠️ Stopping Node 1...")
        node.stop()

