import io
from services.api import get, post, delete
from state.auth import get_token

def _auth_headers():
    token = get_token()
    return {"Authorization": f"Bearer {token}"} if token else {}

def list_docs():
    return get("/docs/list", headers=_auth_headers())

def delete_doc(doc_id: str):
    # ⚠️ Use correct endpoint depending on backend
    # If your backend uses /docs/delete/{id}, change below accordingly
    return delete(f"/docs/{doc_id}", headers=_auth_headers())

def upload_files(files: list):
    """
    Upload one or more files to backend /docs/upload.
    Returns APIResponse.
    """
    if not files:
        return None

    payload = []
    for f in files:
        bytes_data = f.getvalue() if hasattr(f, "getvalue") else f.read()
        payload.append(
            ("files", (f.name, io.BytesIO(bytes_data), f.type or "application/octet-stream"))
        )
    return post("/docs/upload", files=payload, headers=_auth_headers())
