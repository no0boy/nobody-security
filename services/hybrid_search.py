"""
混合检索：Dense（向量语义）+ Sparse（BM25 关键词）+ RRF 融合
- rank_bm25: 纯 Python 实现，零外部服务，~10MB 内存
- jieba: 中文分词
- RRF (Reciprocal Rank Fusion): 分数无关的排序融合算法
"""

import jieba
from rank_bm25 import BM25Okapi
import os

# ── 本地配置（替代缺失的 config 模块）──
HYBRID_SEARCH_ENABLED = True   # 是否启用混合检索
BM25_TOP_K = 10                # BM25 召回数
RRF_K = 60                     # RRF 融合参数
FINAL_TOP_K = 5                # 最终返回数

# 延迟导入，避免循环依赖
_collection = None

def _get_collection():
    global _collection
    if _collection is None:
        import chromadb
        persist_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chroma_data")
        client = chromadb.PersistentClient(path=persist_dir)
        _collection = client.get_or_create_collection(name="nobody_knowledge")
    return _collection


# ========== 全局 BM25 索引 ==========
_bm25: BM25Okapi = None
_bm25_docs: list[dict] = []  # [{id, content, metadata}, ...]
_index_ready = False


def _tokenize(text: str) -> list[str]:
    """中文分词 + 去空"""
    words = jieba.cut(text)
    return [w.strip() for w in words if len(w.strip()) >= 1]


def build_index() -> int:
    """
    从 ChromaDB 读取全部文档片段，构建 BM25 索引
    返回索引文档数。文档变更（上传/删除）后需调用此函数重建
    """
    global _bm25, _bm25_docs, _index_ready
    try:
        results = _get_collection().get(include=["documents", "metadatas"])
        docs = results.get("documents") or []
        ids = results.get("ids") or []
        metas = results.get("metadatas") or []

        if not docs:
            _bm25 = None
            _bm25_docs = []
            _index_ready = False
            print("[BM25] 知识库为空，跳过索引构建")
            return 0

        _bm25_docs = []
        tokenized_corpus = []
        for i, doc in enumerate(docs):
            _bm25_docs.append({
                "id": ids[i] if i < len(ids) else f"doc_{i}",
                "content": doc,
                "metadata": metas[i] if i < len(metas) else {}
            })
            tokenized_corpus.append(_tokenize(doc))

        _bm25 = BM25Okapi(tokenized_corpus)
        _index_ready = True
        print(f"[BM25] 索引构建完成，共 {len(_bm25_docs)} 条文档片段")
        return len(_bm25_docs)
    except Exception as e:
        _bm25 = None
        _bm25_docs = []
        _index_ready = False
        print(f"[BM25] 索引构建失败: {e}")
        return 0


def bm25_search(question: str, top_k: int = None) -> list[dict]:
    """
    纯 BM25 关键词检索
    返回: [{content, title, score, source}, ...]
    """
    global _bm25, _bm25_docs

    if not _index_ready or not _bm25:
        return []

    top_k = top_k or BM25_TOP_K
    tokens = _tokenize(question)
    scores = _bm25.get_scores(tokens)

    # 取 Top-K
    indexed = [(i, s) for i, s in enumerate(scores) if s > 0]
    indexed.sort(key=lambda x: x[1], reverse=True)

    results = []
    for i, score in indexed[:top_k]:
        doc = _bm25_docs[i]
        # BM25 分数归一化到 [0,1]（除以最大值）
        max_score = indexed[0][1] if indexed else 1
        normalized = round(score / max_score, 3) if max_score > 0 else 0
        results.append({
            "content": doc["content"],
            "title": doc["metadata"].get("doc_title", "未知文档"),
            "score": normalized,
            "source": "bm25"
        })
    return results


def _dense_search(question: str, top_k: int) -> list[dict]:
    """向量检索：直接查 ChromaDB"""
    try:
        import chromadb
        col = _get_collection()
        emb = _embed_text(question)
        results = col.query(query_embeddings=[emb], n_results=top_k,
                            include=["documents", "metadatas"])
        docs = []
        if results.get("documents") and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                meta = (results.get("metadatas") or [{}])[0]
                docs.append({
                    "content": doc,
                    "title": meta[i].get("source", "") if i < len(meta) else "",
                    "score": 1.0 - (i * 0.05),  # 近似分数
                    "source": "dense"
                })
        return docs
    except Exception:
        return []


def _embed_text(text: str) -> list:
    """中文语义向量"""
    try:
        import dashscope
        from http import HTTPStatus
        key = os.getenv("DASHSCOPE_API_KEY", "")
        if key:
            dashscope.api_key = key
            resp = dashscope.TextEmbedding.call(model="text-embedding-v3", input=text)
            if resp.status_code == HTTPStatus.OK:
                return resp.output["embeddings"][0]["embedding"]
    except Exception:
        pass
    # 降级：ChromaDB 内置模型
    import chromadb.utils.embedding_functions as ef
    return ef.DefaultEmbeddingFunction()([text])[0]


def hybrid_search(question: str, top_k: int = None) -> list[dict]:
    """
    混合检索主入口
    1. Dense（向量检索）+ Sparse（BM25）双路召回
    2. RRF 融合排序
    3. 返回 Top-K 片段
    """
    if not HYBRID_SEARCH_ENABLED:
        return _dense_search(question, top_k or FINAL_TOP_K)

    top_k = top_k or FINAL_TOP_K
    recall_k = top_k * 3

    # 双路并行检索
    dense_results = _dense_search(question, recall_k)
    sparse_results = bm25_search(question, recall_k)

    # 单路降级
    if not sparse_results:
        return dense_results[:top_k]
    if not dense_results:
        return sparse_results[:top_k]

    # ====== RRF 融合 ======
    rrf_scores = {}
    content_map = {}

    for rank, item in enumerate(dense_results):
        key = item["content"][:120]
        rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (RRF_K + rank + 1)
        content_map[key] = {**item, "source": item.get("source", "dense")}

    for rank, item in enumerate(sparse_results):
        key = item["content"][:120]
        rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (RRF_K + rank + 1)
        if key not in content_map:
            content_map[key] = {**item, "source": item.get("source", "bm25")}
        else:
            content_map[key]["source"] = "hybrid"

    sorted_keys = sorted(rrf_scores, key=rrf_scores.get, reverse=True)
    results = []
    max_score = max(rrf_scores.values()) if rrf_scores else 1.0
    for i, key in enumerate(sorted_keys[:top_k]):
        item = content_map[key]
        normalized = round(rrf_scores[key] / max_score, 3) if max_score > 0 else 0
        results.append({
            "content": item["content"],
            "title": item.get("title", ""),
            "score": min(normalized, 1.0),
            "source": item.get("source", "hybrid"),
        })

    return results


def get_index_status() -> dict:
    """获取 BM25 索引状态"""
    return {
        "enabled": HYBRID_SEARCH_ENABLED,
        "index_ready": _index_ready,
        "doc_count": len(_bm25_docs),
        "rrf_k": RRF_K,
    }
