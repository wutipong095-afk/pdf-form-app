# Deploy — PDF Form Marker

เปิดให้คนอื่นใช้ผ่านอินเทอร์เน็ตด้วย Docker + Caddy (HTTPS อัตโนมัติ)

## 1) เตรียม VPS

- Ubuntu 22.04+ หรือเทียบเท่า
- ติดตั้ง [Docker](https://docs.docker.com/engine/install/) + Docker Compose plugin
- ชี้ DNS A record ของโดเมนมาที่ IP ของ VPS

## 2) ตั้งค่า

```bash
git clone <repo-url> pdf-form-app
cd pdf-form-app
cp .env.example .env
nano .env
```

แก้อย่างน้อย:

| ตัวแปร | ค่า |
|--------|-----|
| `SECRET_KEY` | สตริงสุ่มยาว (เช่น `openssl rand -hex 32`) |
| `ADMIN_USER` / `ADMIN_PASSWORD` | บัญชีแรก |
| `DOMAIN` | โดเมนจริง เช่น `forms.example.com` |
| `SESSION_COOKIE_SECURE` | `true` |
| `AUTH_REQUIRED` | Docker ตั้ง `true` ให้อยู่แล้ว (บังคับ login) |

หลายผู้ใช้:

```env
USERS_JSON={"alice":"pass1","bob":"pass2"}
```

## 3) รัน

```bash
docker compose up -d --build
```

- เปิด `https://โดเมนของคุณ`
- Caddy ขอใบรับรอง Let's Encrypt ให้เองเมื่อ `DOMAIN` เป็นโดเมนจริงและพอร์ต 80/443 เปิดอยู่

ทดสอบบนเครื่อง (HTTP / localhost):

```env
DOMAIN=localhost
SESSION_COOKIE_SECURE=false
```

แล้วเปิด http://localhost

## 4) อัปเดต

```bash
git pull
docker compose up -d --build
```

ข้อมูลผู้ใช้เก็บใน volume `app-data` ไม่หายตอน rebuild

## 5) ตรวจสุขภาพ

```bash
docker compose ps
docker compose logs -f app
```

ล็อกอินด้วยบัญชีจาก `.env` → ควรเห็น `demo-form.pdf` + เทมเพลต `demo-ใบเบิก` ทันที

## หมายเหตุความปลอดภัย

- เปลี่ยนรหัสผ่าน default ก่อนเปิดเน็ต
- อย่า commit ไฟล์ `.env`
- ไลเซนต์ใช้ `license_public.pem` ใน image — **อย่า**ใส่ `keys/ed25519_private.pem` หรือโฟลเดอร์ `scripts/` ลง image ลูกค้า
- อย่าเปิด `LICENSE_BYPASS` บนเครื่องลูกค้า
- `data/machine_id` อยู่บน volume — rebuild container แล้วคีย์เดิมยังใช้ได้
- ถ้าลูกค้าเจอ "ตรวจพบนาฬิกาย้อนหลัง": ให้ปรับเวลาเครื่องให้ถูก หรือออกคีย์ใหม่ให้แล้ว activate (คีย์ใหม่จะรีเซ็ตตัวตรวจนาฬิกา)
- แต่ละ user มีโฟลเดอร์แยกใน `/data/users/<ชื่อ>/`
- จำกัดขนาดอัปโหลดด้วย `MAX_UPLOAD_MB`
