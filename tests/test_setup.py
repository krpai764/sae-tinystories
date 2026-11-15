import torch

from src.config import get_device, load_config, set_seed
from src.device_bench import time_device


def test_config_has_required_keys():
    cfg = load_config()
    for k in ["seed", "paths", "device", "model", "data", "sae", "generation"]:
        assert k in cfg
    assert isinstance(cfg["seed"], int)
    assert cfg["sae"]["expansion"] == 8


def test_seed_is_repeatable():
    set_seed(1)
    a = torch.randn(3)
    set_seed(1)
    b = torch.randn(3)
    assert torch.equal(a, b)


def test_get_device_valid():
    assert get_device() in ("cpu", "mps")


def test_device_timing_reports_cpu_and_mps():
    t_cpu = time_device("cpu", n=256, repeats=3)
    assert t_cpu > 0
    if torch.backends.mps.is_available():
        assert time_device("mps", n=256, repeats=3) > 0
