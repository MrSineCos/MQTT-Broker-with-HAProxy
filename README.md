# MQTT & HAProxy Lab Setup

Hướng dẫn thiết lập và kiểm thử hệ thống MQTT Broker (Mosquitto) kết hợp HAProxy để thực hiện cân bằng tải (Load Balancing) và xử lý SSL/TLS (TLS Offloading).

## 1. Cấu trúc thư mục

```text
mqtt-haproxy/
├── docker-compose.yml
├── README.md
├── ca-authority/             <-- Thư mục giả lập đại diện của cơ quan CA (Cất kỹ ca.key ở đây)
│   ├── ca.crt                <-- Chứng chỉ gốc (Copy file này gửi cho Client)
│   ├── ca.key                <-- Khóa bí mật của CA (Tuyệt đối không chia sẻ)
│   ├── ca.srl                <-- File quản lý số thứ tự chứng chỉ
│   └── server-requests/      <-- Nơi lưu trữ các file .csr (Tùy chọn)
│
├── haproxy/
│   ├── haproxy.cfg
│   └── certs/
│       └── mqtt.pem          <-- Gộp từ server.crt + server.key
│
├── mosquitto/
│   ├── mosquitto.conf
│   ├── passwd
│   ├── certs/                <-- Dùng khi test Mosquitto TLS trực tiếp
│   │   ├── ca.crt
│   │   ├── server.crt
│   │   └── server.key
│   ├── data/
│   └── log/
│
└── test/                     <-- Scripts benchmark (Python, Go, hoặc JMeter)
```

## 2. Tạo chứng chỉ cho server trong môi trường giả lập

### Giai đoạn 1: Đóng giả làm cơ quan cấp chứng chỉ (CA)
Tạo khóa bí mật của CA và tự ký tạo chứng chỉ gốc:
```bash
openssl genrsa -out ca.key 2048
openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 -out ca.crt
```

### Giai đoạn 2: Tạo chứng chỉ và khóa bí mật cho Broker và Proxy
1. Di chuyển đến thư mục `ca-authority`.
2. Tạo private key cho server:
```bash
openssl genrsa -out server.key 2048
```
*(Nếu muốn tự cấp chứng chỉ trực tiếp thay vì qua CA thì chạy lệnh: `openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout server.key -out server.crt` và nhảy sang bước 5)*

3. Tạo đơn yêu cầu chứng chỉ (CSR):
```bash
openssl req -new -out server.csr -key server.key -subj "/CN=<IP_Của_Server>"
```
4. Ký chứng chỉ bằng chứng chỉ CA từ Giai đoạn 1:
```bash
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 365
```
5. Gộp khóa bí mật và chứng chỉ để dùng cho HAProxy:
```bash
sudo cat server.crt server.key | sudo tee mqtt.pem > /dev/null
```
6. Phân phối các file:
- Đưa `mqtt.pem` vào thư mục `./haproxy/certs`.
- Đưa `ca.crt`, `server.crt`, `server.key` vào `./mosquitto/certs`.


## 3. Thiết lập quyền truy cập (File Permissions)

**Mosquitto (Cho tài khoản mặc định 1883)**
```bash
# Chuyển quyền sở hữu thư mục mosquitto cho user 1883
sudo chown -R 1883:1883 ./mosquitto

# Phân quyền cho file mật khẩu và thư mục chứng chỉ
sudo chmod 700 ./mosquitto/passwd
sudo chmod 755 ./mosquitto/certs
sudo chmod 644 ./mosquitto/certs/ca.crt
sudo chmod 644 ./mosquitto/certs/server.crt
sudo chmod 600 ./mosquitto/certs/server.key

# Đảm bảo các thư mục dữ liệu và log có quyền ghi mở rộng
sudo chmod -R 755 ./mosquitto/data ./mosquitto/data2
sudo chmod -R 755 ./mosquitto/log ./mosquitto/log2
```

**HAProxy & Máy trạm CA**
```bash
# Đổi về chủ sở hữu người dùng hiện tại
sudo chown -R sine:sine ./haproxy ./ca-authority ./test

# Quyền cho file chứng chỉ HAProxy
sudo chmod 644 ./haproxy/certs/mqtt.pem

# Bảo vệ toàn diện cho CA gốc
sudo chmod 700 ./ca-authority
sudo chmod 600 ./ca-authority/ca.key
sudo chmod 644 ./ca-authority/ca.crt
```

**Scripts test**
```bash
chmod +x ./test/*.py
```

## 4. Chạy dịch vụ với Docker Compose

1. Copy các file mẫu, chỉnh sửa thông số/ports tương ứng trong `docker-compose.yml` (hoặc `docker-compose-no-proxy.yml`).
2. Dọn dẹp sạch sẽ các container và lỗi cũ:
```bash
sudo docker compose down
```
3. Khởi chạy Docker:
```bash
sudo docker compose up -d
```
4. Kiểm tra dịch vụ:
```bash
sudo docker compose ps
```

*Một câu lệnh restart container nhanh tiết kiệm thời gian khởi động:*
```bash
sudo docker restart mqtt_broker mqtt_broker_2
```

## 5. Quản lý người dùng MQTT

Khởi tạo các tài khoản kết nối cho MQTT client bên trong container `mqtt_broker`:
```bash
sudo docker exec mqtt_broker mosquitto_passwd -b /mosquitto/config/passwd user1 123
sudo docker exec mqtt_broker mosquitto_passwd -b /mosquitto/config/passwd bal1 123
sudo docker exec mqtt_broker mosquitto_passwd -b /mosquitto/config/passwd bal2 123
```
*Ghi chú: Danh sách account mẫu ở trên đều sử dụng chung mức mật khẩu là `123`*

## 6. Xem log hệ thống

- **Log tổng của mọi dịch vụ:**
  ```bash
  sudo docker compose logs -f
  ```
- **Lưu luồng log của riêng HAProxy ra file text:**
  ```bash
  sudo chmod 666 ./haproxy/log/haproxy.log
  sudo docker compose logs -f haproxy > ./haproxy/log/haproxy.log &
  ```

## 7. Các phương pháp kiểm thử Test & Benchmark

Trước tiên, hãy mở log để theo dõi việc tiêu hao tài nguyên:
```bash
sudo docker stats
```

### 7.1 Tấn công DOS
- **Direct Broker IP Attack (Port 1883):** Chỉnh port về `1883` trong đoạn code `dos_attack.py` rồi chạy. 
  => *Kết quả:* CPU utilization broker (`mqtt_broker`) đạt mức nguy hiểm, tăng > 60%.
- **Reverse Proxy Protection (Port 8883):** Chỉnh port về `8883` trong `dos_attack.py` rồi chạy. 
  => *Kết quả:* Tải CPU của proxy và broker sẽ ở dưới mức an toàn < 4%.

### 7.2 Cân bằng tải (Load Balancing)
1. Tracking log của proxy qua `sudo docker compose logs -f haproxy`.
2. Khởi chạy `check_balancing.py`.
3. => *Kết quả:* Thông qua file log có thể thấy được 2 node broker đang luân phiên nhận và giải quyết connection một cách hiệu quả.

### 7.3 Hỗ trợ giải mã TLS ngoài Broker (TLS Offloading)
Thủ thuật này dùng proxy để "cứu tải" quá trình mã hóa/giải mã SSL/TLS nặng nề mà thay vì đó Mosquitto phải nhận.
- **Để Mosquitto tự xử:** Set port bằng `8884` trong file `tls_offloading.py`. Nhận thấy CPU trên `mqtt_broker` sẽ tăng cao đột biến.
- **Giao HAproxy làm SSL proxy proxy:** Set port thành `8883` trong `tls_offloading.py`. CPU của `mqtt_broker` giảm thấy rõ ràng, lượng tải mã hóa được thay thế tại `mqtt_proxy` (HAProxy).
