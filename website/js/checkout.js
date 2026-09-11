(function () {
  'use strict';
  const form = document.getElementById('stripe-form');
  if (!form) return;
  const status = document.getElementById('stripe-status');
  const button = form.querySelector('button');
  const mid = document.getElementById('stripe-mid');
  const plan = document.getElementById('stripe-plan');
  const incoming = new URLSearchParams(location.hash.slice(1)).get('machine_id');
  if (/^[a-f0-9]{16}$/i.test(incoming || '')) mid.value = incoming.toUpperCase();
  const choice = new URLSearchParams(location.search).get('plan');
  if (['1','3','5','10'].includes(choice)) plan.value = choice;
  let requestId = null;
  form.addEventListener('input', () => { requestId = null; });
  fetch('/api/sales/config').then(r => r.ok ? r.json() : {enabled:false}).then(data => {
    button.disabled = !data.enabled;
    status.textContent = data.enabled ? '' : 'Stripe ยังไม่เปิดรับชำระเงิน ใช้ช่องทางติดต่อผู้ขายด้านล่างได้';
  }).catch(() => { status.textContent = 'Stripe ยังไม่พร้อมใช้งาน กรุณาติดต่อผู้ขาย'; });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!form.reportValidity() || button.disabled) return;
    button.disabled = true; status.textContent = 'กำลังเปิดหน้าชำระเงินที่ Stripe…';
    requestId ||= crypto.randomUUID();
    try {
      const response = await fetch('/api/sales/checkout', {method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({machine_id:mid.value.trim().toUpperCase(), email:document.getElementById('stripe-email').value.trim(), plan:plan.value, request_id:requestId})});
      const data = await response.json();
      if (!response.ok) { if (response.status === 409) requestId = null; throw new Error(data.error || 'ชำระเงินไม่สำเร็จ'); }
      const target = new URL(data.url);
      if (target.protocol !== 'https:' || target.hostname !== 'checkout.stripe.com') throw new Error('ลิงก์ชำระเงินไม่ถูกต้อง');
      location.assign(target.href);
    } catch(error) { status.textContent = error.message; button.disabled = false; }
  });
})();
