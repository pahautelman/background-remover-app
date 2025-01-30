import torch

torch.cuda.empty_cache()  # Frees up the GPU memory cache
torch.cuda.memory_summary(device=None, abbreviated=False)  # Optional, for a summary
torch.cuda.synchronize()  # Optional, ensures all streams are done