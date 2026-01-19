import os
import re
import random
import fitz  # PyMuPDF
import google.generativeai as genai
import streamlit as st
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import dotenv

# --- พยายาม Import Prompt จากไฟล์ภายนอก ---
try:
    from prompt import PROMPT_WORKAW
except ImportError:
    PROMPT_WORKAW = "คุณคือผู้ช่วย AI ผู้เชี่ยวชาญด้านกราฟิก ตอบคำถามจากเอกสารที่แนบมาเท่านั้น"

# --- โหลด Config ---
dotenv.load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

if not GOOGLE_API_KEY:
    st.error("❌ ไม่พบ API Key กรุณาตรวจสอบไฟล์ .env")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)

# --- Path Config ---
current_dir = os.path.dirname(os.path.abspath(__file__))
pdf_filename = os.path.join(current_dir, "Graphic.pdf")

# --- Model Config ---
generation_config = {
    "temperature": 0.0,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 2048,
    "response_mime_type": "text/plain",
}

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
}

# --- 🫧 ฟังก์ชันสร้างฟองอากาศ (One-line HTML) 🫧 ---
def create_bubbles(num_bubbles=20):
    bubbles_html = ""
    for _ in range(num_bubbles):
        left = random.randint(1, 99)      # สุ่มตำแหน่งแนวนอน
        size = random.randint(10, 30)     # สุ่มขนาด
        duration = random.randint(10, 25) # สุ่มความเร็ว
        delay = random.randint(0, 15)     # สุ่มเวลาเริ่ม
        opacity = random.uniform(0.1, 0.4)# สุ่มความจาง
        
        # เขียน HTML เป็นบรรทัดเดียว
        bubbles_html += f'<div class="bubble" style="left: {left}%; width: {size}px; height: {size}px; animation-duration: {duration}s; animation-delay: {delay}s; opacity: {opacity};"></div>'
        
    return bubbles_html

# สร้าง HTML ของฟองอากาศเตรียมไว้
bubbles_html_code = create_bubbles()

# --- 🌊 CSS ธีมท้องทะเลน้ำตื้น (Shallow Water Tone) 🌊 ---
base_css = """
<style>
/* 1. Animation พื้นหลังไล่สี */
@keyframes gradient_flow {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

/* 2. Animation ปลาว่ายน้ำ */
@keyframes swim {
    0% { left: -15%; transform: translateY(0px) rotate(0deg); }
    25% { transform: translateY(30px) rotate(5deg); }
    50% { transform: translateY(0px) rotate(0deg); }
    75% { transform: translateY(-30px) rotate(-5deg); }
    100% { left: 110%; transform: translateY(0px) rotate(0deg); }
}

/* 3. Animation ฟองอากาศลอยขึ้น */
@keyframes rise {
    0% { bottom: -50px; transform: translateX(0); }
    50% { transform: translateX(20px); } 
    100% { bottom: 110vh; transform: translateX(-20px); }
}

/* ปรับแต่ง Container หลัก (ใช้โทนสีน้ำตื้นพาสเทลสว่าง #E0F7FA เป็นหลัก) */
[data-testid="stAppViewContainer"] {
    /* ใช้สีหลัก #E0F7FA และไล่เฉดสีใกล้เคียงกันเพื่อให้ยังดูมีการเคลื่อนไหว */
    background: linear-gradient(-45deg, #E0F7FA, #E5F9FB, #DFF2F8, #E0F7FA);
    background-size: 400% 400%;
    animation: gradient_flow 25s ease infinite; /* ปรับให้ไหลช้าลงนิดหน่อยให้ดูนุ่มนวล */
}

/* ส่วนหัวใส */
[data-testid="stHeader"] {
    background-color: rgba(0,0,0,0);
}

/* --- ✨ ตกแต่งหัวข้อ (H1) --- */
h1 {
    /* สีตัวหนังสือเข้ม ไล่ระดับเพื่อให้เด่นบนพื้นหลังสว่าง */
    background: linear-gradient(to right, #0277BD, #00838F);
    background-clip: text;
    -webkit-background-clip: text;
    color: transparent;
    -webkit-text-fill-color: transparent;
    font-weight: 900 !important;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
}

/* ปรับสีข้อความทั่วไปให้เข้มขึ้น อ่านง่าย */
p, li, span, div {
    color: #006064; /* สีเขียวอมฟ้าน้ำทะเลเข้ม */
}

/* Sidebar ใสแบบกระจก */
[data-testid="stSidebar"] {
    background-color: rgba(255, 255, 255, 0.5); /* เพิ่มความขาวให้ Sidebar ชัดขึ้นอีกนิด */
    backdrop-filter: blur(10px);
    border-right: 1px solid rgba(255,255,255,0.7);
}

/* ปรับสีข้อความใน Sidebar */
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
    color: #01579B !important; /* สีน้ำเงินเข้ม */
}

/* Style ของตัวปลา */
.fish-container {
    position: fixed;
    bottom: 20px;
    z-index: 1;
    font-size: 50px;
    animation: swim 20s linear infinite;
    pointer-events: none;
}

/* Style ของฟองอากาศ */
.bubble {
    position: fixed;
    bottom: -50px;
    background: rgba(255, 255, 255, 0.7); /* ฟองชัดขึ้นนิดนึง */
    border-radius: 50%;
    z-index: 0;
    animation: rise infinite ease-in;
    pointer-events: none;
    box-shadow: inset -2px -2px 5px rgba(0,0,0,0.05);
    border: 1px solid rgba(255,255,255,0.9);
}
</style>

<div class="fish-container" style="bottom: 10%; animation-duration: 25s;">🐠</div>
<div class="fish-container" style="bottom: 30%; animation-duration: 18s; animation-delay: 5s; font-size: 30px;">🐡</div>
<div class="fish-container" style="bottom: 60%; animation-duration: 35s; animation-delay: 2s; font-size: 60px;">🐬</div>
<div class="fish-container" style="bottom: 80%; animation-duration: 40s; animation-delay: 10s; font-size: 25px;">🦑</div>
"""

# รวม CSS หลัก กับ HTML ฟองอากาศ
final_html_render = base_css + "\n\n" + bubbles_html_code

st.markdown(final_html_render, unsafe_allow_html=True)

# --- ระบบอ่านไฟล์แบบ Hybrid ---
@st.cache_resource(show_spinner="กำลังดำน้ำหาข้อมูลในไฟล์ PDF... 🤿")
def load_pdf_data_hybrid(file_path):
    text_content = ""
    page_images_map = {} 
    
    if os.path.exists(file_path):
        try:
            doc = fitz.open(file_path)
            for i, page in enumerate(doc):
                page_num = i + 1
                text = page.get_text()
                text_content += f"\n[--- Page {page_num} START ---]\n{text}\n[--- Page {page_num} END ---]\n"
                
                # Crop Image Logic
                image_blocks = [b for b in page.get_text("blocks") if b[6] == 1]
                saved_images = []
                if image_blocks:
                    for img_block in image_blocks:
                        rect = fitz.Rect(img_block[:4])
                        if rect.width > 50 and rect.height > 50: 
                            rect.x0 -= 5; rect.y0 -= 5; rect.x1 += 5; rect.y1 += 5
                            try:
                                pix_crop = page.get_pixmap(matrix=fitz.Matrix(3, 3), clip=rect)
                                saved_images.append(pix_crop.tobytes("png"))
                            except: pass
                
                if not saved_images:
                    pix_full = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    saved_images.append(pix_full.tobytes("png"))

                if saved_images:
                    page_images_map[page_num] = saved_images
            return text_content, page_images_map
        except Exception as e:
            print(f"Error: {e}")
            return "", {}
    else:
        return "", {}

pdf_text, pdf_hybrid_images = load_pdf_data_hybrid(pdf_filename)

if not pdf_text:
    st.warning(f"⚠️ ไม่พบไฟล์ {pdf_filename} กรุณาตรวจสอบว่ามีไฟล์ Graphic.pdf อยู่ในโฟลเดอร์เดียวกับโค้ด")

# --- Prompt System ---
FULL_SYSTEM_PROMPT = f"""
คุณคือ AI ผู้ช่วยตอบคำถามจากเอกสาร (Document QA)
**Strict Rules:**
1. ตอบโดยใช้ข้อมูลใน [CONTEXT] ด้านล่างนี้เท่านั้น
2. ห้ามใช้ความรู้นอกเหนือจากเอกสาร หรือความรู้ทั่วไป
3. หากไม่มีข้อมูลในเอกสาร ให้ตอบว่า "ขออภัยครับ ข้อมูลส่วนนี้ไม่มีระบุไว้ในเอกสาร"
4. ระบุเลขหน้าเสมอ เช่น [PAGE: 5] โดยดูจาก Tag [--- Page X START ---]

[CONTEXT]:
{pdf_text}
"""

# --- Setup Model ---
@st.cache_resource(show_spinner="กำลังเชื่อมต่อคลื่นสมอง AI... 🌊")
def setup_gemini_model():
    candidate_models = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"]
    for model_name in candidate_models:
        try:
            test_model = genai.GenerativeModel(model_name=model_name, safety_settings=SAFETY_SETTINGS, generation_config=generation_config)
            test_model.generate_content("Hi") # Ping test
            real_model = genai.GenerativeModel(model_name=model_name, safety_settings=SAFETY_SETTINGS, generation_config=generation_config, system_instruction=FULL_SYSTEM_PROMPT)
            return real_model, model_name
        except: continue
    return None, None

model, active_model_name = setup_gemini_model()
if model is None: 
    st.error("🚨 ไม่สามารถเชื่อมต่อกับ Gemini ได้เลย (กรุณาเช็ค API Key หรือ Internet)")
    st.stop()

# --- UI & Chat Logic ---
def clear_history():
    st.session_state["messages"] = [{"role": "model", "content": "บุ๋งๆๆ 🫧 สวัสดีค่ะ น้องโลมา AI พร้อมให้บริการแล้วค่า 🐬"}]
    st.rerun()

with st.sidebar:
    st.success(f"⚓ Connected: {active_model_name}")
    if st.button("🗑️ ล้างประวัติ"): clear_history()

st.title("✨ น้องโลมา Graphic Bot 🐬🫧")

if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "model", "content": "บุ๋งๆๆ 🫧 สวัสดีค่ะ น้องโลมา AI พร้อมให้บริการแล้วค่า 🐬"}]

# แสดงประวัติการแชท
for msg in st.session_state["messages"]:
    avatar_icon = "🐠" if msg["role"] == "user" else "🐬"
    with st.chat_message(msg["role"], avatar=avatar_icon):
        st.write(msg["content"])
        if "image_list" in msg:
             for img_data in msg["image_list"]:
                st.image(img_data, caption=f"🖼️ ภาพประกอบจากหน้า {msg.get('page_num_ref')}", use_container_width=True)

# ช่องรับข้อความ
if prompt := st.chat_input("พิมพ์คำถามที่นี่..."):
    st.session_state["messages"].append({"role": "user", "content": prompt})
    st.chat_message("user", avatar="🐠").write(prompt)

    try:
        history_api = [{"role": m["role"], "parts": [{"text": m["content"]}]} for m in st.session_state["messages"] if "content" in m]
        strict_prompt = f"{prompt}\n(คำสั่งลับ: ค้นหาคำตอบจาก Context เท่านั้น และระบุเลขหน้า [PAGE: x])"
        
        response = model.start_chat(history=history_api).send_message(strict_prompt)
        response_text = response.text
        
        page_match = re.search(r"\[PAGE:\s*(\d+)\]", response_text)
        images_to_show = []
        p_num = None
        if page_match:
            try:
                p_num = int(page_match.group(1))
                if p_num in pdf_hybrid_images: images_to_show = pdf_hybrid_images[p_num]
            except: pass

        with st.chat_message("model", avatar="🐬"):
            st.write(response_text)
            if images_to_show:
                for img in images_to_show: st.image(img, caption=f"หน้า {p_num}", use_container_width=True)
        
        msg_data = {"role": "model", "content": response_text}
        if images_to_show:
            msg_data["image_list"] = images_to_show
            msg_data["page_num_ref"] = p_num
        st.session_state["messages"].append(msg_data)

    except Exception as e:
        st.error(f"Error: {e}")