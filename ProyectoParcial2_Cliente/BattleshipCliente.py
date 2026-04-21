import socket
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont
import time
import math

PUERTO = 5000

# ─── Paleta ───────────────────────────────────────────────────────────────────
BG_DARK      = "#050e0e"
BG_PANEL     = "#081818"
GRID_COLOR   = "#0a2a2a"
ACCENT       = "#00ff99"
ACCENT_DIM   = "#007744"
TEXT_MAIN    = "#c8ffe8"
TEXT_DIM     = "#3a7a5a"
WARNING      = "#ff6633"
BORDER       = "#0d3d2d"
BTN_HOVER    = "#00cc77"
HIT_COLOR    = "#ff4444"
MISS_COLOR   = "#1a4a6a"
SHIP_HIT     = "#cc2222"

CELL  = 36
COLS  = "ABCDEFGHIJ"
ROWS  = list(range(1, 11))

BARCOS = [
    ("Portaaviones", 5, "#00ffcc"),
    ("Acorazado",    4, "#00ddaa"),
    ("Crucero",      3, "#00bb88"),
    ("Submarino",    3, "#009966"),
    ("Destructor",   2, "#007744"),
]

EQUIPO = {
    "materia":   "CÓMPUTO DISTRIBUIDO",
    "profesor":  "Dr. Juan Carlos López Pimentel",
    "integrantes": [
        "Kenzo Matoo López",
        "Jetzuvely Del Carmen González Gutiérrez",
    ],
}


# ─── Red ──────────────────────────────────────────────────────────────────────
def recibir_msg(sock):
    msg = b""
    while True:
        c = sock.recv(1)
        if not c:
            raise ConnectionError("Servidor cerró la conexión.")
        if c == b"\n":
            break
        msg += c
    return msg.decode("utf-8")

def enviar_msg(sock, texto):
    sock.sendall((texto + "\n").encode("utf-8"))


# ══════════════════════════════════════════════════════════════════════════════
class BattleshipClient(tk.Tk):

    def __init__(self, host):
        super().__init__()
        self.host        = host
        self.sock        = None
        self.radar_angle = 0
        self.player_num  = None

        # ── Evento para sincronizar el clic de "INICIAR PARTIDA" con el hilo de red
        self._evento_listo    = threading.Event()
        # ── Evento para sincronizar el envío de barcos con el hilo de red
        self._evento_barcos   = threading.Event()
        self._payload_barcos  = None   # string con las coords a enviar

        self.title("BATTLESHIP — Sistema de Combate Naval")
        self.configure(bg=BG_DARK)
        self.geometry("700x620")
        self.resizable(False, False)

        self.fn_title  = tkfont.Font(family="Courier New", size=18, weight="bold")
        self.fn_mono   = tkfont.Font(family="Courier New", size=11)
        self.fn_small  = tkfont.Font(family="Courier New", size=9)
        self.fn_status = tkfont.Font(family="Courier New", size=10, weight="bold")
        self.fn_rules  = tkfont.Font(family="Courier New", size=10)
        self.fn_btn    = tkfont.Font(family="Courier New", size=12, weight="bold")
        self.fn_cell   = tkfont.Font(family="Courier New", size=8, weight="bold")
        self.fn_auth   = tkfont.Font(family="Courier New", size=10)
        self.fn_about  = tkfont.Font(family="Courier New", size=8)

        self._build_ui()
        self._animate_radar()
        threading.Thread(target=self._conectar, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # UI PRINCIPAL
    # ══════════════════════════════════════════════════════════════════════════
    def _build_ui(self):
        header = tk.Frame(self, bg=BG_DARK)
        header.pack(fill="x", padx=20, pady=(18, 0))
        tk.Label(header, text="⚓  BATTLESHIP  ⚓",
                 font=self.fn_title, fg=ACCENT, bg=BG_DARK).pack(side="left")
        self.lbl_conn = tk.Label(header, text="● DESCONECTADO",
                                 font=self.fn_status, fg=WARNING, bg=BG_DARK)
        self.lbl_conn.pack(side="right", padx=4)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=20, pady=8)

        self.main_frame = tk.Frame(self, bg=BG_DARK)
        self.main_frame.pack(fill="both", expand=True, padx=20)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=20, pady=(8, 0))
        footer = tk.Frame(self, bg=BG_DARK)
        footer.pack(fill="x", padx=20, pady=6)
        self.lbl_status = tk.Label(footer, text=f"Conectando a {self.host}:{PUERTO}...",
                                   font=self.fn_small, fg=TEXT_DIM, bg=BG_DARK, anchor="w")
        self.lbl_status.pack(side="left")
        tk.Label(footer, text="SISTEMA v1.0",
                 font=self.fn_small, fg=GRID_COLOR, bg=BG_DARK).pack(side="right")

        self._build_login()
        self._build_lobby()
        self._build_reglas()
        self._build_colocacion()
        self._build_combate()

        self.frame_login.pack(fill="both", expand=True)

    # ══════════════════════════════════════════════════════════════════════════
    # PANTALLA 0 — LOGIN / REGISTRO
    # ══════════════════════════════════════════════════════════════════════════
    def _build_login(self):
        self.frame_login = tk.Frame(self.main_frame, bg=BG_DARK)

        center = tk.Frame(self.frame_login, bg=BG_DARK)
        center.pack(expand=True, fill="both")

        form_wrap = tk.Frame(center, bg=BG_PANEL,
                             highlightthickness=1, highlightbackground=BORDER)
        form_wrap.pack(side="left", fill="both", expand=True, padx=(0, 12), pady=4)

        tk.Label(form_wrap, text="— ACCESO AL SISTEMA —",
                 font=self.fn_small, fg=ACCENT_DIM, bg=BG_PANEL
                 ).pack(anchor="w", padx=14, pady=(12, 6))

        mode_frame = tk.Frame(form_wrap, bg=BG_PANEL)
        mode_frame.pack(fill="x", padx=14, pady=(0, 10))

        self._modo_auth = tk.StringVar(value="LOGIN")

        tk.Radiobutton(mode_frame, text="Iniciar sesión", variable=self._modo_auth,
                       value="LOGIN", font=self.fn_auth, fg=TEXT_MAIN, bg=BG_PANEL,
                       selectcolor=BG_DARK, activebackground=BG_PANEL, activeforeground=ACCENT,
                       command=self._on_modo_cambio).pack(side="left", padx=(0, 20))

        tk.Radiobutton(mode_frame, text="Registrarse", variable=self._modo_auth,
                       value="REGISTRO", font=self.fn_auth, fg=TEXT_MAIN, bg=BG_PANEL,
                       selectcolor=BG_DARK, activebackground=BG_PANEL, activeforeground=ACCENT,
                       command=self._on_modo_cambio).pack(side="left")

        tk.Frame(form_wrap, bg=BORDER, height=1).pack(fill="x", padx=14, pady=6)

        tk.Label(form_wrap, text="Usuario:", font=self.fn_auth,
                 fg=TEXT_DIM, bg=BG_PANEL).pack(anchor="w", padx=14)
        self.entry_usuario = tk.Entry(
            form_wrap, font=self.fn_auth, bg=BG_DARK, fg=TEXT_MAIN,
            insertbackground=ACCENT, relief="flat",
            highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
        self.entry_usuario.pack(fill="x", padx=14, pady=(2, 10), ipady=6)

        tk.Label(form_wrap, text="Contraseña:", font=self.fn_auth,
                 fg=TEXT_DIM, bg=BG_PANEL).pack(anchor="w", padx=14)
        self.entry_pass = tk.Entry(
            form_wrap, font=self.fn_auth, bg=BG_DARK, fg=TEXT_MAIN,
            show="*", insertbackground=ACCENT, relief="flat",
            highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
        self.entry_pass.pack(fill="x", padx=14, pady=(2, 10), ipady=6)
        self.entry_pass.bind("<Return>", lambda e: self._on_auth())

        self.lbl_auth_msg = tk.Label(
            form_wrap, text="", font=self.fn_small,
            fg=WARNING, bg=BG_PANEL, wraplength=280, justify="left")
        self.lbl_auth_msg.pack(anchor="w", padx=14, pady=(0, 6))

        tk.Frame(form_wrap, bg=BORDER, height=1).pack(fill="x", padx=14, pady=4)

        self.btn_auth = tk.Button(
            form_wrap, text="▶  INICIAR SESIÓN",
            font=self.fn_btn, fg=BG_DARK, bg=ACCENT,
            activeforeground=BG_DARK, activebackground=BTN_HOVER,
            bd=0, relief="flat", padx=20, pady=10,
            cursor="hand2", command=self._on_auth)
        self.btn_auth.pack(padx=14, pady=(6, 14))
        self.btn_auth.bind("<Enter>", lambda e: self.btn_auth.config(bg=BTN_HOVER))
        self.btn_auth.bind("<Leave>", lambda e: self.btn_auth.config(bg=ACCENT))

        right = tk.Frame(center, bg=BG_DARK, width=200)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        tk.Label(right, text="— RADAR —",
                 font=self.fn_small, fg=ACCENT_DIM, bg=BG_DARK).pack(pady=(4, 4))
        self.radar_canvas = tk.Canvas(right, width=180, height=180,
                                      bg=BG_DARK, bd=0, highlightthickness=0)
        self.radar_canvas.pack()
        self._build_radar()

        tk.Frame(right, bg=BORDER, height=1).pack(fill="x", pady=8)

        about_frame = tk.Frame(right, bg=BG_PANEL,
                               highlightthickness=1, highlightbackground=BORDER)
        about_frame.pack(fill="x", padx=2)
        tk.Label(about_frame, text="— ACERCA DE —",
                 font=self.fn_small, fg=ACCENT_DIM, bg=BG_PANEL
                 ).pack(anchor="w", padx=8, pady=(6, 2))
        tk.Label(about_frame, text=EQUIPO["materia"],
                 font=tkfont.Font(family="Courier New", size=8, weight="bold"),
                 fg=ACCENT, bg=BG_PANEL, wraplength=180, justify="left"
                 ).pack(anchor="w", padx=8, pady=(0, 2))
        tk.Label(about_frame, text=EQUIPO["profesor"],
                 font=self.fn_about, fg=TEXT_DIM, bg=BG_PANEL,
                 wraplength=180, justify="left"
                 ).pack(anchor="w", padx=8, pady=(0, 6))
        tk.Frame(about_frame, bg=BORDER, height=1).pack(fill="x", padx=8)
        tk.Label(about_frame, text="Integrantes:",
                 font=tkfont.Font(family="Courier New", size=8, weight="bold"),
                 fg=TEXT_DIM, bg=BG_PANEL).pack(anchor="w", padx=8, pady=(4, 2))
        for nombre in EQUIPO["integrantes"]:
            tk.Label(about_frame, text=f"  {nombre}",
                     font=self.fn_about, fg=TEXT_MAIN, bg=BG_PANEL,
                     wraplength=180, justify="left").pack(anchor="w", padx=8)
        tk.Frame(about_frame, bg=BORDER, height=1).pack(fill="x", padx=8, pady=(6, 0))
        tk.Label(about_frame, text="Battleship v1.0",
                 font=self.fn_about, fg=GRID_COLOR, bg=BG_PANEL
                 ).pack(anchor="w", padx=8, pady=(2, 6))

    def _on_modo_cambio(self):
        modo = self._modo_auth.get()
        self.btn_auth.config(text="▶  INICIAR SESIÓN" if modo == "LOGIN" else "▶  REGISTRARSE")
        self.lbl_auth_msg.config(text="", fg=WARNING)

    def _on_auth(self):
        usuario   = self.entry_usuario.get().strip()
        contrasena = self.entry_pass.get().strip()

        if not usuario or not contrasena:
            self.lbl_auth_msg.config(text="⚠ Completa usuario y contraseña", fg=WARNING)
            return
        if not self.sock:
            self.lbl_auth_msg.config(text="⚠ Sin conexión con el servidor", fg=WARNING)
            return

        modo = self._modo_auth.get()
        self.btn_auth.config(state="disabled", text="Enviando...")
        self.lbl_auth_msg.config(text="", fg=WARNING)

        def _enviar():
            try:
                enviar_msg(self.sock, f"{modo}:{usuario}:{contrasena}")
                resp = recibir_msg(self.sock)

                if resp == "AUTH_OK":
                    self.after(0, lambda: self.lbl_auth_msg.config(
                        text="Acceso concedido", fg=ACCENT))
                    # Mismo hilo — no hay race condition
                    self._flujo_post_auth()

                elif resp == "REGISTRO_OK":
                    self.after(0, lambda: self.lbl_auth_msg.config(
                        text="Usuario registrado. Ahora inicia sesión.", fg=ACCENT))
                    self.after(0, lambda: self._modo_auth.set("LOGIN"))
                    self.after(0, self._on_modo_cambio)
                    self.after(0, lambda: self.btn_auth.config(
                        state="normal", text="▶  INICIAR SESIÓN"))

                elif resp.startswith("AUTH_FAIL:") or resp.startswith("REGISTRO_FAIL:"):
                    razon = resp.split(":", 1)[1] if ":" in resp else resp
                    self.after(0, lambda r=razon: self.lbl_auth_msg.config(
                        text=f"✗ {r}", fg=WARNING))
                    self.after(0, lambda: self.btn_auth.config(
                        state="normal",
                        text="▶  INICIAR SESIÓN" if self._modo_auth.get() == "LOGIN"
                             else "▶  REGISTRARSE"))
                else:
                    self.after(0, lambda: self.lbl_auth_msg.config(
                        text=f"Respuesta inesperada: {resp}", fg=WARNING))
                    self.after(0, lambda: self.btn_auth.config(
                        state="normal",
                        text="▶  INICIAR SESIÓN" if self._modo_auth.get() == "LOGIN"
                             else "▶  REGISTRARSE"))

            except ConnectionError as e:
                self.after(0, lambda: self.lbl_auth_msg.config(text=str(e), fg=WARNING))
                self.after(0, lambda: self.btn_auth.config(
                    state="normal",
                    text="▶  INICIAR SESIÓN" if self._modo_auth.get() == "LOGIN"
                         else "▶  REGISTRARSE"))

        threading.Thread(target=_enviar, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # PANTALLA 1 — LOBBY
    # ══════════════════════════════════════════════════════════════════════════
    def _build_lobby(self):
        self.frame_lobby = tk.Frame(self.main_frame, bg=BG_DARK)
        log_frame = tk.Frame(self.frame_lobby, bg=BG_PANEL,
                             highlightthickness=1, highlightbackground=BORDER)
        log_frame.pack(side="left", fill="both", expand=True, padx=(0, 12))
        tk.Label(log_frame, text="— COMUNICACIONES —",
                 font=self.fn_small, fg=ACCENT_DIM, bg=BG_PANEL
                 ).pack(anchor="w", padx=10, pady=(8, 2))
        self.log_text = tk.Text(
            log_frame, bg=BG_PANEL, fg=TEXT_MAIN, font=self.fn_mono,
            bd=0, relief="flat", state="disabled", wrap="word",
            height=16, width=44, padx=10, pady=6, spacing1=3, spacing3=3)
        self.log_text.pack(fill="both", expand=True, padx=2, pady=(0, 6))
        self.log_text.tag_config("server", foreground=ACCENT)
        self.log_text.tag_config("info",   foreground=TEXT_DIM)
        self.log_text.tag_config("warn",   foreground=WARNING)
        self.log_text.tag_config("start",  foreground="#ffdd00")

        right = tk.Frame(self.frame_lobby, bg=BG_DARK, width=200)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        tk.Label(right, text="JUGADOR",
                 font=self.fn_small, fg=TEXT_DIM, bg=BG_DARK).pack(pady=(4, 0))
        self.lbl_player = tk.Label(right, text="---",
                                   font=tkfont.Font(family="Courier New", size=28, weight="bold"),
                                   fg=TEXT_DIM, bg=BG_DARK)
        self.lbl_player.pack(pady=4)
        self.lbl_role = tk.Label(right, text="", font=self.fn_small,
                                 fg=TEXT_DIM, bg=BG_DARK, wraplength=185, justify="center")
        self.lbl_role.pack(pady=2)

        tk.Frame(right, bg=BORDER, height=1).pack(fill="x", pady=8)

        about_frame = tk.Frame(right, bg=BG_PANEL,
                               highlightthickness=1, highlightbackground=BORDER)
        about_frame.pack(fill="x", padx=2)
        tk.Label(about_frame, text="— ACERCA DE —",
                 font=self.fn_small, fg=ACCENT_DIM, bg=BG_PANEL
                 ).pack(anchor="w", padx=8, pady=(6, 2))
        tk.Label(about_frame, text=EQUIPO["materia"],
                 font=tkfont.Font(family="Courier New", size=8, weight="bold"),
                 fg=ACCENT, bg=BG_PANEL, wraplength=185, justify="left"
                 ).pack(anchor="w", padx=8)
        tk.Label(about_frame, text=EQUIPO["profesor"],
                 font=self.fn_about, fg=TEXT_DIM, bg=BG_PANEL,
                 wraplength=185, justify="left"
                 ).pack(anchor="w", padx=8, pady=(0, 4))
        tk.Frame(about_frame, bg=BORDER, height=1).pack(fill="x", padx=8)
        for nombre in EQUIPO["integrantes"]:
            tk.Label(about_frame, text=f"  {nombre}",
                     font=self.fn_about, fg=TEXT_MAIN, bg=BG_PANEL,
                     wraplength=185, justify="left").pack(anchor="w", padx=8)
        tk.Label(about_frame, text="", bg=BG_PANEL).pack()

    # ══════════════════════════════════════════════════════════════════════════
    # PANTALLA 2 — REGLAS
    # ══════════════════════════════════════════════════════════════════════════
    def _build_reglas(self):
        self.frame_reglas = tk.Frame(self.main_frame, bg=BG_DARK)
        tk.Label(self.frame_reglas, text="— REGLAS DE COMBATE —",
                 font=tkfont.Font(family="Courier New", size=13, weight="bold"),
                 fg=ACCENT, bg=BG_DARK).pack(pady=(10, 6))
        rules_box = tk.Frame(self.frame_reglas, bg=BG_PANEL,
                             highlightthickness=1, highlightbackground=BORDER)
        rules_box.pack(fill="both", expand=True, pady=(0, 10))
        self.txt_reglas = tk.Text(rules_box, bg=BG_PANEL, fg=TEXT_MAIN,
                                  font=self.fn_rules, bd=0, relief="flat",
                                  state="disabled", wrap="word",
                                  padx=16, pady=12, spacing1=4, spacing3=4, height=14)
        self.txt_reglas.pack(fill="both", expand=True, padx=2, pady=2)
        self.txt_reglas.tag_config("titulo", foreground=ACCENT,
                                   font=tkfont.Font(family="Courier New", size=11, weight="bold"))
        self.txt_reglas.tag_config("regla", foreground=TEXT_MAIN)

        btn_f = tk.Frame(self.frame_reglas, bg=BG_DARK)
        btn_f.pack(pady=(4, 8))
        self.btn_inicio = tk.Button(btn_f, text="▶  INICIAR PARTIDA",
                                    font=self.fn_btn, fg=BG_DARK, bg=ACCENT,
                                    activeforeground=BG_DARK, activebackground=BTN_HOVER,
                                    bd=0, relief="flat", padx=28, pady=10,
                                    cursor="hand2", command=self._on_inicio)
        self.btn_inicio.pack()
        self.btn_inicio.bind("<Enter>", lambda e: self.btn_inicio.config(bg=BTN_HOVER))
        self.btn_inicio.bind("<Leave>", lambda e: self.btn_inicio.config(bg=ACCENT))

    # ══════════════════════════════════════════════════════════════════════════
    # PANTALLA 3 — COLOCACIÓN
    # ══════════════════════════════════════════════════════════════════════════
    def _build_colocacion(self):
        self.frame_col = tk.Frame(self.main_frame, bg=BG_DARK)
        self._barcos_restantes = list(BARCOS)
        self._barco_actual     = None
        self._orientacion      = "H"
        self._celdas_ocupadas  = {}
        self._barcos_colocados = []

        top = tk.Frame(self.frame_col, bg=BG_DARK)
        top.pack(fill="x", pady=(6, 4))
        tk.Label(top, text="— COLOCA TUS BARCOS —",
                 font=tkfont.Font(family="Courier New", size=13, weight="bold"),
                 fg=ACCENT, bg=BG_DARK).pack(side="left")

        body = tk.Frame(self.frame_col, bg=BG_DARK)
        body.pack(fill="both", expand=True)

        board_wrap = tk.Frame(body, bg=BG_PANEL,
                              highlightthickness=1, highlightbackground=BORDER)
        board_wrap.pack(side="left", padx=(0, 12), pady=4)
        self.board_canvas = tk.Canvas(board_wrap,
                                      width=CELL*10+CELL+2, height=CELL*10+CELL+2,
                                      bg=BG_PANEL, bd=0, highlightthickness=0)
        self.board_canvas.pack(padx=6, pady=6)
        self._draw_board_col()
        self.board_canvas.bind("<Motion>",   self._on_hover)
        self.board_canvas.bind("<Leave>",    self._on_leave)
        self.board_canvas.bind("<Button-1>", self._on_click)
        self.board_canvas.bind("<Button-3>", self._on_rotate)

        side = tk.Frame(body, bg=BG_DARK, width=185)
        side.pack(side="right", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="— FLOTA —",
                 font=self.fn_small, fg=ACCENT_DIM, bg=BG_DARK).pack(pady=(4, 6))
        self.fleet_frame = tk.Frame(side, bg=BG_DARK)
        self.fleet_frame.pack(fill="x")
        tk.Frame(side, bg=BORDER, height=1).pack(fill="x", pady=8)
        self.btn_rotar = tk.Button(side, text="↺  ROTAR (H→V)",
                                   font=self.fn_small, fg=BG_DARK, bg=ACCENT_DIM,
                                   activeforeground=BG_DARK, activebackground=ACCENT,
                                   bd=0, relief="flat", padx=10, pady=6, cursor="hand2",
                                   command=self._toggle_orientacion)
        self.btn_rotar.pack(fill="x", padx=6)
        tk.Frame(side, bg=BORDER, height=1).pack(fill="x", pady=8)
        self.lbl_instruccion = tk.Label(side, text="Selecciona un barco\ny haz clic",
                                        font=self.fn_small, fg=TEXT_DIM, bg=BG_DARK,
                                        justify="center", wraplength=160)
        self.lbl_instruccion.pack(pady=4)
        tk.Frame(side, bg=BORDER, height=1).pack(fill="x", pady=8)
        self.btn_confirmar = tk.Button(side, text="✔  CONFIRMAR",
                                       font=self.fn_btn, fg=BG_DARK, bg=GRID_COLOR,
                                       activeforeground=BG_DARK, activebackground=BTN_HOVER,
                                       bd=0, relief="flat", padx=10, pady=10, cursor="hand2",
                                       state="disabled", command=self._confirmar_colocacion)
        self.btn_confirmar.pack(fill="x", padx=6, pady=4)

    # ══════════════════════════════════════════════════════════════════════════
    # PANTALLA 4 — COMBATE
    # ══════════════════════════════════════════════════════════════════════════
    def _build_combate(self):
        self.frame_combate = tk.Frame(self.main_frame, bg=BG_DARK)
        self._mi_turno        = False
        self._celdas_atacadas = set()

        top = tk.Frame(self.frame_combate, bg=BG_DARK)
        top.pack(fill="x", pady=(4, 4))
        tk.Label(top, text="— COMBATE NAVAL —",
                 font=tkfont.Font(family="Courier New", size=13, weight="bold"),
                 fg=ACCENT, bg=BG_DARK).pack(side="left")
        self.lbl_turno = tk.Label(top, text="Esperando...",
                                  font=self.fn_status, fg=TEXT_DIM, bg=BG_DARK)
        self.lbl_turno.pack(side="right")

        boards = tk.Frame(self.frame_combate, bg=BG_DARK)
        boards.pack(fill="x")

        left_wrap = tk.Frame(boards, bg=BG_DARK)
        left_wrap.pack(side="left", padx=(0, 10))
        tk.Label(left_wrap, text="TABLERO RIVAL  (haz clic para atacar)",
                 font=self.fn_small, fg=ACCENT_DIM, bg=BG_DARK).pack(pady=(0, 2))
        atk_box = tk.Frame(left_wrap, bg=BG_PANEL,
                           highlightthickness=1, highlightbackground=BORDER)
        atk_box.pack()
        self.atk_canvas = tk.Canvas(atk_box,
                                    width=CELL*10+CELL+2, height=CELL*10+CELL+2,
                                    bg=BG_PANEL, bd=0, highlightthickness=0)
        self.atk_canvas.pack(padx=4, pady=4)
        self.atk_canvas.bind("<Button-1>", self._on_ataque_click)
        self.atk_canvas.bind("<Motion>",   self._on_ataque_hover)
        self.atk_canvas.bind("<Leave>",    self._on_ataque_leave)

        right_wrap = tk.Frame(boards, bg=BG_DARK)
        right_wrap.pack(side="left")
        tk.Label(right_wrap, text="MI TABLERO",
                 font=self.fn_small, fg=ACCENT_DIM, bg=BG_DARK).pack(pady=(0, 2))
        def_box = tk.Frame(right_wrap, bg=BG_PANEL,
                           highlightthickness=1, highlightbackground=BORDER)
        def_box.pack()
        self.def_canvas = tk.Canvas(def_box,
                                    width=CELL*10+CELL+2, height=CELL*10+CELL+2,
                                    bg=BG_PANEL, bd=0, highlightthickness=0)
        self.def_canvas.pack(padx=4, pady=4)

        log_box = tk.Frame(self.frame_combate, bg=BG_PANEL,
                           highlightthickness=1, highlightbackground=BORDER)
        log_box.pack(fill="x", pady=(6, 0))
        tk.Label(log_box, text="— BITÁCORA —",
                 font=self.fn_small, fg=ACCENT_DIM, bg=BG_PANEL
                 ).pack(anchor="w", padx=8, pady=(4, 0))
        self.combat_log = tk.Text(log_box, bg=BG_PANEL, fg=TEXT_MAIN,
                                  font=self.fn_small, bd=0, relief="flat",
                                  state="disabled", wrap="word", height=4,
                                  padx=8, pady=4, spacing1=2)
        self.combat_log.pack(fill="x", padx=2, pady=(0, 4))
        self.combat_log.tag_config("hit",   foreground="#ff4444")
        self.combat_log.tag_config("miss",  foreground="#4488cc")
        self.combat_log.tag_config("rival", foreground=WARNING)
        self.combat_log.tag_config("win",   foreground=ACCENT)
        self.combat_log.tag_config("lose",  foreground=WARNING)
        self.combat_log.tag_config("info",  foreground=TEXT_DIM)

        self._atk_estado = {}
        self._def_estado = {}

    # ══════════════════════════════════════════════════════════════════════════
    # RADAR
    # ══════════════════════════════════════════════════════════════════════════
    def _build_radar(self):
        cx, cy, r = 90, 90, 78
        c = self.radar_canvas
        for i in range(1, 5):
            ri = r * i // 4
            c.create_oval(cx-ri, cy-ri, cx+ri, cy+ri, outline=GRID_COLOR, width=1)
        c.create_line(cx-r, cy, cx+r, cy, fill=GRID_COLOR, width=1)
        c.create_line(cx, cy-r, cx, cy+r, fill=GRID_COLOR, width=1)
        self.radar_line = c.create_line(cx, cy, cx+r, cy, fill=ACCENT, width=2)
        c.create_oval(cx-4, cy-4, cx+4, cy+4, fill=ACCENT, outline="")
        self.radar_cx = cx; self.radar_cy = cy; self.radar_r = r

    def _animate_radar(self):
        self.radar_angle = (self.radar_angle + 2) % 360
        a = math.radians(self.radar_angle)
        cx, cy, r = self.radar_cx, self.radar_cy, self.radar_r
        self.radar_canvas.coords(self.radar_line, cx, cy,
                                 cx + r*math.cos(a), cy - r*math.sin(a))
        self.radar_canvas.delete("sweep")
        for i in range(1, 30):
            ai = math.radians(self.radar_angle - i*2)
            alpha = max(0, 1 - i/30)
            g = int(alpha*200); b = int(alpha*60)
            self.radar_canvas.create_line(
                cx, cy, cx+r*math.cos(ai), cy-r*math.sin(ai),
                fill=f"#00{g:02x}{b:02x}", width=1, tags="sweep")
        self.after(20, self._animate_radar)

    # ══════════════════════════════════════════════════════════════════════════
    # TABLERO DE COLOCACIÓN
    # ══════════════════════════════════════════════════════════════════════════
    def _draw_board_col(self):
        c = self.board_canvas; c.delete("all"); off = CELL
        for i, letra in enumerate(COLS):
            c.create_text(off + i*CELL + CELL//2, CELL//2, text=letra,
                          fill=TEXT_DIM, font=self.fn_cell)
        for j, num in enumerate(ROWS):
            c.create_text(CELL//2, off + j*CELL + CELL//2, text=str(num),
                          fill=TEXT_DIM, font=self.fn_cell)
        for col in range(10):
            for row in range(10):
                coord = f"{COLS[col]}{ROWS[row]}"
                x1 = off + col*CELL; y1 = off + row*CELL
                fill = self._celdas_ocupadas.get(coord, BG_PANEL)
                c.create_rectangle(x1, y1, x1+CELL, y1+CELL,
                                   fill=fill, outline=GRID_COLOR, width=1)

    def _pixel_a_coord(self, x, y):
        col = (x - CELL) // CELL; row = (y - CELL) // CELL
        return (col, row) if 0 <= col < 10 and 0 <= row < 10 else None

    def _celdas_de_barco(self, col, row, tamaño, ori):
        celdas = []
        for i in range(tamaño):
            c, r = (col+i, row) if ori == "H" else (col, row+i)
            if c >= 10 or r >= 10: return []
            celdas.append(f"{COLS[c]}{ROWS[r]}")
        return celdas

    def _celdas_validas(self, celdas):
        return all(c not in self._celdas_ocupadas for c in celdas)

    def _on_hover(self, event):
        if not self._barco_actual: return
        pos = self._pixel_a_coord(event.x, event.y)
        self._draw_board_col()
        if pos is None: return
        col, row = pos
        _, tamaño, color = self._barco_actual
        celdas = self._celdas_de_barco(col, row, tamaño, self._orientacion)
        valido = self._celdas_validas(celdas)
        for coord in celdas:
            ci = COLS.index(coord[0]); ri = ROWS.index(int(coord[1:]))
            x1 = CELL + ci*CELL; y1 = CELL + ri*CELL
            self.board_canvas.create_rectangle(x1, y1, x1+CELL, y1+CELL,
                                               fill=color if valido else WARNING,
                                               outline=GRID_COLOR, width=1)

    def _on_leave(self, event): self._draw_board_col()

    def _on_click(self, event):
        if not self._barco_actual: return
        pos = self._pixel_a_coord(event.x, event.y)
        if pos is None: return
        col, row = pos
        nombre, tamaño, color = self._barco_actual
        celdas = self._celdas_de_barco(col, row, tamaño, self._orientacion)
        if not celdas or not self._celdas_validas(celdas):
            self._flash_instruccion("⚠ Posición inválida"); return
        for coord in celdas:
            self._celdas_ocupadas[coord] = color
        self._barcos_colocados.append(celdas)
        self._barcos_restantes.pop(0)
        self._barco_actual = None
        self._draw_board_col(); self._actualizar_flota()
        if not self._barcos_restantes:
            self.btn_confirmar.config(state="normal", bg=ACCENT)
            self.lbl_instruccion.config(text="¡Todos colocados!\nPresiona CONFIRMAR", fg=ACCENT)
        else:
            self._seleccionar_siguiente_barco()

    def _on_rotate(self, event): self._toggle_orientacion()

    def _toggle_orientacion(self):
        self._orientacion = "V" if self._orientacion == "H" else "H"
        self.btn_rotar.config(
            text=f"↺  ROTAR ({'H→V' if self._orientacion == 'H' else 'V→H'})")

    def _actualizar_flota(self):
        for w in self.fleet_frame.winfo_children(): w.destroy()
        colocados = len(self._barcos_colocados)
        for i, (nombre, tamaño, color) in enumerate(BARCOS):
            if i < colocados:
                fg, txt = ACCENT_DIM, f"✔ {nombre} ({'█'*tamaño})"
            elif i == colocados:
                fg, txt = color, f"▶ {nombre} ({'█'*tamaño})"
            else:
                fg, txt = TEXT_DIM, f"  {nombre} ({'░'*tamaño})"
            tk.Label(self.fleet_frame, text=txt, font=self.fn_small,
                     fg=fg, bg=BG_DARK, anchor="w").pack(fill="x", padx=6, pady=2)

    def _seleccionar_siguiente_barco(self):
        if self._barcos_restantes:
            self._barco_actual = self._barcos_restantes[0]
            nombre, tamaño, _ = self._barco_actual
            self.lbl_instruccion.config(
                text=f"Coloca:\n{nombre}\n(tamaño {tamaño})\n\nClic derecho = rotar",
                fg=TEXT_MAIN)
        self._actualizar_flota()

    def _flash_instruccion(self, texto):
        orig = self.lbl_instruccion.cget("text")
        self.lbl_instruccion.config(text=texto, fg=WARNING)
        self.after(1200, lambda: self.lbl_instruccion.config(text=orig, fg=TEXT_MAIN))

    def _confirmar_colocacion(self):
        """
        El botón CONFIRMAR ya no lanza un hilo nuevo.
        Solo arma el payload y dispara el evento para que el hilo de red lo recoja.
        """
        todas = []
        for barco in self._barcos_colocados:
            todas.extend(barco)
        self._payload_barcos = ",".join(todas)
        self.btn_confirmar.config(state="disabled", text="✔  ENVIANDO...")
        self.set_status("Enviando posiciones al servidor...")
        # Desbloquear el hilo de red que está esperando en _evento_barcos
        self._evento_barcos.set()

    # ══════════════════════════════════════════════════════════════════════════
    # TABLEROS DE COMBATE
    # ══════════════════════════════════════════════════════════════════════════
    def _draw_atk_board(self, hover_coord=None):
        c = self.atk_canvas; c.delete("all"); off = CELL
        for i, letra in enumerate(COLS):
            c.create_text(off + i*CELL + CELL//2, CELL//2, text=letra,
                          fill=TEXT_DIM, font=self.fn_cell)
        for j, num in enumerate(ROWS):
            c.create_text(CELL//2, off + j*CELL + CELL//2, text=str(num),
                          fill=TEXT_DIM, font=self.fn_cell)
        for col in range(10):
            for row in range(10):
                coord = f"{COLS[col]}{ROWS[row]}"
                x1 = off + col*CELL; y1 = off + row*CELL
                estado = self._atk_estado.get(coord)
                if estado == "hit":
                    fill, sym = HIT_COLOR, "✕"
                elif estado == "miss":
                    fill, sym = MISS_COLOR, "·"
                elif coord == hover_coord and self._mi_turno and coord not in self._celdas_atacadas:
                    fill, sym = "#1a3a2a", ""
                else:
                    fill, sym = BG_PANEL, ""
                c.create_rectangle(x1, y1, x1+CELL, y1+CELL,
                                   fill=fill, outline=GRID_COLOR, width=1)
                if sym:
                    c.create_text(x1+CELL//2, y1+CELL//2, text=sym,
                                  fill="#ffffff" if estado == "hit" else TEXT_DIM,
                                  font=self.fn_cell)

    def _draw_def_board(self):
        c = self.def_canvas; c.delete("all"); off = CELL
        for i, letra in enumerate(COLS):
            c.create_text(off + i*CELL + CELL//2, CELL//2, text=letra,
                          fill=TEXT_DIM, font=self.fn_cell)
        for j, num in enumerate(ROWS):
            c.create_text(CELL//2, off + j*CELL + CELL//2, text=str(num),
                          fill=TEXT_DIM, font=self.fn_cell)
        for col in range(10):
            for row in range(10):
                coord = f"{COLS[col]}{ROWS[row]}"
                x1 = off + col*CELL; y1 = off + row*CELL
                fill = self._celdas_ocupadas.get(coord, BG_PANEL)
                sym = ""
                estado_rec = self._def_estado.get(coord)
                if estado_rec == "hit":
                    fill = SHIP_HIT; sym = "✕"
                elif estado_rec == "miss":
                    fill = MISS_COLOR; sym = "·"
                c.create_rectangle(x1, y1, x1+CELL, y1+CELL,
                                   fill=fill, outline=GRID_COLOR, width=1)
                if sym:
                    c.create_text(x1+CELL//2, y1+CELL//2, text=sym,
                                  fill="#ffffff", font=self.fn_cell)

    def _on_ataque_hover(self, event):
        pos = self._pixel_a_coord(event.x, event.y)
        if pos and self._mi_turno:
            coord = f"{COLS[pos[0]]}{ROWS[pos[1]]}"
            if coord not in self._celdas_atacadas:
                self._draw_atk_board(hover_coord=coord); return
        self._draw_atk_board()

    def _on_ataque_leave(self, event): self._draw_atk_board()

    def _on_ataque_click(self, event):
        if not self._mi_turno: return
        pos = self._pixel_a_coord(event.x, event.y)
        if pos is None: return
        coord = f"{COLS[pos[0]]}{ROWS[pos[1]]}"
        if coord in self._celdas_atacadas: return
        self._mi_turno = False
        self._celdas_atacadas.add(coord)
        self._actualizar_turno_label(False)
        # Guardar coord y despertar al hilo de red
        self._coord_ataque_pendiente = coord
        self._evento_ataque.set()

    def _actualizar_turno_label(self, es_mi_turno):
        def _u():
            if es_mi_turno:
                self.lbl_turno.config(text="⚔  TU TURNO — ¡Ataca!", fg=ACCENT)
            else:
                self.lbl_turno.config(text="⏳  Turno del rival...", fg=TEXT_DIM)
        self.after(0, _u)

    def log_combat(self, texto, tag="info"):
        def _w():
            self.combat_log.config(state="normal")
            ts = time.strftime("%H:%M:%S")
            self.combat_log.insert("end", f"[{ts}] {texto}\n", tag)
            self.combat_log.see("end")
            self.combat_log.config(state="disabled")
        self.after(0, _w)

    # ══════════════════════════════════════════════════════════════════════════
    # LOOP DE COMBATE  (corre en el mismo hilo de red — sin hilos extra)
    # ══════════════════════════════════════════════════════════════════════════
    def _loop_combate(self):
        self._evento_ataque = threading.Event()
        try:
            while True:
                msg = recibir_msg(self.sock)

                if msg == "TURNO":
                    self._mi_turno = True
                    self._evento_ataque.clear()
                    self._actualizar_turno_label(True)
                    self.set_status("¡Tu turno! Haz clic en el tablero rival")
                    self.after(0, self._draw_atk_board)
                    # Esperar a que el usuario haga clic (sin bloquear el socket)
                    self._evento_ataque.wait()
                    coord = self._coord_ataque_pendiente
                    enviar_msg(self.sock, coord)

                elif msg.startswith("TOCADO|") or msg.startswith("AGUA|"):
                    partes   = msg.split("|")
                    resultado = partes[0]
                    coord     = partes[1] if len(partes) > 1 else "?"
                    if resultado == "TOCADO":
                        self._atk_estado[coord] = "hit"
                        self.log_combat(f"Tu ataque en {coord}: ¡TOCADO! 🎯", "hit")
                        self.set_status(f"¡TOCADO en {coord}!")
                    else:
                        self._atk_estado[coord] = "miss"
                        self.log_combat(f"Tu ataque en {coord}: Agua 💧", "miss")
                        self.set_status(f"Fallo en {coord}. Turno del rival.")
                    self.after(0, self._draw_atk_board)

                elif msg.startswith("RIVAL_ATACO|"):
                    partes    = msg.split("|")
                    coord     = partes[1] if len(partes) > 1 else "?"
                    resultado = partes[2] if len(partes) > 2 else "?"
                    if resultado == "TOCADO":
                        self._def_estado[coord] = "hit"
                        self.log_combat(f"Rival atacó {coord}: ¡TOCÓ uno de tus barcos! 💥", "rival")
                    else:
                        self._def_estado[coord] = "miss"
                        self.log_combat(f"Rival atacó {coord}: Falló el agua 🌊", "rival")
                    self.after(0, self._draw_def_board)

                elif msg == "GANASTE":
                    self.log_combat("🏆 ¡GANASTE! ¡Hundiste toda la flota enemiga!", "win")
                    self.set_status("¡¡VICTORIA!!")
                    self._mi_turno = False
                    self._mostrar_fin("¡VICTORIA! 🏆", ACCENT)
                    break

                elif msg == "PERDISTE":
                    self.log_combat("💀 Perdiste. El rival hundió toda tu flota.", "lose")
                    self.set_status("Derrota...")
                    self._mi_turno = False
                    self._mostrar_fin("DERROTA 💀", WARNING)
                    break

        except ConnectionError as e:
            self.log_combat(str(e), "info")

    def _mostrar_fin(self, texto, color):
        def _u():
            self.lbl_turno.config(text=texto, fg=color,
                                  font=tkfont.Font(family="Courier New", size=14, weight="bold"))
        self.after(0, _u)

    # ══════════════════════════════════════════════════════════════════════════
    # TRANSICIONES ENTRE PANTALLAS
    # ══════════════════════════════════════════════════════════════════════════
    def _mostrar_lobby(self):
        def _swap():
            self.frame_login.pack_forget()
            self.frame_lobby.pack(fill="both", expand=True)
            self.lbl_status.config(text="Autenticado. Esperando al rival...")
        self.after(0, _swap)

    def _mostrar_reglas(self, lineas):
        """Actualiza el texto de reglas y hace el swap de pantalla."""
        self.txt_reglas.config(state="normal")
        self.txt_reglas.delete("1.0", "end")
        for linea in lineas:
            tag = "titulo" if linea == lineas[0] else "regla"
            self.txt_reglas.insert("end", linea + ("\n\n" if tag == "titulo" else "\n"), tag)
        self.txt_reglas.config(state="disabled")
        def _swap():
            self.frame_lobby.pack_forget()
            self.frame_reglas.pack(fill="both", expand=True)
            self.lbl_status.config(text="Lee las reglas y presiona INICIAR PARTIDA")
        self.after(0, _swap)

    def _mostrar_colocacion(self):
        def _swap():
            self.frame_reglas.pack_forget()
            self.frame_col.pack(fill="both", expand=True)
            self.geometry("780x600")
            self.lbl_status.config(text="Coloca tus barcos en el tablero")
            self._seleccionar_siguiente_barco()
        self.after(0, _swap)

    def _mostrar_combate(self):
        def _swap():
            self.frame_col.pack_forget()
            self.frame_combate.pack(fill="both", expand=True)
            self.geometry("900x640")
            self.lbl_status.config(text="¡Combate iniciado!")
            self._draw_atk_board()
            self._draw_def_board()
        self.after(0, _swap)

    # ══════════════════════════════════════════════════════════════════════════
    # BOTÓN "INICIAR PARTIDA"
    # Antes lanzaba un hilo nuevo. Ahora solo dispara el evento para el hilo de red.
    # ══════════════════════════════════════════════════════════════════════════
    def _on_inicio(self):
        self.btn_inicio.config(state="disabled", text="▶  CARGANDO...")
        self._evento_listo.set()   # desbloquea el hilo de red en _flujo_post_auth

    # ══════════════════════════════════════════════════════════════════════════
    # HELPERS UI
    # ══════════════════════════════════════════════════════════════════════════
    def log(self, text, tag="info"):
        def _w():
            self.log_text.config(state="normal")
            self.log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n", tag)
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.after(0, _w)

    def set_status(self, text):
        self.after(0, lambda: self.lbl_status.config(text=text))

    def set_connection(self, connected):
        def _u():
            if connected:
                self.lbl_conn.config(text="● CONECTADO", fg=ACCENT)
            else:
                self.lbl_conn.config(text="● DESCONECTADO", fg=WARNING)
        self.after(0, _u)

    def set_player(self, num, role_text=""):
        def _u():
            self.lbl_player.config(text=str(num), fg=ACCENT)
            self.lbl_role.config(text=role_text, fg=TEXT_DIM)
        self.after(0, _u)

    # ══════════════════════════════════════════════════════════════════════════
    # RED — UN SOLO HILO MANEJA TODO EL PROTOCOLO DE PRINCIPIO A FIN
    # ══════════════════════════════════════════════════════════════════════════
    def _conectar(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, PUERTO))
        except Exception as e:
            self.after(0, lambda: self.lbl_auth_msg.config(
                text=f"Error al conectar: {e}", fg=WARNING))
            self.set_status("Error de conexión.")
            return

        self.set_connection(True)
        self.set_status(f"Conectado a {self.host}:{PUERTO} — Autentícate")

        try:
            msg = recibir_msg(self.sock)
            if msg != "AUTH_REQUERIDA":
                self.after(0, lambda: self.lbl_auth_msg.config(
                    text=f"Protocolo inesperado: {msg}", fg=WARNING))
                return
            # El hilo se detiene aquí. La UI toma el control.
            # Cuando el usuario presiona el botón, _on_auth lanza _enviar
            # en un hilo nuevo que continúa el flujo.
        except ConnectionError as e:
            self.after(0, lambda: self.lbl_auth_msg.config(text=str(e), fg=WARNING))
            self.set_connection(False)

    def _flujo_post_auth(self):
        """
        Corre en el hilo de _enviar (lanzado por _on_auth).
        Es el ÚNICO hilo que lee del socket desde aquí hasta el fin de la partida.
        Usa threading.Event para sincronizarse con la UI sin lanzar más hilos.
        """
        try:
            # ── 1) Bienvenida ──────────────────────────────────────────────
            msg = recibir_msg(self.sock)
            self.log(msg, "server")
            if "Jugador1" in msg:
                self.player_num = 1
                self.set_player(1, "Esperando al\nJugador 2...")
                self.set_status("Esperando Jugador 2...")
            elif "Jugador2" in msg:
                self.player_num = 2
                self.set_player(2, "Jugador 1\nya conectado")

            self._mostrar_lobby()

            # ── 2) "Iniciando Juego" ────────────────────────────────────────
            msg = recibir_msg(self.sock)
            self.log(msg, "start")
            self.set_player(self.player_num, "EN COMBATE")

            # ── 3) Reglas ──────────────────────────────────────────────────
            msg = recibir_msg(self.sock)
            self._mostrar_reglas(msg.split("|"))

            # ── 4) Esperar clic en "INICIAR PARTIDA" ───────────────────────
            # _on_inicio() llama self._evento_listo.set()
            self._evento_listo.wait()
            enviar_msg(self.sock, "LISTO")

            # ── 5) Esperar "COLOCAR_BARCOS" ────────────────────────────────
            resp = recibir_msg(self.sock)
            if resp != "COLOCAR_BARCOS":
                self.log(f"Protocolo inesperado: {resp}", "warn")
                return
            self._mostrar_colocacion()

            # ── 6) Esperar que el usuario confirme sus barcos ──────────────
            # _confirmar_colocacion() asigna self._payload_barcos y llama
            # self._evento_barcos.set()
            self._evento_barcos.wait()
            enviar_msg(self.sock, self._payload_barcos)

            # ── 7) Confirmación de barcos ──────────────────────────────────
            resp = recibir_msg(self.sock)
            if resp != "BARCOS_OK":
                self.log(f"Error barcos: {resp}", "warn")
                return
            self.set_status("Barcos confirmados. Esperando al rival...")
            self.after(0, lambda: self.btn_confirmar.config(
                text="✔  ENVIADO", bg=ACCENT_DIM))
            self._mostrar_combate()

            # ── 8) Bucle de combate ────────────────────────────────────────
            self._loop_combate()

        except ConnectionError as e:
            self.log(str(e), "warn")
            self.set_connection(False)
            self.set_status("Conexión cerrada.")


# ─── Punto de entrada ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Uso: python3 {sys.argv[0]} <host>")
        sys.exit(1)

    app = BattleshipClient(host=sys.argv[1])
    app.mainloop()
