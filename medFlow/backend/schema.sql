CREATE DATABASE medflow;

USE medflow;

-- Crie um banco de dados chamado 'medflow'

-- Tabela de Usuários (Médicos e Admins)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL, -- Em produção usar bcrypt
    role VARCHAR(20) NOT NULL CHECK (role IN ('medico', 'admin', 'recepcao'))
);

-- Tabela de Pacientes
CREATE TABLE patients (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    cpf VARCHAR(11) UNIQUE NOT NULL,
    birth_date DATE NOT NULL
);

-- Tabela de Exames (Metadados)
CREATE TABLE exams (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id),
    doctor_id INTEGER REFERENCES users(id),
    exam_type VARCHAR(50) NOT NULL, -- Ex: Tomografia, Ressonância
    status VARCHAR(20) DEFAULT 'pendente' CHECK (status IN ('pendente', 'processando', 'concluido')),
    file_path VARCHAR(255) NOT NULL, -- Caminho no Storage (S3 ou Disco Local)
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    anonymized BOOLEAN DEFAULT FALSE
);

-- Índices para performance (Essencial para grandes volumes)
CREATE INDEX idx_exams_status ON exams(status);
CREATE INDEX idx_exams_patient ON exams(patient_id);
