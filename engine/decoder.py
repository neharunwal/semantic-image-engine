#!/usr/bin/env python3
"""
engine/decoder.py
-----------------
Offline High-Resolution Image Reconstructor
Reads the lightweight .sem.json manifest, retrieves the matching plate
from the local /inventory folder, composites the sharpened subject cutout,
and exports the restored high-resolution image.
"""

import sys
import os
import json
from PIL import Image, ImageFilter, ImageOps, ImageDraw

def create_procedural_plate(width, height, category="studio", palette=None):
    """
    Generates a high-res backdrop when the local plate image is missing.
    """
    img = Image.new("RGB", (width, height), (30, 30, 35))
    draw = ImageDraw.Draw(img)

    dominant = palette.get("dominant_rgbs", [[200, 200, 210]]) if palette else [[200, 200, 210]]
    primary_color = tuple(dominant[0])

    if category == "sunsets":
        for y in range(height):
            ratio = y / max(height, 1)
            r = int(245 * (1 - ratio) + 20 * ratio)
            g = int(120 * (1 - ratio) + 30 * ratio)
            b = int(30 * (1 - ratio) + 90 * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
    elif category == "beaches":
        for y in range(height):
            ratio = y / max(height, 1)
            r = int(135 * (1 - ratio) + 20 * ratio)
            g = int(206 * (1 - ratio) + 120 * ratio)
            b = int(235 * (1 - ratio) + 160 * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
    else:  # Studio clean neutral
        for y in range(height):
            ratio = y / max(height, 1)
            val = int(220 * (1 - ratio * 0.4))
            draw.line([(0, y), (width, y)], fill=(val, val, int(val * 1.05)))

    return img.filter(ImageFilter.GaussianBlur(radius=4))


def decode_manifest(manifest_path_or_dict, inventory_dir=None, storage_dir=None, output_path=None):
    """
    Reconstructs high-res image from manifest + local inventory + subject cutout.
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    inventory_dir = inventory_dir or os.path.join(base_dir, "inventory")
    storage_dir = storage_dir or os.path.join(base_dir, "storage")

    if isinstance(manifest_path_or_dict, str):
        with open(manifest_path_or_dict, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    else:
        manifest = manifest_path_or_dict

    res = manifest.get("source_resolution", [1920, 1080])
    width, height = res[0], res[1]

    bg_info = manifest.get("background_plate", {})
    cat = bg_info.get("category", "studio")
    rel_path = bg_info.get("relative_path", "")
    palette = bg_info.get("palette", {})

    # 1. Load or synthesize background plate
    plate_full_path = os.path.join(inventory_dir, rel_path)
    if os.path.exists(plate_full_path):
        bg_plate = Image.open(plate_full_path).convert("RGB")
        bg_plate = ImageOps.fit(bg_plate, (width, height), method=Image.Resampling.LANCZOS)
    else:
        bg_plate = create_procedural_plate(width, height, category=cat, palette=palette)

    # 2. Apply optional depth-of-field blur to background
    post = manifest.get("post_processing", {})
    blur_rad = post.get("depth_blur_radius", 0)
    if blur_rad > 0:
        bg_plate = bg_plate.filter(ImageFilter.GaussianBlur(radius=blur_rad))

    # 3. Load subject cutout
    subject_params = manifest.get("subject_params", {})
    cutout_file = subject_params.get("cutout_file", "")
    cutout_path = os.path.join(storage_dir, "cutouts", cutout_file)

    if os.path.exists(cutout_path):
        subject = Image.open(cutout_path).convert("RGBA")
        if subject.size != (width, height):
            subject = subject.resize((width, height), Image.Resampling.LANCZOS)
        # Composite foreground over background plate
        composite = Image.new("RGBA", (width, height))
        composite.paste(bg_plate, (0, 0))
        composite.alpha_composite(subject)
        final_img = composite.convert("RGB")
    else:
        final_img = bg_plate

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        final_img.save(output_path, "JPEG", quality=95)

    return final_img

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 decoder.py <manifest.json> <output_image.jpg>")
        sys.exit(1)
        
    decode_manifest(sys.argv[1], output_path=sys.argv[2])
    print(f"Decoded image saved to {sys.argv[2]}")
