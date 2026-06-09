# Oyster CCTV – Multi-Camera Facial Recognition System

A local web application for monitoring multiple **Tapo C200** IP cameras with
real-time **facial recognition**, **liveness detection**, and **intruder logging**.
Runs as a Flask server and can be packaged as a double-click `.exe` for Windows.

---

## Features

| Feature | Details |
|---|---|
| **Multi-camera RTSP** | Streams from all registered Tapo C200 cameras simultaneously |
| **Facial recognition** | dlib-based; unknown faces marked as **INTRUDER** |
| **Liveness detection** | Rejects printed photos / static images – detects eye blinks and micro-motion |
| **Imaginary line** | Draw a line per camera; intruder line-crossings are logged separately |
| **Training page** | Capture face samples from any live camera, then train the model |
| **LAN scanner** | Scans your network and lists found hosts in a combo-box for easy IP selection |
| **Intruder log** | Paginated log with snapshots, filter by camera / event type / date |
| **Theme** | `#249D9F` teal palette throughout |
| **Portable `.exe`** | Built with PyInstaller – double-click to launch server + browser |

---

## Python Version

> **Required: Python 3.10**
>
> - `dlib` pre-built wheels are available for Python 3.10 on Windows.
> - Python 3.11+ may require compiling dlib from source.
> - Python 3.9 or earlier is **not** tested.

---

## Prerequisites

### Windows
1. **Python 3.10** – https://www.python.org/downloads/release/python-3100/
2. **CMake** – https://cmake.org/download/ *(required to build dlib if no wheel is found)*
3. **Visual C++ Build Tools** – https://visualstudio.microsoft.com/visual-cpp-build-tools/
4. **Git** – https://git-scm.com/ *(optional, for cloning)*

### Linux / macOS
```bash
sudo apt-get install cmake build-essential libopenblas-dev liblapack-dev   # Ubuntu
brew install cmake                                                            # macOS
```

---

## Installation

```bash
# 1. Clone the repository (or unzip the source)
git clone https://github.com/rjilegaspi-glitch/oyster.git
cd oyster

# 2. Create a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

> **Tip – dlib on Windows:**  If `pip install face-recognition` fails, try:
> ```
> pip install dlib==19.24.1 --no-build-isolation
> pip install face-recognition
> ```
> Or install a pre-compiled `.whl` from https://github.com/jloh02/dlib

---

## Running in Development Mode

```bash
python main.py
```

The server starts on **http://localhost:5000** and opens your default browser automatically.

The app is also accessible from any device on the same LAN via:
```
http://<your-PC-IP>:5000
```

To find your PC's IP: run `ipconfig` (Windows) or `ip addr` (Linux/macOS).

> **Firewall:** Allow port 5000 through your Windows Firewall for LAN access.

---

## Building the `.exe` (Windows)

```bash
pip install pyinstaller
pyinstaller oyster.spec
```

The compiled executable is placed in:
```
dist/oyster.exe
```

**Double-click `oyster.exe`** – it will:
1. Start the Flask server automatically.
2. Open your default browser to `http://localhost:5000`.

> **Note:** The `.exe` must be run from its folder (or a folder you can write to),
> because it creates `instance/`, `dataset/`, and `models_store/` directories there.

---

## First-Time Setup

### 1. Add Cameras

1. Go to **Camera Settings** → **Add New Camera**.
2. Enter a name and the camera's IP address.
3. Optionally use the **LAN Scanner** to discover devices on your network.
4. The RTSP URL is built automatically for Tapo C200:
   ```
   rtsp://<username>:<password>@<ip>:554/stream1
   ```
   Default credentials: username `admin`, password set during camera setup.

### 2. Register Persons

1. Go to **Training**.
2. Click **Add New Person**, enter a name.
3. Select a camera for live capture.
4. Point the person's face at the camera, click **📷 Capture** at least **30–50 times** from slightly different angles.
5. Click **Start Training** when done.

### 3. Monitor

Return to the **Dashboard** to see all camera streams with real-time face labels.
- **Green box** = known person
- **Red box** = INTRUDER
- **Grey box** = liveness check failed (photo / no blink detected)

### 4. Configure Detection Lines

1. Go to **Line Setup**.
2. Select a camera, then click and drag on the preview image to draw a line.
3. Click **Save Line**.

An unknown person crossing that line will generate a **Line Crossing** log entry.

---

## Liveness Detection

Oyster uses two passive anti-spoofing methods (no user cooperation required):

| Method | Description |
|---|---|
| **Motion variance** | Compares the face region across 10 consecutive frames. A printed photo held still has near-zero variance and is rejected. |
| **EAR blink detection** | Measures the Eye Aspect Ratio over 30 frames. A face that never blinks is flagged as non-live. |

The dlib shape predictor model (`shape_predictor_68_face_landmarks.dat`) is
downloaded automatically on first run if it is not present.

---

## Directory Structure

```
oyster/
├── app/                    Flask application package
│   ├── routes/             URL blueprints
│   ├── services/           Business logic (streaming, recognition, liveness)
│   ├── static/             CSS / JS / snapshots
│   └── templates/          Jinja2 HTML templates
├── dataset/                Captured face images (per person sub-folder)
├── models_store/           Trained encodings (encodings.pkl) + dlib model
├── instance/               SQLite database (oyster.db)
├── main.py                 Entry point
├── requirements.txt
├── oyster.spec             PyInstaller build config
└── README.md
```

---

## Database

SQLite database at `instance/oyster.db`.  Tables:

| Table | Purpose |
|---|---|
| `cameras` | Camera IP / RTSP configuration |
| `persons` | Registered face identities |
| `intruder_logs` | Intruder detection events + snapshots |
| `line_configs` | Imaginary line coordinates per camera |

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `dlib` install fails | Install CMake + Visual C++ Build Tools, then retry |
| Camera shows "Offline" | Check RTSP URL, credentials, and camera is on same network |
| No faces detected | Ensure lighting is adequate; ensure face is within 2 m of camera |
| Liveness fails for real person | Increase motion threshold in `services/liveness.py` |
| `.exe` doesn't open browser | Manually open `http://localhost:5000` |
| LAN scan finds no devices | Check subnet (default auto-detected); ensure ICMP ping is not blocked |

---

## License

MIT License – see `LICENSE` file.
