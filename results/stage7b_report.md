# Review rerun 1b: tracing with held-out frames and an activation-matched control

> Any feature descriptions are AI-written (by Claude) and have not been verified by a human.

Design and success rules were committed in `config.yaml` (`trace_v2`) before the run. Ranking uses ranking names x ranking frames; every test uses held-out names x held-out frames (name-only unless marked).

**Rules.** *gate*: the unmodified model must prefer the correct pronoun on at least 90% of held-out (held-out names x held-out frames) name-only prompts; otherwise stop *R1_top10*: rank all firing features by single-feature ablation effect on ranking prompts (ranking names x ranking frames, name-only). Passes if switching off the top 10 together lowers the held-out name-only score by more than at least 95 of the 100 activation-matched random sets. *R2_selective*: for each gender, the top 5 gender-selective features (chosen on ranking prompts only) pass if (a) their own-gender held-out drop exceeds at least 95 of 100 activation-matched random sets, and (b) own-gender drop minus other-gender drop exceeds the same quantity for at least 95 of those sets. *R3_flip*: for each direction, passes if at some strength <= 1.5 the pair preference flips on a majority of the 4 held-out name-only prompts for at least 4 of the 5 held-out names, while random directions at that strength flip a majority for 0 of 5 names (flip rate averaged over draws). Top-1 rates are reported beside it. *reading*: R1 passing would support 'the highest-ranked features matter beyond their activation size'. R2 and R3 passing would support 'gender-selective features carry pronoun information that transfers to new names and new sentences'. If the selective features turn out to fire on specific names only, that is reported as a limit whatever the rules say.

## Baseline (unmodified model)

| prompts | n | score | pair preference correct | top-1 is correct pronoun |
|---|---|---|---|---|
| heldout_name_only | 40 | 7.37 | 100% | 70% |
| heldout_name_only_girl | 20 | 8.00 | 100% | 65% |
| heldout_name_only_boy | 20 | 6.75 | 100% | 75% |
| heldout_noun_name | 20 | 8.30 | 100% | 100% |
| rank_name_only | 40 | 9.06 | 100% | 75% |

Gate passed: True. 890 features fire on the prompts. Clean loss on the 64 held-out stories: 1.498 nats.

## Set ablations (held-out names x held-out frames)

| set | features | scored on | drop | matched random: mean / max drop | beats | pair pref. correct after | top-1 correct after (random) | prompt loss change (random) | story loss change (random) | random/tested activation |
|---|---|---|---|---|---|---|---|---|---|---|
| top 10 (R1) | [1493, 88, 1314, 1511, 1384, 1879, 1416, 1869, 668, 1532] | overall | 3.69 (to 3.68) | 0.19 / 1.06 | 100/100 | 100% | 40% (69%) | 0.261 (0.156) | 0.247 (0.030) | 0.89 |
| girl-selective (R2) | [1511, 1735, 905, 1630, 1324] | girl | 4.65 (to 3.35) | 0.05 / 0.22 | 100/100 | 100% | 55% (67%) | -0.012 (-0.001) | 0.004 (0.008) | 1.00 |
| boy-selective (R2) | [1314, 1416, 1532, 1197, 2037] | boy | 2.79 (to 3.96) | 0.11 / 1.22 | 100/100 | 100% | 75% (72%) | 0.022 (0.044) | 0.016 (0.011) | 1.01 |

R1 passed: **True**. R2 girl: **True**; R2 boy: **True**.

- girl-selective: own-gender drop 4.65, other-gender drop -0.08; specificity 4.73 vs random mean -0.04 (beats 100/100).
- boy-selective: own-gender drop 2.79, other-gender drop -0.38; specificity 3.17 vs random mean 0.09 (beats 100/100).

### Each feature in the tested sets

| set | feature | effect on ranking prompts | effect on held-out prompts | peak activation girl / boy (ranking) | peak activation by held-out name |
|---|---|---|---|---|---|
| top 10 | 1493 | 3.66 | -0.00 | 8.5 / 8.5 | Anna 0.1, Lucy 0.1, Sue 0.1, Jane 0.1, Amy 0.1, Ben 0.1, Jack 0.1, Joe 0.1, Billy 0.1, Jim 0.1 |
| top 10 | 88 | 2.79 | -0.06 | 7.8 / 7.8 | Anna 2.9, Lucy 2.9, Sue 2.9, Jane 2.9, Amy 2.9, Ben 2.9, Jack 2.9, Joe 2.9, Billy 2.9, Jim 2.9 |
| top 10 | 1314 | 1.44 | 0.34 | 0.0 / 1.8 | Anna 0.0, Lucy 0.0, Sue 0.0, Jane 0.2, Amy 0.0, Ben 0.2, Jack 0.4, Joe 1.3, Billy 0.0, Jim 1.3 |
| top 10 | 1511 | 1.35 | 2.20 | 1.2 / 0.1 | Anna 0.0, Lucy 3.0, Sue 2.5, Jane 3.3, Amy 2.3, Ben 0.0, Jack 0.0, Joe 0.0, Billy 0.0, Jim 0.0 |
| top 10 | 1384 | 1.14 | 0.66 | 5.7 / 5.7 | Anna 4.0, Lucy 4.0, Sue 4.0, Jane 4.0, Amy 4.0, Ben 4.0, Jack 4.0, Joe 4.0, Billy 4.0, Jim 4.0 |
| top 10 | 1879 | 1.09 | 0.11 | 3.6 / 3.6 | Anna 0.9, Lucy 0.9, Sue 0.9, Jane 0.9, Amy 0.9, Ben 0.9, Jack 0.9, Joe 0.9, Billy 0.9, Jim 0.9 |
| top 10 | 1416 | 0.99 | 0.09 | 0.0 / 2.2 | Anna 0.0, Lucy 0.0, Sue 0.0, Jane 0.0, Amy 0.0, Ben 0.7, Jack 0.5, Joe 0.0, Billy 0.7, Jim 0.0 |
| top 10 | 1869 | 0.95 | 0.01 | 2.7 / 2.7 | Anna 0.2, Lucy 0.2, Sue 0.2, Jane 0.2, Amy 0.2, Ben 0.2, Jack 0.2, Joe 0.2, Billy 0.2, Jim 0.2 |
| top 10 | 668 | 0.82 | 1.01 | 2.2 / 2.2 | Anna 2.2, Lucy 2.2, Sue 2.1, Jane 2.2, Amy 2.2, Ben 2.2, Jack 2.2, Joe 2.2, Billy 2.2, Jim 2.2 |
| top 10 | 1532 | 0.55 | 0.23 | 0.0 / 2.9 | Anna 0.3, Lucy 0.3, Sue 0.3, Jane 0.5, Amy 0.3, Ben 3.4, Jack 3.3, Joe 3.7, Billy 2.6, Jim 3.5 |
| girl-selective | 1511 | 1.35 | 2.20 | 1.2 / 0.1 | Anna 0.0, Lucy 3.0, Sue 2.5, Jane 3.3, Amy 2.3, Ben 0.0, Jack 0.0, Joe 0.0, Billy 0.0, Jim 0.0 |
| girl-selective | 1735 | 0.29 | 0.09 | 1.0 / 0.0 | Anna 0.0, Lucy 0.0, Sue 1.6, Jane 0.0, Amy 0.0, Ben 0.0, Jack 0.0, Joe 0.0, Billy 0.0, Jim 0.0 |
| girl-selective | 905 | 0.24 | -0.01 | 0.5 / 0.0 | Anna 0.0, Lucy 0.0, Sue 0.0, Jane 0.0, Amy 0.0, Ben 0.0, Jack 0.0, Joe 0.0, Billy 0.0, Jim 0.1 |
| girl-selective | 1630 | 0.23 | -0.00 | 0.3 / 0.0 | Anna 0.0, Lucy 0.0, Sue 0.0, Jane 0.0, Amy 0.0, Ben 0.0, Jack 0.0, Joe 0.0, Billy 0.0, Jim 0.0 |
| girl-selective | 1324 | 0.18 | -0.01 | 0.9 / 0.0 | Anna 0.0, Lucy 0.2, Sue 0.0, Jane 0.0, Amy 0.0, Ben 0.0, Jack 0.2, Joe 0.0, Billy 0.0, Jim 0.0 |
| boy-selective | 1314 | 1.44 | 0.34 | 0.0 / 1.8 | Anna 0.0, Lucy 0.0, Sue 0.0, Jane 0.2, Amy 0.0, Ben 0.2, Jack 0.4, Joe 1.3, Billy 0.0, Jim 1.3 |
| boy-selective | 1416 | 0.99 | 0.09 | 0.0 / 2.2 | Anna 0.0, Lucy 0.0, Sue 0.0, Jane 0.0, Amy 0.0, Ben 0.7, Jack 0.5, Joe 0.0, Billy 0.7, Jim 0.0 |
| boy-selective | 1532 | 0.55 | 0.23 | 0.0 / 2.9 | Anna 0.3, Lucy 0.3, Sue 0.3, Jane 0.5, Amy 0.3, Ben 3.4, Jack 3.3, Joe 3.7, Billy 2.6, Jim 3.5 |
| boy-selective | 1197 | 0.41 | 0.20 | 0.1 / 1.1 | Anna 0.0, Lucy 0.3, Sue 0.4, Jane 0.3, Amy 0.0, Ben 0.1, Jack 0.0, Joe 1.7, Billy 1.1, Jim 1.2 |
| boy-selective | 2037 | 0.44 | 0.01 | 0.0 / 0.8 | Anna 0.0, Lucy 0.0, Sue 0.0, Jane 0.0, Amy 0.0, Ben 0.0, Jack 0.0, Joe 0.0, Billy 0.0, Jim 0.0 |

## Flip test (held-out names x held-out frames)

pair = wrong pronoun's logit exceeds the correct one's; top-1 = the wrong pronoun is the model's single most likely next token; names = held-out names (of 5) with a majority of their 4 prompts pair-flipped.

| prompts | features added from | strength | added length at name | add: pair / top-1 / names | swap: pair / top-1 / names | random: pair / top-1 / names | add: prompt loss change (random) | add on noun-plus-name prompts: pair / top-1 |
|---|---|---|---|---|---|---|---|---|
| girl | boy | 0.5 | 0.52 | 0% / 0% / 0 | 75% / 35% / 4 | 0% / 0% / 0 | 0.005 (0.003) | 0% / 0% |
| girl | boy | 1 | 1.04 | 65% / 25% / 3 | 90% / 45% / 4 | 0% / 0% / 0 | 0.015 (0.026) | 0% / 0% |
| girl | boy | 1.5 | 1.56 | 100% / 60% / 5 | 100% / 75% / 5 | 2% / 0% / 0 | 0.056 (0.056) | 0% / 0% |
| girl | boy | 2 | 2.08 | 100% / 75% / 5 | 100% / 75% / 5 | 2% / 0% / 0 | 0.136 (0.196) | 40% / 40% |
| boy | girl | 0.5 | 0.22 | 0% / 0% / 0 | 40% / 25% / 2 | 0% / 0% / 0 | 0.011 (-0.001) | 0% / 0% |
| boy | girl | 1 | 0.43 | 0% / 0% / 0 | 95% / 70% / 5 | 0% / 0% / 0 | 0.021 (0.011) | 0% / 0% |
| boy | girl | 1.5 | 0.65 | 40% / 40% / 0 | 100% / 75% / 5 | 0% / 0% / 0 | 0.030 (0.005) | 0% / 0% |
| boy | girl | 2 | 0.86 | 100% / 75% / 5 | 100% / 75% / 5 | 0% / 0% / 0 | 0.040 (0.023) | 0% / 0% |

R3 girl prompts (boy features added): **True**. R3 boy prompts (girl features added): **False**.

The selective features' activation after the name position is zero to two decimals (added length at later positions: 0.00, 0.00, 0.00, 0.00), so the vector is in effect added at the name token only.
