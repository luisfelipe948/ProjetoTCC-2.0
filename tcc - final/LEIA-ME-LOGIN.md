# Ligando o login do site (Firebase) — passo a passo

Tempo: uns 15 minutos. Custo: R$ 0 (o plano gratuito do Firebase cobre
login e este volume de uso).

## 1. Criar o projeto

1. Entre em https://console.firebase.google.com com uma conta Google.
2. **Adicionar projeto** → dê um nome (ex.: `marcenaria-pai-filho`) →
   pode desligar o Google Analytics → **Criar projeto**.

## 2. Registrar o site e pegar as chaves

1. Na tela inicial do projeto, clique no ícone **`</>` (Web)**.
2. Dê um apelido (ex.: `site`) e **Registrar app**. (Não precisa marcar
   Hosting agora.)
3. O Firebase mostra um bloco `const firebaseConfig = { ... }`. Copie os
   valores para o arquivo **`site/assets/js/firebase-config.js`**,
   trocando cada `COLE_AQUI`.

## 3. Ligar os tipos de login

Menu **Build → Authentication → Começar → Método de login**:

- **E-mail/senha** → Ativar → Salvar.
- **Google** → Ativar → escolha um e-mail de suporte → Salvar. (É só
  isso; o Google já fica funcionando.)
- **Facebook** → veja a seção 5 (dá um pouco mais de trabalho).

## 4. Autorizar o endereço do site

Em **Authentication → Configurações → Domínios autorizados**, confira
se aparecem:

- `localhost` (já vem) — para testar no seu computador;
- o endereço onde o site for publicado (ex.: `marcenariapaiefilho.com.br`).
  Se não aparecer, **Adicionar domínio**.

Sem isso o login com Google/Facebook mostra "este endereço não está
autorizado".

## 5. Facebook (só se for usar)

O Facebook exige um app próprio:

1. Entre em https://developers.facebook.com → **Meus apps → Criar app**
   (tipo "Consumidor" ou "Login do Facebook").
2. Em **Configurações → Básico**, copie **ID do app** e **Chave secreta**.
3. No Firebase, em **Authentication → Facebook**, cole os dois valores e
   copie a **URI de redirecionamento OAuth** que o Firebase mostra.
4. De volta ao app do Facebook: **Facebook Login → Configurações** →
   cole essa URI em **URIs de redirecionamento OAuth válidos** → Salvar.
5. Para pessoas comuns entrarem, o app precisa estar em modo **Ativo
   (Live)**; isso pede uma **Política de Privacidade** publicada (uma
   página simples no site já serve). Em modo desenvolvimento só você e
   quem você cadastrar como testador conseguem entrar.

Se preferir não usar Facebook agora, é só remover o botão
`btn-facebook` do `contato.html` (e a linha dele em `contato.js`).

## 6. Guardar o telefone no perfil (Firestore)

O telefone do perfil fica no Firestore (um banco do Firebase). Se você
**não** ligar o Firestore, o site continua funcionando: o telefone fica
guardado só naquele aparelho.

Para ligar: **Build → Firestore Database → Criar banco** (modo
produção, região `southamerica-east1`) → aba **Regras** → cole e
publique:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /usuarios/{uid} {
      allow read, write: if request.auth != null && request.auth.uid == uid;
    }
  }
}
```

Essas regras fazem cada pessoa só enxergar e mudar o próprio perfil.

## 7. Testar

```
cd site
python -m http.server 8000
```

Abra http://localhost:8000/contato.html, crie uma conta, mande um
orçamento de teste, abra **Meu perfil**, edite, saia, entre de novo e
por fim teste **Excluir perfil**.

## Observações

- As chaves do `firebase-config.js` podem ficar no código público; quem
  protege a conta são os domínios autorizados e as regras acima.
- A senha dos clientes nunca passa por este projeto: quem guarda é o
  Firebase.
- Para excluir a conta ou trocar a senha, o Firebase exige que a pessoa
  confirme a identidade de novo (senha ou janelinha do Google/Facebook).
  O site já faz isso.
- Para ver ou remover usuários à mão: **Authentication → Usuários**.
