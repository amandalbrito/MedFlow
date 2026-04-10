import os
import shutil
import time
import threading
from datetime import datetime
from typing import List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="MedFlow Universal com Stress Test")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "storage"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- Banco de Dados e Métricas em Memória ---
fake_db = {"patients": {}, "exams": [], "counters": {"patient_id": 1, "exam_id": 1}}

# Contadores para o Stress Test
app.state.request_count = 0
app.state.start_time = time.time()

# Modelos
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
    # Incrementa contador de requisições (para o stress test)
    app.state.request_count += 1
    
    # Simula processamento leve
    file_location = f"{UPLOAD_DIR}/{file.filename}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
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
    
    # Mantém apenas os últimos 50 exames na lista para não estourar a memória do Render
    if len(fake_db["exams"]) > 50:
        fake_db["exams"] = fake_db["exams"][-50:]
        
    return {"message": "Exame ingerido", "exam_id": exam_id}

@app.get("/exams", response_model=List[ExamResponse])
def list_exams():
    app.state.request_count += 1
    return fake_db["exams"]

@app.post("/exams/{exam_id}/laudo")
def finalize_exam(exam_id: int, laudo: str = Form(...)):
    app.state.request_count += 1
    for exam in fake_db["exams"]:
        if exam["id"] == exam_id:
            exam["status"] = "concluido"
            return {"message": "Laudo salvo"}
    raise HTTPException(status_code=404, detail="Exame não encontrado")

# --- Rotas de Monitoramento (Para o Stress Test) ---

@app.get("/stats")
def get_stats():
    """Retorna métricas para o painel de stress."""
    elapsed = time.time() - app.state.start_time
    rpm = 0
    if elapsed > 0:
        rpm = (app.state.request_count / elapsed) * 60
    
    return {
        "total_requests": app.state.request_count,
        "uptime_seconds": round(elapsed, 2),
        "requests_per_minute": round(rpm, 2),
        "active_exams_in_memory": len(fake_db["exams"])
    }

@app.post("/reset-stats")
def reset_stats():
    """Reseta os contadores do stress test."""
    app.state.request_count = 0
    app.state.start_time = time.time()
    return {"status": "resetado"}

@app.get("/")
async def read_root():
    return FileResponse('index.html')
