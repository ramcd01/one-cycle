from __future__ import annotations

import re
import unicodedata

TOKEN_PATTERN = re.compile(r"[가-힣]+|[a-zA-Z]+[a-zA-Z0-9]*|\d+(?:[.,]\d+)*")
KOREAN_PARTICLES = tuple(sorted({
    '으로부터','에게서','에서는','으로는','으로도','까지는','부터는','에게는','으로','에서','에게','부터','까지','처럼','보다','하고','이며','이고','이나','거나','에는','에도','만은','만이','은','는','이','가','을','를','에','의','도','만','과','와','로'
}, key=len, reverse=True))

def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize('NFKC', text).lower()).strip()

def _strip_particle(token: str) -> str:
    if not re.fullmatch(r"[가-힣]+", token):
        return token
    for p in KOREAN_PARTICLES:
        if token.endswith(p) and len(token) > len(p)+1:
            return token[:-len(p)]
    return token

def tokenize(text: str) -> list[str]:
    if not isinstance(text, str):
        raise TypeError(f"text는 문자열이어야 합니다: {type(text).__name__}")
    normalized = normalize_text(text)
    if not normalized:
        return []
    result=[]
    for token in TOKEN_PATTERN.findall(normalized):
        cleaned = _strip_particle(token.strip('.,'))
        if cleaned:
            result.append(cleaned)
    return result

def tokenize_corpus(texts: list[str]) -> list[list[str]]:
    return [tokenize(t) for t in texts]
