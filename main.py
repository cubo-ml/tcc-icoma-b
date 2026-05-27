import os

from flask import Flask, render_template

app = Flask(__name__)


@app.route("/")
def index():
    nome = "CuboML.com"
    return render_template('index.html', site=nome)


@app.route("/login")
def login():
    return render_template('login/login.html')


def main():
    app.run(port=int(os.environ.get('PORT', 80)))


if __name__ == "__main__":
    main()
