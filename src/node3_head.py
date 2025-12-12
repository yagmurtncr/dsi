#!/usr/bin/env python3
"""
🔐 NODE 3: ÇIKTI KATMANI (Katman 22-31 + LM Head)

GÜVENLİK:
- Sadece son transformer katmanları (22-31) + LM head
- Embedding kodu YOK (Node 1'e özel)
- İlk/orta katmanlar YOK (Node 1/2'ye özel)
- Node 2'den şifreli hidden state'ler alır
- Final logit'leri üretip Node 2'ye döndürür
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
    from security import prepare_for_json, restore_from_json, json_to_tensor
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
class Node3Config:
    """Node 3 yapılandırması - Katman 22-31 + LM head"""
    node_id: int = 3
    layer_start: int = 22
    layer_end: int = 31
    port: int = 9082
    device: str = "cpu"
    model_path: str = ""  # Model yolu
    allowed_ips: list = None  # IP beyaz listesi


class EncryptionManager:
    """Node 3 şifreleme - RSA-2048 + AES-256"""
    
    #57 - Node 3 Encryption Manager Başlatma
    def __init__(self):
        print("🔐 Node 3 Encryption Manager...")
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()
        self.session_key = secrets.token_bytes(32)  # AES-256 oturum anahtarı
        print("   ✅ RSA-2048 + AES-256 initialized")


class Node3Head:
    """Node 3: Katman 22-31 + norm + LM head - Logit üretir"""
    
    #51 - Node 3 Head Başlatma
    def __init__(self, config: Node3Config, model_path: str):
        self.config = config
        self.model_path = model_path
        self.encryption = EncryptionManager()
        self.secure_mem = SecureMemoryManager(node_id=3)
        self.node_crypto = NodeCrypto(node_id=3)  # 🆕 Inter-node encryption
        if config.device.startswith("cuda"):
            self.secure_gpu = SecureGPUMemory(node_id=3, device=config.device)
        else:
            self.secure_gpu = None
        self.model_loaded = False
        self.server_socket = None
        self.running = False
        
        # Güvenlik: IP beyaz listesi
        self.allowed_ips = config.allowed_ips or ["127.0.0.1", "::1"]
        
        print(f"🚀 Node 3 Head initialized")
        print(f"   Layers: {config.layer_start}-{config.layer_end}")
        print(f"   Port: {config.port}")
        print(f"   Device: {config.device}")
        print(f"   Allowed IPs: {self.allowed_ips}")
        print(f"   Memory: Secure cleanup enabled")
        print(f"   🆕 Inter-node encryption: RSA-2048 + AES-256")
        print(f"   ✅ LM HEAD erişimi (sadece bu node'da!)")
    
    #52 - Model Yükleme (Layer 22-31 + LM Head)
    def load_model(self):
        """
        ⚡ EFFICIENT Model yükleme - Sadece layers 22-31 + norm + LM head!
        """
        if self.model_loaded:
            return
        
        print(f"📥 Loading Node 3 model (layers 22-31 + LM head)...")
        print(f"   ⚡ EFFICIENT MODE: Only loading required layers!")
        
        try:
            # ⚡ EFFICIENT: Sadece gerekli layer'ları yükle
            from efficient_model_loader import EfficientLayerLoader
            
            dtype = torch.float32 if self.config.device == "cpu" else torch.float16
            loader = EfficientLayerLoader(self.model_path, self.config.device)
            
            # Config'i sakla
            self.config_model = loader.config
            
            # Memory tahmini
            estimated_mem = loader.estimate_memory(
                self.config.layer_start, 
                self.config.layer_end,
                include_lm_head=True
            )
            print(f"   📊 Estimated memory: {estimated_mem:.2f} GB")
            
            # Layers 22-31 + norm + lm_head yükle
            self.layers, _, self.lm_head, self.norm = loader.create_partial_model(
                layer_start=self.config.layer_start,
                layer_end=self.config.layer_end,
                include_embed=False,
                include_lm_head=True,
                dtype=dtype
            )
            
            # Rotary embedding oluştur
            from transformers.models.llama.modeling_llama import LlamaRotaryEmbedding
            self.rotary_emb = LlamaRotaryEmbedding(config=loader.config)
            
            # Cihaza taşı
            print(f"   🔄 Moving to {self.config.device}...")
            self.rotary_emb = self.rotary_emb.to(self.config.device)
            self.norm = self.norm.to(self.config.device)
            self.lm_head = self.lm_head.to(self.config.device)
            for layer in self.layers:
                layer.to(self.config.device)
            print(f"   ✅ All components on {self.config.device}")
            
            self.model_checksum = "EFFICIENT_LOAD_MODE"
            self.model_loaded = True
            
            print(f"✅ Node 3 model ready!")
            print(f"   ⚡ Memory efficient: ~{estimated_mem:.1f}GB (vs 16GB full model)")
            print(f"   ✅ LM HEAD yüklendi (sadece bu node)")
            print(f"   ⚠️  Embedding yüklenmedi (Node 1'e özel)")
            print(f"   ⚠️  Katman 0-21 yüklenmedi (Node 1/2'ye özel)")
            
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
        hasher.update(f"node3_layers{self.config.layer_start}-{self.config.layer_end}_lmhead".encode())
        
        return hasher.hexdigest()
    
    #53 - Forward Head (Layer 22-31 + RMSNorm + LM Head → Logits)
    def forward_head(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """İleri geçiş - Katman 22-31 + norm + LM head → Logits"""
        with torch.no_grad():
            # ⚠️ Dtype conversion: Önceki node farklı dtype gönderebilir
            target_dtype = torch.float16 if self.config.device != "cpu" else torch.float32
            hidden_states = hidden_states.to(dtype=target_dtype)
            
            batch_size, seq_length, _ = hidden_states.shape
            
            # Pozisyon embedding'leri
            position_ids = torch.arange(0, seq_length, dtype=torch.long, device=self.config.device)
            position_ids = position_ids.unsqueeze(0).expand(batch_size, -1)
            
            cache_position = torch.arange(0, seq_length, dtype=torch.long, device=self.config.device)
            
            # RoPE (cos, sin) hesapla - transformers 4.42+ için gerekli
            position_embeddings = self.rotary_emb(hidden_states, position_ids)
            
            # Katman 22-31'den geçir
            for layer in self.layers:
                layer_output = layer(
                    hidden_states,
                    position_ids=position_ids,
                    position_embeddings=position_embeddings,
                    use_cache=False
                )
                # Layer çıktısı direkt tensor (tuple DEĞİL!)
                hidden_states = layer_output if isinstance(layer_output, torch.Tensor) else layer_output[0]
            
            # Layer normalizasyon
            hidden_states = self.norm(hidden_states)
            
            # ⚠️ LM head'e göndermeden önce dtype eşitle
            hidden_states = hidden_states.to(dtype=self.lm_head.weight.dtype)
            
            # LM head (vocabulary'ye projeksiyon)
            logits = self.lm_head(hidden_states)
            
            return logits
    
    #54 - Client Request Handler (Node 2'den)
    def handle_client(self, client_socket: socket.socket, client_addr):
        """Node 2'den gelen isteği işle"""
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
            except:
                # Fallback: Plaintext
                request = json.loads(data.decode('utf-8'))
                encrypted_request = False
            
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
            if 2 not in self.node_crypto.peer_public_keys:
                print(f"⚠️ Node 2 key'i henüz yok, forward request reddediliyor...")
                error_response = {'status': 'error', 'error': 'Key exchange not completed'}
                error_bytes = json.dumps(error_response).encode('utf-8')
                client_socket.sendall(len(error_bytes).to_bytes(4, 'big'))
                client_socket.sendall(error_bytes)
                return
            
            # Node 2'den hidden state'leri al
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
                hidden_states = json_to_tensor(hs)
            else:
                hidden_states = torch.tensor(hs)
            
            # Model'in dtype'ına çevir (GPU'da float16)
            if self.config.device.startswith('cuda'):
                hidden_states = hidden_states.to(dtype=torch.float16)
            
            hidden_states = hidden_states.to(self.config.device)
            
            # Node 3'ten geçir
            logits = self.forward_head(hidden_states)
            
            # Sadece son pozisyon logit'lerini döndür (otoregresif üretim için)
            last_logits = logits[:, -1, :].cpu().tolist()
            
            response = {
                'status': 'success',
                'logits': last_logits,
                'node_id': 3
            }
            
            # 🆕 Yanıtı şifrele (eğer peer key varsa)
            if encrypted_request and 2 in self.node_crypto.peer_public_keys:
                response_bytes = self.node_crypto.encrypt_for_peer(response, peer_node_id=2)
            else:
                response_bytes = json.dumps(response).encode('utf-8')
            
            client_socket.sendall(len(response_bytes).to_bytes(4, 'big'))
            client_socket.sendall(response_bytes)
            
        except Exception as e:
            print(f"❌ Request handling failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 🔐 SECURE MEMORY CLEANUP - Her request sonrası
            try:
                # Hidden states ve logits referanslarını temizle
                if 'hidden_states' in locals() and hidden_states is not None:
                    if hasattr(self, 'secure_mem'):
                        self.secure_mem.secure_delete(hidden_states, verbose=False)
                    del hidden_states
                
                if 'logits' in locals() and logits is not None:
                    if hasattr(self, 'secure_mem'):
                        self.secure_mem.secure_delete(logits, verbose=False)
                    del logits
                
                # GPU cache temizle
                if torch.cuda.is_available() and 'cuda' in self.config.device:
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
                
                # Garbage collection
                gc.collect()
                
            except Exception as cleanup_error:
                pass  # Cleanup hatasını sessizce geç
            
            client_socket.close()
    
    #55 - Server Başlatma (Socket Listen)
    def start_server(self):
        """Node 3 sunucusunu başlat"""
        print(f"🌐 Node 3 server starting (Port {self.config.port})...")
        
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('0.0.0.0', self.config.port))
        self.server_socket.listen(5)
        self.running = True
        
        print(f"✅ Node 3 listening on 0.0.0.0:{self.config.port}")
        
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
    
    #56 - Server Durdurma
    def stop(self):
        """Node 3 sunucusunu durdur"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Node 3: Head (Layers 22-31 + LM Head)')
    parser.add_argument('--port', type=int, default=9082)
    parser.add_argument('--device', type=str, default='cpu')
    parser.add_argument('--model-path', type=str, required=True)
    
    args = parser.parse_args()
    
    config = Node3Config(
        port=args.port,
        device=args.device,
        model_path=args.model_path
    )
    
    node = Node3Head(config, args.model_path)
    
    try:
        node.load_model()
        node.start_server()
    except KeyboardInterrupt:
        print("\n⚠️ Stopping Node 3...")
        node.stop()

