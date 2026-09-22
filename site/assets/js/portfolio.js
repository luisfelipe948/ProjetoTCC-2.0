/* ===================================================================
   PORTFOLIO.JS — filtro por categoria e modal de detalhe da peça
   Usado apenas em portfolio.html

   Os projetos vêm de assets/js/portfolio-data.js, um arquivo que o
   cms.py regrava toda vez que o portfólio é alterado no painel.
   Formato de cada peça:
     { id, titulo, descricao, cat (slug), catNome, imagem (url ou null), destaque }
   =================================================================== */

(function () {
  var pecas = window.PORTFOLIO || [];

  var grid = document.getElementById("grid");
  var contagem = document.getElementById("contagem");
  var vazio = document.getElementById("vazio");
  var filtros = document.getElementById("filtros");
  var filtroAtual = "todos";

  function criar(tag, classe, texto) {
    var el = document.createElement(tag);
    if (classe) el.className = classe;
    if (texto !== undefined) el.textContent = texto; // textContent: nunca interpreta HTML
    return el;
  }

  // Monta os botões de filtro a partir das categorias que existem nos dados.
  function montarFiltros() {
    var vistas = {};
    pecas.forEach(function (p) {
      if (!vistas[p.cat]) {
        vistas[p.cat] = p.catNome;
        var chip = criar("button", "chip", p.catNome);
        chip.dataset.filtro = p.cat;
        filtros.appendChild(chip);
      }
    });
  }

  function renderizar() {
    grid.innerHTML = "";
    var visiveis = pecas.filter(function (p) {
      return filtroAtual === "todos" || p.cat === filtroAtual;
    });

    visiveis.forEach(function (p, i) {
      var el = criar("div", "peca");

      if (p.imagem) {
        var foto = criar("img", "peca__img");
        foto.src = p.imagem;
        foto.alt = p.titulo;
        foto.loading = "lazy";
        el.appendChild(foto);
      }

      var conteudo = criar("div", "peca__conteudo");
      conteudo.appendChild(criar("div", "peca__cat", p.catNome));
      conteudo.appendChild(criar("div", "peca__nome", p.titulo));
      el.appendChild(conteudo);

      el.addEventListener("click", function () {
        abrirModal(p);
      });
      grid.appendChild(el);

      // Anima cada peça em cascata ao aparecer (na carga e a cada
      // troca de filtro). js/animacoes.js precisa estar carregado antes.
      if (window.ScrollReveal) {
        window.ScrollReveal.observe(el, Math.min(i * 0.06, 0.4) + "s");
      }
    });

    contagem.textContent =
      visiveis.length + (visiveis.length === 1 ? " projeto encontrado." : " projetos encontrados.");
    vazio.classList.toggle("ativo", visiveis.length === 0);
  }

  filtros.addEventListener("click", function (e) {
    var chip = e.target.closest(".chip");
    if (!chip) return;
    document.querySelectorAll(".chip").forEach(function (c) {
      c.classList.remove("ativo");
    });
    chip.classList.add("ativo");
    filtroAtual = chip.dataset.filtro;
    renderizar();
  });

  var modalFundo = document.getElementById("modal-fundo");
  var modalImg = document.getElementById("modal-img");

  function abrirModal(p) {
    if (p.imagem) {
      modalImg.src = p.imagem;
      modalImg.alt = p.titulo;
      modalImg.hidden = false;
    } else {
      modalImg.removeAttribute("src");
      modalImg.hidden = true;
    }
    document.getElementById("modal-cat").textContent = p.catNome;
    document.getElementById("modal-nome").textContent = p.titulo;
    document.getElementById("modal-desc").textContent = p.descricao;
    modalFundo.classList.add("ativo");
  }

  function fecharModal() {
    modalFundo.classList.remove("ativo");
  }

  document.getElementById("modal-fechar").addEventListener("click", fecharModal);
  modalFundo.addEventListener("click", function (e) {
    if (e.target === modalFundo) fecharModal();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") fecharModal();
  });

  montarFiltros();
  renderizar();
})();
