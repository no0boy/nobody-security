"""RAG引擎 — 语义检索 + 知识库初始化"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _embed_text(text: str) -> list:
    """中文语义向量 — DashScope text-embedding-v3（校园项目同款）"""
    try:
        import dashscope
        from http import HTTPStatus
        # 用 provider.json 里的 key，fallback 到 DASHSCOPE_API_KEY
        prov_path = os.path.join(ROOT, "provider.json")
        key = ""
        if os.path.exists(prov_path):
            with open(prov_path, "r") as f:
                key = json.load(f).get("api_key", "")
        key = key if key and not key.startswith("${") else os.getenv("DASHSCOPE_API_KEY", "")
        if key:
            dashscope.api_key = key
            resp = dashscope.TextEmbedding.call(model="text-embedding-v3", input=text)
            if resp.status_code == HTTPStatus.OK:
                return resp.output["embeddings"][0]["embedding"]
    except Exception:
        pass
    # 降级：ChromaDB 内置模型
    import chromadb.utils.embedding_functions as ef
    fn = ef.DefaultEmbeddingFunction()
    return fn([text])[0]

def init_knowledge():
    import chromadb
    persist = os.path.join(ROOT, "chroma_data")
    client = chromadb.PersistentClient(path=persist)
    col = client.get_or_create_collection(name="nobody_knowledge", metadata={"hnsw:space": "cosine"})
    if col.count() > 0: return
    print("[RAG] 知识库为空，导入...")
    cnt = 0
    for sub in ["seeds", "public"]:
        src = os.path.join(ROOT, "knowledge", sub)
        if not os.path.exists(src): continue
        for root, dirs, files in os.walk(src):
            for f in files:
                if not f.endswith((".txt",".md")): continue
                try:
                    with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                        text = fh.read()
                except: continue
                rel = os.path.relpath(os.path.join(root, f), os.path.join(ROOT, "knowledge"))
                for j, chunk in enumerate([text[i:i+500] for i in range(0, len(text), 500)]):
                    try:
                        col.add(ids=[f"{rel}_chunk_{j}"], embeddings=[_embed_text(chunk)],
                                documents=[chunk], metadatas=[{"source":rel,"chunk":j,"public":sub=="public"}])
                        cnt += 1
                    except: pass
    print(f"[RAG] 已入库 {cnt} 个向量片段")

    # 同时建记忆语义索引
    try:
        from core.memory import Memory
        Memory.sem_index()
    except: pass

def search(question: str) -> str:
    try:
        from services.hybrid_search import build_index, hybrid_search
        build_index()
        results = hybrid_search(question, top_k=5)
        if results:
            return "\n---\n".join([r.get("content","")[:500] for r in results])
    except: pass
    try:
        import chromadb
        col = chromadb.PersistentClient(path=os.path.join(ROOT, "chroma_data")).get_or_create_collection(name="nobody_knowledge")
        emb = _embed_text(question)
        results = col.query(query_embeddings=[emb], n_results=3, include=["documents"])
        if results["documents"] and results["documents"][0]:
            return "\n---\n".join([d[:500] for d in results["documents"][0]])
    except: pass
    return ""
