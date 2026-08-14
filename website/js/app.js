(function () {
  "use strict";

  const state = {
    zoom: 2,
    doc: null,
    pages: 0,
    cur: 0,
    fields: [],
    selIdx: -1,
    chatIdx: -1,
    catalog: null,
    prefix: "",
  };

  function $(id) {
    return document.getElementById(id);
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function escapeAttr(s) {
    return escapeHtml(s).replace(/"/g, "&quot;");
  }

  function docMeta(id) {
    return (state.catalog.docs || []).find((d) => d.id === id);
  }

  function img() {
    return $("pageimg");
  }
  function wrap() {
    return $("pagewrap");
  }
  function scale() {
    const el = img();
    return el.naturalWidth ? el.naturalWidth / el.clientWidth : 1;
  }

  function showPage() {
    if (!state.doc) return;
    const el = img();
    el.src = "pages/" + state.prefix + "-" + state.cur + ".png";
    $("pglabel").textContent = "หน้า " + (state.cur + 1) + " / " + state.pages;
    el.onload = paintMarkers;
  }

  async function loadDoc(name) {
    const meta = docMeta(name);
    if (!meta) return;
    state.doc = name;
    state.pages = meta.pages;
    state.prefix = meta.page_prefix;
    state.zoom = state.catalog.zoom || 2;
    state.cur = 0;
    state.selIdx = -1;
    showPage();
  }

  function paintMarkers() {
    const w = wrap();
    w.querySelectorAll(".marker,.mlabel,.mvalue").forEach((n) => n.remove());
    const s = scale();
    const fillActive = $("panel-fill").classList.contains("active");
    state.fields.forEach((f, i) => {
      if (f.page !== state.cur) return;
      const px = (f.x * state.zoom) / s;
      const py = (f.y * state.zoom) / s;
      const m = document.createElement("div");
      m.className = "marker" + (i === state.selIdx ? " sel" : "");
      m.style.left = px + "px";
      m.style.top = py + "px";
      m.title = f.name + (f.value ? " = " + f.value : "");
      m.onclick = (ev) => {
        ev.stopPropagation();
        if (fillActive) {
          const nv = prompt('ค่าของ "' + f.name + '":', f.value || "");
          if (nv !== null) {
            state.fields[i].value = nv.trim();
            renderAll();
          }
          return;
        }
        state.selIdx = state.selIdx === i ? -1 : i;
        renderAll();
      };
      w.appendChild(m);
      if (f.value) {
        const v = document.createElement("div");
        v.className = "mvalue";
        v.textContent = f.value;
        v.style.left = px + "px";
        v.style.top = py + "px";
        v.style.fontSize = (f.size * state.zoom) / s + "px";
        w.appendChild(v);
      } else {
        const l = document.createElement("div");
        l.className = "mlabel";
        l.textContent = f.name;
        l.style.left = px + "px";
        l.style.top = py - 6 + "px";
        w.appendChild(l);
      }
    });
  }

  function renderList() {
    $("fieldlist").innerHTML = state.fields
      .map((f, i) => {
        const val = f.value ? " = <b>" + escapeHtml(f.value) + "</b>" : "";
        return (
          '<li class="' +
          (i === state.selIdx ? "sel" : "") +
          '" data-i="' +
          i +
          '">' +
          '<span class="fname" data-act="goto">📍 ' +
          escapeHtml(f.name) +
          " <small>(หน้า " +
          (f.page + 1) +
          ", " +
          f.size +
          "pt)</small>" +
          val +
          "</span>" +
          '<button class="del" style="color:#0077ff" data-act="rename" title="เปลี่ยนชื่อฟิลด์">✏️</button>' +
          '<button class="del" data-act="del" title="ลบจุดนี้ทิ้ง">✕</button>' +
          "</li>"
        );
      })
      .join("");
  }

  function renderValues() {
    $("valuelist").innerHTML = state.fields
      .map(
        (f, i) =>
          '<div class="vrow">' +
          '<span class="vname" data-goto="' +
          i +
          '" title="' +
          escapeAttr(f.name) +
          '">📍 ' +
          escapeHtml(f.name) +
          "</span>" +
          '<input data-i="' +
          i +
          '" value="' +
          escapeAttr(f.value || "") +
          '" placeholder="— ว่าง —">' +
          '<button class="del" data-clear="' +
          i +
          '" title="ล้างค่าช่องนี้">✕</button>' +
          "</div>",
      )
      .join("");
  }

  function renderAll() {
    renderList();
    renderValues();
    paintMarkers();
  }

  function gotoField(i) {
    if (state.fields[i].page !== state.cur) {
      state.cur = state.fields[i].page;
      showPage();
    }
  }

  function setTab(tab) {
    document.querySelectorAll("#tabs button").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    $("tab-" + tab).classList.add("active");
    $("panel-" + tab).classList.add("active");
    $("pagewrap").classList.toggle("marking", tab === "edit");
    paintMarkers();
  }

  function bub(text, who) {
    const d = document.createElement("div");
    d.className = "bub " + who;
    d.textContent = text;
    const log = $("chatlog");
    log.appendChild(d);
    log.scrollTop = 1e9;
  }

  function ask() {
    while (state.chatIdx < state.fields.length && state.fields[state.chatIdx].value) {
      state.chatIdx++;
    }
    if (state.chatIdx < state.fields.length) {
      bub("กรอก: " + state.fields[state.chatIdx].name, "bot");
    } else {
      bub('ครบทุกช่องแล้ว ✅ กด "สร้าง PDF" ได้เลย หรือพิมพ์ แก้ [ชื่อฟิลด์] / edit [field] เพื่อแก้ค่า', "bot");
    }
  }

  function startChat() {
    if (!state.fields.length) {
      bub("ยังไม่มีจุดที่มาร์คไว้ — กลับไปแท็บ ① ก่อนครับ", "bot");
      return;
    }
    if (state.chatIdx === -1) {
      state.chatIdx = 0;
      bub("มี " + state.fields.length + " ช่องให้กรอก เริ่มเลย!", "bot");
      ask();
    }
  }

  function handleChat() {
    const input = $("chatinput");
    const v = input.value.trim();
    if (!v) return;
    input.value = "";
    bub(v, "user");
    const m = v.match(/^(?:แก้|edit|fix)\s*(.*)$/i);
    if (m) {
      const q = m[1].trim();
      let i = q ? state.fields.findIndex((f) => f.name === q) : -1;
      if (i < 0 && q) i = state.fields.findIndex((f) => f.name.includes(q));
      if (i < 0) {
        bub('ไม่พบฟิลด์ "' + q + '" — พิมพ์แค่บางส่วนของชื่อก็ได้ หรือแก้ในตารางด้านบน/คลิกจุดบนเอกสารได้เลย', "bot");
        return;
      }
      state.fields[i].value = "";
      state.chatIdx = i;
      renderAll();
      ask();
      return;
    }
    if (state.chatIdx >= 0 && state.chatIdx < state.fields.length) {
      state.fields[state.chatIdx].value = v === "-" ? "" : v;
      if (state.fields[state.chatIdx].page !== state.cur) {
        state.cur = state.fields[state.chatIdx].page;
        showPage();
      }
      renderAll();
      state.chatIdx++;
      ask();
    }
  }

  function tplKey(name) {
    return "fromdd-web-tpl:" + name;
  }

  async function loadTemplate(name) {
    let tpl = null;
    try {
      const raw = localStorage.getItem(tplKey(name));
      if (raw) tpl = JSON.parse(raw);
    } catch (_) {}
    if (!tpl) {
      const res = await fetch("data/templates/" + encodeURIComponent(name) + ".json");
      if (!res.ok) return;
      tpl = await res.json();
    }
    $("tplname").value = name;
    state.fields = tpl.fields || [];
    state.chatIdx = -1;
    $("chatlog").innerHTML = "";
    if (tpl.doc && tpl.doc !== state.doc) {
      $("docsel").value = tpl.doc;
      await loadDoc(tpl.doc);
    }
    renderAll();
  }

  function ascii(s) {
    return new TextEncoder().encode(s);
  }

  function concat(parts) {
    const len = parts.reduce((n, p) => n + p.length, 0);
    const out = new Uint8Array(len);
    let o = 0;
    for (const p of parts) {
      out.set(p, o);
      o += p.length;
    }
    return out;
  }

  function jpegToPdf(jpeg, imgW, imgH, zoom) {
    const pageW = (imgW / zoom).toFixed(2);
    const pageH = (imgH / zoom).toFixed(2);
    const parts = [];
    const offsets = [];
    function add(obj) {
      offsets.push(parts.reduce((n, p) => n + p.length, 0));
      parts.push(typeof obj === "string" ? ascii(obj) : obj);
    }
    add("%PDF-1.4\n");
    add("1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n");
    add("2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n");
    add(
      "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 " +
        pageW +
        " " +
        pageH +
        "] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >> endobj\n",
    );
    add(
      "4 0 obj << /Type /XObject /Subtype /Image /Width " +
        imgW +
        " /Height " +
        imgH +
        " /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length " +
        jpeg.length +
        " >>\nstream\n",
    );
    parts.push(jpeg);
    parts.push(ascii("\nendstream\nendobj\n"));
    const content = pageW + " 0 0 " + pageH + " 0 0 cm /Im0 Do\n";
    add("5 0 obj << /Length " + content.length + " >>\nstream\n" + content + "endstream\nendobj\n");
    const xrefAt = parts.reduce((n, p) => n + p.length, 0);
    let xref = "xref\n0 6\n0000000000 65535 f \n";
    for (let i = 1; i <= 5; i++) {
      xref += String(offsets[i]).padStart(10, "0") + " 00000 n \n";
    }
    parts.push(
      ascii(
        xref +
          "trailer << /Size 6 /Root 1 0 R >>\nstartxref\n" +
          xrefAt +
          "\n%%EOF\n",
      ),
    );
    return concat(parts);
  }

  async function makePdf() {
    if (!state.doc) return;
    const pageImg = img();
    if (!pageImg.naturalWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = pageImg.naturalWidth;
    canvas.height = pageImg.naturalHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(pageImg, 0, 0);
    ctx.fillStyle = "#000";
    ctx.textBaseline = "alphabetic";
    state.fields.forEach((f) => {
      const val = String(f.value || "").trim();
      if (!val || f.page !== state.cur) return;
      ctx.font = f.size * state.zoom + 'px "Leelawadee UI", Tahoma, sans-serif';
      ctx.fillText(val, f.x * state.zoom, f.y * state.zoom);
    });
    const jpeg = await new Promise((resolve) => {
      canvas.toBlob((b) => resolve(b), "image/jpeg", 0.92);
    });
    if (!jpeg) {
      $("result").textContent = "❌ สร้างภาพไม่สำเร็จ";
      return;
    }
    const buf = new Uint8Array(await jpeg.arrayBuffer());
    const pdf = jpegToPdf(buf, canvas.width, canvas.height, state.zoom);
    const name =
      (($("tplname").value || "filled").trim() || "filled") +
      "-" +
      new Date().toISOString().slice(0, 10) +
      ".pdf";
    const blob = new Blob([pdf], { type: "application/pdf" });
    const url = URL.createObjectURL(blob);
    const result = $("result");
    result.replaceChildren("เสร็จแล้ว: ");
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "เปิด " + name;
    result.appendChild(link);
    bub("สร้างไฟล์ " + name + " เรียบร้อย 🎉", "bot");
    link.click();
  }

  async function initCatalog() {
    const res = await fetch("data/catalog.json");
    state.catalog = await res.json();
    const docsel = $("docsel");
    const tplsel = $("tplsel");
    docsel.replaceChildren(new Option("— เลือก PDF —", ""));
    tplsel.replaceChildren(new Option("— เทมเพลตใหม่ —", ""));
    state.catalog.docs.forEach((d) => {
      docsel.add(new Option(d.id, d.id));
      if (d.template) tplsel.add(new Option(d.template, d.template));
    });
    const def = state.catalog.default_doc || state.catalog.docs[0].id;
    const meta = docMeta(def);
    docsel.value = def;
    await loadDoc(def);
    if (meta && meta.template) {
      tplsel.value = meta.template;
      await loadTemplate(meta.template);
    }
  }

  function bind() {
    $("tab-edit").onclick = () => setTab("edit");
    $("tab-fill").onclick = () => {
      setTab("fill");
      renderValues();
      startChat();
    };
    $("prev").onclick = () => {
      if (state.cur > 0) {
        state.cur--;
        showPage();
      }
    };
    $("next").onclick = () => {
      if (state.cur < state.pages - 1) {
        state.cur++;
        showPage();
      }
    };
    img().onclick = (e) => {
      if (!state.doc || !$("panel-edit").classList.contains("active")) return;
      const rect = img().getBoundingClientRect();
      const x = ((e.clientX - rect.left) * scale()) / state.zoom;
      const y = ((e.clientY - rect.top) * scale()) / state.zoom;
      if (state.selIdx >= 0) {
        state.fields[state.selIdx].x = x;
        state.fields[state.selIdx].y = y;
        state.fields[state.selIdx].page = state.cur;
        state.selIdx = -1;
      } else {
        const name = prompt("ชื่อข้อมูลของจุดนี้ (เช่น ชื่อผู้เบิก):");
        if (!name) return;
        const size = parseFloat($("fsize").value) || 14;
        state.fields.push({ name: name.trim(), page: state.cur, x, y, size, value: "" });
      }
      renderAll();
    };
    $("fieldlist").onclick = (e) => {
      const target = e.target;
      const li = target.closest("li[data-i]");
      if (!li) return;
      const i = Number(li.dataset.i);
      const act = target.closest("[data-act]") && target.closest("[data-act]").dataset.act;
      if (act === "rename") {
        const n = prompt("ชื่อใหม่ของฟิลด์:", state.fields[i].name);
        if (n) {
          state.fields[i].name = n.trim();
          renderAll();
        }
      } else if (act === "del") {
        if (!confirm('ลบจุด "' + state.fields[i].name + '" ทิ้ง?')) return;
        state.fields.splice(i, 1);
        state.selIdx = -1;
        renderAll();
      } else {
        state.selIdx = state.selIdx === i ? -1 : i;
        gotoField(i);
        renderAll();
      }
    };
    $("valuelist").addEventListener("input", (e) => {
      const t = e.target;
      if (t.dataset.i === undefined) return;
      state.fields[Number(t.dataset.i)].value = t.value.trim();
      paintMarkers();
      renderList();
    });
    $("valuelist").addEventListener("click", (e) => {
      const t = e.target;
      if (t.dataset.clear !== undefined) {
        state.fields[Number(t.dataset.clear)].value = "";
        renderAll();
        return;
      }
      if (t.dataset.goto !== undefined) {
        gotoField(Number(t.dataset.goto));
        paintMarkers();
      }
    });
    $("chatsend").onclick = handleChat;
    $("chatinput").addEventListener("keydown", (e) => {
      if (e.key === "Enter") handleChat();
    });
    $("clearvals").onclick = () => {
      if (!confirm("ล้างค่าที่กรอกไว้ทั้งหมด เพื่อเริ่มกรอกรอบใหม่? (จุดที่มาร์คไว้ยังอยู่ครบ)")) return;
      state.fields.forEach((f) => {
        f.value = "";
      });
      state.chatIdx = -1;
      $("chatlog").innerHTML = "";
      renderAll();
      startChat();
    };
    $("makepdf").onclick = () => void makePdf();
    $("savetpl").onclick = () => {
      const name = $("tplname").value.trim();
      if (!state.doc || !name) {
        alert("เลือก PDF และตั้งชื่อเทมเพลตก่อน");
        return;
      }
      localStorage.setItem(tplKey(name), JSON.stringify({ doc: state.doc, fields: state.fields }));
      const tplsel = $("tplsel");
      if (![...tplsel.options].some((o) => o.value === name)) tplsel.add(new Option(name, name));
      tplsel.value = name;
      alert('บันทึกเทมเพลต "' + name + '" แล้ว (' + state.fields.length + " จุด)");
    };
    $("docsel").onchange = async (e) => {
      const v = e.target.value;
      if (!v) return;
      await loadDoc(v);
      const meta = docMeta(v);
      if (meta && meta.template) {
        $("tplsel").value = meta.template;
        await loadTemplate(meta.template);
      }
    };
    $("tplsel").onchange = (e) => {
      const v = e.target.value;
      if (!v) {
        state.fields = [];
        renderAll();
        return;
      }
      void loadTemplate(v);
    };
    $("upfile").onchange = () => {
      alert("โหมดทดลองบนเว็บอัปโหลด PDF ภายนอกไม่ได้ — ใช้ใบลาหรือฟอร์มตัวอย่าง หรือติดตั้งโปรแกรมบนเครื่องเพื่อกรอกฟอร์มโรงเรียน");
      $("upfile").value = "";
    };
    window.addEventListener("resize", paintMarkers);
    window.addEventListener("keydown", (e) => {
      if (state.selIdx < 0 || !$("panel-edit").classList.contains("active")) return;
      if (document.activeElement && /INPUT|TEXTAREA/.test(document.activeElement.tagName)) return;
      const step = e.shiftKey ? 5 : 0.5;
      if (e.key === "ArrowUp") state.fields[state.selIdx].y -= step;
      else if (e.key === "ArrowDown") state.fields[state.selIdx].y += step;
      else if (e.key === "ArrowLeft") state.fields[state.selIdx].x -= step;
      else if (e.key === "ArrowRight") state.fields[state.selIdx].x += step;
      else if (e.key === "Escape") {
        state.selIdx = -1;
        renderAll();
        return;
      } else return;
      e.preventDefault();
      paintMarkers();
    });
  }

  fetch("/releases/latest.json", { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : null))
    .then((data) => {
      if (!data || !data.setup_url) return;
      const a = $("setup-link");
      a.href = data.setup_url;
      a.hidden = false;
      if (data.version) a.textContent = "ดาวน์โหลด Setup v" + data.version;
    })
    .catch(() => {});

  bind();
  void initCatalog();
})();
