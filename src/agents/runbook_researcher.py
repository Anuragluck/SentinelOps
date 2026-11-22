from src.tools.hybrid_rag import HybridRetriever


def research(query: str, directory: str = "evals/dataset/runbooks", limit: int = 5):
    return HybridRetriever.from_directory(directory).search(query, limit)
