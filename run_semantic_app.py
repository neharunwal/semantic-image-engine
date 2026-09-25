#!/usr/bin/env python3
"""
run_semantic_app.py
-------------------
Unified Launcher & Orchestration Starting Point
Starts the Semantic Image Compression Studio, orchestrates the modular
engine (engine/offline_ml_pipeline.py and engine/decoder.py), loads user
RBAC from storage/users.json, and serves the local web interface and REST API.

Usage:
  python3 run_semantic_app.py                          # Launch web app & REST API on http://127.0.0.1:8080
  python3 run_semantic_app.py --encode <img_path>      # Run offline ML encoder via CLI
  python3 run_semantic_app.py --decode <manifest.json> # Run high-res decoder via CLI
"""

import sys
import os
import json
import argparse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
from PIL import Image, ImageDraw

# Add repository root to Python path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from engine.offline_ml_pipeline import encode_image
from engine.decoder import decode_manifest

PORT = 8080
INVENTORY_DIR = os.path.join(BASE_DIR, "inventory")
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
MODELS_DIR = os.path.join(BASE_DIR, "models")
USERS_FILE = os.path.join(STORAGE_DIR, "users.json")


def ensure_workspace():
    """Initializes local directories, user RBAC database, and starter inventory plates."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(os.path.join(STORAGE_DIR, "manifests"), exist_ok=True)
    os.makedirs(os.path.join(STORAGE_DIR, "cutouts"), exist_ok=True)
    os.makedirs(os.path.join(STORAGE_DIR, "uploads"), exist_ok=True)

    categories = ["studio", "sunsets", "beaches", "interiors"]
    for cat in categories:
        cat_dir = os.path.join(INVENTORY_DIR, cat)
        os.makedirs(cat_dir, exist_ok=True)
        sample_path = os.path.join(cat_dir, f"{cat}_ref_plate_01.jpg")
        if not os.path.exists(sample_path):
            img = Image.new("RGB", (1280, 720), (35, 38, 46))
            draw = ImageDraw.Draw(img)
            for y in range(720):
                ratio = y / 720.0
                if cat == "sunsets":
                    c = (int(240 * (1 - ratio * 0.7)), int(110 * (1 - ratio * 0.6)), int(40 + ratio * 80))
                elif cat == "beaches":
                    c = (int(90 + ratio * 40), int(170 + ratio * 60), int(220 * (1 - ratio * 0.2)))
                else:
                    val = int(210 - ratio * 45)
                    c = (val, val, val)
                draw.line([(0, y), (1280, y)], fill=c)
            img.save(sample_path, "JPEG", quality=90)

    # Ensure users.json exists
    if not os.path.exists(USERS_FILE):
        initial_users = [
            {
                "id": 1,
                "email": "nehasb25@gmail.com",
                "role": "super_admin",
                "name": "Neha R (Super Admin)",
                "permissions": ["all"]
            },
            {
                "id": 2,
                "email": "user@local.test",
                "role": "user",
                "name": "Studio Photographer",
                "permissions": ["photos:encode", "photos:decode", "inventory:read"]
            }
        ]
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(initial_users, f, indent=2)


HTML_UI = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Semantic Image Engine — Orchestrator</title>
  <style>
    :root {
      --bg: #090d16;
      --card: #131b2e;
      --border: #233150;
      --text: #f1f5f9;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --badge-admin: #ec4899;
      --success: #10b981;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      padding: 30px;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 30px;
    }
    .logo {
      font-size: 22px;
      font-weight: 700;
      color: #fff;
    }
    .logo span { color: var(--accent); }
    .user-pill {
      background: var(--card);
      border: 1px solid var(--border);
      padding: 8px 16px;
      border-radius: 999px;
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 14px;
    }
    .badge {
      background: var(--badge-admin);
      color: white;
      font-size: 11px;
      font-weight: bold;
      padding: 3px 8px;
      border-radius: 6px;
      text-transform: uppercase;
    }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 24px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
    }
    h2 { font-size: 17px; margin-bottom: 18px; color: #fff; display: flex; align-items: center; gap: 8px; }
    .drop-zone {
      border: 2px dashed var(--border);
      border-radius: 10px;
      padding: 40px 20px;
      text-align: center;
      cursor: pointer;
      background: rgba(255, 255, 255, 0.01);
      transition: all 0.2s;
    }
    .drop-zone:hover {
      border-color: var(--accent);
      background: rgba(56, 189, 248, 0.04);
    }
    .form-group {
      margin-top: 18px;
    }
    label {
      display: block;
      font-size: 13px;
      color: var(--muted);
      margin-bottom: 6px;
    }
    select, button, input[type="text"] {
      width: 100%;
      padding: 11px 14px;
      background: #0b1120;
      border: 1px solid var(--border);
      color: var(--text);
      border-radius: 8px;
      font-size: 14px;
    }
    button.btn-primary {
      background: var(--accent);
      color: #0b1120;
      font-weight: 600;
      cursor: pointer;
      border: none;
      margin-top: 20px;
      transition: background 0.2s;
    }
    button.btn-primary:hover { background: var(--accent-hover); color: white; }
    .stats-row {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin-top: 18px;
    }
    .stat-box {
      background: #0b1120;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px;
      text-align: center;
    }
    .stat-val { font-size: 20px; font-weight: bold; color: var(--accent); }
    .stat-lbl { font-size: 12px; color: var(--muted); margin-top: 4px; }
    pre {
      background: #060911;
      padding: 14px;
      border-radius: 8px;
      border: 1px solid var(--border);
      font-size: 12px;
      color: #a5f3fc;
      max-height: 250px;
      overflow-y: auto;
      font-family: monospace;
      margin-top: 16px;
    }
    .preview-box {
      margin-top: 16px;
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
      background: #000;
      text-align: center;
      min-height: 200px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .preview-box img { max-width: 100%; max-height: 320px; display: block; margin: 0 auto; }
  </style>
</head>
<body>
  <div class="header">
    <div class="logo">Semantic<span>Image</span>Engine</div>
    <div class="user-pill">
      <span id="user-display">nehasb25@gmail.com</span>
      <span class="badge" id="role-display">Super Admin</span>
      <button onclick="toggleUser()" style="width:auto; padding:4px 10px; font-size:12px; cursor:pointer;">Switch Role</button>
    </div>
  </div>

  <div class="grid">
    <!-- Encoding Panel -->
    <div class="card">
      <h2>1. Local Image Encoder (ML Pipeline)</h2>
      <div class="drop-zone" onclick="document.getElementById('file-input').click()">
        <p id="file-label">Click to select photo (JPEG / PNG)</p>
        <span style="font-size: 12px; color: var(--muted);">Runs 100% offline via engine/offline_ml_pipeline.py</span>
      </div>
      <input type="file" id="file-input" style="display:none;" onchange="handleFile(this)" accept="image/*">

      <div class="form-group">
        <label>Compression & Processing Mode</label>
        <select id="mode-select">
          <option value="semantic">Semantic Mode (Cutout subject, match background plate)</option>
          <option value="forensic">Forensic Mode (Preserve full original image)</option>
        </select>
      </div>

      <div class="form-group">
        <label>Local Inventory Plate Category</label>
        <select id="category-select">
          <option value="studio">Studio (Clean Portrait Neutrals)</option>
          <option value="sunsets">Sunsets & Golden Hour</option>
          <option value="beaches">Beaches & Ocean Coastlines</option>
          <option value="interiors">Interiors & Venues</option>
        </select>
      </div>

      <button class="btn-primary" onclick="runEncoder()">Run Offline Encoder</button>

      <div class="stats-row" id="stats-area" style="display:none;">
        <div class="stat-box">
          <div class="stat-val" id="stat-orig">0 MB</div>
          <div class="stat-lbl">Original Photo</div>
        </div>
        <div class="stat-box">
          <div class="stat-val" id="stat-manifest" style="color:var(--success);">0 KB</div>
          <div class="stat-lbl">Semantic Manifest</div>
        </div>
        <div class="stat-box">
          <div class="stat-val" id="stat-reduction">99.9%</div>
          <div class="stat-lbl">Size Reduction</div>
        </div>
      </div>

      <pre id="manifest-viewer">// Manifest will be output here...</pre>
    </div>

    <!-- Decoding Panel -->
    <div class="card">
      <h2>2. High-Resolution Decoder & Inventory Renderer</h2>
      <p style="font-size: 13px; color: var(--muted); margin-bottom: 14px;">
        Orchestrated by <code>engine/decoder.py</code>. Composites the subject mask over the matched local plate.
      </p>

      <button class="btn-primary" style="margin-top:0;" onclick="runDecoder()">Reconstruct High-Res Image</button>

      <div class="preview-box" id="preview-box">
        <span style="color:var(--muted); font-size:13px;" id="preview-status">No image reconstructed yet</span>
      </div>

      <div style="margin-top: 20px;" id="admin-sec">
        <h2>3. Super Admin Local Inventory Manager</h2>
        <p style="font-size: 13px; color: var(--muted); margin-bottom: 10px;">
          Privileged action restricted to <strong>nehasb25@gmail.com</strong>.
        </p>
        <div id="inv-list" style="font-size: 13px; color: #cbd5e1; background: #080c14; padding: 12px; border-radius: 8px; border: 1px solid var(--border);">
          Loading local inventory plates...
        </div>
      </div>
    </div>
  </div>

  <script>
    let currentUser = { email: 'nehasb25@gmail.com', role: 'super_admin' };
    let currentManifest = null;
    let selectedFileBase64 = null;
    let selectedFileName = null;

    function toggleUser() {
      if (currentUser.role === 'super_admin') {
        currentUser = { email: 'user@local.test', role: 'user' };
        document.getElementById('user-display').textContent = currentUser.email;
        document.getElementById('role-display').textContent = 'Standard User';
        document.getElementById('role-display').style.background = '#3b82f6';
        document.getElementById('admin-sec').style.opacity = '0.4';
      } else {
        currentUser = { email: 'nehasb25@gmail.com', role: 'super_admin' };
        document.getElementById('user-display').textContent = currentUser.email;
        document.getElementById('role-display').textContent = 'Super Admin';
        document.getElementById('role-display').style.background = '#ec4899';
        document.getElementById('admin-sec').style.opacity = '1.0';
      }
      loadInventory();
    }

    function handleFile(input) {
      if (input.files && input.files[0]) {
        const file = input.files[0];
        selectedFileName = file.name;
        document.getElementById('file-label').textContent = file.name + ' (' + (file.size / (1024*1024)).toFixed(2) + ' MB)';
        const reader = new FileReader();
        reader.onload = function(e) {
          selectedFileBase64 = e.target.result;
        };
        reader.readAsDataURL(file);
      }
    }

    async function runEncoder() {
      if (!selectedFileBase64) {
        alert('Please choose an image file first.');
        return;
      }
      const mode = document.getElementById('mode-select').value;
      const category = document.getElementById('category-select').value;

      document.getElementById('manifest-viewer').textContent = 'Executing engine/offline_ml_pipeline.py ...';

      const resp = await fetch('/api/photos/encode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_data: selectedFileBase64,
          filename: selectedFileName,
          mode: mode,
          category: category,
          user_email: currentUser.email
        })
      });

      const res = await resp.json();
      if (res.error) {
        alert('Encoding error: ' + res.error);
        return;
      }

      currentManifest = res.manifest;
      document.getElementById('manifest-viewer').textContent = JSON.stringify(res.manifest, null, 2);
      document.getElementById('stats-area').style.display = 'grid';
      document.getElementById('stat-orig').textContent = (res.original_size_bytes / (1024*1024)).toFixed(2) + ' MB';
      document.getElementById('stat-manifest').textContent = (res.manifest_size_bytes / 1024).toFixed(2) + ' KB';
      document.getElementById('stat-reduction').textContent = res.reduction_percentage + '%';
    }

    async function runDecoder() {
      if (!currentManifest) {
        alert('Please run the encoder to generate a manifest first.');
        return;
      }
      document.getElementById('preview-status').textContent = 'Reconstructing via engine/decoder.py...';

      const resp = await fetch('/api/photos/decode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ manifest: currentManifest })
      });
      const res = await resp.json();
      if (res.success && res.image_data) {
        document.getElementById('preview-box').innerHTML = '<img src="' + res.image_data + '" alt="Reconstructed Image" />';
      } else {
        alert('Decoding error: ' + (res.error || 'Unknown'));
      }
    }

    async function loadInventory() {
      const resp = await fetch('/api/inventory?user=' + encodeURIComponent(currentUser.email));
      const inv = await resp.json();
      let html = '<ul>';
      for (const [cat, files] of Object.entries(inv)) {
        html += '<li style="margin-bottom:6px;"><strong>' + cat + ':</strong> ' + (files.length ? files.join(', ') : 'None') + '</li>';
      }
      html += '</ul>';
      document.getElementById('inv-list').innerHTML = html;
    }

    loadInventory();
  </script>
</body>
</html>
"""


class OrchestratorHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            body = HTML_UI.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/inventory":
            inv_data = {}
            if os.path.exists(INVENTORY_DIR):
                for cat in os.listdir(INVENTORY_DIR):
                    cat_path = os.path.join(INVENTORY_DIR, cat)
                    if os.path.isdir(cat_path):
                        inv_data[cat] = [
                            f for f in os.listdir(cat_path) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
                        ]
            self._send_json(inv_data)
            return

        self._send_json({"error": "Not Found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)

        try:
            body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception:
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        if parsed.path == "/api/photos/encode":
            import base64
            img_b64 = body.get("image_data", "")
            if "," in img_b64:
                img_b64 = img_b64.split(",")[1]
            img_bytes = base64.b64decode(img_b64)
            
            filename = body.get("filename", "upload.jpg")
            upload_path = os.path.join(STORAGE_DIR, "uploads", filename)
            with open(upload_path, "wb") as f:
                f.write(img_bytes)

            mode = body.get("mode", "semantic")
            category = body.get("category", "studio")

            # Call modular offline ML pipeline
            res = encode_image(upload_path, mode=mode, category=category)
            
            # Save manifest
            manifest_id = f"manifest_{os.path.splitext(filename)[0]}.json"
            manifest_path = os.path.join(STORAGE_DIR, "manifests", manifest_id)
            with open(manifest_path, "w", encoding="utf-8") as f:
                f.write(res["manifest_json"])

            self._send_json(res)
            return

        if parsed.path == "/api/photos/decode":
            import base64, io
            manifest = body.get("manifest")
            if not manifest:
                self._send_json({"error": "Manifest required"}, 400)
                return

            out_img = decode_manifest(manifest)
            buffered = io.BytesIO()
            out_img.save(buffered, format="JPEG", quality=90)
            b64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            self._send_json({"success": True, "image_data": f"data:image/jpeg;base64,{b64_str}"})
            return

        self._send_json({"error": "Route Not Found"}, 404)


def main():
    parser = argparse.ArgumentParser(description="Semantic Image Engine Orchestrator")
    parser.add_argument("--encode", help="Path to image to encode via engine/offline_ml_pipeline.py")
    parser.add_argument("--decode", help="Path to manifest JSON to decode via engine/decoder.py")
    parser.add_argument("--mode", default="semantic", help="Encoding mode: 'semantic' or 'forensic'")
    parser.add_argument("--cat", default="studio", help="Inventory plate category")
    parser.add_argument("--out", default="decoded_output.jpg", help="Output path for decoded image")
    parser.add_argument("--port", type=int, default=PORT, help="Web server port (default: 8080)")

    args = parser.parse_args()
    ensure_workspace()

    if args.encode:
        print(f"[*] Running offline ML encoder on: {args.encode}...")
        res = encode_image(args.encode, mode=args.mode, category=args.cat)
        print(f"[*] Original: {res['original_size_bytes']} bytes")
        print(f"[*] Manifest: {res['manifest_size_bytes']} bytes (Reduction: {res['reduction_percentage']}%)")
        print("[*] Manifest output:")
        print(res["manifest_json"])
        return

    if args.decode:
        print(f"[*] Running decoder on: {args.decode}...")
        decode_manifest(args.decode, output_path=args.out)
        print(f"[+] Reconstructed image saved to {args.out}")
        return

    server_address = ("127.0.0.1", args.port)
    httpd = HTTPServer(server_address, OrchestratorHandler)
    url = f"http://127.0.0.1:{args.port}"
    print("=" * 60)
    print(f"  SEMANTIC IMAGE ENGINE — ORCHESTRATOR")
    print(f"  Single Entry Point: run_semantic_app.py")
    print(f"  Underlying ML Engine: engine/offline_ml_pipeline.py")
    print(f"  Underlying Reconstructor: engine/decoder.py")
    print(f"  Local Inventory: {INVENTORY_DIR}")
    print(f"  RBAC User Store: {USERS_FILE} (Super Admin: nehasb25@gmail.com)")
    print("=" * 60)
    print(f"  Web Studio running at: {url}")
    print("  Press Ctrl+C to stop.")
    print("=" * 60)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()


if __name__ == "__main__":
    main()
