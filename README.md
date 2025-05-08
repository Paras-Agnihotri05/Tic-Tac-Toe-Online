# Tic-Tac-Toe-Online

## Project Overview
This is an online multiplayer Tic Tac Toe game implemented in Python, featuring a client-server architecture that allows multiple players to play together over a network.

## Prerequisites
- Python 3.7+
- Required Python libraries (install via pip):
  ```
  pip install -r requirements.txt
  ```

## Project Structure
- `server.py`: Handles game server logic and player connections
- `client.py`: Manages client-side game interactions
- `game.py`: Implements the core Tic Tac Toe game logic
- `tictactoe.py`: Additional game-related utilities
- `config.json`: Configuration settings
- `users.json`: User management file

## Setup and Running

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the Server
```bash
python server.py
```

### 3. Start a Client
```bash
python client.py
```

## How to Play
1. Run the server first
2. Launch multiple client instances
3. Follow on-screen prompts to create or join a game
4. Take turns placing your X or O on the 3x3 grid
5. First player to get 3 in a row wins!

## Features
- Multiplayer online gameplay
- Real-time game state synchronization
- User authentication
- Game room management

## Troubleshooting
- Ensure all players are on the same network
- Check that the server is running before launching clients
- Verify Python and all dependencies are correctly installed

## Contributing
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License
[Specify your license]

## Contact
[Your contact information]
