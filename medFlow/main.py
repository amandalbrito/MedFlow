import os
import shutil
from datetime import datetime
from typing import List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- Configuração do App ---
app = FastAPI(title="MedFlow API - Modo Demo")

# CORREÇÃO DO CORS: Permite qualquer origem (Ideal para desenvolvimento)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permite o front-end (127.0.0.1:5500)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Diretório para salvar os exames
UPLOAD_DIR = "storage"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- Simulação de Banco de Dados em Memória ---
# (Isso resolve o erro 500 de conexão com banco real)
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

# --- Rotas ---

@app.post("/ingest")
async def ingest_exam(
    file: UploadFile = File(...),
    patient_name: str = Form(...),
    patient_cpf: str = Form(...),
    exam_type: str = Form(...)
):
    """Recebe o exame e salva metadados na memória."""
    
    # 1. Salva o arquivo físico
    file_location = f"{UPLOAD_DIR}/{file.filename}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 2. Lógica simulada de Banco de Dados
    patient_id = fake_db["counters"]["patient_id"]
    fake_db["patients"][patient_cpf] = {"id": patient_id, "name": patient_name}
    fake_db["counters"]["patient_id"] += 1
    
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
    
    return {"message": "Exame ingerido com sucesso", "file_size": file.size, "exam_id": exam_id}


@app.get("/exams", response_model=List[ExamResponse])
def list_exams():
    """Retorna a lista de exames para o médico."""
    # Retorna apenas os dados formatados que o front espera
    return fake_db["exams"]


@app.post("/exams/{exam_id}/laudo")
def finalize_exam(exam_id: int, laudo: str = Form(...)):
    """Finaliza o exame."""
    for exam in fake_db["exams"]:
        if exam["id"] == exam_id:
            exam["status"] = "concluido"
            return {"message": "Laudo salvo e exame finalizado"}
    
    raise HTTPException(status_code=404, detail="Exame não encontrado")