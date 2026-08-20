# เทมเพลตอีเมลออกคีย์ (ผู้ขาย)

ใช้ตอนลูกค้าส่งรหัสเครื่องมาหลังชำระเงิน  
ออกคีย์: `python scripts/gen_license.py <รหัส16ตัว>`  
ไทย `--days 1825` · ต่างประเทศ `--days 3650`

อย่าใส่ private key ในอีเมล และอย่าขอให้ลูกค้าส่ง `license.json` จากเครื่องเก่า

---

## ไทย — ขอรหัสเครื่อง (ถ้ายังไม่ส่งมา)

เรื่อง: FormDD — ส่งรหัสเครื่องเพื่อรับคีย์

```
ขอบคุณที่ซื้อ FormDD

ขั้นตอนถัดไป:
1. เปิดโปรแกรมบนเครื่องที่จะใช้
2. ที่แถบไลเซนต์ คัดลอกรหัสเครื่อง 16 ตัว (มีปุ่มคัดลอก)
3. ตอบกลับอีเมลนี้ด้วยรหัสนั้น

จะส่งคีย์มาให้ภายใน 1 วันทำการ
วางคีย์ในช่องเปิดใช้ไลเซนต์ — ไม่ต้องติดตั้งใหม่
ทดลองฟอร์มตัวอย่างได้ก่อนมีคีย์

FormDD
```

## ไทย — ส่งคีย์

เรื่อง: FormDD — คีย์ไลเซนต์ของเครื่อง {MACHINE_ID}

```
คีย์สำหรับเครื่อง {MACHINE_ID}:

{KEY}

วิธีใช้:
1. เปิด FormDD
2. วางคีย์ในช่องเปิดใช้ไลเซนต์ แล้วกดเปิดใช้
3. ใช้ PDF ของโรงเรียนได้ทันที ไม่ต้องติดตั้งใหม่

คีย์นี้ใช้ได้กับเครื่องนี้เท่านั้น
ย้ายเครื่อง (เมื่อเครื่องเก่าเลิกใช้): ปีละไม่เกิน 2 ครั้ง — ส่งรหัสเครื่องใหม่มาที่อีเมลนี้

FormDD
```

---

## English — request machine ID

Subject: FormDD — send your machine ID for a license key

```
Thanks for buying FormDD.

Next:
1. Open the app on the PC you will use.
2. Copy the 16-character machine ID from the license bar (use Copy).
3. Reply to this email with that ID.

You will get a key within one business day.
Paste it in Activate license — you do not reinstall.
Sample forms work before you have a key.

FormDD
```

## English — send key

Subject: FormDD — license key for {MACHINE_ID}

```
Key for machine {MACHINE_ID}:

{KEY}

How to activate:
1. Open FormDD.
2. Paste the key in Activate license.
3. You can use your own PDFs immediately. No reinstall.

This key is bound to this computer.
Replacing a retired PC: up to 2 times per year — email the new machine ID.

FormDD
```
