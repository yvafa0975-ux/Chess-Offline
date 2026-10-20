# -*- coding: utf-8 -*-
import json, os, random, sys, time, threading, ast, operator, math, struct, wave, subprocess, shutil
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog

try:
    import chess
except ImportError:
    chess = None

APP = "Шахматы Offline 1.6"
BG, PANEL, PANEL2 = "#101722", "#182536", "#213247"
TEXT, MUTED, ACCENT, GREEN = "#edf3fb", "#9eafc5", "#7c9cff", "#46d69a"
LIGHT, DARK, SELECT = "#e8dfca", "#75917f", "#f5d76e"
SYMBOL = {"K":"♔","Q":"♕","R":"♖","B":"♗","N":"♘","P":"♙",
          "k":"♚","q":"♛","r":"♜","b":"♝","n":"♞","p":"♟"}

def data_file():
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA", str(Path.home())))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home()) / ".config"))
    folder = root / "ChessOffline"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "profile.json"

SAVE = data_file()
DEFAULT = {"nickname":"","elo":0,"games":0,"wins":0,"losses":0,"draws":0,
           "level":2,"mode":"Тренировка","fen":"","rated_active":False,
           "level_elo":{str(i):0 for i in range(1,9)}, "verified":False, "verified_before":False}

def load():
    try:
        d = json.loads(SAVE.read_text(encoding="utf-8"))
        DEFAULT.update(d if isinstance(d, dict) else {})
    except Exception:
        pass
    return DEFAULT.copy()

def save(profile):
    try: SAVE.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError: pass

VAL = {1:100, 2:320, 3:330, 4:500, 5:900, 6:20000}

def evaluate(board):
    score = 0
    for ptype, value in VAL.items():
        score += len(board.pieces(ptype, chess.WHITE))*value
        score -= len(board.pieces(ptype, chess.BLACK))*value
    for sq in (chess.D4, chess.E4, chess.D5, chess.E5):
        p = board.piece_at(sq)
        if p: score += 16 if p.color else -16
    return score if board.turn else -score

def search(board, depth, alpha, beta, deadline):
    if time.monotonic() > deadline: raise TimeoutError
    if board.is_checkmate(): return -100000, None
    if board.is_game_over(claim_draw=True): return 0, None
    if depth == 0: return evaluate(board), None
    best, bestmove = -10**9, None
    moves = list(board.legal_moves)
    random.shuffle(moves)
    moves.sort(key=lambda m: board.is_capture(m) or bool(m.promotion), reverse=True)
    for m in moves:
        board.push(m)
        try: score, _ = search(board, depth-1, -beta, -alpha, deadline)
        except TimeoutError:
            board.pop()
            raise
        board.pop()
        score = -score
        if score > best: best, bestmove = score, m
        alpha = max(alpha, score)
        if alpha >= beta: break
    return best, bestmove

def bot_move(board, level):
    """A deliberately beginner-friendly bot with occasional imperfect moves."""
    moves = list(board.legal_moves)
    if not moves: return None
    level = max(1, min(8, int(level)))
    # All levels are softened: lower levels choose randomly often, while even
    # the strongest levels search only briefly and can make a casual mistake.
    random_chance = {1:1.00, 2:.82, 3:.68, 4:.55, 5:.43, 6:.32, 7:.24, 8:.18}[level]
    if random.random() < random_chance:
        return random.choice(moves)
    depth = {1:1, 2:1, 3:1, 4:1, 5:1, 6:1, 7:2, 8:2}[level]
    seconds = {1:.05, 2:.06, 3:.08, 4:.10, 5:.12, 6:.15, 7:.22, 8:.30}[level]
    try:
        _, m = search(board.copy(), depth, -10**9, 10**9, time.monotonic()+seconds)
        return m if m in board.legal_moves else random.choice(moves)
    except TimeoutError:
        return random.choice(moves)

class Game:
    def __init__(self, root):
        self.root=root; self.p=load(); self.board=chess.Board()
        if self.p.get("fen"):
            try: self.board=chess.Board(self.p["fen"])
            except ValueError: pass
        self.mode=self.p.get("mode","Тренировка"); self.level=max(1,min(8,int(self.p.get("level",2))))
        self.selected=None; self.targets=[]; self.thinking=False; self.flipped=False
        # Separate rating for each bot level; old profiles start at zero on all levels.
        saved_level_elo = self.p.get("level_elo", {})
        self.p["level_elo"] = {str(i): max(0, int(saved_level_elo.get(str(i), 0) or 0))
                               for i in range(1, 9)}
        self.p["elo"] = sum(self.p["level_elo"].values())
        self.p["verified"] = bool(self.p.get("verified", False))
        self.p["verified_before"] = bool(self.p.get("verified_before", False))
        save(self.p)
        self.rating_game=bool(self.p.get("rated_active",False))
        root.title(APP); root.configure(bg=BG); root.minsize(850,650)
        self.screen = "home"
        self.make_home()
        root.protocol("WM_DELETE_WINDOW",self.close)
        if not self.p.get("nickname"):
            root.after(250, self.first_profile)

    def clear_root(self):
        for child in self.root.winfo_children():
            child.destroy()

    def first_profile(self):
        # First-run form: nickname is set once and cannot be edited later.
        self.clear_root()
        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill="both", expand=True)
        center = tk.Frame(wrap, bg=PANEL, padx=42, pady=34, highlightthickness=1, highlightbackground="#34465d")
        center.place(relx=.5, rely=.5, anchor="center")
        tk.Label(center, text="♟  ШАХМАТЫ OFFLINE", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 25, "bold")).pack(pady=(0, 8))
        tk.Label(center, text="Создай профиль игрока", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 11)).pack(pady=(0, 22))
        tk.Label(center, text="Ник", bg=PANEL, fg=TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        nick = tk.Entry(center, font=("Segoe UI", 12), width=32, relief="flat")
        nick.pack(ipady=8, pady=(5, 15))
        tk.Label(center, text="Ник нельзя будет изменить позже.", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 18))
        def submit():
            name = nick.get().strip()
            if not name:
                messagebox.showwarning("Нужен ник", "Введи ник, чтобы продолжить.")
                return
            self.p["nickname"] = name[:20]
            save(self.p)
            self.make_home()
        tk.Button(center, text="Продолжить", command=submit, bg=ACCENT, fg="#101722",
                  activebackground="#a3b8ff", relief="flat", font=("Segoe UI", 11, "bold"),
                  padx=24, pady=10, cursor="hand2").pack(fill="x")
        nick.focus_set()

    def make_home(self):
        self.screen = "home"
        self.clear_root()
        self.root.title("Шахматы Offline — главное меню")
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill="both", expand=True)
        top = tk.Frame(outer, bg=BG)
        top.pack(fill="x", padx=34, pady=(30, 20))
        tk.Label(top, text="♟  ШАХМАТЫ", bg=BG, fg=TEXT,
                 font=("Segoe UI", 30, "bold")).pack(anchor="w")
        tk.Label(top, text="OFFLINE  •  ИГРАЙ В СВОЁМ ТЕМПЕ", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(5, 0))
        name = self.p.get("nickname") or "Игрок"
        greet = tk.Frame(outer, bg=BG)
        greet.pack(pady=(14, 2))
        if self.p.get("verified_before"):
            self.verified_badge(greet, size=24, style="chess")
        tk.Label(greet, text=name, bg=BG, fg=TEXT,
                 font=("Segoe UI", 19, "bold")).pack(side="left", padx=(2, 0))
        if self.p.get("verified"):
            self.verified_badge(greet, size=24)
        if self.p.get("verified_before"):
            tk.Label(outer, text='Верифицировано организацией "Chess"', bg=BG, fg="#7faaff",
                     font=("Segoe UI", 9, "bold")).pack(pady=(0, 2))
        if self.p.get("verified"):
            tk.Label(outer, text='Верифицировано "Chess-Offline"', bg=BG, fg="#7faaff",
                     font=("Segoe UI", 9, "bold")).pack(pady=(0, 3))
        tk.Label(outer, text=f"Твой рейтинг: {self.p.get('elo', 0)} ELO   •   Партий сыграно: {self.p.get('games', 0)}",
                 bg=BG, fg=MUTED, font=("Segoe UI", 11)).pack(pady=(0, 22))
        cards = tk.Frame(outer, bg=BG)
        cards.pack(expand=True, padx=30, pady=8)
        self.menu_card(cards, "♙", "ТРЕНИРОВКА",
                       "Играй с ботом без изменения ELO.\\nПробуй новые идеи и учись.",
                       lambda: self.pre_game("Тренировка"), 0, 0, "#213d37")
        self.menu_card(cards, "♚", "РЕЙТИНГ",
                       "Начни с 0 ELO. Победы повышают\\nрейтинг, поражения могут его снизить.",
                       lambda: self.pre_game("Рейтинг"), 0, 1, "#293454")
        self.menu_card(cards, "⚙", "ПРОФИЛЬ",
                       "Измени ник или фамилию.\\nПрогресс хранится на этом ПК.",
                       self.edit_profile, 1, 0, "#3b304d")
        self.menu_card(cards, "▶", "ПРОДОЛЖИТЬ",
                       "Вернись к сохранённой позиции\\nили начни новую партию.",
                       self.continue_game, 1, 1, "#3e3828")
        tk.Button(outer, text="Калькулятор", command=self.open_calculator,
                  bg=PANEL2, fg=TEXT, activebackground=ACCENT, relief="flat",
                  font=("Segoe UI", 10, "bold"), padx=18, pady=7,
                  cursor="hand2").pack(pady=(4, 8))
        tk.Label(outer, text="Полностью офлайн • Боты 1–8 • Сохранение на этом компьютере",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(pady=(0, 22))

    def menu_card(self, parent, icon_text, title, desc, command, row, col, color):
        card = tk.Frame(parent, bg=PANEL, padx=25, pady=22, highlightthickness=1,
                        highlightbackground="#34465d", width=350, height=190)
        card.grid(row=row, column=col, padx=12, pady=12, sticky="nsew")
        card.grid_propagate(False)
        tk.Label(card, text=icon_text, bg=color, fg=TEXT, font=("Segoe UI Symbol", 25),
                 width=3, height=1).pack(anchor="w")
        tk.Label(card, text=title, bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(10, 5))
        tk.Label(card, text=desc, bg=PANEL, fg=MUTED, justify="left",
                 font=("Segoe UI", 9)).pack(anchor="w")
        tk.Button(card, text="Выбрать  →", command=command, bg=color, fg=TEXT,
                  activebackground=ACCENT, relief="flat", font=("Segoe UI", 10, "bold"),
                  padx=14, pady=7, cursor="hand2").pack(anchor="e", side="bottom")

    def pre_game(self, mode):
        self.clear_root()
        frame = tk.Frame(self.root, bg=BG)
        frame.pack(fill="both", expand=True)
        panel = tk.Frame(frame, bg=PANEL, padx=34, pady=30, highlightthickness=1,
                         highlightbackground="#34465d")
        panel.place(relx=.5, rely=.5, anchor="center")
        tk.Label(panel, text=mode.upper(), bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 23, "bold")).pack(pady=(0, 6))
        detail = "Рейтинг: у каждого уровня свой ELO. Победа +20, поражение −10." if mode == "Рейтинг" else "Тренировка: играй без изменения ELO."
        tk.Label(panel, text=detail, bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).pack(pady=(0, 22))
        tk.Label(panel, text="Выбери уровень бота", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))
        level_var = tk.IntVar(value=self.level)
        grid = tk.Frame(panel, bg=PANEL); grid.pack()
        descriptions = ["Случайные ходы", "Очень лёгкий", "Начальный", "Любитель",
                        "Средний", "Выше среднего", "Сложный", "Максимальный"]
        for n in range(1, 9):
            tk.Radiobutton(grid, text=f"{n}  {descriptions[n-1]}", variable=level_var, value=n,
                           bg=PANEL, fg=TEXT, selectcolor=PANEL2, activebackground=PANEL,
                           font=("Segoe UI", 10), anchor="w").grid(row=(n-1)//2, column=(n-1)%2,
                                                                  padx=12, pady=7, sticky="w")
        def start():
            self.level = level_var.get()
            self.p["level"] = self.level
            self.p["mode"] = mode
            self.p["fen"] = ""
            self.p["rated_active"] = mode == "Рейтинг"
            self.board = chess.Board()
            self.rating_game = mode == "Рейтинг"
            self.selected = None; self.targets = []
            save(self.p)
            self.open_board(mode)
        tk.Button(panel, text="Начать партию", command=start, bg=ACCENT, fg="#101722",
                  activebackground="#a3b8ff", relief="flat", font=("Segoe UI", 11, "bold"),
                  padx=22, pady=10).pack(fill="x", pady=(24, 8))
        tk.Button(panel, text="Назад в меню", command=self.make_home, bg=PANEL2, fg=TEXT,
                  relief="flat", font=("Segoe UI", 10), pady=8).pack(fill="x")

    def edit_profile(self):
        # Profile is read-only: nickname is chosen once during first launch.
        self.screen = "profile"
        self.clear_root()
        frame = tk.Frame(self.root, bg=PANEL, padx=35, pady=26)
        frame.place(relx=.5, rely=.5, anchor="center")
        tk.Label(frame, text="ПРОФИЛЬ ИГРОКА", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 20, "bold")).pack(pady=(0, 14))
        tk.Label(frame, text="Твой ник", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w")
        nick_row = tk.Frame(frame, bg=PANEL)
        nick_row.pack(anchor="w", pady=(3, 14))
        if self.p.get("verified_before"):
            self.verified_badge(nick_row, size=22, style="chess")
        tk.Label(nick_row, text=self.p.get("nickname") or "Игрок", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 15, "bold")).pack(side="left", padx=(2, 0))
        if self.p.get("verified"):
            self.verified_badge(nick_row, size=22)
        if self.p.get("verified_before"):
            tk.Label(frame, text='Верифицировано организацией "Chess"', bg=PANEL, fg="#7faaff",
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 2))
        if self.p.get("verified"):
            tk.Label(frame, text='Верифицировано "Chess-Offline"', bg=PANEL, fg="#7faaff",
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 8))
        tk.Label(frame, text=f"Общий ELO: {self.p.get('elo', 0)}", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(frame, text="Рейтинг отдельно для каждого уровня", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(6, 2))
        levels = tk.Frame(frame, bg=PANEL); levels.pack(fill="x", pady=(2, 14))
        level_elo = self.p.get("level_elo", {str(i): 0 for i in range(1, 9)})
        for i in range(1, 9):
            score = int(level_elo.get(str(i), 0))
            tk.Label(levels, text=f"Уровень {i}: {score} ELO",
                     bg=PANEL, fg=GREEN if i == self.level else MUTED, anchor="w",
                     font=("Segoe UI", 9, "bold" if i == self.level else "normal")).pack(anchor="w")
        tk.Button(frame, text="Удалить все данные", command=self.delete_all_data,
                  bg="#7f2d3b", fg="#ffffff", activebackground="#a63a4c",
                  activeforeground="#ffffff", relief="flat", pady=8,
                  font=("Segoe UI", 10, "bold")).pack(fill="x", pady=(0, 8))
        tk.Button(frame, text="Назад", command=self.make_home, bg=PANEL2, fg=TEXT,
                  relief="flat", pady=8).pack(fill="x")

    def delete_all_data(self):
        confirmed = messagebox.askyesno(
            "Удалить все данные?",
            "Будут удалены ник, рейтинг, статистика, сохранённая партия и обе отметки верификации.\n\nЭто действие нельзя отменить. Продолжить?",
            icon="warning")
        if not confirmed:
            return
        try:
            SAVE.unlink(missing_ok=True)
        except OSError as exc:
            messagebox.showerror("Не удалось удалить данные", f"Не получилось удалить файл профиля:\n{exc}")
            return
        self.p = {
            "nickname": "", "elo": 0, "games": 0, "wins": 0, "losses": 0, "draws": 0,
            "level": 2, "mode": "Тренировка", "fen": "", "rated_active": False,
            "level_elo": {str(i): 0 for i in range(1, 9)},
            "verified": False, "verified_before": False
        }
        self.level = 2
        self.mode = "Тренировка"
        self.board = chess.Board()
        self.rating_game = False
        save(self.p)
        self.first_profile()

    def verified_badge(self, parent, size=20, style="offline"):
        """Draw a simple circular blue check for Offline and a queen seal for Chess."""
        import math
        canvas = tk.Canvas(parent, width=size, height=size, bg=parent.cget("bg"),
                           highlightthickness=0, bd=0)
        canvas.pack(side="left", padx=(0, 1))
        blue = "#3390ec"
        cx = cy = size / 2
        if style == "chess":
            # Scalloped blue seal with a white queen.
            points = []
            for i in range(24):
                angle = -math.pi / 2 + i * math.pi / 12
                radius = size * (0.485 if i % 2 == 0 else 0.425)
                points.extend((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
            canvas.create_polygon(*points, fill=blue, outline=blue, smooth=False)
            canvas.create_text(cx, cy, text="♛", fill="#ffffff",
                               font=("DejaVu Sans", max(10, int(size * 0.72)), "bold"))
        else:
            # Solid blue circle with a geometrically clean white checkmark.
            # A filled polygon avoids the uneven joins of a tiny smoothed line.
            pad = size * 0.055
            canvas.create_oval(pad, pad, size - pad, size - pad,
                               fill=blue, outline=blue, width=0)
            check = [
                size * 0.205, size * 0.515,
                size * 0.335, size * 0.390,
                size * 0.435, size * 0.495,
                size * 0.685, size * 0.255,
                size * 0.805, size * 0.375,
                size * 0.435, size * 0.735,
            ]
            canvas.create_polygon(*check, fill="#ffffff", outline="#ffffff",
                                  width=0, smooth=False)
        return canvas

    def open_calculator(self):
        self.screen = "calculator"
        self.clear_root()
        frame = tk.Frame(self.root, bg=PANEL, padx=28, pady=26)
        frame.place(relx=.5, rely=.5, anchor="center")
        tk.Label(frame, text="КАЛЬКУЛЯТОР", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 19, "bold")).pack(pady=(0, 14))
        expression = tk.StringVar()
        entry = tk.Entry(frame, textvariable=expression, width=28, font=("Segoe UI", 16),
                         justify="right", relief="flat")
        entry.pack(ipady=8, pady=(0, 10))
        result = tk.Label(frame, text="", bg=PANEL, fg=GREEN, font=("Segoe UI", 12))
        result.pack(pady=(0, 10))
        def submit(event=None):
            value = expression.get().strip()
            # Secret shortcut is accepted in the calculator, without advertising it in the UI.
            if value == "11111":
                self.p["verified"] = True
                save(self.p)
                self.make_home()
                return
            if value == "22222":
                self.p["verified_before"] = True
                save(self.p)
                self.make_home()
                return
            try:
                tree = ast.parse(value, mode="eval")
                allowed = {ast.Add: operator.add, ast.Sub: operator.sub,
                           ast.Mult: operator.mul, ast.Div: operator.truediv,
                           ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
                           ast.Pow: operator.pow, ast.UAdd: operator.pos,
                           ast.USub: operator.neg}
                def calc(node):
                    if isinstance(node, ast.Expression): return calc(node.body)
                    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                        return node.value
                    if isinstance(node, ast.BinOp) and type(node.op) in allowed:
                        if isinstance(node.op, ast.Pow) and abs(node.right.value if isinstance(node.right, ast.Constant) else 99) > 8:
                            raise ValueError
                        return allowed[type(node.op)](calc(node.left), calc(node.right))
                    if isinstance(node, ast.UnaryOp) and type(node.op) in allowed:
                        return allowed[type(node.op)](calc(node.operand))
                    raise ValueError
                answer = calc(tree)
                if isinstance(answer, float) and answer.is_integer(): answer = int(answer)
                result.config(text=f"= {answer}", fg=GREEN)
            except Exception:
                result.config(text="Ошибка выражения", fg="#ff8b8b")
        entry.bind("<Return>", submit)
        buttons = tk.Frame(frame, bg=PANEL); buttons.pack()
        for idx, label in enumerate(("7", "8", "9", "/", "4", "5", "6", "*", "1", "2", "3", "-", "0", ".", "(", "+", ")", "%")):
            tk.Button(buttons, text=label, width=5, command=lambda ch=label: expression.set(expression.get()+ch),
                      bg=PANEL2, fg=TEXT, relief="flat", font=("Segoe UI", 11)).grid(row=idx//4, column=idx%4, padx=2, pady=2, sticky="nsew")
        tk.Button(frame, text="Посчитать / Enter", command=submit, bg=ACCENT, fg="#101722",
                  relief="flat", pady=8).pack(fill="x", pady=(10, 5))
        tk.Button(frame, text="Назад в меню", command=self.make_home, bg=PANEL2, fg=TEXT,
                  relief="flat", pady=7).pack(fill="x")
        entry.focus_set()

    def open_verification_panel(self):
        self.clear_root()
        frame = tk.Frame(self.root, bg=PANEL, padx=30, pady=26)
        frame.place(relx=.5, rely=.5, anchor="center")
        tk.Label(frame, text="Настройки профиля", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 18, "bold")).pack(pady=(0, 12))
        enabled = tk.BooleanVar(value=bool(self.p.get("verified", False)))
        tk.Checkbutton(frame, text="Включить отметку профиля", variable=enabled,
                       bg=PANEL, fg=TEXT, selectcolor=PANEL2, activebackground=PANEL,
                       font=("Segoe UI", 11)).pack(anchor="w", pady=8)
        def apply():
            self.p["verified"] = bool(enabled.get())
            save(self.p)
            self.make_home()
        tk.Button(frame, text="Сохранить", command=apply, bg=ACCENT, fg="#101722",
                  relief="flat", pady=8).pack(fill="x", pady=(12, 5))
        tk.Button(frame, text="Назад", command=self.open_calculator, bg=PANEL2, fg=TEXT,
                  relief="flat", pady=7).pack(fill="x")

    def continue_game(self):
        mode = self.p.get("mode", "Тренировка")
        if self.p.get("fen"):
            self.open_board(mode)
            if messagebox.askyesno("Сохранённая партия", "Продолжить сохранённую партию?"):
                return
            self.new_game()
        else:
            self.open_board(mode)

    def open_board(self, mode):
        self.mode = mode
        self.modevar = tk.StringVar(value=mode)
        self.p["mode"] = mode
        self.rating_game = mode == "Рейтинг" and bool(self.p.get("rated_active", False))
        if not self.p.get("fen"):
            self.board = chess.Board()
            self.rating_game = mode == "Рейтинг"
            self.p["rated_active"] = self.rating_game
        else:
            try: self.board = chess.Board(self.p["fen"])
            except ValueError: self.board = chess.Board()
        save(self.p)
        self.make_ui()
        self.refresh()
        self.screen = "board"

    def make_ui(self):
        self.screen = "board"
        self.clear_root()
        self.root.title("Шахматы Offline — партия")
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=26, pady=(15, 8))
        tk.Button(top, text="← МЕНЮ", command=self.make_home, bg=PANEL2, fg=TEXT,
                  relief="flat", padx=14, pady=7, cursor="hand2").pack(side="left")
        tk.Label(top, text="  ШАХМАТЫ", bg=BG, fg=TEXT,
                 font=("Segoe UI", 22, "bold")).pack(side="left", padx=15)
        self.profiletop = tk.Label(top, text="", bg=BG, fg=MUTED, font=("Segoe UI", 10))
        self.profiletop.pack(side="right")
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=(0, 15))
        self.left = tk.Frame(body, bg=BG)
        self.left.pack(side="left", fill="both", expand=True)
        self.side = tk.Frame(body, bg=PANEL, width=275)
        self.side.pack(side="right", fill="y", padx=(18, 0))
        self.side.pack_propagate(False)
        self.bf = tk.Frame(self.left, bg=PANEL, padx=8, pady=8)
        self.bf.pack(expand=True, fill="both")
        self.board_canvas = tk.Canvas(self.bf, width=520, height=520, bg=PANEL,
                                      highlightthickness=0, bd=0)
        self.board_canvas.pack(expand=True, fill="both")
        self.board_canvas.bind("<Configure>", lambda event: self.draw())
        self.board_canvas.bind("<Button-1>", self.canvas_click)
        self.cells = {}
        self.status = tk.Label(self.left, text="", bg=BG, fg=TEXT,
                               font=("Segoe UI", 13, "bold"))
        self.status.pack(pady=(7, 2))
        self.hint = tk.Label(self.left, text="Выбери фигуру, затем клетку для хода.",
                             bg=BG, fg=MUTED, font=("Segoe UI", 10))
        self.hint.pack(pady=(0, 4))
        self.section("РЕЖИМ ИГРЫ")
        for m in ("Тренировка", "Рейтинг"):
            tk.Radiobutton(self.side, text=m, variable=self.modevar, value=m, command=self.change_mode,
                bg=PANEL, fg=TEXT, selectcolor=PANEL2, activebackground=PANEL,
                font=("Segoe UI", 10)).pack(anchor="w", padx=15)
        if self.mode != "Рейтинг":
            self.section("УРОВЕНЬ БОТА")
            grid = tk.Frame(self.side, bg=PANEL); grid.pack(fill="x", padx=13)
            self.levelbuttons = []
            for n in range(1,9):
                b=tk.Button(grid,text=str(n),command=lambda x=n:self.set_level(x),relief="flat",
                            font=("Segoe UI",10,"bold"),cursor="hand2")
                b.grid(row=(n-1)//4,column=(n-1)%4,padx=3,pady=3,sticky="ew"); self.levelbuttons.append(b)
            for c in range(4): grid.grid_columnconfigure(c,weight=1)
            self.leveltext=tk.Label(self.side,bg=PANEL,fg=MUTED,wraplength=230,justify="left",font=("Segoe UI",9))
            self.leveltext.pack(fill="x",padx=15,pady=8)
        else:
            self.levelbuttons = []
            self.leveltext = None
        self.section("ПАРТИЯ")
        self.moves=tk.Label(self.side,bg=PANEL,fg=TEXT,font=("Segoe UI",10)); self.moves.pack(anchor="w",padx=15)
        self.action("Новая партия",self.new_game,ACCENT,"#101722")
        if self.mode != "Рейтинг":
            self.action("Отменить ход",self.undo,PANEL2,TEXT)
            self.action("Подсказка",self.show_hint,PANEL2,TEXT)
            self.action("Перевернуть доску",self.flip,PANEL2,TEXT)
        else:
            tk.Label(self.side, text="В рейтинге подсказки и отмена отключены.",
                     bg=PANEL, fg=MUTED, wraplength=230, justify="left",
                     font=("Segoe UI", 9)).pack(anchor="w", padx=15, pady=7)
        self.section("РЕЙТИНГ")
        self.elo=tk.Label(self.side,bg=PANEL,fg=GREEN,font=("Segoe UI",15,"bold")); self.elo.pack(anchor="w",padx=15)
        self.stats=tk.Label(self.side,bg=PANEL,fg=MUTED,justify="left",font=("Segoe UI",9)); self.stats.pack(anchor="w",padx=15,pady=6)

    def section(self,s):
        tk.Label(self.side,text=s,bg=PANEL,fg=ACCENT,font=("Segoe UI",9,"bold")).pack(anchor="w",padx=15,pady=(14,7))
    def action(self,s,fn,bg,fg):
        tk.Button(self.side,text=s,command=fn,bg=bg,fg=fg,activebackground=ACCENT,relief="flat",
                  font=("Segoe UI",9,"bold"),padx=8,pady=7,cursor="hand2").pack(fill="x",padx=15,pady=3)
    def resume_dialog(self):
        if messagebox.askyesno("Незавершённая партия","Продолжить сохранённую партию?"): return
        self.new_game()
    def change_mode(self):
        self.mode=self.modevar.get(); self.p["mode"]=self.mode
        save(self.p); self.refresh()
    def set_level(self,n):
        self.level=n; self.p["level"]=n; save(self.p); self.refresh()
    def new_game(self):
        if self.thinking: return
        self._finish_shown = False
        self.board=chess.Board(); self.selected=None; self.targets=[]
        self.rating_game=self.mode=="Рейтинг"; self.p["rated_active"]=self.rating_game
        self.persist(); self.refresh()
    def square(self,r,c):
        if self.flipped: r,c=7-r,7-c
        return chess.square(c,7-r)
    def canvas_click(self, event):
        size = min(self.board_canvas.winfo_width(), self.board_canvas.winfo_height())
        if size <= 0: return
        offset_x = (self.board_canvas.winfo_width() - size) / 2
        offset_y = (self.board_canvas.winfo_height() - size) / 2
        x, y = event.x - offset_x, event.y - offset_y
        if x < 0 or y < 0 or x >= size or y >= size: return
        c, r = int(x / (size / 8)), int(y / (size / 8))
        self.click(r, c)

    def click(self,r,c):
        if self.thinking or self.board.is_game_over(claim_draw=True) or not self.board.turn: return
        sq=self.square(r,c); piece=self.board.piece_at(sq)
        if self.selected is None:
            if piece and piece.color:
                self.selected=sq; self.targets=[m.to_square for m in self.board.legal_moves if m.from_square==sq]; self.draw()
            return
        move=chess.Move(self.selected,sq)
        if move not in self.board.legal_moves:
            promo=chess.Move(self.selected,sq,promotion=chess.QUEEN)
            if promo in self.board.legal_moves: move=promo
            elif piece and piece.color:
                self.selected=sq; self.targets=[m.to_square for m in self.board.legal_moves if m.from_square==sq]; self.draw(); return
            else: self.selected=None; self.targets=[]; self.draw(); return
        self.board.push(move); self.selected=None; self.targets=[]; self.persist(); self.refresh()
        self.play_sound("move")
        if self.board.is_checkmate(): self.play_sound("mate"); self.finish(); return
        if self.board.is_check(): self.play_sound("check")
        if self.board.is_game_over(claim_draw=True): self.finish(); return
        self.thinking=True; self.status.config(text="Бот думает…")
        self.bot_started = time.monotonic()
        threading.Thread(target=self.bot_worker,daemon=True).start()
    def bot_worker(self):
        started = time.monotonic()
        move = bot_move(self.board.copy(), self.level)
        # Even easy bots should feel like an opponent thinking, not an instant response.
        min_delay = {1:1.1, 2:1.3, 3:1.5, 4:1.7, 5:1.9, 6:2.1, 7:2.3, 8:2.5}.get(self.level, 1.5)
        remaining = min_delay - (time.monotonic() - started)
        if remaining > 0: time.sleep(remaining)
        self.root.after(0,lambda:self.bot_done(move))
    def bot_done(self,m):
        self.thinking=False
        if m and m in self.board.legal_moves: self.board.push(m)
        self.persist(); self.refresh()
        self.play_sound("move")
        if self.board.is_checkmate():
            self.play_sound("mate"); self.finish(); return
        if self.board.is_check(): self.play_sound("check")
        if self.board.is_game_over(claim_draw=True): self.finish()
    def draw(self):
        if not hasattr(self, "board_canvas") or not self.board_canvas.winfo_exists(): return
        canvas = self.board_canvas
        canvas.delete("all")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        size = min(width, height)
        if size < 8: return
        ox, oy = (width-size)/2, (height-size)/2
        cell = size / 8
        targets=set(self.targets); last=self.board.peek() if self.board.move_stack else None
        lastset={last.from_square,last.to_square} if last else set()
        check_square = self.board.king(self.board.turn) if self.board.is_check() else None
        for r in range(8):
            for c in range(8):
                sq=self.square(r,c); p=self.board.piece_at(sq)
                light = (r+c)%2==0
                bg = LIGHT if light else DARK
                if sq in lastset: bg="#b8c66b" if light else "#91a653"
                if sq in targets: bg="#b7d6a5" if light else "#62866b"
                if sq==self.selected: bg=SELECT
                if sq == check_square: bg = "#e7a0a0" if light else "#c95f68"
                x1,y1=ox+c*cell,oy+r*cell; x2,y2=x1+cell,y1+cell
                canvas.create_rectangle(x1,y1,x2,y2,fill=bg,outline=bg)
                if sq in targets and not p:
                    rad=max(3,cell*.11)
                    canvas.create_oval((x1+x2)/2-rad,(y1+y2)/2-rad,(x1+x2)/2+rad,(y1+y2)/2+rad,
                                       fill="#263b2e",outline="")
                if p:
                    glyph=SYMBOL[p.symbol()]
                    font_size=max(18,int(cell*.72))
                    # Draw a subtle shadow under the glyph to improve pawn and piece contrast.
                    color="#fffdf7" if p.color else "#11151c"
                    outline="#3d493f" if p.color else "#d7d0bd"
                    canvas.create_text((x1+x2)/2+1,(y1+y2)/2+2,text=glyph,
                        font=("DejaVu Sans",font_size,"bold"),fill=outline)
                    canvas.create_text((x1+x2)/2,(y1+y2)/2,text=glyph,
                        font=("DejaVu Sans",font_size,"bold"),fill=color)
                if sq == check_square:
                    # Red ring marks the checked king; it disappears automatically when check ends.
                    margin = cell * 0.10
                    canvas.create_oval(x1 + margin, y1 + margin, x2 - margin, y2 - margin,
                                       outline="#ff293f", width=max(3, int(cell * 0.055)))

    def refresh(self):
        prefix = "◆✓ " if self.p.get("verified_before") else ""
        suffix = " ✓" if self.p.get("verified") else ""
        self.profiletop.config(text=f"{prefix}{self.p.get('nickname') or 'Игрок'}{suffix}  •  {self.p.get('elo',0)} ELO")
        for i,b in enumerate(self.levelbuttons,1):
            b.config(bg=ACCENT if i==self.level else PANEL2,fg="#101722" if i==self.level else TEXT)
        desc={1:"Очень лёгкий: случайные ходы.",2:"Лёгкий: часто ошибается.",3:"Начальный уровень.",4:"Любитель: расчёт на 2 полухода.",
              5:"Средний уровень.",6:"Выше среднего.",7:"Сложный: ищет тактику.",8:"Максимальный офлайн-уровень; может думать несколько секунд."}
        if self.leveltext is not None:
            self.leveltext.config(text=desc[self.level])
        self.draw()
        self.moves.config(text=f"Полуходов: {len(self.board.move_stack)}")
        self.elo.config(text=f"{self.p.get('elo',0)} ELO")
        self.stats.config(text=f"Партий: {self.p.get('games',0)}\\nПобед: {self.p.get('wins',0)}\\nПоражений: {self.p.get('losses',0)}\\nНичьих: {self.p.get('draws',0)}")
        if self.board.is_checkmate(): msg="♚ МАТ! Партия завершена."
        elif self.board.is_stalemate() or self.board.is_insufficient_material(): msg="Ничья — нет возможных победных ходов."
        elif self.board.is_check(): msg="⚠ ШАХ! Король под атакой."
        elif self.thinking: msg="Бот думает…"
        else: msg="Твой ход (белые)." if self.board.turn else "Ход бота (чёрные)."
        self.status.config(text=msg)
    def _make_chess_sound(self, kind):
        # Create a short synthesized wooden click / soft check tone using only the stdlib.
        sound_dir = SAVE.parent / "sounds"
        sound_dir.mkdir(parents=True, exist_ok=True)
        path = sound_dir / f"{kind}.wav"
        if path.exists():
            return str(path)
        rate = 22050
        duration = 0.105 if kind == "move" else (0.20 if kind == "check" else 0.30)
        samples = []
        for i in range(int(rate * duration)):
            t = i / rate
            env = math.exp(-t * (42 if kind == "move" else 13))
            noise = random.random() * 2.0 - 1.0
            if kind == "move":
                # Muted wooden knock: brief noise transient with a low resonant body.
                v = env * (0.46 * noise * math.exp(-t * 28)
                           + 0.55 * math.sin(2 * math.pi * 185 * t)
                           + 0.20 * math.sin(2 * math.pi * 410 * t))
            elif kind == "check":
                v = env * (0.36 * math.sin(2 * math.pi * 740 * t)
                           + 0.25 * math.sin(2 * math.pi * 990 * t))
            else:
                v = env * (0.35 * math.sin(2 * math.pi * 520 * t)
                           + 0.30 * math.sin(2 * math.pi * 660 * t))
            samples.append(max(-1.0, min(1.0, v * 0.65)))
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate)
            wav.writeframes(b"".join(struct.pack("<h", int(v * 32767)) for v in samples))
        return str(path)

    def play_sound(self, kind):
        # Use a soft wood-like piece sound instead of the harsh system beep.
        try:
            kind = kind if kind in ("move", "check", "mate") else "move"
            path = self._make_chess_sound(kind)
            if sys.platform == "win32":
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif sys.platform == "darwin":
                subprocess.Popen(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                player = shutil.which("paplay") or shutil.which("aplay")
                if player:
                    subprocess.Popen([player, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            # Audio is optional; never interrupt a chess move if playback is unavailable.
            pass

    def persist(self):
        self.p["fen"]=self.board.fen(); self.p["mode"]=self.mode; self.p["level"]=self.level
        self.p["rated_active"]=self.rating_game; save(self.p)
    def finish(self):
        if getattr(self, "_finish_shown", False):
            return
        self._finish_shown = True
        rated = self.rating_game and self.mode == "Рейтинг"
        delta = 0
        level_elo = self.p.setdefault("level_elo", {str(i): 0 for i in range(1, 9)})
        for i in range(1, 9):
            level_elo.setdefault(str(i), 0)

        if self.board.is_checkmate():
            player_won = not self.board.turn  # Black to move means White delivered mate.
            if player_won:
                title, headline = "ПОБЕДА!", "♕ Ты поставил мат!"
            else:
                title, headline = "ПАРТИЯ ОКОНЧЕНА", "Бот поставил мат."
            if rated:
                self.p["games"] += 1
                if player_won:
                    # Start at +20; as total ELO rises, the reward gradually
                    # decreases, but never below +5.
                    current_elo = sum(int(level_elo.get(str(i), 0)) for i in range(1, 9))
                    reward = max(5, 20 - current_elo // 100)
                    delta = reward
                    self.p["wins"] += 1
                    level_elo[str(self.level)] = int(level_elo.get(str(self.level), 0)) + reward
                else:
                    # Losses start at -1 and grow slowly with rating; never
                    # remove more points than this level currently has.
                    current_elo = sum(int(level_elo.get(str(i), 0)) for i in range(1, 9))
                    penalty = min(current_elo, 1 + current_elo // 200)
                    remaining = penalty
                    # Deduct from the played level first, then other levels if
                    # that level has no points, so a loss still counts globally.
                    order = [self.level] + [i for i in range(1, 9) if i != self.level]
                    for level_id in order:
                        key = str(level_id)
                        available = max(0, int(level_elo.get(key, 0)))
                        take = min(available, remaining)
                        level_elo[key] = available - take
                        remaining -= take
                        if remaining <= 0:
                            break
                    delta = -penalty
                    self.p["losses"] += 1
            elif player_won:
                headline = "♕ Мат! Ты победил бота."
            else:
                headline = "Мат от бота. Попробуй ещё раз!"
        else:
            title, headline = "НИЧЬЯ", "Партия закончилась вничью."
            if rated:
                self.p["games"] += 1
                self.p["draws"] += 1

        self.p["elo"] = sum(int(level_elo.get(str(i), 0)) for i in range(1, 9))
        self.rating_game = False
        self.p["rated_active"] = False
        self.p["fen"] = ""
        save(self.p)
        self.refresh()
        self._show_result_board(title, headline, delta, rated)
        self._finish_shown = False

    def _show_result_board(self, title, headline, delta, rated):
        # Custom dark result panel shown when a game ends.
        win = title == "ПОБЕДА!" or "победил бота" in headline.lower()
        accent = "#46d69a" if win else ("#f2c96d" if title == "НИЧЬЯ" else "#ff7a86")
        dialog = tk.Toplevel(self.root)
        dialog.title(title); dialog.configure(bg=BG); dialog.resizable(False, False)
        dialog.transient(self.root); dialog.grab_set()
        panel = tk.Frame(dialog, bg=PANEL, padx=34, pady=28,
                         highlightthickness=1, highlightbackground="#34465d")
        panel.pack(fill="both", expand=True, padx=2, pady=2)
        tk.Label(panel, text="♟", bg=PANEL, fg=accent,
                 font=("Segoe UI Symbol", 35, "bold")).pack()
        tk.Label(panel, text=title, bg=PANEL, fg=accent,
                 font=("Segoe UI", 20, "bold")).pack(pady=(3, 8))
        tk.Label(panel, text=headline, bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 12, "bold"), wraplength=360).pack(pady=(0, 12))
        tk.Label(panel, text=f"Уровень бота: {self.level} / 8",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).pack(pady=2)
        if rated:
            delta_text = f"{delta:+d} ELO" if delta else "0 ELO"
            tk.Label(panel, text=f"Изменение рейтинга: {delta_text}",
                     bg=PANEL, fg=accent, font=("Segoe UI", 12, "bold")).pack(pady=3)
            tk.Label(panel, text=f"Твой рейтинг: {self.p.get('elo', 0)} ELO",
                     bg=PANEL, fg=TEXT, font=("Segoe UI", 11)).pack(pady=(0, 10))
            if delta > 0:
                tk.Label(panel, text="Награда начинается с +20 и постепенно снижается до +5 по мере роста ELO.",
                         bg=PANEL, fg=MUTED, font=("Segoe UI", 9), wraplength=340).pack(pady=(0, 8))
            elif delta < 0:
                tk.Label(panel, text="Штраф за поражение постепенно растёт вместе с рейтингом.",
                         bg=PANEL, fg=MUTED, font=("Segoe UI", 9), wraplength=340).pack(pady=(0, 8))
        elif "победил бота" in headline.lower():
            tk.Label(panel, text="В режиме тренировки рейтинг не меняется.",
                     bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(pady=(0, 10))
        tk.Button(panel, text="Продолжить", command=dialog.destroy,
                  bg=ACCENT, fg="#101722", activebackground="#a3b8ff",
                  relief="flat", font=("Segoe UI", 10, "bold"),
                  padx=28, pady=8, cursor="hand2").pack(pady=(4, 0))
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        dialog.wait_window()

    def undo(self):
        if self.thinking or len(self.board.move_stack)<2: return
        self.board.pop(); self.board.pop(); self.persist(); self.refresh()
    def show_hint(self):
        if self.board.is_game_over() or not self.board.turn: return
        try: _,m=search(self.board.copy(),2,-10**9,10**9,time.monotonic()+1)
        except TimeoutError: m=None
        if m: self.hint.config(text=f"Подсказка: {chess.square_name(m.from_square)} → {chess.square_name(m.to_square)}")
    def flip(self):
        self.flipped=not self.flipped; self.draw()
    def close(self):
        if hasattr(self, "board") and self.screen == "board":
            self.persist()
        save(self.p)
        self.root.destroy()

def main():
    if chess is None:
        root=tk.Tk(); root.withdraw()
        messagebox.showerror("Не найдена библиотека","Один раз установи зависимость:\\n\\npy -m pip install python-chess\\n\\nЗатем снова запусти игру.")
        root.destroy(); return
    root=tk.Tk(); Game(root); root.mainloop()

if __name__=="__main__": main()
