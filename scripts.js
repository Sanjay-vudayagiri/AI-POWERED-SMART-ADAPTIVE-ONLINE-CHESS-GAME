// File: static/js/scripts.js

const pieceDescriptions = {
  'p': {
    name: 'Pawn (Soldier)',
    rules: [
      'Moves forward 1 square (2 from start)',
      'Captures diagonally forward',
      'Promotes upon reaching far rank'
    ],
    desc: 'Most common piece, can promote to R, N, B, or Q.'
  },
  'r': {
    name: 'Rook',
    rules: [
      'Moves horizontally or vertically any number of squares',
      'Cannot jump over other pieces'
    ],
    desc: 'Strong on open files/ranks; can castle with King.'
  },
  'n': {
    name: 'Knight',
    rules: [
      'Moves in an L-shape (2+1)',
      'Can jump over pieces'
    ],
    desc: 'Only piece that can leap over others.'
  },
  'b': {
    name: 'Bishop',
    rules: [
      'Moves diagonally any number of squares',
      'Cannot jump over other pieces',
      'Stays on one color squares'
    ],
    desc: 'Controls diagonals; each bishop is locked to one color.'
  },
  'q': {
    name: 'Queen',
    rules: [
      'Combines Rook & Bishop moves',
      'Moves any number of squares in any direction'
    ],
    desc: 'Most powerful piece, crucial in offense.'
  },
  'k': {
    name: 'King',
    rules: [
      'Moves 1 square in any direction if safe',
      'Cannot move into check',
      'Can castle with rook'
    ],
    desc: 'Checkmate ends the game.'
  }
};

// 1) Mapping of piece -> video file (in static/videos/)
const pieceAnimations = {
  'p': 'pawn.mp4',
  'r': 'rook.mp4',
  'n': 'knight.mp4',
  'b': 'bishop.mp4',
  'q': 'queen.mp4',
  'k': 'king.mp4'
};

let selectedSquare = null;
let possibleMoves = [];
let selectedMode = "play"; // or "pvp"
let selectedPieceSymbol = null; // We'll track the last selected piece symbol for promotion logic

function handleSquareClick(squareDiv) {
  const row = parseInt(squareDiv.dataset.row);
  const col = parseInt(squareDiv.dataset.col);
  const mode = squareDiv.dataset.mode;

  if (!selectedSquare) {
    fetch('/get_legal_moves', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ row, col, mode })
    })
    .then(res => res.json())
    .then(data => {
      if (data.status === 'ok') {
        selectedSquare = { row, col };
        selectedMode = mode;
        possibleMoves = data.moves;
        selectedPieceSymbol = data.pieceType; // e.g. 'P', 'q'

        highlightSelectedSquare(row, col);
        highlightMoves(possibleMoves);

        if (data.pieceType) {
          showPieceInfo(data.pieceType);
        } else {
          clearPieceInfo();
        }
      } else {
        // e.g. no_piece, not_your_turn
        clearHighlights();
        clearPieceInfo();
      }
    })
    .catch(err => console.error(err));
  } else {
    // We already selected a piece; check if new click is valid
    const isValid = possibleMoves.some(m => m.row === row && m.col === col);
    if (isValid) {
      makeMove(selectedSquare.row, selectedSquare.col, row, col, selectedMode);
    } else {
      clearHighlights();
      clearPieceInfo();
    }
  }
}

function makeMove(fromRow, fromCol, toRow, toCol, mode) {
  let promotion = null;
  // If it's a pawn, check if we're hitting last rank, etc. (You might have that logic here)

  // ...
  // The rest of your existing code for sending /make_move_json
  // ...
  fetch('/make_move_json', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fromRow, fromCol, toRow, toCol, mode, promotion })
  })
  .then(res => res.json())
  .then(data => {
    if (data.status === 'ok') {
      if (data.checkmate) {
        alert("Checkmate!");
      } else if (data.check) {
        alert("Check!");
      }
      window.location.reload();
    } else if (data.status === 'game_over') {
      alert("Game Over!");
      window.location.reload();
    } else {
      console.warn("Move error:", data.status);
      clearHighlights();
      clearPieceInfo();
    }
  })
  .catch(err => console.error(err));
}

/** Only used in PVP mode, but won't break if called in AI mode. */
function undoMove(mode) {
  fetch('/undo_move', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode })
  })
  .then(() => {
    window.location.reload();
  })
  .catch(err => console.error(err));
}

/** Resets the board (both PVP or AI). */
function resetBoard(mode) {
  fetch('/reset_board', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode })
  })
  .then(() => {
    window.location.reload();
  })
  .catch(err => console.error(err));
}

/** Highlight logic (same as your final code). */
function highlightSelectedSquare(row, col) {
  const sq = getSquare(row, col);
  if (sq) sq.classList.add('selected-square');
}

function highlightMoves(movesArray) {
  movesArray.forEach(m => {
    const sq = getSquare(m.row, m.col);
    if (sq) sq.classList.add('highlight-square');
  });
}

function clearHighlights() {
  selectedSquare = null;
  possibleMoves = [];
  selectedPieceSymbol = null;
  document.querySelectorAll('.square').forEach(sq => {
    sq.classList.remove('selected-square', 'highlight-square');
  });
}

/** Show piece info (and also show piece animation). */
function showPieceInfo(symbol) {
  // existing logic to fill #piece-info-panel with rules, desc
  const infoPanel = document.getElementById('piece-info-panel');
  const lower = symbol.toLowerCase();
  const color = (symbol === symbol.toUpperCase()) ? 'White' : 'Black';

  if (!pieceDescriptions[lower]) {
    infoPanel.innerHTML = `<h3>No piece selected</h3>`;
    hidePieceAnimation();
    return;
  }

  const pd = pieceDescriptions[lower];
  infoPanel.innerHTML = `
    <h3>${color} ${pd.name}</h3>
    <p><strong>Rules:</strong></p>
    <ul>
      ${pd.rules.map(r => `<li>${r}</li>`).join('')}
    </ul>
    <p>${pd.desc}</p>
  `;

  // Also show the piece animation
  showPieceAnimation(lower);
}

/** Clear piece info panel and hide the animation. */
function clearPieceInfo() {
  const infoPanel = document.getElementById('piece-info-panel');
  if (infoPanel) {
    infoPanel.innerHTML = `<h3>No piece selected</h3>`;
  }
  // Hide the animation as well
  hidePieceAnimation();
}

/** 2) Show the animation for the given piece. */
function showPieceAnimation(lowerSymbol) {
  const videoBox = document.getElementById('piece-animation-panel');
  const videoElement = document.getElementById('piece-animation');

  if (pieceAnimations[lowerSymbol]) {
    const vidFile = pieceAnimations[lowerSymbol];
    videoElement.src = '/static/videos/' + vidFile;
    videoBox.style.display = 'block';   // make sure it's visible
  } else {
    // no known animation => hide
    videoElement.src = '';
    videoBox.style.display = 'none';
  }
}

/** 3) Hide the animation entirely. */
function hidePieceAnimation() {
  const videoBox = document.getElementById('piece-animation-panel');
  const videoElement = document.getElementById('piece-animation');
  videoElement.src = ''; // stop the video
  videoBox.style.display = 'none';
}

function getSquare(row, col) {
  return document.querySelector(`.square[data-row='${row}'][data-col='${col}']`);
}
