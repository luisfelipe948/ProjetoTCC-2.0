#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CMS da Marcenaria Pai & Filho — painel único, em Python puro (Tkinter).

Não precisa de servidor nem de HTTPS: é um programa de computador comum.
Rode "python cms.py", faça login e gerencie:
  - o portfólio (adicionar, editar, excluir e reordenar peças);
  - as imagens do site (a principal do topo, a versão para celular e a
    ilustração da seção "Conheça nossos projetos").

O site em si (pasta site/) é HTML puro — pode ser aberto direto no
navegador (site/index.html) ou hospedado em qualquer lugar, sem precisar
rodar este programa junto. Toda vez que o portfólio muda, este programa
reescreve o arquivo site/assets/js/portfolio-data.js, que é o que o site
lê para montar a Home e a página de Portfólio.

Dependência: Pillow (pip install pillow)

Primeiro uso:
    python cms.py
    -> como ainda não existe usuário, o programa pede pra você criar um.
"""
import hashlib
import json
import re
import secrets
import shutil
import sqlite3
import tkinter as tk
import unicodedata
import uuid
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageOps, ImageTk
    TEM_PILLOW = True
except ImportError:
    TEM_PILLOW = False

BASE_DIR = Path(__file__).resolve().parent
SITE_DIR = BASE_DIR / "site"
IMG_DIR = SITE_DIR / "assets" / "img"
PORTFOLIO_IMG_DIR = IMG_DIR / "portfolio"
JS_DATA_PATH = SITE_DIR / "assets" / "js" / "portfolio-data.js"
DB_PATH = BASE_DIR / "cms.db"

CATEGORIAS = ["Cozinha", "Quarto", "Sala", "Escritório", "Painel", "Outro"]

# Imagens do site que o admin pode trocar. Cada uma tem um caminho FIXO
# dentro de site/assets/img — o CMS só sobrescreve o arquivo; o HTML/CSS
# do site já aponta pra esse nome, então não precisa mexer em mais nada.
SLOTS_SITE = {
    "hero_desktop": {
        "rotulo": "Imagem principal — computador (topo da Home)",
        "arquivo": IMG_DIR / "hero.jpg",
        "formato": "JPEG",
        "max_lado": 2400,
    },
    "hero_mobile": {
        "rotulo": "Imagem principal — celular (topo da Home)",
        "arquivo": IMG_DIR / "hero-mobile.jpg",
        "formato": "JPEG",
        "max_lado": 1600,
    },
    "showcase": {
        "rotulo": 'Ilustração "Conheça nossos projetos" (Home)',
        "arquivo": IMG_DIR / "guarda_roupa.png",
        "formato": "PNG",
        "max_lado": 1600,
    },
}

PROJETOS_EXEMPLO = [
    ("Cozinha", "Cozinha Planejada", "Armários planejados com puxadores embutidos e bancada em quartzo.", True),
    ("Sala", "Apoio de TV", "Painel ripado em madeira de demolição, com nicho para TV e som.", True),
    ("Quarto", "Guarda-Roupas", "Guarda-roupa de 3,20m com portas de correr e iluminação interna em LED.", True),
    ("Escritório", "Escrivaninha", "Bancada de trabalho com gaveteiro lateral, pensada para home office.", True),
    ("Cozinha", "Ilha Gourmet", "Ilha central em madeira de demolição com tampo em granito preto.", False),
    ("Quarto", "Closet Planejado", "Closet em L com gaveteiro central e espelho embutido na porta.", False),
    ("Painel", "Painel Ripado", "Revestimento ripado do piso ao teto, com iluminação embutida indireta.", False),
    ("Escritório", "Estante Modular", "Estante sob medida com módulos abertos e fechados, do piso ao teto.", False),
]


# =====================================================================
# Banco de dados
# =====================================================================
def conectar():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def preparar_banco():
    con = conectar()
    con.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS projetos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descricao TEXT NOT NULL,
            categoria TEXT NOT NULL,
            imagem TEXT,
            destaque INTEGER NOT NULL DEFAULT 0,
            ordem INTEGER NOT NULL DEFAULT 0
        )
    """)
    con.commit()

    # Na primeira vez, semeia alguns projetos de exemplo (sem foto), só
    # pra o portfólio não começar vazio. É só editar ou excluir depois.
    total = con.execute("SELECT COUNT(*) FROM projetos").fetchone()[0]
    if total == 0:
        for ordem, (cat, titulo, descricao, destaque) in enumerate(PROJETOS_EXEMPLO):
            con.execute(
                "INSERT INTO projetos (titulo, descricao, categoria, destaque, ordem) "
                "VALUES (?, ?, ?, ?, ?)",
                (titulo, descricao, cat, int(destaque), ordem),
            )
        con.commit()
    con.close()


# =====================================================================
# Senha (PBKDF2, sem depender de nada fora da biblioteca padrão)
# =====================================================================
def gerar_hash_senha(senha):
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(salt), 200_000)
    return salt + "$" + h.hex()


def conferir_senha(senha, hash_salvo):
    try:
        salt, h = hash_salvo.split("$")
    except (ValueError, AttributeError):
        return False
    novo = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(salt), 200_000)
    return secrets.compare_digest(novo.hex(), h)


# =====================================================================
# Imagens
# =====================================================================
def slugify(texto):
    ascii_ = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-") or "categoria"


def _abrir_imagem_corrigida(caminho, lado_max):
    img = Image.open(caminho)
    img = ImageOps.exif_transpose(img)
    img.thumbnail((lado_max, lado_max), Image.LANCZOS)
    return img


def salvar_imagem_portfolio(caminho_origem):
    """Copia a imagem escolhida para site/assets/img/portfolio. Devolve o nome do arquivo."""
    PORTFOLIO_IMG_DIR.mkdir(parents=True, exist_ok=True)
    nome = uuid.uuid4().hex
    if TEM_PILLOW:
        img = _abrir_imagem_corrigida(caminho_origem, 1600)
        transparente = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
        if transparente:
            nome += ".png"
            img.convert("RGBA").save(PORTFOLIO_IMG_DIR / nome, format="PNG", optimize=True)
        else:
            nome += ".jpg"
            img.convert("RGB").save(PORTFOLIO_IMG_DIR / nome, format="JPEG", quality=85, optimize=True)
    else:
        ext = Path(caminho_origem).suffix.lower() or ".jpg"
        nome += ext
        shutil.copy2(caminho_origem, PORTFOLIO_IMG_DIR / nome)
    return nome


def remover_imagem_portfolio(nome):
    if not nome:
        return
    try:
        (PORTFOLIO_IMG_DIR / nome).unlink(missing_ok=True)
    except OSError:
        pass


def salvar_imagem_site(chave, caminho_origem):
    """Sobrescreve, no lugar de sempre, uma das imagens fixas do site."""
    slot = SLOTS_SITE[chave]
    destino = slot["arquivo"]
    destino.parent.mkdir(parents=True, exist_ok=True)
    if TEM_PILLOW:
        img = _abrir_imagem_corrigida(caminho_origem, slot["max_lado"])
        if slot["formato"] == "PNG":
            img.convert("RGBA").save(destino, format="PNG", optimize=True)
        else:
            img.convert("RGB").save(destino, format="JPEG", quality=88, optimize=True, progressive=True)
    else:
        shutil.copy2(caminho_origem, destino)


def gerar_portfolio_js():
    """Reescreve site/assets/js/portfolio-data.js a partir do banco de dados."""
    con = conectar()
    linhas = con.execute("SELECT * FROM projetos ORDER BY ordem, id").fetchall()
    con.close()

    dados = [{
        "id": p["id"],
        "titulo": p["titulo"],
        "descricao": p["descricao"],
        "cat": slugify(p["categoria"]),
        "catNome": p["categoria"],
        "imagem": ("assets/img/portfolio/" + p["imagem"]) if p["imagem"] else None,
        "destaque": bool(p["destaque"]),
    } for p in linhas]

    JS_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    conteudo = (
        "// Gerado automaticamente pelo cms.py — não edite à mão.\n"
        "window.PORTFOLIO = " + json.dumps(dados, ensure_ascii=False, indent=2) + ";\n"
    )
    JS_DATA_PATH.write_text(conteudo, encoding="utf-8")


def miniatura_tk(caminho, tamanho=(160, 120)):
    """PhotoImage pronto pra colocar num Label, ou None se não tiver Pillow/arquivo."""
    if not TEM_PILLOW or not caminho or not Path(caminho).exists():
        return None
    try:
        img = Image.open(caminho)
        img = ImageOps.exif_transpose(img)
        img.thumbnail(tamanho, Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


# =====================================================================
# Diálogo: adicionar/editar projeto do portfólio
# =====================================================================
class ProjetoDialog(tk.Toplevel):
    def __init__(self, master, projeto=None):
        super().__init__(master)
        self.projeto = projeto  # sqlite3.Row ou None (projeto novo)
        self.resultado = False
        self.nova_imagem_caminho = None   # arquivo escolhido nesta sessão (ainda não salvo)
        self.remover_imagem_flag = False
        self._miniatura = None

        self.title("Editar projeto" if projeto else "Novo projeto")
        self.geometry("480x560")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        pad = {"padx": 16, "pady": 6}

        ttk.Label(self, text="Título *").pack(anchor="w", **pad)
        self.var_titulo = tk.StringVar(value=projeto["titulo"] if projeto else "")
        ttk.Entry(self, textvariable=self.var_titulo, width=50).pack(fill="x", padx=16)

        ttk.Label(self, text="Categoria *").pack(anchor="w", **pad)
        self.var_categoria = tk.StringVar(value=projeto["categoria"] if projeto else CATEGORIAS[0])
        ttk.Combobox(self, textvariable=self.var_categoria, values=CATEGORIAS).pack(fill="x", padx=16)

        ttk.Label(self, text="Descrição *").pack(anchor="w", **pad)
        self.txt_descricao = tk.Text(self, height=6, width=50, wrap="word")
        self.txt_descricao.pack(fill="x", padx=16)
        if projeto:
            self.txt_descricao.insert("1.0", projeto["descricao"])

        self.var_destaque = tk.BooleanVar(value=bool(projeto["destaque"]) if projeto else False)
        ttk.Checkbutton(self, text="Mostrar na Home (destaque)", variable=self.var_destaque).pack(
            anchor="w", padx=16, pady=(10, 6)
        )

        ttk.Label(self, text="Foto do projeto").pack(anchor="w", **pad)
        self.lbl_imagem_preview = ttk.Label(self)
        self.lbl_imagem_preview.pack(padx=16, pady=4)
        self._atualizar_preview_atual()

        linha_botoes_img = ttk.Frame(self)
        linha_botoes_img.pack(fill="x", padx=16)
        ttk.Button(linha_botoes_img, text="Escolher imagem...", command=self._escolher_imagem).pack(
            side="left"
        )
        ttk.Button(linha_botoes_img, text="Remover foto", command=self._marcar_remover).pack(
            side="left", padx=8
        )

        rodape = ttk.Frame(self)
        rodape.pack(fill="x", padx=16, pady=20, side="bottom")
        ttk.Button(rodape, text="Cancelar", command=self.destroy).pack(side="right")
        ttk.Button(rodape, text="Salvar", command=self._salvar).pack(side="right", padx=8)

    def _caminho_imagem_atual(self):
        if self.projeto and self.projeto["imagem"]:
            return PORTFOLIO_IMG_DIR / self.projeto["imagem"]
        return None

    def _atualizar_preview_atual(self):
        caminho = self._caminho_imagem_atual()
        self._miniatura = miniatura_tk(caminho)
        if self._miniatura:
            self.lbl_imagem_preview.configure(image=self._miniatura, text="")
        else:
            self.lbl_imagem_preview.configure(image="", text="(sem foto)")

    def _escolher_imagem(self):
        caminho = filedialog.askopenfilename(
            title="Escolha a foto do projeto",
            filetypes=[("Imagens", "*.jpg *.jpeg *.png *.webp")],
        )
        if not caminho:
            return
        self.nova_imagem_caminho = caminho
        self.remover_imagem_flag = False
        self._miniatura = miniatura_tk(caminho)
        if self._miniatura:
            self.lbl_imagem_preview.configure(image=self._miniatura, text="")

    def _marcar_remover(self):
        self.nova_imagem_caminho = None
        self.remover_imagem_flag = True
        self.lbl_imagem_preview.configure(image="", text="(sem foto)")

    def _salvar(self):
        titulo = self.var_titulo.get().strip()
        categoria = self.var_categoria.get().strip()
        descricao = self.txt_descricao.get("1.0", "end").strip()

        if not titulo:
            messagebox.showerror("Faltou algo", "Dê um título ao projeto.", parent=self)
            return
        if not categoria:
            messagebox.showerror("Faltou algo", "Escolha uma categoria.", parent=self)
            return
        if not descricao:
            messagebox.showerror("Faltou algo", "Escreva uma descrição curta do projeto.", parent=self)
            return

        nome_imagem = self.projeto["imagem"] if self.projeto else None
        imagem_antiga = nome_imagem

        if self.nova_imagem_caminho:
            nome_imagem = salvar_imagem_portfolio(self.nova_imagem_caminho)
        elif self.remover_imagem_flag:
            nome_imagem = None

        con = conectar()
        if self.projeto is None:
            menor = con.execute("SELECT MIN(ordem) FROM projetos").fetchone()[0]
            ordem = (menor if menor is not None else 0) - 1
            con.execute(
                "INSERT INTO projetos (titulo, descricao, categoria, imagem, destaque, ordem) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (titulo, descricao, categoria, nome_imagem, int(self.var_destaque.get()), ordem),
            )
        else:
            con.execute(
                "UPDATE projetos SET titulo=?, descricao=?, categoria=?, imagem=?, destaque=? WHERE id=?",
                (titulo, descricao, categoria, nome_imagem, int(self.var_destaque.get()), self.projeto["id"]),
            )
        con.commit()
        con.close()

        if imagem_antiga and imagem_antiga != nome_imagem:
            remover_imagem_portfolio(imagem_antiga)

        gerar_portfolio_js()
        self.resultado = True
        self.destroy()


# =====================================================================
# Aplicativo principal (uma janela só, com telas que se alternam)
# =====================================================================
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CMS — Marcenaria Pai & Filho")
        self.root.geometry("1000x640")
        self.root.minsize(860, 560)

        self.usuario_logado = None
        self._miniaturas_slots = {}  # mantém referência das imagens (senão o Tkinter "esquece" e some)

        self.container = ttk.Frame(self.root)
        self.container.pack(fill="both", expand=True)

        self._mostrar_tela_inicial()
        self.root.mainloop()

    # ---------------- navegação ----------------
    def _limpar(self):
        for w in self.container.winfo_children():
            w.destroy()

    def _mostrar_tela_inicial(self):
        con = conectar()
        existe_usuario = con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] > 0
        con.close()
        if existe_usuario:
            self._tela_login()
        else:
            self._tela_criar_admin()

    # ---------------- criar o 1º usuário ----------------
    def _tela_criar_admin(self):
        self._limpar()
        frame = ttk.Frame(self.container)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(frame, text="Bem-vindo!", font=("", 18, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 4))
        ttk.Label(frame, text="Crie o primeiro usuário do painel para começar.").grid(
            row=1, column=0, columnspan=2, pady=(0, 16)
        )

        ttk.Label(frame, text="Usuário").grid(row=2, column=0, sticky="e", padx=6, pady=6)
        var_user = tk.StringVar()
        ttk.Entry(frame, textvariable=var_user, width=28).grid(row=2, column=1, pady=6)

        ttk.Label(frame, text="Senha (mín. 8 caracteres)").grid(row=3, column=0, sticky="e", padx=6, pady=6)
        var_senha = tk.StringVar()
        ttk.Entry(frame, textvariable=var_senha, show="•", width=28).grid(row=3, column=1, pady=6)

        ttk.Label(frame, text="Repita a senha").grid(row=4, column=0, sticky="e", padx=6, pady=6)
        var_senha2 = tk.StringVar()
        ttk.Entry(frame, textvariable=var_senha2, show="•", width=28).grid(row=4, column=1, pady=6)

        def criar():
            usuario = var_user.get().strip().lower()
            senha = var_senha.get()
            if not usuario:
                messagebox.showerror("Faltou algo", "Escolha um nome de usuário.")
                return
            if len(senha) < 8:
                messagebox.showerror("Senha curta", "A senha precisa ter pelo menos 8 caracteres.")
                return
            if senha != var_senha2.get():
                messagebox.showerror("Não confere", "As duas senhas precisam ser iguais.")
                return
            con = conectar()
            con.execute(
                "INSERT INTO usuarios (username, senha_hash) VALUES (?, ?)",
                (usuario, gerar_hash_senha(senha)),
            )
            con.commit()
            con.close()
            messagebox.showinfo("Pronto", "Usuário criado! Agora é só entrar.")
            self._tela_login()

        ttk.Button(frame, text="Criar usuário", command=criar).grid(row=5, column=0, columnspan=2, pady=16)

    # ---------------- login ----------------
    def _tela_login(self):
        self._limpar()
        frame = ttk.Frame(self.container)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(frame, text="CMS — Marcenaria Pai & Filho", font=("", 18, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(0, 20)
        )

        ttk.Label(frame, text="Usuário").grid(row=1, column=0, sticky="e", padx=6, pady=6)
        var_user = tk.StringVar()
        ent_user = ttk.Entry(frame, textvariable=var_user, width=28)
        ent_user.grid(row=1, column=1, pady=6)
        ent_user.focus_set()

        ttk.Label(frame, text="Senha").grid(row=2, column=0, sticky="e", padx=6, pady=6)
        var_senha = tk.StringVar()
        ent_senha = ttk.Entry(frame, textvariable=var_senha, show="•", width=28)
        ent_senha.grid(row=2, column=1, pady=6)

        lbl_erro = ttk.Label(frame, text="", foreground="#b3261e")
        lbl_erro.grid(row=3, column=0, columnspan=2)

        def entrar(event=None):
            con = conectar()
            row = con.execute(
                "SELECT * FROM usuarios WHERE username = ?", (var_user.get().strip().lower(),)
            ).fetchone()
            con.close()
            if row and conferir_senha(var_senha.get(), row["senha_hash"]):
                self.usuario_logado = row["username"]
                self._tela_painel()
            else:
                lbl_erro.configure(text="Usuário ou senha incorretos.")

        ent_senha.bind("<Return>", entrar)
        ttk.Button(frame, text="Entrar", command=entrar).grid(row=4, column=0, columnspan=2, pady=16)

    def _sair(self):
        self.usuario_logado = None
        self._tela_login()

    # ---------------- painel principal ----------------
    def _tela_painel(self):
        self._limpar()

        topo = ttk.Frame(self.container)
        topo.pack(fill="x", padx=16, pady=10)
        ttk.Label(topo, text="Painel — Marcenaria Pai & Filho", font=("", 14, "bold")).pack(side="left")
        ttk.Label(topo, text="  (usuário: %s)" % self.usuario_logado, foreground="#666").pack(side="left")
        ttk.Button(topo, text="Sair", command=self._sair).pack(side="right")

        notebook = ttk.Notebook(self.container)
        notebook.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        aba_portfolio = ttk.Frame(notebook)
        aba_imagens = ttk.Frame(notebook)
        notebook.add(aba_portfolio, text="Portfólio")
        notebook.add(aba_imagens, text="Imagens do site")

        self._montar_aba_portfolio(aba_portfolio)
        self._montar_aba_imagens(aba_imagens)

    # ---------------- aba: portfólio (CRUD) ----------------
    def _montar_aba_portfolio(self, aba):
        botoes = ttk.Frame(aba)
        botoes.pack(fill="x", pady=(10, 6))
        ttk.Button(botoes, text="Novo projeto", command=self._novo_projeto).pack(side="left")
        ttk.Button(botoes, text="Editar", command=self._editar_projeto).pack(side="left", padx=6)
        ttk.Button(botoes, text="Excluir", command=self._excluir_projeto).pack(side="left")
        ttk.Button(botoes, text="Mover ▲", command=lambda: self._mover_projeto(-1)).pack(side="left", padx=(20, 0))
        ttk.Button(botoes, text="Mover ▼", command=lambda: self._mover_projeto(1)).pack(side="left", padx=6)

        colunas = ("titulo", "categoria", "destaque")
        self.tree = ttk.Treeview(aba, columns=colunas, show="headings", selectmode="browse")
        self.tree.heading("titulo", text="Título")
        self.tree.heading("categoria", text="Categoria")
        self.tree.heading("destaque", text="Na Home?")
        self.tree.column("titulo", width=320)
        self.tree.column("categoria", width=160)
        self.tree.column("destaque", width=100, anchor="center")
        self.tree.pack(fill="both", expand=True, pady=6)
        self.tree.bind("<Double-1>", lambda e: self._editar_projeto())

        self._carregar_projetos()

    def _carregar_projetos(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        con = conectar()
        linhas = con.execute("SELECT * FROM projetos ORDER BY ordem, id").fetchall()
        con.close()
        for p in linhas:
            self.tree.insert(
                "", "end", iid=str(p["id"]),
                values=(p["titulo"], p["categoria"], "Sim" if p["destaque"] else "—"),
            )

    def _projeto_selecionado_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _novo_projeto(self):
        dlg = ProjetoDialog(self.root, projeto=None)
        self.root.wait_window(dlg)
        if dlg.resultado:
            self._carregar_projetos()

    def _editar_projeto(self):
        pid = self._projeto_selecionado_id()
        if pid is None:
            messagebox.showinfo("Selecione um projeto", "Clique num projeto da lista primeiro.")
            return
        con = conectar()
        projeto = con.execute("SELECT * FROM projetos WHERE id = ?", (pid,)).fetchone()
        con.close()
        dlg = ProjetoDialog(self.root, projeto=projeto)
        self.root.wait_window(dlg)
        if dlg.resultado:
            self._carregar_projetos()

    def _excluir_projeto(self):
        pid = self._projeto_selecionado_id()
        if pid is None:
            messagebox.showinfo("Selecione um projeto", "Clique num projeto da lista primeiro.")
            return
        con = conectar()
        projeto = con.execute("SELECT * FROM projetos WHERE id = ?", (pid,)).fetchone()
        if not messagebox.askyesno("Excluir projeto", 'Excluir "%s"? Essa ação não pode ser desfeita.' % projeto["titulo"]):
            con.close()
            return
        con.execute("DELETE FROM projetos WHERE id = ?", (pid,))
        con.commit()
        con.close()
        remover_imagem_portfolio(projeto["imagem"])
        gerar_portfolio_js()
        self._carregar_projetos()

    def _mover_projeto(self, direcao):
        pid = self._projeto_selecionado_id()
        if pid is None:
            return
        con = conectar()
        linhas = con.execute("SELECT id, ordem FROM projetos ORDER BY ordem, id").fetchall()
        ids = [r["id"] for r in linhas]
        i = ids.index(pid)
        j = i + direcao
        if 0 <= j < len(ids):
            ids[i], ids[j] = ids[j], ids[i]
            for n, item_id in enumerate(ids):
                con.execute("UPDATE projetos SET ordem = ? WHERE id = ?", (n, item_id))
            con.commit()
        con.close()
        gerar_portfolio_js()
        self._carregar_projetos()
        self.tree.selection_set(str(pid))

    # ---------------- aba: imagens do site ----------------
    def _montar_aba_imagens(self, aba):
        if not TEM_PILLOW:
            ttk.Label(
                aba,
                text="Dica: instale o Pillow (pip install pillow) para redimensionar as imagens "
                     "automaticamente. Sem ele, o arquivo é copiado do jeito que está.",
                foreground="#8a6d1a",
                wraplength=820,
            ).pack(anchor="w", pady=(10, 10))

        for chave, slot in SLOTS_SITE.items():
            linha = ttk.Frame(aba, relief="groove", borderwidth=1)
            linha.pack(fill="x", pady=6, ipady=8, padx=2)

            miniatura = miniatura_tk(slot["arquivo"])
            self._miniaturas_slots[chave] = miniatura  # segura a referência
            lbl_img = ttk.Label(linha, image=miniatura) if miniatura else ttk.Label(linha, text="(sem imagem)")
            lbl_img.pack(side="left", padx=12)

            info = ttk.Frame(linha)
            info.pack(side="left", fill="x", expand=True, padx=12)
            ttk.Label(info, text=slot["rotulo"], font=("", 11, "bold")).pack(anchor="w")
            ttk.Label(info, text=str(slot["arquivo"].relative_to(BASE_DIR))).pack(anchor="w")

            ttk.Button(
                linha, text="Escolher imagem...",
                command=lambda c=chave, lbl=lbl_img: self._trocar_imagem_site(c, lbl),
            ).pack(side="right", padx=12)

    def _trocar_imagem_site(self, chave, label_widget):
        caminho = filedialog.askopenfilename(
            title="Escolha a nova imagem",
            filetypes=[("Imagens", "*.jpg *.jpeg *.png *.webp")],
        )
        if not caminho:
            return
        salvar_imagem_site(chave, caminho)
        nova_miniatura = miniatura_tk(SLOTS_SITE[chave]["arquivo"])
        self._miniaturas_slots[chave] = nova_miniatura
        if nova_miniatura:
            label_widget.configure(image=nova_miniatura, text="")
        messagebox.showinfo("Pronto", '"%s" atualizada.' % SLOTS_SITE[chave]["rotulo"])


# =====================================================================
if __name__ == "__main__":
    preparar_banco()
    gerar_portfolio_js()  # garante que o site já tem o arquivo de dados na primeira vez
    App()
