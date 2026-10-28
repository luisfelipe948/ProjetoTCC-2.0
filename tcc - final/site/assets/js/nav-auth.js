/* ===================================================================
   NAV-AUTH.JS — o botão "Entrar" / menu da conta no topo de todas as páginas

   Procura o <div data-conta> e mostra:
     - visitante:  botão "Entrar"
     - logado:     avatar + primeiro nome, com menu (Meu perfil, Sair)
   O estado "logado" aparece na hora (a partir do último usuário guardado
   neste aparelho) e é confirmado pelo Firebase logo em seguida.
   =================================================================== */

import { aoMudarUsuario, primeiroNome, sair } from "./auth.js";

var raiz = document.querySelector("[data-conta]");
var menu = null;
var botao = null;
var assinatura = "";      // evita redesenhar quando nada mudou

function el(tag, classe, texto) {
  var e = document.createElement(tag);
  if (classe) e.className = classe;
  if (texto !== undefined) e.textContent = texto;   // textContent: nome do usuário nunca vira HTML
  return e;
}

function avatar(user) {
  var a = el("span", "conta__avatar");
  if (user.photoURL) {
    var img = document.createElement("img");
    img.src = user.photoURL;
    img.alt = "";
    img.referrerPolicy = "no-referrer";
    a.appendChild(img);
  } else {
    a.textContent = primeiroNome(user).charAt(0).toUpperCase();
  }
  return a;
}

function abrir(v) {
  if (!menu || !botao) return;
  menu.hidden = !v;
  botao.setAttribute("aria-expanded", v ? "true" : "false");
}

function desenharVisitante() {
  if (assinatura === "visitante") return;
  assinatura = "visitante";
  menu = botao = null;
  raiz.replaceChildren();
  var a = el("a", "conta__entrar", "Entrar");
  a.href = "contato.html#entrar";
  raiz.appendChild(a);
}

function desenharLogado(user) {
  var nova = [user.uid, user.displayName, user.email, user.photoURL].join("|");
  if (assinatura === nova) return;
  assinatura = nova;
  raiz.replaceChildren();

  botao = el("button", "conta__btn");
  botao.type = "button";
  botao.setAttribute("aria-haspopup", "true");
  botao.setAttribute("aria-expanded", "false");
  botao.appendChild(avatar(user));
  botao.appendChild(el("span", "conta__nome", primeiroNome(user)));

  menu = el("div", "conta__menu");
  menu.hidden = true;
  var perfil = el("a", "", "Meu perfil");
  perfil.href = "perfil.html";
  var orcamento = el("a", "", "Pedir orçamento");
  orcamento.href = "contato.html";
  var fora = el("button", "conta__sair", "Sair");
  fora.type = "button";
  menu.append(perfil, orcamento, fora);

  botao.addEventListener("click", function (e) { e.stopPropagation(); abrir(menu.hidden); });
  fora.addEventListener("click", function () {
    document.documentElement.dataset.saindo = "1";      // a página de perfil não deve "expulsar" para o login
    sair().then(function () {
      if (/perfil\.html$/.test(location.pathname)) location.href = "index.html";
    });
  });

  raiz.append(botao, menu);
}

if (raiz) {
  // fechar o menu: registrado uma vez só, vale para qualquer redesenho
  document.addEventListener("click", function (e) { if (!raiz.contains(e.target)) abrir(false); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") abrir(false); });

  desenharVisitante();
  aoMudarUsuario(function (user) {
    if (user) desenharLogado(user); else desenharVisitante();
  });
}
