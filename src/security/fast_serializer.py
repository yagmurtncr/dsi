#!/usr/bin/env python3
"""
🚀 Fast Binary Serializer
JSON yerine binary format kullanarak 3-5x hızlanma sağlar

Özellikler:
- NumPy array'ler için native binary format
- Opsiyonel LZ4 sıkıştırma (2-3x küçültme)
- Şifreleme ile uyumlu
"""

import io
import struct
import numpy as np
from typing import Any, Dict, Union
import torch

# LZ4 sıkıştırma (opsiyonel - çok hızlı)
try:
    import lz4.frame
    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False


class FastSerializer:
    """
    🚀 Hızlı Binary Serializer
    
    JSON'a göre 3-5x daha hızlı, 3x daha küçük boyut.
    """
    
    # Magic bytes for format detection
    MAGIC = b'FSER'
    VERSION = 1
    
    # Type tags
    TYPE_DICT = 1
    TYPE_LIST = 2
    TYPE_TENSOR = 3
    TYPE_NDARRAY = 4
    TYPE_STRING = 5
    TYPE_INT = 6
    TYPE_FLOAT = 7
    TYPE_BOOL = 8
    TYPE_NONE = 9
    
    def __init__(self, use_compression: bool = True):
        """
        Args:
            use_compression: LZ4 sıkıştırma kullan (varsayılan: True)
        """
        self.use_compression = use_compression and HAS_LZ4
    
    def serialize(self, data: Any) -> bytes:
        """
        Veriyi binary formata çevir
        
        Args:
            data: Serialize edilecek veri (dict, list, tensor, vb.)
        
        Returns:
            bytes: Binary veri
        """
        buffer = io.BytesIO()
        
        # Magic + version
        buffer.write(self.MAGIC)
        buffer.write(struct.pack('B', self.VERSION))
        
        # Compression flag
        buffer.write(struct.pack('?', self.use_compression))
        
        # Serialize data
        self._serialize_value(buffer, data)
        
        raw_data = buffer.getvalue()
        
        # Compress if enabled
        if self.use_compression:
            # Skip header (6 bytes) for compression
            header = raw_data[:6]
            payload = raw_data[6:]
            compressed = lz4.frame.compress(payload)
            return header + compressed
        
        return raw_data
    
    def deserialize(self, data: bytes) -> Any:
        """
        Binary veriyi Python objesine çevir
        
        Args:
            data: Binary veri
        
        Returns:
            Any: Deserialize edilmiş veri
        """
        buffer = io.BytesIO(data)
        
        # Check magic
        magic = buffer.read(4)
        if magic != self.MAGIC:
            raise ValueError("Invalid format: magic mismatch")
        
        # Version
        version = struct.unpack('B', buffer.read(1))[0]
        if version != self.VERSION:
            raise ValueError(f"Unsupported version: {version}")
        
        # Compression flag
        is_compressed = struct.unpack('?', buffer.read(1))[0]
        
        # Decompress if needed
        if is_compressed:
            remaining = buffer.read()
            decompressed = lz4.frame.decompress(remaining)
            buffer = io.BytesIO(decompressed)
        
        return self._deserialize_value(buffer)
    
    def _serialize_value(self, buffer: io.BytesIO, value: Any):
        """Tek bir değeri serialize et"""
        
        if value is None:
            buffer.write(struct.pack('B', self.TYPE_NONE))
        
        elif isinstance(value, bool):
            buffer.write(struct.pack('B', self.TYPE_BOOL))
            buffer.write(struct.pack('?', value))
        
        elif isinstance(value, int):
            buffer.write(struct.pack('B', self.TYPE_INT))
            buffer.write(struct.pack('q', value))  # int64
        
        elif isinstance(value, float):
            buffer.write(struct.pack('B', self.TYPE_FLOAT))
            buffer.write(struct.pack('d', value))  # float64
        
        elif isinstance(value, str):
            buffer.write(struct.pack('B', self.TYPE_STRING))
            encoded = value.encode('utf-8')
            buffer.write(struct.pack('I', len(encoded)))
            buffer.write(encoded)
        
        elif isinstance(value, torch.Tensor):
            buffer.write(struct.pack('B', self.TYPE_TENSOR))
            self._serialize_tensor(buffer, value)
        
        elif isinstance(value, np.ndarray):
            buffer.write(struct.pack('B', self.TYPE_NDARRAY))
            self._serialize_ndarray(buffer, value)
        
        elif isinstance(value, dict):
            buffer.write(struct.pack('B', self.TYPE_DICT))
            buffer.write(struct.pack('I', len(value)))
            for k, v in value.items():
                self._serialize_value(buffer, k)
                self._serialize_value(buffer, v)
        
        elif isinstance(value, (list, tuple)):
            buffer.write(struct.pack('B', self.TYPE_LIST))
            buffer.write(struct.pack('I', len(value)))
            for item in value:
                self._serialize_value(buffer, item)
        
        else:
            # Fallback: convert to list
            if hasattr(value, 'tolist'):
                self._serialize_value(buffer, value.tolist())
            else:
                raise TypeError(f"Unsupported type: {type(value)}")
    
    def _deserialize_value(self, buffer: io.BytesIO) -> Any:
        """Tek bir değeri deserialize et"""
        
        type_tag = struct.unpack('B', buffer.read(1))[0]
        
        if type_tag == self.TYPE_NONE:
            return None
        
        elif type_tag == self.TYPE_BOOL:
            return struct.unpack('?', buffer.read(1))[0]
        
        elif type_tag == self.TYPE_INT:
            return struct.unpack('q', buffer.read(8))[0]
        
        elif type_tag == self.TYPE_FLOAT:
            return struct.unpack('d', buffer.read(8))[0]
        
        elif type_tag == self.TYPE_STRING:
            length = struct.unpack('I', buffer.read(4))[0]
            return buffer.read(length).decode('utf-8')
        
        elif type_tag == self.TYPE_TENSOR:
            return self._deserialize_tensor(buffer)
        
        elif type_tag == self.TYPE_NDARRAY:
            return self._deserialize_ndarray(buffer)
        
        elif type_tag == self.TYPE_DICT:
            count = struct.unpack('I', buffer.read(4))[0]
            result = {}
            for _ in range(count):
                key = self._deserialize_value(buffer)
                value = self._deserialize_value(buffer)
                result[key] = value
            return result
        
        elif type_tag == self.TYPE_LIST:
            count = struct.unpack('I', buffer.read(4))[0]
            return [self._deserialize_value(buffer) for _ in range(count)]
        
        else:
            raise ValueError(f"Unknown type tag: {type_tag}")
    
    def _serialize_tensor(self, buffer: io.BytesIO, tensor: torch.Tensor):
        """PyTorch tensor'ı serialize et"""
        # CPU'ya taşı ve numpy'a çevir
        arr = tensor.detach().cpu().numpy()
        self._serialize_ndarray(buffer, arr)
    
    def _deserialize_tensor(self, buffer: io.BytesIO) -> torch.Tensor:
        """PyTorch tensor'ı deserialize et"""
        arr = self._deserialize_ndarray(buffer)
        return torch.from_numpy(arr)
    
    def _serialize_ndarray(self, buffer: io.BytesIO, arr: np.ndarray):
        """NumPy array'i serialize et"""
        # Dtype
        dtype_str = str(arr.dtype)
        dtype_bytes = dtype_str.encode('utf-8')
        buffer.write(struct.pack('B', len(dtype_bytes)))
        buffer.write(dtype_bytes)
        
        # Shape
        buffer.write(struct.pack('B', len(arr.shape)))
        for dim in arr.shape:
            buffer.write(struct.pack('I', dim))
        
        # Data (contiguous)
        data = np.ascontiguousarray(arr).tobytes()
        buffer.write(struct.pack('I', len(data)))
        buffer.write(data)
    
    def _deserialize_ndarray(self, buffer: io.BytesIO) -> np.ndarray:
        """NumPy array'i deserialize et"""
        # Dtype
        dtype_len = struct.unpack('B', buffer.read(1))[0]
        dtype_str = buffer.read(dtype_len).decode('utf-8')
        dtype = np.dtype(dtype_str)
        
        # Shape
        ndim = struct.unpack('B', buffer.read(1))[0]
        shape = tuple(struct.unpack('I', buffer.read(4))[0] for _ in range(ndim))
        
        # Data
        data_len = struct.unpack('I', buffer.read(4))[0]
        data = buffer.read(data_len)
        
        return np.frombuffer(data, dtype=dtype).reshape(shape)


# Singleton
_fast_serializer = None


def get_fast_serializer(use_compression: bool = True) -> FastSerializer:
    """Fast Serializer singleton"""
    global _fast_serializer
    if _fast_serializer is None:
        _fast_serializer = FastSerializer(use_compression=use_compression)
    return _fast_serializer


def fast_serialize(data: Any) -> bytes:
    """Hızlı serialize helper"""
    return get_fast_serializer().serialize(data)


def fast_deserialize(data: bytes) -> Any:
    """Hızlı deserialize helper"""
    return get_fast_serializer().deserialize(data)


# Test
if __name__ == "__main__":
    import time
    import json
    
    print("🚀 Fast Serializer Test")
    print("=" * 50)
    
    # Test data (simulating hidden states)
    test_tensor = torch.randn(1, 100, 4096)
    test_data = {
        'type': 'forward_layers',
        'hidden_states': test_tensor,
        'node_id': 1
    }
    
    serializer = FastSerializer(use_compression=True)
    
    # Binary serialization
    start = time.time()
    binary_data = serializer.serialize(test_data)
    binary_time = time.time() - start
    
    # JSON serialization (for comparison)
    json_data_dict = {
        'type': 'forward_layers',
        'hidden_states': test_tensor.tolist(),
        'node_id': 1
    }
    start = time.time()
    json_data = json.dumps(json_data_dict)
    json_time = time.time() - start
    
    print(f"\n📊 Boyut Karşılaştırması:")
    print(f"   JSON: {len(json_data) / 1024 / 1024:.2f} MB")
    print(f"   Binary: {len(binary_data) / 1024 / 1024:.2f} MB")
    print(f"   Kazanç: {len(json_data) / len(binary_data):.1f}x daha küçük")
    
    print(f"\n⏱️ Hız Karşılaştırması:")
    print(f"   JSON: {json_time * 1000:.1f} ms")
    print(f"   Binary: {binary_time * 1000:.1f} ms")
    print(f"   Kazanç: {json_time / binary_time:.1f}x daha hızlı")
    
    # Verify deserialization
    start = time.time()
    restored = serializer.deserialize(binary_data)
    deser_time = time.time() - start
    
    print(f"\n✅ Deserialize: {deser_time * 1000:.1f} ms")
    print(f"   Shape match: {restored['hidden_states'].shape == test_tensor.shape}")

