# LEARNING NOTES

## Stage 0: Setup

**What it did.** Created the folder layout, an isolated Python environment, a pinned-by-install `requirements.txt`, a `.gitignore` that keeps big files out of version control, and one `config.yaml` holding every setting plus the random seed. It also timed matrix multiplication on the CPU and on the M1's GPU (`mps`).

**Why.** Every later number must be reproducible. A single config and a fixed seed mean a script run next month gives the same answer. The device test matters because SAE training is mostly big matrix multiplies, so the faster device saves hours. The two were close: mps was about 1.3x faster. My first benchmark showed a suspicious 1.006x tie, so I rechecked it with stricter timing (forcing the GPU to finish before stopping the clock) and several matrix shapes before trusting the result.

**Interview questions**
1. *Why fix a random seed and keep settings in one config file?* So experiments are reproducible and any reported number can be traced to the exact settings that produced it.
2. *Why is timing on the GPU trickier than on the CPU?* GPU work is queued asynchronously; if you stop the clock without waiting for the queue to finish you measure launch time, not compute time.
3. *Why benchmark with SAE-shaped matrices rather than just any matrix?* Speed depends on shape and size; the encoder matmul (batch 4096 x width x dictionary) is the workload that will dominate training.
