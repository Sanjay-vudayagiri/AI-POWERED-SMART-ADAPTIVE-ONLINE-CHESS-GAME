import os
import json
import chess

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from chess_logic.minimax import find_best_move
from chess_logic.ai_levels import get_depth_for_level

app = Flask(__name__)
app.secret_key = 'some_secret_key'  # Replace with a secure random key

USER_DATA_FILE = 'user_data.json'
PVP_MOVES_FILE = 'pvp_moves.json'


#####################################
# HELPER: Load/save user data
#####################################
def load_users():
    if not os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'w') as f:
            json.dump({}, f)
        return {}
    with open(USER_DATA_FILE, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_users(users):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(users, f, indent=4)


#####################################
# HELPER: PVP moves logic (undo)
#####################################
def load_pvp_history():
    if not os.path.exists(PVP_MOVES_FILE):
        with open(PVP_MOVES_FILE, 'w') as f:
            json.dump({"history": []}, f)
        return []
    with open(PVP_MOVES_FILE, 'r') as f:
        data = json.load(f)
        return data.get("history", [])

def save_pvp_history(hist):
    with open(PVP_MOVES_FILE, 'w') as f:
        json.dump({"history": hist}, f, indent=4)


#####################################
# HELPER: Convert board -> 8x8 matrix
#####################################
def board_to_matrix(board: chess.Board):
    matrix = []
    for rank in range(7, -1, -1):
        row = []
        for file in range(8):
            sq = rank * 8 + file
            piece = board.piece_at(sq)
            row.append(piece.symbol() if piece else None)
        matrix.append(row)
    return matrix


#####################################
# ROUTES
#####################################
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        users = load_users()
        if email in users:
            return "Email already registered. Please go back and log in."

        # Create a new user record
        users[email] = {
            "name": name,
            "email": email,
            "password": password,
            "games_played": 0,
            "games_won": 0,
            "games_lost": 0,
            "unlocked_level": 1
        }
        save_users(users)

        # Show popup on the login page
        flash("Sign up successful!")
        return redirect(url_for('index'))

    else:
        return render_template('signup.html')


@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']

    # 1) Check if admin
    if email == 'admin123' and password == 'password123':
        session['is_admin'] = True
        return redirect(url_for('admin_dashboard'))

    # 2) Otherwise, normal user
    users = load_users()
    if email in users and users[email]['password'] == password:
        session['user_email'] = email
        session.pop('is_admin', None)  # ensure admin flag is removed
        return redirect(url_for('dashboard'))
    else:
        return "Invalid credentials. Please go back and try again."


@app.route('/dashboard', methods=['GET','POST'])
def dashboard():
    if 'user_email' not in session:
        return redirect(url_for('index'))

    users = load_users()
    user = users[session['user_email']]

    if request.method == 'POST':
        change_option = request.form.get('change_option')
        if change_option == 'password':
            current_password = request.form.get('current_password')
            if current_password != user['password']:
                return "Current password invalid."
            new_password = request.form.get('new_password')
            if new_password:
                user['password'] = new_password

        elif change_option == 'name':
            new_name = request.form.get('new_name')
            if new_name:
                user['name'] = new_name

        elif change_option == 'email':
            new_email = request.form.get('new_email')
            if new_email and new_email not in users:
                old_data = users.pop(session['user_email'])
                old_data['email'] = new_email
                users[new_email] = old_data
                session['user_email'] = new_email
            else:
                return "That new email is invalid or already in use."

        save_users(users)
        return redirect(url_for('dashboard'))

    return render_template('dashboard.html', user=user)


#####################################
# ADMIN
#####################################
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'is_admin' not in session or not session['is_admin']:
        return "Not authorized."

    users = load_users()
    user_list = []
    for email, data in users.items():
        user_list.append({
            "email": email,
            "name": data.get("name"),
            "games_played": data.get("games_played", 0),
            "games_won": data.get("games_won", 0),
            "games_lost": data.get("games_lost", 0),
            "unlocked_level": data.get("unlocked_level", 1)
            # no password
        })
    return render_template('admin_dashboard.html', user_list=user_list)


@app.route('/admin_delete_user/<email>')
def admin_delete_user(email):
    if 'is_admin' not in session or not session['is_admin']:
        return "Not authorized."

    users = load_users()
    if email in users:
        users.pop(email)
        save_users(users)
        flash(f"Deleted user {email}")
    return redirect(url_for('admin_dashboard'))


#####################################
# SELECT LEVEL (Play vs AI)
#####################################
@app.route('/select_level', methods=['GET','POST'])
def select_level():
    if 'user_email' not in session:
        return redirect(url_for('index'))

    users = load_users()
    user = users[session['user_email']]
    unlocked_level = user['unlocked_level']

    if request.method == 'POST':
        chosen_level = int(request.form.get('chosen_level'))
        session['board_fen'] = chess.Board().fen()
        session['current_level'] = chosen_level
        return redirect(url_for('play'))

    return render_template('select_level.html', unlocked_level=unlocked_level)


#####################################
# PLAY vs AI (NO UNDO)
#####################################
@app.route('/play')
def play():
    if 'user_email' not in session:
        return redirect(url_for('index'))
    if 'board_fen' not in session:
        return redirect(url_for('select_level'))

    board = chess.Board(session['board_fen'])
    board_matrix = board_to_matrix(board)
    level = session.get('current_level', 1)
    return render_template('play.html', board_matrix=board_matrix, mode='play', level=level)


#####################################
# PLAYER vs PLAYER (WITH UNDO)
#####################################
@app.route('/play_pvp')
def play_pvp():
    if 'user_email' not in session:
        return redirect(url_for('index'))

    if 'board_fen_pvp' not in session:
        new_board = chess.Board()
        session['board_fen_pvp'] = new_board.fen()
        save_pvp_history([new_board.fen()])

    board = chess.Board(session['board_fen_pvp'])
    board_matrix = board_to_matrix(board)
    return render_template('play_pvp.html', board_matrix=board_matrix)


#####################################
# GET LEGAL MOVES
#####################################
@app.route('/get_legal_moves', methods=['POST'])
def get_legal_moves():
    data = request.get_json()
    row = data['row']
    col = data['col']
    mode = data['mode']

    if mode=='pvp':
        fen = session.get('board_fen_pvp')
    else:
        fen = session.get('board_fen') if mode=='play' else session.get('board_fen_practice')

    if not fen:
        return jsonify({'status': 'no_board'})

    board = chess.Board(fen)
    sq_index = (7 - row)*8 + col
    piece = board.piece_at(sq_index)
    if not piece:
        return jsonify({'status': 'no_piece'})
    if piece.color != board.turn:
        return jsonify({'status': 'not_your_turn'})

    moves = []
    for move in board.legal_moves:
        if move.from_square == sq_index:
            to_sq = move.to_square
            to_rank = 7 - (to_sq // 8)
            to_file = to_sq % 8
            moves.append({'row': to_rank, 'col': to_file})

    return jsonify({
        'status': 'ok',
        'moves': moves,
        'pieceType': piece.symbol()
    })


#####################################
# MAKE MOVE (JSON)
#####################################
@app.route('/make_move_json', methods=['POST'])
def make_move_json():
    data = request.get_json()
    fromRow = data['fromRow']
    fromCol = data['fromCol']
    toRow = data['toRow']
    toCol = data['toCol']
    mode = data['mode']
    promotion_choice = data.get('promotion')

    if mode=='pvp':
        fen_key = 'board_fen_pvp'
    else:
        fen_key = 'board_fen' if mode=='play' else 'board_fen_practice'

    fen = session.get(fen_key)
    if not fen:
        return jsonify({'status': 'no_board'})

    board = chess.Board(fen)
    from_sq = (7 - fromRow)*8 + fromCol
    to_sq = (7 - toRow)*8 + toCol
    move = chess.Move(from_sq, to_sq)

    # Promotion if it's a pawn
    if promotion_choice:
        promo_map = {'q': chess.QUEEN, 'r': chess.ROOK, 'n': chess.KNIGHT, 'b': chess.BISHOP}
        if promotion_choice in promo_map:
            move.promotion = promo_map[promotion_choice]

    if move not in board.legal_moves:
        return jsonify({'status': 'illegal_move'})

    board.push(move)
    session[fen_key] = board.fen()

    is_check = board.is_check()
    is_checkmate = board.is_checkmate()

    # If pvp => record fen in pvp_moves.json
    if mode=='pvp':
        hist = load_pvp_history()
        hist.append(board.fen())
        if len(hist)>2:
            hist.pop(0)
        save_pvp_history(hist)

        if board.is_game_over():
            handle_game_end(board.result(), mode)
            return jsonify({'status': 'game_over','check':is_check,'checkmate':is_checkmate})
        return jsonify({'status': 'ok','check':is_check,'checkmate':is_checkmate})

    # If AI
    if board.is_game_over():
        handle_game_end(board.result(), mode)
        return jsonify({'status': 'game_over','check':is_check,'checkmate':is_checkmate})

    if mode=='play':
        lvl = session.get('current_level', 1)
        ai_depth = get_depth_for_level(lvl)
    else:
        ai_depth = 1

    ai_is_white = board.turn
    best_move = find_best_move(board, ai_depth, ai_is_white)
    if best_move:
        board.push(best_move)
        session[fen_key] = board.fen()
        is_check = board.is_check()
        is_checkmate = board.is_checkmate()
        if board.is_game_over():
            handle_game_end(board.result(), mode)
            return jsonify({'status':'game_over','check':is_check,'checkmate':is_checkmate})

    return jsonify({'status':'ok','check':is_check,'checkmate':is_checkmate})


#####################################
# UNDO (PVP only)
#####################################
@app.route('/undo_move', methods=['POST'])
def undo_move():
    data = request.get_json()
    mode = data['mode']

    if mode=='pvp':
        hist = load_pvp_history()
        if len(hist)>1:
            hist.pop()
            save_pvp_history(hist)
            session['board_fen_pvp'] = hist[-1]
        return jsonify({'status':'ok'})
    else:
        # AI => no undo
        return jsonify({'status':'ok'})


#####################################
# RESET BOARD
#####################################
@app.route('/reset_board', methods=['POST'])
def reset_board():
    data = request.get_json()
    mode = data['mode']

    if mode=='pvp':
        session.pop('board_fen_pvp', None)
        save_pvp_history([])
    elif mode=='play':
        session.pop('board_fen', None)
    else:
        session.pop('board_fen_practice', None)

    return jsonify({'status':'ok'})


#####################################
# GAME END
#####################################
def handle_game_end(result: str, mode: str):
    if mode=='play':
        users = load_users()
        user = users[session['user_email']]
        user['games_played'] += 1
        if result=='1-0':
            user['games_won'] += 1
            if user['unlocked_level']<10:
                user['unlocked_level']+=1
        elif result=='0-1':
            user['games_lost'] += 1
        save_users(users)

    if mode=='pvp':
        session.pop('board_fen_pvp', None)
        save_pvp_history([])
    elif mode=='play':
        session.pop('board_fen', None)
    else:
        session.pop('board_fen_practice', None)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


if __name__=='__main__':
    app.run(debug=True)
