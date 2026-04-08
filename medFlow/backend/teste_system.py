import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
import os
import sys

# Importa o app do arquivo main.py criado anteriormente
# (Assumindo que main.py está na mesma pasta)
from main import app, get_db, UPLOAD_DIR

# --- Fixtures: Preparação do Ambiente ---

@pytest.fixture(scope="module")
def test_client():
    """Cria um cliente de teste para simular requisições HTTP."""
    with TestClient(app) as client:
        yield client

@pytest.fixture(scope="function")
def mock_db(monkeypatch):
    """
    Mocka o banco de dados para não estragar o banco real durante os testes.
    Simula respostas do banco de dados.
    """
    class MockCursor:
        def __init__(self):
            self.data = []
            self.rowcount = 1
        
        def execute(self, query, params=None):
            # Simula busca de paciente existente
            if "SELECT id FROM patients" in query:
                self.fetchone = lambda: {'id': 1}
            # Simula inserção
            elif "INSERT" in query:
                pass
        
        def fetchone(self):
            return {'id': 1}
            
        def fetchall(self):
            return [
                {'id': 1, 'patient_name': 'Paciente Teste', 'exam_type': 'Tomografia', 'status': 'pendente', 'upload_date': '2023-01-01'}
            ]

    class MockConn:
        def cursor(self):
            return MockCursor()
        def commit(self):
            pass
    
    def override_get_db():
        yield MockConn()
    
    # Injeta o mock no sistema
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides = {}

# --- Testes ---

def test_fluxo_ingestao_seguranca(test_client, mock_db, tmp_path):
    """
    Testa o Passo 1 e 2: Ingestão e Segurança.
    Verifica se o sistema aceita o arquivo e se valida os dados.
    """
    # Cria um arquivo falso para simular o exame
    fake_file_content = b"dados_binarios_fake_do_dicom"
    fake_file_path = os.path.join(tmp_path, "exame.dcm")
    
    with open(fake_file_path, "wb") as f:
        f.write(fake_file_content)

    # Tenta fazer upload
    with open(fake_file_path, "rb") as f:
        response = test_client.post(
            "/ingest",
            files={"file": ("exame.dcm", f, "application/octet-stream")},
            data={
                "patient_name": "Paciente Seguro",
                "patient_cpf": "12345678900",
                "exam_type": "Raio-X"
            }
        )
    
    assert response.status_code == 200
    assert "Exame ingerido" in response.json()["message"]
    
    # Verifica se o arquivo foi salvo (Simulação de Persistência)
    assert os.path.exists(os.path.join(UPLOAD_DIR, "exame.dcm"))

def test_fluxo_medico_listagem(test_client, mock_db):
    """
    Testa o Passo 3: Fluxo ao Médico.
    Médico deve ver apenas exames pendentes.
    """
    response = test_client.get("/exams")
    
    assert response.status_code == 200
    data = response.json()
    
    # Valida se retornou a lista e se o status está correto
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]['status'] == 'pendente'
    assert data[0]['patient_name'] == 'Paciente Teste'

def test_fluxo_finalizacao_laudo(test_client, mock_db):
    """
    Testa a finalização do exame pelo médico.
    """
    response = test_client.post(
        "/exams/1/laudo",
        data={"laudo": "Tudo normal."}
    )
    
    assert response.status_code == 200
    assert "finalizado" in response.json()["message"]