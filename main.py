import os

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

from flask import Flask, render_template, request

app = Flask(__name__)

cred = credentials.Certificate("firebase-admin.json")

firebase_admin.initialize_app(cred)

db = firestore.client()


@app.route("/")
def index():
    nome = "CuboML.com"
    return render_template('index.html', site=nome)


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        nome = request.form["nome"]
        senha = request.form["senha"]

        db.collection("usuarios").add({
            "nome": nome,
            "senha": senha
        })

        return "Usuário cadastrado com sucesso!"

    return render_template('login/login.html')


@app.route("/teste")
def teste():

    db.collection("teste").add({

        "mensagem": "Funcionou!",
        "autor": "Lucas"

    })

    return "Dados enviados com sucesso!"



def main():
    app.run(port=int(os.environ.get('PORT', 80)))

    


if __name__ == "__main__":
    main()
