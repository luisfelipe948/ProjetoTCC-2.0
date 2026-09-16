/* ===================================================================
   CONTATO.JS — validação de campos e fluxo de envio do formulário
   Usado apenas em contato.html
   =================================================================== */

(function () {
  var form = document.getElementById("form-orcamento");
  var wrap = document.getElementById("form-wrap");
  var confirmacao = document.getElementById("confirmacao");
  var btnNovo = document.getElementById("btn-novo");

  var validadores = {
    email: function (v) {
      return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim());
    },
    telefone: function (v) {
      return v.replace(/\D/g, "").length >= 10;
    }
  };

  function marcarErro(campoEl, comErro) {
    campoEl.classList.toggle("invalido", comErro);
  }

  function validarCampo(input) {
    var campoEl = input.closest(".campo");
    var valor = input.value.trim();
    var valido = true;

    if (input.hasAttribute("required") && !valor) valido = false;
    if (valido && validadores[input.name]) valido = validadores[input.name](valor);

    marcarErro(campoEl, !valido);
    return valido;
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var campos = form.querySelectorAll("input, select, textarea");
    var tudoValido = true;

    campos.forEach(function (campo) {
      if (!validarCampo(campo)) tudoValido = false;
    });

    if (!tudoValido) {
      var primeiroInvalido = form.querySelector(".invalido input, .invalido select, .invalido textarea");
      if (primeiroInvalido) primeiroInvalido.focus();
      return;
    }

    // ---------------------------------------------------------------
    // Ponto de integração com o back-end.
    // Quando a API existir, troque o bloco abaixo por algo como:
    //
    // fetch("/api/orcamentos", {
    //   method: "POST",
    //   headers: { "Content-Type": "application/json" },
    //   body: JSON.stringify(Object.fromEntries(new FormData(form)))
    // })
    //   .then(function (res) { if (!res.ok) throw new Error(); mostrarConfirmacao(); })
    //   .catch(function () { /* mostrar erro de envio */ });
    // ---------------------------------------------------------------
    mostrarConfirmacao();
  });

  function mostrarConfirmacao() {
    form.style.display = "none";
    confirmacao.classList.add("ativo");
  }

  form.querySelectorAll("input, select, textarea").forEach(function (campo) {
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
