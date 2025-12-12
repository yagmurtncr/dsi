#!/usr/bin/env python3
"""
⚡ D-TEK Performance Configuration

Bu modül sistem genelinde performans optimizasyonlarını sağlar.
"""

import os
import torch

def apply_performance_optimizations():
    """
    Performans optimizasyonlarını uygula
    """
    print("⚡ Performance optimizations applying...")
    
    # 1. cuDNN Benchmark - Daha hızlı conv işlemleri
    if torch.cuda.is_available():
        torch.backends.cudnn.benchmark = True
        torch.backends.cudnn.enabled = True
        print("   ✅ cuDNN benchmark enabled")
    
    # 2. TF32 for faster matrix ops (Ampere+ GPUs)
    if torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        print("   ✅ TF32 enabled (Tensor Float 32)")
    
    # 3. Memory efficient attention (if available)
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    print("   ✅ CUDA memory allocation optimized")
    
    # 4. Disable gradient computation (inference only)
    torch.set_grad_enabled(False)
    print("   ✅ Gradient computation disabled")
    
    # 5. Enable inference mode
    # torch.inference_mode() - bunu context manager olarak kullanmak lazım
    
    print("⚡ Performance optimizations applied!")
    
    return {
        "cudnn_benchmark": torch.backends.cudnn.benchmark if torch.cuda.is_available() else None,
        "tf32_enabled": True if torch.cuda.is_available() else False,
        "grad_enabled": torch.is_grad_enabled()
    }


def get_performance_stats():
    """
    Mevcut performans istatistiklerini döndür
    """
    stats = {
        "pytorch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cudnn_enabled": torch.backends.cudnn.enabled if torch.cuda.is_available() else None,
        "cudnn_benchmark": torch.backends.cudnn.benchmark if torch.cuda.is_available() else None,
    }
    
    if torch.cuda.is_available():
        stats["gpu_count"] = torch.cuda.device_count()
        stats["gpu_names"] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
        
        # Memory stats per GPU
        stats["gpu_memory"] = []
        for i in range(torch.cuda.device_count()):
            mem_allocated = torch.cuda.memory_allocated(i) / (1024**3)
            mem_reserved = torch.cuda.memory_reserved(i) / (1024**3)
            stats["gpu_memory"].append({
                "device": i,
                "allocated_gb": round(mem_allocated, 2),
                "reserved_gb": round(mem_reserved, 2)
            })
    
    return stats


if __name__ == "__main__":
    # Test
    print("🔧 D-TEK Performance Configuration Test")
    print("=" * 50)
    
    # Apply optimizations
    result = apply_performance_optimizations()
    print(f"\nResult: {result}")
    
    # Get stats
    print("\n📊 Performance Stats:")
    stats = get_performance_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")

