/* Alynne Studio: app da Alynne (front-end sem framework) */
(() => {
  "use strict";

  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const PALAVRAS_POR_SEGUNDO = 2.5;
  const ERROS_DE_DOWNLOAD = ["download_bloqueado", "download_falhou", "privado", "sem_video"];

  const estado = {
    config: null,
    jobTimer: null,
    gravar: { cenas: [], idx: 0, fonte: 30 },
  };

  // ------------------------------------------------------------ armazenamento local
  function ler(chave, padrao) {
    try {
      const v = localStorage.getItem(chave);
      return v ? JSON.parse(v) : padrao;
    } catch (e) { return padrao; }
  }
  function gravar(chave, valor) {
    try { localStorage.setItem(chave, JSON.stringify(valor)); return true; }
    catch (e) {
      if (chave === "rv_historico" && Array.isArray(valor) && valor.length > 5) {
        return gravar(chave, valor.slice(0, valor.length - 5));
      }
      return false;
    }
  }
  function remover(chave) { try { localStorage.removeItem(chave); } catch (e) { /* ok */ } }

  const historico = () => ler("rv_historico", []);
  function salvarItem(item) {
    const lista = historico().filter((i) => i.id !== item.id);
    lista.unshift(item);
    gravar("rv_historico", lista.slice(0, 40));
  }
  const acharItem = (id) => historico().find((i) => i.id === id);

  function perfilAtual() {
    const padrao = (estado.config && estado.config.perfil_padrao) || {};
    return Object.assign({}, padrao, ler("rv_perfil", {}));
  }

  // ------------------------------------------------------------ utilidades
  const esc = (s) => String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const extrairLink = (t) => { const m = String(t || "").match(/https?:\/\/[^\s<>"']+/); return m ? m[0].replace(/[.,;)]+$/, "") : ""; };
  const contarPalavras = (t) => (String(t || "").trim().match(/\S+/g) || []).length;
  const numeroBR = (n) => (n == null ? "" : Number(n).toLocaleString("pt-BR"));
  const compacto = (n) => {
    if (n == null) return "";
    if (n >= 1e6) return (n / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " mi";
    if (n >= 1e3) return (n / 1e3).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " mil";
    return String(n);
  };
  const dataCurta = (ms) => new Date(ms).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

  let toastTimer;
  function toast(msg) {
    const t = $("#toast");
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, 2400);
  }

  async function copiar(texto, msg = "Copiado") {
    try { await navigator.clipboard.writeText(texto); toast(msg); }
    catch (e) {
      const area = document.createElement("textarea");
      area.value = texto; document.body.appendChild(area); area.select();
      try { document.execCommand("copy"); toast(msg); } catch (e2) { toast("Não consegui copiar"); }
      area.remove();
    }
  }

  async function api(caminho, opcoes = {}) {
    const resp = await fetch(caminho, Object.assign({ credentials: "same-origin" }, opcoes));
    let corpo = {};
    try { corpo = await resp.json(); } catch (e) { /* sem corpo */ }
    if (resp.status === 401 && corpo.codigo === "sem_login") { mostrarLogin(); throw new Error("sem_login"); }
    if (!resp.ok) {
      const erro = new Error(corpo.detail || corpo.erro || "Algo deu errado. Tente de novo.");
      erro.status = resp.status;
      throw erro;
    }
    return corpo;
  }

  // ------------------------------------------------------------ navegação
  const VIEWS = ["login", "criar", "processando", "resultado", "calendario", "analise", "historico", "perfil"];
  const ABA_DA_VIEW = { criar: "criar", processando: "criar", resultado: "historico", calendario: "calendario",
    analise: "analise", historico: "historico", perfil: "perfil" };
  function mostrar(nome) {
    VIEWS.forEach((v) => { $("#v-" + v).hidden = v !== nome; });
    document.body.classList.toggle("modo-login", nome === "login");
    $$(".aba").forEach((b) => b.classList.toggle("ativo", b.dataset.ir === ABA_DA_VIEW[nome]));
    window.scrollTo(0, 0);
  }
  function ir(nome, id) { location.hash = id ? `${nome}/${id}` : nome; }

  function rota() {
    if (estado.precisaLogin) return mostrar("login");
    const [nome, id] = (location.hash.replace("#", "") || "criar").split("/");
    if (nome === "resultado" && id) {
      const item = acharItem(id);
      if (!item) return ir("criar");
      renderResultado(item);
      return mostrar("resultado");
    }
    if (nome === "historico") { renderHistorico(); return mostrar("historico"); }
    if (nome === "perfil") { carregarPerfil(); return mostrar("perfil"); }
    if (nome === "calendario") return mostrar("calendario");
    if (nome === "analise") { renderInspiracoes(); return mostrar("analise"); }
    if (nome === "processando") {
      if (!estado.processando && !ler("rv_job", null)) return ir("criar");
      return mostrar("processando");
    }
    atualizarResumoPerfil();
    mostrar("criar");
  }

  document.addEventListener("click", (e) => {
    const alvo = e.target.closest("[data-ir]");
    if (alvo) { e.preventDefault(); ir(alvo.dataset.ir); }
  });
  window.addEventListener("hashchange", rota);

  // ------------------------------------------------------------ login
  function mostrarLogin() {
    estado.precisaLogin = true;
    mostrar("login");
    setTimeout(() => $("#senha").focus(), 100);
  }
  $("#form-login").addEventListener("submit", async (e) => {
    e.preventDefault();
    const erro = $("#erro-login");
    erro.hidden = true;
    try {
      await api("/api/login", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ senha: $("#senha").value }),
      });
      estado.precisaLogin = false;
      $("#senha").value = "";
      rota();
      retomarJob();
    } catch (err) {
      erro.textContent = err.message; erro.hidden = false;
    }
  });

  // ------------------------------------------------------------ criar
  function valorChip(grupo) {
    const b = $(`.chips[data-grupo="${grupo}"] .chip.ativo`);
    return b ? b.dataset.valor : "";
  }
  function marcarChip(grupo, valor) {
    $$(`.chips[data-grupo="${grupo}"] .chip`).forEach((b) => b.classList.toggle("ativo", b.dataset.valor === valor));
  }
  $$(".chips[data-grupo]").forEach((grupo) => {
    grupo.addEventListener("click", (e) => {
      const b = e.target.closest(".chip");
      if (b) marcarChip(grupo.dataset.grupo, b.dataset.valor);
    });
  });

  function carregarUltimoPedido() {
    const u = ler("rv_ultimo_pedido", {});
    marcarChip("criar", u.criar || "Reels");
    marcarChip("estilo", u.estilo || "Natural");
    marcarChip("duracao", u.duracao || "30s");
    $("#nicho").value = u.nicho || "";
  }

  $("#btn-colar").addEventListener("click", async () => {
    try {
      const texto = await navigator.clipboard.readText();
      const link = extrairLink(texto);
      if (link) { $("#link").value = link; toast("Link colado"); }
      else toast("Não achei um link copiado");
    } catch (e) { $("#link").focus(); toast("Toque e segure no campo para colar"); }
  });
  $("#link").addEventListener("paste", () => {
    setTimeout(() => { const l = extrairLink($("#link").value); if (l) $("#link").value = l; }, 0);
  });

  $("#arquivo").addEventListener("change", () => {
    const f = $("#arquivo").files[0];
    $("#envio-escolhido").hidden = !f;
    $(".envio-btn").hidden = !!f;
    if (f) {
      const mb = f.size / 1048576;
      $("#envio-nome").textContent = `${f.name} (${mb.toFixed(0)} MB)`;
      const limite = (estado.config && estado.config.max_upload_mb) || 200;
      if (mb > limite) { toast(`O arquivo passa de ${limite} MB`); limparArquivo(); }
    }
  });
  function limparArquivo() {
    $("#arquivo").value = "";
    $("#envio-escolhido").hidden = true;
    $(".envio-btn").hidden = false;
  }
  $("#btn-tirar-arquivo").addEventListener("click", limparArquivo);

  function erroCriar(msg) {
    const el = $("#erro-criar");
    el.textContent = msg || ""; el.hidden = !msg;
    if (msg) el.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  $("#form-criar").addEventListener("submit", (e) => {
    e.preventDefault();
    erroCriar("");
    const link = extrairLink($("#link").value);
    const arquivo = $("#arquivo").files[0];
    const tema = $("#tema").value.trim();
    if (!link && !arquivo) return erroCriar("Cole o link do vídeo ou envie o arquivo.");
    if (!tema) return erroCriar("Escreva sobre o que será o seu vídeo. É isso que garante o tema certo.");

    const pedido = {
      criar: valorChip("criar"),
      nicho: $("#nicho").value.trim(),
      tema,
      produto: $("#produto").value.trim(),
      estilo: valorChip("estilo"),
      duracao: valorChip("duracao"),
      observacoes: $("#observacoes").value.trim(),
    };
    gravar("rv_ultimo_pedido", { criar: pedido.criar, estilo: pedido.estilo, duracao: pedido.duracao, nicho: pedido.nicho });

    const dados = new FormData();
    dados.append("link", link);
    dados.append("pedido", JSON.stringify(pedido));
    dados.append("perfil", JSON.stringify(perfilAtual()));
    if (arquivo) dados.append("arquivo", arquivo, arquivo.name);

    iniciarProcessando(arquivo ? "Enviando o vídeo" : "Criando seu roteiro");
    const barra = $("#upload-barra");
    barra.hidden = !arquivo;

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/gerar");
    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable) $("#upload-progresso").style.width = `${Math.round((ev.loaded / ev.total) * 100)}%`;
    };
    xhr.onload = () => {
      barra.hidden = true;
      let corpo = {};
      try { corpo = JSON.parse(xhr.responseText); } catch (err) { /* nada */ }
      if (xhr.status === 401) return mostrarLogin();
      if (xhr.status >= 400 || !corpo.job_id) return mostrarErroProc(corpo.detail || "Não consegui começar. Tente de novo.");
      gravar("rv_job", { id: corpo.job_id, tipo: "gerar", pedido, link, criado: Date.now() });
      $("#proc-titulo").textContent = "Criando seu roteiro";
      acompanharJob();
    };
    xhr.onerror = () => { barra.hidden = true; mostrarErroProc("Sem conexão. Confira a internet e tente de novo."); };
    xhr.send(dados);
  });

  $("#tema").addEventListener("focus", () => {
    if (!$("#tema-mesmo")) {
      const b = document.createElement("button");
      b.type = "button"; b.id = "tema-mesmo"; b.className = "link-btn"; b.style.marginTop = "8px";
      b.textContent = "Usar o mesmo tema do vídeo, do meu jeito";
      b.addEventListener("click", () => {
        $("#tema").value = "O mesmo tema do vídeo de referência, contado a partir da minha experiência e da minha rotina.";
      });
      $("#tema").parentElement.appendChild(b);
    }
  }, { once: true });

  // ------------------------------------------------------------ processamento
  function iniciarProcessando(titulo) {
    estado.processando = true;
    $("#proc-titulo").textContent = titulo;
    $("#proc-sub").textContent = "Leva de 1 a 2 minutos. Pode deixar a tela aberta.";
    $("#etapas").innerHTML = "";
    $("#proc-erro").hidden = true;
    $("#upload-progresso").style.width = "0";
    location.hash = "processando";
    mostrar("processando");
  }

  function renderEtapas(etapas) {
    $("#etapas").innerHTML = (etapas || [])
      .map((e) => `<li class="${esc(e.status)}">${esc(e.nome)}</li>`).join("");
  }

  function mostrarErroProc(msg, codigo) {
    estado.processando = false;
    clearTimeout(estado.jobTimer);
    remover("rv_job");
    $("#proc-titulo").textContent = "Não deu certo desta vez";
    $("#proc-sub").textContent = "";
    $("#proc-erro-texto").textContent = msg;
    $("#btn-enviar-arquivo").hidden = !ERROS_DE_DOWNLOAD.includes(codigo);
    $("#proc-erro").hidden = false;
  }

  $("#btn-tentar-de-novo").addEventListener("click", () => history.length > 1 ? history.back() : ir("criar"));
  $("#btn-enviar-arquivo").addEventListener("click", () => {
    ir("criar");
    setTimeout(() => {
      $("#envio").scrollIntoView({ behavior: "smooth", block: "center" });
      $("#ajuda-envio").textContent = "O Instagram às vezes bloqueia o link. Grave a tela com som (ou salve o vídeo) e envie aqui.";
      $("#arquivo").click();
    }, 250);
  });

  async function acompanharJob() {
    const job = ler("rv_job", null);
    if (!job) return;
    let dados;
    try {
      dados = await api(`/api/job/${job.id}`);
    } catch (err) {
      if (err.message === "sem_login") return;
      if (err.status === 404) return mostrarErroProc("O servidor reiniciou no meio do processo. Gere de novo, por favor.");
      estado.jobTimer = setTimeout(acompanharJob, 4000); // falha de rede passageira
      return;
    }
    renderEtapas(dados.etapas);
    if (dados.status === "erro") return mostrarErroProc(dados.erro, dados.codigo);
    if (dados.status === "pronto") {
      estado.processando = false;
      remover("rv_job");
      let item;
      if (job.tipo === "ajustar") {
        item = acharItem(job.itemId);
        if (!item) return ir("criar");
        item.anterior = item.resultado;
        item.resultado = dados.resultado;
        item.checklist = {};
        item.ajustes = (item.ajustes || 0) + 1;
      } else {
        const meta = Object.assign({}, dados.meta || {});
        if (meta.transcricao) meta.transcricao = String(meta.transcricao).slice(0, 8000);
        item = {
          id: Date.now().toString(36), criado: Date.now(), pedido: job.pedido,
          meta, resultado: dados.resultado, checklist: {},
        };
        $("#link").value = ""; limparArquivo();
      }
      salvarItem(item);
      toast(job.tipo === "ajustar" ? "Roteiro ajustado" : "Seu roteiro está pronto");
      history.replaceState(null, "", `#resultado/${item.id}`);
      return rota();
    }
    estado.jobTimer = setTimeout(acompanharJob, 2500);
  }

  function retomarJob() {
    const job = ler("rv_job", null);
    if (!job) return;
    if (Date.now() - job.criado > 30 * 60 * 1000) return remover("rv_job");
    $("#proc-titulo").textContent = job.tipo === "ajustar" ? "Ajustando seu roteiro" : "Criando seu roteiro";
    $("#proc-erro").hidden = true;
    estado.processando = true;
    location.hash = "processando";
    mostrar("processando");
    acompanharJob();
  }

  // ------------------------------------------------------------ resultado
  const ROTULOS_ANALISE = [
    ["tema", "Tema principal"], ["nicho", "Nicho"], ["publico", "Público provável"], ["objetivo", "Objetivo"],
    ["tipo", "Tipo de conteúdo"], ["gancho", "Gancho"], ["mecanismo_curiosidade", "Mecanismo de curiosidade"],
    ["estrutura_narrativa", "Estrutura narrativa"], ["desenvolvimento", "Desenvolvimento"],
    ["como_mantem_atencao", "Como mantém a atenção"], ["quebra_de_padrao", "Quebra de padrão"], ["cta", "CTA"],
    ["elementos_visuais", "Elementos visuais"], ["ritmo_edicao", "Ritmo de edição"], ["texto_na_tela", "Texto na tela"],
    ["demonstracao", "Demonstração, produto ou pessoa"], ["emocao_desejo", "Emoção ou desejo"],
    ["mecanismo_retencao", "Por que retém"],
  ];
  const CHECKLIST_GRAVACAO = ["Gancho", "Desenvolvimento", "Demonstração", "CTA", "B-roll", "Texto na tela"];

  function medidas(r) {
    const cenas = (r.roteiro && r.roteiro.cenas) || [];
    const falas = cenas.map((c) => c.fala).concat([(r.roteiro && r.roteiro.cta && r.roteiro.cta.fala) || ""]);
    const palavras = falas.reduce((s, f) => s + contarPalavras(f), 0);
    return { cenas: cenas.length, palavras, segundos: Math.round(palavras / PALAVRAS_POR_SEGUNDO) };
  }

  function lista(arr) { return (arr || []).filter(Boolean); }

  function renderResultado(item) {
    const r = item.resultado || {};
    const rot = r.roteiro || {};
    const a = r.analise || {};
    const f = r.formula || {};
    const v = r.variacoes || {};
    const m = item.meta || {};
    const med = medidas(r);
    const passos = String(f.sequencia || "").split(/→|->|>/).map((s) => s.trim()).filter(Boolean);

    const origemPartes = [m.autor, m.views != null ? `${compacto(m.views)} views` : "", m.likes != null ? `${compacto(m.likes)} curtidas` : ""].filter(Boolean);
    const avisos = lista(r.avisos);
    const preencher = lista(r.campos_para_preencher);

    const cenasHtml = (rot.cenas || []).map((c, i) => `
      <article class="cena">
        <div class="cena-topo">
          <span class="cena-num">Cena ${i + 1}${i === 0 ? " · gancho" : ""}</span>
          <span class="cena-tempo">${esc(c.tempo)}</span>
        </div>
        ${c.fala ? `<p class="fala">${esc(c.fala)}</p>` : `<p class="fala vazia">Sem fala nesta cena</p>`}
        <div class="cena-detalhes">
          ${c.visual ? `<span><b>Mostrar:</b> ${esc(c.visual)}</span>` : ""}
          ${c.enquadramento ? `<span><b>Enquadramento:</b> ${esc(c.enquadramento)}</span>` : ""}
          ${c.acao ? `<span><b>Ação:</b> ${esc(c.acao)}</span>` : ""}
        </div>
        ${c.texto_na_tela ? `<span class="texto-tela">${esc(c.texto_na_tela)}</span>` : ""}
      </article>`).join("");

    const cta = rot.cta || {};
    const ed = rot.edicao || {};
    const segunda = v.segunda_ideia || {};
    const checklist = item.checklist || {};

    $("#resultado").innerHTML = `
      <div class="res-origem">
        ${m.miniatura ? `<img src="${esc(m.miniatura)}" alt="">` : ""}
        <div>
          <div>Referência: ${m.url ? `<a href="${esc(m.url)}" target="_blank" rel="noopener">${esc(m.plataforma || "vídeo")}</a>` : esc(m.plataforma || "vídeo enviado")}</div>
          ${origemPartes.length ? `<div>${esc(origemPartes.join(" · "))}</div>` : ""}
        </div>
      </div>

      <h1 class="res-titulo">${esc(rot.titulo)}</h1>
      <p class="res-conceito">${esc(rot.conceito)}</p>
      <div class="res-medidas">
        <span class="medida">${med.cenas + 1} cenas</span>
        <span class="medida">≈ ${med.segundos}s de fala</span>
        <span class="medida">${esc(item.pedido && item.pedido.duracao || "")} · ${esc(item.pedido && item.pedido.estilo || "")}</span>
      </div>

      <div class="acoes-resultado">
        <button class="btn primario grande" id="btn-gravar">▶ Modo gravar</button>
        <button class="btn suave" id="btn-copiar-falas">Copiar falas</button>
        <button class="btn suave" id="btn-copiar-tudo">Copiar tudo</button>
      </div>

      ${preencher.length ? `<div class="caixa-aviso"><strong>Antes de gravar, complete com a sua verdade:</strong><ul>${preencher.map((p) => `<li>${esc(p)}</li>`).join("")}</ul></div>` : ""}
      ${avisos.length ? `<div class="caixa-aviso caixa-info"><ul>${avisos.map((p) => `<li>${esc(p)}</li>`).join("")}</ul></div>` : ""}

      <section class="bloco">
        <h2 class="bloco-titulo">Por que o vídeo funcionou</h2>
        <div class="formula">
          <div class="formula-passos">${passos.map((p, i) => `${i ? '<span class="seta">→</span>' : ""}<span class="passo">${esc(p)}</span>`).join("")}</div>
          <p><strong>${esc(f.explicacao)}</strong></p>
          <p>${esc(f.por_que_funciona)}</p>
          <details class="analise">
            <summary>Ver análise do vídeo</summary>
            <dl class="lista-def">
              ${[["Tema", a.tema], ["Tipo", a.tipo], ["Gancho", a.gancho], ["Mecanismo de retenção", a.mecanismo_retencao], ["Estrutura", a.estrutura_narrativa], ["CTA", a.cta], ["Fórmula viral", f.sequencia]]
                .map(([k, val]) => `<div><dt>${esc(k)}</dt><dd>${esc(val)}</dd></div>`).join("")}
            </dl>
            <details class="analise">
              <summary>Análise completa</summary>
              <dl class="lista-def">
                ${ROTULOS_ANALISE.map(([k, rot2]) => `<div><dt>${esc(rot2)}</dt><dd>${esc(a[k])}</dd></div>`).join("")}
              </dl>
            </details>
          </details>
        </div>
      </section>

      <section class="bloco">
        <h2 class="bloco-titulo">Roteiro pronto</h2>
        ${cenasHtml}
        <article class="cena cta">
          <div class="cena-topo"><span class="cena-num">CTA · final</span><span class="cena-tempo">${esc(cta.tempo)}</span></div>
          <p class="fala">${esc(cta.fala)}</p>
          <div class="cena-detalhes">${cta.visual ? `<span><b>Mostrar:</b> ${esc(cta.visual)}</span>` : ""}</div>
          ${cta.texto_na_tela ? `<span class="texto-tela">${esc(cta.texto_na_tela)}</span>` : ""}
        </article>
      </section>

      <section class="bloco">
        <h2 class="bloco-titulo">Legenda <button class="link-btn" id="btn-copiar-legenda">copiar</button></h2>
        <p class="texto-corrido">${esc(rot.legenda)}</p>
      </section>

      <section class="bloco">
        <h2 class="bloco-titulo">Edição</h2>
        <dl class="lista-def edicao">
          ${[["Cortes", ed.cortes], ["Zooms", ed.zooms], ["Enquadramento", ed.enquadramento], ["Textos", ed.momentos_de_texto], ["Ritmo", ed.ritmo], ["Efeitos", ed.efeitos]]
            .filter(([, val]) => val).map(([k, val]) => `<div><dt>${esc(k)}</dt><dd>${esc(val)}</dd></div>`).join("")}
        </dl>
      </section>

      <section class="bloco">
        <h2 class="bloco-titulo">Textos na tela <button class="link-btn" id="btn-copiar-textos">copiar</button></h2>
        <ol class="lista-simples">${lista(rot.textos_na_tela).map((t) => `<li>${esc(t)}</li>`).join("")}</ol>
      </section>

      <section class="bloco">
        <h2 class="bloco-titulo">B-roll para gravar</h2>
        <ul class="lista-simples">${lista(rot.broll).map((t) => `<li>${esc(t)}</li>`).join("")}</ul>
      </section>

      <section class="bloco">
        <h2 class="bloco-titulo">Outros ganchos</h2>
        <div class="opcoes">${lista(v.ganchos_extras).map((g, i) => `
          <div class="opcao"><p>${esc(g)}</p><button class="btn contorno" data-trocar-gancho="${i}">Usar</button></div>`).join("")}
        </div>
      </section>

      <section class="bloco">
        <h2 class="bloco-titulo">Outros CTAs</h2>
        <div class="opcoes">${lista(v.ctas_extras).map((g, i) => `
          <div class="opcao"><p>${esc(g)}</p><button class="btn contorno" data-trocar-cta="${i}">Usar</button></div>`).join("")}
        </div>
      </section>

      <section class="bloco">
        <h2 class="bloco-titulo">Segunda ideia</h2>
        <div class="cena">
          <p class="fala" style="font-size:19px">${esc(segunda.titulo)}</p>
          <p style="margin:0 0 10px;color:var(--tinta-2)">${esc(segunda.conceito)}</p>
          ${segunda.gancho ? `<p style="margin:0 0 10px"><b>Gancho:</b> ${esc(segunda.gancho)}</p>` : ""}
          <ol class="lista-simples">${lista(segunda.passos).map((p) => `<li>${esc(p)}</li>`).join("")}</ol>
        </div>
      </section>

      <section class="bloco">
        <h2 class="bloco-titulo">Checklist de gravação</h2>
        <div class="checklist">${CHECKLIST_GRAVACAO.map((c) => `
          <label><input type="checkbox" data-check="${esc(c)}" ${checklist[c] ? "checked" : ""}><span>${esc(c)}</span></label>`).join("")}
        </div>
      </section>

      <section class="bloco">
        <h2 class="bloco-titulo">Quer ajustar?</h2>
        <div class="ajustar">
          <div class="chips" id="chips-ajuste">
            ${["Mais curto", "Mais do meu jeito de falar", "Outro gancho", "Mais leve e engraçado", "Mais emocional", "Outra ideia"].map((c) => `<button type="button" class="chip" data-ajuste="${esc(c)}">${esc(c)}</button>`).join("")}
          </div>
          <textarea id="texto-ajuste" rows="2" placeholder="Ou escreva o que mudar. Ex.: quero gravar sem aparecer o rosto"></textarea>
          <button class="btn primario" id="btn-ajustar">Ajustar roteiro</button>
          ${item.anterior ? `<button class="link-btn" id="btn-desfazer">Voltar para a versão anterior</button>` : ""}
        </div>
      </section>

      <div class="acoes-linha" style="margin-top:28px">
        <button class="btn contorno" data-ir="criar">Novo roteiro</button>
      </div>
    `;

    $("#btn-gravar").onclick = () => abrirGravar(item);
    $("#btn-copiar-falas").onclick = () => copiar(textoFalas(item), "Falas copiadas");
    $("#btn-copiar-tudo").onclick = () => copiar(textoCompleto(item), "Roteiro completo copiado");
    $("#btn-copiar-legenda").onclick = () => copiar(rot.legenda || "", "Legenda copiada");
    $("#btn-copiar-textos").onclick = () => copiar(lista(rot.textos_na_tela).join("\n"), "Textos copiados");

    $$("[data-trocar-gancho]").forEach((b) => b.addEventListener("click", () => {
      const i = Number(b.dataset.trocarGancho);
      const atual = acharItem(item.id) || item;
      const cenas = atual.resultado.roteiro.cenas || [];
      if (!cenas.length) return;
      const extras = atual.resultado.variacoes.ganchos_extras;
      [cenas[0].fala, extras[i]] = [extras[i], cenas[0].fala];
      salvarItem(atual); renderResultado(atual); toast("Gancho trocado na cena 1");
    }));
    $$("[data-trocar-cta]").forEach((b) => b.addEventListener("click", () => {
      const i = Number(b.dataset.trocarCta);
      const atual = acharItem(item.id) || item;
      const extras = atual.resultado.variacoes.ctas_extras;
      [atual.resultado.roteiro.cta.fala, extras[i]] = [extras[i], atual.resultado.roteiro.cta.fala];
      salvarItem(atual); renderResultado(atual); toast("CTA trocado");
    }));
    $$("[data-check]").forEach((c) => c.addEventListener("change", () => {
      const atual = acharItem(item.id) || item;
      atual.checklist = atual.checklist || {};
      atual.checklist[c.dataset.check] = c.checked;
      salvarItem(atual);
    }));

    $("#chips-ajuste").addEventListener("click", (e) => {
      const b = e.target.closest("[data-ajuste]");
      if (!b) return;
      b.classList.toggle("ativo");
    });
    $("#btn-ajustar").onclick = () => pedirAjuste(item);
    const desfazer = $("#btn-desfazer");
    if (desfazer) desfazer.onclick = () => {
      const atual = acharItem(item.id) || item;
      [atual.resultado, atual.anterior] = [atual.anterior, null];
      salvarItem(atual); renderResultado(atual); toast("Versão anterior de volta");
    };
  }

  async function pedirAjuste(item) {
    const chips = $$("#chips-ajuste .chip.ativo").map((b) => b.dataset.ajuste);
    const texto = $("#texto-ajuste").value.trim();
    const instrucao = chips.concat(texto ? [texto] : []).join(". ");
    if (!instrucao) return toast("Escolha ou escreva o que ajustar");
    const atual = acharItem(item.id) || item;
    try {
      iniciarProcessando("Ajustando seu roteiro");
      const corpo = await api("/api/ajustar", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resultado: atual.resultado, meta: Object.assign({}, atual.meta, { miniatura: "" }),
          pedido: atual.pedido, perfil: perfilAtual(), instrucao,
        }),
      });
      gravar("rv_job", { id: corpo.job_id, tipo: "ajustar", itemId: atual.id, criado: Date.now() });
      acompanharJob();
    } catch (err) {
      if (err.message !== "sem_login") mostrarErroProc(err.message);
    }
  }

  // ------------------------------------------------------------ textos para copiar
  function textoFalas(item) {
    const rot = (item.resultado && item.resultado.roteiro) || {};
    const linhas = (rot.cenas || []).map((c, i) => `CENA ${i + 1} (${c.tempo})\n${c.fala || "(sem fala)"}`);
    if (rot.cta) linhas.push(`CTA (${rot.cta.tempo || ""})\n${rot.cta.fala || ""}`);
    return `${rot.titulo || ""}\n\n${linhas.join("\n\n")}`;
  }

  function textoCompleto(item) {
    const r = item.resultado || {};
    const a = r.analise || {}, f = r.formula || {}, rot = r.roteiro || {}, v = r.variacoes || {}, ed = rot.edicao || {};
    const s = v.segunda_ideia || {};
    const L = [];
    L.push("ANÁLISE DO VÍDEO", "");
    L.push(`* Tema: ${a.tema || ""}`, `* Tipo: ${a.tipo || ""}`, `* Gancho: ${a.gancho || ""}`,
      `* Mecanismo de retenção: ${a.mecanismo_retencao || ""}`, `* Estrutura: ${a.estrutura_narrativa || ""}`,
      `* CTA: ${a.cta || ""}`, `* Fórmula viral: ${f.sequencia || ""} (${f.explicacao || ""})`, "");
    L.push("ROTEIRO PRONTO", "", `Título: ${rot.titulo || ""}`, `Conceito: ${rot.conceito || ""}`, "");
    (rot.cenas || []).forEach((c, i) => {
      const extra = [c.enquadramento, c.acao].filter(Boolean).join("; ");
      L.push(`CENA ${i + 1} (${c.tempo || ""})`, `Fala: ${c.fala || ""}`,
        `Visual: ${c.visual || ""}${extra ? ` (${extra})` : ""}`, `Texto na tela: ${c.texto_na_tela || ""}`, "");
    });
    const cta = rot.cta || {};
    L.push(`CTA: ${cta.fala || ""}`, `Texto na tela: ${cta.texto_na_tela || ""}`, "");
    L.push("EDIÇÃO", `Cortes: ${ed.cortes || ""}`, `Zooms: ${ed.zooms || ""}`, `Enquadramento: ${ed.enquadramento || ""}`,
      `Momentos para texto: ${ed.momentos_de_texto || ""}`, `Ritmo: ${ed.ritmo || ""}`, `Efeitos: ${ed.efeitos || ""}`, "");
    L.push("LEGENDA", rot.legenda || "", "");
    L.push("B-ROLL", ...lista(rot.broll).map((b) => `* ${b}`), "");
    L.push("3 GANCHOS EXTRAS", ...lista(v.ganchos_extras).map((g, i) => `${i + 1}. ${g}`), "");
    L.push("2 CTAs EXTRAS", ...lista(v.ctas_extras).map((g, i) => `${i + 1}. ${g}`), "");
    L.push("SEGUNDA IDEIA", `${s.titulo || ""}`, `${s.conceito || ""}`, s.gancho ? `Gancho: ${s.gancho}` : "",
      ...lista(s.passos).map((p, i) => `${i + 1}. ${p}`), "");
    L.push("CHECKLIST DE GRAVAÇÃO", ...CHECKLIST_GRAVACAO.map((c) => `[${(item.checklist || {})[c] ? "x" : " "}] ${c}`));
    return L.join("\n");
  }

  // ------------------------------------------------------------ modo gravar
  function abrirGravar(item) {
    const rot = (item.resultado && item.resultado.roteiro) || {};
    const cenas = (rot.cenas || []).map((c, i) => Object.assign({ rotulo: `Cena ${i + 1}${i === 0 ? " · gancho" : ""}` }, c));
    if (rot.cta) cenas.push(Object.assign({ rotulo: "CTA" }, rot.cta));
    estado.gravar.cenas = cenas;
    estado.gravar.idx = 0;
    estado.gravar.fonte = ler("rv_fonte_gravar", 30);
    $("#gravar").hidden = false;
    document.body.style.overflow = "hidden";
    desenharGravar();
  }
  function desenharGravar() {
    const g = estado.gravar;
    const c = g.cenas[g.idx];
    if (!c) return;
    $("#gravar-contador").textContent = `${g.idx + 1} de ${g.cenas.length}`;
    $("#gravar-corpo").innerHTML = `
      <span class="gravar-tempo">${esc(c.rotulo)} · ${esc(c.tempo || "")}</span>
      <p class="gravar-fala" style="font-size:${g.fonte}px">${esc(c.fala || "(sem fala, só imagem)")}</p>
      <div class="gravar-extra">
        ${c.visual ? `<span><b>Mostrar:</b> ${esc(c.visual)}</span>` : ""}
        ${c.enquadramento ? `<span><b>Enquadramento:</b> ${esc(c.enquadramento)}</span>` : ""}
        ${c.acao ? `<span><b>Ação:</b> ${esc(c.acao)}</span>` : ""}
        ${c.texto_na_tela ? `<span><b>Texto na tela:</b> ${esc(c.texto_na_tela)}</span>` : ""}
      </div>`;
    $("#gravar-ant").disabled = g.idx === 0;
    $("#gravar-prox").textContent = g.idx === g.cenas.length - 1 ? "Concluir" : "Próxima";
  }
  function fecharGravar() { $("#gravar").hidden = true; document.body.style.overflow = ""; }
  $("#gravar-fechar").onclick = fecharGravar;
  $("#gravar-ant").onclick = () => { if (estado.gravar.idx > 0) { estado.gravar.idx--; desenharGravar(); } };
  $("#gravar-prox").onclick = () => {
    const g = estado.gravar;
    if (g.idx >= g.cenas.length - 1) return fecharGravar();
    g.idx++; desenharGravar();
  };
  $("#gravar-maior").onclick = () => { estado.gravar.fonte = Math.min(56, estado.gravar.fonte + 3); gravar("rv_fonte_gravar", estado.gravar.fonte); desenharGravar(); };
  $("#gravar-menor").onclick = () => { estado.gravar.fonte = Math.max(18, estado.gravar.fonte - 3); gravar("rv_fonte_gravar", estado.gravar.fonte); desenharGravar(); };
  document.addEventListener("keydown", (e) => {
    if ($("#gravar").hidden) return;
    if (e.key === "ArrowRight" || e.key === " ") { e.preventDefault(); $("#gravar-prox").click(); }
    if (e.key === "ArrowLeft") $("#gravar-ant").click();
    if (e.key === "Escape") fecharGravar();
  });

  // ------------------------------------------------------------ histórico
  function renderHistorico() {
    const itens = historico();
    const el = $("#lista-historico");
    if (!itens.length) {
      el.innerHTML = `<p class="vazio">Nenhum roteiro ainda. Os que você gerar aparecem aqui.</p>`;
      return;
    }
    el.innerHTML = itens.map((i) => {
      const t = (i.resultado && i.resultado.roteiro && i.resultado.roteiro.titulo) || "Roteiro";
      const mini = i.meta && i.meta.miniatura;
      return `<div class="item-hist" data-abrir="${esc(i.id)}" role="button" tabindex="0">
        ${mini ? `<img src="${esc(mini)}" alt="">` : `<span class="sem-mini"></span>`}
        <div><h3>${esc(t)}</h3><p>${esc(dataCurta(i.criado))} · ${esc((i.pedido && i.pedido.tema) || "").slice(0, 60)}</p></div>
        <button class="apagar" data-apagar="${esc(i.id)}" aria-label="Apagar">apagar</button>
      </div>`;
    }).join("");
  }
  $("#lista-historico").addEventListener("click", (e) => {
    const apagar = e.target.closest("[data-apagar]");
    if (apagar) {
      e.stopPropagation();
      if (confirm("Apagar este roteiro?")) {
        gravar("rv_historico", historico().filter((i) => i.id !== apagar.dataset.apagar));
        renderHistorico();
      }
      return;
    }
    const abrir = e.target.closest("[data-abrir]");
    if (abrir) ir("resultado", abrir.dataset.abrir);
  });

  // ------------------------------------------------------------ perfil
  const CAMPOS_PERFIL = { nome: "#p-nome", instagram: "#p-instagram", descricao: "#p-descricao", publico: "#p-publico", jeito_de_falar: "#p-jeito", evitar: "#p-evitar" };
  function carregarPerfil() {
    const p = perfilAtual();
    Object.entries(CAMPOS_PERFIL).forEach(([k, s]) => { $(s).value = p[k] || ""; });
    $("#perfil-salvo").hidden = true;
  }
  function atualizarResumoPerfil() {
    const p = perfilAtual();
    $("#perfil-resumo-texto").textContent = p.descricao || "Toque para descrever quem você é como creator.";
  }
  $("#form-perfil").addEventListener("submit", (e) => {
    e.preventDefault();
    const p = {};
    Object.entries(CAMPOS_PERFIL).forEach(([k, s]) => { p[k] = $(s).value.trim(); });
    gravar("rv_perfil", p);
    $("#perfil-salvo").hidden = false;
    toast("Perfil salvo");
  });
  $("#btn-perfil-padrao").addEventListener("click", () => {
    if (!confirm("Voltar o perfil para o texto padrão?")) return;
    remover("rv_perfil");
    carregarPerfil();
    toast("Perfil padrão restaurado");
  });
  $("#btn-sair").addEventListener("click", async () => {
    try { await api("/api/logout", { method: "POST" }); } catch (e) { /* ok */ }
    mostrarLogin();
  });

  // ------------------------------------------------------------ perfis de inspiração
  // Salvos neste aparelho por enquanto; na v1.2 passam para o banco do servidor.
  const MAX_INSPIRACOES = 10;
  const CAMINHOS_DE_POST = ["p", "reel", "reels", "tv", "stories", "explore", "accounts", "direct", "s"];
  const inspiracoes = () => ler("rv_inspiracoes", []);

  function extrairUsuario(texto) {
    const t = String(texto || "").trim();
    if (!t) return { erro: "Cole o link do perfil ou o @ da pessoa." };
    const link = extrairLink(t) || (/instagram\.com\//i.test(t) ? "https://" + t.replace(/^\/+/, "") : "");
    if (link) {
      if (!/(^|\.)instagram\.com$/i.test((() => { try { return new URL(link).hostname; } catch (e) { return ""; } })())) {
        return { erro: "Por enquanto a análise funciona com perfis do Instagram." };
      }
      const partes = new URL(link).pathname.split("/").filter(Boolean);
      if (!partes.length) return { erro: "Esse link não tem o nome do perfil." };
      if (CAMINHOS_DE_POST.includes(partes[0].toLowerCase())) {
        return { erro: "Esse é o link de um post. Abra o perfil da pessoa e copie o link de lá." };
      }
      return validarUsuario(partes[0]);
    }
    return validarUsuario(t.replace(/^@/, ""));
  }
  function validarUsuario(u) {
    const usuario = String(u || "").trim().toLowerCase();
    if (!/^[a-z0-9._]{1,30}$/.test(usuario)) return { erro: "Não reconheci esse perfil. Confira o link ou o @." };
    return { usuario };
  }

  function renderInspiracoes() {
    const lista = inspiracoes();
    const el = $("#lista-inspiracoes");
    if (!lista.length) {
      el.innerHTML = `<p class="ajuda">Nenhum perfil ainda. Adicione de 3 a 5 perfis que você admira e que falam com um público parecido com o seu.</p>`;
      return;
    }
    el.innerHTML = lista.map((i) => `
      <div class="inspiracao">
        <span class="mono" aria-hidden="true">${esc(i.usuario.charAt(0).toUpperCase())}</span>
        <div><a href="https://www.instagram.com/${esc(i.usuario)}/" target="_blank" rel="noopener">@${esc(i.usuario)}</a>
          <small>adicionado em ${esc(new Date(i.adicionado).toLocaleDateString("pt-BR"))}</small></div>
        <button class="remover" data-remover-inspiracao="${esc(i.usuario)}" aria-label="Remover @${esc(i.usuario)}">remover</button>
      </div>`).join("");
  }

  $("#form-inspiracao").addEventListener("submit", (e) => {
    e.preventDefault();
    const erro = $("#erro-inspiracao");
    erro.hidden = true;
    const r = extrairUsuario($("#inspiracao").value);
    const lista = inspiracoes();
    if (!r.erro && lista.some((i) => i.usuario === r.usuario)) r.erro = `@${r.usuario} já está na sua lista.`;
    if (!r.erro && lista.length >= MAX_INSPIRACOES) r.erro = `O limite é de ${MAX_INSPIRACOES} perfis. Remova um para adicionar outro.`;
    if (r.erro) { erro.textContent = r.erro; erro.hidden = false; return; }
    lista.push({ usuario: r.usuario, adicionado: Date.now() });
    gravar("rv_inspiracoes", lista);
    $("#inspiracao").value = "";
    renderInspiracoes();
    toast(`@${r.usuario} adicionado`);
  });
  $("#lista-inspiracoes").addEventListener("click", (e) => {
    const b = e.target.closest("[data-remover-inspiracao]");
    if (!b) return;
    const usuario = b.dataset.removerInspiracao;
    if (!confirm(`Remover @${usuario} das inspirações?`)) return;
    gravar("rv_inspiracoes", inspiracoes().filter((i) => i.usuario !== usuario));
    renderInspiracoes();
  });

  // ------------------------------------------------------------ início
  function receberCompartilhamento() {
    const q = new URLSearchParams(location.search);
    const link = extrairLink([q.get("url"), q.get("text"), q.get("title")].filter(Boolean).join(" "));
    if (link) {
      $("#link").value = link;
      history.replaceState(null, "", "/#criar");
      toast("Link recebido");
    }
  }

  async function iniciar() {
    carregarUltimoPedido();
    receberCompartilhamento();
    try {
      estado.config = await api("/api/config");
    } catch (e) {
      estado.config = { perfil_padrao: {}, max_upload_mb: 200 };
    }
    const c = estado.config;
    $("#versao").textContent = c.versao ? `versão ${c.versao}` : "";
    $("#btn-sair").hidden = !c.precisa_senha;
    if (c.precisa_senha && !c.autenticado) return mostrarLogin();
    estado.precisaLogin = false;
    rota();
    retomarJob();
  }

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
  }
  iniciar();
})();
