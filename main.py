import os
import secrets

from flask import Flask, redirect, render_template, session
from werkzeug.middleware.proxy_fix import ProxyFix

from app.auth.oauth import (
    CHAVE_SESSAO,
    auth_bp,
    carregar_ambiente,
    configurar_oauth,
    sessao_iniciada,
    usuario_da_sessao,
)
from app.services.user_service import conquistas_de, conquistas_zeradas

# Le o .env antes de qualquer consulta a variavel de ambiente.
carregar_ambiente()

app = Flask(__name__)


# =========================================================
# ATRAS DE PROXY (Render, Railway, Nginx)
# Nesses lugares o TLS termina no proxy e a aplicacao recebe a
# requisicao em http. Sem isto o url_for(..., _external=True)
# monta redirect_uri com http:// e o Google devolve
# redirect_uri_mismatch, derrubando o login inteiro.
#
# O ProxyFix so olha os cabecalhos X-Forwarded-*; rodando na
# propria maquina ninguem os envia, entao no localhost nada
# muda. Os numeros dizem "confie em UM proxy na frente" - e o
# caso do Render. Vale so quando existe mesmo esse proxy: e ele
# quem garante que o cliente nao forjou os cabecalhos.
# =========================================================

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


# =========================================================
# SESSAO E LOGIN SOCIAL
# Sem FLASK_SECRET_KEY o app ainda sobe: gera uma chave
# aleatoria em memoria, boa apenas para desenvolvimento.
# =========================================================

chave = os.environ.get("FLASK_SECRET_KEY", "").strip()

if not chave:
    chave = secrets.token_hex(32)
    print(
        "[auth] AVISO: FLASK_SECRET_KEY nao definida. "
        "Usando chave aleatoria em memoria (so desenvolvimento) - "
        "as sessoes caem a cada reinicio do servidor."
    )
    print(
        "[auth] AVISO: em producao com MAIS DE UM WORKER isto QUEBRA "
        "o login: cada worker gera a sua chave, o cookie assinado por "
        "um e' recusado pelo outro e o state do OAuth se perde entre "
        "/auth/google e o callback (?erro=oauth_estado intermitente). "
        "Defina FLASK_SECRET_KEY, a MESMA para todos os workers."
    )

app.secret_key = chave


# =========================================================
# COOKIE DE SESSAO
# HTTPONLY: o JavaScript da pagina nao le o cookie.
# SAMESITE "Lax": o navegador manda o cookie quando o usuario
#   volta do Google/LinkedIn (navegacao de topo). "Strict"
#   seguraria o cookie justamente nesse retorno e o callback
#   nao acharia o state - o login quebraria.
# SECURE: o cookie so viaja em https. Ligado em producao; no
#   http://localhost isso impediria o login, por isso o padrao
#   e desligado e a escolha vem do ambiente.
# =========================================================

def cookie_somente_https():
    """Decide o SESSION_COOKIE_SECURE a partir do ambiente."""
    escolha = os.environ.get("SESSION_COOKIE_SECURE", "").strip().lower()

    if escolha:
        return escolha in ("1", "true", "sim", "on", "yes")

    ambiente = (
        os.environ.get("AMBIENTE", "") or os.environ.get("FLASK_ENV", "")
    ).strip().lower()

    if ambiente in ("producao", "production", "prod"):
        return True

    # O Render exporta RENDER=true nas suas maquinas.
    return bool(os.environ.get("RENDER", "").strip())


app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = cookie_somente_https()

configurar_oauth(app)
app.register_blueprint(auth_bp)


@app.context_processor
def injetar_usuario():
    """
    Deixa o usuario logado e suas conquistas visiveis para todas
    as templates - e o que alimenta o menu de conta do cabecalho.

    O cookie guarda apenas a chave do cadastro (mais nome e foto
    de reserva): email e provedor sao lidos do repositorio aqui,
    e nao viajam no navegador.

    Sem ninguem logado, conquistas vem None e a interface decide
    o que fazer. Logado mas sem cadastro em disco (gravacao que
    falhou, ou sessao antiga), devolvemos tudo zerado: numero
    inventado nao entra na tela.
    """
    usuario = usuario_da_sessao()

    if not usuario:
        return {"usuario": None, "conquistas": None}

    try:
        conquistas = conquistas_de(session.get(CHAVE_SESSAO, ""))
    except Exception as erro:
        # Uma pagina inteira nao pode cair por causa do painel de conta.
        print("[usuarios] AVISO: falha ao ler conquistas: " + erro.__class__.__name__)
        conquistas = None

    if conquistas is None:
        conquistas = conquistas_zeradas()

    return {"usuario": usuario, "conquistas": conquistas}


@app.route("/")
def index():
    nome = 'icoma.com.br'
    return render_template('index.html', site = nome)

@app.route("/login")
def login():
    return render_template('login/login.html')

@app.route("/cadastro")
def cadastro():
    return render_template('login/cadastro.html')

@app.route("/dash")
def dash():
    # Painel e area de quem entrou. Sem sessao, volta para o login.
    # /login e /cadastro nao tem guarda nenhuma, entao nao ha como
    # este redirecionamento virar laco.
    if not sessao_iniciada():
        return redirect("/login")

    return render_template('pages/landpage.html')

def main():
    app.run(host="0.0.0.0", port = int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    main()
