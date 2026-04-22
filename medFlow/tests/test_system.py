import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app, get_session
from app.models import User, RoleEnum
from app.security import get_password_hash

# Configuração do Banco de Dados em Memória
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# --- Fixtures ---
@pytest.fixture(name="session")
def session_fixture():
    """Cria o banco de dados em memória para cada teste."""
    SQLModel.metadata.drop_all(engine) 
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # Cria usuários padrão para testes
        user_medico = User(username="medico_teste", hashed_password=get_password_hash("senha123"), role=RoleEnum.medico)
        user_admin = User(username="admin_teste", hashed_password=get_password_hash("admin123"), role=RoleEnum.admin)
        user_recepcao = User(username="recep_teste", hashed_password=get_password_hash("senha123"), role=RoleEnum.recepcao)
        
        session.add(user_medico)
        session.add(user_admin)
        session.add(user_recepcao)
        session.commit()
        yield session

@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Cria o cliente de teste e sobrescreve a dependência do banco."""
    def override_get_session():
        yield session
    
    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

# --- Testes de Autenticação e Segurança ---

def test_login_sucesso(client: TestClient):
    """Testa login válido."""
    response = client.post("/token", data={"username": "medico_teste", "password": "senha123"})
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_login_falha(client: TestClient):
    """Testa login com senha errada."""
    response = client.post("/token", data={"username": "medico_teste", "password": "errada"})
    assert response.status_code == 401

def test_acesso_sem_token(client: TestClient):
    """Testa bloqueio de rota protegida sem token."""
    response = client.get("/exams")
    assert response.status_code == 401

# --- Testes de Controle de Acesso (RBAC) ---

def test_medico_pode_ver_exames(client: TestClient):
    """Médico deve ter acesso de leitura."""
    # Login
    login = client.post("/token", data={"username": "medico_teste", "password": "senha123"})
    token = login.json()["access_token"]
    
    # Acesso
    response = client.get("/exams", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

def test_recepcao_pode_subir_exame(client: TestClient):
    """Recepção deve ter permissão de escrita (ingest)."""
    # Login
    login = client.post("/token", data={"username": "recep_teste", "password": "senha123"})
    token = login.json()["access_token"]
    
    # Upload
    file_content = b"fake_dicom_content"
    response = client.post(
        "/ingest",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("teste.dcm", file_content, "application/octet-stream")},
        data={"patient_name": "Paciente", "patient_cpf": "123", "exam_type": "RX"}
    )
    assert response.status_code == 200

def test_medico_nao_pode_subir_exame(client: TestClient):
    """Médico NÃO deve ter permissão de escrita (ingest) - Regra de Negócio."""
    # Login
    login = client.post("/token", data={"username": "medico_teste", "password": "senha123"})
    token = login.json()["access_token"]
    
    # Tentativa de Upload (deve falhar com 403 Forbidden)
    file_content = b"fake_dicom_content"
    response = client.post(
        "/ingest",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("teste.dcm", file_content, "application/octet-stream")},
        data={"patient_name": "Paciente", "patient_cpf": "123", "exam_type": "RX"}
    )
    assert response.status_code == 403 # Forbidden