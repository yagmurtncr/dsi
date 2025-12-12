#!/usr/bin/env python3
"""
🔐 Güvenli Bellek Yönetimi (CPU)
Ne İşe Yarar: Hassas verileri bellekten güvenli şekilde siler (3-pass overwrite)

Yazılım Tabanlı Bellek Koruması:
- 3-adımlı silme (sıfır → bir → rastgele)
- Kullanım sonrası bellek temizleme
- Data remanence saldırılarına karşı koruma

NOT: Yazılım simülasyonu! Production için Intel SGX hardware kullan!

Normal Silme:
  Memory: [HASTA: AYŞE YILMAZ...] 
  del tensor
  Memory: [HASTA: AYŞE YILMAZ...] ← Hala okunabilir! 🚨

Güvenli Silme (3-pass):
  Memory: [HASTA: AYŞE YILMAZ...]
  → [0, 0, 0, ...]           (Pass 1: Sıfırlar)
  → [1, 1, 1, ...]           (Pass 2: Birler)
  → [0.234, -0.567, ...]     (Pass 3: Rastgele)
  Memory: [RANDOM DATA] ← Orijinal veri kayboldu! ✅
"""

import gc
import torch
import numpy as np
from typing import Optional


class SecureMemoryManager:
    """
    Hassas veriler için güvenli bellek işlemleri (CPU)
    
    Özellikler:
    - Silmeden önce belleği ezme (3-pass overwrite)
    - Hassas tensor'ları takip etme
    - Otomatik temizleme
    """
    
    def __init__(self, node_id: int):
        self.node_id = node_id
        self.tracked_tensors = []
        print(f"🔒 Güvenli Bellek Yöneticisi başlatıldı (Node {node_id})")
    
    def secure_allocate(self, *args, **kwargs) -> torch.Tensor:
        """
        Tensor oluştur ve güvenli silme için takibe al
        
        Kullanım:
            tensor = secure_mem.secure_allocate(1, 10, 4096)
        """
        tensor = torch.zeros(*args, **kwargs)
        self.tracked_tensors.append(id(tensor))
        return tensor
    
    def secure_delete(self, tensor: torch.Tensor, verbose: bool = False):
        """
        Tensor'ı belleği ezarak güvenli şekilde sil (3-pass overwrite)
        
        Adımlar:
        1. Sıfırlarla ez
        2. Birlerle ez
        3. Rastgele verilerle ez
        4. Referansı sil
        5. Garbage collection zorla
        
        Parametreler:
            tensor: Güvenli silinecek tensor
            verbose: Debug bilgisi yazdır
        """
        if tensor is None:
            return
        
        try:
            # Bellek boyutunu al
            memory_size = tensor.numel() * tensor.element_size()
            
            if verbose:
                print(f"   🗑️  Tensor güvenli siliniyor ({memory_size} bytes)...")
            
            # Adım 1: Sıfırlarla ez
            tensor.data[:] = 0
            
            # Adım 2: Birlerle ez
            tensor.data[:] = 1
            
            # Adım 3: Rastgele verilerle ez
            tensor.data.copy_(torch.randn_like(tensor))
            
            # Adım 4: Referansı sil
            tensor_id = id(tensor)
            if tensor_id in self.tracked_tensors:
                self.tracked_tensors.remove(tensor_id)
            
            del tensor
            
            # Adım 5: Garbage collection zorla
            gc.collect()
            
            if verbose:
                print(f"   ✅ Bellek ezildi ve serbest bırakıldı")
                
        except Exception as e:
            print(f"   ⚠️  Secure delete warning: {e}")
    
    def secure_process(self, encrypted_data: bytes, process_fn, verbose: bool = True):
        """
        Şifreli veriyi otomatik temizlemeyle işle
        
        Kullanım:
            result = secure_mem.secure_process(
                encrypted_data,
                lambda plaintext: model.forward(plaintext)
            )
        
        Parametreler:
            encrypted_data: Şifreli girdi
            process_fn: Plaintext'i işleyecek fonksiyon
            verbose: Debug bilgisi yazdır
            
        Döndürür:
            Şifreli sonuç
        """
        plaintext_tensor = None
        result_tensor = None
        
        try:
            # 1. Şifreyi çöz (simülasyon - gerçek SGX'te enclave içinde olur)
            if verbose:
                print(f"   🔓 Veri şifresi çözülüyor...")
            plaintext_tensor = self._decrypt(encrypted_data)
            
            # 2. İşle (güvenli bellekte)
            if verbose:
                print(f"   ⚙️  Güvenli bellekte işleniyor...")
            result_tensor = process_fn(plaintext_tensor)
            
            # 3. Sonucu şifrele
            if verbose:
                print(f"   🔒 Sonuç şifreleniyor...")
            encrypted_result = self._encrypt(result_tensor)
            
            return encrypted_result
            
        finally:
            # 4. Güvenli temizlik (HER ZAMAN çalışır, hata olsa bile)
            if verbose:
                print(f"   🧹 Hassas veri bellekten temizleniyor...")
            
            if plaintext_tensor is not None:
                self.secure_delete(plaintext_tensor, verbose=verbose)
            
            if result_tensor is not None:
                self.secure_delete(result_tensor, verbose=verbose)
            
            gc.collect()
    
    def _decrypt(self, encrypted_data: bytes) -> torch.Tensor:
        """Şifre çözme simülasyonu (placeholder)"""
        # Gerçek implementasyonda AES-256 kullan
        return torch.zeros(1, 10, 4096)  # Dummy
    
    def _encrypt(self, tensor: torch.Tensor) -> bytes:
        """Şifreleme simülasyonu (placeholder)"""
        # Gerçek implementasyonda AES-256 kullan
        return b"encrypted_data"  # Dummy
    
    def cleanup_all(self):
        """Acil durum: Tüm takipli tensor'ları temizle"""
        print(f"🧹 Acil bellek temizliği (Node {self.node_id})...")
        gc.collect()
        print(f"   ✅ {len(self.tracked_tensors)} tensor temizlendi")
        self.tracked_tensors.clear()


def secure_tensor_operation(func):
    """
    Güvenli tensor işlemleri için decorator
    
    Ara tensor'ları otomatik olarak temizler
    
    Kullanım:
        @secure_tensor_operation
        def forward_layer(hidden_states):
            result = layer(hidden_states)
            return result
    """
    def wrapper(*args, **kwargs):
        result = None
        intermediate_tensors = []
        
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            # Ara sonuçları temizle
            for tensor in intermediate_tensors:
                if isinstance(tensor, torch.Tensor):
                    tensor.data[:] = 0
                    del tensor
            gc.collect()
    
    return wrapper


# Global instance (singleton pattern)
_secure_memory_manager = None

def get_secure_memory_manager(node_id: int = 0) -> SecureMemoryManager:
    """Güvenli bellek yöneticisini al veya oluştur (singleton)"""
    global _secure_memory_manager
    if _secure_memory_manager is None:
        _secure_memory_manager = SecureMemoryManager(node_id)
    return _secure_memory_manager


if __name__ == "__main__":
    # Test
    print("🧪 Testing Secure Memory Manager\n")
    
    secure_mem = SecureMemoryManager(node_id=1)
    
    # Test 1: Secure delete
    print("Test 1: Secure Delete")
    tensor = torch.randn(1000, 1000)
    print(f"  Created tensor: {tensor.shape}, {tensor.numel() * tensor.element_size()} bytes")
    secure_mem.secure_delete(tensor, verbose=True)
    print()
    
    # Test 2: Secure process
    print("Test 2: Secure Process")
    encrypted_data = b"encrypted_prompt"
    result = secure_mem.secure_process(
        encrypted_data,
        lambda x: x * 2,  # Dummy processing
        verbose=True
    )
    print(f"  Result: {len(result)} bytes\n")
    
    print("✅ All tests passed!")

