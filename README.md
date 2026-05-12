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
   ```
3. Upload the code to your ESP32-CAM.
4. Open the Serial Monitor (115200 baud rate) to get the IP address assigned to the ESP32.

### 2. Python Environment Setup
1. Clone this repository:
   ```bash
   git clone [https://github.com/husseinabdelkhalek/Your-Repo-Name.git](https://github.com/husseinabdelkhalek/Your-Repo-Name.git)
   cd Your-Repo-Name
   ```
2. Install the required Python packages:
   ```bash
   pip install opencv-contrib-python numpy requests urllib3
   ```
3. Open the `final code.py` file and update the `ESP32_IP` variable with the IP address from step 1:
   ```python
   ESP32_IP = "YOUR_ESP32_IP_ADDRESS"
   ```

## 🎮 How to Use

1. Run the Python script:
   ```bash
   python "final code.py"
   ```
2. **Register a New Face:** Press the **`r`** key on your keyboard while the video stream window is active. Enter the person's name in the terminal and look at the camera. It will capture 50 images and train the model automatically.
3. **Face Recognition:** Once trained, the system will actively scan for known faces. When recognized, it sends an HTTP POST request to the ESP32 to open the servo.
4. **Quit:** Press the **`q`** key to safely stop the stream and close the application.

## 📡 Web Endpoints Reference
The ESP32 hosts a web server with the following endpoints:
* `/` : Web dashboard with live stream and manual controls.
* `/stream` : The MJPEG video stream.
* `/action` (POST): Triggered by Python to open the door (expects a `name` argument).
* `/led/on` & `/led/off` : Manual LED control.
* `/unlock` & `/open_servo` : Manual servo controls.
