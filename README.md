# CMS da Marcenaria Pai & Filho — versão simplificada

Nada de servidor, nada de HTTPS: é só um programa Python (`cms.py`) com
tela de login, que gerencia o portfólio e as imagens do site. O site em
si é HTML puro (pasta `site/`) e funciona sozinho, sem precisar do
programa rodando junto.

## Como usar

1. Instale o Python 3 (se ainda não tiver) e a única dependência:
   ```
   pip install pillow
   ```
2. Rode o painel:
   ```
   python cms.py
   ```
3. Na primeira vez, ele vai pedir pra você criar um usuário e senha.
   Depois disso, é só fazer login.

No painel dá pra:
- **Portfólio**: adicionar, editar, excluir e reordenar as peças (título,
  categoria, descrição, foto e se aparece em destaque na Home).
- **Imagens do site**: trocar a imagem principal do topo (computador e
  celular) e a ilustração da seção "Conheça nossos projetos".

Toda alteração no portfólio já atualiza automaticamente o arquivo
`site/assets/js/portfolio-data.js`, que é o que a Home e a página de
Portfólio leem — não precisa fazer mais nada.

## O site (pasta `site/`)

É HTML/CSS/JS puro. Pra ver como ficou, é só abrir `site/index.html` no
navegador, ou subir a pasta inteira em qualquer hospedagem simples
(não precisa de Python, banco de dados nem servidor rodando).

- `index.html` — Home
- `portfolio.html` — Portfólio completo, com filtro por categoria
- `contato.html` — Página de orçamento. Bem simples: nome, telefone e o
  que a pessoa precisa. Ao enviar, abre o WhatsApp já com a mensagem
  pronta, direto para o número **(11) 91053-8560**.

Pra trocar o número de WhatsApp, edite a constante `NUMERO_WHATSAPP` no
arquivo `site/assets/js/contato.js` (e o link que aparece na página em
`site/contato.html`).

## Onde fica tudo salvo

- `cms.db` — banco de dados local (SQLite), criado automaticamente na
  primeira vez que você roda `cms.py`. Nele ficam o usuário do painel e
  os projetos do portfólio.
- `site/assets/img/portfolio/` — fotos dos projetos.
- `site/assets/img/hero.jpg`, `hero-mobile.jpg`, `guarda_roupa.png` — as
  imagens do site que você troca pela aba "Imagens do site".

## O que foi simplificado em relação à versão anterior

- Sem Flask, sem servidor web, sem HTTPS — é um app de computador comum.
- Sem cadastro de categorias à parte: a categoria é escolhida numa lista
  fixa (Cozinha, Quarto, Sala, Escritório, Painel, Outro) na hora de
  criar/editar o projeto.
- Sem número de WhatsApp configurável pelo painel: fica fixo no código
  do site, já apontando pra (11) 91053-8560.
- Formulário de orçamento com só o essencial: nome, telefone e a
  descrição do que a pessoa precisa (antes tinha sobrenome, e-mail e
  tipo de projeto em campo separado).
