import time
import threading
import requests
import io
import random

# CONFIGURAÇÕES DO CENÁRIO REAL
API_URL = "http://localhost:8000/ingest"
TARGET_MB_PER_SECOND = 58  # Meta para 5TB/dia (aprox 58MB/s)
FILE_SIZE_MB = 10          # Tamanho de cada exame simulado
CONCURRENT_THREADS = 10    # Quantos uploads ao mesmo tempo

def generate_dummy_file(size_mb):
    """Gera dados binários em memória (mais rápido que disco)"""
    # Gera bytes aleatórios para simular o peso de uma imagem DICOM
    return io.BytesIO(os.urandom(size_mb * 1024 * 1024))

def worker(thread_id, results):
    """
    Função que roda em cada thread: simula uma máquina de exames enviando dados.
    """
    while True:
        try:
            # Prepara o arquivo "falso"
            dummy_file = generate_dummy_file(FILE_SIZE_MB)
            
            payload = {
                'patient_name': f'Paciente_Thread_{thread_id}',
                'patient_cpf': f'000{thread_id}{random.randint(100,999)}',
                'exam_type': 'Tomografia'
            }
            
            files = {'file': ('exame_simulado.dcm', dummy_file, 'application/octet-stream')}
            
            # Mede a LATÊNCIA
            start_time = time.time()
            response = requests.post(API_URL, files=files, data=payload, timeout=30)
            end_time = time.time()
            
            latency = end_time - start_time
            throughput = (FILE_SIZE_MB / latency) # MB/s dessa requisição
            
            results.append({
                'status': response.status_code,
                'latency': latency,
                'throughput': throughput
            })
            
            # Simula um intervalo entre exames de uma mesma máquina
            time.sleep(0.1) 
            
        except Exception as e:
            print(f"Erro na Thread {thread_id}: {e}")
            time.sleep(1)

def monitor(results):
    """
    Monitora se estamos atingindo a meta de 5TB/dia.
    """
    print(f"--- INICIANDO SIMULAÇÃO DE CARGA ---")
    print(f"Meta: {TARGET_MB_PER_SECOND} MB/s (equivalente a 5TB/dia)")
    print(f"Simulando: {CONCURRENT_THREADS} máquinas enviando exames de {FILE_SIZE_MB}MB simultaneamente.")
    
    while True:
        time.sleep(5) # Relatório a cada 5 segundos
        
        if not results:
            continue
            
        # Calcula médias dos últimos segundos
        recent_results = results[-50:] # Pega os últimos 50 resultados
        
        avg_latency = sum(r['latency'] for r in recent_results) / len(recent_results)
        total_throughput = sum(r['throughput'] for r in recent_results)
        
        print(f"\n[RELATÓRIO] Threads Ativas: {threading.active_count()}")
        print(f"Latência Média: {avg_latency:.4f} segundos")
        print(f"Vazão Atual: {total_throughput:.2f} MB/s")
        
        # Discussão sobre latência
        if total_throughput < TARGET_MB_PER_SECOND:
            print("⚠️  ALERTA: Vazão abaixo da meta. Considere aumentar threads ou otimizar rede.")
        else:
            print("✅ Sistema suportando a carga de 5TB/dia com sucesso.")

if __name__ == "__main__":
    import os # Necessário para urandom
    
    results = []
    
    # Inicia o monitor em uma thread separada
    threading.Thread(target=monitor, args=(results,), daemon=True).start()
    
    # Inicia os "trabalhadores" (Máquinas de exame)
    threads = []
    for i in range(CONCURRENT_THREADS):
        t = threading.Thread(target=worker, args=(i, results))
        t.daemon = True
        t.start()
        threads.append(t)
    
    # Mantém o script rodando
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nSimulação interrompida.")