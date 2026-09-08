(function () {
  "use strict";
  const form = document.getElementById("purchase-form");
  if (!form) return;
  const en = document.documentElement.lang === "en";
  const mid = document.getElementById("purchase-mid");
  const plan = document.getElementById("purchase-plan");
  const status = document.getElementById("purchase-status");
  // Fragment keeps the machine ID out of server request URLs and referrers.
  const incoming = new URLSearchParams(location.hash.slice(1)).get("machine_id") || "";
  if (/^[a-f0-9]{16}$/i.test(incoming)) mid.value = incoming.toUpperCase();
  if (location.hash.startsWith("#machine_id=")) {
    history.replaceState(null, "", location.pathname + location.search + "#purchase");
    document.getElementById("purchase").scrollIntoView();
  }
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const body = [
      "FormDD", "Machine ID: " + mid.value.toUpperCase(), "Plan: " + plan.value,
      en ? "Name / organization: " : "ชื่อ / หน่วยงาน: ",
      en ? "Please attach your payment receipt, or request payment instructions / a quotation before paying." : "กรุณาแนบสลิป หรือระบุว่าต้องการใบเสนอราคาก่อนชำระเงิน",
    ].join("\n");
    location.href = "mailto:formdd@xambrain.com?subject=" + encodeURIComponent("FormDD license / " + mid.value.toUpperCase()) + "&body=" + encodeURIComponent(body);
    status.textContent = en
      ? "Email prepared, not sent. Attach the receipt and send it in your email app. If no app opens, email the machine ID and plan to formdd@xambrain.com."
      : "เตรียมอีเมลแล้ว แต่ยังไม่ได้ส่ง กรุณาแนบสลิปและกดส่งในแอปอีเมล หากแอปไม่เปิด ให้ส่งรหัสเครื่องและแผนมาที่ formdd@xambrain.com";
  });
})();
