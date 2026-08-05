import os
import math
from PIL import Image
import config
import time

Image.MAX_IMAGE_PIXELS = None # OCAD maps can be huge

def generate_tiles(input_png, output_dir, tile_size=512):
    print(f"Loading image {input_png}...")
    start_time = time.time()
    img = Image.open(input_png).convert("RGBA")
    w, h = img.size
    print(f"Loaded in {time.time() - start_time:.1f}s")
    
    max_dim = max(w, h)
    max_zoom = math.ceil(math.log2(max_dim / tile_size))
    target_dim = tile_size * (2 ** max_zoom)
    
    print(f"Image size: {w}x{h}. Padding to {target_dim}x{target_dim}. Max zoom level: {max_zoom}")
    
    padded_img = Image.new("RGBA", (target_dim, target_dim), (255, 255, 255, 0)) # transparent background
    padded_img.paste(img, (0, 0))
    
    for z in range(max_zoom, -1, -1):
        dim_z = tile_size * (2 ** z)
        print(f"Generating zoom level {z} (size: {dim_z}x{dim_z})...")
        
        if z == max_zoom:
            z_img = padded_img
        else:
            z_img = padded_img.resize((dim_z, dim_z), Image.Resampling.LANCZOS)
        
        num_tiles = 2 ** z
        for tx in range(num_tiles):
            for ty in range(num_tiles):
                left = tx * tile_size
                upper = ty * tile_size
                right = left + tile_size
                lower = upper + tile_size
                
                tile = z_img.crop((left, upper, right, lower))
                
                # Skip empty transparent tiles
                extrema = tile.getextrema()
                if extrema[3][1] == 0:
                    continue 
                    
                tile_dir = os.path.join(output_dir, str(z), str(tx))
                os.makedirs(tile_dir, exist_ok=True)
                tile_path = os.path.join(tile_dir, f"{ty}.png")
                tile.save(tile_path, "PNG")

if __name__ == "__main__":
    out_dir = os.path.join("export", "tiles")
    os.makedirs(out_dir, exist_ok=True)
    generate_tiles(config.PNG_FILE, out_dir)
    print("✅ Tiles generated successfully in /export/tiles/")
