# LEARNING NOTES

## Stage 0: Setup

**What it did.** Created the folder layout, an isolated Python environment, a pinned-by-install `requirements.txt`, a `.gitignore` that keeps big files out of version control, and one `config.yaml` holding every setting plus the random seed. It also timed matrix multiplication on the CPU and on the M1's GPU (`mps`).

**Why.** Every later number must be reproducible. A single config and a fixed seed mean a script run next month gives the same answer. The device test matters because SAE training is mostly big matrix multiplies, so the faster device saves hours. The two were close: mps was about 1.3x faster. My first benchmark showed a suspicious 1.006x tie, so I rechecked it with stricter timing (forcing the GPU to finish before stopping the clock) and several matrix shapes before trusting the result.

**Interview questions**
1. *Why fix a random seed and keep settings in one config file?* So experiments are reproducible and any reported number can be traced to the exact settings that produced it.
2. *Why is timing on the GPU trickier than on the CPU?* GPU work is queued asynchronously; if you stop the clock without waiting for the queue to finish you measure launch time, not compute time.
3. *Why benchmark with SAE-shaped matrices rather than just any matrix?* Speed depends on shape and size; the encoder matmul (batch 4096 x width x dictionary) is the workload that will dominate training.

## Stage 1: Load the model

**What it did.** Chose and loaded TinyStories-8M, a 19.7M-parameter GPT-style model with 8 transformer blocks and a 256-number "width". Generated three short stories from fixed prompts and seeds. Added a forward hook: a function PyTorch calls with a layer's output as the model runs. Mine reads, and optionally replaces, the *residual stream* after block 3.

**Why.** The residual stream is the running vector (256 numbers per token) that every block reads from and adds to. It is where the model's intermediate "thoughts" live, so it is what the sparse autoencoder will decompose. Hooking the same spot lets us later *write back* modified activations (reconstruction, ablation, steering). I picked the 8M model because its width keeps saved activations under the 3 GB disk cap, while it still has several layers. The hook's tests matter: a capture hook must not change the model's logits at all (checked bit-for-bit), and a replace hook must really feed the rest of the model (zeroing it changes the output). I also checked my captured activations against Hugging Face's own `hidden_states`.

**Interview questions**
1. *What is the residual stream, and why decompose it rather than a single MLP layer?* It is the sum of the embedding and every block's contributions, passed along the whole network, so it carries everything the model has computed so far. Features read from it can be used by all later layers.
2. *How do you know your hook does not disturb the model?* A test compares logits with and without the hook for exact equality, and a second test shows that the replace path does change output when we zero the activations, proving the splice is really live.
3. *Why a middle layer?* Early layers mostly hold token identity and late layers mostly encode next-token predictions; middle layers tend to hold richer abstract features, and there are still layers after it, so we can test splicing and steering effects.
