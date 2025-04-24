import json
import cv2
import numpy as np
import os
import hashlib

# --- Configuration ---
# Use the name of the JSON file you loaded
json_filename = "cave.json"

# Mapping of cell types to colors (BGR - OpenCV default)
color_map = [
    ('nothing', (80, 80 , 80)),       # 0 - Dark gray — empty space or background
    ('door', (40, 60 , 120)),         # 1 - Dark red/brown — regular doors
    ('secret', (200, 100, 0)),        # 2 - Dark blue — secret doors
    ('locked', (0, 0 , 200)),         # 3 - Red — locked doors
    ('trapped', (0, 140 , 255)),      # 4 - Orange — trapped doors
    ('stair_down', (0, 200 , 0)),     # 5 - Green — stairs down
    ('stair_up', (200, 200 , 0)),     # 6 - Cyan — stairs up
    ('corridor', (120, 120 , 120)),   # 7 - Medium gray — corridors
    ('room', (150, 150 , 150)),       # 8 - Light gray — room floor
    ('perimeter', (80, 80 , 80)),     # 9 - Dark gray — outer walls
    ('block', (233, 233 , 233))       # 10 - Very light gray — inner walls
]

# --- End of Configuration ---

def pad_image(img: np.ndarray, n: int, pad_value=0) -> np.ndarray:
    if img.ndim == 2:
        # 2D image (height, width)
        pad_width = ((n, n), (n, n))
    elif img.ndim == 3:
        # 3D image (height, width, channels)
        pad_width = ((n, n), (n, n), (0, 0))
    else:
        raise ValueError("Image must have 2 or 3 dimensions")
    
    return np.pad(img, pad_width, mode='constant', constant_values=pad_value)


def grid_numpy(image, rows, cols, cor=(0, 255, 0), espessura=1):
    """
    Efficiently applies a grid to an image using NumPy slicing.

    Args:
        image (np.ndarray): The input image (BGR color or grayscale).
        rows (int): Number of grid rows (will result in rows-1 horizontal lines).
        cols (int): Number of grid columns (will result in cols-1 vertical lines).
        cor (tuple or int): Grid line color (default: BGR green).
                            For grayscale images, use an int (0-255).
        espessura (int): Thickness of grid lines in pixels (default: 1).

    Returns:
        np.ndarray: A copy of the image with the grid drawn.
    """
    # Create a copy of the image to avoid modifying the original
    imagem_com_grid = image.copy()
    altura, largura = imagem_com_grid.shape[:2]

    # Calculate actual grid spacing
    step_y = altura / rows
    step_x = largura / cols

    # --- Horizontal lines ---
    for r in range(1, rows):
        y = int(r * step_y)  # Central position of the line

        # Calculate the line boundaries based on thickness
        # Ensure indices do not go out of image bounds
        y_inicio = max(0, y - espessura // 2)
        # Upper bound is exclusive in slicing, so +1 if thickness is odd
        y_fim = min(altura, y + (espessura + 1) // 2)

        # Apply color to the horizontal line slice
        # imagem_com_grid[y_inicio:y_fim, :, :] selects:
        #   - Rows from y_inicio to y_fim-1
        #   - All columns (:)
        #   - All color channels (:) - if color
        imagem_com_grid[y_inicio:y_fim, :] = cor  # NumPy handles 2D or 3D

    # --- Vertical lines ---
    for c in range(1, cols):
        x = int(c * step_x)  # Central position of the column

        # Calculate the column boundaries based on thickness
        x_inicio = max(0, x - espessura // 2)
        x_fim = min(largura, x + (espessura + 1) // 2)

        # Apply color to the vertical column slice
        # imagem_com_grid[:, x_inicio:x_fim, :] selects:
        #   - All rows (:)
        #   - Columns from x_inicio to x_fim-1
        #   - All color channels (:) - if color
        imagem_com_grid[:, x_inicio:x_fim] = cor

    return imagem_com_grid




def load_dungeon(json_path, cell_size = 11, return_values = False):
    """
    Reads a dungeon JSON file and creates a PNG image using OpenCV.

    Args:
        json_path (str): The path to the dungeon JSON file.
        output_path (str): The path where to save the resulting PNG image.
        cell_size (int): The size (width and height) in pixels for each map cell.
    """
    try:
        with open(json_path, 'r') as f:
            dungeon_data = json.load(f)
        print(f"JSON file '{json_path}' successfully loaded.")
    except FileNotFoundError:
        print(f"Error: JSON file '{json_path}' not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON file '{json_path}'. Check the format.")
        return
    except Exception as e:
        print(f"An unexpected error occurred while reading the JSON: {e}")
        return

    # Check if essential keys exist
    if 'cells' not in dungeon_data or 'cell_bit' not in dungeon_data:
        print("Error: JSON file does not contain 'cells' or 'cell_bit' keys.")
        return

    cells = dungeon_data['cells']
    cell_bits = dungeon_data['cell_bit']

    # Get map dimensions
    if not cells:
        print("Error: The 'cells' matrix is empty.")
        return
    rows = len(cells)
    cols = len(cells[0]) if rows > 0 else 0
    if cols == 0:
        print("Error: Map has no columns.")
        return

    print(f"Map dimensions: {rows} rows x {cols} columns.")

    
    
    cells = np.array(cells, dtype = np.uint32)
    not_processed = np.ones((rows, cols), dtype=bool)
    
    if return_values:
        values = np.zeros((rows, cols), dtype=np.int32)
        i = 0
        for key, color in color_map:
            
            bit = cell_bits.get(key, 0)
            cond_mask = ( (cells & bit) != 0 ) & not_processed

            values[cond_mask] = i

            not_processed[cond_mask] = False
            i += 1
        values = pad_image(values, 4, 0)
        

    not_processed = np.ones((rows, cols), dtype=bool)
    image = np.full((rows, cols, 3), ( 80, 80, 80), dtype=np.uint8)
    print(f"Image size: {rows*cell_size}x{cols*cell_size} pixels.")
    
    
    for key, color in color_map:
        bit = cell_bits.get(key, 0)
        cond_mask = ( (cells & bit) != 0 ) & not_processed
        image[cond_mask] = color

        not_processed[cond_mask] = False
    
    

    image = pad_image(image, 4, 80)
    image = cv2.resize(image, ((cols+8)*cell_size, (rows+8)*cell_size), interpolation=cv2.INTER_AREA)
    image = grid_numpy(image, rows+8, cols+8, cor=(0, 0, 0), espessura=1)

    md5_hash = hashlib.md5(image.tobytes()).hexdigest()
    output_filename = f"{md5_hash}.png"
    

    if os.path.exists(output_filename):
        if return_values:
            return values, output_filename
        print(f"The image with hash {md5_hash} already exists as '{output_filename}'.")
        return

    try:
        # Script path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        full_output_path = os.path.join(script_dir, output_filename)
        cv2.imwrite(full_output_path, image)
        print(f"Dungeon image saved as '{full_output_path}'")
    except Exception:
        # Fallback: try saving in current directory
        try:
            cv2.imwrite(output_filename, image)
            print(f"Dungeon image saved as '{output_filename}' (in current directory)")
        except Exception as e_fallback:
            print(f"Error saving image: {e_fallback}")
    if return_values:
        return values, output_filename



if __name__ == "__main__":
    
    load_dungeon(json_filename) 
    
          
         
         