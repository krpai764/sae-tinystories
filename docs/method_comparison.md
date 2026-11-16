# Method comparison: brief vs. the two SAE papers (read before Stage 3, 2026-11-16)

## Citations (checked against the sources)
- Ronen Eldan, Yuanzhi Li. *TinyStories: How Small Can Language Models Be and Still Speak Coherent English?* arXiv:2305.07759, 2023.
- Trenton Bricken, Adly Templeton, Joshua Batson, Brian Chen, Adam Jermyn, Tom Conerly, Nicholas L. Turner, Cem Anil, Carson Denison, Amanda Askell, Robert Lasenby, Yifan Wu, Shauna Kravec, Nicholas Schiefer, Tim Maxwell, Nicholas Joseph, Zac Hatfield-Dodds, Alex Tamkin, Karina Nguyen, Brayden McLean, Josiah E. Burke, Tristan Hume, Shan Carter, Tom Henighan, Chris Olah. *Towards Monosemanticity: Decomposing Language Models With Dictionary Learning.* Transformer Circuits Thread, 4 Oct 2023. (Author list on the page header omits Hatfield-Dodds; the paper's own BibTeX includes him.)
- Hoagy Cunningham, Aidan Ewart, Logan Riggs, Robert Huben, Lee Sharkey. *Sparse Autoencoders Find Highly Interpretable Features in Language Models.* arXiv:2309.08600, 2023.

## Differences

| Topic | Brief | Bricken et al. | Cunningham et al. | Decision for this project |
|---|---|---|---|---|
| Site | residual stream | MLP activations (1-layer model, 512 neurons) | mainly residual stream (Pythia-70M/410M) | residual stream (as brief; closest to Cunningham) |
| Weights | untied; W_e initialised as W_dᵀ | untied, default PyTorch Kaiming-uniform init | **tied** (encoder M, decoder Mᵀ) | untied (Bricken), with brief's W_e = W_dᵀ init |
| Biases | b_e, b_d, pre-encoder subtract b_d | same (pre-encoder bias tied to −b_d) | encoder bias only, no decoder bias | as brief / Bricken |
| b_d init | mean of data | **geometric median** | n/a | geometric median (Bricken). Cheap to compute; report how far it is from the mean |
| Loss | mean over batch of ‖x−x̂‖² + λ‖f‖₁ | formula shows ‖x−x̂‖²; text says MSE is a mean over vector elements (ambiguous, factor of d) | ‖x−x̂‖² + α‖c‖₁ | squared L2 summed over dims, averaged over batch (brief + Cunningham + Bricken's formula). λ values not comparable with Bricken's text definition |
| Decoder norm | rescale columns to 1 after each step | also **remove gradient component parallel to each column before the step** ("small but real" loss reduction), then renormalise | rows normalised | do both (Bricken) |
| Input scaling | rescale so mean ‖x‖ = √d | not in this paper | not in this paper | keep (harmless global constant; from later practice, not these papers) |
| Optimiser / LR | Adam, 3e-4 | Adam; lower LR + more steps better; annealing did not help | Adam, 1e-3 | Adam 3e-4, no annealing |
| Batch / data | 4096; shuffle across dataset | 8192; 8 B vectors, 1 M steps, **sampling without replacement matters**; repeated epochs increase dead features | 5–50 M vectors, 1–3 epochs | 2.5 M vectors only, so we must repeat epochs. Biggest deviation; watch dead features |
| Dictionary size | 8× | 1×–256× (A/1 = 8×) | R mostly ≤ 8 | 8× = 2048 |
| Sparsity target | L0 10–100 | "generally target L0 < 10 or 20"; distrust L0 that is a large fraction of d | smooth trade-off, no knee | aim L0 ≈ 5–60 (100 would be 40% of d=256) |
| Dead features | resample if >~10% dead in last several thousand batches | resample at steps 25k/50k/75k/100k neurons dead for 12,500 steps; pick inputs ∝ squared loss on 819,200 samples; decoder = unit-norm input; encoder = input × 0.2 × mean alive encoder norm; b_e = 0; reset Adam state | no resampling | Bricken's procedure, scaled to our run length (see below) |
| Metrics | VE, L0, dead fraction, curves | also **ultralow-density** features (< 1e-6) and density histograms | VE vs L0 | add density histogram; 1e-6 is below what 2.5 M tokens can resolve, so use a higher threshold and say so |
| Loss recovered baseline | zero-ablation | zero-ablation, but warn it is a weak baseline that overestimates | perplexity with reconstruction | zero-ablation (brief) **plus mean-ablation** as a stricter baseline |
| Random-model control | randomly initialised copy | **shuffle entries of each trained weight matrix** (keeps weight statistics) | — | shuffled-weights (Bricken); optionally also fresh init |
