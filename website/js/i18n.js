/* Language for the browser demo — Thai by default, English via ?lang=en.
   Wording follows locales/en.json so the demo reads like the installed app. */
(function () {
  "use strict";

  const STORE = "formdd-web-lang";

  const STR = {
    th: {
      "meta.appTitle": "PDF Form Marker — FormDD (ทดลองบนเว็บ)",
      "header.selectPdf": "— เลือก PDF —",
      "header.newTemplate": "— เทมเพลตใหม่ —",
      "header.templateName": "ชื่อเทมเพลต",
      "header.saveTemplate": "💾 บันทึกเทมเพลต",
      "header.thisMachine": "เครื่องนี้",
      "web.home": "หน้าแรก",
      "web.demoTag": "เว็บทดลอง",
      "web.langOther": "English",
      "web.langOtherTitle": "อ่านหน้านี้เป็นภาษาอังกฤษ",
      "web.licMsg":
        "โหมดทดลองบนเว็บ — ใช้ได้เฉพาะใบลาและฟอร์มตัวอย่าง · อัปโหลด PDF โรงเรียนได้เมื่อติดตั้งโปรแกรมบนเครื่อง",
      "web.downloadSetup": "ดาวน์โหลด Setup",
      "web.downloadSetupVer": "ดาวน์โหลด Setup v{version}",
      "web.fontHint": "ฟอนต์ทับ: Leelawadee UI",
      "web.renderFail": "❌ สร้างภาพไม่สำเร็จ",
      "web.saveOk": 'บันทึกเทมเพลต "{name}" แล้ว ({count} จุด)',
      "web.uploadBlocked":
        "โหมดทดลองบนเว็บอัปโหลด PDF ภายนอกไม่ได้ — ใช้ใบลาหรือฟอร์มตัวอย่าง หรือติดตั้งโปรแกรมบนเครื่องเพื่อกรอกฟอร์มโรงเรียน",
      "viewer.pageIdle": "หน้า - / -",
      "viewer.page": "หน้า {cur} / {pages}",
      "viewer.valuePrompt": 'ค่าของ "{name}":',
      "tabs.edit": "① มาร์คจุด",
      "tabs.fill": "② กรอกข้อมูล (แชท)",
      "edit.hint1":
        'คลิก<b>บนเส้นปะพอดี</b>ตรงจุดเริ่มต้นของช่องว่าง → ตัวอักษรจะ "นั่งทับ" บนจุดที่ปัก (จุด = เส้นฐานตัวอักษร)',
      "edit.hint2":
        "🎯 จูนละเอียด: คลิกเลือกจุด (เป็นสีน้ำเงิน) แล้วกดลูกศร ↑↓←→ ขยับทีละ 0.5pt · Shift+ลูกศร = 5pt · Esc = เลิกเลือก",
      "edit.fontSize": "ขนาดตัวอักษร (pt):",
      "edit.hint3": "คลิกชื่อฟิลด์เพื่อเลือก แล้วคลิกตำแหน่งใหม่บนเอกสารเพื่อย้ายจุด · ✕ = ลบ",
      "fill.hint1":
        "✏️ แก้ค่าได้ 3 ทาง: พิมพ์ในตารางนี้ · <b>คลิกจุดสีแดงบนเอกสาร</b> · หรือตอบแชทด้านล่าง · ✕ = ล้างค่าช่องนั้น",
      "fill.clearAll": "🧹 ล้างค่าทั้งหมด (เริ่มรอบใหม่)",
      "fill.chatPlaceholder": "พิมพ์คำตอบแล้วกด Enter…",
      "fill.send": "ส่ง",
      "fill.hint2":
        "พิมพ์ <b>-</b> เพื่อเว้นว่าง · <b>แก้ [ชื่อฟิลด์]</b> หรือ <b>edit [field]</b> เพื่อแก้ค่า",
      "fill.makePdf": "🖨️ สร้าง PDF",
      "fill.pageAlt": "เลือก PDF ก่อน",
      "fields.pageSize": "(หน้า {page}, {size}pt)",
      "fields.renameTitle": "เปลี่ยนชื่อฟิลด์",
      "fields.deleteTitle": "ลบจุดนี้ทิ้ง",
      "fields.emptyPlaceholder": "— ว่าง —",
      "fields.clearTitle": "ล้างค่าช่องนี้",
      "chat.ask": "กรอก: {name}",
      "chat.done":
        'ครบทุกช่องแล้ว ✅ กด "สร้าง PDF" ได้เลย หรือพิมพ์ แก้ [ชื่อฟิลด์] / edit [field] เพื่อแก้ค่า',
      "chat.noMarks": "ยังไม่มีจุดที่มาร์คไว้ — กลับไปแท็บ ① ก่อนครับ",
      "chat.start": "มี {count} ช่องให้กรอก เริ่มเลย!",
      "chat.notFound":
        'ไม่พบฟิลด์ "{q}" — พิมพ์แค่บางส่วนของชื่อก็ได้ หรือแก้ในตารางด้านบน/คลิกจุดบนเอกสารได้เลย',
      "app.donePrefix": "เสร็จแล้ว: ",
      "app.openFile": "เปิด {file}",
      "app.created": "สร้างไฟล์ {file} เรียบร้อย 🎉",
      "app.markNamePrompt": "ชื่อข้อมูลของจุดนี้ (เช่น ชื่อผู้เบิก):",
      "app.renamePrompt": "ชื่อใหม่ของฟิลด์:",
      "app.deleteConfirm": 'ลบจุด "{name}" ทิ้ง?',
      "app.clearConfirm": "ล้างค่าที่กรอกไว้ทั้งหมด เพื่อเริ่มกรอกรอบใหม่? (จุดที่มาร์คไว้ยังอยู่ครบ)",
      "app.needPdfAndName": "เลือก PDF และตั้งชื่อเทมเพลตก่อน",
    },
    en: {
      "meta.appTitle": "PDF Form Marker — FormDD (browser demo)",
      "header.selectPdf": "— Select PDF —",
      "header.newTemplate": "— New template —",
      "header.templateName": "Form name",
      "header.saveTemplate": "💾 Save template",
      "header.thisMachine": "This PC",
      "web.home": "Home",
      "web.demoTag": "Browser demo",
      "web.langOther": "ไทย",
      "web.langOtherTitle": "Read this page in Thai",
      "web.licMsg":
        "Browser demo — sample forms only · install the app on your PC to fill your own PDFs",
      "web.downloadSetup": "Download Setup",
      "web.downloadSetupVer": "Download Setup v{version}",
      "web.fontHint": "Overlay font: Leelawadee UI",
      "web.renderFail": "❌ Could not render the page image",
      "web.saveOk": 'Saved template "{name}" ({count} pins)',
      "web.uploadBlocked":
        "The browser demo cannot upload your own PDF — use a sample form, or install the app on your PC to fill real forms",
      "viewer.pageIdle": "Page - / -",
      "viewer.page": "Page {cur} / {pages}",
      "viewer.valuePrompt": 'Value for "{name}":',
      "tabs.edit": "① Mark fields",
      "tabs.fill": "② Fill data (chat)",
      "edit.hint1":
        "Click <b>exactly on the dotted line</b> at the start of a blank → text sits on the pin (pin = text baseline)",
      "edit.hint2":
        "🎯 Fine-tune: select a pin (blue) then arrow keys ↑↓←→ move 0.5pt · Shift+arrow = 5pt · Esc = deselect",
      "edit.fontSize": "Font size (pt):",
      "edit.hint3":
        "Click a field name to select, then click a new spot on the page to move it · ✕ = delete",
      "fill.hint1":
        "✏️ Edit values three ways: type in this table · <b>click a red pin on the page</b> · or answer in chat · ✕ = clear that field",
      "fill.clearAll": "🧹 Clear all values (new round)",
      "fill.chatPlaceholder": "Type an answer and press Enter…",
      "fill.send": "Send",
      "fill.hint2": "Type <b>-</b> to leave blank · <b>edit [field name]</b> to change a value",
      "fill.makePdf": "🖨️ Create PDF",
      "fill.pageAlt": "Select a PDF first",
      "fields.pageSize": "(page {page}, {size}pt)",
      "fields.renameTitle": "Rename field",
      "fields.deleteTitle": "Delete this pin",
      "fields.emptyPlaceholder": "— empty —",
      "fields.clearTitle": "Clear this value",
      "chat.ask": "Fill: {name}",
      "chat.done": 'All fields done ✅ Click "Create PDF", or type edit [field] to change a value',
      "chat.noMarks": "No marked fields yet — go back to tab ① first",
      "chat.start": "{count} fields to fill — start now!",
      "chat.notFound":
        'Field "{q}" not found — type part of the name, or edit in the table / click a pin on the page',
      "app.donePrefix": "Done: ",
      "app.openFile": "Open {file}",
      "app.created": "Created {file} 🎉",
      "app.markNamePrompt": "Name for this pin (e.g. requester name):",
      "app.renamePrompt": "New field name:",
      "app.deleteConfirm": 'Delete pin "{name}"?',
      "app.clearConfirm": "Clear every value you typed and start a new round? (your pins stay)",
      "app.needPdfAndName": "Select a PDF and enter a template name first",
    },
  };

  function normalize(raw) {
    const v = String(raw || "").trim().toLowerCase();
    if (v.startsWith("en")) return "en";
    if (v.startsWith("th")) return "th";
    return "";
  }

  function stored() {
    try {
      return normalize(localStorage.getItem(STORE));
    } catch (_) {
      return "";
    }
  }

  function remember(value) {
    try {
      localStorage.setItem(STORE, value);
    } catch (_) {}
  }

  /* ?lang= wins, then the last choice made in this browser, then Thai. */
  const asked = normalize(new URLSearchParams(location.search).get("lang"));
  let lang = asked || stored() || "th";
  if (asked) remember(asked);

  const listeners = [];

  function other() {
    return lang === "en" ? "th" : "en";
  }

  function t(key, vars) {
    const table = STR[lang] || STR.th;
    let s = table[key];
    if (s === undefined) s = STR.th[key];
    if (s === undefined) return key;
    if (!vars) return s;
    return s.replace(/\{(\w+)\}/g, (m, name) =>
      vars[name] === undefined ? m : String(vars[name]),
    );
  }

  function applyStatic(root) {
    const scope = root || document;
    scope.querySelectorAll("[data-i18n]").forEach((el) => {
      el.textContent = t(el.dataset.i18n);
    });
    scope.querySelectorAll("[data-i18n-html]").forEach((el) => {
      el.innerHTML = t(el.dataset.i18nHtml);
    });
    scope.querySelectorAll("[data-i18n-ph]").forEach((el) => {
      el.placeholder = t(el.dataset.i18nPh);
    });
    scope.querySelectorAll("[data-i18n-title]").forEach((el) => {
      el.title = t(el.dataset.i18nTitle);
    });
    scope.querySelectorAll("[data-i18n-alt]").forEach((el) => {
      el.alt = t(el.dataset.i18nAlt);
    });
    /* A link that names the other language is written in that language. */
    scope.querySelectorAll("[data-i18n-other-lang]").forEach((el) => {
      el.lang = other();
    });
    document.documentElement.lang = lang;
    document.documentElement.classList.remove("i18n-pending");
    document.title = t("meta.appTitle");
  }

  function setLang(next) {
    const v = normalize(next);
    if (!v || v === lang) return;
    lang = v;
    remember(v);
    const url = new URL(location.href);
    url.searchParams.set("lang", v);
    history.replaceState(null, "", url);
    applyStatic();
    listeners.forEach((fn) => fn(v));
  }

  window.FormDDLang = {
    t: t,
    applyStatic: applyStatic,
    setLang: setLang,
    current: function () {
      return lang;
    },
    other: other,
    onChange: function (fn) {
      listeners.push(fn);
    },
  };

  /* This file runs in <head>, before the body exists: mark the document now so the
     Thai markup stays hidden until applyStatic() has rewritten it. */
  document.documentElement.lang = lang;
  if (lang !== "th") {
    document.documentElement.classList.add("i18n-pending");
    document.title = t("meta.appTitle");
  }

  /* app.js translates as soon as it runs; this only catches the case where it
     never loads, so the page is never left invisible. */
  document.addEventListener("DOMContentLoaded", function () {
    applyStatic();
  });
})();
