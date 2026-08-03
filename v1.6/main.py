from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uuid
import os
import sqlite3
import math
import re
import struct
from typing import List, Optional

app = FastAPI()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

UPLOAD_DIR = os.path.join(BASE_DIR, "archived_files")
os.makedirs(UPLOAD_DIR, exist_ok=True)
DB_PATH = os.path.join(BASE_DIR, "archivio.db")
ALLOWED_3D_EXTENSIONS = {".ply", ".obj", ".stl", ".glb", ".gltf", ".fbx", ".dae", ".3ds", ".off"}
ALLOWED_METADATA_EXTENSIONS = {".txt"}
MAX_METADATA_BYTES = 200_000
MAX_TEXT_SCAN_BYTES = 1_500_000

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def inizializza_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cartelle (
            id TEXT PRIMARY KEY,
            titolo TEXT NOT NULL,
            uploader TEXT,
            data_scavo TEXT,
            note TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reperti (
            id TEXT PRIMARY KEY,
            titolo TEXT NOT NULL,
            uploader TEXT,
            categoria TEXT NOT NULL,
            data_scoperta TEXT,
            note TEXT,
            percorso_file TEXT NOT NULL,
            nome_originale TEXT NOT NULL,
            folder_id TEXT,
            FOREIGN KEY(folder_id) REFERENCES cartelle(id)
        )
    ''')
    conn.commit()
    conn.close()
    ensure_column("reperti", "folder_id", "TEXT")
    ensure_column("reperti", "metadata_path", "TEXT")
    ensure_column("reperti", "metadata_original_name", "TEXT")
    ensure_column("reperti", "metadata_text", "TEXT")
    ensure_column("reperti", "uploader", "TEXT")

def has_column(table_name: str, column_name: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row["name"] for row in cursor.fetchall()]
    conn.close()
    return column_name in columns

def ensure_column(table_name: str, column_name: str, column_type: str):
    if has_column(table_name, column_name):
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
    conn.commit()
    conn.close()

def extension_for(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower()

def validate_3d_file(upload: UploadFile):
    if extension_for(upload.filename) not in ALLOWED_3D_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_3D_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"Only 3D files are allowed ({allowed})")

def validate_metadata_file(upload: Optional[UploadFile]):
    if upload and upload.filename and extension_for(upload.filename) not in ALLOWED_METADATA_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Metadata files must be .txt files")

async def save_upload(upload: UploadFile, allowed_kind: str):
    if allowed_kind == "3d":
        validate_3d_file(upload)
    elif allowed_kind == "metadata":
        validate_metadata_file(upload)

    file_id = str(uuid.uuid4())
    file_extension = extension_for(upload.filename)
    saved_name = f"{file_id}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, saved_name)

    with open(file_path, "wb") as buffer:
        buffer.write(await upload.read())

    return file_id, saved_name, file_path

def read_metadata_text(file_path: Optional[str]) -> str:
    if not file_path or not os.path.exists(file_path):
        return ""

    with open(file_path, "rb") as source:
        raw = source.read(MAX_METADATA_BYTES)
    return raw.decode("utf-8", errors="ignore").strip()

def tokenize(text: str) -> set:
    stopwords = {
        "the", "and", "for", "from", "with", "this", "that", "depth", "date",
        "data", "notes", "note", "file", "model", "cm", "mm", "m", "of", "in",
        "on", "at", "to", "a", "an", "is", "are", "was", "were", "di", "da",
        "del", "della", "dati", "nota", "note"
    }
    return {
        token for token in re.findall(r"[a-zA-Z0-9]{3,}", (text or "").lower())
        if token not in stopwords
    }

def extract_numbers(text: str) -> List[float]:
    values = []
    for match in re.findall(r"[-+]?\d+(?:[.,]\d+)?", text or ""):
        try:
            values.append(float(match.replace(",", ".")))
        except ValueError:
            continue
    return values[:40]

def scan_text_file(path: str) -> str:
    with open(path, "rb") as source:
        raw = source.read(MAX_TEXT_SCAN_BYTES)
    return raw.decode("utf-8", errors="ignore")

def bounds_from_points(points: List[tuple]) -> Optional[dict]:
    if not points:
        return None
    xs, ys, zs = zip(*points)
    dims = [max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)]
    return {
        "dimensions": dims,
        "thickness": min(dims),
        "volume_proxy": dims[0] * dims[1] * dims[2],
    }

def parse_obj_features(path: str) -> dict:
    text = scan_text_file(path)
    vertices = []
    vertex_count = 0
    face_count = 0
    texture_count = 0
    for line in text.splitlines():
        if line.startswith("v "):
            vertex_count += 1
            if len(vertices) < 1200:
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
                    except ValueError:
                        pass
        elif line.startswith("f "):
            face_count += 1
        elif line.startswith("vt "):
            texture_count += 1
    return {
        "vertex_count": vertex_count,
        "face_count": face_count,
        "has_texture": texture_count > 0,
        "bounds": bounds_from_points(vertices),
    }

def parse_ply_features(path: str) -> dict:
    text = scan_text_file(path)
    header, _, body = text.partition("end_header")
    vertex_count = 0
    face_count = 0
    color_props = 0
    is_ascii = "format ascii" in header.lower()
    for line in header.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "element" and parts[1] == "vertex":
            vertex_count = int(parts[2])
        elif len(parts) >= 3 and parts[0] == "element" and parts[1] == "face":
            face_count = int(parts[2])
        elif len(parts) >= 3 and parts[0] == "property" and parts[-1].lower() in {"red", "green", "blue", "alpha"}:
            color_props += 1

    vertices = []
    if is_ascii:
        for line in body.strip().splitlines()[: min(vertex_count, 1200)]:
            parts = line.split()
            if len(parts) >= 3:
                try:
                    vertices.append((float(parts[0]), float(parts[1]), float(parts[2])))
                except ValueError:
                    pass

    return {
        "vertex_count": vertex_count,
        "face_count": face_count,
        "has_texture": color_props >= 3,
        "bounds": bounds_from_points(vertices),
    }

def parse_stl_features(path: str) -> dict:
    file_size = os.path.getsize(path)
    triangle_count = 0
    vertices = []
    with open(path, "rb") as source:
        header = source.read(84)
        if len(header) == 84:
            triangle_count = struct.unpack("<I", header[80:84])[0]

    if triangle_count <= 0 or triangle_count * 50 + 84 != file_size:
        text = scan_text_file(path)
        triangle_count = len(re.findall(r"\bfacet\s+normal\b", text, flags=re.IGNORECASE))
        for match in re.finditer(r"\bvertex\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)", text):
            if len(vertices) >= 1200:
                break
            try:
                vertices.append((float(match.group(1)), float(match.group(2)), float(match.group(3))))
            except ValueError:
                pass

    return {
        "vertex_count": triangle_count * 3,
        "face_count": triangle_count,
        "has_texture": False,
        "bounds": bounds_from_points(vertices),
    }

def extract_3d_features(path: str, original_name: str) -> dict:
    ext = extension_for(original_name)
    features = {
        "extension": ext,
        "file_size": os.path.getsize(path) if os.path.exists(path) else 0,
        "vertex_count": 0,
        "face_count": 0,
        "has_texture": False,
        "bounds": None,
    }
    try:
        if ext == ".obj":
            features.update(parse_obj_features(path))
        elif ext == ".ply":
            features.update(parse_ply_features(path))
        elif ext == ".stl":
            features.update(parse_stl_features(path))
    except Exception:
        pass
    return features

def artifact_profile(row: dict) -> dict:
    metadata_text = row.get("metadata_text") or read_metadata_text(row.get("metadata_path"))
    searchable_text = " ".join([
        row.get("titolo") or "",
        row.get("categoria") or "",
        row.get("uploader") or "",
        row.get("data_scoperta") or "",
        row.get("note") or "",
        metadata_text,
        row.get("nome_originale") or "",
    ])
    features = extract_3d_features(row["percorso_file"], row["nome_originale"])
    return {
        "row": row,
        "metadata_text": metadata_text,
        "tokens": tokenize(searchable_text),
        "numbers": extract_numbers(searchable_text),
        "features": features,
    }

def ratio_similarity(a: float, b: float) -> float:
    if not a or not b:
        return 0
    return min(a, b) / max(a, b)

def compare_profiles(left: dict, right: dict) -> dict:
    left_tokens = left["tokens"]
    right_tokens = right["tokens"]
    shared_tokens = sorted(left_tokens.intersection(right_tokens))
    text_similarity = len(shared_tokens) / max(len(left_tokens.union(right_tokens)), 1)

    lf = left["features"]
    rf = right["features"]
    size_similarity = ratio_similarity(lf.get("file_size", 0), rf.get("file_size", 0))
    vertex_similarity = ratio_similarity(lf.get("vertex_count", 0), rf.get("vertex_count", 0))
    face_similarity = ratio_similarity(lf.get("face_count", 0), rf.get("face_count", 0))
    same_extension = lf.get("extension") == rf.get("extension")
    same_category = left["row"].get("categoria") == right["row"].get("categoria")

    thickness_similarity = 0
    if lf.get("bounds") and rf.get("bounds"):
        thickness_similarity = ratio_similarity(lf["bounds"].get("thickness"), rf["bounds"].get("thickness"))

    number_similarity = 0
    if left["numbers"] and right["numbers"]:
        close_pairs = 0
        for a in left["numbers"]:
            if any(abs(a - b) <= max(0.15 * max(abs(a), abs(b), 1), 1) for b in right["numbers"]):
                close_pairs += 1
        number_similarity = close_pairs / max(len(left["numbers"]), 1)

    score = (
        text_similarity * 36
        + number_similarity * 17
        + size_similarity * 10
        + vertex_similarity * 12
        + face_similarity * 10
        + thickness_similarity * 8
        + (5 if same_category else 0)
        + (2 if same_extension else 0)
    )

    reasons = []
    if shared_tokens:
        reasons.append("shared metadata terms: " + ", ".join(shared_tokens[:8]))
    if same_category:
        reasons.append("same category")
    if same_extension:
        reasons.append("same 3D format")
    if vertex_similarity > 0.7 or face_similarity > 0.7:
        reasons.append("similar mesh density")
    if thickness_similarity > 0.65:
        reasons.append("similar thickness or bounding dimensions")
    if lf.get("has_texture") and rf.get("has_texture"):
        reasons.append("both contain texture or color signals")
    if number_similarity > 0:
        reasons.append("close numeric values in notes or metadata")

    return {
        "score": round(min(score, 100), 1),
        "reasons": reasons[:5],
        "shared_terms": shared_tokens[:12],
    }

def row_to_public(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "titolo": row.get("titolo"),
        "categoria": row.get("categoria"),
        "uploader": row.get("uploader") or "",
        "data_scoperta": row.get("data_scoperta"),
        "note": row.get("note"),
        "nome_originale": row.get("nome_originale"),
        "metadata_original_name": row.get("metadata_original_name"),
    }

inizializza_db()

@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/archivio", response_class=HTMLResponse)
async def archivio_page(request: Request):
    return templates.TemplateResponse("archivio.html", {"request": request})

@app.get("/newfile", response_class=HTMLResponse)
async def new_file_page(request: Request):
    return templates.TemplateResponse("newfile.html", {"request": request})

@app.get("/newfolder", response_class=HTMLResponse)
async def new_folder_page(request: Request):
    return templates.TemplateResponse("newfolder.html", {"request": request})

@app.get("/newresearch", response_class=HTMLResponse)
async def new_research_page(request: Request):
    return templates.TemplateResponse("newresearch.html", {"request": request})

@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request, q: str = ""):
    query = q.strip()
    results = []

    if query:
        pattern = f"%{query.lower()}%"
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM reperti
            WHERE LOWER(titolo) LIKE ?
               OR LOWER(COALESCE(categoria, '')) LIKE ?
               OR LOWER(COALESCE(uploader, '')) LIKE ?
               OR LOWER(COALESCE(data_scoperta, '')) LIKE ?
               OR LOWER(COALESCE(note, '')) LIKE ?
               OR LOWER(COALESCE(metadata_text, '')) LIKE ?
            ORDER BY titolo COLLATE NOCASE
        """, (pattern, pattern, pattern, pattern, pattern, pattern))
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

    return templates.TemplateResponse("searchres.html", {
        "request": request,
        "query": query,
        "results": results,
    })

@app.get("/theTeam", response_class=HTMLResponse)
async def the_team_page(request: Request):
    return templates.TemplateResponse("team.html", {"request": request})

@app.get("/support", response_class=HTMLResponse)
async def support_page(request: Request):
    return templates.TemplateResponse("support.html", {"request": request})

@app.get("/theTeam/Rossella", response_class=HTMLResponse)
async def ross_page(request: Request):
    return templates.TemplateResponse("ross.html", {"request": request})

@app.get("/theTeam/Simone", response_class=HTMLResponse)
async def simo_page(request: Request):
    return templates.TemplateResponse("simo.html", {"request": request})

@app.get("/theTeam/Liliana", response_class=HTMLResponse)
async def lilly_page(request: Request):
    return templates.TemplateResponse("lilly.html", {"request": request})

@app.post("/upload")
async def upload_file(
    titolo: str = Form(...),
    categoria: str = Form(...),
    uploader: str = Form(...),
    data_scoperta: str = Form(None),
    note: str = Form(None),
    file_3d: UploadFile = File(...),
    metadata_txt: Optional[UploadFile] = File(None)
):
    file_id, salvaged_name, file_path = await save_upload(file_3d, "3d")
    metadata_path = None
    metadata_original_name = None
    metadata_text = ""

    if metadata_txt and metadata_txt.filename:
        _, _, metadata_path = await save_upload(metadata_txt, "metadata")
        metadata_original_name = metadata_txt.filename
        metadata_text = read_metadata_text(metadata_path)

    nuovo_modello = {
        "id": file_id,
        "titolo": titolo,
        "categoria": categoria.lower().strip(),
        "data_scoperta": data_scoperta,
        "note": note,
        "uploader": uploader,
        "percorso_file": file_path,
        "nome_originale": file_3d.filename,
        "metadata_path": metadata_path,
        "metadata_original_name": metadata_original_name,
        "metadata_text": metadata_text
    }

    conn = get_db_connection()
    cursor = conn.cursor()
    if has_column("reperti", "filename"):
        cursor.execute(
            """
            INSERT INTO reperti (
                id, titolo, categoria, data_scoperta, note, percorso_file, nome_originale,
                folder_id, filename, metadata_path, metadata_original_name, metadata_text, uploader
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                nuovo_modello["id"],
                nuovo_modello["titolo"],
                nuovo_modello["categoria"],
                nuovo_modello["data_scoperta"],
                nuovo_modello["note"],
                nuovo_modello["percorso_file"],
                nuovo_modello["nome_originale"],
                None,
                salvaged_name,
                nuovo_modello["metadata_path"],
                nuovo_modello["metadata_original_name"],
                nuovo_modello["metadata_text"],
                nuovo_modello["uploader"]
            )
        )
    else:
        cursor.execute(
            """
            INSERT INTO reperti (
                id, titolo, categoria, data_scoperta, note, percorso_file, nome_originale,
                folder_id, metadata_path, metadata_original_name, metadata_text, uploader
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                nuovo_modello["id"],
                nuovo_modello["titolo"],
                nuovo_modello["categoria"],
                nuovo_modello["data_scoperta"],
                nuovo_modello["note"],
                nuovo_modello["percorso_file"],
                nuovo_modello["nome_originale"],
                None,
                nuovo_modello["metadata_path"],
                nuovo_modello["metadata_original_name"],
                nuovo_modello["metadata_text"],
                nuovo_modello["uploader"]
            )
        )
    conn.commit()
    conn.close()

    return {"status": "success", "data": nuovo_modello}

@app.post("/upload-folder")
async def upload_folder(
    request: Request,
    files: List[UploadFile] = File(...),
    metadata_files: Optional[List[UploadFile]] = File(None)
):
    form = await request.form()
    titolo_cartella = form.get("titolo_cartella", "").strip()
    data_scavo = form.get("data_scavo")
    note_cartella = form.get("note_cartella")
    titoli = form.getlist("titoli")
    categorie = form.getlist("categorie")
    uploader_cartella = form.get("uploader_cartella", "").strip()
    datazioni = form.getlist("datazioni")
    note_file = form.getlist("note_file")
    metadata_file_indexes = form.getlist("metadata_file_indexes")

    if not titolo_cartella:
        raise HTTPException(status_code=400, detail="Folder title is required")

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    if len(files) != len(titoli) or len(files) != len(categorie):
        raise HTTPException(status_code=400, detail="File details do not match uploaded files")

    folder_id = str(uuid.uuid4())
    saved_models = []

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO cartelle (id, titolo, data_scavo, note) VALUES (?, ?, ?, ?)",
        (folder_id, titolo_cartella, data_scavo, note_cartella)
    )

    with_filename = has_column("reperti", "filename")
    metadata_by_index = {}
    for meta_index, metadata_upload in zip(metadata_file_indexes, metadata_files or []):
        if not metadata_upload or not metadata_upload.filename:
            continue
        try:
            metadata_by_index[int(meta_index)] = metadata_upload
        except ValueError:
            continue

    for index, upload in enumerate(files):
        file_id, salvaged_name, file_path = await save_upload(upload, "3d")
        metadata_path = None
        metadata_original_name = None
        metadata_text = ""

        metadata_upload = metadata_by_index.get(index)
        if metadata_upload:
            _, _, metadata_path = await save_upload(metadata_upload, "metadata")
            metadata_original_name = metadata_upload.filename
            metadata_text = read_metadata_text(metadata_path)

        titolo = titoli[index].strip() or upload.filename
        categoria = categorie[index].lower().strip() or "other"
        uploader = uploader_cartella
        datazione = datazioni[index] if index < len(datazioni) else ""
        nota = note_file[index] if index < len(note_file) else ""

        if with_filename:
            cursor.execute(
                """
                INSERT INTO reperti (
                    id, titolo, categoria, data_scoperta, note, percorso_file, nome_originale,
                    folder_id, filename, metadata_path, metadata_original_name, metadata_text, uploader
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id, titolo, categoria, datazione, nota, file_path, upload.filename,
                    folder_id, salvaged_name, metadata_path, metadata_original_name, metadata_text, uploader
                )
            )
        else:
            cursor.execute(
                """
                INSERT INTO reperti (
                    id, titolo, categoria, data_scoperta, note, percorso_file, nome_originale,
                    folder_id, metadata_path, metadata_original_name, metadata_text, uploader
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id, titolo, categoria, datazione, nota, file_path, upload.filename,
                    folder_id, metadata_path, metadata_original_name, metadata_text, uploader
                )
            )

        saved_models.append({
            "id": file_id,
            "titolo": titolo,
            "categoria": categoria,
            "uploader": uploader,
            "data_scoperta": datazione,
            "note": nota,
            "percorso_file": file_path,
            "nome_originale": upload.filename,
            "folder_id": folder_id,
            "metadata_original_name": metadata_original_name,
            "uploader": uploader_cartella
        })

    conn.commit()
    conn.close()

    return {"status": "success", "folder_id": folder_id, "data": saved_models}

@app.get("/modelli")
async def lista_modelli(categoria: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()

    if categoria:
        cursor.execute("SELECT * FROM reperti WHERE categoria = ?", (categoria.lower().strip(),))
    else:
        cursor.execute("SELECT * FROM reperti")

    modelli = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return modelli

@app.get("/categories")
async def list_categories():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT categoria FROM reperti ORDER BY categoria")
    categories = [row["categoria"] for row in cursor.fetchall() if row["categoria"]]
    conn.close()
    return categories

@app.post("/research")
async def run_research(request: Request):
    payload = await request.json()
    mode = payload.get("mode", "free")
    category = (payload.get("category") or "").lower().strip()
    target_id = payload.get("target_id")
    query = payload.get("query") or ""

    conn = get_db_connection()
    cursor = conn.cursor()

    if mode == "category" and category:
        cursor.execute("SELECT * FROM reperti WHERE categoria = ?", (category,))
    else:
        cursor.execute("SELECT * FROM reperti")

    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if len(rows) < 2:
        return {"mode": mode, "matches": [], "message": "At least two archived 3D files are required."}

    profiles = [artifact_profile(row) for row in rows]
    query_tokens = tokenize(query)

    matches = []
    if mode == "specific":
        target_profile = next((profile for profile in profiles if profile["row"]["id"] == target_id), None)
        if not target_profile:
            raise HTTPException(status_code=404, detail="Selected archive item not found")

        for profile in profiles:
            if profile["row"]["id"] == target_id:
                continue
            comparison = compare_profiles(target_profile, profile)
            if query_tokens:
                query_overlap = len(query_tokens.intersection(profile["tokens"])) / max(len(query_tokens), 1)
                comparison["score"] = round(min(100, comparison["score"] + query_overlap * 12), 1)
            matches.append({
                "score": comparison["score"],
                "source": row_to_public(target_profile["row"]),
                "match": row_to_public(profile["row"]),
                "reasons": comparison["reasons"],
                "shared_terms": comparison["shared_terms"],
            })
    else:
        for left_index in range(len(profiles)):
            for right_index in range(left_index + 1, len(profiles)):
                left = profiles[left_index]
                right = profiles[right_index]
                comparison = compare_profiles(left, right)
                if query_tokens:
                    query_overlap = len(query_tokens.intersection(left["tokens"].union(right["tokens"]))) / max(len(query_tokens), 1)
                    comparison["score"] = round(min(100, comparison["score"] + query_overlap * 12), 1)
                matches.append({
                    "score": comparison["score"],
                    "source": row_to_public(left["row"]),
                    "match": row_to_public(right["row"]),
                    "reasons": comparison["reasons"],
                    "shared_terms": comparison["shared_terms"],
                })

    matches.sort(key=lambda item: item["score"], reverse=True)
    return {
        "mode": mode,
        "matches": matches[:20],
        "message": "Lightweight local scan completed. Scores are correlation hints, not definitive classifications."
    }

@app.get("/download/{file_id}")
async def download_file(file_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reperti WHERE id = ?", (file_id,))
    modello = cursor.fetchone()
    conn.close()

    if modello:
        return FileResponse(
            path=modello["percorso_file"],
            filename=modello["nome_originale"],
            media_type='application/octet-stream'
        )
    raise HTTPException(status_code=404, detail="File not found")

@app.delete("/modelli/{file_id}")
async def delete_model(file_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reperti WHERE id = ?", (file_id,))
    modello = cursor.fetchone()

    if not modello:
        conn.close()
        raise HTTPException(status_code=404, detail="Model not found")

    file_path = modello["percorso_file"]
    if os.path.exists(file_path):
        os.remove(file_path)

    if "metadata_path" in modello.keys() and modello["metadata_path"] and os.path.exists(modello["metadata_path"]):
        os.remove(modello["metadata_path"])

    cursor.execute("DELETE FROM reperti WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()

    return {"status": "deleted"}

@app.get("/downloadDocumentation")
async def download_documentation():
    documentation_path = os.path.join(BASE_DIR, "static", "files", "Argo_documentation.pdf")
    if os.path.exists(documentation_path):
        return FileResponse(path=documentation_path, filename="Argo_Documentation.pdf", media_type='application/pdf')
    return {"error": "File not found"}

@app.get("/downloadCVross")
async def download_cv_ross():
    cv_path = os.path.join(BASE_DIR, "static", "files", "Rossella_Fumai_CV.pdf")
    if os.path.exists(cv_path):
        return FileResponse(path=cv_path, filename="Rossella_Fumai_CV.pdf", media_type='application/pdf')
    return {"error": "File not found"}

@app.get("/downloadCVsimo")
async def download_cv_simo():
    cv_path = os.path.join(BASE_DIR, "static", "files", "Simone_Gismondi_CV.pdf")
    if os.path.exists(cv_path):
        return FileResponse(path=cv_path, filename="Simone_Gismondi_CV.pdf", media_type='application/pdf')
    return {"error": "File not found"}

@app.get("/downloadCVlilly")
async def download_cv_lilly():
    cv_path = os.path.join(BASE_DIR, "static", "files", "Liliana_Albanese_CV.pdf")
    if os.path.exists(cv_path):
        return FileResponse(path=cv_path, filename="Liliana_Albanese_CV.pdf", media_type='application/pdf')
    return {"error": "File not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
