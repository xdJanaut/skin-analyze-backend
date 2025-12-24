from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from typing import List, Dict, Optional

def draw_detections(
    image_path: str, 
    predictions: list, 
    output_path: str,
    model_sources: Optional[List[str]] = None  # NEW parameter
) -> str:
    """
    Draw bounding boxes and labels on the image with color coding for model sources
    Returns path to the annotated image
    """
    # Open image
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)
    
    # Color mapping for different model sources
    source_colors = {
        'primary': (255, 0, 0),      # Red for acne/primary detections
        'secondary': (0, 150, 255),  # Blue for secondary conditions
        'default': (255, 107, 107)   # Default red
    }
    
    # Class-specific colors (fallback if no source specified)
    class_colors = {
        'Pimples': '#FF6B6B',      # Red
        'Acne': '#FF6B6B',         # Red
        'blackhead': '#4ECDC4',    # Teal
        'whitehead': '#95E1D3',    # Light teal
        'cystic': '#FF0000',       # Bright red
        'acne_scars': '#FFA07A',   # Light salmon
        'papular': '#FF8C69',      # Salmon
        'purulent': '#DC143C',     # Crimson
        'conglobata': '#8B0000',   # Dark red
        'folliculitis': '#FFB6C1', # Light pink
        'milium': '#FFDAB9',       # Peach
        'keloid': '#CD5C5C',       # Indian red
        'flat_wart': '#F08080',    # Light coral
        'syringoma': '#FFE4E1',    # Misty rose
        'crystalline': '#B0E0E6',  # Powder blue
        'melasma': '#8B4513',      # Brown for melasma
        'rosacea': '#FF69B4',      # Pink for rosacea
    }
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    for idx, pred in enumerate(predictions):
        x = pred['x']
        y = pred['y']
        width = pred['width']
        height = pred['height']
        confidence = pred['confidence']
        class_name = pred.get('class', 'unknown')
        
        # Calculate box coordinates
        left = x - width / 2
        top = y - height / 2
        right = x + width / 2
        bottom = y + height / 2
        
        # Determine color based on model source if available
        if model_sources and idx < len(model_sources):
            source = model_sources[idx]
            color = source_colors.get(source, source_colors['default'])
        else:
            # Fallback to class-based colors
            color_hex = class_colors.get(class_name, '#FF6B6B')
            color = tuple(int(color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        
        # Draw bounding box
        draw.rectangle(
            [(left, top), (right, bottom)],
            outline=color,
            width=3
        )
        
        # Draw label background
        label = f"{class_name} {confidence*100:.0f}%"
        
        # Get text size for background
        try:
            bbox = draw.textbbox((left, top), label, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except:
            # Fallback for older PIL versions
            text_width, text_height = 150, 20
        
        # Draw label background rectangle
        draw.rectangle(
            [(left, top - text_height - 4), (left + text_width + 8, top)],
            fill=color
        )
        
        # Draw label text
        draw.text(
            (left + 4, top - text_height - 2),
            label,
            fill=(255, 255, 255),  # White text
            font=font
        )
    
    
    # Save annotated image
    img.save(output_path)
    return output_path

