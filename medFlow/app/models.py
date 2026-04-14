from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel
import enum

class RoleEnum(str, enum.Enum):
    admin = "admin"
    medico = "medico"
    recepcao = "recepcao"

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str
    role: RoleEnum = Field(default=RoleEnum.medico)

class Exam(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_name: str
    patient_cpf: str
    exam_type: str
    status: str = Field(default="pendente")
    file_path: str
    upload_date: datetime = Field(default_factory=datetime.utcnow)

class UserCreate(SQLModel):
    username: str
    password: str
    role: RoleEnum

class Token(SQLModel):
    access_token: str
    token_type: str

class ExamRead(SQLModel):
    id: int
    patient_name: str
    exam_type: str
    status: str
    upload_date: datetime