import random 

def is_valid(board, row, col, num):
    # Vérifie si le nombre est déjà dans la ligne
    for x in range(len(board)):
        if board[row][x] == num:
            return False

    # Vérifie si le nombre est déjà dans la colonne
    for x in range(len(board)):
        if board[x][col] == num:
            return False

    # Vérifie si le nombre est déjà dans la sous-grille 3x3
    box_size = 3 if len(board)==9 else 2
    start_row = row - row % box_size
    start_col = col - col % box_size
    for i in range(box_size):
        for j in range(box_size):
            if board[i + start_row][j + start_col] == num:
                return False

    return True


def solve_sudoku_unique(board):
    solutions = []
    def solve():
        for row in range(len(board)):
            for col in range(len(board)):
                if board[row][col] == 0:
                    for num in range(1, len(board) + 1):
                        if is_valid(board, row, col, num):
                            board[row][col] = num
                            if solve():
                                solutions.append([row[:] for row in board])
                                if len(solutions) > 1:
                                    return False
                            board[row][col] = 0
                    return False
        return True
    solve()
    #print("End of solve_sudoku_unique")
    return len(solutions) == 1


def fill_subgrid(board):
    try:
        nums = list(range(1, len(board) + 1))
        random.shuffle(nums)
        box_side = 3 if len(board)==9 else 2
        for i in range(box_side):
            for j in range(box_side):
                board[i][j] = nums.pop()
        #Filling row1
        for i in (0,1):
            nums = list(range(1, len(board) + 1))
            nums.remove(board[i][0])
            nums.remove(board[i][1])
            random.shuffle(nums)
            board[i][2] = nums.pop()
            board[i][3] = nums.pop()
        for j in range(2):
            nums = list(range(1, len(board) + 1))
            nums.remove(board[0][j])
            nums.remove(board[1][j])
            random.shuffle(nums)
            board[2][j] = nums.pop()
            board[3][j] = nums.pop()
        #Filling last block
        #print_board(board)
        for i in (2,3):
            for j in (2,3):
                nums = list(range(1, len(board) + 1))
                nums.remove(board[i][0])
                nums.remove(board[i][1])
                if board[0][j] in nums : nums.remove(board[0][j])
                if board[1][j] in nums : nums.remove(board[1][j])
                board[i][j]=nums.pop()
        return True
    except IndexError:
        print("Not solvable !")
        return False

def remove_numbers(board, num_holes):
    count = num_holes
    size = len(board)
    max_attempts = 100  # Adjust this value as needed
    tried_configs = set()  # Store tried configurations as tuples
    saved = board    
    while count > 0 and max_attempts > 0:
        row = random.randint(0, size - 1)
        col = random.randint(0, size - 1)
        config = (row, col)  # Create a tuple to represent the configuration

        if config not in tried_configs:
            tried_configs.add(config)

            if board[row][col] != 0:
                backup = board[row][col]
                board[row][col] = 0
                copy_board = [row[:] for row in board]
                #print(f"checking if unique solution {max_attempts}")
                if solve_sudoku_unique(copy_board):
                    count -= 1
                    saved = board
                    #print(f"Unique solution found {count} holes remaining")
                else:
                    board[row][col] = backup
                    max_attempts -= 1
                    #print(f"Solution not unique {max_attempts}")
                
                
    if max_attempts == 0:
        print("No unique solution found after", max_attempts, "attempts.")
        return saved, False
    return board, True

def print_board(board):
    for row in board:
        print(row)
        
def create_board(size, difficulty='easy'):
    #print("Creating BOARD ...")
    board = [[9 for _ in range(size)] for _ in range(size)]
    # print_board(board)
    #print("Filling sudoku...")
    while not fill_subgrid(board):
        True
    #print_board(board)
    #print("Solving done.")
    if difficulty == 'easy':
        num_holes = 20 if size == 9 else 4
    elif difficulty == 'medium':
        num_holes = 35 if size == 9 else 6
    elif difficulty == 'hard':
        num_holes = 50 if size == 9 else 8
    else:
        num_holes = 40  # Default to medium if difficulty is not recognized
    #print("REMOVING NUMBERS ...")
    #print(board)
    board, found = remove_numbers(board, num_holes)
    #print("Finishsed REMOVING NUMBERS ...")
    return board
