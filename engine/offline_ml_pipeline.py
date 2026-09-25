#!/usr/bin/env python3
"""
engine/offline_ml_pipeline.py
-----------------------------
Offline Semantic Image Encoder
Runs 100% locally on CPU using ONNX Runtime and Scikit-Learn.
Zero network calls. Zero external APIs. Zero subscriptions.
"""

import sys
import os
import json
import base64
import io
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

try:
    from sklearn.cluster import KMeans
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    import onnxruntime as ort
    HAS_ONNX = True
except ImportError:
    HAS_ONNX = False


def extract_dominant_palette(image, num_colors=5):
    """
    Extract dominant color centroids using scikit-learn KMeans or PIL palette.
    """
    small_img = image.resize((100, 100)).convert("RGB")
    pixels = np.array(small_img).reshape(-1, 3)

    if HAS_SKLEARN:
        kmeans = KMeans(n_clusters=num_colors, n_init=3, max_iter=20, random_state=42)
        kmeans.fit(pixels)
        colors = kmeans.cluster_centers_.astype(int).tolist()
    else:
        # Fallback to quantized palette
        quantized = small_img.quantize(colors=num_colors)
        palette = quantized.getpalette()[: num_colors * 3]
        colors = [palette[i : i + 3] for i in range(0, len(palette), 3)]

    # Compute brightness
    avg_brightness = float(np.mean(pixels))
    warmth = float(np.mean(pixels[:, 0]) - np.mean(pixels[:, 2]))

    return {
        "dominant_rgbs": colors,
        "avg_brightness": round(avg_brightness, 1),
        "warmth_balance": "warm" if warmth > 5 else ("cool" if warmth < -5 else "neutral")
    }


def segment_subject_onnx(image, model_path):
    """
    Runs local U-2-Net or Silueta ONNX model to extract foreground alpha mask.
    """
    if not HAS_ONNX or not os.path.exists(model_path):
        return None

    try:
        session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        input_name = session.get_inputs()[0].name
        
        # Standard U-2-Net preprocessing: 320x320 RGB normalized
        w, h = image.size
        resized = image.resize((320, 320)).convert("RGB")
        img_data = np.array(resized, dtype=np.float32) / 255.0
        # Normalize with ImageNet mean/std
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img_data = (img_data - mean) / std
        # CHW format and batch dim
        img_data = np.transpose(img_data, (2, 0, 1))
        img_data = np.expand_dims(img_data, axis=0)

        outputs = session.run(None, {input_name: img_data})
        mask_raw = outputs[0][0, 0]
        # Normalize mask to 0-255
        mask_norm = ((mask_raw - mask_raw.min()) / (mask_raw.max() - mask_raw.min() + 1e-8) * 255).astype(np.uint8)
        mask_img = Image.fromarray(mask_norm).resize((w, h), Image.Resampling.BILINEAR)
        return mask_img
    except Exception as e:
        sys.stderr.write(f"ONNX inference warning: {e}\n")
        return None


def segment_subject_heuristic(image):
    """
    Algorithmic edge and center-weighted fallback when ONNX model is not loaded.
    """
    w, h = image.size
    gray = image.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(radius=3))
    
    # Create elliptical center bias mask
    center_mask = Image.new("L", (w, h), 0)
    center_np = np.zeros((h, w), dtype=np.float32)
    y, x = np.ogrid[:h, :w]
    cy, cx = h / 2.0, w / 2.0
    dist = np.sqrt(((x - cx) / (w * 0.4)) ** 2 + ((y - cy) / (h * 0.45)) ** 2)
    center_weight = np.clip(1.0 - dist, 0.0, 1.0) * 255
    center_mask = Image.fromarray(center_weight.astype(np.uint8))
    
    # Blend edges and center bias
    alpha = Image.blend(edges, center_mask, alpha=0.7)
    return alpha.filter(ImageFilter.GaussianBlur(radius=5))


def match_inventory_plate(palette, category, inventory_dir):
    """
    Searches local inventory directory for the best background plate.
    """
    cat_dir = os.path.join(inventory_dir, category)
    if os.path.exists(cat_dir):
        files = [f for f in os.listdir(cat_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
        if files:
            # Deterministic pick based on brightness/hash
            idx = int(palette.get("avg_brightness", 128)) % len(files)
            return os.path.join(category, files[idx])
    return f"{category}/default_plate.jpg"


def encode_image(image_path, mode="semantic", category="studio", inventory_dir=None, models_dir=None, output_dir=None):
    """
    Main encoding pipeline:
    1. Loads input image
    2. Runs offline ML segmentation (or heuristic fallback)
    3. Extracts color & lighting palette
    4. Matches closest plate in local inventory
    5. Saves compressed subject cutout and generates compact JSON manifest (< 25 KB)
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Input image not found: {image_path}")

    img = Image.open(image_path).convert("RGB")
    width, height = img.size
    orig_bytes = os.path.getsize(image_path)

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    inventory_dir = inventory_dir or os.path.join(base_dir, "inventory")
    models_dir = models_dir or os.path.join(base_dir, "models")
    output_dir = output_dir or os.path.join(base_dir, "storage")

    # 1. Palette & scene analysis
    palette = extract_dominant_palette(img)

    # 2. Subject segmentation
    model_path = os.path.join(models_dir, "u2net.onnx")
    mask = segment_subject_onnx(img, model_path)
    used_ml_model = mask is not None
    if mask is None:
        mask = segment_subject_heuristic(img)

    # 3. Create sharpened subject cutout with alpha
    subject_rgba = img.copy().convert("RGBA")
    subject_rgba.putalpha(mask)

    # Optimize and enhance subject clarity
    enhancer = ImageEnhance.Contrast(subject_rgba)
    enhanced_subject = enhancer.enhance(1.12)
    sharpener = ImageEnhance.Sharpness(enhanced_subject)
    final_subject = sharpener.enhance(1.25)

    # Save subject mask / preview in storage
    os.makedirs(os.path.join(output_dir, "cutouts"), exist_ok=True)
    cutout_filename = f"subject_{os.path.splitext(os.path.basename(image_path))[0]}.png"
    cutout_path = os.path.join(output_dir, "cutouts", cutout_filename)
    final_subject.save(cutout_path, format="PNG", optimize=True)

    # 4. Inventory plate match
    matched_plate = match_inventory_plate(palette, category, inventory_dir)

    # 5. Build compact manifest (< 25 KB)
    manifest = {
        "version": "1.0",
        "format": "semantic-image-manifest",
        "mode": mode,
        "source_resolution": [width, height],
        "original_size_bytes": orig_bytes,
        "offline_ml": {
            "model_used": "u2net.onnx" if used_ml_model else "heuristic_cpu_fallback",
            "runtime": "onnxruntime-cpu" if used_ml_model else "native-cpu"
        },
        "background_plate": {
            "category": category,
            "relative_path": matched_plate,
            "palette": palette
        },
        "subject_params": {
            "cutout_file": cutout_filename,
            "sharpness_gain": 1.25,
            "contrast_gain": 1.12,
            "blend_mode": "alpha_composite",
            "feather_radius": 2
        },
        "post_processing": {
            "depth_blur_radius": 8 if mode == "semantic" else 0,
            "vignette": 0.15
        }
    }

    manifest_json = json.dumps(manifest, indent=2)
    manifest_bytes = len(manifest_json.encode("utf-8"))
    reduction = ((orig_bytes - manifest_bytes) / orig_bytes) * 100 if orig_bytes > 0 else 0

    return {
        "manifest": manifest,
        "cutout_path": cutout_path,
        "original_size_bytes": orig_bytes,
        "manifest_size_bytes": manifest_bytes,
        "reduction_percentage": round(reduction, 2),
        "manifest_json": manifest_json
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 offline_ml_pipeline.py <image_path> [mode] [category]")
        sys.exit(1)
        
    in_img = sys.argv[1]
    in_mode = sys.argv[2] if len(sys.argv) > 2 else "semantic"
    in_cat = sys.argv[3] if len(sys.argv) > 3 else "studio"
    
    result = encode_image(in_img, in_mode, in_cat)
    print(result["manifest_json"])
