import json
import random
import cv2
import numpy as np
import os
import hashlib

# --- Configuration ---

# Mapping of cell types to colors (BGR - OpenCV default)
def map_to_rgb(map_array):
    color_map = [
        (80, 80 , 80),     # 0 - Dark gray — empty space or background
        (40, 60 , 120),    # 1 - Dark red/brown — regular doors
       (80, 80 , 80),     # 2 - Dark gray — secret doors
        (0, 0 , 200),      # 3 - Red — locked doors
       (40, 60 , 120),  # 4 - Dark red/brown — trap doors
        (0, 200 , 0),      # 5 - Green — stairs down
        (200, 200 , 0),    # 6 - Cyan — stairs up
        (120, 120 , 120),  # 7 - Medium gray — corridors
        (150, 150 , 150),  # 8 - Light gray — room floor
        (80, 80 , 80),     # 9 - Dark gray — walls
    ]
    
    h, w = map_array.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    
    for idx, color in enumerate(color_map):
        rgb[map_array == idx] = color
    return rgb

EMPTY = 0
DOOR = 1
SECRET = 2
LOCKED = 3
TRAPPED = 4
STAIR_DOWN = 5
STAIR_UP = 6
CORRIDOR = 7
ROOM = 8
WALL = 9


MIN_ROOM = 4      # Minimum inner room size
MARGIN = 2        # Buffer around rooms
MIN_LEAF = MIN_ROOM + MARGIN * 2 # Min partition size
MIN_SPLIT = MIN_LEAF * 2     # Min size to allow splitting


class Node:
    __slots__ = ('x', 'y', 'w', 'h', 'left', 'right', 'room')

    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.left = self.right = None
        self.room = None # (rx, ry, rw, rh)

    def split(self):
        if self.left or self.right:
            return False

        split_horizontally = random.choice((True, False))
        if self.w > self.h and self.w / self.h >= 1.25:
            split_horizontally = True
        elif self.h > self.w and self.h / self.w >= 1.25:
            split_horizontally = False

        # max_dim = max(self.w, self.h) - MIN_LEAF
        can_split_horizontally = self.w >= MIN_SPLIT
        can_split_vertically = self.h >= MIN_SPLIT

        if not can_split_horizontally and not can_split_vertically:
             return False # Cannot split in either direction

        # If preferred split isn't possible, try the other
        if split_horizontally and not can_split_horizontally:
            split_horizontally = False
        elif not split_horizontally and not can_split_vertically:
            split_horizontally = True

        # Perform the split
        if split_horizontally:
            if not can_split_horizontally: return False # Double check
            max_split = self.w - MIN_LEAF
            if max_split < MIN_LEAF: return False
            split_pos = random.randint(MIN_LEAF, max_split)
            self.left = Node(self.x, self.y, split_pos, self.h)
            self.right = Node(self.x + split_pos, self.y, self.w - split_pos, self.h)
            return True
        else: # Split vertically
            if not can_split_vertically: return False # Double check
            max_split = self.h - MIN_LEAF
            if max_split < MIN_LEAF: return False
            split_pos = random.randint(MIN_LEAF, max_split)
            self.left = Node(self.x, self.y, self.w, split_pos)
            self.right = Node(self.x, self.y + split_pos, self.w, self.h - split_pos)
            return True


    def create_room(self, grid):
        if self.left or self.right:
            if self.left:
                self.left.create_room(grid)
            if self.right:
                self.right.create_room(grid)
            if self.left and self.right:
                center1 = self.left.get_room_center()
                center2 = self.right.get_room_center()
                if center1 and center2:
                    carve_corridor(grid, center1[0], center1[1], center2[0], center2[1])
        else:
            # Leaf node: create a room
            room_w = random.randint(MIN_ROOM, self.w - MARGIN)
            room_h = random.randint(MIN_ROOM, self.h - MARGIN)
            room_x = random.randint(self.x + MARGIN // 2, self.x + self.w - room_w - MARGIN // 2)
            room_y = random.randint(self.y + MARGIN // 2, self.y + self.h - room_h - MARGIN // 2)

            grid[room_y : room_y + room_h, room_x : room_x + room_w] = ROOM
            self.room = (room_x, room_y, room_w, room_h)

    def get_room_center(self):
        if self.room:
            rx, ry, rw, rh = self.room
            return (rx + rw // 2, ry + rh // 2)
        else:
            center1, center2 = None, None
            if self.left:
                center1 = self.left.get_room_center()
            if self.right:
                center2 = self.right.get_room_center()

            if center1 and center2:
                return random.choice((center1, center2))
            elif center1:
                return center1
            elif center2:
                return center2
            else:
                return None

def carve_corridor(grid, x1, y1, x2, y2):
    # Carve L-shaped corridors, ensuring not to overwrite existing ROOMS
    cx, cy = x1, y1
    while cx != x2 or cy != y2:
        move_x = (cx != x2)
        move_y = (cy != y2)

        # Prioritize moving along the axis with greater distance, or randomly if equal
        if move_x and move_y:
            if abs(x2 - cx) > abs(y2 - cy):
                prefer_x = True
            elif abs(y2 - cy) > abs(x2 - cx):
                prefer_x = False
            else:
                prefer_x = random.choice([True, False])
        elif move_x:
            prefer_x = True
        else: # move_y must be true
            prefer_x = False

        if prefer_x:
            # Move horizontally
            if cx < x2: cx += 1
            else: cx -= 1
        else:
            # Move vertically
            if cy < y2: cy += 1
            else: cy -= 1

        # Carve only if the target is a WALL
        if 0 <= cy < grid.shape[0] and 0 <= cx < grid.shape[1] and grid[cy, cx] == WALL:
             grid[cy, cx] = CORRIDOR




def is_near_special_door(grid, y, x, radius):
    h, w = grid.shape
    y0, y1 = max(0, y - radius), min(h, y + radius + 1)
    x0, x1 = max(0, x - radius), min(w, x + radius + 1)
    subgrid = grid[y0:y1, x0:x1]
    return np.any(np.isin(subgrid, [LOCKED, SECRET]))

def generate_dungeon_json(seed, height, width ):
    random.seed(seed)
    np.random.seed(seed)
    grid = np.full((height, width), WALL, dtype=np.int32)

    # --- BSP Split ---
    root = Node(0, 0, width, height)
    nodes_to_split = [root]
    final_leaves = []

    while nodes_to_split:
        node = nodes_to_split.pop(0)
        if node.split():
            nodes_to_split.extend([node.left, node.right])
        else:
            final_leaves.append(node)

    # --- Create Rooms & Corridors ---
    root.create_room(grid)

    # --- Place Doors ---
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if grid[y, x] == CORRIDOR:
                up, down = grid[y - 1, x], grid[y + 1, x]
                left, right = grid[y, x - 1], grid[y, x + 1]

                vertical = ((up == ROOM and down == CORRIDOR) or (down == ROOM and up == CORRIDOR)) \
                           and left == WALL and right == WALL
                horizontal = ((left == ROOM and right == CORRIDOR) or (right == ROOM and left == CORRIDOR)) \
                             and up == WALL and down == WALL

                if vertical or horizontal:
                    grid[y, x] = DOOR if random.random() > 0.16 else random.choice([SECRET, LOCKED, TRAPPED])

    # --- Valid Stair Spots ---
    radius = 3
    valid_stair_spots = [
        (y, x) for y, x in zip(*np.where(grid == ROOM))
        if not is_near_special_door(grid, y, x, radius)
    ]

    # --- Place Stairs ---
    if len(valid_stair_spots) >= 2:
        stair_up_pos, stair_down_pos = random.sample(valid_stair_spots, 2)
        grid[stair_up_pos] = STAIR_UP
        grid[stair_down_pos] = STAIR_DOWN

    grid = grid.tolist()
    
    return {
         'id': hashlib.md5(json.dumps(grid).encode('utf-8')).hexdigest(),
         'width': width,
         'height': height,
         'seed': seed,
         'map': grid, 
    }


def parse_dungeon_json(path_or_str):
    try:
        data = json.loads(path_or_str)
    except json.JSONDecodeError:
        if not os.path.isfile(path_or_str):
            raise FileNotFoundError(f"File not found or is not a valid json.")
        with open(path_or_str, 'r', encoding='utf-8') as f:
            data = json.load(f)
    return data['id'], np.array(data['map'], dtype=np.int32).reshape(data['height'], data['width'])

def save_dungeon_json(json_str):
    filename = f"{json_str["id"]}.json"
    with open(filename, 'w') as f:
        f.write(json.dumps(json_str))
    return filename



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




def load_dungeon(json_path, rows, cols, seed, cell_size = 11, return_values = False):
    height, width = rows, cols
    if not os.path.exists(json_path):
        values = generate_dungeon_json(seed, rows, cols)
        save_dungeon_json(values)
        height, width = values["height"], values["width"]
        values = np.array(values["map"], dtype=np.int32).reshape(height, width)
    else:
        values = parse_dungeon_json(json_path)[1]
        height, width = values.shape
    
    
    values = pad_image(values, 4, 0)
    image = map_to_rgb(values)
    image = cv2.resize(image, ((width+8)*cell_size, (height+8)*cell_size), interpolation=cv2.INTER_AREA)
    image = grid_numpy(image, height+8, width+8, cor=(0, 0, 0), espessura=1)

    md5_hash = hashlib.md5(image.tobytes()).hexdigest()
    output_filename = f"./maps/{md5_hash}.png"
    

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
    
    load_dungeon("blahblah", 88, 88, np.random.randint(16777216)) 
    
          
         
         