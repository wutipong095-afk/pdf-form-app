(function () {
  "use strict";

  const SETUP_FALLBACK = "releases/FormDD-Setup-0.3.2.exe";

  function bindSetupLinks() {
    const nodes = document.querySelectorAll("[data-setup]");
    nodes.forEach((a) => {
      if (!a.getAttribute("href") || a.getAttribute("href") === "#") {
        a.setAttribute("href", SETUP_FALLBACK);
      }
    });
    fetch("releases/latest.json", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data || !data.setup_url) return;
        nodes.forEach((a) => {
          a.href = data.setup_url;
          if (data.version && a.dataset.setupLabel !== "plain") {
            a.textContent = a.dataset.setupEn
              ? "Download Setup v" + data.version
              : "ดาวน์โหลด Setup v" + data.version;
          }
        });
      })
      .catch(() => {});
  }

  bindSetupLinks();

  /**
   * เมื่อมีคลิปจริงบน YouTube ให้ใส่รหัสหลัง v=
   * เช่น https://www.youtube.com/watch?v=AbCdEfGhIjK → "AbCdEfGhIjK"
   * ว่างไว้ = เล่นคลิปตัวอย่างในหน้านี้
   */
  const YOUTUBE_ID = "";

  /* Captions follow the language of the page the player sits on. */
  const EN = document.documentElement.lang === "en";

  const DURATION = 198;
  const SCENES = [
    {
      t: 0,
      src: "pages/yt-thumb.png",
      th: "สอนใช้ PDF Form Marker (FormDD) ใน 3 นาที",
      en: "PDF Form Marker (FormDD) in 3 minutes",
    },
    {
      t: 18,
      src: "pages/leave-0.png",
      th: "เปิดโปรแกรม แล้วเลือกใบลา.pdf จากรายการเอกสาร",
      en: "Open the app and pick a form from the document list",
    },
    {
      t: 48,
      src: "pages/leave-0.png",
      th: "แท็บ ① มาร์คจุด — คลิกบนเส้นปะเพื่อปักจุดแดง",
      en: "Tab ① Mark fields — click the dotted line to drop a red pin",
    },
    {
      t: 88,
      src: "pages/demo-form-0.png",
      th: "สลับแท็บ ② กรอกข้อมูล ตอบแชทหรือพิมพ์ในตาราง",
      en: "Switch to tab ② Fill data — answer in chat or type in the table",
    },
    {
      t: 130,
      src: "pages/leave-0.png",
      th: "ข้อความทับบนฟอร์มทันที แล้วกดสร้าง PDF",
      en: "Text sits on the form right away, then click Create PDF",
    },
    {
      t: 158,
      src: "pages/demo-form-0.png",
      th: "เปิดงานเก่า ค้นหาไฟล์ที่กรอกแล้วโดยไม่ต้องไล่ใน Explorer",
      en: "Reopen past work — find a filled file without digging through Explorer",
    },
    {
      t: 180,
      src: "pages/yt-thumb.png",
      th: "โปรแกรมเต็มใช้ออฟไลน์บนเครื่องโรงเรียน",
      en: "The full app runs offline on the PC at work",
    },
  ];

  function $(id) {
    return document.getElementById(id);
  }

  function fmt(sec) {
    const s = Math.max(0, Math.floor(sec));
    const m = Math.floor(s / 60);
    const r = s % 60;
    return m + ":" + String(r).padStart(2, "0");
  }

  if (!$("yt-player")) return;

  if (YOUTUBE_ID) {
    $("yt-mock-tag").hidden = true;
    $("yt-id-label").textContent = YOUTUBE_ID;
    $("yt-screen").hidden = true;
    $("yt-bar").hidden = true;
    const box = $("yt-embed");
    box.hidden = false;
    box.classList.add("show");
    const frame = document.createElement("iframe");
    frame.src =
      "https://www.youtube-nocookie.com/embed/" +
      encodeURIComponent(YOUTUBE_ID) +
      "?rel=0";
    frame.title = EN ? "PDF Form Marker walkthrough" : "สอนใช้ PDF Form Marker";
    frame.allow =
      "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
    frame.allowFullscreen = true;
    box.appendChild(frame);
    return;
  }

  let playing = false;
  let t = 0;
  let last = 0;
  let raf = 0;

  function sceneAt(time) {
    let cur = SCENES[0];
    for (let i = 0; i < SCENES.length; i++) {
      if (time >= SCENES[i].t) cur = SCENES[i];
    }
    return cur;
  }

  function paint() {
    const scene = sceneAt(t);
    const img = $("yt-img");
    if (img.getAttribute("src") !== scene.src) img.src = scene.src;
    const cap = $("yt-caption");
    cap.textContent = EN ? scene.en : scene.th;
    cap.classList.toggle("show", playing || t > 0);
    $("yt-played").style.width = (t / DURATION) * 100 + "%";
    $("yt-time").textContent = fmt(t) + " / " + fmt(DURATION);
    $("yt-toggle").textContent = playing ? "❚❚" : "▶";
    $("yt-bigplay").classList.toggle("hidden", playing);
  }

  function tick(now) {
    if (!playing) return;
    const dt = (now - last) / 1000;
    last = now;
    t += dt;
    if (t >= DURATION) {
      t = DURATION;
      playing = false;
    }
    paint();
    if (playing) raf = requestAnimationFrame(tick);
  }

  function play() {
    if (t >= DURATION) t = 0;
    playing = true;
    last = performance.now();
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(tick);
    paint();
  }

  function pause() {
    playing = false;
    cancelAnimationFrame(raf);
    paint();
  }

  $("yt-bigplay").onclick = play;
  $("yt-toggle").onclick = () => (playing ? pause() : play());
  $("yt-progress").onclick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    t = ((e.clientX - rect.left) / rect.width) * DURATION;
    paint();
    if (playing) {
      last = performance.now();
    }
  };

  paint();
})();
