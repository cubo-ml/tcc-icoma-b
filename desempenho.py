# Sistema de média do SkillBloom. Fica na MESMA pasta do main.py (arquivo próprio, não cole dentro do main.py).
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, session
from firebase_admin import firestore

from app.auth.oauth import CHAVE_SESSAO

bp = Blueprint("desempenho", __name__)

# ordem e nomes iguais aos do painel (/dash)
CHAVES = {"com": "Comunicação", "team": "Trabalho em equipe", "prob": "Resolução de problemas",
          "pro": "Proatividade", "emp": "Inteligência emocional", "self": "Responsabilidade"}

# Questionário do painel: uma pergunta por competência, na ordem da página, e o gabarito dela
QUIZ_CHAVES = ["com", "team", "prob", "pro", "emp", "self"]
GABARITO = [1, 2, 1, 3, 1, 2]


def _agora():
    # horário de Brasília; funciona em qualquer computador (não depende de pacote extra no Windows)
    return datetime.now(timezone(timedelta(hours=-3)))


def _uid():
    """Quem está logado: o mesmo identificador que o login do site já guarda na sessão."""
    u = session.get(CHAVE_SESSAO)
    return str(u).replace("/", "_") if u else None


def _ref(uid):
    return firestore.client().collection("desempenho").document(str(uid).replace("/", "_"))


def _calcular(d):
    soma, tent = d.get("soma", {}), d.get("tent", {})
    comps = [{"n": nome, "v": round(soma[k] / tent[k])} for k, nome in CHAVES.items() if tent.get(k)]
    geral = round(sum(c["v"] for c in comps) / len(comps)) if comps else 0
    total = d.get("total", 0)
    sucesso = round(d.get("acertos", 0) / total * 100) if total else None
    return {"competencias": comps, "geral": geral, "sucesso": sucesso,
            "acessos": d.get("acessos_mes", {}).get(_agora().strftime("%Y-%m")),
            "ultimo": d.get("ultimo")}


@firestore.transactional
def _gravar(tx, ref, eventos, acerto):
    snap = ref.get(transaction=tx)
    d = snap.to_dict() if snap.exists else {}
    soma, tent = d.setdefault("soma", {}), d.setdefault("tent", {})
    for chave, pts in eventos:
        soma[chave] = soma.get(chave, 0) + pts
        tent[chave] = tent.get(chave, 0) + 1
    if acerto is not None:                       # uma missão respondida no simulador
        d["total"] = d.get("total", 0) + 1
        d["acertos"] = d.get("acertos", 0) + (1 if acerto else 0)
    r = _calcular(d)
    d["geral"] = r["geral"]                      # a porcentagem geral fica salva na conta da pessoa
    d["atualizado"] = firestore.SERVER_TIMESTAMP
    tx.set(ref, d)
    return r


def registrar(uid, eventos, acerto=None):
    """eventos = [("com", 100), ("pro", 80)]"""
    db = firestore.client()
    return _gravar(db.transaction(), _ref(uid), eventos, acerto)


def registrar_acesso(uid):
    _ref(uid).set({"acessos_mes": {_agora().strftime("%Y-%m"): firestore.Increment(1)}}, merge=True)


def montar_dados(uid):
    snap = _ref(uid).get()
    return _calcular(snap.to_dict() if snap.exists else {})


def _pts(v):
    return max(0, min(100, int(v)))


@bp.post("/api/desempenho/registrar")
def api_registrar():
    uid = _uid()
    if not uid:
        return jsonify(erro="login"), 401
    j = request.get_json(silent=True) or {}
    ev, acerto = [], None
    if j.get("habilidade") in CHAVES:
        pts = _pts(j.get("pontos", 0))
        ev.append((j["habilidade"], pts))
        acerto = pts == 100
    if j.get("pro") is not None:
        ev.append(("pro", _pts(j["pro"])))
    if not ev:
        return jsonify(erro="vazio"), 400
    return jsonify(registrar(uid, ev, acerto))


@bp.get("/api/desempenho/resumo")
def api_resumo():
    uid = _uid()
    return (jsonify(montar_dados(uid)), 200) if uid else (jsonify(erro="login"), 401)


@bp.post("/api/questionario")
def api_questionario():
    """Questionário de teste do painel: cada resposta vira 100 (certa) ou 0 (errada) na competência dela."""
    uid = _uid()
    if not uid:
        return jsonify(erro="login"), 401
    esc = (request.get_json(silent=True) or {}).get("escolhas")
    if not isinstance(esc, list) or len(esc) != len(GABARITO):
        return jsonify(erro="respostas"), 400
    try:
        ev = [(QUIZ_CHAVES[i], 100 if int(esc[i]) == GABARITO[i] else 0) for i in range(len(GABARITO))]
    except (TypeError, ValueError):
        return jsonify(erro="respostas"), 400
    pct = round(sum(1 for _, p in ev if p == 100) / len(ev) * 100)
    registrar(uid, ev)
    _ref(uid).set({"ultimo": {"p": pct, "d": _agora().strftime("%d/%m/%Y")}}, merge=True)
    return jsonify(dados=montar_dados(uid))