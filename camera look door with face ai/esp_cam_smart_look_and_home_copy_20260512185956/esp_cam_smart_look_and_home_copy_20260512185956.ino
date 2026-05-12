#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <ESP32Servo.h>

const char* ssid     = "WE_4AF905";
const char* password = "8552ddb0";

// Camera model pins (ESP32-CAM)
#define PWDN_GPIO_NUM    32
#define RESET_GPIO_NUM   -1
#define XCLK_GPIO_NUM     0
#define SIOD_GPIO_NUM    26
#define SIOC_GPIO_NUM    27
#define Y9_GPIO_NUM      35
#define Y8_GPIO_NUM      34
#define Y7_GPIO_NUM      39
#define Y6_GPIO_NUM      36
#define Y5_GPIO_NUM      21
#define Y4_GPIO_NUM      19
#define Y3_GPIO_NUM      18
#define Y2_GPIO_NUM       5
#define VSYNC_GPIO_NUM   25
#define HREF_GPIO_NUM    23
#define PCLK_GPIO_NUM    22

// Built-in LED pin
#define LED_PIN 2

// Servo pin
#define SERVO_PIN 15

// Web server port
WebServer server(80);

// Thresholds for light levels
const int DARK_THRESHOLD = 110;
const int BRIGHT_THRESHOLD = 130;

bool isLEDOn = false;

// إعداد السيرفو
Servo myServo;

// تعريف مبدئي لمهمة الإضاءة
void brightnessTask(void*);

void startCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if(psramFound()){
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 30;
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_CIF;
    config.jpeg_quality = 30;
    config.fb_count = 1;
  }

  esp_err_t err = esp_camera_init(&config);
  if(err != ESP_OK){
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }
  Serial.println("Camera initialized successfully");
}

int calculateBrightness() {
  camera_fb_t *fb = esp_camera_fb_get();
  if(!fb){
    Serial.println("Camera capture failed");
    return 0;
  }
  long total = 0;
  int count = 0;
  for(size_t i = 0; i < fb->len; i += 3){
    uint8_t r = fb->buf[i];
    uint8_t g = fb->buf[i+1];
    uint8_t b = fb->buf[i+2];
    int brightness = (r*0.299) + (g*0.587) + (b*0.114);
    total += brightness;
    count++;
  }
  esp_camera_fb_return(fb);
  return count > 0 ? total/count : 0;
}

void handleRoot() {
  String html = "<html><head><title>ESP32-CAM</title></head><body>";
  html += "<h1>Live Stream</h1>";
  html += "<img src=\"/stream\" width=\"640\" height=\"480\">";
  html += "<h2>LED Control</h2>";
  html += "<button onclick=\"location.href='/led/on'\">ON</button> ";
  html += "<button onclick=\"location.href='/led/off'\">OFF</button>";
  html += "<h2>Servo Control</h2>";
  html += "<button onclick=\"location.href='/unlock'\">Auto Unlock</button>";
  html += "<h2>Manual Servo</h2>";
  html += "<button onclick=\"location.href='/open_servo'\">Open Servo</button>";
  html += "</body></html>";
  server.send(200, "text/html", html);
}

void handleStream() {
  WiFiClient client = server.client();
  client.print("HTTP/1.1 200 OK\r\nContent-Type: multipart/x-mixed-replace; boundary=frame\r\n\r\n");
  while(client.connected()){
    camera_fb_t *fb = esp_camera_fb_get();
    if(!fb) break;
    client.print("--frame\r\nContent-Type: image/jpeg\r\n\r\n");
    client.write(fb->buf, fb->len);
    client.print("\r\n");
    esp_camera_fb_return(fb);
    vTaskDelay(10/portTICK_PERIOD_MS);
  }
}

void handleLedOn() {
  digitalWrite(LED_PIN, HIGH);
  isLEDOn = true;
  server.send(200, "text/plain", "LED ON");
}

void handleLedOff() {
  digitalWrite(LED_PIN, LOW);
  isLEDOn = false;
  server.send(200, "text/plain", "LED OFF");
}

void handleUnlock() {
  myServo.write(90);
  server.send(200, "text/plain", "Auto Unlock");
  vTaskDelay(3000/portTICK_PERIOD_MS);
  myServo.write(0);
}

void handleOpenServo() {
  myServo.write(90);
  Serial.println("Servo opened manually");
  server.send(200, "text/plain", "Servo Opened");
  vTaskDelay(2000/portTICK_PERIOD_MS);
  myServo.write(0);
  Serial.println("Servo closed after manual open");
}

// ✅ الـ endpoint الجديد للتعرف على الوجوه
void handleAction() {
  // التحقق من وجود بيانات في الـ POST request
  if(server.hasArg("name")) {
    String personName = server.arg("name");
    
    Serial.println("========================================");
    Serial.println("[ACTION] تم التعرف على شخص!");
    Serial.print("[ACTION] الاسم: ");
    Serial.println(personName);
    Serial.println("[ACTION] فتح السيرفو لمدة 10 ثواني...");
    
    // فتح السيرفو
    myServo.write(90);
    
    // إرسال رد للـ Python فوراً
    server.send(200, "text/plain", "Door opened for: " + personName);
    
    // الانتظار 10 ثواني
    Serial.println("[ACTION] الباب مفتوح...");
    vTaskDelay(10000/portTICK_PERIOD_MS);  // 10 ثواني
    
    // إغلاق السيرفو
    myServo.write(0);
    Serial.println("[ACTION] تم إغلاق الباب");
    Serial.println("========================================");
    
  } else {
    // لو مفيش اسم، افتح السيرفو برضو
    Serial.println("[ACTION] تم استقبال أمر فتح بدون اسم");
    
    myServo.write(90);
    server.send(200, "text/plain", "Door opened");
    
    vTaskDelay(10000/portTICK_PERIOD_MS);  // 10 ثواني
    
    myServo.write(0);
    Serial.println("[ACTION] تم إغلاق الباب");
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  myServo.attach(SERVO_PIN);
  myServo.write(0);

  WiFi.begin(ssid, password);
  while(WiFi.status() != WL_CONNECTED){
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected to WiFi");
  Serial.println(WiFi.localIP());

  startCamera();

  server.on("/", handleRoot);
  server.on("/stream", HTTP_GET, handleStream);
  server.on("/led/on", HTTP_GET, handleLedOn);
  server.on("/led/off", HTTP_GET, handleLedOff);
  server.on("/unlock", HTTP_GET, handleUnlock);
  server.on("/open_servo", HTTP_GET, handleOpenServo);
  
  // ✅ إضافة الـ endpoint الجديد
  server.on("/action", HTTP_POST, handleAction);
  
  server.begin();
  Serial.println("HTTP server started");

  xTaskCreate(brightnessTask, "Brightness", 4096, NULL, 1, NULL);
}

void loop() {
  server.handleClient();
}

void brightnessTask(void*){
  while(true){
    int b = calculateBrightness();
    if(b < DARK_THRESHOLD && !isLEDOn){
      digitalWrite(LED_PIN, HIGH);
      isLEDOn = true;
    } else if(b > BRIGHT_THRESHOLD && isLEDOn){
      digitalWrite(LED_PIN, LOW);
      isLEDOn = false;
    }
    vTaskDelay(1000/portTICK_PERIOD_MS);
  }
}