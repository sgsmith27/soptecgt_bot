import os
import json
from typing import List, Dict, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

INDEX_PATH = "kb_index_embeddings.npz"
META_PATH = "kb_index_meta.json"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_model: Optional[SentenceTransformer] = None
_embeddings: Optional[np.ndarray] = None
_meta: Optional[List[Dict]] = None


def _load_index_if_needed():
    global _model, _embeddings, _meta

    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)

    if _embeddings is None:
        if not os.path.exists(INDEX_PATH):
            raise RuntimeError(
                f"No se encontró el archivo de embeddings '{INDEX_PATH}'. "
                f"Ejecuta primero 'python rag_index.py'."
            )
        data = np.load(INDEX_PATH)
        _embeddings = data["embeddings"]

    if _meta is None:
        if not os.path.exists(META_PATH):
            raise RuntimeError(
                f"No se encontró el archivo de metadatos '{META_PATH}'. "
                f"Ejecuta primero 'python rag_index.py'."
            )
        with open(META_PATH, "r", encoding="utf-8") as f:
            _meta = json.load(f)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
    b_norm = b / (np.linalg.norm(b) + 1e-9)
    return np.dot(a_norm, b_norm)


def buscar_soluciones(
    descripcion: str,
    categoria: Optional[str] = None,
    subcategoria: Optional[str] = None,
    top_k: int = 3,
) -> List[Dict]:
    """
    
    Devuelve una lista de dicts:
    {
      "title": str,
      "path": str,
      "category": str,
      "content": str,
      "score": float
    }
    """
    _load_index_if_needed()

    assert _embeddings is not None
    assert _meta is not None
    assert _model is not None

    #query
    query_parts = []
    if categoria:
        query_parts.append(f"Categoría: {categoria}")
    if subcategoria:
        query_parts.append(f"Subcategoría: {subcategoria}")
    query_parts.append(f"Descripción del problema: {descripcion}")

    full_query = "\n".join(query_parts)

    query_emb = _model.encode([full_query], convert_to_numpy=True)[0]

    sims = _cosine_similarity(_embeddings, query_emb)

    desc_low = (descripcion or "").lower()

    for i, doc in enumerate(_meta):
        title_low = (doc.get("title") or "").lower()
        bonus = 0.0

        
        if "no enciende" in desc_low and "no enciende" in title_low:
            bonus += 0.15
        if "pantalla negra" in desc_low and "pantalla negra" in title_low:
            bonus += 0.15
        if "se reinicia" in desc_low and "se reinicia" in title_low:
            bonus += 0.15

        sims[i] += bonus

    # Ordenamos por similitud descendente
    sorted_idx = np.argsort(-sims)
    
    results: List[Dict] = []
    cat_norm = (categoria or "").strip().lower()
    sub_norm = (subcategoria or "").strip().lower()

    for idx in sorted_idx:
        doc = _meta[idx]

        doc_cat = (doc.get("category") or "").strip().lower()
        doc_path = (doc.get("path") or "").strip().lower()
        doc_title = (doc.get("title") or "").strip().lower()

        #Filtrar por categoría exacta si viene
        if cat_norm:
            if doc_cat != cat_norm:
                continue
        
        if sub_norm:
            if sub_norm not in doc_path and sub_norm not in doc_title:
                continue

        results.append(
            {
                "title": doc["title"],
                "path": doc["path"],
                "category": doc["category"],
                "content": doc["content"],
                "score": float(sims[idx]),
            }
        )

        if len(results) >= top_k:
            break

    
    if not results and not cat_norm:
        for idx in sorted_idx[:top_k]:
            doc = _meta[idx]
            results.append(
                {
                    "title": doc["title"],
                    "path": doc["path"],
                    "category": doc["category"],
                    "content": doc["content"],
                    "score": float(sims[idx]),
                }
            )


    
    return results


if __name__ == "__main__":
    # Pequeña prueba manual
    print("Probando RAG engine...\n")
    ejemplos = [
        {
            "desc": "teclado no escribe",
            "cat": "periferico",
            "sub": "teclado",
        },
        {
            "desc": "mouse no se mueve",
            "cat": "periferico",
            "sub": "mouse",
        },
    ]

    for ej in ejemplos:
        print("=" * 80)
        print(f"Consulta: {ej['desc']} (cat={ej['cat']}, sub={ej['sub']})\n")
        res = buscar_soluciones(ej["desc"], ej["cat"], ej["sub"], top_k=2)
        for r in res:
            print(f"- {r['title']}  [cat={r['category']}, score={r['score']:.3f}]")
            print(f"  path: {r['path']}")
            print()
