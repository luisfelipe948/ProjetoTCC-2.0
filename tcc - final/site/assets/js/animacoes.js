/* ===================================================================
   ANIMACOES.JS — animação de entrada (ao carregar a página) e ao
   rolar a tela. Compartilhado por index.html, portfolio.html e
   contato.html — carregue esse arquivo ANTES do script específico de
   cada página.

   Como usar:
   - Marque qualquer elemento com o atributo data-reveal no HTML.
   - Elementos que já aparecem na tela ao carregar a página (o hero,
     por exemplo) animam quase na hora — é o efeito de "entrada".
     Elementos mais abaixo animam conforme o usuário rola até eles.
   - Pra criar um efeito em cascata entre elementos vizinhos (ex: os
     3 cards de "Sobre Nós" aparecendo um depois do outro), defina
     --reveal-delay inline no HTML:
       <h3 data-reveal style="--reveal-delay: .12s">...</h3>
   - Páginas que criam elementos dinamicamente (o grid do portfólio)
     podem chamar window.ScrollReveal.observe(elemento, atraso) depois
     de inserir o elemento no DOM.
   =================================================================== */

(function () {
  var prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var supportsIO = "IntersectionObserver" in window;

  var observer = supportsIO
    ? new IntersectionObserver(
        function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting) {
              entry.target.classList.add("is-visible");
              observer.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.15, rootMargin: "0px 0px -6% 0px" }
      )
    : null;

  function revelar(el, atraso) {
    el.setAttribute("data-reveal", "");
    if (atraso) el.style.setProperty("--reveal-delay", atraso);

    if (prefersReduced || !observer) {
      el.classList.add("is-visible");
      return;
    }
    observer.observe(el);
  }

  // Elementos já marcados com data-reveal no HTML
  document.querySelectorAll("[data-reveal]").forEach(function (el) {
    revelar(el);
  });

  // API exposta pra scripts de página (ex: js/portfolio.js) registrarem
  // elementos criados dinamicamente depois que esta página já carregou.
  window.ScrollReveal = { observe: revelar };
})();
