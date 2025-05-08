import sys
import socket
import json
import bcrypt
import selectors
import os
from typing import List
import re


# Global variable to track rooms
rooms = {}
authenticated_clients = {}
client_usernames = {}

def load_config(config_path):
    """Load server configuration from the provided config file."""
    config_path = os.path.expanduser(config_path)
    if not os.path.exists(config_path):
        print(f"Error: {config_path} doesn't exist.")
        sys.exit(1)
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: {config_path} is not in a valid JSON format.")
        sys.exit(1)
    required_keys = {'port', 'userDatabase'}
    missing_keys = required_keys - config.keys()
    if missing_keys:
        missing_keys_list = ', '.join(sorted(missing_keys))
        print(f"Error: {config_path} missing key(s): {missing_keys_list}")
        sys.exit(1)
    port = config['port']
    if not isinstance(port, int) or not (1024 <= port <= 65535):
        print("Error: port number out of range")
        sys.exit(1)
    return config

def load_users(user_file):
    user_file = os.path.expanduser(user_file)
    if not os.path.exists(user_file):
        users = []
        save_users(users, user_file)
        return users
    try:
        with open(user_file, 'r') as file:
            users = json.load(file)
            if isinstance(users, list):
                return users
            else:
                raise ValueError("Invalid JSON structure")
    except json.JSONDecodeError:
        print(f"Error: {user_file} is not in a valid JSON format.")
        sys.exit(1)

def save_users(users, user_file):
    user_file = os.path.expanduser(user_file)
    try:
        with open(user_file, 'w') as file:
            json.dump(users, file, indent=4)
            file.flush()
    except Exception as e:
        print(f"Error saving users: {e}")

def check_login(conn, username, password, users):
    for user in users:
        if user.get('username') == username:
            if bcrypt.checkpw(password.encode(), user['password'].encode()):
                authenticated_clients[conn] = True  # Mark this connection as authenticated
                client_usernames[conn] = username  # Map connection to username
                return "LOGIN:ACKSTATUS:0\n"  # Successful login
            return "LOGIN:ACKSTATUS:2\n"  # Wrong password
    return "LOGIN:ACKSTATUS:1\n"  # User not found


def handle_register(conn, data, users, user_file):
    """Handle user registration."""
    parts = data.strip().split(":")
    if len(parts) != 3:
        conn.sendall("REGISTER:ACKSTATUS:2\n".encode())  # Invalid format
        return

    _, username, password = parts
    response = register_user(username, password, users, user_file)
    conn.sendall(response.encode())

def register_user(username, password, users, user_file):
    for user in users:
        if user.get('username') == username:
            return "REGISTER:ACKSTATUS:1\n"  # User already exists
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    new_user = {"username": username, "password": hashed_password}
    users.append(new_user)
    save_users(users, user_file)
    return "REGISTER:ACKSTATUS:0\n"  # Successful registration

def handle_roomlist(conn, data):
    """Handle ROOMLIST request and send available rooms based on mode."""
    parts = data.strip().split(":")
    
    # Validate the format - there should be exactly 2 parts (ROOMLIST and mode)
    if len(parts) != 2:
        conn.sendall("ROOMLIST:ACKSTATUS:1\n".encode())  # Invalid format
        return

    mode = parts[1]
    
    # Check if mode is valid (should be PLAYER or VIEWER)
    if mode.upper() not in ["PLAYER", "VIEWER"]:
        conn.sendall("ROOMLIST:ACKSTATUS:1\n".encode())  # Invalid mode
        return

    # Filter rooms based on the valid mode
    if mode.upper() == "PLAYER":
        available_rooms = [name for name, room in rooms.items() if room['players'] < 2]
    else:  # mode is VIEWER
        available_rooms = list(rooms.keys())  # Show all rooms for VIEWER mode
    
    # Send room list or notify no rooms available
    if available_rooms:
        room_list = ",".join(available_rooms)
        conn.sendall(f"ROOMLIST:ACKSTATUS:0:Rooms available to join as {mode}: {room_list}\n".encode())
    else:
        conn.sendall(f"ROOMLIST:ACKSTATUS:0:\n".encode())


def handle_place_message(room_name, conn, x, y):
    room = get_room_or_send_noroom(room_name, conn)
    if not room:
        conn.sendall("NOROOM\n".encode())
        return

    # Ignore move if it's not the player's turn
    if conn != room['current_turn']:
        room['move_queue'].append((conn, x, y))  # Add to queue
        conn.sendall("PLACE:ACKSTATUS:3\n".encode())  # Tell client their move was queued
        return

    board = room['board']
    # Check if the position is already occupied
    if board[y][x] != ' ':
        conn.sendall("PLACE:ACKSTATUS:2\n".encode())  # Invalid move
        return

    # Determine the marker based on the current turn
    marker = 'X' if conn == room['player1'] else 'O'
    # Place the marker ('X' or 'O') on the board
    board[y][x] = marker

    # Convert the 2D board to a 9-character string (1D representation)
    board_status = ''.join(
        ['0' if cell == ' ' else '1' if cell == 'X' else '2' for row in board for cell in row]
    )

    # Check for a win or a draw
    if check_winner(board, marker):
        winner_username = get_username_from_conn(conn)
        send_gameend_message(room, board_status, 0, winner_username)
        delete_room(room_name)  # End game and delete room
    elif is_draw(board):
        send_gameend_message(room, board_status, 1)
        delete_room(room_name)  # End game and delete room
    else:
        # Switch turns between player1 and player2
        room['current_turn'] = room['player2'] if conn == room['player1'] else room['player1']
        
        # Send the BOARDSTATUS message to all players and viewers
        board_status_message = f"BOARDSTATUS:{board_status}\n"
        broadcast_to_room(room, board_status_message)

        # Process any queued moves for the next player
        process_queued_moves(room_name)

def process_queued_moves(room_name):
    room = rooms[room_name]
    if not room['move_queue']:
        return

    # Check if the queued move is for the player whose turn it is
    next_conn, x, y = room['move_queue'][0]
    if next_conn == room['current_turn']:
        room['move_queue'].pop(0)  # Remove from the queue
        handle_place_message(room_name, next_conn, x, y)  # Process the queued move
        # Recursively check for the next queued move
        process_queued_moves(room_name)

    
def get_room_or_send_noroom(room_name, conn):
    """Helper function to get the room for a client or send NOROOM if not found."""
    for room_name, room in rooms.items():
        if conn == room['player1'] or conn == room['player2']:
            return room
    # If no room is found, send the NOROOM message
    conn.sendall("NOROOM\n".encode())
    return None

def send_gameend_message(room, board_status, status_code, winner_username=None):
    """Send GAMEEND message to all players and viewers in the room."""
    if status_code == 0:  # Game won by a player
        gameend_message = f"GAMEEND:{board_status}:0:{winner_username}\n"
    elif status_code == 1:  # Game ended in a draw
        gameend_message = f"GAMEEND:{board_status}:1\n"
    elif status_code == 2:  # Game ended by forfeit
        gameend_message = f"GAMEEND:{board_status}:2:{winner_username}\n"
    
    # Send GAMEEND to all players and viewers
    broadcast_to_room(room, gameend_message)

def broadcast_to_room(room, message):
    """Broadcast a message to all players and viewers in the room."""
    for player in [room['player1'], room['player2']]:
        print("in here ie error is with accessing player")
        player.sendall(message.encode())
    
    for viewer in room['viewers']:
        print("in here ie error is with accessing viewer")
        viewer.sendall(message.encode())

def delete_room(room_name):
    """Delete the room once the game ends."""
    if room_name in rooms:
        del rooms[room_name]
    print(f"Room '{room_name}' has been deleted.")

def handle_forfeit(conn, room_name):
    room = get_room_or_send_noroom(room_name, conn)
    if not room:
        conn.sendall("NOROOM\n".encode())
        return

    forfeiting_player = conn
    opponent = room['player1'] if conn == room['player2'] else room['player2']
    winner_username = get_username_from_conn(opponent)

    # Convert the board to string format for the GAMEEND message
    board_status = ''.join(['0' if cell == ' ' else '1' if cell == 'X' else '2' for row in room['board'] for cell in row])

    # Send GAMEEND message with the forfeit code (2)
    send_gameend_message(room, board_status, 2, winner_username)
    
    # Remove room after forfeit
    delete_room(room_name)


def check_winner(board: List[List[str]], player: str) -> bool:
    """Check if the given player has won the game."""

    # Check rows
    for row in board:
        if all(cell == player for cell in row):
            return True

    # Check columns
    for col in range(3):
        if all(board[row][col] == player for row in range(3)):
            return True

    # Check diagonals
    if all(board[i][i] == player for i in range(3)):
        return True
    if all(board[i][2 - i] == player for i in range(3)):
        return True

    return False

def is_draw(board: List[List[str]]) -> bool:
    """Check if the game is a draw."""
    # If any cell is still empty, the game is not a draw
    for row in board:
        if ' ' in row:
            return False
    return True  # No empty spaces, so it's a draw



def handle_create(conn, data):
    """Handle room creation request."""
    parts = data.strip().split(":")
    if len(parts) != 2:
        conn.sendall("CREATE:ACKSTATUS:4\n".encode())  # Invalid format
        return

    _, room_name = parts
    
    # Validate the room name
    if not re.match(r'^[\w\s-]+$', room_name) or len(room_name) > 20:
        conn.sendall("CREATE:ACKSTATUS:1\n".encode())  # Invalid room name
        return
    
    if len(rooms) >= 256:
        conn.sendall("CREATE:ACKSTATUS:3\n".encode())  # Max rooms limit reached
        return
    
    if room_name in rooms:
        conn.sendall("CREATE:ACKSTATUS:2\n".encode())  # Room already exists
        return

    # Initialize the board with empty spaces (' ')
    initial_board = [[' ' for _ in range(3)] for _ in range(3)]  # A 3x3 grid filled with empty spaces

    # Create the room and automatically join the user
    rooms[room_name] = {
        'modes': ["PLAYER", "VIEWER"],
        'players': 1,
        'viewers': [],
        'player1': conn,
        'player1_username': get_username_from_conn(conn),
        'player2': None,  # Will be assigned later
        'player2_username': None,  # Will be assigned later
        'board': initial_board,  # Set the empty 3x3 board
        'current_turn': conn,  # Track whose turn it is (starts with player1)
        'move_queue': []  # Queue for moves that are sent out of turn
    }

    conn.sendall("CREATE:ACKSTATUS:0\n".encode())  # Room successfully created
    print(f"Successfully created room {room_name}")


def handle_join(conn, room_name, mode, username):
    """Handle room join request."""
    if room_name not in rooms:
        conn.sendall(f"JOIN:ACKSTATUS:1\n".encode())  # Room doesn't exist
        return
    if mode.upper() not in ["PLAYER", "VIEWER"]:
        conn.sendall("JOIN:ACKSTATUS:3\n".encode())  # Invalid mode
        return
    
    room = rooms[room_name]
    
    if mode.upper() == "PLAYER" and room['players'] >= 2:
        conn.sendall(f"JOIN:ACKSTATUS:2\n".encode())  # Room already full
        return

    # Join the room as a player or viewer
    if mode.upper() == "PLAYER":
        room['players'] += 1
        # Assign player 1 or player 2
        if 'player1' not in room:
            room['player1'] = conn
            room['player1_username'] = username
        else:
            room['player2'] = conn
            room['player2_username'] = username
        print(room['players'])
        # Send ACK for successful join
        conn.sendall(f"JOIN:ACKSTATUS:0\n".encode())

        # If two players have joined, start the game
        if room['players'] == 2:
            print("startgame called")
            start_game(room_name)
    
    elif mode.upper() == "VIEWER":
        room['viewers'].append(conn)
        conn.sendall(f"JOIN:ACKSTATUS:0\n".encode())  # ACK viewer join

        # Immediately send INPROGRESS to the new viewer
        player1_username = room['player1_username']
        player2_username = room.get('player2_username', 'Waiting for player 2')
        inprogress_message = f"INPROGRESS:{player1_username}:{player2_username}\n"
        conn.sendall(inprogress_message.encode())


def get_room_for_player(conn):
    """Find the room the player is in."""
    for room_name, room in rooms.items():
        if conn == room.get('player1') or conn == room.get('player2'):
            return room_name
    return None

def start_game(room_name):
    room = rooms[room_name]
    if 'player1' in room and 'player2' in room:
        player1_conn = room['player1']
        player2_conn = room['player2']
        player1_username = room['player1_username']
        player2_username = room['player2_username']
        
        room['current_turn'] = player1_conn
        begin_message = f"BEGIN:{player1_username}:{player2_username}\n"
        
        all_clients = [player1_conn, player2_conn] + room.get('viewers', [])
        
        # Send BEGIN to players
        for client in [player1_conn, player2_conn]:
            client.sendall(begin_message.encode())
        
        # Send INPROGRESS to viewers
        inprogress_message = f"INPROGRESS:{player1_username}:{player2_username}\n"
        for viewer in room['viewers']:
            viewer.sendall(inprogress_message.encode())


def check_authenticated(conn):
    """Check if the client is authenticated."""
    return authenticated_clients.get(conn, False)

def handle_client(conn, mask, selector, users, user_file):
    try:
        data = conn.recv(8192).decode()
        if data:
            # Handle LOGIN command
            if data.startswith("LOGIN"):
                parts = data.strip().split(":")
                if len(parts) != 3:
                    conn.sendall("LOGIN:ACKSTATUS:3\n".encode())  # Invalid format
                else:
                    _, username, password = parts
                    response = check_login(conn, username, password, users)  # Pass conn as an argument
                    if "LOGIN:ACKSTATUS:0\n" in response:
                        authenticated_clients[conn] = True  # Mark the client as authenticated
                    conn.sendall(response.encode())

            # Handle REGISTER command
            elif data.startswith("REGISTER"):
                handle_register(conn, data, users, user_file)

            # Handle CREATE command
            elif data.startswith("CREATE"):
                if not check_authenticated(conn):
                    conn.sendall("BADAUTH\n".encode())
                else:
                    handle_create(conn, data)

            # Handle ROOMLIST command
            elif data.startswith("ROOMLIST"):
                if not check_authenticated(conn):
                    conn.sendall("BADAUTH\n".encode())
                else:
                    handle_roomlist(conn, data)

            # Handle PLACE command
            elif data.startswith("PLACE"):
                if not check_authenticated(conn):
                    conn.sendall("BADAUTH\n".encode())
                else:
                    parts = data.strip().split(":")
                    if len(parts) == 3:
                        _, x, y = parts
                        room_name = get_room_for_player(conn)
                        if room_name:
                            # Handle the move
                            try:
                                x = int(x)
                                y = int(y)
                                handle_place_message(room_name, conn, x, y)
                            except ValueError:
                                pass  # Invalid coordinates
                        else:
                            conn.sendall("NOROOM\n".encode())  # Client is not in any room
                    else:
                        pass  # Invalid format




            # Handle FORFEIT command
            elif data.startswith("FORFEIT"):
                if not check_authenticated(conn):
                    conn.sendall("BADAUTH\n".encode())
                else:
                    room_name = get_room_for_player(conn)
                    if room_name:
                        handle_forfeit(conn, room_name)
                    else:
                        conn.sendall("NOROOM\n".encode())  # Client is not in any room

            # Handle JOIN command
            elif data.startswith("JOIN"):
                if not check_authenticated(conn):
                    conn.sendall("BADAUTH\n".encode())
                else:
                    parts = data.strip().split(":")
                    if len(parts) != 3:
                        conn.sendall("JOIN:ACKSTATUS:3\n".encode())  # Invalid format
                    else:
                        _, room_name, mode = parts
                        username = get_username_from_conn(conn)  # Implement this function to get the username
                        handle_join(conn, room_name, mode, username)

        else:
            # Client disconnected, handle forfeit
            room_name = get_room_for_player(conn)
            if room_name:
                handle_forfeit(conn, room_name)
            print("Closing connection")
            selector.unregister(conn)
            conn.close()

    except Exception as e:
        print(f"Error: {e}")
        selector.unregister(conn)
        conn.close()


def get_username_from_conn(conn):
    return client_usernames.get(conn, None)  # Get the username from the new dictionary



def accept_wrapper(sock, selector, users, user_file):
    """Accept a new client connection."""
    conn, addr = sock.accept()
    print(f"Accepted connection from {addr}")
    conn.setblocking(False)
    # Register client connection for reading
    selector.register(conn, selectors.EVENT_READ, lambda conn, mask: handle_client(conn, mask, selector, users, user_file))


def run_server(config):
    user_file = config["userDatabase"]
    users = load_users(user_file)
    host = ''
    port = config["port"]
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
    server_socket.bind((host, port))
    server_socket.listen()
    server_socket.setblocking(False)
    print(f"Server listening on port {port}...")
    selector = selectors.DefaultSelector()
    selector.register(server_socket, selectors.EVENT_READ, lambda sock, mask: accept_wrapper(sock, selector, users, user_file))

    while True:
        events = selector.select()
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python server.py <config_file>")
        sys.exit(1)
    config_path = sys.argv[1]
    config = load_config(config_path)
    run_server(config)