/* ===================================================================
   CONTATO.JS — login/cadastro e envio do orçamento pelo WhatsApp

   Fluxo da página:
     1. visitante  -> vê "Entrar / Criar conta" (e-mail e senha, Google, Facebook)
     2. logado     -> vê o formulário de orçamento (nome e e-mail vêm da conta)
     3. enviou     -> mensagem de confirmação

   Nada do orçamento passa por servidor: o script monta um link
   "https://wa.me/<numero>?text=..." com a mensagem pronta e abre o WhatsApp.
   =================================================================== */

import {
  configurado, aoMudarUsuario, entrarEmail, criarConta, entrarGoogle, entrarFacebook,
  recuperarSenha, sair, traduzirErro, carregarPerfilExtra, perfilExtraLocal, salvarPerfilExtra, primeiroNome
} from "./auth.js";

// Número fixo do WhatsApp da marcenaria (com código do país 55).
var NUMERO_WHATSAPP = "5511910538560";

function $(id) { return document.getElementById(id); }

var estados = {
  carregando: $("estado-carregando"),
  auth: $("painel-auth"),
  orcamento: $("form-orcamento"),
  confirmacao: $("confirmacao")
};

function mostrar(nome) {
  Object.keys(estados).forEach(function (k) {
    if (k === "confirmacao") estados[k].classList.toggle("ativo", k === nome);
    else estados[k].hidden = k !== nome;
  });
}

/* ===================================================================
   1) ENTRAR / CRIAR CONTA
   =================================================================== */
var modo = "entrar";                 // "entrar" | "criar"
var formAuth = $("form-auth");
var avisoErro = $("auth-erro");
var avisoOk = $("auth-ok");
var btnAuth = $("btn-auth");

function avisar(el, texto) {
  avisoErro.hidden = true;
  avisoOk.hidden = true;
  if (texto) { el.textContent = texto; el.hidden = false; }
}

function trocarAba(novo) {
  modo = novo;
  var criar = modo === "criar";
  $("aba-entrar").setAttribute("aria-selected", String(!criar));
  $("aba-criar").setAttribute("aria-selected", String(criar));
  $("linha-nome").hidden = !criar;
  $("auth-titulo").textContent = criar ? "Criar sua conta" : "Entrar na sua conta";
  $("auth-sub").textContent = criar
    ? "É rápido. Com a conta você acompanha seus dados e pede orçamentos quando quiser."
    : "Use o e-mail e a senha que você cadastrou.";
  btnAuth.textContent = criar ? "Criar conta" : "Entrar";
  $("auth-senha").setAttribute("autocomplete", criar ? "new-password" : "current-password");
  $("msg-senha").textContent = criar ? "A senha precisa ter pelo menos 6 caracteres." : "Digite a sua senha.";
  $("btn-esqueci").hidden = criar;
  formAuth.querySelectorAll(".campo").forEach(function (c) { c.classList.remove("invalido"); });
  avisar(null, "");
}

document.querySelectorAll("[data-aba]").forEach(function (b) {
  b.addEventListener("click", function () { trocarAba(b.dataset.aba); });
});

function emailOk(v) { return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v); }

function validarAuth() {
  var ok = true;
  function marcar(nome, valido) {
    formAuth.querySelector('[data-campo="' + nome + '"]').classList.toggle("invalido", !valido);
    if (!valido) ok = false;
  }
  if (modo === "criar") marcar("nome", $("auth-nome").value.trim().length >= 2);
  marcar("email", emailOk($("auth-email").value.trim()));
  var senha = $("auth-senha").value;
  marcar("senha", modo === "criar" ? senha.length >= 6 : senha.length > 0);
  if (!ok) {
    var primeiro = formAuth.querySelector(".invalido input");
    if (primeiro) primeiro.focus();
  }
  return ok;
}

function ocupado(v) {
  [btnAuth, $("btn-google"), $("btn-facebook")].forEach(function (b) { b.disabled = v; });
}

async function executar(acao) {
  avisar(null, "");
  if (!configurado) { $("aviso-config").hidden = false; return; }
  ocupado(true);
  try {
    await acao();           // se der certo, aoMudarUsuario troca a tela sozinho
  } catch (e) {
    avisar(avisoErro, traduzirErro(e));
  } finally {
    ocupado(false);
  }
}

formAuth.addEventListener("submit", function (e) {
  e.preventDefault();
  if (!validarAuth()) return;
  var email = $("auth-email").value.trim();
  var senha = $("auth-senha").value;
  executar(function () {
    return modo === "criar"
      ? criarConta($("auth-nome").value.trim(), email, senha)
      : entrarEmail(email, senha);
  });
});

formAuth.querySelectorAll("input").forEach(function (i) {
  i.addEventListener("input", function () {
    var c = i.closest(".campo");
    if (c) c.classList.remove("invalido");
  });
});

$("btn-google").addEventListener("click", function () { executar(entrarGoogle); });
$("btn-facebook").addEventListener("click", function () { executar(entrarFacebook); });

$("btn-esqueci").addEventListener("click", function () {
  var email = $("auth-email").value.trim();
  if (!emailOk(email)) {
    formAuth.querySelector('[data-campo="email"]').classList.add("invalido");
    $("auth-email").focus();
    avisar(avisoErro, "Digite o seu e-mail acima e toque de novo em “Esqueci minha senha”.");
    return;
  }
  executar(async function () {
    await recuperarSenha(email);
    avisar(avisoOk, "Se existir uma conta com esse e-mail, enviamos o link para criar uma nova senha.");
  });
});

/* ===================================================================
   2) FORMULÁRIO DE ORÇAMENTO (só aparece logado)
   =================================================================== */
var form = $("form-orcamento");
var linkReabrir = $("link-whatsapp-de-novo");
var usuario = null;

function preencherLogado(user) {
  var av = $("logado-avatar");
  av.replaceChildren();
  if (user.photoURL) {
    var img = document.createElement("img");
    img.src = user.photoURL;
    img.alt = "";
    img.referrerPolicy = "no-referrer";
    av.appendChild(img);
  } else {
    av.textContent = primeiroNome(user).charAt(0).toUpperCase();
  }
  $("logado-nome").textContent = user.displayName || primeiroNome(user);
  $("logado-email").textContent = user.email || "";
  $("form-ola").textContent = "Olá, " + primeiroNome(user) + "!";
}

function validarCampo(input) {
  var campoEl = input.closest(".campo");
  if (!campoEl) return true;
  var valor = input.value.trim();
  var valido = true;

  if (input.hasAttribute("required") && !valor) valido = false;
  if (valido && input.name === "telefone") {
    valido = valor.replace(/\D/g, "").length >= 10;
  }
  campoEl.classList.toggle("invalido", !valido);
  return valido;
}

function montarMensagem(dados, user) {
  return [
    "Olá! Gostaria de solicitar um orçamento pelo site.",
    "",
    "Nome: " + (user.displayName || primeiroNome(user)),
    "E-mail: " + (user.email || "—"),
    "Telefone: " + dados.telefone,
    "Ambiente: " + dados.ambiente,
    "",
    "O que preciso:",
    dados.descricao
  ].join("\n");
}

function linkDoWhatsapp(mensagem) {
  return "https://wa.me/" + NUMERO_WHATSAPP + "?text=" + encodeURIComponent(mensagem);
}

form.addEventListener("submit", function (e) {
  e.preventDefault();
  if (!usuario) return;

  var campos = form.querySelectorAll("input[name], select, textarea");
  var tudoValido = true;
  campos.forEach(function (campo) {
    if (!validarCampo(campo)) tudoValido = false;
  });
  if (!tudoValido) {
    var primeiroInvalido = form.querySelector(".invalido input, .invalido select, .invalido textarea");
    if (primeiroInvalido) primeiroInvalido.focus();
    return;
  }

  var dados = Object.fromEntries(new FormData(form));
  var link = linkDoWhatsapp(montarMensagem(dados, usuario));

  if ($("salvar-telefone").checked) {
    salvarPerfilExtra(usuario.uid, { telefone: dados.telefone.trim() });
  }

  linkReabrir.href = link;
  window.open(link, "_blank", "noopener");
  mostrar("confirmacao");
});

// Ao digitar/escolher, o erro some na hora. Ao sair do campo, só reclamamos se já tem algo
// escrito (ex.: telefone curto) — assim a mensagem de erro não some nem aparece no meio
// do clique no botão "Enviar" e empurra o botão pra longe do dedo.
form.querySelectorAll("input[name], select, textarea").forEach(function (campo) {
  var limpar = function () {
    var c = campo.closest(".campo");
    if (c && c.classList.contains("invalido")) validarCampo(campo);
  };
  campo.addEventListener("input", limpar);
  campo.addEventListener("change", limpar);
  campo.addEventListener("blur", function () {
    if (campo.value.trim()) validarCampo(campo);
  });
});

$("btn-novo").addEventListener("click", function () {
  form.querySelectorAll("select, textarea").forEach(function (c) { c.value = ""; });
  form.querySelectorAll(".campo").forEach(function (c) { c.classList.remove("invalido"); });
  mostrar("orcamento");
});

$("btn-sair-form").addEventListener("click", function () { sair(); });

/* ===================================================================
   3) QUEM ESTÁ NA PÁGINA?
   A tela aparece na hora, com o que já sabemos deste aparelho (origem "guardado"), e é
   confirmada pelo Firebase em seguida (origem "firebase"). Nada aqui espera pelo Firestore.
   =================================================================== */
var telefoneEditado = false;
var buscouServidor = {};
$("telefone").addEventListener("input", function () { telefoneEditado = true; });

aoMudarUsuario(function (user, origem) {
  var antes = usuario;
  usuario = user;

  if (!user) {
    if (antes) form.reset();
    telefoneEditado = false;
    $("aviso-config").hidden = configurado;
    if (estados.auth.hidden) trocarAba(location.hash === "#criar" ? "criar" : "entrar");
    mostrar("auth");
    return;
  }

  var vinhaDoLogin = !estados.auth.hidden;       // acabou de entrar nesta página
  preencherLogado(user);

  // telefone: primeiro a cópia deste aparelho (instantânea)
  var local = perfilExtraLocal(user.uid);
  if (local.telefone && !$("telefone").value && !telefoneEditado) $("telefone").value = local.telefone;

  if (!estados.confirmacao.classList.contains("ativo")) mostrar("orcamento");

  // entrou agora: já cai no orçamento, no topo e com o cursor no primeiro campo vazio
  if (vinhaDoLogin && origem === "firebase") {
    if (location.hash) history.replaceState(null, "", location.pathname);
    window.scrollTo(0, 0);
    ($("telefone").value ? $("ambiente") : $("telefone")).focus({ preventScroll: true });
  }

  // depois, sem travar nada, confere o telefone no servidor
  if (origem === "firebase" && !buscouServidor[user.uid]) {
    buscouServidor[user.uid] = true;
    carregarPerfilExtra(user.uid).then(function (extra) {
      if (usuario && usuario.uid === user.uid && extra && extra.telefone && !$("telefone").value && !telefoneEditado) {
        $("telefone").value = extra.telefone;
      }
    });
  }
});
