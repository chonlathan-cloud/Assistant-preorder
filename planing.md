### 📅 Phase 1: การเตรียม Infrastructure & Environment (GCP Setup)

ก่อนเริ่มเขียนโค้ด ต้องวางรากฐานบน Google Cloud ให้พร้อมครับ:

1.  **GCP Project:** สร้างโปรเจกต์ใหม่และเปิดใช้งาน (Enable) API ต่อไปนี้:
    * `Cloud Run API` (สำหรับรันบอทและ FE)
    * `Cloud Tasks API` (สำหรับตั้งเวลายิงคำสั่งระดับมิลลิวินาที)
    * `Firestore API` (สำหรับเก็บ Configuration)
    * `Secret Manager API` (สำหรับเก็บ Cookies ของ 2 บัญชี)
    * `Vertex AI API` (สำหรับใช้ Gemini 3 Flash ช่วยดูหน้าจอ)
2.  **Region:** เลือกใช้ **`asia-southeast1` (Singapore)** ทุกบริการเพื่อความเร็วสูงสุด

---

### 🔑 Phase 2: การจัดการ Session (The Authentication)

เนื่องจากคุณใช้ iPhone 14 เราต้องทำการ "ดูด" Session จากคอมพิวเตอร์มาฝากไว้บน Cloud:

1.  **Local Login:** เขียน Script Python สั้นๆ รันบนคอมพิวเตอร์เพื่อเปิด Chrome (Playwright) ให้คุณ Scan QR Code ล็อกอิน Lazada ทั้ง 2 บัญชี
2.  **Save State:** สั่ง `context.storage_state(path="session_acc_1.json")`
3.  **Upload to Secret Manager:** นำไฟล์ JSON ไปเก็บใน **Secret Manager** ตั้งชื่อว่า `LAZ_SESSION_1` และ `LAZ_SESSION_2`
    * *Guru Tip: คุกกี้ Lazada มีอายุจำกัด ควรต่ออายุ (Refresh) ทุกๆ 1-2 วันก่อนวันขายจริง*

---

### 💻 Phase 3: การพัฒนาตัวบอท (The Worker - Cloud Run)

นี่คือหัวใจของระบบ (Core Logic) โดยใช้ **Python + Playwright**:

1.  **Parallel Execution:** เขียนโค้ดให้รองรับการรับค่า `Account_ID` เพื่อให้รัน 2 บัญชีพร้อมกันได้ (Concurrency)
2.  **Logic Flow (Workflow A):**
    * **Warm-up:** เข้าหน้าสินค้าล่วงหน้า 5-10 วินาที
    * **Variant Selection:** ระบุพิกัดหรือ Text ของสี (เช่น `Classic Black`)
    * **Quantity Selector:** ใส่ลอจิกวนลูปกดปุ่ม `+` หรือพิมพ์ตัวเลขในช่องจำนวน
    * **Fast Checkout:** กด `Buy Now` -> `Place Order` (โดยตั้งค่า Default Payment เป็น Bank Transfer/QR ไว้แล้ว)
3.  **Vertex AI Fallback:** หาก `page.wait_for_selector` หาปุ่มไม่เจอเกิน 2 วินาที -> สั่ง Screenshot -> ส่งให้ **Gemini 3 Flash** วิเคราะห์หาพิกัดปุ่มใหม่ทันที

---

### 🖥️ Phase 4: การสร้างระบบควบคุม (The Brain - FE & DB)

สร้างหน้าจอให้คุณสั่งการได้ง่ายๆ:

1.  **Front-End:** ใช้ **Streamlit** Deploy บน Cloud Run (ประหยัดและเขียนง่าย)
2.  **Database:** ใช้ **Firestore** เก็บ Data:
    * `Product URL`
    * `Variant Name` & `Qty`
    * `Target Time` (วัน/เวลาที่ของเข้า)
3.  **Task Orchestrator:** เมื่อคุณกด "Schedule" ใน FE ระบบจะสร้าง **Cloud Task** เพื่อนัดหมายเวลาปลุกบอท (Worker)

---

### 🛡️ Phase 5: กลยุทธ์การกด 40-50 ใบ (The Scaling Strategy)

เพื่อให้ได้จำนวนตามเป้าหมาย (Massive Order):

1.  **The Loop:** เนื่องจาก 1 Order อาจจำกัดจำนวนชิ้น (เช่น 10 ใบ) บอทต้องมีลอจิก **"Auto-Retry"** ทันทีหลังจากกด Place Order สำเร็จชิ้นแรก เพื่อกลับไปกดชิ้นที่ 2-3 ต่อจนกว่าของจะหมด
2.  **Multi-Instance:** หาก 2 บัญชียังไม่พอ คุณสามารถเพิ่มบัญชีที่ 3, 4 เข้ามาในระบบได้ง่ายๆ เพราะโครงสร้างเป็น Cloud Run ที่ Scale-out ได้อิสระ

---

### 🧪 Phase 6: การทดสอบและจำลอง (Simulation)

**"อย่าไปลองครั้งแรกในวันขายจริง"**
1.  **Dry Run:** ทดลองรันบอทกับสินค้าอื่นในร้านที่มีราคาถูกๆ (หลักสิบบาท) เพื่อเช็คว่าบอทสามารถกดจนถึงหน้า "รอชำระเงิน" ได้จริงไหม
2.  **Timing Test:** เช็คความต่างของเวลาระหว่าง Cloud Scheduler กับเวลาจริง (Latency Check)

---

### 📋 สรุป Action Plan สำหรับคุณ (Checklist)

| ลำดับ | สิ่งที่ต้องทำ | เครื่องมือ (Tools) |
| :--- | :--- | :--- |
| 1 | สร้าง GCP Project & Enable APIs | Google Cloud Console |
| 2 | เขียน Script ดึง Cookies จากคอม | Python (Playwright) |
| 3 | เขียน Dockerfile ของ Worker (Bot) | Docker + Playwright + Python |
| 4 | พัฒนาหน้า FE สำหรับตั้งค่า | Streamlit |
| 5 | ทดสอบระบบกับสินค้าทั่วไป | Lazada App + Cloud Run |

---