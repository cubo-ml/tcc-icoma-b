/* SkillBloom — melhorias do simulador. Carregue DEPOIS do game.js. */
(function () {
  "use strict";

  /* ---------- Correção: o brilho do hover acendia todos os objetos
     que dividiam o mesmo material (ex.: tudo que usa "dark"). ---------- */
  INT.forEach(g => g.traverse(o => {
    if (o.material && o.material.emissive) o.material = o.material.clone();
  }));

  /* ---------- Visual 3D ---------- */
  R.toneMappingExposure = 1.05;
  scene.background.setHex(0x0c1822);
  scene.fog.color.setHex(0x0c1822);

  const luzTela = new THREE.PointLight(0x4caeff, .45, 2.4);   // reflexo azul do monitor
  luzTela.position.set(0, 1.2, -2.1);
  scene.add(luzTela);

  const fita = new THREE.Mesh(new THREE.BoxGeometry(2.9, .012, .012),
    new THREE.MeshBasicMaterial({ color: 0x4caeff }));          // fita de LED na mesa
  fita.position.set(0, .735, -1.845);
  scene.add(fita);

  const N = 140, pos = new Float32Array(N * 3);                 // poeira flutuando na luz
  for (let i = 0; i < N; i++) {
    pos[i * 3] = (Math.random() - .5) * 8;
    pos[i * 3 + 1] = .4 + Math.random() * 2.8;
    pos[i * 3 + 2] = -3.4 + Math.random() * 3.8;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  scene.add(new THREE.Points(geo, new THREE.PointsMaterial({
    size: .03, color: 0xcfe3ff, transparent: true, opacity: .35, depthWrite: false })));

  const loopOriginal = window.loop;
  window.loop = function (t) {
    const p = geo.attributes.position.array;
    for (let i = 0; i < N; i++) {
      p[i * 3 + 1] += .0007;
      p[i * 3] += Math.sin(t / 3000 + i) * .0004;
      if (p[i * 3 + 1] > 3.2) p[i * 3 + 1] = .4;
    }
    geo.attributes.position.needsUpdate = true;
    loopOriginal(t);
  };

  /* ---------- Tarefas: lista limpa, sem ícones, por prioridade ---------- */
  window.item = function (t, click) {
    const m = Math.max(0, t.left);
    const tempo = m >= 60 ? (m / 60 | 0) + "h" + String(m % 60).padStart(2, "0") : m + " min";
    const prio = ["normal", "alta", "urgente"][t.pri - 1];
    return `<div class="tk p${t.pri}" onclick="${click}" title="Prioridade ${prio}"><span class="pd"></span>` +
      `<div class="tx"><b>${t.title}</b><small>${t.sub}</small><i class="bar"><u style="width:${clamp(t.left / t.tot * 100)}%"></u></i></div>` +
      `<time>${tempo}</time></div>`;
  };

  const spawnOriginal = window.spawn;                           // no máximo 6 tarefas na mesa
  window.spawn = function (k) { if (S.tasks.length < 6) spawnOriginal(k); };

  /* ---------- Aba "Painel" no PC (dinheiro, reputação, equipe, clientes) ---------- */
  TABS[3][1] = "Painel";

  const panelOriginal = window.renderPanel;
  window.renderPanel = function () {
    panelOriginal();
    if (view === "pc" && tab === "rep") {
      const bar = v => `<i class="bar"><u style="width:${clamp(v)}%"></u></i>`;
      const kpi = (l, v, b) => `<div class="kpi"><span>${l}</span><b>${v}</b>${b || ""}</div>`;
      $("pbody").innerHTML =
        `<div class="kpis">${kpi("Dinheiro", "R$ " + Math.round(S.money))}${kpi("Reputação", Math.round(S.rep), bar(S.rep))}` +
        `${kpi("Equipe", Math.round(S.soc), bar(S.soc))}${kpi("Clientes", Math.round(S.cust), bar(S.cust))}` +
        `${kpi("Energia", Math.round(S.energy) + "%", bar(S.energy))}${kpi("Estresse", Math.round(stress()) + "%", bar(stress()))}</div>` +
        `<div class="kline"><span>Dia ${S.day} · ${role()}</span><span>Concluídas ${S.done}</span><span>Perdidas ${S.missed}</span>` +
        `<span>Combo x${Math.max(1, S.combo)}</span><span>Rank ${rank()}</span></div>`;
    }
  };

  /* ---------- HUD: tarefas ordenadas, estresse no topo, sem bloco de números ---------- */
  const hudOriginal = window.renderHUD;
  window.renderHUD = function () {
    hudOriginal();
    const l = S.tasks.slice().sort((a, b) => b.pri - a.pri || a.left - b.left);
    $("tasks").innerHTML =
      l.slice(0, 5).map(t => item(t, `goTask(${t.id})`)).join("") +
      (l.length > 5 ? `<div class="mais">+${l.length - 5} na fila</div>` : "") ||
      `<div class="vazio">Nenhuma tarefa pendente.</div>`;

    const st = document.querySelector("#skills .stats"); if (st) st.remove();
    const r = document.querySelectorAll("#skills .sk.r"); if (r.length > 1) r[r.length - 1].remove();

    const s = Math.round(stress()), el = $("stressTop");
    el.className = s > 70 ? "alto" : s > 40 ? "med" : "";
    el.querySelector("u").style.width = s + "%";
    el.querySelector("b").textContent = s + "%";

    if (view === "pc" && tab === "rep") renderPanel();
  };

  /* ---------- Eventos: mais variados, espaçados e que mexem na rotina ---------- */
  const EV = [
    ["Bônus da diretoria pelo bom trimestre.", { money: 200, self: 2 }],
    ["Um cliente importante elogiou a empresa.", { rep: 8, cust: 6, com: 2 }],
    ["A campanha de marketing deu resultado: novos clientes.", { cust: 12 }],
    ["A equipe comemorou uma meta batida.", { soc: 8, energy: 4 }],
    ["Café fresco na copa: o clima melhorou.", { soc: 5, energy: 6 }],
    ["Um fornecedor ofereceu desconto por pagamento antecipado.", { money: 120 }],
    ["A internet caiu por alguns minutos.", { energy: -4 }, () => spawn("email")],
    ["Reunião surpresa da diretoria: chegaram e-mails urgentes.", { rep: -2 }, () => { spawn("email"); spawn("email"); }],
    ["Um funcionário pediu feedback sobre o próprio trabalho.", {}, () => spawn("emp")],
    ["Auditoria interna: há documentos para organizar.", { prob: 1 }, () => { spawn("doc"); spawn("doc"); }],
    ["Reclamação nas redes sociais sobre um atendimento.", { rep: -6, cust: -4 }, () => spawn("call")],
    ["A impressora travou papel.", { money: -50 }, () => { S.jam = true; }]
  ];
  let proximo = S.time + rnd(60, 110), dia = S.day;

  const tickOriginal = window.tick;
  window.tick = function () {
    if (over || paused()) return;
    tickOriginal();
    if (S.day !== dia) { dia = S.day; proximo = S.time + rnd(60, 110); }
    if (!over && S.time >= proximo && S.time < DE - 30) {
      proximo = S.time + rnd(70, 130);
      const e = pick(EV), efeito = fx2(e[1]);
      apply(e[1]);
      if (e[2]) e[2]();
      const texto = e[0] + (efeito ? " (" + efeito + ")" : "");
      if (e[2]) showPopup(texto, "Acontecimento"); else toast(texto);
      dirty = 1; refresh();
    }
  };

  /* ---------- Conexão com o site: cada tarefa concluída ou perdida vai para o banco ---------- */
  const HAB = { email: "com", doc: "prob", emp: "emp", call: "com", print: "self" };

  function enviar(habilidade, acertou) {
    try {
      fetch("/api/missao", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ habilidade, acertou }),
        keepalive: true
      }).catch(() => {});
    } catch (e) {}
  }

  const completeOriginal = window.complete;
  window.complete = function (t, fx, msg) {
    const hab = Object.keys(fx).find(k => k in SK) || HAB[t.k];
    const ok = ((fx.rep || 0) + (fx.cust || 0) + (fx.soc || 0) + (fx.money || 0)) > 0;
    enviar(hab, ok);
    completeOriginal(t, fx, msg);
  };

  const expireOriginal = window.expire;
  window.expire = function (t) {
    enviar(HAB[t.k], false);
    expireOriginal(t);
  };
})();