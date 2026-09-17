# =========================================================
# SERVICO DE USUARIOS
# A regra de negocio do cadastro social fica aqui: o modulo de
# login (app/auth/oauth.py) so entrega o perfil que o Google ou
# o LinkedIn devolveu, e este servico decide o que gravar.
#
# Regra principal, decidida no projeto:
#   - PRIMEIRO login  -> cria o cadastro com conquistas ZERADAS
#                        e carimba criado_em.
#   - Demais logins   -> NAO zera nada. So atualiza nome, foto e
#                        ultimo_acesso, porque a pessoa pode ter
#                        trocado a foto la no provedor.
# =========================================================

from app.models.user import Conquistas, Usuario, agora_iso, montar_chave
from app.repositories import user_repository


def chave_do_perfil(perfil):
    """Chave do usuario a partir do dicionario de perfil do login social."""
    perfil = perfil or {}

    return montar_chave(
        perfil.get("provedor"),
        perfil.get("id_externo"),
        perfil.get("email"),
    )


def conquistas_zeradas():
    """Conquistas de quem acabou de chegar: tudo em zero."""
    return Conquistas().para_dict()


# =========================================================
# CADASTRO
# =========================================================

def registrar_ou_atualizar(perfil):
    """
    Cadastra o usuario do login social, ou atualiza o que ja existe.

    Recebe o dicionario montado em _perfil_do_token (nome, email,
    foto, provedor) acrescido de id_externo.
    Devolve as conquistas em dicionario, prontas para a interface.
    """
    perfil = perfil or {}
    provedor = (perfil.get("provedor") or "desconhecido").strip().lower()

    chave = chave_do_perfil(perfil)
    if not chave:
        # Sem id e sem email nao ha como reconhecer a pessoa no
        # proximo login. Melhor nao gravar do que criar duplicata.
        print(
            "[usuarios] AVISO: " + provedor +
            " nao devolveu identificador estavel; cadastro nao foi gravado."
        )
        return conquistas_zeradas()

    momento = agora_iso()

    def aplicar(usuario, conquistas):
        # ---------------------------------------------
        # JA CADASTRADO: as conquistas ficam como estao.
        # Campo vazio vindo do provedor nao apaga o que ja
        # temos - so substituimos quando veio conteudo.
        # ---------------------------------------------
        if perfil.get("nome"):
            usuario.nome = perfil["nome"]

        if perfil.get("foto"):
            usuario.foto = perfil["foto"]

        if perfil.get("email") and not usuario.email:
            usuario.email = perfil["email"]

        usuario.ultimo_acesso = momento

    # Ler e gravar de uma vez so: se a pessoa abrir duas abas ao
    # mesmo tempo, os dois logins nao podem se atropelar e zerar
    # o progresso de quem gravou primeiro.
    usuario, conquistas = user_repository.atualizar(chave, aplicar)

    if usuario is None:
        # ---------------------------------------------
        # PRIMEIRO LOGIN: nasce o cadastro, tudo zerado.
        # ---------------------------------------------
        usuario = Usuario(
            id_externo=(perfil.get("id_externo") or "").strip(),
            provedor=provedor,
            nome=perfil.get("nome") or "Usuario",
            email=perfil.get("email") or "",
            foto=perfil.get("foto") or "",
            criado_em=momento,
            ultimo_acesso=momento,
        )
        conquistas = Conquistas()
        user_repository.salvar(usuario, conquistas)

    return conquistas.para_dict()


# =========================================================
# PROGRESSO
# =========================================================

def atualizar_conquistas(chave, funcao):
    """
    Muda as conquistas de um usuario sem perder escrita concorrente.

    Use SEMPRE isto para somar acerto, erro, desafio ou sequencia.
    O caminho ingenuo - conquistas_de(), somar 1, salvar - le e
    grava em dois momentos: duas requisicoes juntas leem o mesmo
    numero e uma delas some. Aqui o repositorio le, aplica a sua
    funcao e grava tudo sob a mesma trava.

    A funcao recebe o objeto Conquistas e pode alterar os campos
    direto (conquistas.acertos += 1) ou devolver outro Conquistas.

    Devolve as conquistas gravadas em dicionario, ou None quando
    nao existe cadastro para a chave.
    """
    def aplicar(usuario, conquistas):
        return funcao(conquistas)

    usuario, conquistas = user_repository.atualizar(chave, aplicar)

    if conquistas is None:
        return None

    return conquistas.para_dict()


# =========================================================
# CONSULTA
# =========================================================

def conquistas_de(chave):
    """
    Conquistas gravadas do usuario, em dicionario.
    Devolve None quando nao existe cadastro para a chave - quem
    chama decide o que mostrar na tela.
    """
    usuario, conquistas = user_repository.buscar(chave)

    if conquistas is None:
        return None

    return conquistas.para_dict()


def usuario_de(chave):
    """Dados cadastrais do usuario em dicionario, ou None."""
    usuario, conquistas = user_repository.buscar(chave)

    if usuario is None:
        return None

    return usuario.para_dict()
