"""Null corpus generators for statistical significance testing."""

from __future__ import annotations

import random
from collections import Counter


def letter_frequency_shuffle(text: str, seed: int | None = None) -> str:
    """Shuffle all letters in the text, preserving overall frequency distribution.

    This is the simplest null model. It destroys all structure (word boundaries,
    positional patterns) while keeping the same letter counts.
    """
    rng = random.Random(seed)
    letters = list(text)
    rng.shuffle(letters)
    return "".join(letters)


def markov_chain_null(text: str, order: int = 2, seed: int | None = None) -> str:
    """Generate a text of the same length using a character-level Markov chain.

    Preserves local letter-pair (or triple) frequencies, which is a stronger
    null model than simple shuffling — it maintains the natural transition
    probabilities of Hebrew while destroying long-range patterns.
    """
    rng = random.Random(seed)
    if len(text) <= order:
        return text

    # Build transition table
    transitions: dict[str, list[str]] = {}
    for i in range(len(text) - order):
        key = text[i : i + order]
        next_char = text[i + order]
        transitions.setdefault(key, []).append(next_char)

    # Generate
    start_idx = rng.randint(0, len(text) - order - 1)
    result = list(text[start_idx : start_idx + order])

    for _ in range(len(text) - order):
        key = "".join(result[-order:])
        if key in transitions:
            result.append(rng.choice(transitions[key]))
        else:
            # Fallback: random letter from frequency distribution
            result.append(rng.choice(text))

    return "".join(result[: len(text)])


def word_permutation_null(words: list[str], seed: int | None = None) -> list[str]:
    """Permute word order, preserving all words but destroying sequence.

    This is useful for testing roshei/sofei tevot: the same first/last letters
    exist, but their order is randomized.
    """
    rng = random.Random(seed)
    shuffled = words.copy()
    rng.shuffle(shuffled)
    return shuffled
