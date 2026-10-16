"""
Image Preprocessor for Document AI.
Provides clean, deterministic image enhancement for document OCR and previews
using Pillow and NumPy (grayscale, contrast stretching, adaptive binarization, rotation).
"""

from typing import Tuple
from PIL import Image, ImageOps, ImageFilter
import numpy as np

from document_ai.logging_config import get_logger

logger = get_logger("image_preprocessor")


def convert_to_grayscale(img: Image.Image) -> Image.Image:
    """Converts image to grayscale if not already in L mode."""
    if img.mode != "L":
        return img.convert("L")
    return img


def enhance_contrast(img: Image.Image) -> Image.Image:
    """Applies autocontrast to normalize dynamic range."""
    gray = convert_to_grayscale(img)
    return ImageOps.autocontrast(gray, cutoff=1)


def binarize_otsu(img: Image.Image) -> Image.Image:
    """
    Computes Otsu's thresholding deterministically on grayscale image.
    Separates foreground document ink from background paper texture.
    """
    gray = convert_to_grayscale(img)
    arr = np.array(gray)

    # Calculate histogram and probabilities
    hist, bin_edges = np.histogram(arr, bins=256, range=(0, 256))
    hist = hist.astype(float)
    total_pixels = arr.size

    current_max = 0.0
    threshold = 127
    sum_total = np.dot(np.arange(256), hist)

    sum_b = 0.0
    weight_b = 0.0

    for i in range(256):
        weight_b += hist[i]
        if weight_b == 0:
            continue
        weight_f = total_pixels - weight_b
        if weight_f == 0:
            break

        sum_b += i * hist[i]
        mean_b = sum_b / weight_b
        mean_f = (sum_total - sum_b) / weight_f

        # Between-class variance
        between_var = weight_b * weight_f * ((mean_b - mean_f) ** 2)
        if between_var > current_max:
            current_max = between_var
            threshold = i

    # Threshold image
    binarized_arr = np.where(arr > threshold, 255, 0).astype(np.uint8)
    return Image.fromarray(binarized_arr, mode="L")


def deskew_and_denoise(img: Image.Image) -> Image.Image:
    """
    Applies light median filtering to remove scanner salt-and-pepper noise.
    """
    gray = convert_to_grayscale(img)
    # Light median filter removes high-frequency scanner noise without blurring thin fonts
    filtered = gray.filter(ImageFilter.MedianFilter(size=3))
    return filtered


def prepare_clean_image(img: Image.Image) -> Image.Image:
    """Flattens alpha channels onto pure white canvas and handles palette transparency cleanly."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        canvas = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        canvas.paste(rgba, mask=rgba.split()[3])
        return canvas.convert("RGB")
    return img.convert("RGB")


def smart_upscale_for_ocr(img: Image.Image, target_dimension: int = 2000) -> Image.Image:
    """
    Upscales low-resolution images (such as web PNGs, mobile photos, or 72 DPI scans)
    to match Tesseract's optimal font x-height (~30-33 pixels, ~300 DPI).
    """
    w, h = img.size
    max_dim = max(w, h)
    if max_dim < target_dimension:
        scale = target_dimension / max_dim
        new_w = int(w * scale)
        new_h = int(h * scale)
        return img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    return img


def preprocess_for_ocr(img: Image.Image) -> Image.Image:
    """
    Industry-grade image preprocessing pipeline for Tesseract 5 LSTM OCR:
    1. Alpha flattening onto white canvas
    2. Smart upscaling for small text/resolutions
    3. Grayscale conversion
    4. Dynamic range autocontrast
    5. Light median denoising
    """
    clean_rgb = prepare_clean_image(img)
    upscaled = smart_upscale_for_ocr(clean_rgb)
    enhanced = enhance_contrast(upscaled)
    denoised = deskew_and_denoise(enhanced)
    return denoised
