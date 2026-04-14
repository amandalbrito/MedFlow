import threading
import time
import requests
import io
import random
import sys
import os

# --- CONFIGURAÇÕES DO CENÁRIO (5TB/DIA) ---
# Cálculo: 5TB = 5,242,880 MB.
# 5,242,880 MB / 86.400 segundos = ~60.68 MB/s necessários.
# Vamos definir a meta como 58 MB/s para ter uma margem segura.

API_URL = "http://127.0.0.1:8000" 
USER = "admin"
PASS = "admin123"

# Configuração de Carga
FILE_SIZE_MB = 5
TARGET_MB_S = 58.0        # Meta de vazão para atingir 5TB/dia
THREADS = 50              # Número de usuários simultâneos (ajuste conforme seu processador)
DURATION = 60             # Duração do teste em segundos

# --- MÉTRICAS GLOBAIS ---
total_bytes_sent = 0
total_requests = 0
success_count = 0
fail_count = 0
lock = threading.Lock()

def get_token():
    print(f"🔑 Autenticando em {API_URL}...")
    
    response = requests.post(f"{API_URL}/token", data={"username": USER, "password": PASS})
    if response.status_code == 200:
        print("✅ Token obtido com sucesso.")
        return response.json()["access_token"]
    sys.exit(1)

def worker(token, payload):
    global total_requests, success_count, fail_count, total_bytes_sent
    end_time = time.time() + DURATION
    headers = {"Authorization": f"Bearer {token}"}

    # OTIMIZAÇÃO CRÍTICA: Usar Session (Keep-Alive) evita reabrir conexão TCP a cada envio
    session = requests.Session()

    while time.time() < end_time:
        try:
            # Reutiliza o payload em memória (muito mais rápido que gerar novo arquivo)
            fake_file = io.BytesIO(payload)
            
            files = {'file': ('exam_simulation.dcm', fake_file, 'application/octet-stream')}
            data = {
                'patient_name': f'Paciente_{random.randint(1, 99999)}',
                'patient_cpf': f'{random.randint(10000000000, 99999999999)}',
                'exam_type': 'Tomografia'
            }

            # Usa a sessão mantida aberta
            r = session.post(f"{API_URL}/ingest", files=files, data=data, headers=headers, timeout=15)
            
            with lock:
                total_requests += 1
                total_bytes_sent += len(payload)
                if r.status_code == 200:
                    success_count += 1
                else:
                    fail_count += 1

        except Exception as e:
            with lock:
                fail_count += 1

def monitor():
    global total_requests, success_count, fail_count, total_bytes_sent
    
    print(f"\n⚡ Iniciando Simulação de Carga")
    print(f"🎯 Meta para 5TB/dia: Manter > {TARGET_MB_S} MB/s")
    print("-" * 80)
    print(f"{'Tempo(s)':<10} | {'Reqs':<8} | {'Sucesso':<8} | {'MB/s Atual':<12} | {'Status Meta':<15}")
    print("-" * 80)
    
    start_time = time.time()
    last_bytes = 0
    
    while time.time() - start_time < DURATION:
        time.sleep(1)
        elapsed = int(time.time() - start_time)
        
        with lock:
            current_bytes = total_bytes_sent
            
            # Calcula vazão do último segundo
            mb_sent_last_sec = (current_bytes - last_bytes) / (1024 * 1024)
            last_bytes = current_bytes
            
            # Verifica meta
            status_meta = "⚠️ ABAIXO" if mb_sent_last_sec < TARGET_MB_S else "✅ OK"
            
            print(f"{elapsed:<10} | {total_requests:<8} | {last_bytes:<8} | {mb_sent_last_sec:<12.2f} | {status_meta:<15}")

    # Relatório Final
    print("\n" + "="*40)
    total_mb = total_bytes_sent / (1024 * 1024)
    avg_mbps = (total_bytes_sent / DURATION) / (1024*1024)
    
    print(f"📊 RELATÓRIO FINAL")
    print(f"Total Enviado:   {total_mb:.2f} MB")
    print(f"Vazão Média:     {avg_mbps:.2f} MB/s")
    
    if avg_mbps >= TARGET_MB_S:
        print("🎉 RESULTADO: O sistema SUPORTA o volume de 5TB/dia!")
    else:
        print(f"⚠️ RESULTADO: O sistema NÃO SUPORTA.")
        print(f"   Faltam {TARGET_MB_S - avg_mbps:.2f} MB/s para atingir a meta.")

if __name__ == "__main__":
    # 1. Prepara o payload (Gera o arquivo UMA vez para economizar CPU)
    print(f"📦 Gerando arquivo de {FILE_SIZE_MB}MB em memória...")
    payload = os.urandom(1024 * 1024 * FILE_SIZE_MB)
    print("✅ Arquivo pronto.")
    
    token = get_token()
    
    # Inicia Monitor
    monitor_thread = threading.Thread(target=monitor)
    monitor_thread.start()
    
    # Inicia Threads de Carga
    threads = []
    print(f"🚀 Lançando {THREADS} threads simultâneas...")
    for _ in range(THREADS):
        t = threading.Thread(target=worker, args=(token, payload))
        t.start()
        threads.append(t)
    
    for t in threads:
        t.join()
    
    monitor_thread.join()