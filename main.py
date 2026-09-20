import os
import secrets

from flask import Flask, redirect, render_template, session, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

import firebase_admin
from firebase_admin import credentials, firestore, auth

from app.auth.oauth import (
    CHAVE_SESSAO,
    auth_bp,
    carregar_ambiente,
    configurar_oauth,
    sessao_iniciada,
    usuario_da_sessao,
)
from app.services.user_service import conquistas_de, conquistas_zeradas


# =========================================================
# AMBIENTE
# =========================================================

carregar_ambiente()

app = Flask(__name__)


# =========================================================
# FIREBASE
# =========================================================

cred = credentials.Certificate("firebase-admin.json")

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()


# =========================================================
# ATRAS DE PROXY
# =========================================================

app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1
)


# =========================================================
# SESSAO E LOGIN SOCIAL
# =========================================================

chave = os.environ.get("FLASK_SECRET_KEY", "").strip()

if not chave:
    chave = secrets.token_hex(32)

    print(
        "[auth] AVISO: FLASK_SECRET_KEY nao definida. "
        "Usando chave aleatoria em memoria (so desenvolvimento)."
    )

    print(
        "[auth] AVISO: em producao com MAIS DE UM WORKER isto QUEBRA "
        "o login. Defina FLASK_SECRET_KEY."
    )

app.secret_key = chave


# =========================================================
# COOKIE DE SESSAO
# =========================================================

def cookie_somente_https():
    """Decide o SESSION_COOKIE_SECURE a partir do ambiente."""

    escolha = os.environ.get(
        "SESSION_COOKIE_SECURE",
        ""
    ).strip().lower()

    if escolha:
        return escolha in (
            "1",
            "true",
            "sim",
            "on",
            "yes"
        )

    ambiente = (
        os.environ.get("AMBIENTE", "")
        or os.environ.get("FLASK_ENV", "")
    ).strip().lower()

    if ambiente in (
        "producao",
        "production",
        "prod"
    ):
        return True

    return bool(
        os.environ.get(
            "RENDER",
            ""
        ).strip()
    )


app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = cookie_somente_https()


# =========================================================
# OAUTH
# =========================================================

configurar_oauth(app)

app.register_blueprint(auth_bp)


# =========================================================
# USUARIO GLOBAL DAS TEMPLATES
# =========================================================

@app.context_processor
def injetar_usuario():
    """
    Deixa o usuario logado e suas conquistas visiveis
    para todas as templates.
    """

    usuario = usuario_da_sessao()

    if not usuario:
        return {
            "usuario": None,
            "conquistas": None
        }

    try:
        conquistas = conquistas_de(
            session.get(CHAVE_SESSAO, "")
        )

    except Exception as erro:

        print(
            "[usuarios] AVISO: falha ao ler conquistas: "
            + erro.__class__.__name__
        )

        conquistas = None

    if conquistas is None:
        conquistas = conquistas_zeradas()

    return {
        "usuario": usuario,
        "conquistas": conquistas
    }


# =========================================================
# PAGINA INICIAL
# =========================================================

@app.route("/")
def index():

    nome = "icoma.com.br"

    return render_template(
        "index.html",
        site=nome
    )


# =========================================================
# LOGIN
# =========================================================

@app.route("/login")
def login():

    return render_template(
        "login/login.html"
    )


# =========================================================
# CADASTRO
# =========================================================

@app.route("/cadastro")
@app.route("/login/cadastro")
def cadastro():
    return render_template("login/cadastro.html")

# =========================================================
# API DO CADASTRO
# =========================================================

@app.route("/api/cadastro", methods=["POST"])
def cadastrar_usuario():

    try:

        dados = request.get_json()

        nome = dados.get("nome")
        nascimento = dados.get("nascimento")
        genero = dados.get("genero")
        email = dados.get("email")
        telefone = dados.get("telefone")
        senha = dados.get("senha")


        # -------------------------------------------------
        # VERIFICAR CAMPOS
        # -------------------------------------------------

        if (
            not nome
            or not nascimento
            or not email
            or not telefone
            or not senha
        ):

            return jsonify({
                "sucesso": False,
                "mensagem": "Preencha todos os campos obrigatórios."
            }), 400


        # -------------------------------------------------
        # CRIAR USUARIO NO FIREBASE AUTHENTICATION
        # -------------------------------------------------

        usuario = auth.create_user(
            email=email,
            password=senha,
            display_name=nome
        )


        # -------------------------------------------------
        # SALVAR DADOS NO FIRESTORE
        # -------------------------------------------------

        db.collection("usuarios").document(
            usuario.uid
        ).set({

            "uid": usuario.uid,
            "nome": nome,
            "nascimento": nascimento,
            "genero": genero,
            "email": email,
            "telefone": telefone

        })


        # -------------------------------------------------
        # RESPOSTA DE SUCESSO
        # -------------------------------------------------

        return jsonify({

            "sucesso": True,
            "mensagem": "Conta criada com sucesso!"

        })


    # -----------------------------------------------------
    # EMAIL JÁ EXISTENTE
    # -----------------------------------------------------

    except auth.EmailAlreadyExistsError:

        return jsonify({

            "sucesso": False,
            "mensagem": "Este e-mail já está cadastrado."

        }), 400


    # -----------------------------------------------------
    # OUTRO ERRO
    # -----------------------------------------------------

    except Exception as erro:

        print(
            "[cadastro] ERRO:",
            erro
        )

        return jsonify({

            "sucesso": False,
            "mensagem": "Ocorreu um erro ao criar a conta."

        }), 500


# =========================================================
# TESTE DO FIREBASE
# =========================================================

@app.route("/teste")
def teste():

    db.collection("teste").add({

        "mensagem": "Funcionou!",
        "autor": "Lucas"

    })

    return "Dados enviados com sucesso!"


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dash")
def dash():

    # Se nao estiver logado,
    # volta para o login.

    if not sessao_iniciada():

        return redirect("/login")

    return render_template(
        "pages/landpage.html"
    )


# =========================================================
# INICIAR SERVIDOR
# =========================================================

def main():

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                10000
            )
        )
    )


if __name__ == "__main__":
    main()