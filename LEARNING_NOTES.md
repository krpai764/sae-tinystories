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

## Stage 2: Collect activations

**What it did.** Ran the model over about 2.5 million tokens of TinyStories (12,747 stories) and saved the 256-number residual-stream vector at layer 3 for every token into one big memory-mapped file, alongside the token IDs, story index and position. Did the same for 200k tokens of held-out stories that the autoencoder will never train on.

**Why.** The autoencoder is trained on these vectors, not on text. Saving them once is far cheaper than re-running the model every epoch. A memory-mapped file lets us read a slice from disk without loading all 2.6 GB into the laptop's 8.6 GB of RAM. Keeping the token ID for each row means that when a feature fires strongly, we can look up the exact word and story. Each story starts with an end-of-text token, which always produces the same vector; I will leave it out of training because it carries no information. Two things went wrong and were fixed: the first run crashed from GPU memory growth because every batch had a different length (fixed by padding to a few standard lengths), and the held-out set contained 3 stories identical to training stories (TinyStories has duplicates), so I excluded them.

**Interview questions**
1. *Why keep a held-out split, and how did you check it was really held out?* To measure the autoencoder on text it never saw. I checked for exact story overlap by comparing token sequences and found 3 duplicates in the dataset, then excluded them.
2. *How do you know the saved activations are correct?* A test recomputes random stories one at a time on the CPU and compares to the saved rows (max difference about 2e-6), which also shows padding in batches does not change real tokens thanks to causal attention.
3. *Why did the first collection run crash, and how did you diagnose it?* The Apple GPU backend kept memory per distinct input shape, and sorted-by-length batches had almost every length once. I reproduced it in a small benchmark, saw driver memory climb from 2.8 to 7 GB, then bucketed lengths and confirmed memory stayed flat.

## Stage 3: Train the sparse autoencoders

**What it did.** Built a sparse autoencoder from scratch: it turns each 256-number activation into 2048 non-negative "feature strengths", most of them zero, then rebuilds the activation as a weighted sum of 2048 unit-length directions. Trained four versions with different sparsity penalties (λ = 0.5, 1, 2, 4) for 20 passes over 2.5M tokens.

**Why.** λ trades accuracy for sparsity: bigger λ means fewer active features per token (easier to interpret) but worse reconstruction. Variance explained fell from 0.93 to 0.78 as active features per token fell from 88 to 5.5. Features that stop firing ("dead") waste capacity; at λ = 4 almost a quarter died by epoch 4, so they were re-initialised toward inputs the autoencoder reconstructed worst (Bricken et al.'s resampling).

**Interview questions**
1. *Why constrain decoder columns to unit length?* Otherwise the model can shrink feature strengths and grow the directions, cutting the L1 penalty without becoming sparser.
2. *What is a dead feature and why resample it?* One that never fires; it contributes nothing. Resampling points it at badly reconstructed inputs so it can learn something useful.
3. *How did you pick λ?* A short pilot over a wide grid found the usable range (λ ≥ 10 collapsed, λ = 0.3 was dense), then four values spaced 2x within it.

## Stage 4: Faithfulness

**What it did.** Took the held-out stories, ran the model normally to get its next-word loss, then ran it again with the layer-3 activations replaced by (a) the autoencoder's reconstruction, (b) all zeros and (c) the average activation. "Loss recovered" = how much of the damage from wiping the layer (b or c) the reconstruction undoes.

**Why.** Variance explained says the reconstruction is numerically close, but not whether it keeps what the model *uses*. Loss recovered tests that directly. Zeroing is a weak baseline (the activations have a large constant component), so I also report mean-replacement, which is stricter. Even the most faithful autoencoder raises loss by 0.30 nats, so a "96% recovered" headline understates how much the model still loses.

**Interview questions**
1. *What does loss recovered measure that variance explained does not?* Whether the information the model actually relies on survives, via the downstream loss, not just raw reconstruction error.
2. *Why two baselines?* Zero-ablation is easy to beat; mean-ablation removes only the token-specific part, so it gives a more honest, lower number.
3. *Why leave position 0 untouched in the main numbers?* The autoencoder never trained on that constant start-of-story vector; I also report replacing it, and the conclusions don't change.

## Stage 5: Interpret features

**What it did.** Took 200 random features from the chosen autoencoder and, for each, collected the 20 text snippets where it fires most strongly, 5 random firings, and the output words its direction promotes. Wrote a label for each (all labels are AI-written, not human-checked). Then tested the labels blind: a fresh AI that never saw the evidence got only the label and had to pick the 5 real firing snippets out of 10. Did the same for an autoencoder trained on a copy of the model with its weights shuffled.

**Why.** Top examples are seductive: even the shuffled model's features looked clean at the top (41/50 seemed clear). The blind test with random (often weak) firings is a fairer check: real labels scored 0.78 versus 0.56 for the control (chance 0.50), and only 37/200 real features passed the strict "random firings fit too" rule.

**Interview questions**
1. *Why train an SAE on a model with shuffled weights?* As a control: if its features looked just as interpretable, our method would be finding patterns in the text or the method itself, not in the model.
2. *Why sample firings uniformly rather than using the top ones in the blind test?* Top firings are the easiest cases; most firings are weaker, and a label should explain typical behaviour too. Detection fell from 0.94 for strong to 0.64 for weak firings.
3. *What is the main weakness of this evaluation?* Labels were written and scored by AI models of the same family with no human check, and the non-firing distractors were random tokens, which makes the test easier than it could be.

## Stage 6: Steering

**What it did.** While the model wrote a story, added a multiple of one feature's direction to its internal activations at layer 3, and compared the text with no steering and with a random direction of the same length. Six features came from the ones that were both clear and 5/5 in the blind test; two were deliberately weak-label features.

**Why.** If a feature really means something to the model, pushing on it should change the text in the matching way. The random control shows how much change you get just from disturbing the activations at all.

**What happened.** At half a feature's usual strong firing the text stayed fluent and only drifted; at one times most stayed fluent. At two times, every chosen feature broke the text into repeats of the word the feature predicts next ("girl girl girl", "scary monster", "so so sad"). The random directions also broke the text at that size, but into unrelated words. One weak-label feature ("sunshine") steered the most gracefully.

**Interview questions**
1. *Why compare with a random direction of the same size?* Any big push breaks a small model; the control separates "the feature did something specific" from "we disturbed the activations".
2. *Why did steering produce repeated next words rather than whole themes?* Many of these features fire on one token and predict the next; amplifying them hard pushes the model to emit that prediction over and over. Themes would need gentler pushes or more abstract features.
3. *Why scale by the feature's own firing strength?* It puts features on a common footing; a fixed absolute size would be gentle for some and huge for others. Even so, 2x was already as long as a typical activation here, so the brief's 2/5/10x was too strong.
