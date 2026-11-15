"""Time matmuls on CPU and mps (a stand-in for SAE training cost)."""
from __future__ import annotations

import time

import torch


def time_matmul(device: str, m: int, k: int, n: int, repeats: int = 20) -> float:
    """Mean seconds for one (m,k)@(k,n) float32 matmul on `device`.

    The final .item() forces all queued work to finish on both devices, so the
    timing is honest even though mps runs asynchronously.
    """
    a = torch.randn(m, k, device=device)
    b = torch.randn(k, n, device=device)
    for _ in range(5):  # warm-up
        (a @ b).sum().item()
    start = time.perf_counter()
    for _ in range(repeats):
        c = a @ b
    c.sum().item()
    return (time.perf_counter() - start) / repeats


def time_device(device: str, n: int = 2048, repeats: int = 20) -> float:
    """Convenience: square n x n matmul."""
    return time_matmul(device, n, n, n, repeats)
