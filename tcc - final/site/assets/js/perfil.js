/* ===================================================================
   PERFIL.JS — editar perfil, trocar senha, sair e excluir a conta
   Quem não está logado é mandado para a página de login (contato.html).
   =================================================================== */

import {
  aoMudarUsuario, atualizarPerfil, carregarPerfilExtra, perfilExtraLocal, provedores, primeiroNome,
  trocarSenha, excluirConta, sair, traduzirErro, usuarioAtual
} from "./auth.js";

function $(id) { return document.getElementById(id); }

var wrap = $("perfil-wrap");
var carregando = $("estado-carregando");
var erro = $("perfil-erro");
var ok = $("perfil-ok");
var formPerfil = $("form-perfil");
var formSenha = $("form-senha");
var modal = $("modal-excluir");
var usuario = null;
var provs = [];

function avisar(el, texto) {
  erro.hidden = true;
  ok.hidden = true;
  if (texto) { el.textContent = texto; el.hidden = false; window.scrollTo({ top: 0, behavior: "smooth" }); }
}

function nomeProvedor(p) {
  if (p === "google.com") return "Google";
  if (p === "facebook.com") return "Facebook";
  return "E-mail e senha";
}

function desenharLateral(user) {
  var av = $("perfil-avatar");
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
  $("perfil-nome").textContent = user.displayName || primeiroNome(user);
  $("perfil-email").textContent = user.email || "";
  var prov = $("perfil-prov");
  prov.textContent = "Entra com " + provs.map(nomeProvedor).join(" + ");
  prov.hidden = false;
}

function telefoneOk(v) { return v === "" || v.replace(/\D/g, "").length >= 10; }

formPerfil.addEventListener("submit", async function (e) {
  e.preventDefault();
  var nome = $("p-nome").value.trim();
  var tel = $("p-telefone").value.trim();
  var nomeValido = nome.length >= 2;
  var telValido = telefoneOk(tel);
  formPerfil.querySelector('[data-campo="nome"]').classList.toggle("invalido", !nomeValido);
  formPerfil.querySelector('[data-campo="telefone"]').classList.toggle("invalido", !telValido);
  if (!nomeValido || !telValido) return;

  var btn = $("btn-salvar-perfil");
  btn.disabled = true;
  try {
    await atualizarPerfil(nome, tel);
    usuario = usuarioAtual();
    desenharLateral(usuario);
    editado = false;
    avisar(ok, "Pronto! Seus dados foram atualizados.");
  } catch (err) {
    avisar(erro, traduzirErro(err));
  } finally {
    btn.disabled = false;
  }
});

formSenha.addEventListener("submit", async function (e) {
  e.preventDefault();
  var atual = $("s-atual").value;
  var nova = $("s-nova").value;
  formSenha.querySelector('[data-campo="atual"]').classList.toggle("invalido", !atual);
  formSenha.querySelector('[data-campo="nova"]').classList.toggle("invalido", nova.length < 6);
  if (!atual || nova.length < 6) return;

  var btn = $("btn-trocar-senha");
  btn.disabled = true;
  try {
    await trocarSenha(atual, nova);
    formSenha.reset();
    avisar(ok, "Senha trocada com sucesso.");
  } catch (err) {
    avisar(erro, traduzirErro(err));
  } finally {
    btn.disabled = false;
  }
});

$("btn-sair").addEventListener("click", async function () {
  document.documentElement.dataset.saindo = "1";
  await sair();
  location.href = "index.html";
});

/* ---------- excluir perfil ---------- */
var usaSenha = false;

$("btn-excluir").addEventListener("click", function () {
  $("modal-erro").hidden = true;
  $("excluir-senha").value = "";
  usaSenha = provs.indexOf("password") !== -1;
  $("campo-senha-excluir").hidden = !usaSenha;
  $("campo-senha-excluir").classList.remove("invalido");
  var social = !usaSenha;
  $("excluir-social").hidden = !social;
  if (social) $("excluir-social-nome").textContent = provs.map(nomeProvedor).join(" / ");
  modal.showModal();
});

$("excluir-cancelar").addEventListener("click", function () { modal.close(); });

$("form-excluir").addEventListener("submit", async function (e) {
  e.preventDefault();
  var senha = $("excluir-senha").value;
  if (usaSenha && !senha) {
    $("campo-senha-excluir").classList.add("invalido");
    $("excluir-senha").focus();
    return;
  }
  var btn = $("excluir-confirmar");
  btn.disabled = true;
  try {
    document.documentElement.dataset.saindo = "1";   // evita o redirecionamento ao login durante a exclusão
    await excluirConta(senha);
    modal.close();
    location.href = "index.html";
  } catch (err) {
    delete document.documentElement.dataset.saindo;
    var el = $("modal-erro");
    el.textContent = traduzirErro(err);
    el.hidden = false;
  } finally {
    btn.disabled = false;
  }
});

/* ---------- quem está aqui? ----------
   Desenha na hora com o que já sabemos deste aparelho ("guardado") e confirma com o Firebase
   ("firebase"). O telefone vem da cópia local e só depois é conferido no servidor, sem travar. */
var editado = false;      // a pessoa já mexeu nos campos: não sobrescrevemos o que ela digitou
var buscouServidor = {};
["p-nome", "p-telefone"].forEach(function (id) {
  $(id).addEventListener("input", function () { editado = true; });
});

aoMudarUsuario(function (user, origem) {
  if (!user) {
    // só o Firebase decide se não há login de verdade; o "palpite" vazio é ignorado
    if (origem === "firebase" && !document.documentElement.dataset.saindo) location.replace("contato.html#entrar");
    return;
  }
  usuario = user;
  provs = provedores(user);
  desenharLateral(user);
  $("cartao-senha").hidden = provs.indexOf("password") === -1;
  $("p-email").value = user.email || "";
  if (!editado) {
    $("p-nome").value = user.displayName || "";
    $("p-telefone").value = perfilExtraLocal(user.uid).telefone || "";
  }
  carregando.hidden = true;
  wrap.hidden = false;

  if (origem === "firebase" && !buscouServidor[user.uid]) {
    buscouServidor[user.uid] = true;
    carregarPerfilExtra(user.uid).then(function (extra) {
      if (!editado && usuario && usuario.uid === user.uid && extra && extra.telefone) {
        $("p-telefone").value = extra.telefone;
      }
    });
  }
});
