/* ===================================================================
   NAV.JS — controla o menu hambúrguer no mobile.
   Carregue este arquivo em toda página que tenha um .nav com
   .nav__toggle e .nav__links (index.html, portfolio.html, contato.html).
   =================================================================== */

(function () {
  var toggle = document.querySelector(".nav__toggle");
  var links = document.querySelector(".nav__links");
  if (!toggle || !links) return;

  function fechar() {
    links.classList.remove("aberto");
    toggle.setAttribute("aria-expanded", "false");
  }

  function alternar() {
    var aberto = links.classList.toggle("aberto");
    toggle.setAttribute("aria-expanded", aberto ? "true" : "false");
  }

  toggle.addEventListener("click", function (e) {
    e.stopPropagation();
    alternar();
  });

  // Fecha o menu ao clicar em qualquer link dele
  links.querySelectorAll("a").forEach(function (a) {
    a.addEventListener("click", fechar);
  });

  // Fecha se clicar fora do menu
  document.addEventListener("click", function (e) {
    if (!links.contains(e.target) && !toggle.contains(e.target)) {
      fechar();
    }
  });

  // Fecha automaticamente se a tela for redimensionada para desktop
  window.addEventListener("resize", function () {
    if (window.innerWidth > 700) fechar();
  });

  // Fecha com a tecla Esc
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") fechar();
  });
})();
