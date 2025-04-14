import random

import numpy as np
from http.server import SimpleHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

import json
import json2image as j2i

sides =np.array([[ -1, 0], [ 0, 1] , [ 1, 0] , [ 0, -1]] 
             
, dtype= np.int32)

places = ['f', 'r', 'b', 'l' ] 
              # N, L, S, O
walkable = [1,7,8] # door, corridor, room


json_filename = "cave.json" 
class_number = 1
n_enemies = 11

# --- Being Class ---
class Being:
    """Representa um personagem ou inimigo no RPG."""
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
        self.facing = random.choice(places)
        

    def move_being(self, action=None, map=None, enemies=None, player=None, valid_mov=True):
        """Move o ser. Jogador usa tank controls, NPC usa movimento aleatório."""
        if self.is_player:
            current_facing_index = places.index(self.facing)
    
            if action == 'l':  # Rotacionar para a Esquerda
                new_facing_index = (current_facing_index - 1 + len(places)) % len(places)  # Wrap around
                self.facing = places[new_facing_index]
                print(f"{self.name} virou para '{self.facing}'")
    
            elif action == 'r':  # Rotacionar para a Direita
                new_facing_index = (current_facing_index + 1) % len(places)  # Wrap around
                self.facing = places[new_facing_index]
                print(f"{self.name} virou para '{self.facing}'")
                
            elif action == 'f':  # Mover para Frente (na direção facing)
                movement_vector = sides[current_facing_index]
                new_position = self.position + movement_vector
                # Converte new_position para tupla para indexar corretamente o array map
                if (not any(np.array_equal(new_position, enemy.position) for enemy in enemies)
                        and (int(map[tuple(new_position)]) in walkable)):
                    self.position = new_position
                else:
                    return
                print(f"{self.name} moveu para frente ({self.facing}) para {self.position}")
    
            elif action == 'b':  # Mover para Trás (oposto da direção facing)
                movement_vector = sides[current_facing_index]
                new_position = self.position - movement_vector
                if (not any(np.array_equal(new_position, enemy.position) for enemy in enemies)
                        and (int(map[tuple(new_position)]) in walkable)):
                    self.position = new_position
                else:
                    valid_mov = False
                    return
                print(f"{self.name} moveu para trás (oposto de {self.facing}) para {self.position}")
    
        else:
            # Movimentação de NPC com direção aleatória
            random_index = random.randint(0, 3)
            movement = sides[random_index]
            new_position = self.position + movement
            print(f"NPC {self.name} tentando mover de {self.position} para {new_position}")
            if (not any(np.array_equal(new_position, enemy.position) for enemy in enemies)
                    and (not np.array_equal(new_position, player.position))
                    and (int(map[tuple(new_position)]) in walkable)):
                self.position = new_position
     
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
    1: ["Rato Gigante", "Gosma", "Batedor Kobold"],
    2: ["Goblin", "Lobo Feroz", "Zumbi"],
    3: ["Orc", "Guerreiro Esquelético", "Aranha Grande"],
    4: ["Ogro", "Troll", "Espectro"],
    5: ["Minotauro", "Golem de Pedra", "Filhote de Wyvern"],
    6: ["Gigante", "Quimera", "Dragão Jovem"],
    7: ["Senhor Elemental", "Hidra", "Golem Ancestral"],
    8: ["Dragão", "Lich", "Príncipe Demônio"]
}

def create_enemies(map, class_number, n_enemies):
    
    possible_positions = np.argwhere(map == 8)
    len_pos = len(possible_positions)

    if len_pos >= n_enemies:
        random_indices = np.random.choice(len_pos, size=n_enemies, replace=False)
        choices = possible_positions[random_indices]
    else:
        print(f"Ocorreu um erro possible_positions returnou apenas {len_pos}.")
        return
    
    enemies = []
    for i in range(n_enemies):
        possible_names = ENEMY_TYPES.get(class_number, [f"Anomalia Classe {class_number}"])
        name = random.choice(possible_names)
        enemies.append(Being(name, class_number, choices[i]))
    
    return enemies

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
        self.log.append(f"<br>Bem-vindo, {self.player.name}! ")

    def process_player_action(self, action):
        if self.game_over:
            self.log.append("<br>Jogo finalizado. Reinicie para jogar novamente.")
            return
            
        valid_mov = True
        
        print("\nPlayer:" , self.player.position, action)
        
        if action in places:
            self.player.move_being(action, self.map, self.enemies, valid_mov=valid_mov)
            print("\nPlayer:" , self.player.position)
            
        elif action in ['a', 's']:
            use_special = (action == 's')
            roll = random.randint(1, 100)
            damage = calculate_damage(self.player, self.current_enemy, roll, use_special)
            dmg = self.current_enemy.take_damage(damage)
            act = "usa habilidade especial" if use_special else "ataca"
            self.log.append(f"{self.player.name} {act} {self.current_enemy.name}! (Roll: {roll}) causou {dmg} de dano.")
            if not self.current_enemy.is_alive():
                self.log.append(f"<br>*** Vitória! {self.current_enemy.name} foi derrotado. ***")
                #self.enemy = create_enemy(self.map, self.player.cn)
                #self.log.append(f"<br>Um novo inimigo surge: {self.enemy.name}.")
            else:
                self.enemy_turn()
        elif action == 't':
            self.log.append(f"{self.player.name} tentou fugir... e conseguiu!")
            #self.enemy = create_enemy(self.map, self.player.cn)
            #self.log.append(f"<br>Mas um novo inimigo já está à espreita: {self.enemy.name}.")
        elif action == 'x':
            self.log.append("<br>Encerrando o jogo. Até a próxima!")
            self.game_over = True
        
        if  valid_mov:
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
        self.log.append(f"{self.current_enemy.name} ataca {self.player.name}! (Roll: {roll}) causou {dmg} de dano.")
        if not self.player.is_alive():
            self.log.append(f"<br>--- Game Over: {self.player.name} foi derrotado por {self.current_enemy.name}. ---")
            self.game_over = True


    # --- NEW METHOD TO GET STATE AS DICT ---
    def get_state_dict(self):
        """Returns the current game state as a dictionary suitable for JSON."""
        return {
            "needs_setup": self.player is None,
            "player": self.player.get_dict(map=self.map) if self.player else None,
            "enemy": self.current_enemy.get_dict(map=self.map) if self.current_enemy else None,
            "log": self.log[:], # Send a copy of the recent log
            "map_path": self.map_path,
            "game_over": self.game_over,
        }

# --- Instância global do jogo ---
game = Game()

# --- MODIFIED Handler ---
class RPGRequestHandler(SimpleHTTPRequestHandler):

    # Override log_message to prevent cluttering the console during AJAX polling
    # def log_message(self, format, *args):
    #    # Uncomment the line below to re-enable basic logging
    #    # super().log_message(format, *args)
    #    pass


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
                elif action in ['a', 's', 't', 'f', 'r', 'b', 'l']:
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
    print(f"Servidor RPG rodando em http://localhost:{port}")
    
    print("Certifique-se que 'index.html' e 'cave.json' estão no diretório de execução.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando o servidor.")
        httpd.shutdown()
        httpd.server_close()

if __name__ == "__main__":
    # Ensure map file exists before starting server
    # (Game() constructor now handles this)
    run_server(8000)

