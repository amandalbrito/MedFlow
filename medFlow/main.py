import os
import shutil
from datetime import datetime
from typing import List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# --- Configuração ---
app = FastAPI(title="MedFlow Universal")

# Permite acesso de qualquer origem (Essencial para Web e Local)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://amandalbrito.github.io/MedFlow/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Diretório para salvar os exames
UPLOAD_DIR = "storage"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- Banco de Dados em Memória (Funciona local e na nuvem sem config) ---
fake_db = {
    "patients": {},
    "exams": [],
    "counters": {"patient_id": 1, "exam_id": 1}
}

# --- Modelos de Dados ---
class ExamResponse(BaseModel):
    id: int
    patient_name: str
    exam_type: str
    status: str
    upload_date: str

# --- Rotas da API ---

@app.post("/ingest")
async def ingest_exam(
    file: UploadFile = File(...),
    patient_name: str = Form(...),
    patient_cpf: str = Form(...),
    exam_type: str = Form(...)
):
    # Salva arquivo
    file_location = f"{UPLOAD_DIR}/{file.filename}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Lógica de Banco
    exam_id = fake_db["counters"]["exam_id"]
    new_exam = {
        "id": exam_id,
        "patient_name": patient_name,
        "exam_type": exam_type,
        "status": "pendente",
        "upload_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    fake_db["exams"].append(new_exam)
    fake_db["counters"]["exam_id"] += 1
    
    return {"message": "Exame ingerido com sucesso", "exam_id": exam_id}

@app.get("/exams", response_model=List[ExamResponse])
def list_exams():
    return fake_db["exams"]

@app.post("/exams/{exam_id}/laudo")
def finalize_exam(exam_id: int, laudo: str = Form(...)):
    for exam in fake_db["exams"]:
        if exam["id"] == exam_id:
            exam["status"] = "concluido"
            return {"message": "Laudo salvo"}
    raise HTTPException(status_code=404, detail="Exame não encontrado")

# --- Rota para servir o Frontend (Funciona na Web e Local) ---
@app.get("/")
async def read_root():
    # Retorna o arquivo HTML quando acessa a raiz do site
    return FileResponse('index.html')
