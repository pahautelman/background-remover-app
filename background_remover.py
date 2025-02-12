import os
import zipfile
from pathlib import Path
from PIL import Image, ImageOps
import pillow_heif  # New import for HEIC support
pillow_heif.register_heif_opener()  # Register HEIC file opener with Pillow
import torch
import tempfile
from carvekit.api.high import HiInterface
from typing import List
import rx
from rx import operators as ops

# Initialize CarveKit interface with your configuration
def initialize_interface(use_gpu: bool) -> HiInterface:
    if use_gpu:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    else:
        device = 'cpu'
    return HiInterface(
        object_type="object",
        batch_size_seg=2,
        batch_size_matting=1,
        device=device,
        seg_mask_size=640,
        fp16=True if device == 'cuda' else False
    )

def trim_transparency(image: Image.Image) -> Image.Image:
    """Trim transparent borders from image"""
    bbox = image.getbbox()
    return image.crop(bbox) if bbox else image

def calculate_target_size(original_size: tuple) -> tuple:
    """
    Calculate target size based on scaling rules:
    - Max width: 1400px
    - Max height: 2400px
    - Maintain aspect ratio
    - Scale to whichever dimension is closer to target
    """
    orig_width, orig_height = original_size
    width_ratio = 1400 / orig_width
    height_ratio = 2400 / orig_height
    
    # Choose the ratio that brings the closer dimension to its target
    scale = min(width_ratio, height_ratio)
    
    new_width = int(orig_width * scale)
    new_height = int(orig_height * scale)
    
    # Ensure we don't exceed maximum dimensions
    return (min(new_width, 1400), min(new_height, 2400))

def auto_rotate(image: Image.Image) -> Image.Image:
    """Fix image orientation using EXIF data"""
    return ImageOps.exif_transpose(image)

def ensure_portrait_mode(image: Image.Image) -> Image.Image:
    """Flips image so that it is in portrait mode"""
    if image.width > image.height:
        return image.transpose(Image.ROTATE_270)
    return image

def process_image(image: Image.Image, interface: HiInterface) -> Image.Image:
    """Full processing pipeline for a single image"""
    # Convert to portrait mode
    image_prep = ensure_portrait_mode(image)

    # Remove background
    bg_removed = interface([image_prep])[0]
    
    # Trim transparent areas
    trimmed = trim_transparency(bg_removed)
    del bg_removed
    
    # Auto-rotate based on EXIF data
    rotated = auto_rotate(trimmed)
    
    # Resize according to rules
    target_size = calculate_target_size(rotated.size)
    resized = rotated.resize(target_size, Image.LANCZOS)
    
    # Create final canvas
    canvas = Image.new("RGB", (2048, 2732), (255, 255, 255))
    x = (2048 - resized.width) // 2
    y = (2732 - resized.height) // 2
    canvas.paste(resized, (x, y), resized.convert("RGBA") if resized.mode == 'RGBA' else None)
    
    return canvas

def process_files(input_paths, use_gpu: bool = False) -> rx.Observable:
    return rx.of(input_paths).pipe(
        ops.map(lambda paths: _process_files(paths, use_gpu))
    )

def _process_files(input_paths: List[str], use_gpu: bool) -> tempfile.NamedTemporaryFile:
    """Process multiple files and create a temporary ZIP archive."""
    interface = initialize_interface(use_gpu)
    
    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Process all images
            for input_path in input_paths:
                try:
                    with Image.open(input_path) as img:
                        processed = process_image(img, interface)
                        filename = Path(input_path).stem + "_processed.png"
                        save_path = os.path.join(temp_dir, filename)
                        processed.save(save_path, "PNG")
                except Exception as e:
                    print(f"Error processing {input_path}: {str(e)}")
                    continue
            
            # Create ZIP archive
            with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        zipf.write(
                            os.path.join(root, file),
                            arcname=file
                        )

        return temp_zip  # Return the temporary ZIP file
    
    except Exception as e:
        os.remove(temp_zip.name)  # Clean up in case of failure
        raise e
    
    finally:
        del interface  # Clean up CarveKit interface
