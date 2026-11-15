import pytest
import torch

from src.config import load_config
from src.model import generate, get_activations, load_model, residual_hook

cfg = load_config()
LAYER = cfg["model"]["layer"]


@pytest.fixture(scope="module")
def model_tok():
    return load_model(cfg, device="cpu")


@pytest.fixture(scope="module")
def ids(model_tok):
    _, tok = model_tok
    text = "Once upon a time, there was a little girl named Lily. She loved to play."
    return tok(text, return_tensors="pt").input_ids


def test_activation_shape(model_tok, ids):
    model, _ = model_tok
    acts = get_activations(model, ids, LAYER)
    assert acts.shape == (1, ids.shape[1], model.config.hidden_size)
    assert acts.shape[-1] == 256


def test_batched_shape(model_tok):
    model, _ = model_tok
    x = torch.randint(0, 1000, (4, 32))
    assert get_activations(model, x, LAYER).shape == (4, 32, 256)


def test_matches_huggingface_hidden_states(model_tok, ids):
    """Independent check: HF's hidden_states[L+1] is the output of block L."""
    model, _ = model_tok
    with torch.no_grad():
        ref = model(ids, output_hidden_states=True).hidden_states[LAYER + 1]
    assert torch.allclose(get_activations(model, ids, LAYER), ref, atol=1e-6)


def test_capture_hook_does_not_change_output(model_tok, ids):
    model, _ = model_tok
    with torch.no_grad():
        clean = model(ids).logits
        store: list = []
        with residual_hook(model, LAYER, store=store):
            hooked = model(ids).logits
    assert len(store) == 1
    assert torch.equal(clean, hooked)  # bit-for-bit identical


def test_identity_replace_does_not_change_output(model_tok, ids):
    model, _ = model_tok
    with torch.no_grad():
        clean = model(ids).logits
        with residual_hook(model, LAYER, replace=lambda h: h):
            spliced = model(ids).logits
    assert torch.equal(clean, spliced)


def test_zero_replace_does_change_output(model_tok, ids):
    """Proves the replace path really feeds the rest of the model."""
    model, _ = model_tok
    with torch.no_grad():
        clean = model(ids).logits
        with residual_hook(model, LAYER, replace=torch.zeros_like):
            zeroed = model(ids).logits
    assert not torch.allclose(clean, zeroed, atol=1e-3)


def test_hook_is_removed_after_context(model_tok, ids):
    model, _ = model_tok
    with residual_hook(model, LAYER, replace=torch.zeros_like):
        pass
    assert len(model.transformer.h[LAYER]._forward_hooks) == 0


def test_generation_same_with_and_without_hook(model_tok):
    model, tok = model_tok
    p = cfg["generation"]["prompts"][0]
    a = generate(model, tok, p, seed=0, max_new_tokens=20)
    with residual_hook(model, LAYER, store=[]):
        b = generate(model, tok, p, seed=0, max_new_tokens=20)
    assert a == b
