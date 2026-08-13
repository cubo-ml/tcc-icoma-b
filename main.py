import os

from flask import render_template, Flask

app = Flask(__name__)

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
    return render_template('pages/landpage.html')

def main():
    app.run(host="0.0.0.0", port = int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    main()
