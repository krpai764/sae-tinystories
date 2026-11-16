import torch

from src.sae import SparseAutoencoder
from src.trace import ablate_features, add_vector, reconstruct_only


def _setup():
    torch.manual_seed(0)
    sae = SparseAutoencoder(16, 64, seed=1)
    with torch.no_grad():
        sae.b_e.add_(0.3)  # make plenty of features fire
    return sae, torch.randn(2, 5, 16), 2.0


def test_ablate_nothing_is_identity():
    sae, h, c = _setup()
    assert torch.allclose(ablate_features(sae, c, [])(h), h, atol=1e-5)


def test_ablate_removes_exactly_one_feature_contribution():
    sae, h, c = _setup()
    f = sae.encode(h * c)
    j = int(f[:, 1:].sum((0, 1)).argmax())
    out = ablate_features(sae, c, [j])(h)
    expect = h - f[..., j:j + 1] * sae.W_d[:, j] / c
    assert torch.allclose(out[:, 1:], expect[:, 1:], atol=1e-5)
    assert torch.equal(out[:, 0], h[:, 0])  # EOS position untouched
    assert sae.encode(out * c)[:, 1:, j].sum() < f[:, 1:, j].sum()


def test_reconstruct_only_and_add_vector():
    sae, h, c = _setup()
    r = reconstruct_only(sae, c)(h)
    assert torch.allclose(r[:, 1:], sae(h[:, 1:] * c)[0] / c, atol=1e-6) and torch.equal(r[:, 0], h[:, 0])
    v = torch.ones(5, 16)
    assert torch.allclose(add_vector(v)(h), h + 1)
