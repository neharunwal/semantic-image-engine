# Semantic Offline Image Engine (100% Air-Gapped)

An open-source, database-free, offline-first image compression and semantic reconstruction engine.
Converts high-resolution photos (50–100 MB) into compact semantic manifests (< 25 KB) using local machine learning models and a local filesystem inventory.

---

## Key Highlights

- **Zero Database Dependency:** Runs completely on the local filesystem (`/inventory` and `/storage`).
- **100% Offline & Free:** Uses local ONNX Runtime CPU inference and scikit-learn. No online endpoints, zero API keys, no subscriptions.
- **Role-Based Access Control (RBAC):** Built-in REST API with role permissions.
  - **Super Admin:** `nehasb25@gmail.com` (full permissions to add/delete inventory plates, inspect manifests, manage users).
  - **Standard Users:** Upload, compress, and download manifests.
- **Dual Mode:**
  - **Semantic Mode (Weddings, Portraits, Social):** Segments subject, sharpens details, and composites with pre-cached high-res background plates (Sky, Sunset, Beach, Studio).
  - **Forensic Mode (Archival, Archaeology):** Preserves raw pixel metrics without generative alteration.

---

## Quick Start (Single-File Runner)

We provide a self-contained single-file runner: `run_semantic_app.py`.
It automatically creates the entire directory structure, writes the backend REST API, creates the local inventory, generates procedural fallback plates, and serves an interactive web UI.

### 1. Prerequisites
Ensure you have Python 3.8+ installed.

Install the standard open-source dependencies:
```bash
pip install onnxruntime pillow scikit-learn numpy
```

*(Optional: If you want to run the Node.js Express server instead of the Python runner, Node 18+ is required).*

### 2. Run the Application
Simply execute the runner script:
```bash
python3 run_semantic_app.py
```

### 3. Open in Your Browser
The terminal will display:
```
======================================================================
  Semantic Offline Image Engine Started!
  URL: http://127.0.0.1:8080
  Super Admin Email: nehasb25@gmail.com
======================================================================
```
Open `http://127.0.0.1:8080` in your web browser.

---

## Directory Architecture

When `run_semantic_app.py` runs, it creates:

```
semantic_engine/
├── inventory/                  # Local high-resolution background plates
│   ├── studio/                 # Clean portrait backdrops
│   ├── sunset/                 # Golden hour gradients & horizons
│   ├── beach/                  # Coastal shoreline plates
│   └── weddings/               # Warm ambient indoor settings
│
├── models/                     # Offline ML weights
│   └── u2net.onnx              # Pre-downloaded segmentation model
│
├── storage/
│   ├── users.json              # Local RBAC credentials store
│   └── manifests/              # Generated KB-sized .sem.json files
│
└── app.py                      # REST API & Web UI server
```

---

## REST API Reference

All requests accept and return JSON. Authentication uses Bearer JWT tokens.

| Method | Endpoint | Authorization | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/login` | Public | Authenticates user; grants token and role |
| `GET` | `/api/inventory` | Public / User | Lists available background plates from local disk |
| `POST` | `/api/photos/process` | User / Admin | Runs ML segmentation; outputs < 25 KB manifest |
| `POST` | `/api/photos/render` | User / Admin | Reconstructs 4K/8K image using local inventory |
| `DELETE` | `/api/inventory/<cat>/<file>` | `super_admin` only | Deletes an inventory plate from disk |
| `GET` | `/api/admin/users` | `super_admin` only | Lists local users and assigned roles |

---

## Adding Real High-Res Plates & Models

1. **Background Plates:** Drop any 4K/8K JPEGs into `inventory/studio/`, `inventory/sunset/`, `inventory/beach/`, etc. The engine automatically indexes them on disk.
2. **Offline AI Weights:** Download `u2net.onnx` from the official open-source U-2-Net repository and place it into `models/u2net.onnx`. If the file is not yet downloaded, the engine automatically uses an algorithmic edge-contour fallback so the app works immediately.

---

## License
Open-source under MIT License. Deploy anywhere (Docker, Bare Metal, Air-gapped VPS).
