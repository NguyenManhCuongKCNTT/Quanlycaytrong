# Hệ Thống Giám Sát Và Điều Khiển Cây Trồng

Đây là một giải pháp IoT hoàn chỉnh để giám sát và điều khiển tự động việc chăm sóc cây trồng. Hệ thống bao gồm:

1. Mã nguồn ESP32 cho việc đọc cảm biến và điều khiển thiết bị
2. Ứng dụng web Flask với WebSocket cho cập nhật thời gian thực
3. Giao diện web responsive để giám sát và điều khiển

## Cấu Trúc Dự Án

```
he-thong-giam-sat-cay-trong/
├── esp32_plant_monitor.ino       # Mã Arduino cho ESP32
├── server/
│   ├── app.py                    # Ứng dụng Flask chính
│   ├── config.py                 # Cấu hình hệ thống
│   ├── extensions.py             # Extensions Flask
│   ├── models.py                 # Models cơ sở dữ liệu
│   ├── routes.py                 # Kết nối API
│   ├── requirements.txt          # Thư viện Python
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css         # CSS styles
│   │   └── js/
│   │       └── main.js           # JavaScript cho dashboard
│   └── templates/
│       └── index.html            # Template HTML chính
└── README.md                     # File này
```

## Các Thành Phần Phần Cứng

- ESP32 microcontroller
- Cảm biến nhiệt độ và độ ẩm DHT11
- Cảm biến độ ẩm đất sử dụng chip LM393
- Cảm biến ánh sáng
- Module relay để điều khiển máy bơm
- Module relay để điều khiển đèn

## Kết Nối Phần Cứng

1. Kết nối cảm biến DHT11 với chân GPIO5 của ESP32
2. Kết nối cảm biến độ ẩm đất với chân GPIO34 (ADC)
3. Kết nối cảm biến ánh sáng với chân GPIO32 (ADC)
4. Kết nối relay máy bơm với chân GPIO26
5. Kết nối relay đèn với chân GPIO27
6. Tải mã lên ESP32

## Cài Đặt MQTT

Hệ thống sử dụng giao thức MQTT để kết nối giữa ESP32 và máy chủ web. Các chủ đề (topics) được sử dụng:

- `plant/temperature` - Dữ liệu nhiệt độ
- `plant/humidity` - Dữ liệu độ ẩm không khí
- `plant/soil_moisture` - Dữ liệu độ ẩm đất
- `plant/light_level` - Dữ liệu ánh sáng
- `plant/pump_status` - Trạng thái bơm (ON/OFF)
- `plant/light_status` - Trạng thái đèn (ON/OFF)
- `plant/mode` - Chế độ hoạt động (AUTO/MANUAL)
- `plant/thresholds` - Ngưỡng cài đặt
- `plant/command` - Lệnh điều khiển
- `plant/data` - Dữ liệu đầy đủ dạng JSON

## Cài Đặt Máy Chủ

1. Cài đặt các thư viện Python:

   ```bash
   # Tạo môi trường ảo
   python -m venv venv

   # Kích hoạt môi trường ảo - Windows
   venv\Scripts\activate
   # Kích hoạt môi trường ảo - macOS/Linux
   source venv/bin/activate
   ```

   ```
   pip install -r requirements.txt
   ```

2. Tạo file `.env` nằm trong server với cấu hình:
   ```
   SECRET_KEY=zdfxgchvjbknkm1234567@#$%dfgchvjbk
   DEBUG=True
   DATABASE_URL=sqlite:///server/plant_monitor.db
   MQTT_BROKER_URL=test.mosquitto.org
   MQTT_BROKER_PORT=1883
   MQTT_USERNAME=
   MQTT_PASSWORD=
   MQTT_KEEPALIVE=60
   MQTT_TLS_ENABLED=False
   MQTT_CLIENT_ID=flask_plant_monitor
   ```

3. Chạy ứng dụng Flask:
   ```
   python app.py
   ```

4. Truy cập dashboard tại http://localhost:5000

## Tính Năng

- **Giám sát thời gian thực** nhiệt độ, độ ẩm không khí, độ ẩm đất và ánh sáng
- **Chế độ tự động** điều khiển máy bơm và đèn dựa trên ngưỡng cài đặt
- **Chế độ thủ công** để điều khiển trực tiếp máy bơm và đèn
- **Hiển thị dữ liệu lịch sử** với biểu đồ theo ngày, tuần, tháng, năm
- **Thiết kế responsive** hoạt động trên cả thiết bị di động và máy tính
- **Xử lý lỗi mạnh mẽ** vẫn hoạt động ngay cả khi một số cảm biến gặp sự cố

## Giải Thích Cơ Chế Hoạt Động

1. **ESP32**:
   - Đọc dữ liệu từ các cảm biến mỗi 5 giây
   - Chỉ gửi dữ liệu khi có sự thay đổi đáng kể hoặc sau mỗi 60 giây
   - Trong chế độ tự động, bơm chạy 3 giây, sau đó đợi 1 phút kiểm tra lại
   - Đèn tự động bật khi mức ánh sáng dưới ngưỡng cài đặt

2. **Máy Chủ Flask**:
   - Nhận dữ liệu cảm biến từ ESP32 thông qua MQTT
   - Lưu trữ dữ liệu vào cơ sở dữ liệu SQLite
   - Cung cấp API để truy vấn dữ liệu lịch sử
   - Giao tiếp với client qua WebSocket để cập nhật thời gian thực

3. **Giao Diện Web**:
   - Hiển thị dữ liệu thời gian thực với tròn tiến độ gradient
   - Cho phép chuyển đổi giữa chế độ tự động và thủ công
   - Hiển thị dữ liệu lịch sử bằng ChartJS
   - Cập nhật trạng thái máy bơm và đèn
