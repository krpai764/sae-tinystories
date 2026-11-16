import numpy as np
import pytest
import torch

from src.config import load_config
from src.eval import const_replace, keep_pos0, loss_recovered, sae_replace, story_losses
from src.model import load_model
from src.sae import SparseAutoencoder

cfg = load_config()
L = cfg["model"]["layer"]


@pytest.fixture(scope="module")
def mt():
    return load_model(cfg, device="cpu")


@pytest.fixture(scope="module")
def seqs(mt):
    _, tok = mt
    texts = ["Once upon a time there was a cat. The cat liked milk.", "Tom ran to the park.", "A bird sang a song."]
    return [np.asarray([tok.eos_token_id] + tok(t).input_ids, dtype=np.int32) for t in texts]


def test_loss_recovered_formula():
    assert loss_recovered(2.0, 6.0, 2.0) == 1.0
    assert loss_recovered(2.0, 6.0, 6.0) == 0.0
    assert loss_recovered(2.0, 6.0, 4.0) == 0.5


def test_identity_splice_equals_clean(mt, seqs):
    model, tok = mt
    c = story_losses(model, seqs, L, "cpu", None, pad_id=tok.eos_token_id)
    s = story_losses(model, seqs, L, "cpu", lambda h: h, pad_id=tok.eos_token_id)
    assert np.allclose(c[0], s[0], atol=1e-4) and (c[1] == s[1]).all()


def test_counts_are_len_minus_one(mt, seqs):
    model, tok = mt
    _, n = story_losses(model, seqs, L, "cpu", None, pad_id=tok.eos_token_id)
    assert n.tolist() == [len(s) - 1 for s in seqs]


def test_padding_and_batching_do_not_change_loss(mt, seqs):
    model, tok = mt
    a = story_losses(model, seqs, L, "cpu", None, batch_size=1, pad_multiple=1, pad_id=tok.eos_token_id)
    b = story_losses(model, seqs, L, "cpu", None, batch_size=3, pad_multiple=64, pad_id=tok.eos_token_id)
    assert np.allclose(a[0], b[0], atol=1e-3)


def test_zero_ablation_hurts_and_keep_pos0_changes_it(mt, seqs):
    model, tok = mt
    kw = dict(pad_id=tok.eos_token_id)
    clean = story_losses(model, seqs, L, "cpu", None, **kw)[0].sum()
    zero = story_losses(model, seqs, L, "cpu", const_replace(None), **kw)[0].sum()
    zero_k = story_losses(model, seqs, L, "cpu", keep_pos0(const_replace(None)), **kw)[0].sum()
    assert zero > clean + 1 and zero_k > clean + 1 and abs(zero - zero_k) > 1e-3


def test_keep_pos0_leaves_first_position_alone():
    h = torch.randn(2, 5, 8)
    out = keep_pos0(torch.zeros_like)(h)
    assert torch.equal(out[:, 0], h[:, 0]) and out[:, 1:].abs().sum() == 0


def test_sae_replace_undoes_scale():
    """With a perfect-reconstruction stand-in, rescale and un-rescale cancel."""
    class Perfect(torch.nn.Module):
        def forward(self, x):
            return x, None
    h = torch.randn(2, 5, 8)
    assert torch.allclose(sae_replace(Perfect(), 6.36)(h), h, atol=1e-6)
