# =========================================================
# LOGIN SOCIAL - GOOGLE E LINKEDIN
# OAuth 2.0 / OpenID Connect com Authlib.
#
# Regra de ouro deste modulo: sem credenciais no ambiente
# nada estoura. As rotas continuam existindo e apenas
# redirecionam para /login?erro=oauth_indisponivel, de modo
# que o site inteiro sobe e funciona em qualquer maquina.
#
# Rotas publicadas (prefixo /auth):
#   GET /auth/google             inicia o fluxo do Google
#   GET /auth/google/callback    conclui e cria a sessao
#   GET /auth/linkedin           inicia o fluxo do LinkedIn
#   GET /auth/linkedin/callback  conclui e cria a sessao
#   GET /auth/sair               encerra a sessao
# =========================================================

import os
from dotenv import load_dotenv

load_dotenv()
import secrets

from flask import Blueprint, current_app, redirect, request, session, url_for

from app.services.user_service import (
    chave_do_perfil,
    registrar_ou_atualizar,
    usuario_de,
)


# =========================================================
# IMPORTES OPCIONAIS
# Authlib e python-dotenv sao desejaveis, nao obrigatorios.
# =========================================================

try:
    from authlib.integrations.flask_client import OAuth
except Exception:
    OAuth = None
    print(
        "[auth] AVISO: Authlib nao esta instalado. "
        "O login social fica desativado. "
        "Instale com: pip install -r requirements.txt"
    )


def carregar_ambiente():
    """Le o arquivo .env, quando python-dotenv estiver disponivel."""
    try:
        from dotenv import load_dotenv
    except Exception:
        print(
            "[auth] AVISO: python-dotenv nao esta instalado; "
            "serao usadas apenas as variaveis ja exportadas no sistema."
        )
        return

    load_dotenv()


# =========================================================
# CONSTANTES DO CONTRATO COM O FRONT-END
# Os codigos abaixo sao lidos pelas paginas de autenticacao
# em ?erro=<codigo>. Nao renomear.
# =========================================================

ERRO_INDISPONIVEL = "oauth_indisponivel"
ERRO_NEGADO = "oauth_negado"
ERRO_ESTADO = "oauth_estado"
ERRO_FALHOU = "oauth_falhou"

DESTINO_PADRAO = "/dash"
PAGINA_PADRAO = "/login"

DESCOBERTA_GOOGLE = "https://accounts.google.com/.well-known/openid-configuration"

AUTORIZACAO_LINKEDIN = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_LINKEDIN = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_LINKEDIN = "https://api.linkedin.com/v2/userinfo"
USERINFO_GOOGLE = "https://openidconnect.googleapis.com/v1/userinfo"

ENDERECOS_DE_PERFIL = {
    "google": USERINFO_GOOGLE,
    "linkedin": USERINFO_LINKEDIN,
}


class FalhaDeAutenticacao(Exception):
    """Erro interno que ja sabe qual codigo mostrar ao usuario."""

    def __init__(self, codigo):
        super().__init__(codigo)
        self.codigo = codigo


# =========================================================
# REGISTRO DOS PROVEDORES
# So entra no registro o provedor que tem as duas variaveis
# de ambiente preenchidas.
# =========================================================

_oauth = None
_registrados = set()


def _credenciais(provedor):
    prefixo = provedor.upper()
    identificador = os.environ.get(prefixo + "_CLIENT_ID", "").strip()
    segredo = os.environ.get(prefixo + "_CLIENT_SECRET", "").strip()
    return identificador, segredo


def _avisar_ausencia(provedor):
    prefixo = provedor.upper()
    print(
        "[auth] " + provedor + ": " + prefixo + "_CLIENT_ID / " + prefixo +
        "_CLIENT_SECRET nao definidas. O botao respondera 'indisponivel'. "
        "Veja o .env.example."
    )


def configurar_oauth(app):
    """Prepara o Authlib e registra os provedores configurados."""
    global _oauth

    _registrados.clear()

    if OAuth is None:
        return

    _oauth = OAuth(app)

    identificador, segredo = _credenciais("google")
    if identificador and segredo:
        _oauth.register(
            name="google",
            client_id=identificador,
            client_secret=segredo,
            server_metadata_url=DESCOBERTA_GOOGLE,
            client_kwargs={"scope": "openid email profile"},
        )
        _registrados.add("google")
    else:
        _avisar_ausencia("google")

    identificador, segredo = _credenciais("linkedin")
    if identificador and segredo:
        # OpenID Connect atual do LinkedIn. As antigas r_liteprofile
        # e r_emailaddress foram descontinuadas.
        _oauth.register(
            name="linkedin",
            client_id=identificador,
            client_secret=segredo,
            authorize_url=AUTORIZACAO_LINKEDIN,
            access_token_url=TOKEN_LINKEDIN,
            api_base_url="https://api.linkedin.com/v2/",
            userinfo_endpoint=USERINFO_LINKEDIN,
            client_kwargs={
                "scope": "openid profile email",
                "token_endpoint_auth_method": "client_secret_post",
            },
        )
        _registrados.add("linkedin")
    else:
        _avisar_ausencia("linkedin")


def _cliente(provedor):
    """Cliente do provedor, ou None quando ele nao esta configurado."""
    if _oauth is None or provedor not in _registrados:
        return None
    try:
        return _oauth.create_client(provedor)
    except Exception as erro:
        _registrar_falha(provedor, erro)
        return None


# =========================================================
# AUXILIARES DE NAVEGACAO
# =========================================================

def caminho_seguro(valor):
    """
    Aceita somente caminho relativo da propria aplicacao.
    Qualquer coisa com esquema, host ou barra dupla vira /dash,
    para o parametro next nao virar um open redirect.
    """
    if not valor or not isinstance(valor, str):
        return DESTINO_PADRAO

    caminho = valor.strip()

    if not caminho.startswith("/"):
        return DESTINO_PADRAO
    if caminho.startswith("//"):
        return DESTINO_PADRAO
    if "\\" in caminho or ":" in caminho:
        return DESTINO_PADRAO
    if "\n" in caminho or "\r" in caminho or "\t" in caminho:
        return DESTINO_PADRAO

    return caminho


def _pagina_de_origem(destino):
    """A mensagem de erro volta para a pagina de onde o usuario saiu."""
    if destino.startswith("/cadastro"):
        return "/cadastro"
    return PAGINA_PADRAO


def _falhar(pagina, codigo):
    return redirect(pagina + "?erro=" + codigo)


def _registrar_aviso(provedor, resumo):
    """
    Escreve no log do servidor. O texto vem SEMPRE do proprio
    codigo: nada que tenha vindo do provedor ou da query entra
    aqui. O navegador continua vendo so o codigo de erro.
    """
    mensagem = "[auth] " + provedor + ": " + resumo
    try:
        current_app.logger.warning(mensagem)
    except Exception:
        print(mensagem)


def _registrar_falha(provedor, erro):
    """
    Registra a falha pelo NOME DA CLASSE da excecao, como o resto
    do projeto ja faz. repr(erro) despejaria no log um texto que,
    em alguns caminhos, veio de fora (query do provedor) - e quem
    le o log nao precisa do recado de terceiro.
    """
    _registrar_aviso(provedor, erro.__class__.__name__)


def _codigo_da_excecao(erro):
    """Traduz a excecao do Authlib para um dos codigos do contrato."""
    nome = type(erro).__name__.lower()
    texto = str(erro).lower()

    if "state" in nome or "csrf" in nome or "mismatching" in nome:
        return ERRO_ESTADO
    if "state" in texto or "csrf" in texto:
        return ERRO_ESTADO
    if "denied" in texto or "cancel" in texto:
        return ERRO_NEGADO

    return ERRO_FALHOU


# =========================================================
# SESSAO DO USUARIO
# O cookie guarda o minimo: a chave do cadastro, mais nome e
# foto como reserva. O perfil completo (email, provedor) sai
# do repositorio, a partir da chave.
# =========================================================

CHAVE_SESSAO = "usuario_chave"
NOME_SESSAO = "usuario_nome"
FOTO_SESSAO = "usuario_foto"


def _da_sessao(nome):
    return str(session.get(nome) or "").strip()


def _provedor_da_chave(chave):
    """A chave e "provedor:identificador" - o provedor nao e segredo."""
    if ":" not in chave:
        return ""
    return chave.split(":", 1)[0]


def _reserva_da_sessao():
    """
    Nome e foto guardados no cookie. Sessao antiga (cookie gravado
    por uma versao anterior, que salvava o perfil inteiro) tambem
    e aproveitada: quem ja estava logado nao e deslogado por causa
    da mudanca.
    """
    nome = _da_sessao(NOME_SESSAO)
    foto = _da_sessao(FOTO_SESSAO)

    if not nome and not foto:
        antigo = session.get("usuario")
        if isinstance(antigo, dict):
            nome = str(antigo.get("nome") or "").strip()
            foto = str(antigo.get("foto") or "").strip()

    return nome, foto


def sessao_iniciada():
    """Tem alguem logado nesta sessao?"""
    if _da_sessao(CHAVE_SESSAO):
        return True

    nome, foto = _reserva_da_sessao()
    return bool(nome or foto)


def usuario_da_sessao():
    """
    Perfil do usuario logado, ou None quando nao ha ninguem.

    Le o cadastro no repositorio pela chave da sessao. Se o
    registro nao estiver la (a gravacao falhou, ou a sessao e de
    antes do cadastro existir), devolve a reserva do cookie: a
    pessoa continua logada, so aparece menos coisa na tela.
    Entrar no site NUNCA pode parar por causa disto.
    """
    if not sessao_iniciada():
        return None

    chave = _da_sessao(CHAVE_SESSAO)
    nome, foto = _reserva_da_sessao()

    if chave:
        try:
            perfil = usuario_de(chave)
        except Exception as erro:
            _registrar_falha("sessao", erro)
            perfil = None

        if perfil:
            return perfil

    return {
        "nome": nome or "Usuario",
        "foto": foto,
        "provedor": _provedor_da_chave(chave),
        "email": "",
    }


def encerrar_sessao():
    """Apaga tudo o que o login deixou no cookie."""
    for nome in (CHAVE_SESSAO, NOME_SESSAO, FOTO_SESSAO,
                 "auth_nonce", "auth_next", "usuario"):
        session.pop(nome, None)


# =========================================================
# PERFIL DO USUARIO
# =========================================================

def _perfil_do_token(provedor, cliente, token):
    """
    Extrai os dados do usuario. Ordem de preferencia:
    1. userinfo que o proprio Authlib ja validou no id_token;
    2. leitura do id_token conferindo o nonce (Google);
    3. endpoint userinfo do provedor.
    """
    perfil = token.get("userinfo") if isinstance(token, dict) else None

    if not perfil and provedor == "google":
        try:
            perfil = cliente.parse_id_token(
                token,
                nonce=session.get("auth_nonce"),
            )
        except Exception as erro:
            _registrar_falha(provedor, erro)
            if "nonce" in str(erro).lower():
                # id_token que nao pertence a esta sessao.
                raise FalhaDeAutenticacao(ERRO_ESTADO)
            perfil = None

    if not perfil:
        perfil = _perfil_pelo_endpoint(provedor, cliente, token)

    if not perfil:
        return None

    return {
        "nome": (
            perfil.get("name")
            or perfil.get("given_name")
            or perfil.get("email")
            or "Usuario"
        ),
        "email": perfil.get("email") or "",
        "foto": perfil.get("picture") or "",
        "provedor": provedor,
        # Identificador estavel da conta no provedor: "sub" e o campo
        # do OpenID Connect (Google e LinkedIn atual), "id" atende
        # respostas antigas. O email e o ultimo recurso, porque a
        # pessoa pode troca-lo na conta.
        "id_externo": (
            perfil.get("sub")
            or perfil.get("id")
            or perfil.get("email")
            or ""
        ),
    }


def _perfil_pelo_endpoint(provedor, cliente, token):
    try:
        return cliente.userinfo(token=token)
    except Exception as erro:
        _registrar_falha(provedor, erro)

    endereco = ENDERECOS_DE_PERFIL.get(provedor)
    if not endereco:
        return None

    try:
        resposta = cliente.get(endereco, token=token)
        return resposta.json()
    except Exception as erro:
        _registrar_falha(provedor, erro)
        return None


# =========================================================
# FLUXO
# =========================================================

def _iniciar(provedor):
    destino = caminho_seguro(request.args.get("next"))
    session["auth_next"] = destino

    pagina = _pagina_de_origem(destino)

    cliente = _cliente(provedor)
    if cliente is None:
        return _falhar(pagina, ERRO_INDISPONIVEL)

    retorno = url_for("auth." + provedor + "_callback", _external=True)

    try:
        if provedor == "google":
            # O nonce amarra o id_token a esta sessao.
            # O state de CSRF o proprio Authlib gera e confere.
            nonce = secrets.token_urlsafe(24)
            session["auth_nonce"] = nonce
            return cliente.authorize_redirect(retorno, nonce=nonce)

        return cliente.authorize_redirect(retorno)
    except Exception as erro:
        _registrar_falha(provedor, erro)
        return _falhar(pagina, ERRO_FALHOU)


def _concluir(provedor):
    destino = caminho_seguro(session.pop("auth_next", DESTINO_PADRAO))
    pagina = _pagina_de_origem(destino)

    # O provedor avisa a recusa pela query, antes de qualquer token.
    # O conteudo de ?error= e escrito por terceiros: serve para
    # escolher o codigo de erro, mas nunca vai para o log.
    recusa = request.args.get("error", "")
    if recusa:
        _registrar_aviso(provedor, "autorizacao recusada pelo provedor")
        if "denied" in recusa or "cancel" in recusa:
            return _falhar(pagina, ERRO_NEGADO)
        return _falhar(pagina, ERRO_FALHOU)

    cliente = _cliente(provedor)
    if cliente is None:
        return _falhar(pagina, ERRO_INDISPONIVEL)

    try:
        token = cliente.authorize_access_token()
    except Exception as erro:
        _registrar_falha(provedor, erro)
        return _falhar(pagina, _codigo_da_excecao(erro))

    try:
        usuario = _perfil_do_token(provedor, cliente, token)
    except FalhaDeAutenticacao as falha:
        session.pop("auth_nonce", None)
        return _falhar(pagina, falha.codigo)

    session.pop("auth_nonce", None)

    if not usuario:
        return _falhar(pagina, ERRO_FALHOU)

    # =====================================================
    # CADASTRO DA CONTA
    # A sessao sozinha esquece tudo quando o servidor reinicia.
    # Aqui o perfil vira cadastro em disco, com as conquistas.
    #
    # BLINDAGEM: se a gravacao falhar (disco cheio, permissao,
    # base ruim), o login CONTINUA. Perder a gravacao e ruim;
    # impedir a pessoa de entrar e pior.
    # =====================================================

    chave = ""

    try:
        chave = chave_do_perfil(usuario)
        registrar_ou_atualizar(usuario)
    except Exception as erro:
        _registrar_falha(provedor, erro)

    # =====================================================
    # O QUE VAI PARA O COOKIE
    # O cookie de sessao do Flask e ASSINADO, nao criptografado:
    # qualquer um que o copie le o conteudo sem saber a
    # secret_key. Por isso guardamos so a chave do cadastro.
    # Nome e foto ficam como RESERVA, para o cabecalho continuar
    # funcionando se a gravacao em disco tiver falhado. Email e
    # id do provedor nao entram: sao lidos do repositorio.
    # =====================================================
    session["usuario_chave"] = chave
    session["usuario_nome"] = usuario.get("nome") or "Usuario"
    session["usuario_foto"] = usuario.get("foto") or ""
    session.pop("usuario", None)

    # Voltar para /login ou /cadastro depois de entrar nao faz sentido:
    # nesses casos o usuario segue para o painel.
    if destino in ("/login", "/cadastro"):
        return redirect(DESTINO_PADRAO)

    return redirect(destino)


# =========================================================
# ROTAS
# =========================================================

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/google")
def google_login():
    return _iniciar("google")


@auth_bp.route("/google/callback")
def google_callback():
    return _concluir("google")


@auth_bp.route("/linkedin")
def linkedin_login():
    return _iniciar("linkedin")


@auth_bp.route("/linkedin/callback")
def linkedin_callback():
    return _concluir("linkedin")


@auth_bp.route("/sair")
def sair():
    encerrar_sessao()
    return redirect("/")
