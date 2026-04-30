import paho.mqtt.client as mqtt
import ssl
import time

# --- CONFIGURATION ---
HAPROXY_IP = "192.168.197.129"
SECURE_PORT = 8883  # Cổng SSL trên HAProxy
TOPIC = "lab/tls_offloading"
USER = "user1"
PASS = "123"

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("✅ [Client] Connected to HAProxy via SSL/TLS (Port 8883)")
        client.subscribe(TOPIC)
    else:
        print(f"❌ Connection failed with code {rc}")

def on_message(client, userdata, msg):
    print(f"📩 [Broker Response] Received message: {msg.payload.decode()} on topic {msg.topic}")

# Khởi tạo client
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id="TLS_Offload_Demo")
client.username_pw_set(USER, PASS)
client.on_connect = on_connect
client.on_message = on_message

# --- CẤU HÌNH TLS CHO CLIENT ---
# Client BẮT BUỘC phải dùng TLS vì HAProxy đang yêu cầu ở cổng 8883
client.tls_set(cert_reqs=ssl.CERT_NONE)
client.tls_insecure_set(True)

try:
    print(f"🚀 Connecting to HAProxy at {HAPROXY_IP}:{SECURE_PORT}...")
    client.connect(HAPROXY_IP, SECURE_PORT, 60)
    
    client.loop_start()
    
    # Gửi tin nhắn test
    for i in range(3):
        message = f"TLS Offloading Test - Message {i+1}"
        print(f"📤 Sending: {message}")
        client.publish(TOPIC, message)
        time.sleep(2)
        
    client.loop_stop()
    client.disconnect()
    print("🏁 Demo finished.")

except Exception as e:
    print(f"❌ Error: {e}")