import socket
import sys
import multiprocessing

def handle_login_response(response, game_state):
    """Handle the login response from the server."""
    if response.startswith("LOGIN:ACKSTATUS:"):
        status = response.split(":")[2]
        if status == "0":
            print("Login successful.")
        elif status == "1":
            print(f"Error: User {game_state['username']} not found.")
        elif status == "2":
            print("Error: Incorrect password.")
        else:
            print("Unexpected response:", response)

def handle_register_response(response):
    """Handle the registration response from the server."""
    if response.startswith("REGISTER:ACKSTATUS:"):
        status = response.split(":")[2]
        if status == "0":
            print("Registration successful.")
        elif status == "1":
            print("Error: Username already exists.")
        else:
            print("Unexpected response:", response)

def handle_roomlist_response(response):
    """Handle the room list response from the server."""
    if response.startswith("ROOMLIST:ACKSTATUS:"):
        parts = response.split(":")
        if len(parts) > 2 and parts[2] == "0":
            if len(parts) > 4:
                room_list = parts[4]
                if room_list:
                    print(parts[3] + ": " + room_list)
                else:
                    print("No rooms available.")
            else:
                print("No rooms available.")
        elif len(parts) > 1 and parts[1] == "1":
            print("Error: Invalid mode.")
        else:
            print(response)

def handle_create_response(response):
    """Handle the room creation response from the server."""
    if response.startswith("CREATE:ACKSTATUS:"):
        parts = response.split(":")
        
        if len(parts) >= 3:
            status = parts[2]
            if status == "0":
                print("Room created successfully.")
                print("Waiting for other player to join....")
            elif status == "1":
                print("Error: Invalid room name.")
            elif status == "2":
                print("Error: Room already exists.")
            elif status == "3":
                print("Error: Maximum number of rooms reached.")
            else:
                print("Unexpected response number error:", response)
        else:
            print("Unexpected response size error:", response)

def handle_join_response(response):
    """Handle the join room response from the server."""
    if response.startswith("JOIN:ACKSTATUS:"):
        status = response.split(":")[2]
        if status == "0":
            print("Successfully joined the room.")
        elif status == "1":
            print("Error: Room does not exist.")
        elif status == "2":
            print("Error: Room is full for players.")
        elif status == "3":
            print("Error: Invalid mode.")
        else:
            print("Unexpected response:", response)

def handle_place_error(response):
    """Handle the PLACE response from the server."""
    if response.startswith("PLACE:ACKSTATUS:"):
        status = response.split(":")[2]
        if status=="2":
            print("There is already a Marker here.")
        if status=="3":
            print("Not your turn your move has been Queued")

def handle_begin(response, game_state):
    """Handle BEGIN message from the server."""
    parts = response.split(":")
    print(response)
    if len(parts) == 3:
        player1 = parts[1]
        player2 = parts[2]
        if game_state["username"] == player1:
            print(f"It is your turn, {player1}.")
            game_state["player_turn"] = True
            game_state["opposing_player"] = player2
        elif game_state["username"] == player2:
            print(f"It is {player1}'s turn.")
            game_state["player_turn"] = False
            game_state["opposing_player"] = player1
        else:
            print(f"It is {player1}'s turn now")

def handle_place_response(response, game_state):
    """Handle the BOARDSTATUS message from the server and switch turns."""
    parts = response.split(":")
    if len(parts) > 1:
        board_status = parts[1]  # Get the board status string

        # Check if the length of the board status is correct
        if len(board_status) != 9:
            print(f"Unexpected board status length: {len(board_status)}. Response: {response}")
            return
        board_status = board_status.replace('1', 'X').replace('2', 'O').replace('0', ' ')
        # Create the formatted board from the string
        formatted_board = [
            f"{board_status[0]} | {board_status[1]} | {board_status[2]}",
            f"{board_status[3]} | {board_status[4]} | {board_status[5]}",
            f"{board_status[6]} | {board_status[7]} | {board_status[8]}"
        ]
        
        print("\nCurrent board status:")
        print("\n".join(formatted_board))

        if game_state["player_turn"]:
            print(f"It is now {game_state['opposing_player']}'s turn.")
            game_state["player_turn"] = False
        else:
            print(f"It is your turn, {game_state['username']}.")
            game_state["player_turn"] = True

def handle_gameend(response, game_state):
    """Handle the GAMEEND message from the server."""
    parts = response.split(":")
    if len(parts) >= 4:
        board_status = parts[1]
        game_result = parts[2]
        winner = parts[3]

        # Display final board status
        formatted_board = [
            f"{board_status[0]} | {board_status[1]} | {board_status[2]}",
            f"{board_status[3]} | {board_status[4]} | {board_status[5]}",
            f"{board_status[6]} | {board_status[7]} | {board_status[8]}"
        ]
        print("\nFinal board status:")
        print("\n".join(formatted_board))

        if game_result == "0":
            print(f"{winner} wins!")
        elif game_result == "1":
            print("The game is a draw.")
        elif game_result == "2":
            print("game forfeited")
        else:
            print("Unexpected game result.")

        # End the game
        game_state["running"] = False


def handle_inprogress(response):
    """Handle INPROGRESS message from the server."""
    parts = response.split(":")
    if len(parts) == 3:
        current_turn_player = parts[1]
        opposing_player = parts[2]
        print(f"Match between {current_turn_player} and {opposing_player} is in progress, it's {current_turn_player}'s turn.")

def handle_forfeit_response(response, game_state):
    """Handle the FORFEIT response from the server."""
    parts = response.split(":")
    if parts[0] == "FORFEIT":
        print(f"{game_state['username']} has forfeited the game.")
        game_state["running"] = False  # Stop the game loop

def handle_badauth(response):
    """Handle BADAUTH response"""
    if response == 'BADAUTH':
        print("Error: You must be logged in to perform this action")

def handle_server_message(response, game_state):
    """Handle messages received from the server."""
    if response.startswith("LOGIN:"):
        handle_login_response(response, game_state)  # Pass game_state here
    elif response.startswith("REGISTER:"):
        handle_register_response(response)
    elif response.startswith("ROOMLIST:"):
        handle_roomlist_response(response)
    elif response.startswith("CREATE:"):
        handle_create_response(response)
    elif response.startswith("JOIN:"):
        handle_join_response(response)
    elif response.startswith("BEGIN:"):
        handle_begin(response, game_state)  # Also needs game_state
    elif response.startswith("INPROGRESS:"):
        handle_inprogress(response)
    elif response.startswith("BOARDSTATUS:"):
        handle_place_response(response, game_state)  # Pass game_state here
    elif response.startswith("FORFEIT:"):
        handle_forfeit_response(response, game_state)  # Pass game_state here
    elif response.startswith("GAMEEND:"):
        handle_gameend(response, game_state)
    elif response.startswith("BADAUTH"):
        handle_badauth(response)
    elif response.startswith("PLACE"):
        handle_place_error(response)
    else:
        print("Server says:", response)

def listen_for_messages(sock, game_state):
    """Listener function to handle messages from the server."""
    buffer = ""
    while True:
        try:
            response = sock.recv(8192).decode()  # Receive data from the server
            if not response:
                print("Server has closed the connection.")
                game_state["running"] = False  # Update the running state
                break

            buffer += response  # Add the new data to the buffer

            # Process complete messages
            while '\n' in buffer:
                # Split the buffer into complete messages
                message, buffer = buffer.split('\n', 1)  # Split on the first newline
                if message:
                    handle_server_message(message, game_state)  # Handle the complete message

        except Exception as e:
            print(f"Error receiving message from server: {e}")
            game_state["running"] = False  # Update the running state
            break



def handle_place(sock, game_state):
    """Handle placing a marker on the board."""
    while True:
        if not game_state["player_turn"]:
            continue  # Wait until it's the player's turn

        try:
            # Get the X and Y coordinates from the user
            x = int(input("Enter X coordinate (0-2): ").strip())
            y = int(input("Enter Y coordinate (0-2): ").strip())
            if 0 <= x <= 2 and 0 <= y <= 2:
            # Ensure that coordinates are within bounds
                # Send the PLACE message to the server in the format PLACE:<x>:<y>
                sock.sendall(f"PLACE:{x}:{y}".encode())
                break
            else:
                print("Invalid coordinates. Please enter numbers between 0 and 2.")
        except ValueError:
            print("Please enter valid integers for coordinates.")

def handle_user_input(sock, game_state):
    """Handle user commands and send them to the server."""
    while True:
        command = input().strip().upper()
        if command == "LOGIN":
            username = input("Enter your username: ")
            password = input("Enter your password: ")
            game_state["username"] = username
            sock.sendall(f"LOGIN:{username}:{password}".encode())
        elif command == "REGISTER":
            username = input("Enter a new username: ")
            password = input("Enter a new password: ")
            sock.sendall(f"REGISTER:{username}:{password}".encode())
        elif command == "ROOMLIST":
            mode = input("Enter mode (PLAYER/VIEWER): ")
            sock.sendall(f"ROOMLIST:{mode}".encode())
        elif command == "CREATE":
            room_name = input("Enter the room name: ")
            sock.sendall(f"CREATE:{room_name}".encode())
        elif command == "JOIN":
            room_name = input("Enter the room name to join: ")
            mode = input("Enter mode (PLAYER/VIEWER): ")
            sock.sendall(f"JOIN:{room_name}:{mode}".encode())
        elif command == "FORFEIT":
            sock.sendall("FORFEIT".encode())  # Send FORFEIT message to the server
        elif command == "PLACE":
            x = input("Enter X coordinate (0-2): ").strip()
            y = input("Enter Y coordinate (0-2): ").strip()
                # Send the PLACE message to the server in the format PLACE:<x>:<y>
            sock.sendall(f"PLACE:{x}:{y}".encode())
        elif command == "QUIT":
            print("Closing connection and exiting...")
            game_state["running"] = False  # Set running to False
            return  # Return from the function
        else:
            print("Invalid command. Please try again.")

def main():
    if len(sys.argv) != 3:
        print("Usage: python client.py <host> <port>")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])

    # Create a manager to share data between processes
    manager = multiprocessing.Manager()
    game_state = manager.dict()  # Shared dictionary for game state

    # Initialize game state
    game_state["username"] = None
    game_state["player_turn"] = False
    game_state["opposing_player"] = None
    game_state["running"] = True

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        print(f"Connected to server at {host}:{port}")
    except Exception as e:
        print(f"Failed to connect to server: {e}")
        sys.exit(1)

    # Create a process for listening to messages from the server
    listener_process = multiprocessing.Process(target=listen_for_messages, args=(sock, game_state))
    listener_process.start()

    # Handle user input in the main process
    try:
        while game_state["running"]:
            handle_user_input(sock, game_state)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        sock.close()
        listener_process.terminate()  # Ensure the listener process is terminated
        listener_process.join()  # Ensure the listener process ends

if __name__ == "__main__":
    main()