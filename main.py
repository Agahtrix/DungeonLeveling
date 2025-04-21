import random

import numpy as np
from http.server import SimpleHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
import json

import json2image as j2i

sides =np.array([[ -1, 0], [ 0, 1] , [ 1, 0] , [ 0, -1]] 
             
, dtype= np.int32)

directions = ['n', 'e', 's', 'w'] 
              # N, L, S, O
walkable = [1,6,7,8] # door, corridor, room


json_filename = "cave.json" 
class_number = 1
n_enemies = 11

# --- Being Class ---
class Being:
    """Represents a character or enemy in the RPG."""
    def __init__(self, name, class_number, position, is_player=False):
        self.name = name
        self.cn = class_number
        self.hp = None
        self.defense = None
        self.attack_power = None
        self.special_power = None
        self.is_player = is_player
        try:
            min_hp_calc = 8 * (10**(self.cn - 1))
            max_hp_calc = 8 * (15**(self.cn - 1))
            
            if min_hp_calc >= max_hp_calc:
                max_hp_calc = min_hp_calc * 1.5
            self.hp = random.randint(int(min_hp_calc), int(max_hp_calc))
            self.hp = max(1, self.hp)
        except OverflowError:
            print(f"Warning: Overflow encountered generating HP for class {self.cn}. Using fallback.")
            self.hp = 10000 + (self.cn * 1000)
        self.hp = max(1, self.hp)
        self.defense = max(1, random.randint(int(self.hp / 3.5), int(self.hp / 3.0)) )
        self.attack_power = max(1, random.randint(int(self.hp / 4.0), int(self.hp / 3.5)) ) 
        self.special_power = max( self.attack_power+1, random.randint(int(self.hp / 3.0), int(self.hp / 2.0)) ) 

        self.max_hp = self.hp  # Armazena HP máximo para referência
        self.position = position
        self.facing = random.choice(directions)
        

    def move_being(self, action=None, map=None, enemies=None, player=None, valid_mov=True):
        """Moves the being. Player uses standard controls: 'n', 'e', 's', 'w'.
            NPC uses random movement."""

        # PLAYER
        if self.is_player:
            if action in directions:
                idx = directions.index(action)
                movement_vector = sides[idx]
                new_position = self.position + movement_vector
                self.facing = directions[idx]

                if (not any(np.array_equal(new_position, enemy.position) for enemy in enemies)
                        and int(map[tuple(new_position)]) in walkable):
                    self.position = new_position
                else:
                    valid_mov = False
            else:
                valid_mov = False


        # NPC
        else:
            random_index = random.randint(0, 3)
            movement_vector = sides[random_index]
            new_position = self.position + movement_vector

            if (not any(np.array_equal(new_position, enemy.position) for enemy in enemies)
                    and not np.array_equal(new_position, player.position)
                    and int(map[tuple(new_position)]) in walkable):
                self.position = new_position
                self.facing = directions[random_index] 

     
    def get_dict(self, map=None):
        # Return player state as a dictionary
        return {
            "name": self.name,
            "class_number": self.cn,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "def": self.defense,
            "atk": self.attack_power, 
            "special": self.special_power,
            "position": [self.position[0]/float(map.shape[0]),self.position[1]/float(map.shape[1])],
            "facing": self.facing
            # Add other stats here
        }


    def is_alive(self):
        return self.hp > 0

    def take_damage(self, damage):
        actual_damage = max(0, int(damage))
        self.hp -= actual_damage
        self.hp = max(0, self.hp)
        return actual_damage

# --- Função de cálculo de dano ---
def calculate_damage(attacker, defender, roll, use_special=False):
    if use_special:
        attack_stat = attacker.special_power
    else:
        attack_stat = attacker.attack_power

    if defender.max_hp <= 0:
        return 0

    damage_modifier = 0.5 + (roll / 100.0)
    base_damage = damage_modifier * attack_stat
    defense_factor = defender.defense / defender.max_hp
    final_damage = base_damage * (1.0 - defense_factor)
    return max(0, int(final_damage))

# --- Inimigos disponíveis ---
ENEMY_TYPES = {
    1: [
        "Giant Rat",
        "Blue Slime",
        "Kobold Scout",
        "Cave Spider",
        "Forest Bat",
        "Field Mouse",
        "Swarm of Beetles",
        "Mud Frog",
    ],

    2: [
        "Goblin Grunt",
        "Goblin Shaman",
        "Dire Wolf",
        "Bandit",
        "Zombie",
        "Harpy",
        "Ghoul",
        "Bandit Archer",
    ],

    3: [
        "Orc Warrior",
        "Orc Berserker",
        "Skeletal Soldier",
        "Giant Spider",
        "Warg Rider",
        "Wraith",
        "Skeleton Knight",
        "Tribal Shaman",
    ],

    4: [
        "Ogre",
        "Troll",
        "Specter",
        "Elite Orc Captain",
        "Skeleton Archer",
        "Fire Wraith",
        "Orc War Priest",
        "Bone Golem",
    ],

    5: [
        "Minotaur",
        "Stone Golem",
        "Basilisk",
        "Sand Wyrm",
        "Bandit Captain",
        "Ice Golem",
        "Cave Scorpion",
        "Bandit Mage",
    ],

    6: [
        "Hill Giant",
        "Chimera",
        "Young Dragon",
        "Fire Elemental",
        "Lesser Lich",
        "Earth Elemental",
        "Storm Drake",
        "Dark Knight",
    ],

    7: [
        "Elemental Lord",
        "Hydra",
        "Ancient Golem",
        "Orc Warlord",
        "Shadow Assassin",
        "Death Knight",
        "Sea Serpent",
        "Volcanic Elemental",
    ],

    8: [
        "Elder Dragon",
        "Lich King",
        "Archdemon",
        "Titan",
        "Void Entity",
        "Prime Elemental",
        "Celestial Phoenix",
        "World Serpent",
        "Abyssal Horror",
    ],
}

def create_enemies(map, class_number, n_enemies):
    
    possible_positions = np.argwhere(map == 8)
    len_pos = len(possible_positions)

    if len_pos >= n_enemies:
        random_indices = np.random.choice(len_pos, size=n_enemies, replace=False)
        choices = possible_positions[random_indices]
    else:
        print(f"An error occurred, possible_positions returned only {len_pos}.")
        return
    
    enemies = []
    for i in range(n_enemies):
        possible_names = ENEMY_TYPES.get(class_number, [f"Anomaly Class {class_number}"])
        name = random.choice(possible_names)
        enemies.append(Being(name, class_number, choices[i]))
    
    return enemies



def get_nearby_enemies(enemies, player, map, radius=6):
    """
    Returns all enemies whose grid position
    (via .grid_position()) is within 'radius' squares
    of the player's position.
    """

    
    px, py = player.position
    r2 = radius * radius

    nearby = []
    append = nearby.append
    for e in enemies:
        ex, ey = e.position
        dx = ex - px
        dy = ey - py
        if dx*dx + dy*dy <= r2:
            append(e.get_dict(map=map))
    return nearby if nearby else None


# --- Classe que controla o estado do jogo ---
class Game:
    def __init__(self):
        self.map = j2i.load_dungeon(json_filename, return_values = True)
        self.map_path = self.map[1]
        self.map = self.map[0]
        self.log = []
        self.player = None
        self.enemies = None
        self.current_enemy = None
        self.game_over = False

    def new_game(self, player_name, class_number):
        self.log = []
        start_position = np.argwhere(self.map == 6)
        start_position = start_position[0].tolist()

        
        self.player = Being(player_name if player_name.strip() else "Hero", class_number, start_position, is_player=True)
        self.enemies = create_enemies(self.map, class_number, n_enemies)
        self.game_over = False
        self.log.append(f"\nWelcome, {self.player.name}!")

    def process_player_action(self, action):
        if self.game_over:
            self.log.append("\nGame over. Restart to play again.")
            return
            
        valid_mov = True
        
        
        if action in directions:
            self.player.move_being(action, self.map, self.enemies, valid_mov=valid_mov)

            
        elif action in ['a', 'sp']:
            use_special = (action == 'sp')
            roll = random.randint(1, 100)
            damage = calculate_damage(self.player, self.current_enemy, roll, use_special)
            dmg = self.current_enemy.take_damage(damage)
            act = "uses special ability" if use_special else "attacks"
            self.log.append(f"{self.player.name} {act} {self.current_enemy.name}! (Roll: {roll}) dealt {dmg} damage.")
            if not self.current_enemy.is_alive():
                self.log.append(f"\n*** Victory! {self.current_enemy.name} was defeated. ***")
                #self.enemy = create_enemy(self.map, self.player.cn)
                #self.log.append(f"\nA new enemy appears: {self.enemy.name}.")
            else:
                self.enemy_turn()
        elif action == 't':
            self.log.append(f"{self.player.name} tried to escape... and succeeded!")
            #self.enemy = create_enemy(self.map, self.player.cn)
            #self.log.append(f"\nBut a new enemy is already lurking: {self.enemy.name}.")
        elif action == 'x':
            self.log.append("\nEnding the game. See you next time!")
            self.game_over = True

        if valid_mov:
            for i in range(len(self.enemies)):
                # print(f"\nEnemy{i}:" , self.enemies[i].position)
                self.enemies[i].move_being(map=self.map, enemies=self.enemies, player=self.player)
                # print(f"\nEnemy{i}:" , self.enemies[i].position)

             
    def enemy_turn(self):
        if not self.current_enemy.is_alive():
            return
        roll = random.randint(1, 100)
        damage = calculate_damage(self.current_enemy, self.player, roll, use_special=False)
        dmg = self.player.take_damage(damage)
        self.log.append(f"{self.current_enemy.name} attacks {self.player.name}! (Roll: {roll}) dealt {dmg} damage.")
        if not self.player.is_alive():
            self.log.append(f"\n--- Game Over: {self.player.name} was defeated by {self.current_enemy.name}. ---")
            self.game_over = True


    # --- NEW METHOD TO GET STATE AS DICT ---
    def get_state_dict(self):
        """Returns the current game state as a dictionary suitable for JSON."""
        return {
            "needs_setup": self.player is None,
            "player": self.player.get_dict(map=self.map) if self.player else None,
            "enemy": self.current_enemy.get_dict(map=self.map) if self.current_enemy else None,
            "enemies": get_nearby_enemies(self.enemies, self.player, self.map) if self.enemies is not None and self.player is not None else None,
            "log": self.log[:],  # Send a copy of the recent log
            "map_path": self.map_path,
            "game_over": self.game_over,
        }

game = Game()

class RPGRequestHandler(SimpleHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        action = qs.get("action", [None])[0]

        # --- API Endpoint: /api/game_state ---
        if parsed.path == '/api/game_state':
            try:
                # Process actions BEFORE getting state
                if action == "start":
                    name = qs.get("name", ["Hero"])[0]
                    try:
                        class_number = int(qs.get("class", ["1"])[0])
                        if not (1 <= class_number <= 8):
                            class_number = 1
                    except ValueError:
                        class_number = 1
                    game.new_game(name, class_number)
                elif action == "restart":
                    game.__init__() # Re-initialize game
                elif action in ['a', 'sp', 't', 'n', 'e', 's', 'w']:
                    if game.player is not None: # Only process if game started
                        game.process_player_action(action)
                # Action 'get_state' or any other/no action just returns current state

                # Get current state AFTER processing action
                state_dict = game.get_state_dict()
                json_response = json.dumps(state_dict) # Convert dict to JSON string

                # Send JSON response
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-cache") # Important for APIs
                self.end_headers()
                self.wfile.write(json_response.encode("utf-8"))

            except Exception as e:
                 # Send error as JSON if possible
                 self.send_response(500) # Internal Server Error
                 self.send_header("Content-type", "application/json; charset=utf-8")
                 self.send_header("Cache-Control", "no-cache")
                 self.end_headers()
                 error_json = json.dumps({"error": f"Server error: {e.__class__.__name__}", "details": str(e)})
                 self.wfile.write(error_json.encode("utf-8"))
                 print(f"Error processing API request: {e}") # Log server-side

        # --- Serve index.html for the root path ---
        elif parsed.path == '/':
            try:
                # Serve index.html directly
                with open("index.html", "rb") as f: # Read as binary
                    self.send_response(200)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(f.read())
            except FileNotFoundError:
                 self.send_error(404, "File Not Found: index.html")
            except Exception as e:
                 self.send_error(500, f"Error reading index.html: {e}")

        # --- Serve other static files (like map.png) ---
        else:
            # Use the parent class's handler for static files
            # It looks for files relative to where the server is running
            super().do_GET()


# --- Servidor multithread (Unchanged) ---
class ThreadingSimpleServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

def run_server(port=8000):
    server_address = ("", port)
    httpd = ThreadingSimpleServer(server_address, RPGRequestHandler)
    print(f"RPG server running at http://localhost:{port}\n")
    
    print("Make sure 'index.html' and 'cave.json' are in the execution directory.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down the server.")
        httpd.shutdown()
        httpd.server_close()

if __name__ == "__main__":
    # Ensure map file exists before starting server
    # (Game() constructor now handles this)
    run_server(8000)

