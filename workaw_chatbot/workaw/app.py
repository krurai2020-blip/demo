import os
import re
import time
import random
import fitz  # PyMuPDF
import google.generativeai as genai
from google.api_core import exceptions
import streamlit as st
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import dotenv

# --- 1. โหลด Config และตั้งค่า API ---
dotenv.load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

if not GOOGLE_API_KEY:
    st.error("❌ ไม่พบ API Key กรุณาตรวจสอบไฟล์ .env")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)

# --- 2. Path & Model Config ---
current_dir = os.path.dirname(os.path.abspath(__file__))
pdf_filename = os.path.join(current_dir, "Graphic.pdf")

generation_config = {
    "temperature": 0.0,
    "top_p": 0.95,
    "max_output_tokens": 2500,
    "response_mime_type": "text/plain",
}

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
}

# --- 3. UI: ฟังก์ชันสร้างฟองอากาศ (Visual Effects) ---
def create_bubbles(num_bubbles=20):
    bubbles_html = ""
    for _ in range(num_bubbles):
        left = random.randint(1, 99)
        size = random.randint(10, 30)
        duration = random.randint(15, 30)
        delay = random.randint(0, 15)
        opacity = random.uniform(0.2, 0.5)
        bubbles_html += f'<div class="bubble" style="left: {left}%; width: {size}px; height: {size}px; animation-duration: {duration}s; animation-delay: {delay}s; opacity: {opacity};"></div>'
    return bubbles_html

# --- 4. CSS: ธีม Pastel Ocean Dream ---
bubbles_html_code = create_bubbles()
animated_ocean_css = f"""
<style>
@keyframes gradient_flow {{
    0% {{ background-position: 0% 50%; }}
    50% {{ background-position: 100% 50%; }}
    100% {{ background-position: 0% 50%; }}
}}
@keyframes swim {{
    0% {{ left: -15%; transform: translateY(0px) rotate(0deg); }}
    50% {{ transform: translateY(20px) rotate(5deg); }}
    100% {{ left: 110%; transform: translateY(0px) rotate(0deg); }}
}}
@keyframes rise {{
    0% {{ bottom: -50px; transform: translateX(0); }}
    100% {{ bottom: 110vh; transform: translateX(-15px); }}
}}
[data-testid="stAppViewContainer"] {{
    background: linear-gradient(-45deg, #e0c3fc, #ffdee9, #b5fffc, #8ec5fc, #c2e9fb);
    background-size: 400% 400%;
    animation: gradient_flow 15s ease infinite;
}}
.bubble {{
    position: fixed;
    bottom: -50px;
    background: radial-gradient(circle at 30% 30%, rgba(255,255,255,0.9), rgba(255,255,255,0.4));
    border-radius: 50%;
    z-index: 0;
    animation: rise infinite ease-in;
    pointer-events: none;
}}
.fish-container {{
    position: fixed; z-index: 1; font-size: 50px;
    animation: swim 25s linear infinite; pointer-events: none;
}}
</style>
<div class="fish-container" style="bottom: 15%;">🐠</div>
<div class="fish-container" style="bottom: 65%; animation-delay: 5s;">🐬</div>
{bubbles_html_code}
"""
st.set_page_config(page_title="Graphic Bot", page_icon="🐬")
st.markdown(animated_ocean_css, unsafe_allow_html=True)

# --- 5. ระบบอ่านไฟล์ Hybrid (Text + Images) ---
@st.cache_resource(show_spinner="กำลังดำน้ำหาข้อมูลในไฟล์ PDF... 🤿")
def load_pdf_data_hybrid(file_path):
    text_content = ""
    page_images_map = {} 
    
    if not os.path.exists(file_path):
        return "", {}

    try:
        doc = fitz.open(file_path)
        for i, page in enumerate(doc):
            page_num = i + 1
            text = page.get_text()
            text_content += f"\n[--- Page {page_num} START ---]\n{text}\n[--- Page {page_num} END ---]\n"
            
            # Extract Images
            saved_images = []
            image_blocks = [b for b in page.get_text("blocks") if b[6] == 1]
            
            for img_block in image_blocks:
                rect = fitz.Rect(img_block[:4])
                if rect.width > 50 and rect.height > 50:
                    try:
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect)
                        saved_images.append(pix.tobytes("png"))
                    except: pass
            
            if not saved_images: # ถ้าไม่มีบล็อกรูป ให้จับภาพทั้งหน้า
                pix_full = page.get_pixmap(matrix=fitz.Matrix(1, 1))
                saved_images.append(pix_full.tobytes("png"))
            
            page_images_map[page_num] = saved_images
        return text_content, page_images_map
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return "", {}

pdf_text, pdf_hybrid_images = load_pdf_data_hybrid(pdf_filename)

# --- 6. Prompt System ---
SYSTEM_PROMPT = f"""
คุณคือ AI ผู้ช่วยตอบคำถามจากเอกสารด้านคอมพิวเตอร์กราฟิกที่ละเอียดรอบคอบ
**Strict Rules:**
1. ตอบโดยใช้ข้อมูลใน [CONTEXT] เท่านั้น
2. หากเนื้อหาในเอกสารมีความยาว ให้ตอบให้ครบถ้วนทุกประเด็น "ห้ามย่อความ"
3. ระบุเลขหน้าเสมอในรูปแบบ [PAGE: x]
4. หากไม่พบข้อมูล ให้บอกว่า "ขออภัยค่ะ ข้อมูลนี้ไม่มีในเอกสาร"

[CONTEXT]:
{pdf_text}
"""

# --- 7. Model Setup ---
@st.cache_resource
def setup_gemini_model():
    candidate_models = ["gemini-2.0-flash", "gemini-1.5-flash"]
    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                safety_settings=SAFETY_SETTINGS,
                generation_config=generation_config,
                system_instruction=SYSTEM_PROMPT
            )
            model.generate_content("Hi", request_options={"timeout": 10}) 
            return model, model_name
        except: continue
    return None, None

model, active_model_name = setup_gemini_model()

# --- 8. Chat Logic & Retry System ---
def send_message_with_retry(chat_session, prompt_text):
    for attempt in range(3):
        try:
            return chat_session.send_message(prompt_text)
        except exceptions.ResourceExhausted:
            wait_time = 5 * (attempt + 1)
            st.toast(f"⏳ ระบบยุ่งเล็กน้อย รอ {wait_time} วินาที...", icon="🐢")
            time.sleep(wait_time)
        except Exception as e:
            st.error(f"Error: {e}")
            break
    return None

# --- 9. UI Main Layout ---
st.title("✨ น้องโลมา Graphic Bot 🐬🫧")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "model", "content": "บุ๋งๆๆ🫧 สวัสดีค่ะ น้องโลมาพร้อมให้บริการด้านกราฟิกแล้วค่า🐬"}]

for msg in st.session_state.messages:
    avatar = "🐠" if msg["role"] == "user" else "🐬"
    with st.chat_message(msg["role"], avatar=avatar):
        st.write(msg["content"])
        if "image_list" in msg:
            for img in msg["image_list"]:
                st.image(img, caption=f"🖼️ อ้างอิงหน้า {msg.get('page_num_ref')}")

if prompt := st.chat_input("ถามเกี่ยวกับบทเรียนกราฟิก..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user", avatar="🐠").write(prompt)

    with st.chat_message("model", avatar="🐬"):
        with st.spinner("น้องโลมากำลังค้นหาข้อมูล..."):
            history = [{"role": m["role"], "parts": [{"text": m["content"]}]} for m in st.session_state.messages[-10:]]
            chat_session = model.start_chat(history=history[:-1])
            response = send_message_with_retry(chat_session, prompt)
            
            if response:
                response_text = response.text
                st.write(response_text)
                
                # Image Matching Logic
                page_match = re.search(r"\[PAGE:\s*(\d+)\]", response_text)
                images_to_show = []
                p_num = None
                
                if page_match:
                    p_num = int(page_match.group(1))
                    images_to_show = pdf_hybrid_images.get(p_num, [])
                    for img in images_to_show:
                        st.image(img, caption=f"ภาพประกอบจากหน้า {p_num}")
                
                st.session_state.messages.append({
                    "role": "model", 
                    "content": response_text,
                    "image_list": images_to_show,
                    "page_num_ref": p_num
                })

with st.sidebar:
    st.success(f"⚓ Model: {active_model_name}")
    if st.button("🗑️ ล้างประวัติการสนทนา"):
        st.session_state.messages = [{"role": "model", "content": "บุ๋งๆๆ🫧 เริ่มต้นคุยกันใหม่นะคะ🐬"}]
        st.rerun()