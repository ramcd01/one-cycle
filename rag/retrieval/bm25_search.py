from __future__ import annotations

import math
from collections import Counter
import numpy as np
from .models import LoadedCorpus, SearchResult
from .tokenizer import tokenize, tokenize_corpus

class BM25SearchError(RuntimeError):
    pass

class BM25Index:
    def __init__(self, corpus_tokens: list[list[str]], *, k1: float = 1.5, b: float = 0.75) -> None:
        if not corpus_tokens:
            raise BM25SearchError('BM25 코퍼스가 비어 있습니다.')
        self.k1=k1; self.b=b; self.document_count=len(corpus_tokens)
        self.document_lengths=np.asarray([len(x) for x in corpus_tokens], dtype=np.float32)
        self.average_document_length=float(self.document_lengths.mean())
        self.term_frequencies=[Counter(x) for x in corpus_tokens]
        df=Counter()
        for tokens in corpus_tokens:
            df.update(set(tokens))
        self.idf={term: math.log(1.0 + (self.document_count-freq+0.5)/(freq+0.5)) for term,freq in df.items()}

    @classmethod
    def from_corpus(cls, corpus: LoadedCorpus) -> 'BM25Index':
        return cls(tokenize_corpus([item.search_text for item in corpus.items]))

    def get_scores(self, query_tokens: list[str]) -> np.ndarray:
        scores=np.zeros(self.document_count, dtype=np.float32)
        for term in query_tokens:
            idf=self.idf.get(term)
            if idf is None:
                continue
            for i, tf_map in enumerate(self.term_frequencies):
                tf=tf_map.get(term,0)
                if tf==0:
                    continue
                length_ratio=self.document_lengths[i]/max(self.average_document_length,1.0)
                denominator=tf+self.k1*(1.0-self.b+self.b*length_ratio)
                scores[i]+=idf*(tf*(self.k1+1.0))/denominator
        return scores

def bm25_search(corpus: LoadedCorpus, index: BM25Index, query: str, *, top_k: int) -> list[SearchResult]:
    if top_k <= 0:
        raise BM25SearchError('top_k는 1 이상이어야 합니다.')
    query_tokens=tokenize(query)
    if not query_tokens:
        raise BM25SearchError('질문에서 BM25 토큰을 생성하지 못했습니다.')
    scores=index.get_scores(query_tokens)
    indexes=np.argsort(-scores, kind='stable')[:min(top_k, corpus.size)]
    results=[]
    for rank, idx in enumerate(indexes, start=1):
        i=int(idx); score=float(scores[i])
        if score <= 0:
            continue
        item=corpus.get_item(i)
        results.append(SearchResult(i, item.chunk_id, item, bm25_score=score, bm25_rank=rank, matched_by={'bm25'}))
    return results
