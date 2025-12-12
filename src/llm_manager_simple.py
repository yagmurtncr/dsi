#!/usr/bin/env python3
"""Simple LLM Manager - CPU Mode (Tek Model)"""

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from typing import Dict, List
import os


class SimpleLLMManager:
    """Basit LLM Manager - CPU modunda tek model"""
    
    def __init__(self, model_path: str, device: str = "cpu"):
        """
        Args:
            model_path: Model path
            device: "cpu" veya "cuda:0"
        """
        self.model_path = model_path
        self.device = device
        self.model = None
        self.tokenizer = None
        self.model_loaded = False
        
        print(f"🤖 Simple LLM Manager başlatılıyor...")
        print(f"   Model: {model_path}")
        print(f"   Device: {device}")
    
    def load_model(self):
        """Model ve tokenizer'ı yükler"""
        if self.model_loaded:
            print("   ⚠️  Model zaten yüklü")
            return
        
        print(f"📥 Model yükleniyor ({self.device})...")
        
        # Tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_path,
            local_files_only=True,
            trust_remote_code=False
        )
        
        # Model (CPU için float32, GPU için float16)
        dtype = torch.float32 if self.device == "cpu" else torch.float16
        
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            local_files_only=True,
            trust_remote_code=False,
            torch_dtype=dtype,
            low_cpu_mem_usage=True
        )
        
        self.model.to(self.device)
        self.model.eval()
        
        self.model_loaded = True
        print(f"✅ Model yüklendi ({dtype})")
    
    def generate(self, prompt: str, max_new_tokens: int = 50, temperature: float = 0.7) -> Dict:
        """
        Text generation
        
        Args:
            prompt: Input text
            max_new_tokens: Max tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Dict with 'generated_text' and 'tokens_generated'
        """
        if not self.model_loaded:
            self.load_model()
        
        # Tokenize
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        input_length = inputs.input_ids.shape[1]
        
        # Generate
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=True,
                top_p=0.9,
                pad_token_id=self.tokenizer.eos_token_id
            )
        
        # Decode (sadece yeni token'lar)
        generated_ids = outputs[0][input_length:]
        generated_text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
        
        return {
            'generated_text': generated_text,
            'tokens_generated': len(generated_ids)
        }


if __name__ == "__main__":
    # Test
    model_path = os.getenv(
        "MODEL_PATH",
        "/mnt/model-cache/hub/decoder-only/models--meta-llama--Llama-3.1-8B-Instruct/snapshots/0e9e39f249a16976918f6564b8830bc894c89659"
    )
    
    manager = SimpleLLMManager(model_path, device="cpu")
    manager.load_model()
    
    result = manager.generate("Hello! How are you?", max_new_tokens=20)
    print(f"\n✅ Generated: {result['generated_text']}")

