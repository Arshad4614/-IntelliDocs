# backend/database/faiss_handler.py
# Windows-friendly FAISS utils for document RAG + conversation memory.
# - Uses IndexIDMap over IndexFlatIP for stable IDs
# - ALWAYS uses add_with_ids (never add) to avoid IDMap errors
# - Keeps a simple meta.pkl (dim, next_id, items=list aligned to rows)

from __future__ import annotations
from pathlib import Path
import pickle
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
import faiss
import numpy as np
import logging

# Storage# 
ROOT = Path(__file__).resolve().parents[2]  # repo root
BASE = ROOT / "vectorstores"
DOCS_DIR = BASE / "docs"
CONV_DIR = BASE / "conversations"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
CONV_DIR.mkdir(parents=True, exist_ok=True)
#creat faiss index and meta path return for  doc and cov #-----
def _paths(ns: str) -> Tuple[Path, Path]:
    if ns == "docs":
        return DOCS_DIR / "index.faiss", DOCS_DIR / "meta.pkl"
    if ns == "conv":
        return CONV_DIR / "index.faiss", CONV_DIR / "meta.pkl"
    raise ValueError(f"Unknown namespace: {ns}")
# Helpers---#
# --------------------------------------------------------------------------
def _norm_id(x)-> str: # this always return Id  as string #
    if x is None:
        return ""
    if isinstance(x, ObjectId):
        return str(x)
    return str(x)

# vector normalization for fais search#
def _norm(X: np.ndarray) -> np.ndarray:
    X = X.astype("float32")
    if X.ndim == 1:
        X = X.reshape(1, -1)
    faiss.normalize_L2(X)
    return X
# it creat new fais index#---
def _new_idmap(dim: int) -> faiss.IndexIDMap:
    return faiss.IndexIDMap(faiss.IndexFlatIP(dim))
#-- verify add with id inside faiss--#
def _is_idmap(ix: faiss.Index) -> bool:
    return hasattr(ix, "add_with_ids")
#-- load fais and meta index if file is present then load id index map is present and vector are not tjhrough error and if fais is empty it creat new---#
def _load(ns: str) -> Tuple[faiss.IndexIDMap, Dict[str, Any]]:
    idx_path, meta_path = _paths(ns)
    if idx_path.exists() and meta_path.exists():
        idx = faiss.read_index(str(idx_path))
        if not _is_idmap(idx):
            if getattr(idx, "ntotal", 0) > 0:
                raise RuntimeError(
                    f"FAISS: {idx_path.name} is not an IDMap but already has vectors. "
                    f"Delete these files once so we can rebuild as IDMap:\n  {idx_path}\n  {meta_path}"
                )
            idx = faiss.IndexIDMap(idx)

        with open(meta_path, "rb") as f:
            meta = pickle.load(f)
        meta.setdefault("dim", None)
        meta.setdefault("next_id", int(getattr(idx, "ntotal", 0)))
        meta.setdefault("items", [])
        nt = int(getattr(idx, "ntotal", 0))
        if len(meta["items"]) < nt:
            meta["items"].extend([None] * (nt - len(meta["items"])))
        return idx, meta
    idx = _new_idmap(1)
    meta = {"dim": None, "next_id": 0, "items": []}
    return idx, meta
# save index and meta on disk#
def _save(ns: str, idx: faiss.IndexIDMap, meta: Dict[str, Any]) -> None:
    idx_path, meta_path = _paths(ns)
    faiss.write_index(idx, str(idx_path))
    with open(meta_path, "wb") as f:
        pickle.dump(meta, f)
# it ensure that either you are changing your model or no--#
def _ensure_dim(idx: faiss.IndexIDMap, meta: Dict[str, Any], d: int) -> faiss.IndexIDMap:
    if meta["dim"] is None:
        if getattr(idx, "ntotal", 0) != 0:
            raise ValueError("Index not empty but dim is None; delete index files and retry.")
        idx = _new_idmap(d)
        meta["dim"] = d
        return idx
    if meta["dim"] != d:
        raise ValueError(f"FAISS dimension mismatch: existing={meta['dim']}, new={d}. Delete files to rebuild.")
    return idx

# DOCS namespace id assign , metadata store , and save index----------------#

def docs_add(
    *, 
    user_id: str, 
    doc_id: Optional[str], 
    texts: List[str], 
    vectors: List[List[float]], 
    filename: Optional[str] = None
) -> Dict[str, Any]:
    if not vectors or not texts:
        return {"added": 0}
    if len(vectors) != len(texts):
        raise ValueError("docs_add: vectors/texts length mismatch")

    X = _norm(np.array(vectors, dtype="float32"))
    d = X.shape[1]
    idx, meta = _load("docs")
    idx = _ensure_dim(idx, meta, d)

    start = int(meta["next_id"])
    ids = np.arange(start, start + X.shape[0], dtype="int64")
    idx.add_with_ids(X, ids)

    for i, t in enumerate(texts):
        rowid = int(ids[i])
        md = {
            "ns": "docs",
            "user_id": _norm_id(user_id),
            "doc_id": _norm_id(doc_id),
            "filename": filename,
            "text": t,
            "deleted": False,
        }
        if len(meta["items"]) <= rowid:
            meta["items"].extend([None] * (rowid - len(meta["items"]) + 1))
        meta["items"][rowid] = md

    meta["next_id"] = int(start + X.shape[0])
    _save("docs", idx, meta)

    # 🔎 Debug print
    print("\n--- FAISS ADD DEBUG ---")
    print("Added vectors:", len(texts))
    print("user_id saved :", _norm_id(user_id))
    print("doc_id saved  :", _norm_id(doc_id))
    print("filename      :", filename)
    print("ntotal vectors:", idx.ntotal)
    print("--- END ADD DEBUG ---\n")

    return {"added": len(texts), "first_id": start}

# return similar chunk when we ask questions-----#
def docs_search(
    *, 
    user_id: str, 
    query_vector: List[float], 
    top_k: int = 5, 
    filename: Optional[str] = None, 
    doc_id: Optional[str] = None, 
    oversample: int = 50
) -> List[Dict[str, Any]]:
    idx, meta = _load("docs")
    if getattr(idx, "ntotal", 0) == 0 or not meta["items"]:
        return []

    q = _norm(np.array(query_vector, dtype="float32"))
    K = min(oversample, idx.ntotal)  # always oversample more than needed
    D, I = idx.search(q, K)

    candidates: List[Dict[str, Any]] = []
    for score, rowid in zip(D[0].tolist(), I[0].tolist()):
        if rowid < 0:
            continue
        info = meta["items"][rowid] if rowid < len(meta["items"]) else None
        if not info:
            continue
        # ✅ only skip if explicitly True
        if info.get("deleted") is True:
            continue

        # ✅ normalize IDs before compare
        if _norm_id(info.get("user_id")) != _norm_id(user_id):
            continue
        if filename and str(info.get("filename")) != str(filename):
            continue
        if doc_id:
            # normalize both sides before comparing (handles ObjectId and str)
            if _norm_id(info.get("doc_id")) != _norm_id(doc_id):
                continue
        candidates.append({
            "score": float(score),
            "id": int(rowid),
            "text": info.get("text", ""),
            "metadata": info,
        })

    # sort by score and keep top_k
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:top_k]

# delet all chunks of one document --#
def docs_remove_by_doc_id(*, user_id: str, doc_id: str) -> Dict[str, Any]:
    idx, meta = _load("docs")
    if not meta["items"]:
        return {"deleted": 0}
    count = 0
    # collect rowids to remove from FAISS index
    #rowids_to_remove: List[int] = []

    for i, info in enumerate(meta["items"]):
        if not info:
            continue
        if (
            _norm_id(info.get("user_id")) == _norm_id(user_id)
            and _norm_id(info.get("doc_id")) == _norm_id(doc_id)
            and not info.get("deleted")
        ):
            # mark deleted in metadata and schedule removal
            info["deleted"] = True
            count += 1

    _save("docs", idx, meta)
# debug
    print(f"--- FAISS REMOVE DEBUG ---\nRequested doc_id: {_norm_id(doc_id)}\nRemoved vectors: {count}\n--- END REMOVE DEBUG ---")
    return {"deleted": count}
# CONVERSATION namespace---- it add every meesage of chat in to faiss after making chunks -----#
def conv_save_vectors(*, user_id: str, conversation_id: str, texts: List[str], vectors: List[List[float]], roles: Optional[List[Optional[str]]] = None, message_ids: Optional[List[Optional[str]]] = None) -> Dict[str, Any]:
    if not vectors or not texts:
        return {"added": 0}
    if len(vectors) != len(texts):
        raise ValueError("conv_save_vectors: vectors/texts length mismatch")
    if roles and len(roles) != len(texts):
        raise ValueError("conv_save_vectors: roles length mismatch")
    if message_ids and len(message_ids) != len(texts):
        raise ValueError("conv_save_vectors: message_ids length mismatch")

    X = _norm(np.array(vectors, dtype="float32"))
    d = X.shape[1]
    idx, meta = _load("conv")
    idx = _ensure_dim(idx, meta, d)

    start = int(meta["next_id"])
    ids = np.arange(start, start + X.shape[0], dtype="int64")
    idx.add_with_ids(X, ids)

    for i, t in enumerate(texts):
        rowid = int(ids[i])
        md = {
            "ns": "conv",
            "user_id": _norm_id(user_id),
            "conversation_id": _norm_id(conversation_id),
            "role": roles[i] if roles else None,
            "message_id": message_ids[i] if message_ids else None,
            "text": t,
            "deleted": False,
        }
        if len(meta["items"]) <= rowid:
            meta["items"].extend([None] * (rowid - len(meta["items"]) + 1))
        meta["items"][rowid] = md

    meta["next_id"] = int(start + X.shape[0])
    _save("conv", idx, meta)
    return {"added": len(texts)}
# it search in conversation memory and return similar message--------#
def conv_search(*, user_id: str, conversation_id: str, query_vector: List[float], top_k: int = 5, oversample: int = 50) -> List[Dict[str, Any]]:
    idx, meta = _load("conv")
    if getattr(idx, "ntotal", 0) == 0 or not meta["items"]:
        return []

    q = _norm(np.array(query_vector, dtype="float32"))
    K = min(oversample, idx.ntotal)
    D, I = idx.search(q, K)

    candidates: List[Dict[str, Any]] = []
    for score, rowid in zip(D[0].tolist(), I[0].tolist()):
        if rowid < 0:
            continue
        info = meta["items"][rowid] if rowid < len(meta["items"]) else None
        if not info or info.get("deleted"):
            continue
        if _norm_id(info.get("user_id")) != _norm_id(user_id):
            continue
        if _norm_id(info.get("conversation_id")) != _norm_id(conversation_id):
            continue
        candidates.append({
            "score": float(score),
            "id": int(rowid),
            "text": info.get("text", ""),
            "metadata": info,
        })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:top_k]

# --------------------------------------------------------------------------
# Backward-compat wrappers
# --------------------------------------------------------------------------
def save_to_faiss(vectors: List[List[float]], metadata_list: List[Dict[str, Any]]):
    if not vectors or not metadata_list:
        return {"added": 0}
    texts = [(md.get("chunk") or md.get("text") or "") for md in metadata_list]
    user_id = _norm_id(metadata_list[0].get("user_id"))
    doc_id = _norm_id(metadata_list[0].get("doc_id"))
    filename = metadata_list[0].get("filename")
    return docs_add(user_id=user_id, doc_id=doc_id, texts=texts, vectors=vectors, filename=filename)

def search_in_faiss_for_user(
    query_vector: List[float], 
    user_id: str, 
    doc_id: Optional[str] = None, 
    filename: Optional[str] = None, 
    top_k: int = 5
):
    # Debug start
    print("\n--- FAISS SEARCH DEBUG ---")
    print("Input user_id:", user_id)
    print("Input doc_id :", doc_id)
    print("Input filename:", filename)

    results = docs_search(
        user_id=_norm_id(user_id), 
        query_vector=query_vector, 
        top_k=top_k, 
        filename=filename, 
        doc_id=_norm_id(doc_id) if doc_id else None
    )

    # Debug output
    print("Total retrieved candidates:", len(results))
    for i, r in enumerate(results[:3]):  # show top 3
        print(f"[{i}] score={r['score']:.4f}")
        print("    text snippet:", r['text'][:100].replace("\n", " "))
        print("    metadata:", r['metadata'])

    if not results:
        print("⚠️ No results found (likely user_id/doc_id mismatch or deleted flag).")

    print("--- END DEBUG ---\n")
    return results
