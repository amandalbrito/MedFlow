import os
import aiofiles
import time
from typing import List
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import SQLModel, Session, select, create_engine

from app.models import User, Exam, UserCreate, Token, ExamRead, RoleEnum
from app.security import verify_password, get_password_hash, create_access_token, decode_token, oauth2_scheme
from app.config import settings

# --- Banco de Dados ---
engine = create_engine(settings.DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

# Evento para configurar o SQLite para alta performance (WAL Mode)
from sqlalchemy import event

@event.listens_for(engine, "connect")
def set_sqllite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    # WAL Mode: Permite leitura e escrita simultânea (mais rápido)
    cursor.execute("PRAGMA journal_mode=WAL;")
    # NORMAL: Escreve no disco a cada comando, não a cada byte (mais arriscado em queda de energia, mas 10x mais rápido)
    cursor.execute("PRAGMA synchronous=NORMAL;")
    # Aumenta o cache em memória (em KB)
    cursor.execute("PRAGMA cache_size=-64000")
    cursor.close()

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    
    # LÓGICA ADICIONADA: Criar admin padrão se não existir
    with Session(engine) as session:
        admin = session.exec(select(User).where(User.username == "admin")).first()
        if not admin:
            hashed_pw = get_password_hash("admin123")
            admin_user = User(username="admin", hashed_password=hashed_pw, role=RoleEnum.admin)
            session.add(admin_user)
            session.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(title="MedFlow Pro", lifespan=lifespan)

# CORS
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Dependências ---
def get_session():
    with Session(engine) as session:
        yield session

def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    payload = decode_token(token)
    if payload is None: raise credentials_exception
    username: str = payload.get("sub")
    if username is None: raise credentials_exception
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None: raise credentials_exception
    return user

def require_role(roles: List[RoleEnum]):
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Operação não permitida")
        return current_user
    return role_checker

# --- Métricas ---
app.state.request_count = 0
app.state.start_time = time.time()

# --- Rotas ---

# --- Rotas de Autenticação ---
@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    # CORREÇÃO: Usar a sessão injetada, não criar uma nova
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/users/", status_code=201)
def create_user(user: UserCreate, current_user: User = Depends(require_role([RoleEnum.admin])), session: Session = Depends(get_session)):
    # CORREÇÃO: Usar a sessão injetada
    db_user = User(
        username=user.username,
        hashed_password=get_password_hash(user.password),
        role=user.role
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return {"id": db_user.id, "username": db_user.username}

UPLOAD_DIR = "storage"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/ingest")
async def ingest_exam(file: UploadFile = File(...), patient_name: str = Form(...), patient_cpf: str = Form(...), exam_type: str = Form(...), current_user: User = Depends(require_role([RoleEnum.admin, RoleEnum.recepcao])), session: Session = Depends(get_session)):
    app.state.request_count += 1
    safe_filename = os.path.basename(file.filename)
    file_location = os.path.join(UPLOAD_DIR, safe_filename)
    async with aiofiles.open(file_location, 'wb') as out_file:
        await out_file.write(await file.read())
    new_exam = Exam(patient_name=patient_name, patient_cpf=patient_cpf, exam_type=exam_type, file_path=file_location)
    session.add(new_exam)
    session.commit()
    session.refresh(new_exam)
    return {"message": "Exame salvo", "id": new_exam.id}

@app.get("/exams", response_model=List[ExamRead])
def list_exams(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return session.exec(select(Exam).order_by(Exam.upload_date.desc()).limit(50)).all()

@app.post("/exams/{exam_id}/laudo")
def finalize_exam(exam_id: int, current_user: User = Depends(require_role([RoleEnum.medico])), session: Session = Depends(get_session)):
    exam = session.get(Exam, exam_id)
    if not exam: raise HTTPException(status_code=404, detail="Exame não encontrado")
    exam.status = "concluido"
    session.add(exam)
    session.commit()
    return {"status": "success"}

@app.get("/stats")
def get_stats():
    elapsed = time.time() - app.state.start_time
    rpm = (app.state.request_count / elapsed) * 60 if elapsed > 0 else 0
    return {"total_requests": app.state.request_count, "uptime_seconds": round(elapsed, 2), "requests_per_minute": round(rpm, 2)}

@app.get("/")
def read_root():
    return FileResponse('../index.html')