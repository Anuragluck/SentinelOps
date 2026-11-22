from src.tools.hybrid_rag import Chunk, HybridRetriever, reciprocal_rank_fusion


def test_exact_error_code_retrieval():
    chunks = [Chunk("a", "ERR_POOL_EXHAUSTED connection pool", "a.md", {}),
              Chunk("b", "unrelated catalog cache", "b.md", {})]
    assert HybridRetriever(chunks).search("ERR_POOL_EXHAUSTED", 1)[0].chunk_id == "a"


def test_rrf_combines_ranked_sources():
    a = Chunk("a", "a", "a", {})
    b = Chunk("b", "b", "b", {})
    assert [c.chunk_id for c in reciprocal_rank_fusion([a, b], [b, a], limit=2)] == ["a", "b"]
