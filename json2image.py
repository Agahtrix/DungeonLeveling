import json
import cv2
import numpy as np
import os # Importar a biblioteca os
import hashlib

# --- Configuração ---
# Use o nome do arquivo JSON que você carregou
json_filename = "cave.json" #'The Black Cyst of Lord Greywulf 01.json'


# Mapeamento de tipos de célula para cores (BGR - padrão do OpenCV)

color_map = [
    ('nothing', (80, 80 , 80)),       # 0 - Cinza escuro — espaço vazio ou fundo
    ('door', (40, 60 , 120)),         # 1 - Azul escuro — portas normais
    ('secret', (200, 100, 0)),        # 2 - Laranja escuro — portas secretas
    ('locked', (0, 0 , 200)),         # 3 - Azul — portas trancadas
    ('trapped', (0, 140 , 255)),      # 4 - Azul claro — portas com armadilha
    ('stair_down', (0, 200 , 0)),     # 5 - Verde — escadas para baixo
    ('stair_up', (200, 200 , 0)),     # 6 - Amarelo — escadas para cima
    ('corridor', (120, 120 , 120)),   # 7 - Cinza médio — corredores
    ('room', (150, 150 , 150)),       # 8 - Cinza claro — chão de sala
    ('perimeter', (80, 80 , 80)),     # 9 - Cinza escuro — paredes externas
    ('block', (233, 233 , 233))       # 10 - Cinza muito claro — paredes internas
]

# --- Fim da Configuração ---


def grid_numpy(image, rows, cols, cor=(0, 255, 0), espessura=1):
    """
    Aplica um grid a uma imagem de forma eficiente usando NumPy slicing.

    Args:
        image (np.ndarray): A imagem de entrada (colorida BGR ou escala de cinza).
        rows (int): Número de linhas no grid (resultará em rows-1 linhas horizontais).
        cols (int): Número de colunas no grid (resultará em cols-1 linhas verticais).
        cor (tuple ou int): Cor das linhas do grid (padrão: verde BGR).
                             Para imagens em escala de cinza, use um int (0-255).
        espessura (int): Espessura das linhas do grid em pixels (padrão: 1).

    Returns:
        np.ndarray: Uma cópia da imagem com o grid desenhado.
    """
    # Cria uma cópia da imagem para não modificar a original
    imagem_com_grid = image.copy()
    altura, largura = imagem_com_grid.shape[:2]

    # Calcula o espaçamento real do grid
    step_y = altura / rows
    step_x = largura / cols

    # --- Linhas horizontais ---
    for r in range(1, rows):
        y = int(r * step_y) # Posição central da linha

        # Calcula os limites da linha com base na espessura
        # Garante que os índices não saiam dos limites da imagem
        y_inicio = max(0, y - espessura // 2)
        # O limite superior é exclusivo no slicing, por isso +1 se espessura for ímpar
        y_fim = min(altura, y + (espessura + 1) // 2)

        # Aplica a cor à fatia (slice) da linha horizontal
        # imagem_com_grid[y_inicio:y_fim, :, :] seleciona:
        #   - Linhas de y_inicio até y_fim-1
        #   - Todas as colunas (:)
        #   - Todos os canais de cor (:) - se for colorida
        imagem_com_grid[y_inicio:y_fim, :] = cor # NumPy lida com 2D ou 3D

    # --- Linhas verticais ---
    for c in range(1, cols):
        x = int(c * step_x) # Posição central da coluna

        # Calcula os limites da coluna com base na espessura
        x_inicio = max(0, x - espessura // 2)
        x_fim = min(largura, x + (espessura + 1) // 2)

        # Aplica a cor à fatia (slice) da coluna vertical
        # imagem_com_grid[:, x_inicio:x_fim, :] seleciona:
        #   - Todas as linhas (:)
        #   - Colunas de x_inicio até x_fim-1
        #   - Todos os canais de cor (:) - se for colorida
        imagem_com_grid[:, x_inicio:x_fim] = cor # NumPy lida com 2D ou 3D

    return imagem_com_grid



def load_dungeon(json_path, cell_size = 11, return_values = False):
    """
    Lê um arquivo JSON de masmorra e cria uma imagem PNG usando OpenCV.

    Args:
        json_path (str): O caminho para o arquivo JSON da masmorra.
        output_path (str): O caminho onde salvar a imagem PNG resultante.
        cell_size (int): O tamanho (largura e altura) em pixels para cada célula do mapa.
    """
    try:
        with open(json_path, 'r') as f:
            dungeon_data = json.load(f)
        print(f"Arquivo JSON '{json_path}' carregado com sucesso.")
    except FileNotFoundError:
        print(f"Erro: Arquivo JSON '{json_path}' não encontrado.")
        return
    except json.JSONDecodeError:
        print(f"Erro: Falha ao decodificar o arquivo JSON '{json_path}'. Verifique o formato.")
        return
    except Exception as e:
        print(f"Ocorreu um erro inesperado ao ler o JSON: {e}")
        return

    # Verificar se as chaves essenciais existem
    if 'cells' not in dungeon_data or 'cell_bit' not in dungeon_data:
        print("Erro: O arquivo JSON não contém as chaves 'cells' ou 'cell_bit'.")
        return

    cells = dungeon_data['cells']
    cell_bits = dungeon_data['cell_bit']

    # Obter dimensões do mapa
    if not cells:
        print("Erro: A matriz 'cells' está vazia.")
        return
    rows = len(cells)
    cols = len(cells[0]) if rows > 0 else 0
    if cols == 0:
        print("Erro: Mapa sem colunas.")
        return

    print(f"Dimensões do mapa: {rows} linhas x {cols} colunas.")
    
    
    cells = np.array(cells, dtype = np.uint32)
    not_processed = np.ones((rows, cols), dtype=bool)
    
    if return_values:
        values = np.zeros((rows, cols), dtype=np.int32)
        i = 0
        for key, color in color_map:
            
            bit = cell_bits.get(key, 0)
            cond_mask = ( (cells & bit) != 0 ) & not_processed
            # Atribui a cor para essas células
            values[cond_mask] = i
            # Marca essas células como já atribuídas para não sobrescrevê-las em condições subsequentes
            not_processed[cond_mask] = False
            i += 1
        
        
        

    
    #image = (np.round((values.astype(np.float64)/i) * 255)).astype(np.uint8)
        # Usar 3 canais para cores BGR
    not_processed = np.ones((rows, cols), dtype=bool)
    image = np.full((rows, cols, 3), ( 80, 80, 80), dtype=np.uint8)
    print(f"Criando imagem com dimensões: {rows*cell_size}x{cols*cell_size} pixels.")
    
    
    for key, color in color_map:
        bit = cell_bits.get(key, 0)
        cond_mask = ( (cells & bit) != 0 ) & not_processed
        # Atribui a cor para essas células
        image[cond_mask] = color
        # Marca essas células como já atribuídas para não sobrescrevê-las em condições subsequentes
        not_processed[cond_mask] = False
    
    
    # Escalar e Salvar a imagem
    image = cv2.resize(image, (cols*cell_size, rows*cell_size), interpolation=cv2.INTER_AREA)
    image = grid_numpy(image, rows, cols, cor=(0, 0, 0), espessura=1)

# Calcular o hash MD5 da imagem
    md5_hash = hashlib.md5(image.tobytes()).hexdigest()
    output_filename = f"{md5_hash}.png"
    
    

    # Verificar se já existe
    if os.path.exists(output_filename):
        if return_values:
            return values, output_filename
        print(f"A imagem com hash {md5_hash} já existe como '{output_filename}'.")
        return

    try:
        # Caminho do script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        full_output_path = os.path.join(script_dir, output_filename)
        cv2.imwrite(full_output_path, image)
        print(f"Imagem da masmorra salva como '{full_output_path}'")
    except Exception:
        # Fallback: tentar salvar no diretório atual
        try:
            cv2.imwrite(output_filename, image)
            print(f"Imagem da masmorra salva como '{output_filename}' (no diretório atual)")
        except Exception as e_fallback:
            print(f"Erro ao salvar a imagem: {e_fallback}")
    if return_values:
        return values, output_filename

# --- Execução ---
if __name__ == "__main__":
    
    load_dungeon(json_filename) 
    
          
         
         