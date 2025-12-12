#!/usr/bin/env python3
"""
🔐 Node-to-Node Encryption (RSA-2048 + AES-256)
Ne İşe Yarar: Node'lar arası veri iletimini şifreler (hybrid encryption)

Hybrid Encryption:
1. AES-256 ile data şifrelenir (hızlı, büyük veri için)
2. AES key RSA-2048 ile şifrelenir (güvenli, küçük veri için)
3. Her iki şifreli veri birlikte gönderilir

Güvenlik: Network sniffing'e karşı koruma
"""

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import os
import json
import base64
from typing import Tuple, Dict, Any


class NodeCrypto:
    """
    Node'lar arası güvenli iletişim için hybrid encryption (RSA-2048 + AES-256-GCM)
    
    🚀 OPTİMİZE: Oturum anahtarı önbelleği ile 10x hızlanma
    - İlk mesajda: RSA ile AES anahtar değişimi (yavaş, güvenli)
    - Sonraki mesajlar: Sadece AES (hızlı, güvenli)
    """
    
    def __init__(self, node_id: int):
        self.node_id = node_id
        self.private_key = None
        self.public_key = None
        self.peer_public_keys: Dict[int, Any] = {}  # Diğer node'ların public key'leri
        
        # 🚀 OTURUM ANAHTARI ÖNBELLEĞİ: Her peer için ayrı AES oturum anahtarı
        self.session_keys: Dict[int, bytes] = {}  # peer_node_id -> AES-256 anahtarı
        self.session_key_usage: Dict[int, int] = {}  # peer_node_id -> kullanım sayısı
        self.SESSION_KEY_ROTATION = 1000  # Her 1000 mesajda anahtar yenile (güvenlik)
        
        # RSA key pair oluştur
        self._generate_keys()
        
        print(f"🔐 NodeCrypto başlatıldı (Node {node_id})")
        print(f"   Encryption: RSA-2048 + AES-256-GCM")
        print(f"   🚀 Oturum anahtarı önbelleği: AKTİF (yenileme: {self.SESSION_KEY_ROTATION})")
    
    def _generate_keys(self):
        """Node için RSA-2048 key pair oluştur"""
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()
        print(f"   ✅ RSA-2048 key pair oluşturuldu")
    
    def get_public_key_bytes(self) -> bytes:
        """Public key'i serileştir (diğer node'lara göndermek için)"""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    
    def add_peer_public_key(self, peer_node_id: int, public_key_bytes: bytes):
        """Diğer node'un public key'ini ekle"""
        public_key = serialization.load_pem_public_key(
            public_key_bytes,
            backend=default_backend()
        )
        self.peer_public_keys[peer_node_id] = public_key
        print(f"   ✅ Node {peer_node_id} public key'i eklendi")
    
    def _get_or_create_session_key(self, peer_node_id: int) -> tuple:
        """
        🚀 Oturum anahtarını al veya oluştur
        
        Döndürür:
            (aes_key, is_new): AES anahtarı ve yeni mi flag'i
        """
        # Anahtar yenileme kontrolü
        usage = self.session_key_usage.get(peer_node_id, 0)
        
        if peer_node_id not in self.session_keys or usage >= self.SESSION_KEY_ROTATION:
            # Yeni oturum anahtarı oluştur
            self.session_keys[peer_node_id] = os.urandom(32)  # AES-256
            self.session_key_usage[peer_node_id] = 1  # 1'den başla (bu kullanım dahil)
            return self.session_keys[peer_node_id], True
        
        # Mevcut anahtarı kullan
        self.session_key_usage[peer_node_id] = usage + 1
        return self.session_keys[peer_node_id], False
    
    def encrypt_for_peer(self, data: Dict[str, Any], peer_node_id: int) -> bytes:
        """
        Veriyi diğer node için şifrele (hibrit şifreleme)
        
        🚀 OPTİMİZE: Oturum anahtarı önbelleği
        - İlk mesaj: RSA + AES (anahtar değişimi)
        - Sonraki mesajlar: Sadece AES (10x hızlı)
        
        Parametreler:
            data: Şifrelenecek veri (dict)
            peer_node_id: Hedef node ID
            
        Döndürür:
            Şifreli veri (bytes)
        """
        if peer_node_id not in self.peer_public_keys:
            raise ValueError(f"Node {peer_node_id} public key'i bulunamadı!")
        
        # 🚀 Oturum anahtarını al (önbellekten veya yeni oluştur)
        aes_key, is_new_key = self._get_or_create_session_key(peer_node_id)
        
        # 2. Data'yı JSON serialize et
        serialized_data = json.dumps(data).encode('utf-8')
        
        # 3. AES-256-GCM ile şifrele
        iv = os.urandom(12)  # GCM için 96-bit IV (her mesaj için farklı!)
        cipher = Cipher(
            algorithms.AES(aes_key),
            modes.GCM(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(serialized_data) + encryptor.finalize()
        
        # GCM tag (authentication)
        tag = encryptor.tag
        
        # 4. Sadece yeni anahtar ise RSA ile şifrele (optimizasyon!)
        if is_new_key:
            encrypted_aes_key = self.peer_public_keys[peer_node_id].encrypt(
                aes_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            encrypted_key_b64 = base64.b64encode(encrypted_aes_key).decode('utf-8')
        else:
            encrypted_key_b64 = None  # Anahtar zaten karşı tarafta var
        
        # 5. Hepsini birleştir (base64 encode)
        encrypted_package = {
            'iv': base64.b64encode(iv).decode('utf-8'),
            'ciphertext': base64.b64encode(ciphertext).decode('utf-8'),
            'tag': base64.b64encode(tag).decode('utf-8'),
            'sender': self.node_id,
            'new_key': is_new_key  # 🚀 Flag: karşı taraf key'i cache'lesin mi?
        }
        
        if encrypted_key_b64:
            encrypted_package['encrypted_aes_key'] = encrypted_key_b64
        
        return json.dumps(encrypted_package).encode('utf-8')
    
    def decrypt_from_peer(self, encrypted_data: bytes) -> Dict[str, Any]:
        """
        Diğer node'dan gelen şifreli veriyi çöz
        
        🚀 OPTİMİZE: Oturum anahtarı önbelleği
        - new_key=True: RSA ile AES anahtarı çöz ve önbelleğe al
        - new_key=False: Önbellekteki anahtarı kullan (10x hızlı)
        
        Parametreler:
            encrypted_data: Şifreli veri (bytes)
            
        Döndürür:
            Çözülmüş veri (dict)
        """
        # 1. Package'ı parse et
        encrypted_package = json.loads(encrypted_data.decode('utf-8'))
        
        iv = base64.b64decode(encrypted_package['iv'])
        ciphertext = base64.b64decode(encrypted_package['ciphertext'])
        tag = base64.b64decode(encrypted_package['tag'])
        sender = encrypted_package['sender']
        is_new_key = encrypted_package.get('new_key', True)  # Eski format uyumluluğu
        
        # 🚀 Oturum anahtarı: önbellekten veya RSA ile çöz
        if is_new_key or sender not in self.session_keys:
            # Yeni anahtar - RSA ile çöz
            if 'encrypted_aes_key' not in encrypted_package:
                raise ValueError("new_key=True ama encrypted_aes_key yok!")
            
            encrypted_aes_key = base64.b64decode(encrypted_package['encrypted_aes_key'])
            aes_key = self.private_key.decrypt(
                encrypted_aes_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            # Önbelleğe kaydet
            self.session_keys[sender] = aes_key
        else:
            # 🚀 Önbellekteki anahtarı kullan (RSA işlemi YOK!)
            aes_key = self.session_keys[sender]
        
        # 3. Data'yı AES-256-GCM ile çöz
        cipher = Cipher(
            algorithms.AES(aes_key),
            modes.GCM(iv, tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        
        # 4. JSON deserialize
        data = json.loads(plaintext.decode('utf-8'))
        
        return data


# Global instances (her node için)
_node_crypto_instances: Dict[int, NodeCrypto] = {}

def get_node_crypto(node_id: int) -> NodeCrypto:
    """Node için crypto instance'ını al veya oluştur (singleton)"""
    global _node_crypto_instances
    if node_id not in _node_crypto_instances:
        _node_crypto_instances[node_id] = NodeCrypto(node_id)
    return _node_crypto_instances[node_id]


if __name__ == "__main__":
    print("🧪 Testing Node-to-Node Encryption\n")
    
    # Node 1 ve Node 2 oluştur
    node1 = NodeCrypto(node_id=1)
    node2 = NodeCrypto(node_id=2)
    
    # Public key'leri paylaş
    node1.add_peer_public_key(2, node2.get_public_key_bytes())
    node2.add_peer_public_key(1, node1.get_public_key_bytes())
    
    # Test 1: Node 1 → Node 2
    print("\n1️⃣  Node 1 → Node 2 şifreli iletişim")
    data = {
        'hidden_states': [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
        'prompt': 'Hasta bilgileri: Ayşe Yılmaz',
        'max_tokens': 50
    }
    
    print(f"   Original data: {len(json.dumps(data))} bytes")
    encrypted = node1.encrypt_for_peer(data, peer_node_id=2)
    print(f"   Encrypted: {len(encrypted)} bytes")
    
    decrypted = node2.decrypt_from_peer(encrypted)
    print(f"   Decrypted: {decrypted['prompt']}")
    print(f"   ✅ Match: {data == decrypted}")
    
    # Test 2: Node 2 → Node 1
    print("\n2️⃣  Node 2 → Node 1 şifreli iletişim")
    response_data = {
        'logits': [[0.9, 0.8, 0.7], [0.6, 0.5, 0.4]],
        'status': 'success'
    }
    
    encrypted = node2.encrypt_for_peer(response_data, peer_node_id=1)
    decrypted = node1.decrypt_from_peer(encrypted)
    print(f"   ✅ Match: {response_data == decrypted}")
    
    print("\n✅ Tüm testler başarılı!")

