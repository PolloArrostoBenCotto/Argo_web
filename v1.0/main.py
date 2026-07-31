from fastapi.responses import HTMLResponse
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
import shutil
import uuid
import sqlite3

app = FastAPI(title="ARGOchivio")
app.mount("/files", StaticFiles(directory="templates/files"), name="files")

UPLOAD_DIR = "./archivio_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)
DB_PATH = "archivio.db"

# Funzione per connettersi al database e creare la tabella se non esiste
def inizializza_db():
    conn = sqlite3.connect(DB_PATH)
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

# Inizializziamo il database all'avvio
inizializza_db()

@app.post("/upload")
async def upload_modello(
    titolo: str = Form(...),
    categoria: str = Form(...),
    data_scoperta: str = Form(""),
    note: str = Form(""),
    file_3d: UploadFile = File(...)
):
    '''
    if not file_3d.filename.endswith('.ply'):
        raise HTTPException(status_code=400, detail="Formato non supportato. Caricare solo file .ply")
    '''
    file_id = str(uuid.uuid4())
    nome_file_sicuro = f"{file_id}.ply"
    percorso_salvataggio = os.path.join(UPLOAD_DIR, nome_file_sicuro)

    with open(percorso_salvataggio, "wb") as buffer:
        shutil.copyfileobj(file_3d.file, buffer)

    # SALVATAGGIO NEL DATABASE SQLITE
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO reperti (id, titolo, categoria, data_scoperta, note, percorso_file, nome_originale) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (file_id, titolo, categoria.lower().strip(), data_scoperta, note, percorso_salvataggio, file_3d.filename)
    )
    conn.commit()
    conn.close()

    return {"status": "Successo", "id_generato": file_id}

@app.get("/modelli")
async def ottieni_modelli(categoria: str = None):
    conn = sqlite3.connect(DB_PATH)
    # Trasformiamo i risultati in dizionari leggibili
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    
    if categoria:
        cursor.execute("SELECT * FROM reperti WHERE categoria = ?", (categoria.lower().strip(),))
    else:
        cursor.execute("SELECT * FROM reperti")
        
    righe = cursor.fetchall()
    conn.close()
    
    # Convertiamo il formato di SQLite in una lista JSON classica
    risultati = [dict(riga) for riga in righe]
    return risultati

@app.get("/download/{file_id}")
async def scarica_file(file_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reperti WHERE id = ?", (file_id,))
    reperto = cursor.fetchone()
    conn.close()

    if reperto:
        return FileResponse(
            path=reperto["percorso_file"], 
            filename=reperto["nome_originale"], 
            media_type='application/octet-stream'
        )
    raise HTTPException(status_code=404, detail="Model not found")

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("templates/index1.3.html", "r", encoding="utf-8") as f:
        return f.read()