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

# --- โหลด Environment Variables ---
dotenv.load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# --- Page Config (ต้องอยู่บรรทัดแรกๆ) ---
st.set_page_config(
    page_title="น้องโลมา Graphic Bot 🐬",
    page_icon="🐬",
    layout="wide"
)

# --- CSS & Animation Setup ---
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

animated_ocean_css = f"""
<style>
@keyframes gradient_flow {{
    0% {{ background-position: 0% 50%; }}
    50% {{ background-position: 100% 50%; }}
    100% {{ background-position: 0% 50%; }}
}}
@keyframes swim {{
    0% {{ left: -15%; transform: translateY(0px) rotate(0deg); }}
    25% {{ transform: translateY(20px) rotate(5deg); }}
    50% {{ transform: translateY(0px) rotate(0deg); }}
    75% {{ transform: translateY(-20px) rotate(-5deg); }}
    100% {{ left: 110%; transform: translateY(0px) rotate(0deg); }}
}}
@keyframes rise {{
    0% {{ bottom: -50px; transform: translateX(0); }}
    50% {{ transform: translateX(15px); }} 
    100% {{ bottom: 110vh; transform: translateX(-15px); }}
}}
[data-testid="stAppViewContainer"] {{
    background: linear-gradient(-45deg, #e0c3fc, #ffdee9, #b5fffc, #8ec5fc, #c2e9fb);
    background-size: 400% 400%;
    animation: gradient_flow 15s ease infinite;
}}
[data-testid="stHeader"] {{ background-color: rgba(0,0,0,0); }}
[data-testid="stSidebar"] {{
    background-color: rgba(255, 255, 255, 0.4);
    backdrop-filter: blur(15px);
    border-right: 1px solid rgba(255,255,255,0.6);
    box-shadow: 5px 0 15px rgba(224, 195, 252, 0.1);
}}
.fish-container {{
    position: fixed;
    bottom: 20px;
    z-index: 1; 
    font-size: 50px;
    animation: swim 25s linear infinite;
    pointer-events: none;
    opacity: 0.9;
    filter: saturate(1.2);
}}
.bubble {{
    position: fixed;
    bottom: -50px;
    background: radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.4));
    border-radius: 50%;
    z-index: 0;
    animation: rise infinite ease-in;
    pointer-events: none;
    box-shadow: 0px 0px 10px rgba(255, 255, 255, 0.5);
}}
</style>
<div class="fish-container" style="bottom: 15%; animation-duration: 28s;">🐠</div>
<div class="fish-container" style="bottom: 35%; animation-duration: 20s; animation-delay: 5s; font-size: 30px;">🐡</div>
<div class="fish-container" style="bottom: 65%; animation-duration: 38s; animation-delay: 2s; font-size: 60px;">🐬</div>
<div class="fish-container" style="bottom: 85%; animation-duration: 45s; animation-delay: 10s; font-size: 25px;">🦑</div>
{create_bubbles()}
"""
st.markdown(animated_ocean_css, unsafe_allow_html=True)

# --- เช็ค API Key ---
if not GOOGLE_API_KEY:
    st.error("❌ ไม่พบ API Key กรุณาตั้งค่าในไฟล์ .env หรือ Secrets")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)

# --- ฟังก์ชันโหลด PDF ---
@st.cache_resource(show_spinner="กำลังดำน้ำหาข้อมูลในไฟล์ PDF... 🤿")
def load_pdf_data_hybrid(file_source):
    """
    รองรับทั้ง path (str) และ file object (UploadedFile)
    """
    text_content = ""
    page_images_map = {} 
    
    try:
        # เปิดไฟล์จาก Path หรือ UploadedFile
        if isinstance(file_source, str):
            doc = fitz.open(file_source)
        else:
            # กรณีเป็น Bytes (จากการ upload)
            doc = fitz.open(stream=file_source.read(), filetype="pdf")

        for i, page in enumerate(doc):
            page_num = i + 1
            text = page.get_text()
            text_content += f"\n[--- Page {page_num} START ---]\n{text}\n[--- Page {page_num} END ---]\n"
            
            # Image Logic
            image_blocks = [b for b in page.get_text("blocks") if b[6] == 1]
            saved_images = []
            
            if image_blocks:
                for img_block in image_blocks:
                    rect = fitz.Rect(img_block[:4])
                    # ตรวจสอบขนาดขั้นต่ำ
                    if rect.width > 50 and rect.height > 50: 
                        # ขยายขอบเล็กน้อยและตรวจสอบว่าไม่เกินหน้ากระดาษ (Intersection)
                        rect.x0 -= 5; rect.y0 -= 5; rect.x1 += 5; rect.y1 += 5
                        rect = rect & page.rect  # ตัดส่วนที่เกินหน้ากระดาษออก
                        
                        try:
                            pix_crop = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect) # ลด Matrix ลงนิดหน่อยเพื่อความเร็ว
                            saved_images.append(pix_crop.tobytes("png"))
                        except: pass
            
            # ถ้าไม่มีรูปในหน้านั้น ให้ Capture ทั้งหน้า
            if not saved_images:
                try:
                    pix_full = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                    saved_images.append(pix_full.tobytes("png"))
                except: pass

            if saved_images:
                page_images_map[page_num] = saved_images
        
        return text_content, page_images_map

    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return "", {}

# --- จัดการไฟล์ PDF ---
current_dir = os.path.dirname(os.path.abspath(__file__))
default_pdf_path = os.path.join(current_dir, "Graphic.pdf")

with st.sidebar:
    st.header("📂 เอกสารความรู้")
    uploaded_file = st.file_uploader("อัปโหลด PDF ใหม่ (ถ้ามี)", type=["pdf"])
    
    if uploaded_file:
        pdf_source = uploaded_file
        st.success("✅ ใช้ไฟล์ที่อัปโหลด")
    elif os.path.exists(default_pdf_path):
        pdf_source = default_pdf_path
        st.info(f"✅ ใช้ไฟล์: {os.path.basename(default_pdf_path)}")
    else:
        pdf_source = None
        st.warning("⚠️ ไม่พบไฟล์ Graphic.pdf และไม่มีการอัปโหลด")

# โหลดข้อมูลถ้ามี Source
pdf_text, pdf_hybrid_images = load_pdf_data_hybrid(pdf_source) if pdf_source else ("", {})

# --- Model Setup ---
FULL_SYSTEM_PROMPT = f"""
คุณคือ AI ผู้ช่วยตอบคำถามจากเอกสาร (Document QA)
**Strict Rules:**
1. ตอบโดยใช้ข้อมูลใน [CONTEXT] ด้านล่างนี้เท่านั้น
2. ห้ามใช้ความรู้นอกเหนือจากเอกสาร หรือความรู้ทั่วไป
3. หากไม่มีข้อมูลในเอกสาร ให้ตอบว่า "ขออภัยค่ะ ข้อมูลส่วนนี้ไม่มีระบุไว้ในเอกสาร"
4. ระบุเลขหน้าเสมอ เช่น [PAGE: 5] โดยดูจาก Tag [--- Page X START ---]

[CONTEXT]:
{pdf_text}
"""

generation_config = {
    "temperature": 0.3, # เพิ่มนิดหน่อยให้ลื่นไหลขึ้น
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 2000,
}

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
}

@st.cache_resource
def setup_gemini_model():
    # Model List: ปรับให้เป็นชื่อที่ Google เปิดให้บริการจริง
    candidate_models = [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-1.0-pro"
    ]  
    
    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                safety_settings=SAFETY_SETTINGS,
                generation_config=generation_config,
                system_instruction=FULL_SYSTEM_PROMPT
            )
            # Test Dry Run
            model.generate_content("Ping")
            return model, model_name
        except Exception:
            continue
            
    return None, None

model, active_model_name = setup_gemini_model()

if not model:
    st.error("🚨 ไม่สามารถเชื่อมต่อกับ Gemini Server ได้ กรุณาเช็ค API Key หรือ Internet")
    st.stop()

with st.sidebar:
    st.caption(f"🤖 Brain: {active_model_name}")
    if st.button("🗑️ ล้างประวัติแชท"):
        st.session_state["messages"] = [{"role": "model", "content": "บุ๋งๆๆ 🫧 สวัสดีค่ะ น้องโลมา AI พร้อมให้บริการแล้วค่า 🐬"}]
        st.rerun()

# --- Chat Interface ---
st.title("✨ น้องโลมา Graphic Bot 🐬🫧")

if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "model", "content": "บุ๋งๆๆ 🫧 สวัสดีค่ะ น้องโลมา AI พร้อมให้บริการแล้วค่า 🐬"}]

# แสดง History
for msg in st.session_state["messages"]:
    avatar_icon = "🐠" if msg["role"] == "user" else "🐬"
    with st.chat_message(msg["role"], avatar=avatar_icon):
        st.markdown(msg["content"])
        if "image_list" in msg:
             for img_data in msg["image_list"]:
                st.image(img_data, caption=f"🖼️ ภาพประกอบหน้า {msg.get('page_num_ref')}", width=400)

# Input
if prompt := st.chat_input("พิมพ์คำถามเกี่ยวกับกราฟิกที่นี่..."):
    if not pdf_text:
        st.error("⚠️ กรุณาอัปโหลด PDF หรือตรวจสอบไฟล์ Graphic.pdf ก่อนเริ่มสนทนา")
    else:
        # Add User Message
        st.session_state["messages"].append({"role": "user", "content": prompt})
        st.chat_message("user", avatar="🐠").markdown(prompt)

        try:
            # Prepare History (Google API Require: starts with user, alternating)
            history_api = []
            for m in st.session_state["messages"]:
                if m["role"] == "model" and m["content"].startswith("บุ๋งๆๆ"): 
                    continue # ข้ามข้อความต้อนรับ เพราะ model ห้ามเริ่มก่อนใน API history
                history_api.append({"role": m["role"], "parts": [{"text": m["content"]}]})

            chat_session = model.start_chat(history=history_api)
            
            with st.spinner("น้องโลมาแอบไปอ่านหนังสือมาตอบ... 📖"):
                response = chat_session.send_message(prompt)
                response_text = response.text

            # Image Extraction Logic
            page_match = re.search(r"\[PAGE:\s*(\d+)\]", response_text)
            images_to_show = []
            p_num = None
            
            if page_match:
                p_num = int(page_match.group(1))
                if p_num in pdf_hybrid_images:
                    images_to_show = pdf_hybrid_images[p_num]

            # Show Result
            with st.chat_message("model", avatar="🐬"):
                st.markdown(response_text)
                if images_to_show:
                    for img in images_to_show:
                        st.image(img, caption=f"หน้า {p_num}")

            # Save Model Message
            msg_data = {"role": "model", "content": response_text}
            if images_to_show:
                msg_data["image_list"] = images_to_show
                msg_data["page_num_ref"] = p_num
            st.session_state["messages"].append(msg_data)

        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {str(e)}")