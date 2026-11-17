# Project brief: Sparse autoencoders on a small story-writing language model

You are helping me build a portfolio project in mechanistic interpretability. I am a student working alone. Read this whole brief before doing anything, then start at Stage 0.

## Goal

Find the individual concepts ("features") that a small pretrained language model uses internally, by training sparse autoencoders on its internal activations. Then show the features are real by steering the model with them, and trace one behaviour back to the features that cause it.

This follows published methods. It is a careful application with honest measurements, not new research. Say so in the README and cite the prior work.

## My constraints

- Machine: MacBook Air M1, no fan, no dedicated GPU. Use PyTorch on CPU or the "mps" device. Time both once on a small test and keep the faster one.
- No paid APIs or cloud services. Everything runs locally.
- Ask me before any download larger than 1 GB, and keep saved activations under about 3 GB on disk.
- Long runs: save checkpoints so they can resume, and tell me to start them with `caffeinate -i` so the Mac does not sleep.
- I want to understand everything, so explain as you go (see "Working rules").

## Stack

Python 3.11 or later, PyTorch, Hugging Face `transformers` and `datasets`, NumPy, pandas, matplotlib, pytest. Capture activations with plain PyTorch forward hooks. Write the sparse autoencoder yourself; do not use an interpretability library for it.

## Model and data

- Model: one of the public TinyStories models on Hugging Face (the `roneneldan/TinyStories-*` family). Check which model IDs exist before choosing. Prefer one with several layers and an internal width of a few hundred, small enough to run comfortably on this laptop. Tell me which you chose and why.
- Text: the public TinyStories dataset. Keep a held-out split that is never used for training the autoencoder.

## Stages

Stop after every stage, show me the results, and wait for me to say continue.

**Stage 0. Setup.** Create the repository layout (`src/`, `tests/`, `scripts/`, `results/`, `figures/`), a virtual environment, `requirements.txt`, a `.gitignore` that excludes data and checkpoints, and a config file holding every setting and the random seed.
*Check:* `pytest` runs and a device test reports CPU and mps speed.

**Stage 1. Load the model.** Load it, generate three short stories from fixed prompts, and add a hook that returns the residual-stream activations at one middle layer.
*Check:* stories are readable; a test confirms the hooked activations have the expected shape and that the hook does not change the model's output.

**Stage 2. Collect activations.** Run the model over roughly 2 to 5 million tokens and save the activations at the chosen layer to disk in a memory-mapped file, with the matching token IDs so any activation can be traced back to its text.
*Check:* report file size, the mean and spread of activation norms, and a test that a saved row matches a freshly computed one.

**Stage 3. Train the sparse autoencoder.** Implement it from scratch: an encoder with a ReLU, a decoder with unit-norm columns, a dictionary about 8 times wider than the model's internal width, and a loss of reconstruction error plus an L1 sparsity penalty. Train about four versions with different sparsity penalties.
*Report for each:* fraction of variance explained, average number of active features per token, fraction of features that never fire, and training curves.

**Stage 4. Check faithfulness.** Replace the model's real activations with the autoencoder's reconstruction and measure the model's next-token loss on held-out text. Compare three cases: clean model, reconstruction spliced in, and the layer zeroed out. Report the share of loss recovered.
*Check:* choose one autoencoder to carry forward and justify the choice from Stages 3 and 4 in a short table.

**Stage 5. Interpret features.** For 200 randomly chosen live features, save the 20 text snippets where each fires most strongly, with the firing token marked. Also save a few random-strength examples per feature, not only the top ones. Create a labels file for me to fill in by hand; propose a label for each, marked as a suggestion.
*Report:* the share of features that look like one clear concept, the share that are unclear, and examples of both. Do not present only the good ones.

**Stage 6. Steering.** Pick 5 to 8 clearly labelled features. During generation, add a multiple of each feature's decoder direction to the activations at that layer, using fixed prompts and seeds. Include a control: a random direction with the same size.
*Report:* side-by-side text for no steering, feature steering at three strengths, and the random control. Include the cases where steering fails or breaks the text.

**Stage 7. Trace one behaviour (time-boxed).** Pick one simple, measurable behaviour, such as choosing "he" or "she" after a named character. Build a small test set, define a numeric score (for example the difference between the two words' scores), then switch features off one at a time and rank them by effect. Compare against switching off random features.
*Limit:* at most two working sessions. If it does not give a clear answer by then, write up what was tried and what was seen, and move on.

**Stage 8. Feature browser and report.** Generate a single static HTML page from the saved results, where a reader can pick a feature and see its label, top snippets and steering examples. Write `README.md` (what this is, how to run it, the headline numbers) and `REPORT.md` (method, results, failures, limits, prior work).

## Definition of done

- At least 20 features with documented meanings and evidence.
- At least 5 steering demonstrations with controls.
- Faithfulness numbers from Stage 4.
- Stage 7 either completed or honestly written up as unsuccessful.
- The browser page, README and REPORT.
- Every figure and number can be regenerated by a script in `scripts/`.

## Working rules

1. Never invent or estimate a result. Every number in the README and REPORT must come from a file in `results/` produced by a script.
2. Keep `PROGRESS.md` updated after each stage: what is done, what is next, key decisions and where results live. A new session on a different model must be able to continue from it.
3. Keep `LEARNING_NOTES.md`: after each stage, add a plain-language explanation of what the stage did, why, and three questions an interviewer might ask me about it with short answers.
4. Fix random seeds and record them. Use small, fast settings first to check the code works, then scale up.
5. Write tests for the autoencoder (shapes, decoder normalisation, loss decreasing on a toy problem) and for the hooks.
6. When a result looks surprising or too good, check for a bug before reporting it.
7. Suggest a git commit after each stage, and wait for me to approve it.
8. Prior work to cite, after checking the exact titles and authors: the TinyStories paper (Eldan and Li, 2023), "Towards Monosemanticity" (Bricken et al., 2023), and "Sparse Autoencoders Find Highly Interpretable Features in Language Models" (Cunningham et al., 2023).

## Method notes

These are starting points from my understanding of the published methods, not verified settings. Read the two sparse autoencoder papers before Stage 3, follow them where they differ, and tell me what differed.

**Autoencoder (Stage 3).**
- Encode: f = ReLU(W_e·(x − b_d) + b_e). Decode: x̂ = W_d·f + b_d. Here x is the model's activation vector at one token, x̂ is its reconstruction, f is the vector of feature strengths, W_e and b_e are the encoder weights and bias, and W_d and b_d are the decoder weights and bias.
- Loss = mean of ‖x − x̂‖² + λ·‖f‖₁, where ‖x − x̂‖² is the squared reconstruction error, ‖f‖₁ is the sum of feature strengths, and λ is the sparsity penalty.
- Before training, rescale all activations by one constant so their average length is the square root of the model's internal width. This makes λ values comparable across layers.
- Start b_d at the mean activation. Start W_d with random unit-length columns and W_e as its transpose.
- After every optimiser step, rescale each decoder column back to length 1.
- Shuffle activations across the whole dataset, so a batch never comes from one story.
- Starting settings: Adam, learning rate around 0.0003, batch size 4096, λ swept over four values spaced by a factor of about 3. Run a short trial first to find the range of λ that gives between roughly 10 and 100 active features per token.
- Dead features: count features that have not fired in the last several thousand batches. If more than about a tenth are dead, re-initialise them toward inputs the autoencoder reconstructs badly, and report that you did.

**Faithfulness (Stage 4).** Loss recovered = (L_zero − L_spliced) / (L_zero − L_clean), where L_clean is the model's next-token loss untouched, L_spliced is its loss with the reconstruction put in place of the real activations, and L_zero is its loss with that layer's activations set to zero. A value near 1 means the reconstruction preserves what the model needs. Remember to undo the rescaling before splicing back in.

**Choosing one autoencoder.** Prefer the one with high loss recovered and few dead features at a low count of active features per token. Show the trade-off as a table and a chart; there is no single correct answer, so explain the choice.

**Interpreting (Stage 5).** For each feature, also record how often it fires and which output words its decoder direction makes more likely (project the direction through the model's output layer). A feature whose top examples and promoted words tell the same story is more believable.

**Steering (Stage 6).** Scale steering strength relative to the typical activation length at that layer, for example 2, 5 and 10 times the feature's usual firing strength. Very large values will break the text; show where that starts.

**Tracing (Stage 7).** Score = (model's score for the correct word) − (score for the wrong word), averaged over the test set. For each feature, set its strength to zero, decode, splice back in while keeping the autoencoder's reconstruction error added on, and record the change in score. Rank features by that change and compare the top ones against the same number of randomly chosen features.

**Sanity checks.** Train one autoencoder on activations from a randomly initialised copy of the model. Its features should be much less interpretable; if they look just as good, the interpretation method is fooling us.
