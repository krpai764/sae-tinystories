"""Text -> token sequences. One story per sequence, EOS-prefixed, truncated.

The same preprocessing must be used everywhere (activation collection, Stage 4
loss evaluation, Stage 7 test sets), so it lives here.
"""
from __future__ import annotations

import numpy as np

from src.config import ROOT


def tokenize_story(text: str, tok, max_len: int) -> np.ndarray:
    """EOS + story tokens, truncated to max_len. int32 array.

    The model saw <|endoftext|> between stories in training, so position 0 is
    always EOS (a stable 'start of story' marker).
    """
    ids = tok(text.strip(), add_special_tokens=False).input_ids
    return np.asarray([tok.eos_token_id] + ids[: max_len - 1], dtype=np.int32)


def load_parquet_texts(rel_path: str, cache_dir) -> list[str]:
    """Download (once) and read one TinyStories parquet shard; returns all texts."""
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download

    path = hf_hub_download("roneneldan/TinyStories", rel_path, repo_type="dataset",
                           cache_dir=cache_dir)
    return pq.read_table(path, columns=["text"]).column("text").to_pylist()


def select_stories(texts: list[str], tok, max_len: int, token_budget: int, seed: int,
                   chunk: int = 1024, exclude: set | None = None) -> list[np.ndarray]:
    """Randomly sample stories (seeded) until adding another would exceed token_budget.

    Returned in length-bucketed order (sorted by length inside chunks of `chunk`
    stories) so batches need little padding. Order is deterministic given seed.
    `exclude`: set of story token-sequence byte strings to skip (used to keep the
    held-out split free of stories that also appear in the training sample).
    """
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(texts))
    seqs, total = [], 0
    for i in order:
        s = tokenize_story(texts[i], tok, max_len)
        if exclude is not None and s.tobytes() in exclude:
            continue
        if total + len(s) > token_budget:
            break
        seqs.append(s)
        total += len(s)
    out = []
    for a in range(0, len(seqs), chunk):
        out.extend(sorted(seqs[a:a + chunk], key=len))
    return out


def flatten(seqs: list[np.ndarray]):
    """Flat token ids, story index per token, position per token, story offsets."""
    lens = np.array([len(s) for s in seqs], dtype=np.int64)
    offsets = np.concatenate([[0], np.cumsum(lens)])
    tokens = np.concatenate(seqs).astype(np.int32)
    story = np.repeat(np.arange(len(seqs), dtype=np.int32), lens)
    pos = (np.arange(len(tokens)) - offsets[story]).astype(np.int16)
    return tokens, story, pos, offsets
