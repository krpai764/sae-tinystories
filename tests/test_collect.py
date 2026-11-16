import json

import numpy as np
import pytest
import torch

from src.collect import collect, load_split
from src.config import ROOT, load_config
from src.data import flatten, tokenize_story
from src.model import get_activations, load_model

cfg = load_config()
LAYER = cfg["model"]["layer"]
TEXTS = [
    "Once upon a time there was a cat. The cat liked milk.",
    "Tom ran to the park. He played all day and then went home to sleep.",
    "A bird sang.",
    "Mia had a red ball. She threw it high. It did not come down. Mia was sad, but then her dad found it in a tree.",
]


@pytest.fixture(scope="module")
def model_tok():
    return load_model(cfg, device="cpu")


def test_tokenize_story_eos_prefix_and_truncation(model_tok):
    _, tok = model_tok
    s = tokenize_story("Hello there. " * 100, tok, max_len=16)
    assert s[0] == tok.eos_token_id and len(s) == 16 and s.dtype == np.int32
    short = tokenize_story("  A bird sang. ", tok, max_len=256)
    assert short[0] == tok.eos_token_id and len(short) == 1 + len(tok("A bird sang.").input_ids)


def test_flatten_indices():
    seqs = [np.array([5, 6, 7], dtype=np.int32), np.array([8, 9], dtype=np.int32)]
    tokens, story, pos, offsets = flatten(seqs)
    assert tokens.tolist() == [5, 6, 7, 8, 9]
    assert story.tolist() == [0, 0, 0, 1, 1]
    assert pos.tolist() == [0, 1, 2, 0, 1]
    assert offsets.tolist() == [0, 3, 5]


def test_collect_rows_match_fresh_and_resume(model_tok, tmp_path):
    model, tok = model_tok
    seqs = sorted([tokenize_story(t, tok, 256) for t in TEXTS], key=len)
    info = collect(model, seqs, tmp_path, "t", LAYER, "cpu", batch_size=2, checkpoint_every=1,
                   pad_id=tok.eos_token_id, log=lambda *_: None)
    assert info["num_tokens"] == sum(len(s) for s in seqs)
    acts, tokens, story, pos, offsets = load_split(tmp_path, "t")
    assert acts.shape == (len(tokens), 256)
    # the saved row for token i equals a freshly computed one (padded batching must not matter)
    for sid, s in enumerate(seqs):
        fresh = get_activations(model, torch.from_numpy(s.astype(np.int64))[None], LAYER)[0].numpy()
        saved = np.asarray(acts[offsets[sid]:offsets[sid + 1]])
        assert np.allclose(saved, fresh, atol=1e-5)
        assert (tokens[offsets[sid]:offsets[sid + 1]] == s).all()

    # resume: pretend only the first batch finished, wipe the rest, rerun -> identical
    before = np.asarray(acts).copy()
    (tmp_path / "t_progress.json").write_text(json.dumps({"stories_done": 2}))
    mm = np.load(tmp_path / "t_acts.npy", mmap_mode="r+")
    mm[offsets[2]:] = 0
    mm.flush()
    del mm
    collect(model, seqs, tmp_path, "t", LAYER, "cpu", batch_size=2, checkpoint_every=1,
            pad_id=tok.eos_token_id, log=lambda *_: None)
    assert np.allclose(np.load(tmp_path / "t_acts.npy"), before, atol=1e-6)


@pytest.mark.skipif(not (ROOT / "data" / "train_acts.npy").exists(), reason="Stage 2 data not collected")
def test_real_saved_row_matches_fresh_and_is_traceable(model_tok):
    model, tok = model_tok
    acts, tokens, story, pos, offsets = load_split(ROOT / "data", "train")
    rng = np.random.default_rng(0)
    for sid in rng.choice(len(offsets) - 1, 5, replace=False):
        a, b = offsets[sid], offsets[sid + 1]
        fresh = get_activations(model, torch.from_numpy(tokens[a:b].astype(np.int64))[None], LAYER)[0].numpy()
        assert np.abs(fresh - np.asarray(acts[a:b])).max() <= cfg["data"]["tolerance_atol"]
        assert tokens[a] == tok.eos_token_id and pos[a] == 0 and (story[a:b] == sid).all()
        assert len(tok.decode(tokens[a:b])) > 0  # any activation can be traced back to text
    assert np.isfinite(np.asarray(acts[:100000])).all()
