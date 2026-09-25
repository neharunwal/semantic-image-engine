/**
 * server/index.js
 * ---------------
 * Node.js Express REST API
 * Handles JWT auth, RBAC for nehasb25@gmail.com, photo uploads,
 * calls engine/offline_ml_pipeline.py and engine/decoder.py as subprocesses,
 * and manages local /inventory files.
 */
const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const jwt = require('jsonwebtoken');
const multer = require('multer');

const app = express();
const PORT = process.env.PORT || 3001;
const JWT_SECRET = process.env.JWT_SECRET || 'semantic-engine-secret-2026';

const BASE_DIR = path.resolve(__dirname, '..');
const USERS_FILE = path.join(BASE_DIR, 'storage', 'users.json');
const INVENTORY_DIR = path.join(BASE_DIR, 'inventory');
const UPLOADS_DIR = path.join(BASE_DIR, 'storage', 'uploads');

if (!fs.existsSync(UPLOADS_DIR)) fs.mkdirSync(UPLOADS_DIR, { recursive: true });

const upload = multer({ dest: UPLOADS_DIR });

app.use(cors());
app.use(express.json());

// Auth Middleware
function authenticate(req, res, next) {
  const authHeader = req.headers.authorization;
  if (!authHeader) return res.status(401).json({ error: 'Missing Authorization header' });
  const token = authHeader.replace('Bearer ', '');
  jwt.verify(token, JWT_SECRET, (err, decoded) => {
    if (err) return res.status(403).json({ error: 'Invalid or expired token' });
    req.user = decoded;
    next();
  });
}

function requireAdmin(req, res, next) {
  if (req.user && (req.user.email === 'nehasb25@gmail.com' || req.user.role === 'super_admin')) {
    return next();
  }
  return res.status(403).json({ error: 'Super Admin access required for nehasb25@gmail.com' });
}

// 1. Auth Login Route
app.post('/api/auth/login', (req, res) => {
  const { email } = req.body;
  if (!fs.existsSync(USERS_FILE)) return res.status(500).json({ error: 'Users store missing' });
  const users = JSON.parse(fs.readFileSync(USERS_FILE, 'utf8'));
  const user = users.find(u => u.email.toLowerCase() === (email || '').toLowerCase());
  if (!user) return res.status(404).json({ error: 'User not registered in local storage' });

  const token = jwt.sign({ email: user.email, role: user.role, permissions: user.permissions }, JWT_SECRET, { expiresIn: '7d' });
  res.json({ token, user });
});

// 2. Inventory Listing
app.get('/api/inventory', (req, res) => {
  const result = {};
  if (fs.existsSync(INVENTORY_DIR)) {
    const cats = fs.readdirSync(INVENTORY_DIR).filter(f => fs.statSync(path.join(INVENTORY_DIR, f)).isDirectory());
    for (const cat of cats) {
      result[cat] = fs.readdirSync(path.join(INVENTORY_DIR, cat)).filter(f => /\.(jpg|jpeg|png|webp)$/i.test(f));
    }
  }
  res.json(result);
});

// 3. Process Photo (Runs Python offline ML pipeline)
app.post('/api/photos/process', authenticate, upload.single('image'), (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'Image file required' });
  const mode = req.body.mode || 'semantic';
  const category = req.body.category || 'studio';
  const scriptPath = path.join(BASE_DIR, 'engine', 'offline_ml_pipeline.py');

  const py = spawn('python3', [scriptPath, req.file.path, mode, category]);
  let stdout = '';
  let stderr = '';
  py.stdout.on('data', d => stdout += d.toString());
  py.stderr.on('data', d => stderr += d.toString());

  py.on('close', code => {
    if (code !== 0) {
      console.error(stderr);
      return res.status(500).json({ error: 'Pipeline processing failed', details: stderr });
    }
    try {
      const parsed = JSON.parse(stdout);
      res.json({ success: true, manifest: parsed });
    } catch (e) {
      res.status(500).json({ error: 'Malformed manifest output', raw: stdout });
    }
  });
});

// 4. Admin Inventory CRUD (Super Admin nehasb25@gmail.com only)
app.delete('/api/inventory/:category/:filename', authenticate, requireAdmin, (req, res) => {
  const filePath = path.join(INVENTORY_DIR, req.params.category, req.params.filename);
  if (fs.existsSync(filePath)) {
    fs.unlinkSync(filePath);
    return res.json({ success: true, deleted: req.params.filename });
  }
  res.status(404).json({ error: 'Plate not found in local inventory' });
});

app.listen(PORT, () => console.log(`Semantic Engine REST API running on http://127.0.0.1:${PORT}`));
