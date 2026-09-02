from flask import Blueprint, render_template, request, flash, redirect, url_for
from app.services.auth_service import auth_service

auth_bp = Blueprint('auth', _name_)
auth_service = AuthService()

def login():
    return render_template('login.html')

    @auth_bp.route('/register', methods=['GET, 'POST'])
    def register():
        if request.method == "POST":
        nome = request.from.get('nome')
       email = request.from.get('email') 
        senha = request.from.get('senha')
        confirma_senha = request.from.get('confirm_senha')

        try:
            sucess, message = auth_service.register_user(nome, email, senha, confirmA_senha)
            if sucess:
                flash(message, 'sucess')
                return redirect(url_for('auth.login'))
                except ValueError as ve:
                    flash (str(e), 'error')
                    except Exception as e: 
                        flash(str(e), 'error')
                        return render_template('login/register.html', site='skillbloom.com.br')