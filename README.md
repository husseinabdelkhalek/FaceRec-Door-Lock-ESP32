# ESP32-CAM Smart Face Recognition Lock 🚪👁️

An IoT-based smart door lock system that utilizes an ESP32-CAM module and Python. The system streams live video to a Python application, performs real-time face recognition, and automatically triggers a servo motor to unlock the door when a known face is detected.

## ✨ Features
* **Real-time Face Recognition:** Uses OpenCV and the LBPH Face Recognizer algorithm.
* **Auto-Illumination:** The ESP32-CAM automatically turns on its built-in flash/LED in low-light conditions using image brightness calculations.
* **Optimized MJPEG Streaming:** Multi-threaded Python script with connection pooling and chunk reading for a high-performance, low-latency video feed.
* **Remote Servo Control:** Unlocks the door automatically upon recognition or manually via a web interface.
* **Easy Registration:** Add new faces directly through the Python application with a single keypress.

## 🛠️ Hardware Requirements
* ESP32-CAM Module
* FTDI Programmer (for uploading code to the ESP32)
* Servo Motor (connected to GPIO 15)
* Jumper Wires & Power Supply

## 💻 Software & Libraries

**For the ESP32 (Arduino IDE):**
* ESP32 Board Manager
* `ESP32Servo` Library
* `esp_camera.h`

**For Python:**
* `opencv-contrib-python` (cv2)
* `numpy`
* `requests`
* `urllib3`

## 🚀 Setup & Installation

### 1. ESP32-CAM Setup
1. Open the `.ino` file in the Arduino IDE.
2. Update your Wi-Fi credentials in the code:
   ```cpp
   const char* ssid     = "YOUR_WIFI_SSID";
   const char* password = "YOUR_WIFI_PASSWORD";
