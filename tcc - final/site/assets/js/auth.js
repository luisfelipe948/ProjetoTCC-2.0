/* ===================================================================
   AUTH.JS — login, cadastro e perfil (Firebase Authentication)

   O site é HTML puro, sem servidor próprio. Para ter conta de usuário de
   verdade (e-mail + senha, Google, Facebook) usamos o Firebase, que cuida
   de guardar senha com segurança e de falar com Google/Facebook.

   Este arquivo é o único que conversa com o Firebase. As páginas só
   importam as funções daqui:  import { entrarEmail, sair } from "./auth.js"

   Dados do perfil:
     - nome, e-mail e foto ficam na própria conta do Firebase;
     - telefone fica no Firestore, em usuarios/{uid}, e também numa cópia
       local (localStorage) para aparecer na hora.

   Velocidade (o que este arquivo faz para as páginas abrirem rápido):
     1. começa a baixar o Firebase assim que a página abre;
     2. guarda uma "foto" do último usuário (nome, e-mail, foto) e mostra
        a tela de logado NA HORA, enquanto o Firebase confirma por trás;
     3. o Firestore (pesado) só é carregado quando precisa, e nenhuma tela
        espera por ele: o telefone aparece da cópia local e é atualizado
        em seguida, se houver novidade.
   =================================================================== */

import { firebaseConfig } from "./firebase-config.js";

const V = "10.14.1";
const CDN = "https://www.gstatic.com/firebasejs/" + V + "/";

export const configurado =
  !!firebaseConfig.apiKey && firebaseConfig.apiKey.indexOf("COLE_AQUI") === -1;

let A = null;          // módulo firebase-auth
let FS = null;         // módulo firebase-firestore (só se precisar)
let appInst = null;
let auth = null;
let db = null;
let promAuth = null;
let promDb = null;

/* ---------- carregamento do Firebase ---------- */
function iniciarAuth() {
  if (!configurado) return Promise.reject(new Error("nao-configurado"));
  if (!promAuth) {
    promAuth = Promise.all([import(CDN + "firebase-app.js"), import(CDN + "firebase-auth.js")])
      .then(function (m) {
        appInst = m[0].initializeApp(firebaseConfig);
        A = m[1];
        auth = A.getAuth(appInst);
        auth.languageCode = "pt-BR";
        return A;
      });
  }
  return promAuth;
}

function iniciarDb() {
  if (!promDb) {
    promDb = Promise.all([iniciarAuth(), import(CDN + "firebase-firestore.js")]).then(function (m) {
      FS = m[1];
      db = FS.getFirestore(appInst);
      return FS;
    });
  }
  return promDb;
}

// começa a baixar já, em paralelo com o resto da página
if (configurado) iniciarAuth().catch(function () {});

function comTempo(promessa, ms) {
  return new Promise(function (resolve, reject) {
    var t = setTimeout(function () { reject(new Error("tempo-esgotado")); }, ms);
    promessa.then(function (v) { clearTimeout(t); resolve(v); }, function (e) { clearTimeout(t); reject(e); });
  });
}

/* Espera o Firebase terminar de ler a sessão salva e devolve o usuário atual. */
async function pronto() {
  const m = await iniciarAuth();
  await auth.authStateReady();
  return { m: m, user: auth.currentUser };
}

/* ---------- mensagens de erro em português ---------- */
var ERROS = {
  "auth/invalid-credential": "E-mail ou senha incorretos.",
  "auth/wrong-password": "E-mail ou senha incorretos.",
  "auth/user-not-found": "E-mail ou senha incorretos.",
  "auth/invalid-email": "Esse e-mail não parece válido.",
  "auth/email-already-in-use": "Já existe uma conta com esse e-mail. Tente entrar.",
  "auth/weak-password": "A senha precisa ter pelo menos 6 caracteres.",
  "auth/missing-password": "Digite a sua senha.",
  "auth/too-many-requests": "Muitas tentativas. Aguarde um pouco e tente de novo.",
  "auth/network-request-failed": "Sem conexão com a internet. Tente de novo.",
  "auth/popup-closed-by-user": "A janela de login foi fechada antes de terminar.",
  "auth/cancelled-popup-request": "A janela de login foi fechada antes de terminar.",
  "auth/popup-blocked": "O navegador bloqueou a janela de login. Libere pop-ups para este site.",
  "auth/account-exists-with-different-credential":
    "Já existe uma conta com esse e-mail usando outro método. Entre pelo método original.",
  "auth/operation-not-allowed": "Esse método de login ainda não foi ativado no Firebase.",
  "auth/unauthorized-domain": "Este endereço não está autorizado no Firebase (veja o LEIA-ME-LOGIN).",
  "auth/requires-recent-login": "Por segurança, confirme a sua identidade e tente de novo.",
  "auth/user-disabled": "Esta conta foi desativada."
};

export function traduzirErro(e) {
  var code = e && e.code;
  return ERROS[code] || "Não deu certo. Tente de novo em instantes.";
}

/* ---------- "foto" do último usuário (só para desenhar a tela rápido) ----------
   Guarda apenas nome, e-mail e foto. Não dá acesso a nada: tudo o que mexe na conta
   continua passando pelo Firebase, que confirma a sessão de verdade em seguida. */
var CHAVE_USUARIO = "auth:ultimo";

function guardarUsuario(user) {
  try {
    if (!user) { localStorage.removeItem(CHAVE_USUARIO); return; }
    localStorage.setItem(CHAVE_USUARIO, JSON.stringify({
      uid: user.uid, displayName: user.displayName || null, email: user.email || null,
      photoURL: user.photoURL || null,
      providers: (user.providerData || []).map(function (p) { return p.providerId; })
    }));
  } catch (e) {}
}

function lerUsuarioGuardado() {
  try {
    var d = JSON.parse(localStorage.getItem(CHAVE_USUARIO));
    if (d && d.uid) {
      return {
        uid: d.uid, displayName: d.displayName, email: d.email, photoURL: d.photoURL,
        providerData: (d.providers || []).map(function (p) { return { providerId: p }; })
      };
    }
  } catch (e) {}
  return null;
}

/* ---------- estado do usuário ----------
   callback(user, origem)
     origem "guardado": palpite imediato (vem da "foto" salva neste aparelho);
     origem "firebase": resposta confirmada pelo Firebase.
   Quem usa deve tratar "guardado" só como aparência; ações importantes esperam "firebase". */
var ouvintes = [];
var criando = false;      // durante o cadastro, esperamos o nome ser gravado antes de avisar a tela

function notificar() {
  var user = auth ? auth.currentUser : null;
  guardarUsuario(user);
  ouvintes.forEach(function (f) { f(user, "firebase"); });
}

export function aoMudarUsuario(callback) {
  if (!configurado) { callback(null, "firebase"); return; }
  ouvintes.push(callback);
  callback(lerUsuarioGuardado(), "guardado");     // aparece na hora
  iniciarAuth().then(function (m) {
    m.onAuthStateChanged(auth, function (user) {
      if (criando) return;
      guardarUsuario(user);
      callback(user, "firebase");
    });
  }).catch(function () { callback(null, "firebase"); });
}

export function usuarioAtual() { return auth ? auth.currentUser : null; }

export function provedores(user) {
  return (user && user.providerData ? user.providerData : []).map(function (p) { return p.providerId; });
}

export function primeiroNome(user) {
  var nome = (user && user.displayName) || "";
  return nome.trim().split(/\s+/)[0] || (user && user.email ? user.email.split("@")[0] : "Conta");
}

/* ---------- entrar / criar conta ---------- */
export async function entrarEmail(email, senha) {
  const m = await iniciarAuth();
  return m.signInWithEmailAndPassword(auth, email, senha);
}

export async function criarConta(nome, email, senha) {
  const m = await iniciarAuth();
  criando = true;
  try {
    const cred = await m.createUserWithEmailAndPassword(auth, email, senha);
    await m.updateProfile(cred.user, { displayName: nome });
    return cred;
  } finally {
    criando = false;
    notificar();           // agora a tela já recebe o nome certo, sem piscar o e-mail
  }
}

export async function entrarGoogle() {
  const m = await iniciarAuth();
  const p = new m.GoogleAuthProvider();
  p.setCustomParameters({ prompt: "select_account" });
  return m.signInWithPopup(auth, p);
}

export async function entrarFacebook() {
  const m = await iniciarAuth();
  const p = new m.FacebookAuthProvider();
  p.addScope("email");
  return m.signInWithPopup(auth, p);
}

export async function recuperarSenha(email) {
  const m = await iniciarAuth();
  return m.sendPasswordResetEmail(auth, email);
}

export async function sair() {
  const m = await iniciarAuth();
  guardarUsuario(null);
  return m.signOut(auth);
}

/* ---------- perfil (telefone) ---------- */
function chaveLocal(uid) { return "perfil:" + uid; }

/* Cópia local: instantânea. É a que as telas mostram primeiro. */
export function perfilExtraLocal(uid) {
  try { return JSON.parse(localStorage.getItem(chaveLocal(uid))) || {}; } catch (e) { return {}; }
}

function guardarLocal(uid, dados) {
  try { localStorage.setItem(chaveLocal(uid), JSON.stringify(Object.assign(perfilExtraLocal(uid), dados))); } catch (e) {}
}

/* Versão do servidor (Firestore). Nunca trava a tela: tem limite de tempo e cai na cópia local. */
export async function carregarPerfilExtra(uid) {
  try {
    const fs = await comTempo(iniciarDb(), 6000);
    const snap = await comTempo(fs.getDoc(fs.doc(db, "usuarios", uid)), 4000);
    if (snap.exists()) {
      var d = snap.data();
      guardarLocal(uid, d);
      return d;
    }
  } catch (e) { /* Firestore desligado ou lento: segue com o que já temos aqui */ }
  return perfilExtraLocal(uid);
}

export async function salvarPerfilExtra(uid, dados) {
  guardarLocal(uid, dados);                    // na hora, no aparelho
  try {
    const fs = await comTempo(iniciarDb(), 6000);
    await comTempo(fs.setDoc(fs.doc(db, "usuarios", uid), dados, { merge: true }), 8000);
  } catch (e) { /* fica pelo menos no aparelho */ }
}

export async function atualizarPerfil(nome, telefone) {
  const p = await pronto();
  const user = p.user;
  if (nome !== undefined && nome !== user.displayName) {
    await p.m.updateProfile(user, { displayName: nome });
    notificar();
  }
  if (telefone !== undefined) await salvarPerfilExtra(user.uid, { telefone: telefone });
  return user;
}

/* Confirma a identidade de novo (o Firebase exige isso para trocar senha e excluir conta). */
export async function reautenticar(senhaAtual) {
  const p = await pronto();
  const m = p.m, user = p.user;
  const provs = provedores(user);
  if (provs.indexOf("password") !== -1) {
    const cred = m.EmailAuthProvider.credential(user.email, senhaAtual || "");
    return m.reauthenticateWithCredential(user, cred);
  }
  if (provs.indexOf("google.com") !== -1) {
    return m.reauthenticateWithPopup(user, new m.GoogleAuthProvider());
  }
  if (provs.indexOf("facebook.com") !== -1) {
    return m.reauthenticateWithPopup(user, new m.FacebookAuthProvider());
  }
}

export async function trocarSenha(senhaAtual, novaSenha) {
  await reautenticar(senhaAtual);
  const p = await pronto();
  return p.m.updatePassword(p.user, novaSenha);
}

export async function excluirConta(senhaAtual) {
  await reautenticar(senhaAtual);
  const p = await pronto();
  const user = p.user;
  try {
    const fs = await comTempo(iniciarDb(), 6000);
    await comTempo(fs.deleteDoc(fs.doc(db, "usuarios", user.uid)), 6000);
  } catch (e) {}
  try { localStorage.removeItem(chaveLocal(user.uid)); } catch (e) {}
  guardarUsuario(null);
  return p.m.deleteUser(user);
}
