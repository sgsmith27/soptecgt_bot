import os
import json
from typing import List, Dict

import numpy as np
from sentence_transformers import SentenceTransformer


KB_DIR = "kb"

# Archivos de salida del índice
INDEX_PATH = "kb_index_embeddings.npz"
META_PATH = "kb_index_meta.json"

# Modelo de embeddings
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def load_markdown_files(base_dir: str) -> List[Dict]:
    """
    Recorre la carpeta kb/ y devuelve una lista de documentos:
    {
      "id": int,
      "path": "kb/perifericos/topaz_no_muestra_firma.md",
      "category": "perifericos",
      "title": "Problema ...",
      "content": "texto completo del md"
    }
    """
    docs = []
    doc_id = 0

    for root, _, files in os.walk(base_dir):
        for fname in files:
            if not fname.lower().endswith(".md"):
                continue

            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, base_dir)

            
            parts = rel_path.split(os.sep)
            category = parts[0] if len(parts) > 1 else "general"

            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            
            title = None
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("#"):
                    title = line.lstrip("#").strip()
                    break

            if not title:
                title = fname

            docs.append(
                {
                    "id": doc_id,
                    "path": rel_path.replace(os.sep, "/"),
                    "category": category,
                    "title": title,
                    "content": content,
                }
            )
            doc_id += 1

    return docs


def build_index():
    print(f"📚 Cargando documentos desde '{KB_DIR}'...")
    docs = load_markdown_files(KB_DIR)
    if not docs:
        print("⚠️ No se encontraron documentos .md en la carpeta kb/.")
        return

    print(f"✅ Se encontraron {len(docs)} documentos. Generando embeddings...")

    model = SentenceTransformer(MODEL_NAME)
    texts = [d["content"] for d in docs]

    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        show_progress_bar=True,
    )

    # embeddings en un .npz comprimido
    np.savez_compressed(INDEX_PATH, embeddings=embeddings)

    # metadatos en JSON
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)

    print(f"💾 Índice guardado en: {INDEX_PATH}")
    print(f"💾 Metadatos guardados en: {META_PATH}")
    print("🎉 Indexación RAG completada.")


if __name__ == "__main__":
    build_index()
