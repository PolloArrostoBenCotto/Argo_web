from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uuid
import os

app = FastAPI()

# Montiamo la cartella degli statici per CSS e Font
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configuriamo Jinja2 per leggere i file HTML nella cartella templates
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "archived_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Database finto in memoria
modelli_db = []

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
        "categoria": categoria,
        "data_scoperta": data_scoperta,
        "note": note,
        "filename": salvaged_name
    }
    modelli_db.append(nuovo_modello)
    return {"status": "success", "data": nuovo_modello}

@app.get("/modelli")
async def lista_modelli(categoria: str = None):
    if categoria:
        return [m for m in modelli_db if m["categoria"] == categoria]
    return modelli_db

@app.get("/download/{file_id}")
async def download_file(file_id: str):
    modello = next((m for m in modelli_db if m["id"] == file_id), None)
    if modello:
        file_path = os.path.join(UPLOAD_DIR, modello["filename"])
        return FileResponse(path=file_path, filename=f"{modello['titolo']}.ply", media_type='application/octet-stream')
    return {"error": "File not found"}

@app.delete("/modelli/{file_id}")
async def delete_model(file_id: str):
    modello = next((m for m in modelli_db if m["id"] == file_id), None)
    if not modello:
        raise HTTPException(status_code=404, detail="Model not found")

    file_path = os.path.join(UPLOAD_DIR, modello["filename"])
    if os.path.exists(file_path):
        os.remove(file_path)

    modelli_db.remove(modello)
    return {"status": "deleted"}

@app.get("/downloadDocumentation")
async def download_documentation():
    documentation_path = os.path.join("static", "Argo_documentation.pdf")
    if os.path.exists(documentation_path):
        return FileResponse(path=documentation_path, filename="Argo_Documentation.pdf", media_type='application/pdf')
    return {"error": "File not found"}
