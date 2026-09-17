# =========================================================
# MODELOS DE USUARIO
# Estruturas de dados puras, sem banco: o repositorio grava
# tudo em JSON, entao cada classe sabe virar dicionario
# (para_dict) e voltar de dicionario (de_dict).
#
# Todas as datas sao texto em ISO 8601 UTC. Guardar data como
# texto evita conversor especial na hora de salvar o JSON.
# =========================================================

from dataclasses import dataclass, field
from datetime import datetime, timezone


def agora_iso():
    """Momento atual em ISO 8601 UTC, sem microssegundos."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def montar_chave(provedor, id_externo, email=""):
    """
    Chave global do usuario: provedor + ":" + id_externo.

    O id do provedor e o unico identificador estavel - a pessoa
    pode trocar o email da conta. Quando o provedor nao devolve
    id, caimos para o email, mas sempre com o provedor na frente:
    email puro como chave global misturaria contas Google e
    LinkedIn da mesma pessoa.

    CAIXA: o login social monta id_externo com sub -> id -> email,
    entao o email pode chegar tanto em id_externo quanto no
    parametro email. Email nao diferencia maiuscula de minuscula:
    "Edu.Silva@Gmail.com" e "edu.silva@gmail.com" sao a MESMA
    pessoa e precisam cair na mesma chave, senao o segundo login
    cria um cadastro novo e o progresso do primeiro fica orfao.
    Por isso normalizamos a caixa sempre que o identificador for
    um email (tem "@"). Um "sub" opaco do provedor fica intocado:
    ele pode diferenciar maiuscula de minuscula.
    """
    provedor = _texto(provedor).strip().lower() or "desconhecido"
    identificador = _texto(id_externo).strip()

    if not identificador:
        identificador = _texto(email).strip()

    if not identificador:
        return ""

    if "@" in identificador:
        identificador = identificador.lower()

    return provedor + ":" + identificador


# =========================================================
# CONVERSORES TOLERANTES
# O JSON pode ter sido editado a mao ou vir de uma versao
# antiga do projeto. Nada aqui pode estourar excecao.
# =========================================================

def _texto(valor):
    if valor is None:
        return ""
    if isinstance(valor, str):
        return valor
    return str(valor)


def _inteiro(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


# =========================================================
# CONQUISTAS
# O painel da conta mostra estes numeros. Usuario novo comeca
# com tudo em zero - nada de numero inventado em cadastro
# recem-criado.
# =========================================================

@dataclass
class Conquistas:
    sequencia_dias: int = 0
    indice_competencia: int = 0
    acertos: int = 0
    erros: int = 0
    desafios_concluidos: int = 0
    ranking: int = 0

    def para_dict(self):
        return {
            "sequencia_dias": self.sequencia_dias,
            "indice_competencia": self.indice_competencia,
            "acertos": self.acertos,
            "erros": self.erros,
            "desafios_concluidos": self.desafios_concluidos,
            "ranking": self.ranking,
        }

    @classmethod
    def de_dict(cls, dados):
        if not isinstance(dados, dict):
            dados = {}

        return cls(
            sequencia_dias=_inteiro(dados.get("sequencia_dias")),
            indice_competencia=_inteiro(dados.get("indice_competencia")),
            acertos=_inteiro(dados.get("acertos")),
            erros=_inteiro(dados.get("erros")),
            desafios_concluidos=_inteiro(dados.get("desafios_concluidos")),
            ranking=_inteiro(dados.get("ranking")),
        )


# =========================================================
# USUARIO
# Espelha o que o login social devolve (nome, email, foto,
# provedor) mais o carimbo de quando entrou pela primeira vez
# e de quando entrou por ultimo.
# =========================================================

@dataclass
class Usuario:
    id_externo: str = ""
    provedor: str = ""
    nome: str = ""
    email: str = ""
    foto: str = ""
    criado_em: str = field(default_factory=agora_iso)
    ultimo_acesso: str = field(default_factory=agora_iso)

    @property
    def chave(self):
        """Chave usada pelo repositorio para guardar este usuario."""
        return montar_chave(self.provedor, self.id_externo, self.email)

    def para_dict(self):
        return {
            "id_externo": self.id_externo,
            "provedor": self.provedor,
            "nome": self.nome,
            "email": self.email,
            "foto": self.foto,
            "criado_em": self.criado_em,
            "ultimo_acesso": self.ultimo_acesso,
        }

    @classmethod
    def de_dict(cls, dados):
        if not isinstance(dados, dict):
            dados = {}

        momento = agora_iso()

        return cls(
            id_externo=_texto(dados.get("id_externo")),
            provedor=_texto(dados.get("provedor")),
            nome=_texto(dados.get("nome")),
            email=_texto(dados.get("email")),
            foto=_texto(dados.get("foto")),
            criado_em=_texto(dados.get("criado_em")) or momento,
            ultimo_acesso=_texto(dados.get("ultimo_acesso")) or momento,
        )
