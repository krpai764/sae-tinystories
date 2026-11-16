import torch

from src.sae import SparseAutoencoder, geometric_median


def test_shapes():
    sae = SparseAutoencoder(d=16, m=128, seed=0)
    x = torch.randn(32, 16)
    x_hat, f = sae(x)
    assert x_hat.shape == (32, 16) and f.shape == (32, 128)
    assert (f >= 0).all()  # ReLU


def test_init_unit_decoder_and_tied_init():
    sae = SparseAutoencoder(d=16, m=128, seed=0)
    assert torch.allclose(sae.W_d.norm(dim=0), torch.ones(128), atol=1e-6)
    assert torch.equal(sae.W_e, sae.W_d.T)
    assert sae.W_e.data_ptr() != sae.W_d.data_ptr()  # untied: separate parameters


def test_decoder_stays_unit_norm_after_steps():
    torch.manual_seed(0)
    sae = SparseAutoencoder(d=16, m=64, seed=0)
    opt = torch.optim.Adam(sae.parameters(), lr=1e-2)
    for _ in range(20):
        x = torch.randn(64, 16)
        loss, _, _ = sae.loss_terms(x, *sae(x), lam=0.1)
        opt.zero_grad()
        loss.backward()
        sae.remove_parallel_decoder_grad()
        opt.step()
        sae.normalize_decoder()
    assert torch.allclose(sae.W_d.norm(dim=0), torch.ones(64), atol=1e-5)


def test_parallel_gradient_removed():
    sae = SparseAutoencoder(d=8, m=32, seed=0)
    x = torch.randn(16, 8)
    sae.loss_terms(x, *sae(x), lam=0.1)[0].backward()
    sae.remove_parallel_decoder_grad()
    assert (sae.W_d.grad * sae.W_d).sum(0).abs().max() < 1e-6


def test_loss_terms_match_definition():
    x = torch.tensor([[1.0, 2.0]])
    x_hat = torch.tensor([[0.0, 0.0]])
    f = torch.tensor([[0.5, 0.0, 1.5]])
    total, recon, sp = SparseAutoencoder.loss_terms(x, x_hat, f, lam=2.0)
    assert recon.item() == 5.0 and sp.item() == 2.0 and total.item() == 9.0


def test_loss_decreases_and_recovers_sparse_toy_features():
    """Toy problem: data = sparse combinations of 32 random unit directions in 16-d."""
    torch.manual_seed(0)
    d, n_true = 16, 32
    true = torch.randn(n_true, d)
    true /= true.norm(dim=1, keepdim=True)

    def batch(n=512):
        coef = torch.rand(n, n_true) * (torch.rand(n, n_true) < 0.05)
        return coef @ true

    sae = SparseAutoencoder(d, 64, seed=1)
    opt = torch.optim.Adam(sae.parameters(), lr=3e-3)
    losses = []
    for _ in range(3000):
        x = batch()
        loss, _, _ = sae.loss_terms(x, *sae(x), lam=0.2)  # 0.02 was too weak: L0 ~15 vs true ~1.6
        opt.zero_grad()
        loss.backward()
        sae.remove_parallel_decoder_grad()
        opt.step()
        sae.normalize_decoder()
        losses.append(loss.item())
    assert sum(losses[-100:]) / 100 < 0.5 * sum(losses[:100]) / 100  # ~3x drop; L1 term sets a floor
    # most true directions should be matched by some decoder column (cos > 0.9)
    cos = (true @ sae.W_d.detach()).max(dim=1).values
    assert (cos > 0.9).float().mean() > 0.9


def test_resample_resets_dead_features():
    torch.manual_seed(0)
    sae = SparseAutoencoder(d=8, m=32, seed=0)
    opt = torch.optim.Adam(sae.parameters(), lr=1e-3)
    x = torch.randn(256, 8)
    sae.loss_terms(x, *sae(x), lam=0.1)[0].backward()
    opt.step()
    sae.normalize_decoder()  # as in the real training loop
    dead = torch.zeros(32, dtype=torch.bool)
    dead[[3, 7]] = True
    k = sae.resample(dead, x, opt, generator=torch.Generator().manual_seed(0))
    assert k == 2
    assert torch.allclose(sae.W_d.norm(dim=0), torch.ones(32), atol=1e-5)
    assert sae.b_e[3] == 0 and sae.b_e[7] == 0
    assert opt.state[sae.W_e]["exp_avg"][3].abs().sum() == 0
    assert opt.state[sae.W_d]["exp_avg_sq"][:, 7].abs().sum() == 0


def test_geometric_median_robust_to_outlier():
    x = torch.cat([torch.zeros(99, 2), torch.tensor([[100.0, 100.0]])])
    gm = geometric_median(x)
    assert gm.norm() < 0.1 and x.mean(0).norm() > 1


def test_enc_init_scale():
    a = SparseAutoencoder(d=16, m=128, seed=0)
    b = SparseAutoencoder(d=16, m=128, seed=0, enc_init_scale=0.25)
    assert torch.allclose(b.W_e, 0.25 * a.W_e) and torch.equal(a.W_d, b.W_d)
