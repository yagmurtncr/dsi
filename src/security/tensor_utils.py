#!/usr/bin/env python3
"""
🚀 Tensor Serialization Utils
Tensor'ları JSON-uyumlu formata çevirir (base64 + LZ4)

Özellikler:
- JSON içinde taşınabilir (encryption ile uyumlu)
- LZ4 sıkıştırma (3x küçültme)
- NumPy/PyTorch uyumlu
"""

import base64
import numpy as np
import torch
from typing import Dict, Any, Union

# LZ4 sıkıştırma
try:
    import lz4.frame
    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False


def tensor_to_json(tensor: torch.Tensor) -> Dict[str, Any]:
    """
    PyTorch tensor'ı JSON-uyumlu dict'e çevir
    
    Args:
        tensor: PyTorch tensor
        
    Returns:
        Dict: {'_tensor': True, 'data': base64, 'shape': [...], 'dtype': str}
    """
    arr = tensor.detach().cpu().numpy()
    data_bytes = np.ascontiguousarray(arr).tobytes()
    
    # LZ4 sıkıştır (varsa)
    if HAS_LZ4:
        compressed = lz4.frame.compress(data_bytes)
        is_compressed = True
    else:
        compressed = data_bytes
        is_compressed = False
    
    return {
        '_tensor': True,
        'data': base64.b64encode(compressed).decode('ascii'),
        'shape': list(arr.shape),
        'dtype': str(arr.dtype),
        'compressed': is_compressed
    }


def json_to_tensor(data: Dict[str, Any]) -> torch.Tensor:
    """
    JSON dict'i PyTorch tensor'a çevir
    
    Args:
        data: tensor_to_json çıktısı
        
    Returns:
        torch.Tensor
    """
    raw_bytes = base64.b64decode(data['data'])
    
    # Decompress
    if data.get('compressed', False) and HAS_LZ4:
        raw_bytes = lz4.frame.decompress(raw_bytes)
    
    arr = np.frombuffer(raw_bytes, dtype=np.dtype(data['dtype']))
    arr = arr.reshape(data['shape'])
    
    # Writable copy yap (PyTorch uyarısını önlemek için)
    arr = arr.copy()
    
    return torch.from_numpy(arr)


def prepare_for_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dict içindeki tensor'ları JSON-uyumlu hale getir
    
    Args:
        data: Tensor içerebilecek dict
        
    Returns:
        Dict: JSON-uyumlu dict
    """
    result = {}
    for key, value in data.items():
        if isinstance(value, torch.Tensor):
            result[key] = tensor_to_json(value)
        elif isinstance(value, np.ndarray):
            result[key] = tensor_to_json(torch.from_numpy(value))
        elif isinstance(value, dict):
            result[key] = prepare_for_json(value)
        elif isinstance(value, list):
            result[key] = [
                prepare_for_json(v) if isinstance(v, dict) else 
                tensor_to_json(v) if isinstance(v, torch.Tensor) else v 
                for v in value
            ]
        else:
            result[key] = value
    return result


def restore_from_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    JSON'dan tensor'ları geri yükle
    
    Args:
        data: prepare_for_json çıktısı
        
    Returns:
        Dict: Tensor'ları restore edilmiş dict
    """
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            if value.get('_tensor'):
                result[key] = json_to_tensor(value)
            else:
                result[key] = restore_from_json(value)
        elif isinstance(value, list):
            result[key] = [
                json_to_tensor(v) if isinstance(v, dict) and v.get('_tensor') else
                restore_from_json(v) if isinstance(v, dict) else v
                for v in value
            ]
        else:
            result[key] = value
    return result


# Test
if __name__ == "__main__":
    import time
    import json
    
    print("🧪 Tensor Utils Test")
    print("=" * 50)
    
    # Test tensor (hidden states boyutunda)
    tensor = torch.randn(1, 100, 4096)
    print(f"Original tensor shape: {tensor.shape}")
    print(f"Original tensor size: {tensor.numel() * 4 / 1024 / 1024:.2f} MB")
    
    # Convert to JSON-compatible
    start = time.time()
    json_data = tensor_to_json(tensor)
    encode_time = time.time() - start
    
    json_str = json.dumps(json_data)
    print(f"\nJSON string size: {len(json_str) / 1024 / 1024:.2f} MB")
    print(f"Compression ratio: {tensor.numel() * 4 / len(json_str):.1f}x")
    print(f"Encode time: {encode_time * 1000:.1f} ms")
    
    # Restore
    start = time.time()
    restored = json_to_tensor(json.loads(json_str))
    decode_time = time.time() - start
    
    print(f"Decode time: {decode_time * 1000:.1f} ms")
    print(f"Shape match: {restored.shape == tensor.shape}")
    print(f"Values match: {torch.allclose(tensor, restored)}")

