#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CMS da Marcenaria Pai & Filho — painel único, em Python (Tkinter + Pillow).

Rode "python cms.py".

  - Na PRIMEIRA vez o programa pede o cadastro: nome, e-mail e senha.
  - Depois disso você entra com o E-MAIL e a senha.
  - "Esqueci minha senha": um código de 6 dígitos é enviado para o e-mail
    cadastrado; com o código você escolhe uma senha nova.

No painel você gerencia:
  - o portfólio (adicionar, editar, excluir e reordenar peças);
  - as imagens do site (a principal do topo, a versão para celular e a
    ilustração da seção "Conheça nossos projetos").

Em todo lugar que tem imagem o painel mostra a que está NO SITE agora e
guarda as 5 imagens anteriores, para você voltar para uma delas com um clique.

O site (pasta site/) é HTML puro. Toda vez que o portfólio muda, este
programa reescreve site/assets/js/portfolio-data.js, que é o que o site lê.

Visual: mesma paleta do site (site/assets/css/base.css — preto-café,
nogueira, oliva, cobre, areia), com cantos arredondados e botões suaves.
As fontes do site (Spoof, Fraunces, Work Sans) são usadas se estiverem
instaladas; senão o painel cai num fallback parecido.

Dependência: Pillow  ->  pip install pillow

Código por e-mail (Gmail) — configuração:
    1. Na conta Google que vai ENVIAR os e-mails, ative a verificação em 2
       etapas e crie uma "Senha de app" (myaccount.google.com/apppasswords).
    2. Crie o arquivo email_config.json AO LADO deste programa (nunca dentro
       da pasta site/, que é pública):
           {"remetente": "conta.que.envia@gmail.com", "senha_app": "xxxx xxxx xxxx xxxx"}
       (ou use as variáveis de ambiente CMS_EMAIL_REMETENTE e CMS_EMAIL_SENHA_APP).
       Há um modelo em email_config.exemplo.json.
    3. Não envie esse arquivo pro GitHub — ele guarda a senha de app.
"""
import hashlib
import json
import os
import re
import secrets
import shutil
import smtplib
import sqlite3
import ssl
import threading
import time
import tkinter as tk
import unicodedata
import uuid
from email.message import EmailMessage
from pathlib import Path
from tkinter import filedialog, ttk
from tkinter import font as tkfont

try:
    from PIL import Image, ImageDraw, ImageOps, ImageTk
    TEM_PILLOW = True
except ImportError:  # o painel precisa do Pillow para desenhar a interface
    TEM_PILLOW = False

BASE_DIR = Path(__file__).resolve().parent
SITE_DIR = BASE_DIR / "site"
IMG_DIR = SITE_DIR / "assets" / "img"
PORTFOLIO_IMG_DIR = IMG_DIR / "portfolio"
JS_DATA_PATH = SITE_DIR / "assets" / "js" / "portfolio-data.js"
DB_PATH = BASE_DIR / "cms.db"

# Histórico: cópias das imagens que foram trocadas. Fica FORA da pasta do site,
# então nada daqui é publicado.
HIST_DIR = BASE_DIR / "historico_imagens"
HIST_MAX = 5

# Código de recuperação de senha, enviado por e-mail (Gmail). Veja o topo do arquivo.
EMAIL_CONFIG_PATH = BASE_DIR / "email_config.json"
CODIGO_VALIDADE_MIN = 10      # minutos que o código vale
CODIGO_MAX_TENTATIVAS = 5     # erros permitidos antes de pedir outro código
CODIGO_ESPERA_REENVIO = 60    # segundos entre um pedido de código e outro
SENHA_MIN = 8
LOGIN_MAX_FALHAS = 5          # erros de senha seguidos antes de travar um pouco
LOGIN_TRAVA_SEG = 30

CATEGORIAS = ["Cozinha", "Quarto", "Sala", "Escritório", "Painel", "Outro"]

# Imagens do site que o admin pode trocar. Cada uma tem um caminho FIXO
# dentro de site/assets/img — o CMS só sobrescreve o arquivo; o HTML/CSS
# do site já aponta pra esse nome, então não precisa mexer em mais nada.
SLOTS_SITE = {
    "hero_desktop": {
        "rotulo": "Imagem principal — computador",
        "onde": "Topo da Home",
        "arquivo": IMG_DIR / "hero.jpg",
        "formato": "JPEG",
        "max_lado": 2400,
        "proporcao": 16 / 9,
    },
    "hero_mobile": {
        "rotulo": "Imagem principal — celular",
        "onde": "Topo da Home no celular",
        "arquivo": IMG_DIR / "hero-mobile.jpg",
        "formato": "JPEG",
        "max_lado": 1600,
        "proporcao": 3 / 4,
    },
    "showcase": {
        "rotulo": "Ilustração “Conheça nossos projetos”",
        "onde": "Seção do meio da Home",
        "arquivo": IMG_DIR / "guarda_roupa.png",
        "formato": "PNG",
        "max_lado": 1600,
        "proporcao": 4 / 3,
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
# Visual — mesma paleta e mesmos elementos do site (site/assets/css/base.css)
# =====================================================================
PRETO_CAFE = "#1A130B"    # fundo geral
NOGUEIRA = "#241A13"      # painéis, cards, header
CASCA = "#3D2D21"
OLIVA = "#4A5233"
OLIVA_CLARO = "#6B7448"
COBRE = "#B4713C"
AREIA = "#E8DCC8"
CREME = "#FFFCF6"
TEXTO = "#EDE3D3"
TEXTO_SUAVE = "#B9A991"
ERRO = "#C97A63"

LINHA = "#3F352C"           # rgba(232,220,200,.14) sobre nogueira
LINHA_PRETO = "#372F26"     # idem, sobre preto-café
NAV_INATIVO = "#BFB4A2"
LOGO_SUB = "#B2ADA6"
CARD_HOVER = "#2C2017"      # card em hover
CARD_SEL = "#2B2F1F"        # card selecionado (nogueira com um toque de oliva)

# degradê verde das "peças" sem foto (.peca no site)
PECA_TOPO = (0x5C, 0x6B, 0x3E)
PECA_FUNDO = (0x3E, 0x4A, 0x2A)

CARD_W, CARD_H = 224, 280   # proporção 4:5, igual ao .peca do site
RAIO_CARD = 18

_FONTES = {}


def resolver_fontes(root):
    """Usa as fontes do site se estiverem instaladas; senão, um fallback parecido."""
    instaladas = set(tkfont.families(root))

    def escolher(candidatas, padrao):
        for nome in candidatas:
            if nome in instaladas:
                return nome
        return padrao

    _FONTES["titulo"] = escolher([
        "Spoof", "Futura", "Century Gothic", "Avenir Next", "Avenir"], "Helvetica")
    _FONTES["serif"] = escolher(["Fraunces", "Georgia", "Cambria", "Times New Roman"], "Times")
    _FONTES["corpo"] = escolher(
        ["Work Sans", "Segoe UI", "Helvetica Neue", "Ubuntu", "Noto Sans", "DejaVu Sans"], "Helvetica"
    )


def fonte(familia, tamanho, estilo=""):
    base = (_FONTES.get(familia, "Helvetica"), tamanho)
    return base + (estilo,) if estilo else base


def espacar(texto):
    """Imita o letter-spacing largo do site (eyebrow, categorias)."""
    palavras = texto.upper().split(" ")
    return "  ".join("\u2009".join(p) for p in palavras)


def misturar(c1, c2, t):
    """Mistura duas cores hex (t=0 -> c1, t=1 -> c2). Tk não tem transparência."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02X%02X%02X" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def cortar(texto, fnt, largura_max):
    if fnt.measure(texto) <= largura_max:
        return texto
    while texto and fnt.measure(texto + "…") > largura_max:
        texto = texto[:-1]
    return texto.rstrip() + "…"


def aplicar_tema(root):
    """Só o que ainda usa ttk: a barra de rolagem fina."""
    root.configure(bg=PRETO_CAFE)
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(
        "Vertical.TScrollbar", background=CASCA, troughcolor=PRETO_CAFE, bordercolor=PRETO_CAFE,
        arrowcolor=TEXTO_SUAVE, lightcolor=CASCA, darkcolor=CASCA, relief="flat", gripcount=0,
    )
    s.map("Vertical.TScrollbar", background=[("active", OLIVA)])
    s.layout("Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
        ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    s.configure("Vertical.TScrollbar", width=10)


# =====================================================================
# Formas arredondadas (desenhadas com Pillow, com bordas suaves)
# =====================================================================
_FORMAS = {}
_MINIS = {}
_SS = 4  # supersampling: desenha 4x maior e reduz, pra borda ficar lisa


def forma(w, h, raio, fill, borda=None, bw=1):
    """PhotoImage de um retângulo arredondado (fundo transparente nos cantos)."""
    w, h = max(int(w), 2), max(int(h), 2)
    chave = (w, h, raio, fill, borda, bw)
    foto = _FORMAS.get(chave)
    if foto is None:
        if fill is None:           # interior transparente (só o anel da borda)
            fill = (0, 0, 0, 0)
        if len(_FORMAS) > 400:
            _FORMAS.clear()
        img = Image.new("RGBA", (w * _SS, h * _SS), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        r = min(raio, h // 2, w // 2) * _SS
        if borda:
            d.rounded_rectangle((0, 0, w * _SS - 1, h * _SS - 1), radius=r, fill=borda)
            d.rounded_rectangle(
                (bw * _SS, bw * _SS, w * _SS - 1 - bw * _SS, h * _SS - 1 - bw * _SS),
                radius=max(r - bw * _SS, 0), fill=fill,
            )
        else:
            d.rounded_rectangle((0, 0, w * _SS - 1, h * _SS - 1), radius=r, fill=fill)
        foto = ImageTk.PhotoImage(img.resize((w, h), Image.LANCZOS))
        _FORMAS[chave] = foto
    return foto


def _mascara(w, h, raio):
    m = Image.new("L", (w * _SS, h * _SS), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * _SS - 1, h * _SS - 1), radius=raio * _SS, fill=255)
    return m


def _degrade_peca(w, h):
    topo = Image.new("RGB", (w, h), PECA_TOPO)
    fundo = Image.new("RGB", (w, h), PECA_FUNDO)
    return Image.composite(fundo, topo, Image.linear_gradient("L").resize((w, h)))


def miniatura(caminho, w, h, raio=10, modo="cover", fundo=NOGUEIRA, gradiente=True):
    """
    Miniatura arredondada de uma imagem do disco.
    modo "cover" corta pra preencher (como o card do site); "contain" mostra a imagem inteira.
    Sem arquivo: degradê verde das peças (ou None, se gradiente=False).
    O cache considera a data do arquivo, então trocar a imagem atualiza a miniatura.
    """
    w, h = max(int(w), 4), max(int(h), 4)
    existe = bool(caminho) and Path(caminho).exists()
    try:
        mt = Path(caminho).stat().st_mtime_ns if existe else 0
    except OSError:
        mt, existe = 0, False
    chave = (str(caminho) if existe else None, mt, w, h, raio, modo, fundo, gradiente)
    if chave in _MINIS:
        return _MINIS[chave]

    base = None
    if existe:
        try:
            img = ImageOps.exif_transpose(Image.open(caminho))
            if modo == "contain":
                img = img.convert("RGBA")
                caixa = Image.new("RGBA", (w * _SS, h * _SS), fundo)
                img.thumbnail((w * _SS, h * _SS), Image.LANCZOS)
                caixa.alpha_composite(img, ((w * _SS - img.width) // 2, (h * _SS - img.height) // 2))
                base = caixa.convert("RGB")
            else:
                base = ImageOps.fit(img.convert("RGB"), (w * _SS, h * _SS), Image.LANCZOS)
        except Exception:
            base = None
    if base is None:
        if not gradiente:
            return None
        base = _degrade_peca(w * _SS, h * _SS)

    base = base.convert("RGBA")
    base.putalpha(_mascara(w, h, raio))
    foto = ImageTk.PhotoImage(base.resize((w, h), Image.LANCZOS))
    if len(_MINIS) > 300:
        _MINIS.clear()
    _MINIS[chave] = foto
    return foto


def fabricar_card(caminho, tamanho, raio=RAIO_CARD):
    """Card de "peça" igual ao do site: foto (ou degradê verde) + degradê escuro embaixo pro texto."""
    w, h = tamanho
    S = 2
    base = None
    if caminho and Path(caminho).exists():
        try:
            img = ImageOps.exif_transpose(Image.open(caminho)).convert("RGB")
            base = ImageOps.fit(img, (w * S, h * S), Image.LANCZOS)
        except Exception:
            base = None
    if base is None:
        base = _degrade_peca(w * S, h * S)
    grad = Image.linear_gradient("L").resize((w * S, h * S))
    alfa = grad.point(lambda v: int(255 * 0.75 * max(0.0, 1 - (1 - v / 255) / 0.55)))
    sombra = Image.new("RGBA", (w * S, h * S), (24, 17, 9, 0))
    sombra.putalpha(alfa)
    final = Image.alpha_composite(base.convert("RGBA"), sombra)
    m = Image.new("L", (w * S, h * S), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * S - 1, h * S - 1), radius=raio * S, fill=255)
    final.putalpha(m)
    return ImageTk.PhotoImage(final.resize((w, h), Image.LANCZOS))


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
    # Cadastro de quem cuida do painel (feito uma única vez, na primeira abertura).
    con.execute("""
        CREATE TABLE IF NOT EXISTS admin_cadastro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL,
            criado_em REAL NOT NULL
        )
    """)
    # Histórico das imagens trocadas (as 5 últimas de cada lugar).
    # alvo: "slot:hero_desktop" | "projeto:12"
    con.execute("""
        CREATE TABLE IF NOT EXISTS historico_imagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alvo TEXT NOT NULL,
            arquivo TEXT NOT NULL,
            criado_em REAL NOT NULL
        )
    """)
    con.commit()

    # Migração: o cadastro da versão anterior não tinha senha nem código de recuperação.
    colunas = {r["name"] for r in con.execute("PRAGMA table_info(admin_cadastro)")}
    novas = (
        ("senha_hash", "TEXT"),
        ("reset_hash", "TEXT"),
        ("reset_expira", "REAL"),
        ("reset_tentativas", "INTEGER NOT NULL DEFAULT 0"),
        ("reset_enviado_em", "REAL"),
    )
    for nome, tipo in novas:
        if nome not in colunas:
            con.execute("ALTER TABLE admin_cadastro ADD COLUMN %s %s" % (nome, tipo))
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
# Cadastro, login por e-mail e recuperação de senha por código
# =====================================================================
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def email_valido(email):
    return bool(EMAIL_RE.match(email))


def gerar_hash_senha(senha):
    """PBKDF2 (biblioteca padrão): guarda só o hash, nunca a senha."""
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(salt), 200_000)
    return salt + "$" + h.hex()


def conferir_senha(senha, hash_salvo):
    try:
        salt, h = hash_salvo.split("$")
        novo = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(salt), 200_000)
    except (ValueError, AttributeError):
        return False
    return secrets.compare_digest(novo.hex(), h)


_HASH_FALSO = gerar_hash_senha("x")   # usado quando o e-mail não existe, pra demorar o mesmo tempo


def obter_cadastro():
    con = conectar()
    row = con.execute("SELECT * FROM admin_cadastro ORDER BY id LIMIT 1").fetchone()
    con.close()
    return row


def criar_cadastro(nome, email, senha):
    con = conectar()
    con.execute("DELETE FROM admin_cadastro")
    con.execute(
        "INSERT INTO admin_cadastro (nome, email, criado_em, senha_hash) VALUES (?, ?, ?, ?)",
        (nome, email, time.time(), gerar_hash_senha(senha)),
    )
    con.commit()
    con.close()


def definir_senha_do_cadastro(senha):
    """Cadastro feito na versão anterior (sem senha): define a senha uma vez."""
    con = conectar()
    con.execute("UPDATE admin_cadastro SET senha_hash = ?", (gerar_hash_senha(senha),))
    con.commit()
    con.close()


def autenticar(email, senha):
    """Devolve o cadastro se e-mail e senha conferem; senão None."""
    cad = obter_cadastro()
    certo = cad is not None and cad["email"].lower() == email.strip().lower()
    ok = conferir_senha(senha, cad["senha_hash"] if certo and cad["senha_hash"] else _HASH_FALSO)
    return cad if (certo and ok) else None


def atualizar_nome(nome):
    con = conectar()
    con.execute("UPDATE admin_cadastro SET nome = ?", (nome,))
    con.commit()
    con.close()


def trocar_senha(senha_atual, nova):
    cad = obter_cadastro()
    if cad is None or not conferir_senha(senha_atual, cad["senha_hash"]):
        return False
    con = conectar()
    con.execute("UPDATE admin_cadastro SET senha_hash = ?", (gerar_hash_senha(nova),))
    con.commit()
    con.close()
    return True


def dados_do_usuario_antigo():
    """Bancos da versão com login por usuário ainda têm a tabela `usuarios`: reaproveita o e-mail pra pré-preencher."""
    try:
        con = conectar()
        row = con.execute("SELECT username, email FROM usuarios ORDER BY id LIMIT 1").fetchone()
        con.close()
        if row:
            return (row["username"] or "").strip(), (row["email"] or "").strip()
    except sqlite3.Error:
        pass
    return "", ""


class EmailNaoConfigurado(Exception):
    pass


class EnvioMuitoRapido(Exception):
    def __init__(self, restam):
        super().__init__(restam)
        self.restam = restam


def carregar_config_email():
    """Lê o remetente e a senha de app do Gmail (variáveis de ambiente ou email_config.json)."""
    remetente = os.environ.get("CMS_EMAIL_REMETENTE", "").strip()
    senha_app = os.environ.get("CMS_EMAIL_SENHA_APP", "").strip()
    if (not remetente or not senha_app) and EMAIL_CONFIG_PATH.exists():
        try:
            dados = json.loads(EMAIL_CONFIG_PATH.read_text(encoding="utf-8"))
            remetente = remetente or str(dados.get("remetente", "")).strip()
            senha_app = senha_app or str(dados.get("senha_app", "")).strip()
        except (OSError, ValueError):
            pass
    if not remetente or not senha_app or "COLE" in senha_app.upper():
        raise EmailNaoConfigurado()
    return remetente, senha_app.replace(" ", "")  # o Google mostra a senha de app com espaços


def enviar_email_codigo(destino, codigo):
    remetente, senha_app = carregar_config_email()
    msg = EmailMessage()
    msg["Subject"] = "Seu código de verificação — CMS Marcenaria Pai & Filho"
    msg["From"] = remetente
    msg["To"] = destino
    msg.set_content(
        "Seu código para redefinir a senha do painel é:\n\n"
        "    %s\n\n"
        "Ele vale por %d minutos. Se não foi você que pediu, ignore este e-mail."
        % (codigo, CODIGO_VALIDADE_MIN)
    )
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=20) as smtp:
        smtp.login(remetente, senha_app)
        smtp.send_message(msg)


def iniciar_recuperacao(email):
    """Gera o código, guarda só o hash dele (com validade) e envia para o e-mail cadastrado.

    Se o e-mail digitado não for o cadastrado, não faz nada e não avisa quem está na tela —
    assim ninguém descobre qual e-mail é o do painel."""
    con = conectar()
    try:
        row = con.execute("SELECT * FROM admin_cadastro ORDER BY id LIMIT 1").fetchone()
        if row is None:
            return
        espera = CODIGO_ESPERA_REENVIO - (time.time() - (row["reset_enviado_em"] or 0))
        if espera > 0:
            raise EnvioMuitoRapido(int(espera) + 1)
        if row["email"].lower() != email.strip().lower():
            return
        codigo = "%06d" % secrets.randbelow(1_000_000)
        con.execute(
            "UPDATE admin_cadastro SET reset_hash = ?, reset_expira = ?, reset_tentativas = 0, "
            "reset_enviado_em = ? WHERE id = ?",
            (gerar_hash_senha(codigo), time.time() + CODIGO_VALIDADE_MIN * 60, time.time(), row["id"]),
        )
        con.commit()
        try:
            enviar_email_codigo(row["email"], codigo)
        except Exception:
            # o envio falhou: volta ao estado de antes, então um código anterior (ainda válido) continua valendo
            con.execute(
                "UPDATE admin_cadastro SET reset_hash = ?, reset_expira = ?, reset_tentativas = ?, "
                "reset_enviado_em = ? WHERE id = ?",
                (row["reset_hash"], row["reset_expira"], row["reset_tentativas"], row["reset_enviado_em"], row["id"]),
            )
            con.commit()
            raise
    finally:
        con.close()


def redefinir_senha_com_codigo(email, codigo, nova_senha):
    """Confere o código e troca a senha. Devolve (ok, mensagem_de_erro)."""
    con = conectar()
    try:
        row = con.execute("SELECT * FROM admin_cadastro ORDER BY id LIMIT 1").fetchone()
        if row is None or not row["reset_hash"] or row["email"].lower() != email.strip().lower():
            return False, "Código inválido ou expirado. Peça um novo código."
        if time.time() > (row["reset_expira"] or 0) or row["reset_tentativas"] >= CODIGO_MAX_TENTATIVAS:
            con.execute("UPDATE admin_cadastro SET reset_hash = NULL, reset_expira = NULL WHERE id = ?", (row["id"],))
            con.commit()
            return False, "O código expirou ou teve tentativas demais. Peça um novo código."
        if not conferir_senha(codigo, row["reset_hash"]):
            con.execute("UPDATE admin_cadastro SET reset_tentativas = reset_tentativas + 1 WHERE id = ?", (row["id"],))
            con.commit()
            restam = CODIGO_MAX_TENTATIVAS - row["reset_tentativas"] - 1
            return False, "Código incorreto. Tentativas restantes: %d." % max(restam, 0)
        con.execute(
            "UPDATE admin_cadastro SET senha_hash = ?, reset_hash = NULL, reset_expira = NULL, "
            "reset_tentativas = 0 WHERE id = ?",
            (gerar_hash_senha(nova_senha), row["id"]),
        )
        con.commit()
        return True, ""
    finally:
        con.close()


# =====================================================================
# Histórico de imagens (as 5 anteriores de cada lugar)
# =====================================================================
def alvo_slot(chave):
    return "slot:" + chave


def alvo_projeto(pid):
    return "projeto:%d" % pid


def listar_historico(alvo):
    con = conectar()
    linhas = con.execute(
        "SELECT * FROM historico_imagens WHERE alvo = ? ORDER BY id DESC LIMIT ?", (alvo, HIST_MAX)
    ).fetchall()
    con.close()
    # ignora entradas cujo arquivo sumiu
    return [r for r in linhas if (HIST_DIR / r["arquivo"]).exists()]


def caminho_historico(item):
    return HIST_DIR / item["arquivo"]


def arquivar_imagem(alvo, caminho_atual):
    """Guarda uma cópia da imagem que está prestes a ser trocada e mantém só as 5 últimas."""
    if not caminho_atual or not Path(caminho_atual).exists():
        return
    HIST_DIR.mkdir(parents=True, exist_ok=True)
    nome = uuid.uuid4().hex + (Path(caminho_atual).suffix.lower() or ".jpg")
    shutil.copy2(caminho_atual, HIST_DIR / nome)
    con = conectar()
    con.execute(
        "INSERT INTO historico_imagens (alvo, arquivo, criado_em) VALUES (?, ?, ?)", (alvo, nome, time.time())
    )
    antigas = con.execute(
        "SELECT id, arquivo FROM historico_imagens WHERE alvo = ? ORDER BY id DESC", (alvo,)
    ).fetchall()[HIST_MAX:]
    for r in antigas:
        (HIST_DIR / r["arquivo"]).unlink(missing_ok=True)
        con.execute("DELETE FROM historico_imagens WHERE id = ?", (r["id"],))
    con.commit()
    con.close()


def remover_do_historico(item_id):
    con = conectar()
    row = con.execute("SELECT arquivo FROM historico_imagens WHERE id = ?", (item_id,)).fetchone()
    con.execute("DELETE FROM historico_imagens WHERE id = ?", (item_id,))
    con.commit()
    con.close()
    if row:
        (HIST_DIR / row["arquivo"]).unlink(missing_ok=True)


def apagar_historico_do_alvo(alvo):
    con = conectar()
    for r in con.execute("SELECT arquivo FROM historico_imagens WHERE alvo = ?", (alvo,)).fetchall():
        (HIST_DIR / r["arquivo"]).unlink(missing_ok=True)
    con.execute("DELETE FROM historico_imagens WHERE alvo = ?", (alvo,))
    con.commit()
    con.close()


def data_legivel(epoch):
    return time.strftime("%d/%m/%Y às %H:%M", time.localtime(epoch))


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
    img.load()  # carrega agora: o arquivo de origem pode ser apagado logo depois
    return img


def salvar_imagem_portfolio(caminho_origem):
    """Copia a imagem escolhida para site/assets/img/portfolio. Devolve o nome do arquivo."""
    PORTFOLIO_IMG_DIR.mkdir(parents=True, exist_ok=True)
    nome = uuid.uuid4().hex
    img = _abrir_imagem_corrigida(caminho_origem, 1600)
    transparente = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    if transparente:
        nome += ".png"
        img.convert("RGBA").save(PORTFOLIO_IMG_DIR / nome, format="PNG", optimize=True)
    else:
        nome += ".jpg"
        img.convert("RGB").save(PORTFOLIO_IMG_DIR / nome, format="JPEG", quality=85, optimize=True)
    return nome


def remover_imagem_portfolio(nome):
    if not nome:
        return
    try:
        (PORTFOLIO_IMG_DIR / nome).unlink(missing_ok=True)
    except OSError:
        pass


def salvar_imagem_site(chave, caminho_origem, item_historico=None):
    """
    Troca uma das imagens fixas do site. A que estava no ar vai para o histórico.
    Se a nova vem do histórico (item_historico), ela sai de lá (troca de lugar com a atual).
    """
    slot = SLOTS_SITE[chave]
    destino = slot["arquivo"]
    destino.parent.mkdir(parents=True, exist_ok=True)
    img = _abrir_imagem_corrigida(caminho_origem, slot["max_lado"])   # já na memória
    if item_historico is not None:
        remover_do_historico(item_historico)
    arquivar_imagem(alvo_slot(chave), destino)
    if slot["formato"] == "PNG":
        img.convert("RGBA").save(destino, format="PNG", optimize=True)
    else:
        img.convert("RGB").save(destino, format="JPEG", quality=88, optimize=True, progressive=True)


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
        # só publica a foto se o arquivo existe (evita imagem quebrada no site)
        "imagem": ("assets/img/portfolio/" + p["imagem"])
        if p["imagem"] and (PORTFOLIO_IMG_DIR / p["imagem"]).exists() else None,
        "destaque": bool(p["destaque"]),
    } for p in linhas]

    JS_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    conteudo = (
        "// Gerado automaticamente pelo cms.py — não edite à mão.\n"
        "window.PORTFOLIO = " + json.dumps(dados, ensure_ascii=False, indent=2) + ";\n"
    )
    JS_DATA_PATH.write_text(conteudo, encoding="utf-8")


# =====================================================================
# Componentes visuais (os "elementos" do site, com cantos suaves)
# =====================================================================
def eyebrow(parent, texto, bg):
    """Rótulo pequeno com traço cobre à esquerda (.eyebrow)."""
    f = tk.Frame(parent, bg=bg)
    tk.Frame(f, bg=COBRE, width=32, height=2).pack(side="left", padx=(0, 12))
    tk.Label(f, text=espacar(texto), bg=bg, fg=AREIA, font=fonte("corpo", 8, "bold")).pack(side="left")
    return f


def logo(parent, bg, subtitulo="PAINEL"):
    """Logo do header (.nav__logo)."""
    f = tk.Frame(parent, bg=bg)
    tk.Label(f, text="MARCENARIA PAI & FILHO", bg=bg, fg=CREME, font=fonte("titulo", 14, "bold")).pack(anchor="w")
    tk.Label(f, text=espacar(subtitulo), bg=bg, fg=LOGO_SUB, font=fonte("corpo", 7)).pack(anchor="w", pady=(4, 0))
    return f


def numero_circulo(parent, n, bg):
    """Bolinha numerada da lista da lateral (.lateral__lista .num)."""
    c = tk.Canvas(parent, width=30, height=30, bg=bg, highlightthickness=0)
    c._img = forma(30, 30, 15, bg, misturar(bg, AREIA, 0.30))
    c.create_image(0, 0, anchor="nw", image=c._img)
    c.create_text(15, 15, text=str(n), fill=COBRE, font=fonte("serif", 10))
    return c


def rotulo_campo(parent, texto, bg=PRETO_CAFE):
    """Rótulo em caixa-alta pequena acima do campo (.campo label)."""
    tk.Label(
        parent, text=texto.upper(), bg=bg, fg=TEXTO_SUAVE, font=fonte("corpo", 8, "bold"), anchor="w"
    ).pack(anchor="w", pady=(0, 6))


def centralizar(janela, pai):
    janela.update_idletasks()
    w, h = janela.winfo_reqwidth(), janela.winfo_reqheight()
    x = pai.winfo_rootx() + (pai.winfo_width() - w) // 2
    y = pai.winfo_rooty() + (pai.winfo_height() - h) // 2
    janela.geometry("%dx%d+%d+%d" % (w, h, max(x, 0), max(y, 0)))


def cores_botao(estilo, bg):
    """(preenchimento, borda, texto, preenchimento_hover, borda_hover)"""
    if estilo == "primary":
        return OLIVA, OLIVA, CREME, OLIVA_CLARO, OLIVA_CLARO
    if estilo == "ghost":
        return bg, misturar(bg, AREIA, 0.40), AREIA, misturar(bg, AREIA, 0.10), AREIA
    if estilo == "soft":
        f, h = misturar(bg, AREIA, 0.07), misturar(bg, AREIA, 0.14)
        return f, f, AREIA, h, h
    if estilo == "danger":
        return ERRO, ERRO, PRETO_CAFE, "#D88C75", "#D88C75"
    if estilo == "danger_ghost":
        return bg, misturar(bg, ERRO, 0.50), ERRO, misturar(bg, ERRO, 0.12), ERRO
    if estilo == "aba":
        h = misturar(bg, AREIA, 0.08)
        return bg, bg, NAV_INATIVO, h, h
    if estilo == "aba_on":
        return OLIVA, OLIVA, CREME, OLIVA_CLARO, OLIVA_CLARO
    if estilo == "chip":
        f = misturar(bg, AREIA, 0.04)
        return f, misturar(bg, AREIA, 0.16), TEXTO_SUAVE, f, OLIVA_CLARO
    if estilo == "chip_on":
        return OLIVA, OLIVA_CLARO, CREME, OLIVA, OLIVA_CLARO
    raise ValueError(estilo)


class Botao(tk.Canvas):
    """Botão arredondado com hover (.btn do site, mais suave)."""

    def __init__(self, pai, texto, comando, estilo="primary", bg=PRETO_CAFE, pequeno=False,
                 pilula=False, maiusculo=True):
        self._fnt = tkfont.Font(font=fonte("corpo", 9 if pequeno else 10, "bold"))
        self._alt = 36 if pequeno else 44
        self._raio = self._alt // 2 if pilula else (10 if pequeno else 12)
        self._texto = texto.upper() if maiusculo else texto
        largura = self._fnt.measure(self._texto) + (2 * (18 if pequeno else 26))
        super().__init__(pai, width=largura, height=self._alt, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self._bgpai = bg
        self._estilo = estilo
        self._cmd = comando
        self._hover = False
        self._img = None
        self.bind("<Configure>", lambda e: self._desenhar(e.width))
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonRelease-1>", self._soltou)

    def definir_estilo(self, estilo):
        if estilo != self._estilo:
            self._estilo = estilo
            self._desenhar(self.winfo_width())

    def _set_hover(self, v):
        self._hover = v
        self._desenhar(self.winfo_width())

    def _soltou(self, e):
        if 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height() and self._cmd:
            self._cmd()

    def _desenhar(self, w):
        if w < 6:
            return
        fill, borda, fg, fill_h, borda_h = cores_botao(self._estilo, self._bgpai)
        if self._hover:
            fill, borda = fill_h, borda_h
        self.delete("all")
        self._img = forma(w, self._alt, self._raio, fill, borda, 1)
        self.create_image(0, 0, anchor="nw", image=self._img)
        self.create_text(w / 2, self._alt / 2, text=self._texto, fill=fg, font=self._fnt)


class Campo(tk.Canvas):
    """Campo de texto de uma linha com cantos arredondados (.campo do site)."""

    def __init__(self, pai, variavel, bg=PRETO_CAFE, senha=False, altura=46, largura=300):
        super().__init__(pai, width=largura, height=altura, bg=bg, highlightthickness=0, bd=0)
        self._alt = altura
        self._fill = NOGUEIRA if bg == PRETO_CAFE else PRETO_CAFE
        self._foco = False
        self._img = None
        self.entry = tk.Entry(
            self, textvariable=variavel, bg=self._fill, fg=TEXTO, insertbackground=TEXTO, relief="flat", bd=0,
            highlightthickness=0, font=fonte("corpo", 11), show="•" if senha else "",
            selectbackground=OLIVA, selectforeground=CREME,
        )
        self._win = self.create_window(16, altura // 2, window=self.entry, anchor="w")
        self.entry.bind("<FocusIn>", lambda e: self._set_foco(True))
        self.entry.bind("<FocusOut>", lambda e: self._set_foco(False))
        self.bind("<Configure>", lambda e: self._desenhar(e.width))
        self.bind("<Button-1>", lambda e: self.entry.focus_set())

    def _set_foco(self, v):
        self._foco = v
        self._desenhar(self.winfo_width())

    def _desenhar(self, w):
        if w < 40:
            return
        self.delete("fundo")
        borda = OLIVA_CLARO if self._foco else misturar(self._fill, AREIA, 0.16)
        self._img = forma(w, self._alt, 12, self._fill, borda, 2 if self._foco else 1)
        self.create_image(0, 0, anchor="nw", image=self._img, tags="fundo")
        self.tag_lower("fundo")
        self.itemconfigure(self._win, width=w - 32)


class CampoTexto(tk.Canvas):
    """Caixa de texto de várias linhas, arredondada."""

    def __init__(self, pai, linhas=4, bg=PRETO_CAFE, largura=300):
        altura = 28 + linhas * 24
        super().__init__(pai, width=largura, height=altura, bg=bg, highlightthickness=0, bd=0)
        self._alt = altura
        self._fill = NOGUEIRA if bg == PRETO_CAFE else PRETO_CAFE
        self._foco = False
        self._img = None
        self.texto = tk.Text(
            self, bg=self._fill, fg=TEXTO, insertbackground=TEXTO, relief="flat", bd=0, highlightthickness=0,
            wrap="word", font=fonte("corpo", 11), selectbackground=OLIVA, selectforeground=CREME, padx=0, pady=0,
        )
        self._win = self.create_window(16, 14, window=self.texto, anchor="nw")
        self.texto.bind("<FocusIn>", lambda e: self._set_foco(True))
        self.texto.bind("<FocusOut>", lambda e: self._set_foco(False))
        self.bind("<Configure>", lambda e: self._desenhar(e.width))
        self.bind("<Button-1>", lambda e: self.texto.focus_set())

    def _set_foco(self, v):
        self._foco = v
        self._desenhar(self.winfo_width())

    def _desenhar(self, w):
        if w < 40:
            return
        self.delete("fundo")
        borda = OLIVA_CLARO if self._foco else misturar(self._fill, AREIA, 0.16)
        self._img = forma(w, self._alt, 12, self._fill, borda, 2 if self._foco else 1)
        self.create_image(0, 0, anchor="nw", image=self._img, tags="fundo")
        self.tag_lower("fundo")
        self.itemconfigure(self._win, width=w - 32, height=self._alt - 28)

    def obter(self):
        return self.texto.get("1.0", "end").strip()

    def definir(self, valor):
        self.texto.delete("1.0", "end")
        self.texto.insert("1.0", valor)


class Chips(tk.Frame):
    """Escolha de uma opção entre várias (igual aos filtros do portfólio do site)."""

    def __init__(self, pai, opcoes, variavel, bg=PRETO_CAFE, colunas=3):
        super().__init__(pai, bg=bg)
        self._var = variavel
        self._botoes = {}
        for i, nome in enumerate(opcoes):
            b = Botao(self, nome, lambda n=nome: self._escolher(n), "chip", bg=bg, pequeno=True,
                      pilula=True, maiusculo=False)
            b.grid(row=i // colunas, column=i % colunas, sticky="w", padx=(0, 8), pady=(0, 8))
            self._botoes[nome] = b
        self._atualizar()

    def _escolher(self, nome):
        self._var.set(nome)
        self._atualizar()

    def _atualizar(self):
        for nome, b in self._botoes.items():
            b.definir_estilo("chip_on" if nome == self._var.get() else "chip")


class Interruptor(tk.Canvas):
    """Chave liga/desliga (no lugar da caixinha de marcar)."""

    def __init__(self, pai, texto, variavel, bg=PRETO_CAFE):
        self._fnt = tkfont.Font(font=fonte("corpo", 11))
        self._texto = texto
        largura = 46 + 12 + self._fnt.measure(texto)
        super().__init__(pai, width=largura, height=28, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self._var = variavel
        self._bgpai = bg
        self._imgs = []
        self.bind("<Button-1>", lambda e: self._alternar())
        self._desenhar()

    def _alternar(self):
        self._var.set(not self._var.get())
        self._desenhar()

    def _desenhar(self):
        self.delete("all")
        on = bool(self._var.get())
        trilho = forma(46, 26, 13, OLIVA if on else misturar(self._bgpai, AREIA, 0.12),
                       OLIVA_CLARO if on else misturar(self._bgpai, AREIA, 0.22))
        botao = forma(18, 18, 9, CREME if on else TEXTO_SUAVE)
        self._imgs = [trilho, botao]
        self.create_image(0, 1, anchor="nw", image=trilho)
        self.create_image(24 if on else 4, 5, anchor="nw", image=botao)
        self.create_text(58, 14, anchor="w", text=self._texto, fill=TEXTO, font=self._fnt)


class AreaRolavel(tk.Frame):
    """Área com rolagem vertical (barra fina que só aparece quando precisa)."""

    def __init__(self, pai, bg=PRETO_CAFE):
        super().__init__(pai, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.barra = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._rolagem)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.interno = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window(0, 0, window=self.interno, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.interno.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._barra_visivel = False

    def _rolagem(self, lo, hi):
        self.barra.set(lo, hi)
        precisa = not (float(lo) <= 0.0 and float(hi) >= 1.0)
        if precisa and not self._barra_visivel:
            self.barra.pack(side="right", fill="y", padx=(8, 0), before=self.canvas)
            self._barra_visivel = True
        elif not precisa and self._barra_visivel:
            self.barra.pack_forget()
            self._barra_visivel = False

    def rolar(self, passos):
        if self._barra_visivel:
            self.canvas.yview_scroll(passos, "units")

    def mostrar(self, widget):
        """Rola até o widget ficar visível."""
        self.update_idletasks()
        total = max(self.interno.winfo_height(), 1)
        topo = widget.winfo_y() / total
        base = (widget.winfo_y() + widget.winfo_height()) / total
        lo, hi = self.canvas.yview()
        if topo < lo:
            self.canvas.yview_moveto(topo)
        elif base > hi:
            self.canvas.yview_moveto(base - (hi - lo))


class PreviewImagem(tk.Canvas):
    """Mostra a imagem de um arquivo ocupando a largura disponível, mantendo a proporção."""

    def __init__(self, pai, caminho_fn, proporcao, bg=NOGUEIRA, raio=14, modo="contain", fundo=PRETO_CAFE):
        super().__init__(pai, height=100, bg=bg, highlightthickness=0, bd=0)
        self._caminho_fn = caminho_fn     # função: devolve o caminho ATUAL (relido a cada desenho)
        self._prop = proporcao
        self._raio = raio
        self._modo = modo
        self._fundo = fundo
        self._img = None
        self._larg = 0
        self.bind("<Configure>", lambda e: self._ao_config(e.width))

    def _ao_config(self, w):
        if w < 20:
            return
        self._larg = w
        h = int(w / self._prop)
        if int(self.cget("height")) != h:
            self.configure(height=h)
        self.atualizar()

    def atualizar(self):
        """Relê o arquivo do disco e redesenha (chamado depois de trocar a imagem)."""
        if self._larg < 20:
            return
        h = int(self._larg / self._prop)
        self.delete("all")
        self._img = miniatura(self._caminho_fn(), self._larg, h, self._raio, self._modo, self._fundo)
        self.create_image(0, 0, anchor="nw", image=self._img)


class Cartao(tk.Canvas):
    """Container com fundo arredondado e borda fina (.sobre__card). Coloque os widgets em `.interno`."""

    def __init__(self, pai, bg_pai=PRETO_CAFE, fill=NOGUEIRA, borda=LINHA, raio=RAIO_CARD, padx=22, pady=20,
                 largura=300):
        super().__init__(pai, width=largura, height=10, bg=bg_pai, highlightthickness=0, bd=0)
        self._fill, self._borda, self._raio = fill, borda, raio
        self._padx, self._pady = padx, pady
        self._img = None
        self.interno = tk.Frame(self, bg=fill)
        self._win = self.create_window(padx, pady, window=self.interno, anchor="nw")
        self._larg = 0
        self.bind("<Configure>", self._ao_config)
        self.interno.bind("<Configure>", self._ao_interno)

    def _ao_config(self, e):
        if e.width < 20:
            return
        self._larg = e.width
        self.itemconfigure(self._win, width=max(e.width - 2 * self._padx, 1))
        self.interno.update_idletasks()
        self._ao_interno(None)
        self._desenhar()

    def _ao_interno(self, e):
        precisa = self.interno.winfo_reqheight() + 2 * self._pady
        if int(self.cget("height")) != precisa:
            self.configure(height=precisa)

    def _desenhar(self):
        h = max(int(self.cget("height")), 4)
        self.delete("fundo")
        self._img = forma(self._larg, h, self._raio, self._fill, self._borda)
        self.create_image(0, 0, anchor="nw", image=self._img, tags="fundo")
        self.tag_lower("fundo")


class FaixaHistorico(tk.Frame):
    """As 5 imagens anteriores de um lugar. Clicar numa chama ao_escolher(item)."""

    TAM = 44

    def __init__(self, pai, alvo, ao_escolher, bg=NOGUEIRA):
        super().__init__(pai, bg=bg)
        self._alvo = alvo
        self._ao_escolher = ao_escolher
        self._bg = bg
        self._fotos = []
        self.recarregar()

    def recarregar(self):
        for w in self.winfo_children():
            w.destroy()
        self._fotos = []
        itens = listar_historico(self._alvo)
        tk.Label(
            self, text=espacar("Anteriores"), bg=self._bg, fg=TEXTO_SUAVE, font=fonte("corpo", 8, "bold"), anchor="w"
        ).pack(anchor="w", pady=(0, 8))
        if not itens:
            tk.Label(
                self, text="Quando você trocar a imagem, a anterior fica guardada aqui.",
                bg=self._bg, fg=TEXTO_SUAVE, font=fonte("corpo", 9), justify="left", anchor="w", wraplength=240,
            ).pack(anchor="w")
            return
        linha = tk.Frame(self, bg=self._bg)
        linha.pack(anchor="w")
        for item in itens:
            foto = miniatura(caminho_historico(item), self.TAM, self.TAM, 10, "cover", NOGUEIRA, gradiente=False)
            if foto is None:
                continue
            anel = forma(self.TAM, self.TAM, 10, None, OLIVA_CLARO, 2)
            self._fotos.extend([foto, anel])
            c = tk.Canvas(linha, width=self.TAM, height=self.TAM, bg=self._bg, highlightthickness=0, bd=0,
                          cursor="hand2")
            c.create_image(0, 0, anchor="nw", image=foto)
            c.pack(side="left", padx=(0, 8))
            c.bind("<Enter>", lambda e, c=c, a=anel: c.create_image(0, 0, anchor="nw", image=a, tags="anel"))
            c.bind("<Leave>", lambda e, c=c: c.delete("anel"))
            c.bind("<Button-1>", lambda e, it=item: self._ao_escolher(it))


# =====================================================================
# Caixa de mensagem no estilo do site (substitui os messagebox cinzas do sistema)
# =====================================================================
class Caixa(tk.Toplevel):
    """Modal igual ao .modal do site: fundo nogueira, borda fina, botões do tema."""

    def __init__(self, master, titulo, mensagem, tipo="info", rotulo_ok="OK", perigo=False, imagem=None):
        super().__init__(master, bg=LINHA)
        self.resultado = False
        self.title(titulo)
        self.resizable(False, False)
        self.transient(master)
        self._imagem = imagem

        corpo = tk.Frame(self, bg=NOGUEIRA)
        corpo.pack(fill="both", expand=True, padx=1, pady=1)
        if tipo == "erro":
            tk.Frame(corpo, bg=ERRO, width=3).pack(side="left", fill="y")

        conteudo = tk.Frame(corpo, bg=NOGUEIRA)
        conteudo.pack(fill="both", expand=True, padx=30, pady=26)
        tk.Label(
            conteudo, text=titulo, bg=NOGUEIRA, fg=AREIA, font=fonte("titulo", 15, "bold"), anchor="w",
        ).pack(anchor="w")
        if imagem is not None:
            tk.Label(conteudo, image=imagem, bg=NOGUEIRA, bd=0).pack(anchor="w", pady=(14, 0))
        tk.Label(
            conteudo, text=mensagem, bg=NOGUEIRA, fg=TEXTO_SUAVE, font=fonte("corpo", 11),
            justify="left", anchor="w", wraplength=380,
        ).pack(anchor="w", pady=(10, 24))

        botoes = tk.Frame(conteudo, bg=NOGUEIRA)
        botoes.pack(fill="x")
        self.btn_ok = Botao(botoes, rotulo_ok, self._ok, "danger" if perigo else "primary", bg=NOGUEIRA, pequeno=True)
        self.btn_ok.pack(side="right")
        if tipo == "confirma" or imagem is not None:
            Botao(botoes, "Cancelar", self.destroy, "ghost", bg=NOGUEIRA, pequeno=True).pack(
                side="right", padx=(0, 10))

        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self._ok())
        centralizar(self, master)
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass

    def _ok(self):
        self.resultado = True
        self.destroy()


def mostrar_caixa(master, titulo, mensagem, tipo="info", **kw):
    """tipo: 'info' | 'erro' | 'confirma'. Devolve True se o usuário confirmou."""
    dlg = Caixa(master, titulo, mensagem, tipo, **kw)
    master.wait_window(dlg)
    return dlg.resultado


def confirmar_volta_imagem(master, item, lugar):
    """Mostra a imagem guardada em tamanho maior e pergunta se quer voltar para ela."""
    foto = miniatura(caminho_historico(item), 380, 250, 14, "contain", NOGUEIRA, gradiente=False)
    return mostrar_caixa(
        master, "Voltar para esta imagem?",
        "Adicionada em %s.\n%s" % (data_legivel(item["criado_em"]), lugar),
        "confirma", rotulo_ok="Usar esta", imagem=foto,
    )


# =====================================================================
# Linha da lista de projetos (card clicável com a miniatura da foto atual)
# =====================================================================
class LinhaProjeto(tk.Canvas):
    ALTURA = 86

    def __init__(self, pai, projeto, ao_clicar, ao_duplo):
        super().__init__(pai, height=self.ALTURA, bg=PRETO_CAFE, highlightthickness=0, bd=0, cursor="hand2")
        self.p = projeto
        self.selecionada = False
        self._hover = False
        self._f_tit = tkfont.Font(font=fonte("corpo", 12, "bold"))
        self._f_cat = tkfont.Font(font=fonte("corpo", 8))
        self._f_badge = tkfont.Font(font=fonte("corpo", 8, "bold"))
        caminho = PORTFOLIO_IMG_DIR / projeto["imagem"] if projeto["imagem"] else None
        self._thumb = miniatura(caminho, 52, 64, 10, "cover")
        self._refs = []
        self.bind("<Configure>", lambda e: self.desenhar(e.width))
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Button-1>", lambda e: ao_clicar(projeto["id"]))
        self.bind("<Double-Button-1>", lambda e: ao_duplo())

    def definir_selecionada(self, v):
        if v != self.selecionada:
            self.selecionada = v
            self.desenhar(self.winfo_width())

    def _set_hover(self, v):
        self._hover = v
        self.desenhar(self.winfo_width())

    def desenhar(self, w):
        if w < 120:
            return
        H = self.ALTURA
        if self.selecionada:
            fill, borda = CARD_SEL, OLIVA_CLARO
        elif self._hover:
            fill, borda = CARD_HOVER, CASCA
        else:
            fill, borda = NOGUEIRA, LINHA
        self.delete("all")
        fundo = forma(w, H, 16, fill, borda, 1)
        self._refs = [fundo]
        self.create_image(0, 0, anchor="nw", image=fundo)
        if self._thumb:
            self.create_image(16, (H - 64) // 2, anchor="nw", image=self._thumb)

        x_texto = 16 + 52 + 18
        reserva = 120 if self.p["destaque"] else 20
        titulo = cortar(self.p["titulo"], self._f_tit, w - x_texto - reserva)
        self.create_text(x_texto, H / 2 - 9, anchor="w", text=titulo, fill=AREIA, font=self._f_tit)
        self.create_text(
            x_texto, H / 2 + 14, anchor="w", text=espacar(self.p["categoria"]), fill=TEXTO_SUAVE, font=self._f_cat
        )
        if self.p["destaque"]:
            texto = "NA HOME"
            bw = self._f_badge.measure(texto) + 26
            pilula = forma(bw, 26, 13, misturar(fill, OLIVA, 0.6), OLIVA_CLARO, 1)
            self._refs.append(pilula)
            self.create_image(w - 18 - bw, H / 2 - 13, anchor="nw", image=pilula)
            self.create_text(w - 18 - bw / 2, H / 2, text=texto, fill=CREME, font=self._f_badge)


class ChipUsuario(tk.Canvas):
    """Pílula do topo com a inicial e o nome de quem cadastrou o painel."""

    def __init__(self, pai, nome, comando, bg=NOGUEIRA):
        self._fnt = tkfont.Font(font=fonte("corpo", 10))
        self._nome = cortar(nome, self._fnt, 160)
        largura = 10 + 28 + 10 + self._fnt.measure(self._nome) + 18
        super().__init__(pai, width=largura, height=44, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self._bgpai = bg
        self._inicial = (nome.strip()[:1] or "?").upper()
        self._hover = False
        self._refs = []
        self._cmd = comando
        self.bind("<Enter>", lambda e: self._set(True))
        self.bind("<Leave>", lambda e: self._set(False))
        self.bind("<ButtonRelease-1>", lambda e: self._cmd())
        self._desenhar()

    def _set(self, v):
        self._hover = v
        self._desenhar()

    def _desenhar(self):
        w = int(self.cget("width"))
        self.delete("all")
        pilula = forma(w, 44, 22, misturar(self._bgpai, AREIA, 0.10 if self._hover else 0.05),
                       AREIA if self._hover else misturar(self._bgpai, AREIA, 0.22))
        avatar = forma(28, 28, 14, OLIVA, OLIVA_CLARO)
        self._refs = [pilula, avatar]
        self.create_image(0, 0, anchor="nw", image=pilula)
        self.create_image(8, 8, anchor="nw", image=avatar)
        self.create_text(22, 22, text=self._inicial, fill=CREME, font=fonte("corpo", 10, "bold"))
        self.create_text(46, 22, anchor="w", text=self._nome, fill=TEXTO, font=self._fnt)


# =====================================================================
# Diálogo: minha conta (nome e senha)
# =====================================================================
class ContaDialog(tk.Toplevel):
    def __init__(self, master, cadastro):
        super().__init__(master, bg=LINHA)
        self.resultado = None      # "salvo" | None
        self.title("Minha conta")
        self.resizable(False, False)
        self.transient(master)

        corpo = tk.Frame(self, bg=NOGUEIRA)
        corpo.pack(fill="both", expand=True, padx=1, pady=1)
        c = tk.Frame(corpo, bg=NOGUEIRA)
        c.pack(fill="both", expand=True, padx=30, pady=26)
        tk.Label(c, text="Minha conta", bg=NOGUEIRA, fg=AREIA, font=fonte("titulo", 15, "bold"), anchor="w").pack(
            anchor="w")
        tk.Label(
            c, text="Você entra com o e-mail abaixo. É para ele que vai o código se você esquecer a senha.",
            bg=NOGUEIRA, fg=TEXTO_SUAVE, font=fonte("corpo", 10), justify="left", anchor="w", wraplength=380,
        ).pack(anchor="w", pady=(10, 18))

        rotulo_campo(c, "E-mail", NOGUEIRA)
        tk.Label(c, text=cadastro["email"], bg=NOGUEIRA, fg=TEXTO, font=fonte("corpo", 11), anchor="w").pack(
            anchor="w", pady=(0, 16))

        self.var_nome = tk.StringVar(value=cadastro["nome"])
        rotulo_campo(c, "Nome", NOGUEIRA)
        Campo(c, self.var_nome, bg=NOGUEIRA, largura=380).pack(fill="x", pady=(0, 10))
        Botao(c, "Salvar nome", self._salvar_nome, "ghost", bg=NOGUEIRA, pequeno=True).pack(anchor="w")

        tk.Frame(c, bg=LINHA, height=1).pack(fill="x", pady=(20, 18))

        self.var_atual, self.var_nova, self.var_nova2 = tk.StringVar(), tk.StringVar(), tk.StringVar()
        rotulo_campo(c, "Senha atual", NOGUEIRA)
        Campo(c, self.var_atual, bg=NOGUEIRA, senha=True, largura=380).pack(fill="x", pady=(0, 12))
        rotulo_campo(c, "Nova senha (mín. %d caracteres)" % SENHA_MIN, NOGUEIRA)
        Campo(c, self.var_nova, bg=NOGUEIRA, senha=True, largura=380).pack(fill="x", pady=(0, 12))
        rotulo_campo(c, "Repita a nova senha", NOGUEIRA)
        Campo(c, self.var_nova2, bg=NOGUEIRA, senha=True, largura=380).pack(fill="x")

        self.lbl_msg = tk.Label(c, text="", bg=NOGUEIRA, fg=ERRO, font=fonte("corpo", 10), anchor="w",
                                justify="left", wraplength=380)
        self.lbl_msg.pack(anchor="w", pady=(8, 0))

        botoes = tk.Frame(c, bg=NOGUEIRA)
        botoes.pack(fill="x", pady=(14, 0))
        Botao(botoes, "Trocar senha", self._trocar_senha, "primary", bg=NOGUEIRA, pequeno=True).pack(side="right")
        Botao(botoes, "Fechar", self.destroy, "ghost", bg=NOGUEIRA, pequeno=True).pack(side="right", padx=(0, 10))

        self.bind("<Escape>", lambda e: self.destroy())
        centralizar(self, master)
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass

    def _msg(self, texto, ok=False):
        self.lbl_msg.configure(text=texto, fg=AREIA if ok else ERRO)

    def _salvar_nome(self):
        nome = self.var_nome.get().strip()
        if not nome:
            self._msg("Digite o seu nome.")
            return
        atualizar_nome(nome)
        self.resultado = "salvo"
        self._msg("Nome atualizado.", ok=True)

    def _trocar_senha(self):
        nova = self.var_nova.get()
        if len(nova) < SENHA_MIN:
            self._msg("A nova senha precisa ter pelo menos %d caracteres." % SENHA_MIN)
        elif nova != self.var_nova2.get():
            self._msg("As duas senhas novas precisam ser iguais.")
        elif not trocar_senha(self.var_atual.get(), nova):
            self._msg("A senha atual está incorreta.")
        else:
            self.var_atual.set("")
            self.var_nova.set("")
            self.var_nova2.set("")
            self._msg("Senha trocada.", ok=True)


# =====================================================================
# Diálogo: adicionar/editar projeto do portfólio
# =====================================================================
class ProjetoDialog(tk.Toplevel):
    PREV_W, PREV_H = 132, 165

    def __init__(self, master, projeto=None):
        super().__init__(master, bg=PRETO_CAFE)
        self.projeto = projeto  # sqlite3.Row ou None (projeto novo)
        self.resultado = False
        # mudança de foto ainda não salva: ("arquivo", caminho) | ("historico", item) | ("remover", None)
        self.pendente = None
        self._refs = []

        self.title("Editar projeto" if projeto else "Novo projeto")
        self.resizable(False, False)
        self.transient(master)

        # rodapé (empacotado primeiro pra nunca ser cortado)
        rodape = tk.Frame(self, bg=NOGUEIRA)
        rodape.pack(side="bottom", fill="x")
        tk.Frame(rodape, bg=LINHA, height=1).pack(fill="x")
        botoes = tk.Frame(rodape, bg=NOGUEIRA)
        botoes.pack(fill="x", padx=36, pady=16)
        Botao(botoes, "Salvar", self._salvar, "primary", bg=NOGUEIRA).pack(side="right")
        Botao(botoes, "Cancelar", self.destroy, "ghost", bg=NOGUEIRA).pack(side="right", padx=(0, 10))

        corpo = tk.Frame(self, bg=PRETO_CAFE)
        corpo.pack(fill="both", expand=True, padx=36, pady=(26, 22))

        # ---------------- coluna do formulário ----------------
        esq = tk.Frame(corpo, bg=PRETO_CAFE)
        esq.pack(side="left", anchor="n")
        eyebrow(esq, "Portfólio", PRETO_CAFE).pack(anchor="w")
        tk.Label(
            esq, text="Editar projeto" if projeto else "Novo projeto", bg=PRETO_CAFE, fg=AREIA,
            font=fonte("titulo", 22, "bold"),
        ).pack(anchor="w", pady=(2, 18))

        rotulo_campo(esq, "Título *")
        self.var_titulo = tk.StringVar(value=projeto["titulo"] if projeto else "")
        self.campo_titulo = Campo(esq, self.var_titulo, largura=440)
        self.campo_titulo.pack(fill="x", pady=(0, 16))

        rotulo_campo(esq, "Categoria *")
        atual = projeto["categoria"] if projeto else CATEGORIAS[0]
        opcoes = CATEGORIAS if atual in CATEGORIAS else CATEGORIAS + [atual]
        self.var_categoria = tk.StringVar(value=atual)
        Chips(esq, opcoes, self.var_categoria).pack(anchor="w", pady=(0, 8))

        rotulo_campo(esq, "Descrição *")
        self.campo_descricao = CampoTexto(esq, linhas=4, largura=440)
        self.campo_descricao.pack(fill="x", pady=(0, 18))
        if projeto:
            self.campo_descricao.definir(projeto["descricao"])

        self.var_destaque = tk.BooleanVar(value=bool(projeto["destaque"]) if projeto else False)
        Interruptor(esq, "Mostrar na Home (destaque)", self.var_destaque).pack(anchor="w")

        # ---------------- coluna da imagem ----------------
        dir_ = tk.Frame(corpo, bg=PRETO_CAFE)
        dir_.pack(side="left", anchor="n", padx=(34, 0))
        cartao = Cartao(dir_, PRETO_CAFE, largura=380, padx=22, pady=20)
        cartao.pack()
        c = cartao.interno
        eyebrow(c, "Imagem do projeto", NOGUEIRA).pack(anchor="w", pady=(0, 14))

        previews = tk.Frame(c, bg=NOGUEIRA)
        previews.pack(anchor="w")
        col1 = tk.Frame(previews, bg=NOGUEIRA)
        col1.pack(side="left")
        tk.Label(col1, text=espacar("Atual no site"), bg=NOGUEIRA, fg=TEXTO_SUAVE,
                 font=fonte("corpo", 7, "bold")).pack(anchor="w", pady=(0, 6))
        self.cv_atual = tk.Canvas(col1, width=self.PREV_W, height=self.PREV_H, bg=NOGUEIRA,
                                  highlightthickness=0, bd=0)
        self.cv_atual.pack()
        col2 = tk.Frame(previews, bg=NOGUEIRA)
        col2.pack(side="left", padx=(16, 0))
        self.lbl_nova = tk.Label(col2, text=espacar("Nova"), bg=NOGUEIRA, fg=TEXTO_SUAVE,
                                 font=fonte("corpo", 7, "bold"))
        self.lbl_nova.pack(anchor="w", pady=(0, 6))
        self.cv_nova = tk.Canvas(col2, width=self.PREV_W, height=self.PREV_H, bg=NOGUEIRA,
                                 highlightthickness=0, bd=0)
        self.cv_nova.pack()

        self.lbl_legenda = tk.Label(
            c, text="", bg=NOGUEIRA, fg=TEXTO_SUAVE, font=fonte("corpo", 9), justify="left", anchor="w",
            wraplength=280,
        )
        self.lbl_legenda.pack(anchor="w", pady=(10, 12))

        acoes = tk.Frame(c, bg=NOGUEIRA)
        acoes.pack(anchor="w")
        Botao(acoes, "Escolher imagem…", self._escolher_imagem, "ghost", bg=NOGUEIRA, pequeno=True).pack(side="left")
        Botao(acoes, "Remover foto", self._marcar_remover, "danger_ghost", bg=NOGUEIRA, pequeno=True).pack(
            side="left", padx=(10, 0))

        self.faixa = None
        if projeto:
            tk.Frame(c, bg=LINHA, height=1).pack(fill="x", pady=(18, 16))
            self.faixa = FaixaHistorico(c, alvo_projeto(projeto["id"]), self._escolher_do_historico)
            self.faixa.pack(anchor="w")

        self._desenhar_previews()
        centralizar(self, master)
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.campo_titulo.entry.focus_set()

    # ---------------- imagem ----------------
    def _caminho_atual(self):
        if self.projeto and self.projeto["imagem"]:
            return PORTFOLIO_IMG_DIR / self.projeto["imagem"]
        return None

    def _desenhar_previews(self):
        W, H = self.PREV_W, self.PREV_H
        atual = self._caminho_atual()
        tem_atual = bool(atual and atual.exists())
        self.cv_atual.delete("all")
        self._foto_atual = miniatura(atual, W, H, 14, "cover")
        self.cv_atual.create_image(0, 0, anchor="nw", image=self._foto_atual)

        self.cv_nova.delete("all")
        tipo, valor = self.pendente if self.pendente else (None, None)
        self.lbl_nova.configure(text=espacar("Nova (ao salvar)") if tipo else espacar("Nova"))
        if tipo == "arquivo":
            self._foto_nova = miniatura(valor, W, H, 14, "cover")
            legenda = "A imagem nova vai para o site quando você salvar."
        elif tipo == "historico":
            self._foto_nova = miniatura(caminho_historico(valor), W, H, 14, "cover")
            legenda = "Voltando para uma imagem anterior. Vale quando você salvar."
        elif tipo == "remover":
            self._foto_nova = miniatura(None, W, H, 14, "cover", gradiente=True)
            legenda = "A foto será removida ao salvar — o site mostra o fundo verde."
        else:
            self._foto_nova = forma(W, H, 14, misturar(NOGUEIRA, PRETO_CAFE, 0.5), misturar(NOGUEIRA, AREIA, 0.12))
            legenda = (
                "É a foto que está no site agora." if tem_atual
                else "Sem foto: o site mostra o fundo verde da peça."
            )
        self.cv_nova.create_image(0, 0, anchor="nw", image=self._foto_nova)
        if not tipo:
            self.cv_nova.create_text(W / 2, H / 2, text="Escolha uma\nimagem nova", fill=TEXTO_SUAVE,
                                     font=fonte("corpo", 9), justify="center")
        self.lbl_legenda.configure(text=legenda)

    def _escolher_imagem(self):
        caminho = filedialog.askopenfilename(
            title="Escolha a foto do projeto", filetypes=[("Imagens", "*.jpg *.jpeg *.png *.webp")],
        )
        if not caminho:
            return
        self.pendente = ("arquivo", caminho)
        self._desenhar_previews()

    def _escolher_do_historico(self, item):
        if confirmar_volta_imagem(self, item, "Ela vai ficar no lugar da foto atual deste projeto."):
            self.pendente = ("historico", item)
            self._desenhar_previews()

    def _marcar_remover(self):
        self.pendente = ("remover", None)
        self._desenhar_previews()

    # ---------------- salvar ----------------
    def _salvar(self):
        titulo = self.var_titulo.get().strip()
        categoria = self.var_categoria.get().strip()
        descricao = self.campo_descricao.obter()

        if not titulo:
            mostrar_caixa(self, "Faltou algo", "Dê um título ao projeto.", "erro")
            return
        if not categoria:
            mostrar_caixa(self, "Faltou algo", "Escolha uma categoria.", "erro")
            return
        if not descricao:
            mostrar_caixa(self, "Faltou algo", "Escreva uma descrição curta do projeto.", "erro")
            return

        con = conectar()
        if self.projeto is None:
            menor = con.execute("SELECT MIN(ordem) FROM projetos").fetchone()[0]
            ordem = (menor if menor is not None else 0) - 1
            cur = con.execute(
                "INSERT INTO projetos (titulo, descricao, categoria, imagem, destaque, ordem) "
                "VALUES (?, ?, ?, NULL, ?, ?)",
                (titulo, descricao, categoria, int(self.var_destaque.get()), ordem),
            )
            pid, imagem_atual = cur.lastrowid, None
        else:
            pid, imagem_atual = self.projeto["id"], self.projeto["imagem"]
            con.execute(
                "UPDATE projetos SET titulo=?, descricao=?, categoria=?, destaque=? WHERE id=?",
                (titulo, descricao, categoria, int(self.var_destaque.get()), pid),
            )
        con.commit()

        if self.pendente:
            tipo, valor = self.pendente
            novo = None
            try:
                if tipo == "arquivo":
                    novo = salvar_imagem_portfolio(valor)
                elif tipo == "historico":
                    novo = salvar_imagem_portfolio(caminho_historico(valor))
                    remover_do_historico(valor["id"])       # sai do histórico: virou a atual
            except Exception as erro:   # arquivo corrompido, formato estranho...
                con.close()
                mostrar_caixa(self, "Não consegui usar essa imagem", "Tente outra foto. (%s)" % erro, "erro")
                return
            if imagem_atual:                                # a que estava no ar vai pro histórico
                arquivar_imagem(alvo_projeto(pid), PORTFOLIO_IMG_DIR / imagem_atual)
                remover_imagem_portfolio(imagem_atual)
            con.execute("UPDATE projetos SET imagem = ? WHERE id = ?", (novo, pid))
            con.commit()
        con.close()

        gerar_portfolio_js()
        self.resultado = True
        self.destroy()


def info_arquivo(caminho):
    """'1920 × 1080 px · 277 KB' do arquivo que está no site agora."""
    try:
        caminho = Path(caminho)
        kb = caminho.stat().st_size / 1024
        with Image.open(caminho) as img:
            return "%d × %d px  ·  %s" % (img.width, img.height, ("%.0f KB" % kb) if kb < 1024 else ("%.1f MB" % (kb / 1024)))
    except Exception:
        return "arquivo não encontrado"


# =====================================================================
# Aplicativo principal (uma janela só, com telas que se alternam)
# =====================================================================
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CMS — Marcenaria Pai & Filho")
        self.root.geometry("1180x780")
        self.root.minsize(1000, 680)
        resolver_fontes(self.root)
        aplicar_tema(self.root)

        self.cadastro = None
        self._enviando = False
        self._falhas = 0
        self._bloqueado_ate = 0.0
        self._email_digitado = ""
        self.pagina = "portfolio"
        self.abas = {}
        self._area_rolavel = None
        self._sel_id = None
        self._linhas = {}
        self._card_img = None

        self.container = tk.Frame(self.root, bg=PRETO_CAFE)
        self.container.pack(fill="both", expand=True)

        self.root.bind_all("<MouseWheel>", self._roda)
        self.root.bind_all("<Button-4>", self._roda)
        self.root.bind_all("<Button-5>", self._roda)

        self._iniciar()
        self.root.mainloop()

    # ---------------- navegação ----------------
    def _limpar(self):
        self._area_rolavel = None
        for w in self.container.winfo_children():
            w.destroy()

    def _iniciar(self):
        """Sem cadastro: cria. Com cadastro: pede e-mail e senha."""
        self.cadastro = obter_cadastro()
        if self.cadastro is None:
            self._tela_cadastro()
        elif not self.cadastro["senha_hash"]:
            self._tela_definir_senha()     # cadastro feito na versão sem senha
        else:
            self._tela_login()

    def _roda(self, e):
        area = self._area_rolavel
        try:
            if area is None or not area.winfo_exists():
                return
            w = self.root.winfo_containing(e.x_root, e.y_root)
        except (KeyError, tk.TclError):
            return
        while w is not None and w is not area:
            w = w.master
        if w is None:
            return
        if getattr(e, "num", 0) == 4:
            area.rolar(-2)
        elif getattr(e, "num", 0) == 5:
            area.rolar(2)
        else:
            area.rolar(-2 if e.delta > 0 else 2)

    # ---------------- layout dividido (igual à página de orçamento do site) ----------------
    def _layout_dividido(self, titulo, texto, passos, eyebrow_txt, titulo_form, texto_form):
        """Lateral nogueira à esquerda (59%) + coluna do formulário à direita (41%)."""
        self._limpar()
        tela = tk.Frame(self.container, bg=PRETO_CAFE)
        tela.pack(fill="both", expand=True)
        tela.grid_columnconfigure(0, weight=59, uniform="col")
        tela.grid_columnconfigure(1, weight=41, uniform="col")
        tela.grid_rowconfigure(0, weight=1)

        # --- lateral
        lateral = tk.Frame(tela, bg=NOGUEIRA)
        lateral.grid(row=0, column=0, sticky="nsew")
        miolo = tk.Frame(lateral, bg=NOGUEIRA)
        miolo.pack(fill="both", expand=True, padx=60, pady=46)
        logo(miolo, NOGUEIRA).pack(side="top", anchor="w")
        tk.Label(
            miolo, text="Painel de controle do site da marcenaria.", bg=NOGUEIRA, fg=TEXTO_SUAVE,
            font=fonte("corpo", 10),
        ).pack(side="bottom", anchor="w")

        corpo = tk.Frame(miolo, bg=NOGUEIRA)
        corpo.pack(expand=True, anchor="w")
        tk.Label(
            corpo, text=titulo, bg=NOGUEIRA, fg=AREIA, font=fonte("corpo", 26, "bold"),
            justify="left", anchor="w", wraplength=400,
        ).pack(anchor="w")
        tk.Label(
            corpo, text=texto, bg=NOGUEIRA, fg=TEXTO_SUAVE, font=fonte("corpo", 12),
            justify="left", anchor="w", wraplength=360,
        ).pack(anchor="w", pady=(18, 30))
        for n, passo in enumerate(passos, start=1):
            linha = tk.Frame(corpo, bg=NOGUEIRA)
            linha.pack(anchor="w", pady=7)
            numero_circulo(linha, n, NOGUEIRA).pack(side="left", padx=(0, 14))
            tk.Label(
                linha, text=passo, bg=NOGUEIRA, fg=AREIA, font=fonte("corpo", 11),
                justify="left", anchor="w", wraplength=330,
            ).pack(side="left")

        # --- coluna do formulário
        coluna = tk.Frame(tela, bg=PRETO_CAFE)
        coluna.grid(row=0, column=1, sticky="nsew")
        form = tk.Frame(coluna, bg=PRETO_CAFE)
        form.place(relx=0.5, rely=0.5, anchor="center")

        eyebrow(form, eyebrow_txt, PRETO_CAFE).pack(anchor="w")
        tk.Label(form, text=titulo_form, bg=PRETO_CAFE, fg=AREIA, font=fonte("titulo", 24, "bold")).pack(
            anchor="w", pady=(2, 0)
        )
        tk.Label(form, text=texto_form, bg=PRETO_CAFE, fg=TEXTO_SUAVE, font=fonte("corpo", 11)).pack(
            anchor="w", pady=(8, 26)
        )
        return form

    def _campo(self, form, rotulo, variavel, senha=False):
        caixa = tk.Frame(form, bg=PRETO_CAFE)
        caixa.pack(fill="x", pady=(0, 16))
        rotulo_campo(caixa, rotulo)
        campo = Campo(caixa, variavel, senha=senha, largura=360)
        campo.pack(fill="x")
        return campo.entry

    # ---------------- pequenos auxiliares das telas de entrada ----------------
    def _link(self, form, texto, comando, pady=(16, 0)):
        lbl = tk.Label(form, text=texto, bg=PRETO_CAFE, fg=COBRE, font=fonte("corpo", 10, "underline"),
                       cursor="hand2")
        lbl.pack(anchor="w", pady=pady)
        lbl.bind("<Button-1>", lambda e: comando())
        return lbl

    def _lbl_erro(self, form):
        lbl = tk.Label(form, text="", bg=PRETO_CAFE, fg=ERRO, font=fonte("corpo", 10), anchor="w",
                       justify="left", wraplength=360)
        lbl.pack(anchor="w", pady=(0, 6))
        return lbl

    def _entrar_no_painel(self):
        self.cadastro = obter_cadastro()
        self._falhas = 0
        self._tela_painel()

    # ---------------- cadastro (primeira vez) ----------------
    def _tela_cadastro(self):
        form = self._layout_dividido(
            "Bem-vindo ao painel.",
            "É a primeira vez por aqui. Faça o cadastro e já comece a cuidar do site.",
            [
                "Informe seu nome, e-mail e uma senha.",
                "Daqui pra frente você entra com o e-mail e a senha.",
                "Se esquecer a senha, um código chega no seu e-mail.",
            ],
            "Primeiro acesso", "Criar cadastro", "Você só faz isso uma vez.",
        )
        _, email_antigo = dados_do_usuario_antigo()
        var_nome, var_email = tk.StringVar(), tk.StringVar(value=email_antigo)
        var_senha, var_senha2 = tk.StringVar(), tk.StringVar()
        ent_nome = self._campo(form, "Seu nome", var_nome)
        ent_email = self._campo(form, "E-mail", var_email)
        ent_senha = self._campo(form, "Senha (mín. %d caracteres)" % SENHA_MIN, var_senha, senha=True)
        ent_senha2 = self._campo(form, "Repita a senha", var_senha2, senha=True)
        ent_nome.focus_set()
        lbl_erro = self._lbl_erro(form)

        def criar(event=None):
            nome, email = var_nome.get().strip(), var_email.get().strip().lower()
            if not nome:
                lbl_erro.configure(text="Digite o seu nome.")
            elif not email_valido(email):
                lbl_erro.configure(text="Digite um e-mail válido: é nele que chega o código de recuperação.")
            elif len(var_senha.get()) < SENHA_MIN:
                lbl_erro.configure(text="A senha precisa ter pelo menos %d caracteres." % SENHA_MIN)
            elif var_senha.get() != var_senha2.get():
                lbl_erro.configure(text="As duas senhas precisam ser iguais.")
            else:
                criar_cadastro(nome, email, var_senha.get())
                self._entrar_no_painel()

        ent_nome.bind("<Return>", lambda e: ent_email.focus_set())
        ent_email.bind("<Return>", lambda e: ent_senha.focus_set())
        ent_senha.bind("<Return>", lambda e: ent_senha2.focus_set())
        ent_senha2.bind("<Return>", criar)
        Botao(form, "Criar cadastro", criar, "primary").pack(fill="x", pady=(4, 0))

    def _tela_definir_senha(self):
        """Cadastro que já existia (sem senha): define a senha uma vez e entra."""
        form = self._layout_dividido(
            "Agora o painel tem senha.",
            "O seu cadastro já existe. Falta escolher a senha para os próximos acessos.",
            [
                "Escolha uma senha com pelo menos %d caracteres." % SENHA_MIN,
                "Você entra com o e-mail %s." % self.cadastro["email"],
                "Se esquecer a senha, um código chega nesse e-mail.",
            ],
            "Segurança", "Criar senha", "Falta só isso.",
        )
        var_senha, var_senha2 = tk.StringVar(), tk.StringVar()
        ent_senha = self._campo(form, "Senha (mín. %d caracteres)" % SENHA_MIN, var_senha, senha=True)
        ent_senha2 = self._campo(form, "Repita a senha", var_senha2, senha=True)
        ent_senha.focus_set()
        lbl_erro = self._lbl_erro(form)

        def salvar(event=None):
            if len(var_senha.get()) < SENHA_MIN:
                lbl_erro.configure(text="A senha precisa ter pelo menos %d caracteres." % SENHA_MIN)
            elif var_senha.get() != var_senha2.get():
                lbl_erro.configure(text="As duas senhas precisam ser iguais.")
            else:
                definir_senha_do_cadastro(var_senha.get())
                self._entrar_no_painel()

        ent_senha.bind("<Return>", lambda e: ent_senha2.focus_set())
        ent_senha2.bind("<Return>", salvar)
        Botao(form, "Salvar senha", salvar, "primary").pack(fill="x", pady=(4, 0))

    # ---------------- login por e-mail ----------------
    def _tela_login(self):
        form = self._layout_dividido(
            "Gerencie o site da marcenaria.",
            "Portfólio e imagens num lugar só, sem precisar mexer em código.",
            [
                "Cadastre, edite e reordene os projetos do portfólio.",
                "Troque as imagens principais do site.",
                "Tudo é publicado sozinho no site.",
            ],
            "Acesso", "Entrar no painel", "Use o e-mail e a senha do seu cadastro.",
        )
        var_email, var_senha = tk.StringVar(), tk.StringVar()
        ent_email = self._campo(form, "E-mail", var_email)
        ent_senha = self._campo(form, "Senha", var_senha, senha=True)
        ent_email.focus_set()
        lbl_erro = self._lbl_erro(form)

        def entrar(event=None):
            self._email_digitado = var_email.get().strip()
            agora = time.time()
            if agora < self._bloqueado_ate:
                lbl_erro.configure(text="Muitas tentativas. Aguarde %d segundos." % (self._bloqueado_ate - agora + 1))
                return
            if autenticar(var_email.get(), var_senha.get()):
                self._entrar_no_painel()
                return
            self._falhas += 1
            if self._falhas >= LOGIN_MAX_FALHAS:
                self._falhas = 0
                self._bloqueado_ate = time.time() + LOGIN_TRAVA_SEG
                lbl_erro.configure(text="Muitas tentativas. Aguarde %d segundos." % LOGIN_TRAVA_SEG)
            else:
                lbl_erro.configure(text="E-mail ou senha incorretos.")
            var_senha.set("")

        ent_email.bind("<Return>", lambda e: ent_senha.focus_set())
        ent_senha.bind("<Return>", entrar)
        Botao(form, "Entrar", entrar, "primary").pack(fill="x", pady=(4, 0))
        self._link(form, "Esqueci minha senha", self._tela_esqueci_senha)

    # ---------------- esqueci minha senha (código por e-mail) ----------------
    def _enviar_codigo(self, email, ao_fim):
        """Envia o código sem travar a janela. ao_fim(True/False) roda quando termina."""
        if self._enviando:
            return
        self._enviando = True
        self.root.configure(cursor="watch")
        resultado = {}

        def trabalho():
            try:
                iniciar_recuperacao(email)
                resultado["ok"] = True
            except Exception as erro:      # volta pra thread principal, que mostra a mensagem
                resultado["erro"] = erro

        threading.Thread(target=trabalho, daemon=True).start()

        def checar():
            if not resultado:
                self.root.after(100, checar)
                return
            self._enviando = False
            self.root.configure(cursor="")
            erro = resultado.get("erro")
            if erro is None:
                ao_fim(True)
                return
            if isinstance(erro, EmailNaoConfigurado):
                mostrar_caixa(
                    self.root, "E-mail não configurado",
                    "Falta configurar a conta Gmail que envia o código. Crie o arquivo email_config.json "
                    "ao lado do cms.py (veja o modelo email_config.exemplo.json).", "erro")
            elif isinstance(erro, EnvioMuitoRapido):
                mostrar_caixa(
                    self.root, "Calma um instante",
                    "Um código acabou de ser enviado. Aguarde %d segundos para pedir outro." % erro.restam, "erro")
            elif isinstance(erro, smtplib.SMTPAuthenticationError):
                mostrar_caixa(
                    self.root, "Gmail recusou o login",
                    "Confira o remetente e a senha de app no email_config.json. "
                    "Precisa ser uma senha de app, não a senha normal da conta.", "erro")
            else:
                mostrar_caixa(
                    self.root, "Não consegui enviar",
                    "Não foi possível falar com o Gmail. Verifique a internet e tente de novo.", "erro")
            ao_fim(False)

        checar()

    def _tela_esqueci_senha(self):
        form = self._layout_dividido(
            "Esqueceu a senha?",
            "Sem problema. Enviamos um código de 6 dígitos para o e-mail do seu cadastro.",
            [
                "Digite o e-mail do seu cadastro.",
                "Abra o e-mail e copie o código.",
                "Escolha uma nova senha.",
            ],
            "Recuperação", "Esqueci minha senha", "Informe o e-mail para receber o código.",
        )
        var_email = tk.StringVar(value=self._email_digitado)
        ent = self._campo(form, "E-mail", var_email)
        ent.focus_set()

        def enviar(event=None):
            email = var_email.get().strip().lower()
            if not email_valido(email):
                mostrar_caixa(self.root, "E-mail inválido", "Digite um e-mail válido.", "erro")
                return

            def depois(ok):
                if ok:
                    mostrar_caixa(
                        self.root, "Código enviado",
                        "Se esse for o e-mail do painel, o código já está na caixa de entrada "
                        "(olhe o spam também). Ele vale por %d minutos." % CODIGO_VALIDADE_MIN)
                    self._tela_codigo(email)

            self._enviar_codigo(email, depois)

        ent.bind("<Return>", enviar)
        Botao(form, "Enviar código", enviar, "primary").pack(fill="x", pady=(4, 0))
        self._link(form, "Voltar ao login", self._tela_login)

    def _tela_codigo(self, email):
        form = self._layout_dividido(
            "Quase lá.",
            "Digite o código que chegou no e-mail e escolha a sua nova senha.",
            [
                "Copie o código de 6 dígitos do e-mail.",
                "Escolha uma senha com pelo menos %d caracteres." % SENHA_MIN,
                "Entre no painel com a nova senha.",
            ],
            "Recuperação", "Nova senha", "Código enviado para %s." % email,
        )
        var_codigo, var_senha, var_senha2 = tk.StringVar(), tk.StringVar(), tk.StringVar()
        ent_codigo = self._campo(form, "Código de 6 dígitos", var_codigo)
        self._campo(form, "Nova senha (mín. %d caracteres)" % SENHA_MIN, var_senha, senha=True)
        ent_senha2 = self._campo(form, "Repita a nova senha", var_senha2, senha=True)
        ent_codigo.focus_set()
        lbl_erro = self._lbl_erro(form)

        def redefinir(event=None):
            codigo, nova = var_codigo.get().strip(), var_senha.get()
            if not re.fullmatch(r"\d{6}", codigo):
                lbl_erro.configure(text="O código tem 6 números.")
            elif len(nova) < SENHA_MIN:
                lbl_erro.configure(text="A senha precisa ter pelo menos %d caracteres." % SENHA_MIN)
            elif nova != var_senha2.get():
                lbl_erro.configure(text="As duas senhas precisam ser iguais.")
            else:
                ok, erro = redefinir_senha_com_codigo(email, codigo, nova)
                if not ok:
                    lbl_erro.configure(text=erro)
                    return
                mostrar_caixa(self.root, "Senha alterada", "Pronto! Agora é só entrar com a nova senha.")
                self._tela_login()

        def reenviar():
            def depois(ok):
                if ok:
                    mostrar_caixa(self.root, "Código reenviado", "Se o e-mail for o do painel, chegou um código novo.")
            self._enviar_codigo(email, depois)

        ent_senha2.bind("<Return>", redefinir)
        Botao(form, "Redefinir senha", redefinir, "primary").pack(fill="x", pady=(4, 0))
        self._link(form, "Reenviar código", reenviar)
        self._link(form, "Voltar ao login", self._tela_login, pady=(8, 0))

    def _sair(self):
        self._tela_login()

    def _abrir_conta(self):
        dlg = ContaDialog(self.root, self.cadastro)
        self.root.wait_window(dlg)
        if dlg.resultado == "salvo":
            self.cadastro = obter_cadastro()
            self._tela_painel(self.pagina)

    # ---------------- painel principal ----------------
    def _tela_painel(self, pagina="portfolio"):
        self._limpar()
        self.tela = tk.Frame(self.container, bg=PRETO_CAFE)
        self.tela.pack(fill="both", expand=True)

        # topo (nogueira): navegação + título da página, como o .topo do portfólio
        self.topo = tk.Frame(self.tela, bg=NOGUEIRA)
        self.topo.pack(fill="x")
        self._montar_nav(self.topo)
        self.titulo_area = tk.Frame(self.topo, bg=NOGUEIRA)
        self.titulo_area.pack(fill="x", padx=48, pady=(26, 26))
        tk.Frame(self.tela, bg=LINHA_PRETO, height=1).pack(fill="x")

        # rodapé (.footer)
        rodape = tk.Frame(self.tela, bg=NOGUEIRA)
        rodape.pack(side="bottom", fill="x")
        tk.Label(
            rodape, text="© 2026 Marcenaria Pai & Filho", bg=NOGUEIRA, fg=TEXTO_SUAVE, font=fonte("corpo", 9)
        ).pack(side="left", padx=48, pady=14)
        tk.Label(
            rodape, text="painel de controle", bg=NOGUEIRA, fg=TEXTO_SUAVE, font=fonte("corpo", 9)
        ).pack(side="right", padx=48)

        self.corpo = tk.Frame(self.tela, bg=PRETO_CAFE)
        self.corpo.pack(fill="both", expand=True)

        self._abrir_pagina(pagina)

    def _montar_nav(self, pai):
        nav = tk.Frame(pai, bg=NOGUEIRA)
        nav.pack(fill="x", padx=48, pady=(26, 0))
        logo(nav, NOGUEIRA).pack(side="left")

        Botao(nav, "Sair", self._sair, "ghost", bg=NOGUEIRA, pequeno=True).pack(side="right", padx=(12, 0))
        ChipUsuario(nav, self.cadastro["nome"], self._abrir_conta).pack(side="right")

        abas = tk.Frame(nav, bg=NOGUEIRA)
        abas.pack(side="right", padx=(0, 22))
        self.abas = {}
        for chave, texto in (("portfolio", "Portfólio"), ("imagens", "Imagens do site")):
            b = Botao(abas, texto, lambda c=chave: self._abrir_pagina(c), "aba", bg=NOGUEIRA, pilula=True,
                      maiusculo=False)
            b.pack(side="left", padx=(0, 6))
            self.abas[chave] = b

    def _estilizar_nav(self):
        for chave, b in self.abas.items():
            b.definir_estilo("aba_on" if chave == self.pagina else "aba")

    def _abrir_pagina(self, pagina):
        self.pagina = pagina
        self._estilizar_nav()
        self._area_rolavel = None
        for w in list(self.titulo_area.winfo_children()) + list(self.corpo.winfo_children()):
            w.destroy()
        if pagina == "portfolio":
            self._pagina_portfolio()
        else:
            self._pagina_imagens()

    def _titulo_pagina(self, titulo, subtitulo):
        eyebrow(self.titulo_area, "Painel", NOGUEIRA).pack(anchor="w")
        tk.Label(
            self.titulo_area, text=titulo, bg=NOGUEIRA, fg=AREIA, font=fonte("titulo", 28, "bold")
        ).pack(anchor="w", pady=(2, 0))
        tk.Label(
            self.titulo_area, text=subtitulo, bg=NOGUEIRA, fg=TEXTO_SUAVE, font=fonte("corpo", 11),
            justify="left", anchor="w",
        ).pack(anchor="w", pady=(8, 0))

    # ---------------- página: portfólio (CRUD) ----------------
    def _pagina_portfolio(self):
        self._titulo_pagina(
            "Portfólio",
            "Adicione, edite e reordene as peças. Cada alteração já atualiza o site automaticamente.",
        )

        area = tk.Frame(self.corpo, bg=PRETO_CAFE)
        area.pack(fill="both", expand=True, padx=48, pady=(24, 24))
        area.grid_columnconfigure(0, weight=1)
        area.grid_rowconfigure(0, weight=1)

        esquerda = tk.Frame(area, bg=PRETO_CAFE)
        esquerda.grid(row=0, column=0, sticky="nsew")
        direita = tk.Frame(area, bg=PRETO_CAFE)
        direita.grid(row=0, column=1, sticky="n", padx=(36, 0))

        # barra de ações
        barra = tk.Frame(esquerda, bg=PRETO_CAFE)
        barra.pack(fill="x")
        Botao(barra, "Novo projeto", self._novo_projeto, "primary", pequeno=True).pack(side="left")
        Botao(barra, "Editar", self._editar_projeto, "ghost", pequeno=True).pack(side="left", padx=(10, 0))
        Botao(barra, "Excluir", self._excluir_projeto, "danger_ghost", pequeno=True).pack(side="left", padx=(10, 0))
        Botao(barra, "Mover ▼", lambda: self._mover_projeto(1), "soft", pequeno=True).pack(side="right")
        Botao(barra, "Mover ▲", lambda: self._mover_projeto(-1), "soft", pequeno=True).pack(
            side="right", padx=(0, 10))

        self.lbl_contagem = tk.Label(esquerda, text="", bg=PRETO_CAFE, fg=TEXTO_SUAVE, font=fonte("corpo", 10))
        self.lbl_contagem.pack(anchor="w", pady=(16, 10))

        self.lista = AreaRolavel(esquerda, PRETO_CAFE)
        self.lista.pack(fill="both", expand=True)
        self._area_rolavel = self.lista

        # pré-visualização no formato do card do site (.peca)
        eyebrow(direita, "Pré-visualização", PRETO_CAFE).pack(anchor="w", pady=(2, 14))
        self.canvas_card = tk.Canvas(
            direita, width=CARD_W, height=CARD_H, bg=PRETO_CAFE, highlightthickness=0, bd=0
        )
        self.canvas_card.pack(anchor="w")
        tk.Label(
            direita, text="Assim a peça aparece no site,\ncom a foto que está no ar agora.", bg=PRETO_CAFE,
            fg=TEXTO_SUAVE, font=fonte("corpo", 10), justify="left",
        ).pack(anchor="w", pady=(12, 0))

        self._carregar_projetos()

    def _desenhar_card(self, categoria, titulo, caminho_foto):
        c = self.canvas_card
        c.delete("all")
        self._card_img = fabricar_card(caminho_foto, (CARD_W, CARD_H))
        c.create_image(0, 0, anchor="nw", image=self._card_img)
        nome = c.create_text(
            20, CARD_H - 22, anchor="sw", text=titulo, fill=CREME, font=fonte("corpo", 14), width=CARD_W - 40,
        )
        if categoria:
            topo_nome = c.bbox(nome)[1]
            c.create_text(
                20, topo_nome - 6, anchor="sw", text=espacar(categoria), fill="#E6DFD3", font=fonte("corpo", 8),
            )

    def _ao_selecionar(self):
        if self._sel_id is None:
            self._desenhar_card("", "Selecione um projeto", None)
            return
        con = conectar()
        p = con.execute("SELECT * FROM projetos WHERE id = ?", (self._sel_id,)).fetchone()
        con.close()
        if p is None:
            self._sel_id = None
            self._desenhar_card("", "Selecione um projeto", None)
            return
        caminho = PORTFOLIO_IMG_DIR / p["imagem"] if p["imagem"] else None
        self._desenhar_card(p["categoria"], p["titulo"], caminho)

    def _carregar_projetos(self):
        for w in self.lista.interno.winfo_children():
            w.destroy()
        self._linhas = {}
        con = conectar()
        projetos = con.execute("SELECT * FROM projetos ORDER BY ordem, id").fetchall()
        con.close()
        for p in projetos:
            linha = LinhaProjeto(self.lista.interno, p, self._clicar_projeto, self._editar_projeto)
            linha.pack(fill="x", pady=(0, 10))
            self._linhas[p["id"]] = linha
        if self._sel_id not in self._linhas:
            self._sel_id = None
        for pid, linha in self._linhas.items():
            linha.definir_selecionada(pid == self._sel_id)
        n = len(projetos)
        self.lbl_contagem.configure(text="%d projeto%s" % (n, "" if n == 1 else "s"))
        self._ao_selecionar()

    def _clicar_projeto(self, pid):
        self._sel_id = pid
        for i, linha in self._linhas.items():
            linha.definir_selecionada(i == pid)
        self._ao_selecionar()

    def _projeto_selecionado_id(self):
        return self._sel_id

    def _novo_projeto(self):
        dlg = ProjetoDialog(self.root, projeto=None)
        self.root.wait_window(dlg)
        if dlg.resultado:
            self._carregar_projetos()

    def _editar_projeto(self):
        pid = self._projeto_selecionado_id()
        if pid is None:
            mostrar_caixa(self.root, "Selecione um projeto", "Clique num projeto da lista primeiro.")
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
            mostrar_caixa(self.root, "Selecione um projeto", "Clique num projeto da lista primeiro.")
            return
        con = conectar()
        projeto = con.execute("SELECT * FROM projetos WHERE id = ?", (pid,)).fetchone()
        if not mostrar_caixa(
            self.root, "Excluir projeto",
            'Excluir "%s"? Essa ação não pode ser desfeita.' % projeto["titulo"],
            "confirma", rotulo_ok="Excluir", perigo=True,
        ):
            con.close()
            return
        con.execute("DELETE FROM projetos WHERE id = ?", (pid,))
        con.commit()
        con.close()
        remover_imagem_portfolio(projeto["imagem"])
        apagar_historico_do_alvo(alvo_projeto(pid))
        self._sel_id = None
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
        if pid in self._linhas:
            self.lista.mostrar(self._linhas[pid])

    # ---------------- página: imagens do site ----------------
    def _pagina_imagens(self):
        self._titulo_pagina(
            "Imagens do site",
            "Cada cartão mostra a imagem que está no site agora. Ao trocar, a anterior fica guardada "
            "(as 5 últimas) pra você voltar quando quiser.",
        )

        rolavel = AreaRolavel(self.corpo, PRETO_CAFE)
        rolavel.pack(fill="both", expand=True, padx=38, pady=(22, 10))
        self._area_rolavel = rolavel

        self._prev_slots, self._info_slots, self._faixas_slots = {}, {}, {}
        grade = tk.Frame(rolavel.interno, bg=PRETO_CAFE)
        grade.pack(fill="x", anchor="n", pady=(4, 12))
        for col in range(len(SLOTS_SITE)):
            grade.grid_columnconfigure(col, weight=1, uniform="slot")

        for idx, (chave, slot) in enumerate(SLOTS_SITE.items()):
            cartao = Cartao(grade, PRETO_CAFE, largura=300, padx=22, pady=20)
            cartao.grid(row=0, column=idx, sticky="new", padx=10)
            c = cartao.interno

            cab = tk.Frame(c, bg=NOGUEIRA)
            cab.pack(fill="x")
            tk.Label(cab, text="%02d" % (idx + 1), bg=NOGUEIRA, fg=COBRE, font=fonte("serif", 12)).pack(anchor="w")
            tk.Label(
                cab, text=slot["rotulo"], bg=NOGUEIRA, fg=AREIA, font=fonte("corpo", 13, "bold"),
                justify="left", anchor="w", wraplength=250,
            ).pack(anchor="w", pady=(6, 2))
            tk.Label(
                cab, text=slot["onde"], bg=NOGUEIRA, fg=TEXTO_SUAVE, font=fonte("corpo", 10), anchor="w",
            ).pack(anchor="w")

            tk.Label(
                c, text=espacar("Atual no site"), bg=NOGUEIRA, fg=TEXTO_SUAVE, font=fonte("corpo", 7, "bold"),
            ).pack(anchor="w", pady=(16, 7))
            prev = PreviewImagem(c, lambda s=slot: s["arquivo"], 1.6, bg=NOGUEIRA, raio=14,
                                 modo="contain", fundo=PRETO_CAFE)
            prev.pack(fill="x")
            info = tk.Label(c, text=info_arquivo(slot["arquivo"]), bg=NOGUEIRA, fg=TEXTO_SUAVE,
                            font=fonte("corpo", 9), anchor="w")
            info.pack(anchor="w", pady=(8, 14))

            Botao(c, "Trocar imagem…", lambda ch=chave: self._trocar_imagem_site(ch), "primary", bg=NOGUEIRA,
                  pequeno=True).pack(anchor="w")

            tk.Frame(c, bg=LINHA, height=1).pack(fill="x", pady=(18, 16))
            faixa = FaixaHistorico(c, alvo_slot(chave), lambda item, ch=chave: self._voltar_imagem_site(ch, item))
            faixa.pack(anchor="w")

            self._prev_slots[chave], self._info_slots[chave], self._faixas_slots[chave] = prev, info, faixa

    def _atualizar_slot(self, chave):
        """Relê a imagem do disco: o cartão passa a mostrar a que está no site agora."""
        self._prev_slots[chave].atualizar()
        self._info_slots[chave].configure(text=info_arquivo(SLOTS_SITE[chave]["arquivo"]))
        self._faixas_slots[chave].recarregar()

    def _trocar_imagem_site(self, chave):
        caminho = filedialog.askopenfilename(
            title="Escolha a nova imagem", filetypes=[("Imagens", "*.jpg *.jpeg *.png *.webp")],
        )
        if not caminho:
            return
        try:
            salvar_imagem_site(chave, caminho)
        except Exception as erro:
            mostrar_caixa(self.root, "Não consegui usar essa imagem", "Tente outro arquivo. (%s)" % erro, "erro")
            return
        self._atualizar_slot(chave)
        mostrar_caixa(
            self.root, "Pronto",
            "“%s” atualizada. A imagem anterior ficou guardada em “Anteriores”." % SLOTS_SITE[chave]["rotulo"],
        )

    def _voltar_imagem_site(self, chave, item):
        slot = SLOTS_SITE[chave]
        if not confirmar_volta_imagem(
            self.root, item, "Ela vai ocupar o lugar de “%s”. A atual fica guardada." % slot["rotulo"]
        ):
            return
        try:
            salvar_imagem_site(chave, caminho_historico(item), item_historico=item["id"])
        except Exception as erro:
            mostrar_caixa(self.root, "Não consegui voltar a imagem", str(erro), "erro")
            return
        self._atualizar_slot(chave)


# =====================================================================
if __name__ == "__main__":
    if not TEM_PILLOW:
        _r = tk.Tk()
        _r.withdraw()
        from tkinter import messagebox
        messagebox.showerror("Falta o Pillow", "Instale com:\n\npip install pillow")
        raise SystemExit(1)
    preparar_banco()
    gerar_portfolio_js()  # garante que o site já tem o arquivo de dados na primeira vez
    App()
