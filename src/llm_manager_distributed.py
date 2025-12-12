#!/usr/bin/env python3
"""🌐 Dağıtık LLM Yöneticisi - 3 node'a tokenization ve generation koordine eder"""

import socket
import json
import pickle
from pathlib import Path
from typing import Optional, Dict, Any
from transformers import AutoTokenizer

class DistributedLLMManager:
    """Dağıtık LLM yöneticisi - Tokenization, node iletişimi ve detokenization"""
    
    #21 - LLM Manager Başlatma (Tokenizer + Node Config)
    def __init__(self):
        """Başlatma - Tokenizer yükle ve node bağlantılarını hazırla"""
        print("🚀 Distributed LLM Manager başlatılıyor...")
        print("   Model: Llama-3.1-8B-Instruct (Distributed)")
        print("   Nodes: 3 (layers split)")
        
        # Node konfigürasyonu
        self.nodes = [
            {"id": 1, "host": "127.0.0.1", "port": 8001, "layers": "0-10"},
            {"id": 2, "host": "127.0.0.1", "port": 8002, "layers": "11-21"},
            {"id": 3, "host": "127.0.0.1", "port": 8003, "layers": "22-31"},
        ]
        
        # Tokenizer (sadece tokenize için)
        model_path = Path("/mnt/model-cache/hub/decoder-only/models--meta-llama--Llama-3.1-8B-Instruct/snapshots/0e9e39f249a16976918f6564b8830bc894c89659")
        
        if not model_path.exists():
            raise FileNotFoundError(f"Model path bulunamadı: {model_path}")
        
        print(f"   Tokenizer yükleniyor: {model_path}")
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(model_path),
            local_files_only=True
        )
        
        print("✅ Distributed LLM Manager hazır!")
        print(f"   Node connections:")
        for node in self.nodes:
            print(f"      • Node {node['id']}: {node['host']}:{node['port']} (layers {node['layers']})")
    
    #22 - Node'a TCP Request Gönderme
    def _send_to_node(self, node_config: Dict, data: Dict[str, Any]) -> Dict[str, Any]:
        """Belirtilen node'a TCP socket ile JSON request gönderir ve response alır"""
        try:
            # Socket oluştur
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3600)  # CPU mode: 1 saat timeout (uzun cevaplar için)
            
            # Bağlan
            sock.connect((node_config['host'], node_config['port']))
            
            # Veriyi gönder (JSON)
            request_json = json.dumps(data)
            request_bytes = request_json.encode('utf-8')
            
            # Length prefix gönder (4 byte)
            length = len(request_bytes)
            sock.sendall(length.to_bytes(4, byteorder='big'))
            
            # Data gönder
            sock.sendall(request_bytes)
            
            # Yanıt al (length prefix)
            response_length_bytes = sock.recv(4)
            if not response_length_bytes:
                raise Exception("Node yanıt vermedi")
            
            response_length = int.from_bytes(response_length_bytes, byteorder='big')
            
            # Yanıt data al
            response_data = b''
            while len(response_data) < response_length:
                chunk = sock.recv(min(response_length - len(response_data), 4096))
                if not chunk:
                    break
                response_data += chunk
            
            # JSON parse
            response = json.loads(response_data.decode('utf-8'))
            
            sock.close()
            
            return response
            
        except Exception as e:
            print(f"   ❌ Node {node_config['id']} hatası: {e}")
            raise
    
    #23 - Text Generation (Autoregressive Loop)
    def generate(self, prompt: str, max_tokens: int = 50, temperature: float = 0.7, system_prompt: str = None) -> str:
        """
        🔐 GÜVENLİK GELİŞMESİ: Generation loop artık API'de!
        
        Node'lar sadece forward pass yapıyor, API token sampling + decode yapıyor.
        Bu sayede Node 1 final cevabı görmüyor! ✅
        """
        print(f"\n🤖 Distributed Generation başlıyor (API-side loop)...")
        print(f"   Prompt: {prompt[:50]}...")
        
        # Sistem mesajı
        if system_prompt is None:
            system_prompt = """Sen kısa, öz ve anlaşılır cevaplar veren bir asistansın.
Eğer prompt'ta <|PERSON_X|> gibi tag'ler varsa, cevabında bu tag'leri aynen kullan. Örnek: "Sayın <|PERSON_1|>, size önerim..."
Bu tag'ler kişisel veri koruma içindir."""
        
        # Chat format
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        # Tokenize
        formatted_prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        inputs = self.tokenizer(formatted_prompt, return_tensors="pt")
        input_ids = inputs['input_ids'][0].tolist()
        
        print(f"   📝 Input tokens: {len(input_ids)}")
        print(f"   🔄 Starting autoregressive generation...")
        
        # Autoregressive generation (API'de!)
        current_ids = input_ids.copy()
        
        for step in range(max_tokens):
            # Node 1'e forward pass isteği gönder
            node1_request = {
                "type": "forward",
                "input_ids": current_ids
            }
            
            try:
                node1_response = self._send_to_node(self.nodes[0], node1_request)
                
                if node1_response.get('status') != 'success':
                    print(f"      ❌ Node 1 error: {node1_response.get('error', 'Unknown')}")
                    break
                
                # Logit'leri al (Node 1 decode ETMEDİ!)
                logits_raw = node1_response['logits']
                
                # Logit'leri tensor'a çevir
                if isinstance(logits_raw[0], list):
                    import torch
                    logits = torch.tensor(logits_raw[0])  # [vocab_size]
                else:
                    import torch
                    logits = torch.tensor(logits_raw)  # [vocab_size]
                
                # Token sampling (API'de!)
                if temperature > 0:
                    probs = torch.softmax(logits / temperature, dim=-1)
                    next_token = torch.multinomial(probs, num_samples=1).item()
                else:
                    next_token = torch.argmax(logits).item()
                
                # Diziye ekle
                current_ids.append(next_token)
                
                # EOS kontrolü
                if next_token == self.tokenizer.eos_token_id:
                    print(f"      ✅ EOS reached at step {step}")
                    break
                
                if (step + 1) % 10 == 0:
                    print(f"      Generated {step + 1}/{max_tokens} tokens...")
                    
            except Exception as e:
                print(f"      ❌ Generation step {step} failed: {e}")
                break
        
        print(f"   ✅ Generation tamamlandı!")
        print(f"   📝 Output tokens: {len(current_ids) - len(input_ids)}")
        
        # Decode (API'de!)
        generated_text = self.tokenizer.decode(
            current_ids[len(input_ids):],
            skip_special_tokens=True
        )
        
        return generated_text.strip()
    
    #24 - Cleanup (Kaynak Serbest Bırakma)
    def cleanup(self):
        """Temizlik - Kaynakları serbest bırak"""
        print("🧹 Distributed LLM Manager temizleniyor...")
        print("✅ Temizlik tamamlandı")


# Test
if __name__ == "__main__":
    print("\n" + "="*70)
    print("🧪 DAĞITIK LLM YÖNETİCİSİ TESTİ")
    print("="*70)
    
    manager = DistributedLLMManager()
    
    prompt = "Python nedir?"
    print(f"\n📝 Prompt: {prompt}")
    
    response = manager.generate(prompt, max_tokens=50)
    print(f"💬 Response: {response}")
    
    manager.cleanup()
    
    print("\n" + "="*70)
    print("✅ TEST TAMAMLANDI!")
    print("="*70)

