# Semantic Image Engine

An offline-first, semantic image compression and reconstruction platform designed to turn multi-megabyte photos into compact, human-readable JSON manifests (`< 25 KB`) using local inventory pattern matching and CPU-based machine learning.

Zero external API calls. Zero cloud dependencies. Zero subscriptions. 100% self-hostable.

---

## Architecture Overview

`run_semantic_app.py` serves as the **single starting point and orchestrator** that boots the entire system, initializes the local filesystem inventory, coordinates the underlying ML pipeline, and serves the web UI and REST API.

```
semantic-image-engine/
│
├── run_semantic_app.py        # ★ Unified entry point & launcher (CLI & Web UI orchestrator)
│
├── engine/                    # Core Python offline processing modules
│   ├── offline_ml_pipeline.py # Local ONNX Runtime segmentation & Scikit-learn palette analyzer
│   └── decoder.py             # High-resolution image compositor & inventory renderer
│
├── server/                    # Dedicated Node.js / Express REST API (Alternative backend)
│   ├── index.js               # Express server with JWT auth & RBAC
│   └── package.json           # Node.js dependencies (express, multer, jsonwebtoken)
│
├── storage/                   # Local file-based storage (No SQL required)
│   ├── users.json             # RBAC user credentials (nehasb25@gmail.com as super_admin)
│   ├── manifests/             # Generated compact .sem.json files (< 25 KB)
│   ├── cutouts/               # Extracted alpha masks & subject cutouts
│   └── uploads/               # Temporary incoming photos
│
├── inventory/                 # Local high-resolution background plates library
│   ├── studio/                # Clean neutral portrait backgrounds
│   ├── sunsets/               # Golden hour and sunset plates
│   ├── beaches/               # Coastal and ocean water scenes
│   └── interiors/             # Architectural & indoor venues
│
├── models/                    # Offline open-source ML weights directory
│   └── u2net.onnx             # Downloadable U-2-Net weights (CPU inference)
│
├── schema.sql                 # Optional MySQL 8.0+ schema for database deployments
└── requirements.txt           # Python dependencies (onnxruntime, pillow, scikit-learn, numpy)
```

---

## Quick Start (Single Command)

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/neharunwal/semantic-image-engine.git
cd semantic-image-engine
pip install -r requirements.txt
```

### 2. Launch the Application
Run the orchestrator:
```bash
python3 run_semantic_app.py
```
Open **`http://127.0.0.1:8080`** in your browser.

The orchestrator will automatically:
- Create and scaffold `/inventory`, `/models`, and `/storage`.
- Seed reference backdrop plates in `/inventory/`.
- Initialize `storage/users.json` with **`nehasb25@gmail.com`** as **Super Admin**.
- Launch the interactive browser studio with compression metrics, live manifest inspection, and image decoding preview.

---

## Command Line Interface (CLI)

`run_semantic_app.py` can also orchestrate individual tasks directly from the terminal:

### Encode a Photo via Offline ML Pipeline:
```bash
python3 run_semantic_app.py --encode path/to/photo.jpg --mode semantic --cat studio
```
*Outputs the compact JSON manifest and saves the subject cutout mask.*

### Reconstruct High-Res Image from Manifest:
```bash
python3 run_semantic_app.py --decode storage/manifests/manifest_photo.json --out highres_output.jpg
```
*Composites the subject cutout over the matched local inventory plate.*

---

## Modular Engines

### 1. `engine/offline_ml_pipeline.py`
- **Subject Segmentation:** Runs `onnxruntime` with local model weights (`models/u2net.onnx` or `silueta.onnx`). If weights are not yet downloaded, an adaptive edge-contrast heuristic CPU fallback runs seamlessly.
- **Color & Lighting Extraction:** Uses `scikit-learn` KMeans clustering to extract dominant color centroids, warmth balance, and average luminance.
- **Inventory Matcher:** Selects the optimal background plate from the local `/inventory` folder matching the analyzed lighting.

### 2. `engine/decoder.py`
- Reconstructs high-resolution images on demand.
- Fetches the local plate from `/inventory`, applies depth blur if requested by the manifest, and alpha-composites the sharpened subject.

### 3. `server/index.js` (Node.js Alternative)
For environments where you prefer running an Express REST API:
```bash
cd server
npm install
npm start
```
- Listens on `http://127.0.0.1:3001`
- JWT authentication with role-based access control.
- Enforces Super Admin permissions for `nehasb25@gmail.com`.

### 4. `schema.sql` (MySQL Alternative)
If you decide to deploy with a relational database instead of the local filesystem:
```bash
mysql -u root -p < schema.sql
```

---

## Role-Based Access Control (RBAC)

Configured out-of-the-box in `storage/users.json`:
- **`nehasb25@gmail.com`** — **Super Admin**: Full CRUD access to inventory plates, user management, and system pipelines.
- **`editor@local.test`** — **Standard User**: Can encode photos, download manifests, and decode images.
