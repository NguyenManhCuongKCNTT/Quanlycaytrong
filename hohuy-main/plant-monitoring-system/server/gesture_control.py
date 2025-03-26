import cv2
import mediapipe as mp
import time
import threading
import argparse
import os
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('gesture_control')

load_dotenv()

MQTT_BROKER = os.getenv('MQTT_BROKER_URL', 'test.mosquitto.org')
MQTT_PORT = int(os.getenv('MQTT_BROKER_PORT', 1883))
MQTT_USERNAME = os.getenv('MQTT_USERNAME', '')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', '')
MQTT_CLIENT_ID = os.getenv('MQTT_CLIENT_ID', 'gesture_control') + '_gesture'

TOPIC_COMMAND = "plant/command"

CAMERA_SOURCE = os.getenv('CAMERA_SOURCE', '1')
if CAMERA_SOURCE.isdigit():
    CAMERA_SOURCE = int(CAMERA_SOURCE)

GESTURE_DURATION = 1.5
index_finger_timer = 0.0  
middle_finger_timer = 0.0  
fist_timer = 0.0  

current_gesture = None
last_index_state = None  
last_middle_state = None 
light_state = False
pump_state = False

def connect_mqtt():
    client = mqtt.Client(client_id=MQTT_CLIENT_ID)
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logger.info("Kết nối MQTT thành công!")
        else:
            logger.error(f"Kết nối MQTT thất bại với mã lỗi {rc}")
    
    client.on_connect = on_connect
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    return client

def send_command(client, command):
    client.publish(TOPIC_COMMAND, command)
    logger.info(f"Đã gửi lệnh: {command}")

def is_hand_in_resting_position(hand_landmarks):
    landmarks = hand_landmarks.landmark
    wrist_y = landmarks[mp.solutions.hands.HandLandmark.WRIST].y
    
    # Check if wrist is higher (smaller y value) than finger tips
    index_tip_y = landmarks[mp.solutions.hands.HandLandmark.INDEX_FINGER_TIP].y
    middle_tip_y = landmarks[mp.solutions.hands.HandLandmark.MIDDLE_FINGER_TIP].y
    ring_tip_y = landmarks[mp.solutions.hands.HandLandmark.RING_FINGER_TIP].y
    pinky_tip_y = landmarks[mp.solutions.hands.HandLandmark.PINKY_TIP].y
    
    # If wrist is higher than all finger tips, it's likely in resting position
    return wrist_y < index_tip_y and wrist_y < middle_tip_y and wrist_y < ring_tip_y and wrist_y < pinky_tip_y

def is_index_finger_up(hand_landmarks):
    landmarks = hand_landmarks.landmark
    # Index finger is up if tip is higher (smaller y value) than PIP joint
    return landmarks[mp.solutions.hands.HandLandmark.INDEX_FINGER_TIP].y < landmarks[mp.solutions.hands.HandLandmark.INDEX_FINGER_PIP].y

def is_middle_finger_up(hand_landmarks):
    landmarks = hand_landmarks.landmark
    # Middle finger is up if tip is higher (smaller y value) than PIP joint
    return landmarks[mp.solutions.hands.HandLandmark.MIDDLE_FINGER_TIP].y < landmarks[mp.solutions.hands.HandLandmark.MIDDLE_FINGER_PIP].y

def is_fist(hand_landmarks):
    landmarks = hand_landmarks.landmark
    index_finger_down = landmarks[mp.solutions.hands.HandLandmark.INDEX_FINGER_TIP].y > landmarks[mp.solutions.hands.HandLandmark.INDEX_FINGER_PIP].y
    middle_finger_down = landmarks[mp.solutions.hands.HandLandmark.MIDDLE_FINGER_TIP].y > landmarks[mp.solutions.hands.HandLandmark.MIDDLE_FINGER_PIP].y
    ring_finger_down = landmarks[mp.solutions.hands.HandLandmark.RING_FINGER_TIP].y > landmarks[mp.solutions.hands.HandLandmark.RING_FINGER_PIP].y
    pinky_down = landmarks[mp.solutions.hands.HandLandmark.PINKY_TIP].y > landmarks[mp.solutions.hands.HandLandmark.PINKY_PIP].y
    
    return index_finger_down and middle_finger_down and ring_finger_down and pinky_down

def detect_gesture(mqtt_client, test_mode=False):
    global index_finger_timer, middle_finger_timer, fist_timer, current_gesture, light_state, pump_state
    global last_index_state, last_middle_state
    
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )
    mp_drawing = mp.solutions.drawing_utils
    
    logger.info(f"Đang mở camera từ nguồn: {CAMERA_SOURCE}")
    cap = cv2.VideoCapture(CAMERA_SOURCE)
    
    if not cap.isOpened():
        logger.error(f"Không thể mở camera từ nguồn: {CAMERA_SOURCE}")
        return
    
    logger.info("Đã mở camera thành công")
    
    while cap.isOpened():
        success, image = cap.read()
        if not success:
            logger.error("Không thể đọc khung hình từ camera")
            break
            
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = hands.process(image_rgb)
        image = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        current_time = time.time()
        gesture_text = "Không phát hiện cử chỉ"
        
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(
                    image, 
                    hand_landmarks, 
                    mp_hands.HAND_CONNECTIONS
                )
                
                # Check if hand is in resting position (wrist higher than fingers)
                if is_hand_in_resting_position(hand_landmarks):
                    gesture_text = "Tay đang ở vị trí nghỉ"
                    # Reset states if needed
                    if current_gesture != "resting":
                        current_gesture = "resting"
                    continue
                
                # Check individual finger states
                index_up = is_index_finger_up(hand_landmarks)
                middle_up = is_middle_finger_up(hand_landmarks)
                is_fist_gesture = is_fist(hand_landmarks)
                
                # Handle index finger for light control
                if index_up != last_index_state and last_index_state is not None:
                    if index_up:  # Index finger went up
                        index_finger_timer = current_time
                        gesture_text = "Phát hiện ngón trỏ dơ lên"
                    else:  # Index finger went down
                        if current_time - index_finger_timer >= GESTURE_DURATION and light_state:
                            logger.info("Phát hiện cử chỉ: Hạ ngón trỏ - Tắt đèn")
                            if not test_mode:
                                send_command(mqtt_client, "LIGHT_OFF")
                            light_state = False
                            gesture_text = "ĐÃ TẮT ĐÈN!"
                
                # Handle middle finger for pump control
                if middle_up != last_middle_state and last_middle_state is not None:
                    if middle_up:  # Middle finger went up
                        middle_finger_timer = current_time
                        gesture_text = "Phát hiện ngón giữa dơ lên"
                    else:  # Middle finger went down
                        if current_time - middle_finger_timer >= GESTURE_DURATION and pump_state:
                            logger.info("Phát hiện cử chỉ: Hạ ngón giữa - Tắt máy bơm")
                            if not test_mode:
                                send_command(mqtt_client, "PUMP_OFF")
                            pump_state = False
                            gesture_text = "ĐÃ TẮT MÁY BƠM!"
                
                # Continuously check for active gestures
                if index_up:
                    if current_time - index_finger_timer >= GESTURE_DURATION and not light_state:
                        logger.info("Phát hiện cử chỉ: Giơ ngón trỏ - Bật đèn")
                        if not test_mode:
                            send_command(mqtt_client, "LIGHT_ON")
                        light_state = True
                        index_finger_timer = current_time  # Reset timer to prevent multiple triggers
                        gesture_text = "ĐÃ BẬT ĐÈN!"
                
                if middle_up:
                    if current_time - middle_finger_timer >= GESTURE_DURATION and not pump_state:
                        logger.info("Phát hiện cử chỉ: Giơ ngón giữa - Bật máy bơm")
                        if not test_mode:
                            send_command(mqtt_client, "PUMP_ON")
                        pump_state = True
                        middle_finger_timer = current_time  # Reset timer to prevent multiple triggers
                        gesture_text = "ĐÃ BẬT MÁY BƠM!"
                
                # Handle fist gesture
                if is_fist_gesture:
                    if current_gesture != "fist":
                        current_gesture = "fist"
                        fist_timer = current_time
                    
                    if current_time - fist_timer >= GESTURE_DURATION:
                        # Turn everything off with fist
                        if light_state or pump_state:
                            logger.info("Phát hiện cử chỉ: Nắm tay - Tắt tất cả thiết bị")
                            if light_state and not test_mode:
                                send_command(mqtt_client, "LIGHT_OFF")
                            if pump_state and not test_mode:
                                send_command(mqtt_client, "PUMP_OFF")
                            light_state = False
                            pump_state = False
                            gesture_text = "ĐÃ TẮT TẤT CẢ!"
                else:
                    if current_gesture == "fist":
                        current_gesture = None
                
                # Update last states
                last_index_state = index_up
                last_middle_state = middle_up
        else:
            # No hand detected, reset states
            current_gesture = None
            
        if test_mode:
            # Display states
            cv2.putText(image, f"Đèn: {'BẬT' if light_state else 'TẮT'}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.putText(image, f"Bơm: {'BẬT' if pump_state else 'TẮT'}", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.putText(image, gesture_text, (10, 90), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Display instructions
            cv2.putText(image, "Hướng dẫn:", (10, image.shape[0] - 150), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(image, "- Giơ ngón trỏ 1s: Bật đèn", (10, image.shape[0] - 120), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(image, "- Hạ ngón trỏ 1s: Tắt đèn", (10, image.shape[0] - 90), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(image, "- Giơ ngón giữa 1s: Bật bơm", (10, image.shape[0] - 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(image, "- Hạ ngón giữa 1s: Tắt bơm", (10, image.shape[0] - 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(image, "- Cổ tay cao hơn ngón tay: Nghỉ (không điều khiển)", (10, image.shape[0] - 0), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            cv2.imshow('Điều Khiển Bằng Cử Chỉ', image)
            
            if cv2.waitKey(5) & 0xFF == 27:  # Press ESC to exit
                break
    
    cap.release()
    if test_mode:
        cv2.destroyAllWindows()

def run_gesture_detection(test_mode=False):
    try:
        logger.info("Khởi động hệ thống nhận diện cử chỉ")
        if test_mode:
            logger.info("Chạy ở chế độ test với hiển thị camera")
            detect_gesture(None, test_mode=True)
        else:
            mqtt_client = connect_mqtt()
            mqtt_client.loop_start()
            detect_gesture(mqtt_client)
            mqtt_client.loop_stop()
    except Exception as e:
        logger.error(f"Lỗi trong thread nhận diện cử chỉ: {str(e)}")

def start_gesture_thread(test_mode=False):
    gesture_thread = threading.Thread(target=run_gesture_detection, args=(test_mode,))
    gesture_thread.daemon = True
    gesture_thread.start()
    return gesture_thread

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Điều khiển bằng cử chỉ tay')
    parser.add_argument('--test', action='store_true', help='Chạy ở chế độ test với hiển thị camera')
    args = parser.parse_args()
    
    run_gesture_detection(test_mode=args.test)