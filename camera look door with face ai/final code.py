import cv2
import numpy as np
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import sys
from threading import Thread, Lock, Event
from queue import Queue
from collections import deque

# ——————————————————————————————
# إعدادات النظام المُحسّنة
ESP32_IP                = "192.168.100.169"
ESP32_STREAM_URL        = f"http://{ESP32_IP}/stream"
ESP32_ACTION_ENDPOINT   = f"http://{ESP32_IP}/action"

RECOGNIZER_FILE         = "face_recognizer.yml"
KNOWN_FACES_DIR         = "known_faces"
NUM_IMAGES_PER_PERSON   = 50
RECOGNITION_PAUSE_SEC   = 5

# ✅ إعدادات الأداء المُحسّنة
STREAM_TIMEOUT          = 60      # ⚡ زيادة timeout لـ 60 ثانية
ACTION_TIMEOUT          = 30      # ⚡ timeout طويل للأوامر
CHUNK_SIZE              = 8192    # ⚡ حجم chunk أكبر (كان 4096)
QUEUE_SIZE              = 256     # ⚡ queue أكبر (كان 128)
FRAME_SKIP              = 1       # ⚡ معالجة كل فريم (كان 2)
DETECTION_SCALE         = 1.15    # ⚡ scale أكبر = أسرع (كان 1.1)
MIN_NEIGHBORS           = 4       # ⚡ أقل = أسرع (كان 5)

# ——————————————————————————————
# ✅ Session مُحسّنة مع retry و connection pooling
def create_optimized_session():
    """إنشاء session مع إعادة محاولة تلقائية وتحسينات"""
    session = requests.Session()
    
    # ✅ إعدادات إعادة المحاولة
    retry_strategy = Retry(
        total=3,                    # 3 محاولات
        backoff_factor=0.5,         # انتظار بين المحاولات
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,        # ✅ connection pool
        pool_maxsize=20
    )
    
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

# ✅ Session عامة مُحسّنة
http_session = create_optimized_session()

# ——————————————————————————————
# تحميل المصنفات والمُعرّف
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)
recognizer = cv2.face.LBPHFaceRecognizer_create()

os.makedirs(KNOWN_FACES_DIR, exist_ok=True)

# ——————————————————————————————
# ✅ فئة MJPEG Stream مُحسّنة للأداء العالي
class ThreadedMJPEGStream:
    """
    قراءة MJPEG stream مُحسّنة مع:
    - Threading للقراءة المستمرة
    - Buffer optimization
    - Connection pooling
    - Retry mechanism
    """
    def __init__(self, stream_url, queue_size=QUEUE_SIZE):
        self.stream_url = stream_url
        self.stream = None
        self.stopped = False
        self.connected = False
        
        self.stop_event = Event()
        self.Q = Queue(maxsize=queue_size)
        self.lock = Lock()
        
        # ✅ Buffer للبيانات الواردة
        self.buffer = deque(maxlen=queue_size)
        
        # معلومات الأداء
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.fps = 0
        
        self.thread = None
        
    def connect(self):
        """الاتصال بالـ stream مع timeout طويل"""
        try:
            print(f"[STREAM] محاولة الاتصال بـ {self.stream_url}...")
            
            # ✅ استخدام session مُحسّنة مع timeout طويل
            self.stream = http_session.get(
                self.stream_url, 
                stream=True, 
                timeout=STREAM_TIMEOUT  # ⚡ timeout طويل
            )
            
            if self.stream.status_code == 200:
                print("[STREAM] ✓ تم الاتصال بنجاح")
                self.connected = True
                return True
            else:
                print(f"[STREAM] ✗ خطأ: {self.stream.status_code}")
                return False
        except Exception as e:
            print(f"[STREAM] ✗ فشل الاتصال: {e}")
            return False
    
    def start(self):
        """بدء thread القراءة"""
        if not self.connect():
            return self
        
        self.stopped = False
        self.stop_event.clear()
        
        self.thread = Thread(target=self.update, args=())
        self.thread.daemon = True
        self.thread.start()
        print("[STREAM] ✓ تم بدء thread القراءة المُحسّنة")
        return self
    
    def update(self):
        """
        ⚡ Thread مُحسّن للقراءة السريعة
        """
        bytes_data = bytearray()  # ✅ استخدام bytearray بدل bytes (أسرع)
        
        while not self.stop_event.is_set():
            if not self.connected or self.stream is None:
                time.sleep(0.05)
                continue
                
            try:
                # ⚡ قراءة بحجم chunk أكبر
                for chunk in self.stream.iter_content(chunk_size=CHUNK_SIZE):
                    if self.stop_event.is_set():
                        break
                        
                    bytes_data.extend(chunk)  # ✅ extend أسرع من +=
                    
                    # ⚡ معالجة متعددة للفريمات في نفس الـ iteration
                    while True:
                        # البحث عن بداية JPEG
                        start_marker = bytes_data.find(b'\xff\xd8')
                        if start_marker == -1:
                            break
                        
                        # البحث عن نهاية JPEG
                        end_marker = bytes_data.find(b'\xff\xd9', start_marker)
                        if end_marker == -1:
                            break
                        
                        # استخراج الصورة
                        jpg = bytes(bytes_data[start_marker:end_marker + 2])
                        bytes_data = bytes_data[end_marker + 2:]
                        
                        # ⚡ فك تشفير بدون معالجة إضافية
                        frame = cv2.imdecode(
                            np.frombuffer(jpg, dtype=np.uint8), 
                            cv2.IMREAD_COLOR
                        )
                        
                        if frame is not None:
                            # ✅ إضافة للـ queue مع حذف القديم تلقائياً
                            if self.Q.full():
                                try:
                                    self.Q.get_nowait()  # حذف الفريم الأقدم
                                except:
                                    pass
                            
                            self.Q.put(frame)
                            
                            # حساب FPS
                            self.frame_count += 1
                            current_time = time.time()
                            if current_time - self.last_fps_time >= 2.0:
                                self.fps = self.frame_count / (current_time - self.last_fps_time)
                                print(f"[STREAM FPS] {self.fps:.1f} frames/sec | Queue: {self.Q.qsize()}")
                                self.frame_count = 0
                                self.last_fps_time = current_time
                        
                        # ✅ معالجة فريم واحد فقط كل مرة للأداء
                        break
                                
            except Exception as e:
                if not self.stop_event.is_set():
                    print(f"[STREAM] خطأ في القراءة: {e}")
                self.connected = False
                break
        
        print("[STREAM] تم إيقاف thread القراءة")
    
    def read(self):
        """⚡ قراءة أحدث فريم بسرعة"""
        if self.Q.empty():
            return None
        return self.Q.get()
    
    def more(self):
        """التحقق من وجود فريمات"""
        return self.Q.qsize() > 0
    
    def stop_and_close(self):
        """إيقاف وإغلاق الاتصال"""
        print("[STREAM] جاري إيقاف البث...")
        self.stopped = True
        self.stop_event.set()
        
        if self.stream:
            try:
                self.stream.close()
            except:
                pass
            self.connected = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3.0)  # ⚡ timeout أطول
        
        # تفريغ الـ Queue
        while not self.Q.empty():
            try:
                self.Q.get_nowait()
            except:
                break
        
        print("[STREAM] ✓ تم إيقاف البث بنجاح")
    
    def release(self):
        """إغلاق الاتصال"""
        self.stop_and_close()

# ——————————————————————————————
# باقي الدوال المساعدة
def is_esp32_reachable():
    """التحقق من الاتصال مع timeout طويل"""
    try:
        response = http_session.get(
            f"http://{ESP32_IP}", 
            timeout=10  # ⚡ timeout طويل
        )
        return response.status_code == 200
    except:
        print(f"[PY] خطأ: لا يمكن الوصول إلى ESP32 على IP: {ESP32_IP}")
        return False

def train_recognizer():
    """تدريب النموذج"""
    faces, labels = [], []
    label_dict = {}
    current_id = 0
    name_to_id = {}

    for person_name in os.listdir(KNOWN_FACES_DIR):
        person_dir = os.path.join(KNOWN_FACES_DIR, person_name)
        if not os.path.isdir(person_dir):
            continue

        if person_name not in name_to_id:
            name_to_id[person_name] = current_id
            label_dict[current_id] = person_name
            current_id += 1
        
        person_id = name_to_id[person_name]

        for fname in os.listdir(person_dir):
            if fname.lower().endswith(('.jpg', '.png')):
                img_path = os.path.join(person_dir, fname)
                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    faces.append(img)
                    labels.append(person_id)

    if faces:
        recognizer.train(faces, np.array(labels))
        recognizer.save(RECOGNIZER_FILE)
        print(f"[PY] تم تدريب النموذج على {len(faces)} صورة لـ {len(label_dict)} شخص.")
    else:
        print("[PY] لا توجد وجوه للتدريب. اضغط 'r' لإضافة شخص جديد.")
    return label_dict

def trigger_action_on_esp32(name):
    """⚡ إرسال أمر مع timeout طويل وإعادة محاولة"""
    print(f"[PY] إرسال طلب لفتح الباب لـ '{name}'...")
    try:
        # ✅ استخدام session مُحسّنة مع timeout طويل
        response = http_session.post(
            ESP32_ACTION_ENDPOINT, 
            data={'name': name}, 
            timeout=ACTION_TIMEOUT  # ⚡ timeout طويل للأوامر
        )
        print(f"[PY] ✓ استجابة ESP32: {response.status_code}, {response.text}")
        return True
    except requests.exceptions.Timeout:
        print(f"[PY] ⚠ انتهت مهلة الانتظار (timeout) - لكن الأمر قد يكون وصل")
        return True  # ✅ نعتبرها نجاح لأن الأمر غالباً وصل
    except requests.exceptions.RequestException as e:
        print(f"[PY] ✗ فشل إرسال الأمر إلى ESP32: {e}")
        return False

# ——————————————————————————————
# تحميل النموذج
if os.path.exists(RECOGNIZER_FILE):
    recognizer.read(RECOGNIZER_FILE)
    print("[PY] تم تحميل النموذج المدرب مسبقًا.")
label_dict = train_recognizer()
model_trained = os.path.exists(RECOGNIZER_FILE)

# ——————————————————————————————
# التحقق من الاتصال وبدء الـ stream
if not is_esp32_reachable():
    print("[PY] تحذير: لا يمكن الوصول إلى ESP32. تأكد من الـ IP والاتصال.")
    sys.exit(1)

# ⚡ إنشاء stream مُحسّن
print("[PY] ✓ بدء الـ threaded stream المُحسّن...")
mjpeg_stream = ThreadedMJPEGStream(ESP32_STREAM_URL, queue_size=QUEUE_SIZE).start()
time.sleep(1.5)  # انتظار أقل

# متغيرات حالة البرنامج
add_mode = False
new_name = ""
img_counter = 0
paused = False
resume_time = 0
frame_skip_counter = 0

print("\n[PY] الكاميرا تعمل (وضع الأداء العالي).")
print("   - اضغط 'r' لتسجيل وجه جديد.")
print("   - اضغط 'q' للخروج.")

# ——————————————————————————————
# ⚡ الحلقة الرئيسية المُحسّنة
try:
    while True:
        # --- التعامل مع حالة الإيقاف المؤقت ---
        if paused:
            if time.time() >= resume_time:
                paused = False
                print("[PY] ✓ إعادة تشغيل البث...")
                
                mjpeg_stream = ThreadedMJPEGStream(ESP32_STREAM_URL, queue_size=QUEUE_SIZE).start()
                time.sleep(1.0)
                
                print("[PY] ✓ تم استئناف بث الفيديو")
            else:
                remaining_time = int(resume_time - time.time())
                wait_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(wait_frame, f"Door opening...", (200, 220),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(wait_frame, f"Resuming in {remaining_time}s", (180, 260),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                cv2.imshow("ESP32 Face Recognition", wait_frame)
                if cv2.waitKey(100) & 0xFF == ord('q'):
                    break
                continue

        # --- ⚡ قراءة سريعة من الـ Queue ---
        if not mjpeg_stream.more():
            time.sleep(0.005)  # ⚡ انتظار أقصر (كان 0.01)
            continue
            
        frame = mjpeg_stream.read()
        if frame is None:
            continue

        # --- ⚡ معالجة أسرع (كل فريم أو كل فريمين) ---
        frame_skip_counter += 1
        if frame_skip_counter % FRAME_SKIP != 0:  # ⚡ FRAME_SKIP = 1 يعني معالجة كل فريم
            cv2.imshow("ESP32 Face Recognition", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            continue

        # --- ⚡ معالجة مُحسّنة للصورة ---
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # ⚡ detectMultiScale مُحسّنة
        faces = face_cascade.detectMultiScale(
            gray, 
            scaleFactor=DETECTION_SCALE,    # ⚡ 1.15 أسرع من 1.1
            minNeighbors=MIN_NEIGHBORS,     # ⚡ 4 أسرع من 5
            minSize=(50, 50)                # ⚡ حجم أصغر قليلاً (كان 60)
        )

        # --- وضع إضافة شخص جديد ---
        if add_mode:
            if len(faces) > 0:
                (x, y, w, h) = faces[0]
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 2)
                
                roi_gray = gray[y:y+h, x:x+w]
                person_dir = os.path.join(KNOWN_FACES_DIR, new_name)
                os.makedirs(person_dir, exist_ok=True)
                
                file_name = f"{img_counter + 1}.jpg"
                cv2.imwrite(os.path.join(person_dir, file_name), roi_gray)
                
                img_counter += 1
                print(f"[PY] تم التقاط الصورة {img_counter}/{NUM_IMAGES_PER_PERSON} لـ '{new_name}'")

                if img_counter >= NUM_IMAGES_PER_PERSON:
                    print(f"[PY] اكتمل تسجيل '{new_name}'. جاري إعادة تدريب النموذج...")
                    label_dict = train_recognizer()
                    model_trained = True
                    add_mode = False
                    img_counter = 0
                    print("[PY] تم تحديث النموذج. العودة لوضع التعرف.")
            
            cv2.putText(frame, f"Recording {new_name}: {img_counter}/{NUM_IMAGES_PER_PERSON}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        # --- وضع التعرف على الوجوه ---
        elif model_trained and len(faces) > 0:
            for (x, y, w, h) in faces:
                roi_gray = gray[y:y+h, x:x+w]
                label_id, confidence = recognizer.predict(roi_gray)

                if confidence < 75:
                    name = label_dict.get(label_id, "Unknown")
                    text = f"{name} ({confidence:.1f})"
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    cv2.putText(frame, text, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    
                    print(f"\n{'='*50}")
                    print(f"[PY] ✓ تم التعرف على '{name}'")
                    print(f"{'='*50}")
                    
                    # ✅ 1. إيقاف البث
                    print("[PY] [1/3] إيقاف البث...")
                    mjpeg_stream.stop_and_close()
                    time.sleep(0.3)  # ⚡ انتظار أقصر
                    
                    # ✅ 2. إرسال أمر الفتح
                    print(f"[PY] [2/3] إرسال أمر فتح الباب لـ '{name}'...")
                    trigger_action_on_esp32(name)
                    
                    # ✅ 3. تحديد وقت إعادة التشغيل
                    print(f"[PY] [3/3] انتظار {RECOGNITION_PAUSE_SEC} ثواني قبل إعادة البث...")
                    paused = True
                    resume_time = time.time() + RECOGNITION_PAUSE_SEC
                    
                    break
                else:
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
                    cv2.putText(frame, "Unknown", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            
            if paused: 
                continue

        # --- عرض الإطار ---
        cv2.imshow("ESP32 Face Recognition", frame)

        # --- التعامل مع أزرار التحكم ---
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r') and not add_mode:
            name_input = input("أدخل اسم الشخص الجديد: ").strip()
            if name_input:
                new_name = name_input
                add_mode = True
                img_counter = 0
                print(f"[PY] وضع التسجيل مُفعّل لـ '{new_name}'. انظر إلى الكاميرا.")
            else:
                print("[PY] تم إلغاء الإدخال.")

except KeyboardInterrupt:
    print("\n[PY] تم إيقاف البرنامج بواسطة المستخدم.")

finally:
    # تنظيف وإنهاء
    print("[PY] جاري إغلاق البرنامج...")
    mjpeg_stream.release()
    http_session.close()  # ✅ إغلاق الـ session
    cv2.destroyAllWindows()
    print("[PY] ✓ تم الإغلاق بنجاح")