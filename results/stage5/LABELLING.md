# How to label (Stage 5)

1. Open `batch_1.md`. Each feature shows its firing frequency, top 20 snippets (firing token in [[brackets]]), 5 random firings and the output tokens its decoder direction promotes.
2. In `labels.csv`, fill `your_label`, `your_verdict` (`clear`, `unclear`, or `dead-or-junk`) and optionally `your_notes`.
3. The `(SUGGESTION)` columns are Claude's guesses from the same evidence. Treat them as a second opinion, not ground truth. They're based mostly on the top examples, so they lean optimistic.
4. A feature counts as **clear** only if one concept explains the top examples *and* the random firings are mostly consistent with it. The Stage 5 report counts verdicts from your columns, not the suggestions.
5. Rerunning `scripts/stage5_write_labels.py` refreshes the suggestion columns and never overwrites your columns.
