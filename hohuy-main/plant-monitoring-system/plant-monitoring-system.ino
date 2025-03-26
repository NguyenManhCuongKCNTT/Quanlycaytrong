#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <ArduinoJson.h>
#include <time.h>

#define MQTT_MAX_PACKET_SIZE 1024

const char* ssid = "Disconnect";
const char* password = "2444666668888888";

const char* mqtt_server = "test.mosquitto.org";
const int mqtt_port = 1883;

const char* topic_temperature = "plant/temperature";
const char* topic_humidity = "plant/humidity";
const char* topic_soil_moisture = "plant/soil_moisture";
const char* topic_light_level = "plant/light_level";
const char* topic_pump_status = "plant/pump_status";
const char* topic_light_status = "plant/light_status";
const char* topic_mode = "plant/mode"; 
const char* topic_thresholds = "plant/thresholds";
const char* topic_command = "plant/command";
const char* topic_data = "plant/data";

#define DHTPIN 5        
#define DHTTYPE DHT11   
#define SOIL_MOISTURE_PIN 34  
#define LIGHT_SENSOR_PIN 32    
#define PUMP_RELAY_PIN 26   
#define LIGHT_RELAY_PIN 27

#define TEMPERATURE_THRESHOLD 0.2
#define HUMIDITY_THRESHOLD 1.0
#define SOIL_MOISTURE_THRESHOLD 2
#define LIGHT_LEVEL_THRESHOLD 20

#define PUMP_RUN_TIME 3000       
#define PUMP_WAIT_TIME 60000     

struct {
  float temperature_min = 18.0;
  float temperature_max = 30.0;
  int soil_moisture_min = 30;  
  float humidity_min = 40.0;
  int light_level_min = 30;
} thresholds;

bool autoMode = true;
bool pumpStatus = false;
bool lightStatus = false;

float lastTemperature = 0;
float lastHumidity = 0;
int lastSoilMoisture = 0;
int lastLightLevel = 0;
bool isFirstReading = true;

unsigned long pumpStartTime = 0;     
unsigned long pumpLastRunTime = 0;   

const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 7 * 3600; 
const int daylightOffset_sec = 0;

DHT dht(DHTPIN, DHTTYPE);

WiFiClient espClient;
PubSubClient client(espClient);

unsigned long lastReadingTime = 0;
const long readingInterval = 5000;

unsigned long lastForcedUpdate = 0;
const long forcedUpdateInterval = 60000;

void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  int timeout_counter = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    timeout_counter++;
    if (timeout_counter >= 20) {
      Serial.println("WiFi connection timeout. Restarting...");
      ESP.restart();
    }
  }
  
  Serial.println("");
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
}

void callback(char* topic, byte* payload, unsigned int length) {
  char message[length + 1];
  for (unsigned int i = 0; i < length; i++) {
    message[i] = (char)payload[i];
  }
  message[length] = '\0';
  
  String messageStr = String(message);
  String topicStr = String(topic);
  
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("]: ");
  Serial.println(message);
  
  if (topicStr.equals(topic_command)) {
    handleCommand(messageStr);
  } 
  else if (topicStr.equals(topic_mode)) {
    bool newAutoMode = (messageStr.equals("AUTO"));
    if (newAutoMode != autoMode) {
      autoMode = newAutoMode;
      Serial.println(autoMode ? "Switched to AUTO mode" : "Switched to MANUAL mode");
    }
  } 
  else if (topicStr.equals(topic_thresholds)) {
    JsonDocument doc;
    deserializeJson(doc, message);
    updateThresholds(doc.as<JsonObject>());
  }
}

void reconnect() {
  int attempts = 0;
  while (!client.connected() && attempts < 5) {
    Serial.print("Attempting MQTT connection...");
    
    String clientId = "ESP32PlantMonitor-";
    clientId += String(random(0xffff), HEX);
    
    if (client.connect(clientId.c_str())) {
      Serial.println("connected");
      
      client.subscribe(topic_command);
      client.subscribe(topic_mode);
      client.subscribe(topic_thresholds);
      
      isFirstReading = true;
      
    } else {
      attempts++;
      Serial.print("failed, rc=");
      Serial.print(client.state());
      
      if (attempts >= 5) {
        Serial.println("Too many failed attempts. Will try again later.");
        return;
      }
      
      delay(5000);
    }
  }
}

void readSensors() {
  // Biến theo dõi xem có cảm biến nào đọc thành công không
  bool anySensorSuccess = false;
  
  // Biến lưu trữ dữ liệu cảm biến
  float temperature = lastTemperature;
  float humidity = lastHumidity;
  int soilMoisturePercent = lastSoilMoisture;
  int lightLevelPercent = lastLightLevel;
  
  bool temperatureChanged = false;
  bool humidityChanged = false;
  bool soilMoistureChanged = false;
  bool lightLevelChanged = false;
  
  float newHumidity = dht.readHumidity();
  float newTemperature = dht.readTemperature();
  
  if (!isnan(newHumidity) && !isnan(newTemperature)) {
    temperature = newTemperature;
    humidity = newHumidity;
    temperatureChanged = abs(temperature - lastTemperature) >= TEMPERATURE_THRESHOLD;
    humidityChanged = abs(humidity - lastHumidity) >= HUMIDITY_THRESHOLD;
    anySensorSuccess = true;
    
    Serial.print("Temperature: ");
    Serial.print(temperature);
    Serial.println(" °C");
    
    Serial.print("Humidity: ");
    Serial.print(humidity);
    Serial.println(" %");
  } else {
    Serial.println("Failed to read from DHT sensor!");
  }
  
  int soilMoistureRaw = analogRead(SOIL_MOISTURE_PIN);
  int newSoilMoisturePercent = map(soilMoistureRaw, 4095, 1000, 0, 100);
  newSoilMoisturePercent = constrain(newSoilMoisturePercent, 0, 100);
  
  soilMoisturePercent = newSoilMoisturePercent;
  soilMoistureChanged = abs(soilMoisturePercent - lastSoilMoisture) >= SOIL_MOISTURE_THRESHOLD;
  anySensorSuccess = true;
  
  Serial.print("Soil Moisture: ");
  Serial.print(soilMoisturePercent);
  Serial.println(" %");
  
  // Đọc cảm biến ánh sáng (vẫn đọc ngay cả khi DHT thất bại)
  int lightRaw = analogRead(LIGHT_SENSOR_PIN);
  int newLightLevelPercent = map(lightRaw, 4095, 0, 0, 100);
  newLightLevelPercent = constrain(newLightLevelPercent, 0, 100);
  
  lightLevelPercent = newLightLevelPercent;
  lightLevelChanged = abs(lightLevelPercent - lastLightLevel) >= LIGHT_LEVEL_THRESHOLD;
  anySensorSuccess = true;
  
  Serial.print("Light Level: ");
  Serial.print(lightLevelPercent);
  Serial.println(" %");
  
  // Xác định xem có cần publish dữ liệu không
  bool shouldPublish = false;
  unsigned long currentMillis = millis();
  
  if (isFirstReading || currentMillis - lastForcedUpdate >= forcedUpdateInterval) {
    shouldPublish = true;
    lastForcedUpdate = currentMillis;
    isFirstReading = false;
  } 
  else if (temperatureChanged || humidityChanged || soilMoistureChanged || lightLevelChanged) {
    shouldPublish = true;
  }
  
  if (shouldPublish && anySensorSuccess) {
    publishData(temperature, humidity, soilMoisturePercent, lightLevelPercent);
    lastTemperature = temperature;
    lastHumidity = humidity;
    lastSoilMoisture = soilMoisturePercent;
    lastLightLevel = lightLevelPercent;
  }
  
  managePumpSystem(soilMoisturePercent);
  manageLightSystem(lightLevelPercent);
}

void managePumpSystem(int soilMoisturePercent) {
  unsigned long currentMillis = millis();
  
  if (autoMode) {
    if (pumpStatus && (currentMillis - pumpStartTime >= PUMP_RUN_TIME)) {
      pumpStatus = false;
      digitalWrite(PUMP_RELAY_PIN, HIGH);
      client.publish(topic_pump_status, "OFF");
      Serial.println("Pump turned OFF after timed run");
      pumpLastRunTime = currentMillis;
    }
    
    if ((soilMoisturePercent < thresholds.soil_moisture_min) && !pumpStatus) {
      if (currentMillis - pumpLastRunTime >= PUMP_WAIT_TIME) {
        pumpStatus = true;
        digitalWrite(PUMP_RELAY_PIN, LOW);
        client.publish(topic_pump_status, "ON");
        Serial.println("Pump turned ON");
        pumpStartTime = currentMillis;
      }
    }
  }
}

void manageLightSystem(int lightLevelPercent) {
  if (autoMode) {
    if (lightLevelPercent < thresholds.light_level_min) {
      if (!lightStatus) {
        lightStatus = true;
        digitalWrite(LIGHT_RELAY_PIN, LOW); 
        client.publish(topic_light_status, "ON");
        Serial.println("Light turned ON");
      }
    } else {
      if (lightStatus) {
        lightStatus = false;
        digitalWrite(LIGHT_RELAY_PIN, HIGH);
        client.publish(topic_light_status, "OFF");
        Serial.println("Light turned OFF");
      }
    }
  }
}

void publishData(float temperature, float humidity, int soilMoisture, int lightLevel) {
  struct tm timeinfo;
  if(!getLocalTime(&timeinfo)){
    Serial.println("Failed to obtain time");
    return;
  }
  
  char dateTimeStr[20];
  strftime(dateTimeStr, sizeof(dateTimeStr), "%Y-%m-%d %H:%M:%S", &timeinfo);
  
  JsonDocument doc;
  doc["temperature"] = temperature;
  doc["humidity"] = humidity;
  doc["soil_moisture"] = soilMoisture;
  doc["light_level"] = lightLevel;
  doc["timestamp"] = dateTimeStr;
  
  char buffer[256];
  serializeJson(doc, buffer);
  
  // Luôn publish tất cả dữ liệu cảm biến khi có bất kỳ thay đổi nào
  client.publish(topic_temperature, String(temperature).c_str());
  client.publish(topic_humidity, String(humidity).c_str());
  client.publish(topic_soil_moisture, String(soilMoisture).c_str());
  client.publish(topic_light_level, String(lightLevel).c_str());
  
  // Gửi toàn bộ dữ liệu dưới dạng JSON
  client.publish(topic_data, buffer);
  
  Serial.println("Sensor data published to MQTT");
}

void handleCommand(String command) {
  if (command.equals("PUMP_ON")) {
    pumpStatus = true;
    digitalWrite(PUMP_RELAY_PIN, LOW); 
    client.publish(topic_pump_status, "ON");
    Serial.println("Pump turned ON by command");
    
    if (autoMode) {
      pumpStartTime = millis();
    }
  } 
  else if (command.equals("PUMP_OFF")) {
    pumpStatus = false;
    digitalWrite(PUMP_RELAY_PIN, HIGH);  
    client.publish(topic_pump_status, "OFF");
    Serial.println("Pump turned OFF by command");
  } 
  else if (command.equals("LIGHT_ON")) {
    lightStatus = true;
    digitalWrite(LIGHT_RELAY_PIN, LOW); 
    client.publish(topic_light_status, "ON");
    Serial.println("Light turned ON by command");
  } 
  else if (command.equals("LIGHT_OFF")) {
    lightStatus = false;
    digitalWrite(LIGHT_RELAY_PIN, HIGH); 
    client.publish(topic_light_status, "OFF");
    Serial.println("Light turned OFF by command");
  }
}

void updateThresholds(JsonObject thresholdsJson) {
  if (thresholdsJson["temperature_min"].is<float>()) {
    thresholds.temperature_min = thresholdsJson["temperature_min"];
  }
  if (thresholdsJson["temperature_max"].is<float>()) {
    thresholds.temperature_max = thresholdsJson["temperature_max"];
  }
  if (thresholdsJson["soil_moisture_min"].is<int>()) {
    thresholds.soil_moisture_min = thresholdsJson["soil_moisture_min"];
  }
  if (thresholdsJson["humidity_min"].is<float>()) {
    thresholds.humidity_min = thresholdsJson["humidity_min"];
  }
  if (thresholdsJson["light_level_min"].is<int>()) {
    thresholds.light_level_min = thresholdsJson["light_level_min"];
  }
  
  Serial.println("Thresholds updated:");
  Serial.print("Temperature min: ");
  Serial.println(thresholds.temperature_min);
  Serial.print("Temperature max: ");
  Serial.println(thresholds.temperature_max);
  Serial.print("Soil moisture min: ");
  Serial.println(thresholds.soil_moisture_min);
  Serial.print("Humidity min: ");
  Serial.println(thresholds.humidity_min);
  Serial.print("Light level min: ");
  Serial.println(thresholds.light_level_min);
}

void setup() {
  Serial.begin(115200);
  
  pinMode(SOIL_MOISTURE_PIN, INPUT);
  pinMode(LIGHT_SENSOR_PIN, INPUT);
  pinMode(PUMP_RELAY_PIN, OUTPUT);
  pinMode(LIGHT_RELAY_PIN, OUTPUT);
  
  digitalWrite(PUMP_RELAY_PIN, HIGH);  
  digitalWrite(LIGHT_RELAY_PIN, HIGH); 
  
  dht.begin();
  
  setup_wifi();
  
  randomSeed(micros());
  
  client.setSocketTimeout(60);
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
  
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);

  Serial.println("Setup complete");
}

void loop() {
  static unsigned long lastReconnectAttempt = 0;
  
  if (!client.connected()) {
    unsigned long now = millis();
    if (now - lastReconnectAttempt > 30000) {
      lastReconnectAttempt = now;
      reconnect();
    }
  } else {
    client.loop();
    
    unsigned long currentMillis = millis();
    if (currentMillis - lastReadingTime >= readingInterval) {
      lastReadingTime = currentMillis;
      readSensors();
    }
  }
}