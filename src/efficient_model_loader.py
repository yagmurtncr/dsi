#!/usr/bin/env python3
"""
⚡ EFFICIENT MODEL LOADER - Memory-Optimized Layer Loading

Bu modül safetensors'tan sadece gerekli layer'ları yükler.
Tam modeli RAM'e almadan, direkt dosyadan tensor okur.

Memory Savings:
- Eski yöntem: 48GB peak (her node tam model yükler)
- Yeni yöntem: ~16GB peak (sadece gerekli layer'lar)
"""

import os
import json
import torch
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from safetensors import safe_open
from transformers import AutoConfig, LlamaForCausalLM
import torch.nn as nn


class EfficientLayerLoader:
    """
    Safetensors'tan sadece gerekli layer'ları yükler
    
    Avantajlar:
    - Zero-copy mmap: Disk'ten direkt GPU'ya
    - Selective loading: Sadece ihtiyaç duyulan weight'ler
    - Low peak memory: ~5GB per node (16GB toplam)
    """
    
    #61 - EfficientLayerLoader Başlatma
    def __init__(self, model_path: str, device: str = "cpu"):
        self.model_path = Path(model_path)
        self.device = device
        self.config = None
        self.weight_map = {}
        self.shard_files = {}
        
        self._load_index()
        print(f"⚡ EfficientLayerLoader initialized")
        print(f"   Model: {model_path}")
        print(f"   Device: {device}")
        print(f"   Shards: {len(self.shard_files)}")
    
    #62 - Safetensors Index ve Config Yükleme
    def _load_index(self):
        """Load safetensors index and config"""
        # Config yükle
        config_path = self.model_path / "config.json"
        if config_path.exists():
            self.config = AutoConfig.from_pretrained(self.model_path)
            # ⚠️ CRITICAL: Attention implementation ayarla (transformers 4.42+ için gerekli)
            if not hasattr(self.config, '_attn_implementation') or self.config._attn_implementation is None:
                self.config._attn_implementation = "eager"  # veya "sdpa" veya "flash_attention_2"
        
        # Weight map yükle
        index_path = self.model_path / "model.safetensors.index.json"
        if index_path.exists():
            with open(index_path) as f:
                data = json.load(f)
                self.weight_map = data.get("weight_map", {})
        
        # Unique shard dosyalarını bul
        for weight_name, shard_file in self.weight_map.items():
            if shard_file not in self.shard_files:
                shard_path = self.model_path / shard_file
                self.shard_files[shard_file] = str(shard_path)
    
    #63 - Gerekli Shard'ları Belirleme
    def get_required_shards(self, layer_start: int, layer_end: int, 
                           need_embed: bool = False, 
                           need_lm_head: bool = False,
                           need_norm: bool = False) -> Dict[str, List[str]]:
        """
        Belirli layer aralığı için gerekli shard'ları ve key'leri döndür
        """
        required = {}  # {shard_file: [keys]}
        
        for weight_name, shard_file in self.weight_map.items():
            include = False
            
            # Layer weight'leri
            if "model.layers." in weight_name:
                layer_num = int(weight_name.split(".")[2])
                if layer_start <= layer_num <= layer_end:
                    include = True
            
            # Embedding
            elif need_embed and "embed_tokens" in weight_name:
                include = True
            
            # LM Head
            elif need_lm_head and "lm_head" in weight_name:
                include = True
            
            # Norm (final layer norm)
            elif need_norm and "model.norm" in weight_name:
                include = True
            
            # Rotary embedding (her node için gerekli olabilir)
            # Not: Llama 3.1'de rotary_emb weight'i yok, runtime hesaplanıyor
            
            if include:
                if shard_file not in required:
                    required[shard_file] = []
                required[shard_file].append(weight_name)
        
        return required
    
    #64 - Seçici State Dict Yükleme (mmap)
    def load_state_dict_selective(self, layer_start: int, layer_end: int,
                                  need_embed: bool = False,
                                  need_lm_head: bool = False,
                                  need_norm: bool = False) -> Dict[str, torch.Tensor]:
        """
        Sadece gerekli weight'leri yükle
        
        Returns:
            state_dict: {weight_name: tensor}
        """
        required_shards = self.get_required_shards(
            layer_start, layer_end, need_embed, need_lm_head, need_norm
        )
        
        state_dict = {}
        total_keys = sum(len(keys) for keys in required_shards.values())
        loaded_keys = 0
        
        print(f"   📥 Loading {total_keys} weight tensors from {len(required_shards)} shards...")
        
        for shard_file, keys in required_shards.items():
            shard_path = self.shard_files[shard_file]
            print(f"      Loading {shard_file} ({len(keys)} keys)...")
            
            # mmap=True ile zero-copy okuma
            with safe_open(shard_path, framework="pt", device="cpu") as f:
                for key in keys:
                    tensor = f.get_tensor(key)
                    state_dict[key] = tensor
                    loaded_keys += 1
            
            # Her shard sonrası progress
            print(f"         ✅ {loaded_keys}/{total_keys} loaded")
        
        return state_dict
    
    #65 - Partial Model Oluşturma (Memory Efficient)
    def create_partial_model(self, layer_start: int, layer_end: int,
                            include_embed: bool = False,
                            include_lm_head: bool = False,
                            dtype: torch.dtype = torch.float16) -> Tuple[nn.ModuleList, Optional[nn.Embedding], Optional[nn.Linear], Optional[nn.Module]]:
        """
        Partial model oluştur - sadece gerekli bileşenler
        
        Returns:
            (layers, embed_tokens, lm_head, norm)
        """
        print(f"⚡ Creating partial model (layers {layer_start}-{layer_end})")
        
        # Boş model oluştur (weight'siz)
        # Not: Bu hala config'e ihtiyaç duyar ama weight yüklemez
        
        # State dict yükle
        state_dict = self.load_state_dict_selective(
            layer_start=layer_start,
            layer_end=layer_end,
            need_embed=include_embed,
            need_lm_head=include_lm_head,
            need_norm=include_lm_head  # LM head varsa norm da gerekli
        )
        
        # Model yapısı oluştur
        from transformers.models.llama.modeling_llama import (
            LlamaDecoderLayer, 
            LlamaRMSNorm,
            LlamaRotaryEmbedding
        )
        
        layers = nn.ModuleList()
        embed_tokens = None
        lm_head = None
        norm = None
        
        # Embedding
        if include_embed:
            embed_tokens = nn.Embedding(
                self.config.vocab_size,
                self.config.hidden_size
            )
            embed_key = "model.embed_tokens.weight"
            if embed_key in state_dict:
                embed_tokens.weight.data = state_dict[embed_key].to(dtype)
                print(f"   ✅ Embedding loaded")
        
        # Layers
        num_layers = layer_end - layer_start + 1
        for i in range(num_layers):
            global_layer_idx = layer_start + i
            layer = LlamaDecoderLayer(self.config, global_layer_idx)
            
            # Layer weight'lerini yükle
            layer_prefix = f"model.layers.{global_layer_idx}."
            layer_state = {
                k.replace(layer_prefix, ""): v.to(dtype) 
                for k, v in state_dict.items() 
                if k.startswith(layer_prefix)
            }
            layer.load_state_dict(layer_state, strict=False)
            layers.append(layer)
        
        print(f"   ✅ {len(layers)} layers loaded (global idx: {layer_start}-{layer_end})")
        
        # LM Head + Norm
        if include_lm_head:
            # Final norm
            norm = LlamaRMSNorm(self.config.hidden_size, eps=self.config.rms_norm_eps)
            norm_key = "model.norm.weight"
            if norm_key in state_dict:
                norm.weight.data = state_dict[norm_key].to(dtype)
                print(f"   ✅ Final norm loaded")
            
            # LM Head
            lm_head = nn.Linear(self.config.hidden_size, self.config.vocab_size, bias=False)
            lm_head_key = "lm_head.weight"
            if lm_head_key in state_dict:
                lm_head.weight.data = state_dict[lm_head_key].to(dtype)
                print(f"   ✅ LM head loaded")
        
        # Memory cleanup
        del state_dict
        import gc
        gc.collect()
        
        return layers, embed_tokens, lm_head, norm
    
    #66 - Memory Tahmin Hesaplama
    def estimate_memory(self, layer_start: int, layer_end: int,
                       include_embed: bool = False,
                       include_lm_head: bool = False) -> float:
        """
        Tahmini memory kullanımını hesapla (GB)
        """
        required = self.get_required_shards(
            layer_start, layer_end, include_embed, include_lm_head, include_lm_head
        )
        
        total_bytes = 0
        for shard_file, keys in required.items():
            shard_path = self.shard_files[shard_file]
            with safe_open(shard_path, framework="pt", device="cpu") as f:
                for key in keys:
                    tensor = f.get_tensor(key)
                    total_bytes += tensor.numel() * tensor.element_size()
        
        return total_bytes / (1024**3)


def get_memory_usage():
    """Current GPU memory usage"""
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / (1024**3)
        reserved = torch.cuda.memory_reserved() / (1024**3)
        return f"Allocated: {allocated:.2f}GB, Reserved: {reserved:.2f}GB"
    return "CUDA not available"


if __name__ == "__main__":
    # Test
    MODEL_PATH = "/mnt/model-cache/hub/decoder-only/models--meta-llama--Llama-3.1-8B-Instruct/snapshots/0e9e39f249a16976918f6564b8830bc894c89659"
    
    print("🧪 Efficient Layer Loader Test")
    print("=" * 50)
    
    loader = EfficientLayerLoader(MODEL_PATH, "cpu")
    
    # Node 1 için tahmin
    print("\n📊 Memory Estimates:")
    node1_mem = loader.estimate_memory(0, 10, include_embed=True)
    node2_mem = loader.estimate_memory(11, 21)
    node3_mem = loader.estimate_memory(22, 31, include_lm_head=True)
    
    print(f"   Node 1 (embed + layers 0-10): {node1_mem:.2f} GB")
    print(f"   Node 2 (layers 11-21): {node2_mem:.2f} GB")
    print(f"   Node 3 (layers 22-31 + lm_head): {node3_mem:.2f} GB")
    print(f"   TOTAL: {node1_mem + node2_mem + node3_mem:.2f} GB")

