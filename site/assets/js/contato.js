/* ===================================================================
   CONTATO.JS — validação simples e envio do formulário pelo WhatsApp

   Nada é enviado para nenhum servidor: o script monta um link
   "https://wa.me/<numero>?text=..." com a mensagem já pronta e abre
   essa conversa numa aba nova.
   =================================================================== */

(function () {
  // Número fixo do WhatsApp da marcenaria (com código do país 55).
  var NUMERO_WHATSAPP = "5511910538560";

  var form = document.getElementById("form-orcamento");
  var confirmacao = document.getElementById("confirmacao");
  var btnNovo = document.getElementById("btn-novo");
  var linkReabrir = document.getElementById("link-whatsapp-de-novo");

  function validarCampo(input) {
    var campoEl = input.closest(".campo");
    var valor = input.value.trim();
    var valido = true;

    if (input.hasAttribute("required") && !valor) valido = false;
    if (valido && input.name === "telefone") {
      valido = valor.replace(/\D/g, "").length >= 10;
    }

    campoEl.classList.toggle("invalido", !valido);
    return valido;
  }

  function montarMensagem(dados) {
    return [
      "Olá! Gostaria de solicitar um orçamento pelo site.",
      "",
      "Nome: " + dados.nome,
      "Telefone: " + dados.telefone,
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

    var campos = form.querySelectorAll("input, textarea");
    var tudoValido = true;
    campos.forEach(function (campo) {
      if (!validarCampo(campo)) tudoValido = false;
    });
    if (!tudoValido) {
      var primeiroInvalido = form.querySelector(".invalido input, .invalido textarea");
      if (primeiroInvalido) primeiroInvalido.focus();
      return;
    }

    var dados = Object.fromEntries(new FormData(form));
    var link = linkDoWhatsapp(montarMensagem(dados));

    linkReabrir.href = link;
    window.open(link, "_blank", "noopener");
    form.style.display = "none";
    confirmacao.classList.add("ativo");
  });

  form.querySelectorAll("input, textarea").forEach(function (campo) {
    campo.addEventListener("blur", function () {
      validarCampo(campo);
    });
  });

  btnNovo.addEventListener("click", function () {
    form.reset();
    form.querySelectorAll(".campo").forEach(function (c) {
      c.classList.remove("invalido");
    });
    confirmacao.classList.remove("ativo");
    form.style.display = "block";
  });
})();
