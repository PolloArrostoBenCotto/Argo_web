from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uuid
import os
import sqlite3

app = FastAPI()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Montiamo la cartella degli statici per CSS e Font
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Configuriamo Jinja2 per leggere i file HTML nella cartella templates
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

UPLOAD_DIR = os.path.join(BASE_DIR, "archived_files")
os.makedirs(UPLOAD_DIR, exist_ok=True)
DB_PATH = os.path.join(BASE_DIR, "archivio.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def inizializza_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reperti (
            id TEXT PRIMARY KEY,
            titolo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            data_scoperta TEXT,
            note TEXT,
            percorso_file TEXT NOT NULL,
            nome_originale TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

inizializza_db()

def has_column(table_name: str, column_name: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row["name"] for row in cursor.fetchall()]
    conn.close()
    return column_name in columns

@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    # Rende la pagina principale (Landing Page)
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/archivio", response_class=HTMLResponse)
async def archivio_page(request: Request):
    # Rende la pagina di gestione dei file .PLY
    return templates.TemplateResponse("archivio.html", {"request": request})

@app.post("/upload")
async def upload_file(
    titolo: str = Form(...),
    categoria: str = Form(...),
    data_scoperta: str = Form(None),
    note: str = Form(None),
    file_3d: UploadFile = File(...)
):
    file_id = str(uuid.uuid4())
    file_extension = os.path.splitext(file_3d.filename)[1]
    salvaged_name = f"{file_id}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, salvaged_name)
    
    with open(file_path, "wb") as buffer:
        buffer.write(await file_3d.read())

    nuovo_modello = {
        "id": file_id,
        "titolo": titolo,
        "categoria": categoria.lower().strip(),
        "data_scoperta": data_scoperta,
        "note": note,
        "percorso_file": file_path,
        "nome_originale": file_3d.filename
    }

    conn = get_db_connection()
    cursor = conn.cursor()
    if has_column("reperti", "filename"):
        cursor.execute(
            """
            INSERT INTO reperti (
                id, titolo, categoria, data_scoperta, note, percorso_file, nome_originale, filename
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                nuovo_modello["id"],
                nuovo_modello["titolo"],
                nuovo_modello["categoria"],
                nuovo_modello["data_scoperta"],
                nuovo_modello["note"],
                nuovo_modello["percorso_file"],
                nuovo_modello["nome_originale"],
                salvaged_name,
            )
        )
    else:
        cursor.execute(
            """
            INSERT INTO reperti (
                id, titolo, categoria, data_scoperta, note, percorso_file, nome_originale
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                nuovo_modello["id"],
                nuovo_modello["titolo"],
                nuovo_modello["categoria"],
                nuovo_modello["data_scoperta"],
                nuovo_modello["note"],
                nuovo_modello["percorso_file"],
                nuovo_modello["nome_originale"],
            )
        )
    conn.commit()
    conn.close()

    return {"status": "success", "data": nuovo_modello}

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

    cursor.execute("DELETE FROM reperti WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()

    return {"status": "deleted"}

@app.get("/downloadDocumentation")
async def download_documentation():
    documentation_path = os.path.join(BASE_DIR, "static", "Argo_documentation.pdf")
    if os.path.exists(documentation_path):
        return FileResponse(path=documentation_path, filename="Argo_Documentation.pdf", media_type='application/pdf')
    return {"error": "File not found"}
