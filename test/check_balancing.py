import paho.mqtt.client as mqtt
import time
import ssl

# --- Cấu hình ---
HAPROXY_IP = "192.168.197.129"
PORT = 8883
PASSWORD = "123"
# Danh sách user theo thứ tự bạn yêu cầu
USERS = ["bal1", "bal2", "bal1", "bal2"]

def run_test():
    for i, username in enumerate(USERS):
        client_id = f"Client_Step_{i+1}_{username}"
        
        # Khởi tạo client (sử dụng callback_api_version mới nhất)
        client = mqtt.Client(client_id=client_id, callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        client.username_pw_set(username, PASSWORD)
        
        # Thiết lập SSL/TLS để làm việc với cổng 8883 của HAProxy
        # cert_reqs=ssl.CERT_NONE giúp bỏ qua việc kiểm tra chứng chỉ (phù hợp cho môi trường Lab)
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)

        try:
            print(f"🔄 Bước {i+1}: Đang kết nối với USER: {username}...")
            client.connect(HAPROXY_IP, PORT, 60)
            
            client.loop_start()
            # Gửi tin nhắn để HAProxy và Broker ghi nhận traffic
            client.publish("demo/rotation", f"Hello from {username} at step {i+1}")
            
            # Chờ một chút để HAProxy xử lý và ghi log
            time.sleep(1) 
            
            client.disconnect()
            client.loop_stop()
            print(f"✅ Bước {i+1} hoàn tất. Đã ngắt kết nối.\n")
            
        except Exception as e:
            print(f"❌ Lỗi ở bước {i+1} ({username}): {e}")
        
        # Khoảng nghỉ ngắn giữa các lần kết nối để HAProxy phân phối Round Robin chuẩn xác
        time.sleep(0.5)

if __name__ == "__main__":
    print("🚀 Bắt đầu kiểm tra luân phiên HAProxy...")
    run_test()
    print("🏁 Kiểm tra kết thúc.")