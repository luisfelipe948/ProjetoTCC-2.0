/* ===================================================================
   PORTFOLIO.JS — filtro por categoria e modal de detalhe da peça
   Usado apenas em portfolio.html
   =================================================================== */

(function () {
  // Dados de exemplo. Troque por dados reais (ou por uma chamada de API)
  // quando o back-end estiver pronto.
  var pecas = [
    { cat: "cozinha",    nome: "Cozinha Planejada", cor: "cor-cozinha",    desc: "Armários planejados com puxadores embutidos e bancada em quartzo." },
    { cat: "sala",       nome: "Apoio de TV",        cor: "cor-sala",       desc: "Painel ripado em madeira de demolição, com nicho para TV e som." },
    { cat: "quarto",     nome: "Guarda-Roupas",      cor: "cor-quarto",     desc: "Guarda-roupa de 3,20m com portas de correr e iluminação interna em LED." },
    { cat: "escritorio", nome: "Escrivaninha",       cor: "cor-escritorio", desc: "Bancada de trabalho com gaveteiro lateral, pensada para home office." },
    { cat: "cozinha",    nome: "Ilha Gourmet",       cor: "cor-cozinha",    desc: "Ilha central em madeira de demolição com tampo em granito preto." },
    { cat: "quarto",     nome: "Closet Planejado",   cor: "cor-quarto",     desc: "Closet em L com gaveteiro central e espelho embutido na porta." },
    { cat: "painel",     nome: "Painel Ripado",      cor: "cor-painel",     desc: "Revestimento ripado do piso ao teto, com iluminação embutida indireta." },
    { cat: "escritorio", nome: "Estante Modular",    cor: "cor-escritorio", desc: "Estante sob medida com módulos abertos e fechados, do piso ao teto." }
  ];

  var nomesCategoria = {
    cozinha: "Cozinha",
    quarto: "Quarto",
    sala: "Sala",
    escritorio: "Escritório",
    painel: "Painel"
  };

  var grid = document.getElementById("grid");
  var contagem = document.getElementById("contagem");
  var vazio = document.getElementById("vazio");
  var filtroAtual = "todos";

  function renderizar() {
    grid.innerHTML = "";
    var visiveis = pecas.filter(function (p) {
      return filtroAtual === "todos" || p.cat === filtroAtual;
    });

    visiveis.forEach(function (p, i) {
      var el = document.createElement("div");
      el.className = "peca " + p.cor;
      el.innerHTML =
        '<div class="peca__conteudo">' +
        '<div class="peca__cat">' + nomesCategoria[p.cat] + "</div>" +
        '<div class="peca__nome">' + p.nome + "</div>" +
        "</div>";
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

  document.getElementById("filtros").addEventListener("click", function (e) {
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

  function abrirModal(p) {
    document.getElementById("modal-topo").className = "modal__topo " + p.cor;
    document.getElementById("modal-cat").textContent = nomesCategoria[p.cat];
    document.getElementById("modal-nome").textContent = p.nome;
    document.getElementById("modal-desc").textContent = p.desc;
    modalFundo.classList.add("ativo");
  }

  document.getElementById("modal-fechar").addEventListener("click", function () {
    modalFundo.classList.remove("ativo");
  });
  modalFundo.addEventListener("click", function (e) {
    if (e.target === modalFundo) modalFundo.classList.remove("ativo");
  });

  renderizar();
})();
