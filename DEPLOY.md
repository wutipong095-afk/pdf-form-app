# Deploy — PDF Form Marker

> **โหมดขั้นสูง / นักพัฒนา** — ผลิตภัณฑ์หลักสำหรับโรงเรียนคือตัวติดตั้ง Windows ออฟไลน์ (`127.0.0.1`)  
> Docker + Caddy ใช้เมื่อต้องการทดลอง/โฮสต์เองเท่านั้น **ไม่แนะนำเป็น production สำหรับโรงเรียนหลายเครื่อง**  
> ข้อจำกัดสำคัญ: คลังเอกสาร (`library.json` / รากคลัง) เป็นของเครื่องร่วมกัน — ยังไม่แยก tenant ต่อผู้ใช้; อย่าเปิดให้ผู้ใช้ที่ไม่น่าเชื่อถือ

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

- เปลี่ยนรหัสผ่าน default ก่อนเปิดเน็ต (แอปจะปฏิเสธสตาร์ทบนเน็ตถ้ายังเป็น `changeme` และไม่มี `USERS_JSON`)
- ตั้ง `ADMIN_USERS` (คั่นด้วย comma) ถ้าต้องการหลาย admin — API สำรอง/ไลเซนต์/ตั้งคลังจำกัดเฉพาะ admin
- อย่า commit ไฟล์ `.env`
- ไลเซนต์ใช้ `license_public.pem` ใน image — **อย่า**ใส่ `keys/ed25519_private.pem` หรือโฟลเดอร์ `scripts/` ลง image ลูกค้า
- อย่าเปิด `LICENSE_BYPASS` บนเครื่องลูกค้า
- `data/machine_id` อยู่บน volume — rebuild container แล้วคีย์เดิมยังใช้ได้
- ถ้าลูกค้าเจอ "ตรวจพบนาฬิกาย้อนหลัง": ให้ปรับเวลาเครื่องให้ถูก หรือออกคีย์ใหม่ให้แล้ว activate (คีย์ใหม่จะรีเซ็ตตัวตรวจนาฬิกา)
- แต่ละ user มีโฟลเดอร์ uploads/templates/output แยกใน `/data/users/<ชื่อ>/` แต่**คลังเอกสารร่วมกัน**
- จำกัดขนาดอัปโหลดด้วย `MAX_UPLOAD_MB` / หน้า PDF ด้วย `MAX_PDF_PAGES`
- อย่าถือว่า multi-user Docker พร้อม isolation ระดับ production จนกว่าจะมี tenant แยกคลัง
