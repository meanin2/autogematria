# Hebrew Normalization Specification

All Hebrew text in AutoGematria passes through a canonical normalization pipeline
before storage or search. This document defines every rule.

## Source Text

Primary source: Sefaria "Tanach with Text Only" — consonantal Hebrew, no nikkud,
no taamim. However, user input and other sources may contain diacritics, so the
pipeline handles them defensively.

## Normalization Steps (in execution order)

### 1. Strip Nikkud (Vowel Points)

Remove all Unicode characters in these ranges:
- U+05B0..U+05BD (shva through meteg)
- U+05BF (rafe)
- U+05C1, U+05C2 (shin dot, sin dot)
- U+05C4, U+05C5 (upper dot, lower dot)
- U+05C7 (qamats qatan)

### 2. Strip Taamim (Cantillation Marks)

Remove all Unicode characters in range U+0591..U+05AF.

### 3. Punctuation Handling

| Character | Unicode | Action |
|-----------|---------|--------|
| Maqaf (Hebrew hyphen) | U+05BE | Replace with space |
| Sof Pasuq (verse-end colon) | U+05C3 | Remove |
| Paseq | U+05C0 | Remove |
| Geresh | U+05F3 | Remove |
| Gershayim | U+05F4 | Remove |

### 4. Final-Letter Normalization (CONFIGURABLE)

Hebrew has 5 letters with distinct final (sofit) forms. Policy is configurable:

| Final | Medial | When `NORMALIZE` | When `PRESERVE` |
|-------|--------|-------------------|------------------|
| ך | כ | ך → כ | keep ך |
| ם | מ | ם → מ | keep ם |
| ן | נ | ן → נ | keep ן |
| ף | פ | ף → פ | keep ף |
| ץ | צ | ץ → צ | keep ץ |

- **NORMALIZE** (default): Used for search/ELS/substring matching. Ensures a name
  like "אברהם" matches regardless of word position.
- **PRESERVE**: Used when computing gematria, since MISPAR_GADOL assigns different
  values to final letters (ך=500, ם=600, ן=700, ף=800, ץ=900).

### 5. Whitespace Normalization

- Collapse multiple consecutive spaces to a single space
- Strip leading and trailing whitespace

### 6. Validation

After normalization, every character MUST be either:
- A Hebrew consonant: א (U+05D0) through ת (U+05EA)
- A space (U+0020)

Any other character indicates a normalization bug or unexpected input.

## Edge Cases

- **Empty verses**: Rare but possible. Stored as empty string.
- **Aramaic passages**: Daniel 2:4b–7:28, Ezra 4:8–6:18, 7:12–26 contain Aramaic
  text using the same Hebrew script. Same normalization applies.
- **Ketiv/Qere**: We use the written text (ketiv) as provided by Sefaria.
- **Pe/Samekh markers**: Paragraph break indicators that may appear in some text
  editions. Not present in "Tanach with Text Only" but stripped if encountered.

## Usage in Code

```python
from autogematria.normalize import normalize_hebrew, FinalsPolicy

# For search/ELS (default):
text = normalize_hebrew("בְּרֵאשִׁ֖ית")  # → "בראשית"

# For gematria computation:
text = normalize_hebrew("אברהם", FinalsPolicy.PRESERVE)  # → "אברהם" (keeps ם)
```
