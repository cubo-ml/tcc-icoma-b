# =========================================================
# REPOSITORIO DE USUARIOS - ARQUIVO JSON
# Guarda quem entrou pelo login social em data/usuarios.json.
# Sem banco de dados: o TCC roda em qualquer maquina so com
# a biblioteca padrao do Python.
#
# Tres cuidados que o codigo toma:
#   1. Gravacao ATOMICA (arquivo temporario + os.replace).
#      Gravar por cima corromperia a base se o processo
#      morresse no meio da escrita.
#   2. Uma TRAVA de modulo, porque o servidor de
#      desenvolvimento do Flask atende em varias threads.
#      Quem precisa ler, mudar e gravar deve usar atualizar(),
#      que faz os tres passos sob a MESMA trava - buscar() +
#      salvar() sao duas travas e perdem escrita concorrente.
#   3. Base ausente, vazia ou invalida NAO estoura excecao:
#      vira base vazia, avisa uma vez e o site segue de pe.
#
# Formato do arquivo:
#   {
#     "google:1234": {
#       "usuario":    { ... },
#       "conquistas": { ... }
#     }
#   }
# =========================================================

import json
import os
import threading

from datetime import datetime, timezone

from app.models.user import Conquistas, Usuario


# =========================================================
# CAMINHOS E TRAVA
# A raiz do projeto fica tres pastas acima deste arquivo
# (app/repositories/user_repository.py).
# =========================================================

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASTA_DADOS = os.path.join(RAIZ, "data")
ARQUIVO = os.path.join(PASTA_DADOS, "usuarios.json")

_trava = threading.Lock()
_ja_avisou = set()


def _avisar_uma_vez(assunto, mensagem):
    """
    Avisa no console so na primeira vez. Repetir o mesmo aviso a
    cada requisicao so atrapalharia a leitura do log.
    Nunca citamos email, foto ou token aqui.
    """
    if assunto in _ja_avisou:
        return

    _ja_avisou.add(assunto)
    print("[usuarios] " + mensagem)


# =========================================================
# LEITURA
# =========================================================

def _reservar_nome_corrompido():
    """
    Escolhe - e RESERVA - um nome .corrompido que ainda nao existe.

    O carimbo antigo vinha de agora_iso(), com resolucao de um
    segundo: tres corrupcoes dentro do mesmo segundo caiam no mesmo
    nome e o os.replace sobrescrevia a copia anterior em silencio.
    Agora o carimbo tem microssegundos e o pid, e o nome e criado
    com O_EXCL (falha se ja existir). Se ainda assim colidir,
    numeramos. Nenhum .corrompido e sobrescrito.
    """
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    raiz = ARQUIVO + ".corrompido." + carimbo + "." + str(os.getpid())

    tentativa = 0

    while True:
        destino = raiz if tentativa == 0 else raiz + "-" + str(tentativa)

        try:
            descritor = os.open(
                destino,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError:
            tentativa += 1
            if tentativa > 1000:
                raise
            continue

        os.close(descritor)
        return destino


def _preservar_corrompido():
    """
    Renomeia a base invalida para .corrompido antes de recomecar.
    Apagar seria destruir dados reais de quem ja logou.
    """
    try:
        # O nome ja vem reservado por nos: o os.replace abaixo so
        # troca o lugar-marcado vazio que acabamos de criar, nunca
        # uma copia anterior de verdade.
        destino = _reservar_nome_corrompido()
        os.replace(ARQUIVO, destino)
        print(
            "[usuarios] AVISO: base de usuarios invalida. "
            "O arquivo anterior foi preservado em " + os.path.basename(destino) + "."
        )
    except OSError as erro:
        _avisar_uma_vez(
            "preservar",
            "AVISO: base invalida e nao foi possivel preserva-la (" +
            erro.__class__.__name__ + "). Seguindo com base vazia.",
        )


def _ler_base():
    """Devolve o dicionario inteiro da base. Problema no arquivo vira base vazia."""
    if not os.path.exists(ARQUIVO):
        return {}

    try:
        with open(ARQUIVO, "r", encoding="utf-8") as arquivo:
            conteudo = arquivo.read().strip()
    except OSError as erro:
        _avisar_uma_vez(
            "leitura",
            "AVISO: nao foi possivel ler a base de usuarios (" +
            erro.__class__.__name__ + "). Seguindo com base vazia.",
        )
        return {}

    if not conteudo:
        return {}

    try:
        dados = json.loads(conteudo)
    except ValueError:
        _preservar_corrompido()
        return {}

    if not isinstance(dados, dict):
        _preservar_corrompido()
        return {}

    return dados


# =========================================================
# ESCRITA ATOMICA
# =========================================================

def _gravar_base(dados):
    """
    Grava em arquivo temporario no MESMO diretorio e so entao
    troca pelo definitivo com os.replace, que e atomico.
    Assim a base nunca fica pela metade.

    O temporario nasce com os.open e 0o600 (so o dono le e
    escreve), porque o JSON guarda o email real de quem entrou.
    O open() comum deixaria 0o644 - legivel por qualquer conta da
    maquina. No Windows isso tem pouco efeito, mas o projeto
    tambem roda em Linux, e o os.replace leva a permissao junto
    para o arquivo definitivo.
    """
    os.makedirs(PASTA_DADOS, exist_ok=True)

    temporario = ARQUIVO + ".tmp" + str(os.getpid())

    try:
        descritor = os.open(
            temporario,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o600,
        )

        try:
            arquivo = os.fdopen(descritor, "w", encoding="utf-8")
        except Exception:
            os.close(descritor)
            raise

        with arquivo:
            json.dump(dados, arquivo, ensure_ascii=False, indent=2)
            arquivo.flush()
            os.fsync(arquivo.fileno())

        os.replace(temporario, ARQUIVO)
    except OSError:
        # Deixar lixo .tmp para tras so confundiria a proxima gravacao.
        try:
            if os.path.exists(temporario):
                os.remove(temporario)
        except OSError:
            pass
        raise


# =========================================================
# API DO REPOSITORIO
# =========================================================

def buscar(chave):
    """
    Procura um usuario pela chave.
    Devolve sempre um par (usuario, conquistas); quando nao existe
    cadastro, devolve (None, None) - assim quem chama pode
    desempacotar o resultado sem testar antes.
    """
    chave = (chave or "").strip()
    if not chave:
        return None, None

    with _trava:
        base = _ler_base()

    registro = base.get(chave)
    if not isinstance(registro, dict):
        return None, None

    usuario = Usuario.de_dict(registro.get("usuario"))
    conquistas = Conquistas.de_dict(registro.get("conquistas"))

    return usuario, conquistas


def salvar(usuario, conquistas):
    """
    Grava (ou regrava) o usuario e suas conquistas.
    Devolve a chave usada. Erro de disco sobe para quem chamou:
    quem decide o que fazer com a falha e a camada de login.
    """
    chave = usuario.chave
    if not chave:
        _avisar_uma_vez(
            "sem_chave",
            "AVISO: perfil sem identificador estavel; cadastro nao foi gravado.",
        )
        return ""

    if conquistas is None:
        conquistas = Conquistas()

    with _trava:
        base = _ler_base()
        base[chave] = {
            "usuario": usuario.para_dict(),
            "conquistas": conquistas.para_dict(),
        }
        _gravar_base(base)

    return chave


def atualizar(chave, funcao):
    """
    Le, altera e grava o cadastro SEM soltar a trava no meio.

    Por que existe: quem fazia buscar() -> muda as conquistas ->
    salvar() pegava a trava duas vezes, e entre uma e outra cabia
    outra requisicao. As duas liam o mesmo valor e a ultima a
    gravar apagava o progresso da primeira. Aqui a leitura, a
    alteracao e a gravacao acontecem dentro da MESMA trava.

    A funcao recebe (usuario, conquistas) e pode:
      - alterar os objetos no lugar e nao devolver nada;
      - devolver as conquistas novas;
      - devolver o par (usuario, conquistas).

    Devolve o par (usuario, conquistas) ja gravado, ou (None, None)
    quando nao existe cadastro para a chave.

    ATENCAO: a funcao roda com a trava na mao. Ela nao pode chamar
    buscar/salvar/atualizar, senao o processo trava a si mesmo.
    """
    chave = (chave or "").strip()
    if not chave:
        return None, None

    with _trava:
        base = _ler_base()
        registro = base.get(chave)

        if not isinstance(registro, dict):
            return None, None

        usuario = Usuario.de_dict(registro.get("usuario"))
        conquistas = Conquistas.de_dict(registro.get("conquistas"))

        resultado = funcao(usuario, conquistas)

        if isinstance(resultado, tuple) and len(resultado) == 2:
            usuario, conquistas = resultado
        elif isinstance(resultado, Conquistas):
            conquistas = resultado
        elif isinstance(resultado, Usuario):
            usuario = resultado

        if usuario is None:
            return None, None

        if conquistas is None:
            conquistas = Conquistas()

        # Gravamos sempre na chave pedida: a funcao pode ter mexido
        # no nome ou na foto, mas mudar a chave criaria um cadastro
        # solto em vez de atualizar este.
        base[chave] = {
            "usuario": usuario.para_dict(),
            "conquistas": conquistas.para_dict(),
        }
        _gravar_base(base)

    return usuario, conquistas


def listar():
    """
    Todos os cadastros, em uma lista de pares (usuario, conquistas),
    ordenados pela chave. Util para telas de ranking.
    """
    with _trava:
        base = _ler_base()

    cadastros = []

    for chave in sorted(base.keys()):
        registro = base.get(chave)
        if not isinstance(registro, dict):
            continue

        cadastros.append((
            Usuario.de_dict(registro.get("usuario")),
            Conquistas.de_dict(registro.get("conquistas")),
        ))

    return cadastros
