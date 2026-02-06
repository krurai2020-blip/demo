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

# --- 1. โหลด Config & API Key ---
dotenv.load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

if not GOOGLE_API_KEY:
    st.error("❌ ไม่พบ API Key กรุณาตรวจสอบไฟล์ .env")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)

# --- 2. Path Config ---
current_dir = os.path.dirname(os.path.abspath(__file__))
pdf_filename = os.path.join(current_dir, "Graphic.pdf")

# --- 3. Model & Safety Config ---
generation_config = {
    "temperature": 0.0,
    "max_output_tokens": 3000, # เพิ่มให้ AI ตอบได้ยาวขึ้นไม่ตัดตอน
}

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
}

# --- 4. ระบบอ่านไฟล์แบบ Hybrid (Smart Crop ปรับปรุงใหม่) ---
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
                
                # ดึงเฉพาะรูปภาพที่มีขนาดเหมาะสม ไม่เอาไอคอนเล็กๆ
                image_blocks = [b for b in page.get_text("blocks") if b[6] == 1]
                saved_images = []
                
                for img_block in image_blocks:
                    rect = fitz.Rect(img_block[:4])
                    if rect.width > 120 and rect.height > 120: # กรองขนาดที่ดูเป็นรูปภาพประกอบจริงๆ
                        if 0.3 < (rect.width / rect.height) < 3.0:
                            try:
                                pix_crop = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect)
                                saved_images.append(pix_crop.tobytes("png"))
                            except: pass
                
                # ถ้าไม่เจอรูปเลย ให้ Capture ทั้งหน้าแบบเบาๆ
                if not saved_images:
                    pix_full = page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2))
                    saved_images.append(pix_full.tobytes("png"))

                page_images_map[page_num] = saved_images
            return text_content, page_images_map
        except Exception as e:
            st.error(f"Error reading PDF: {e}")
            return "", {}
    return "", {}

pdf_text, pdf_hybrid_images = load_pdf_data_hybrid(pdf_filename)

# --- 5. ระบบ Chat Memory (Sliding Window ประหยัด Token) ---
def get_clean_history(messages, window_size=6):
    """ส่งประวัติเฉพาะส่วนข้อความ และจำกัดจำนวน Turn เพื่อไม่ให้ Token เต็ม"""
    clean_history = []
    for m in messages[-window_size:]:
        if "content" in m:
            clean_history.append({"role": m["role"], "parts": [{"text": m["content"]}]})
    return clean_history

# --- 6. Prompt System (สั่งให้ตอบครบถ้วน ห้ามย่อ) ---
FULL_SYSTEM_PROMPT = f"""
คุณคือผู้เชี่ยวชาญด้านคอมพิวเตอร์กราฟิก ตอบคำถามโดยใช้ข้อมูลจาก [CONTEXT] เท่านั้น
กฎเหล็ก:
1. ห้ามย่อความเด็ดขาด ให้ตอบเนื้อหาทั้งหมดที่ปรากฏในเอกสารให้ครบทุกประเด็น
2. หากคำตอบกระจายอยู่หลายหน้า ให้นำมารวมกันให้หมด
3. ต้องระบุเลขหน้าในรูปแบบ [PAGE: x] ท้ายคำตอบเสมอ
[CONTEXT]:
{pdf_text}
"""

# --- 7. Setup Model ---
@st.cache_resource
def get_model():
    return genai.GenerativeModel(
        model_name="gemini-2.0-flash", 
        safety_settings=SAFETY_SETTINGS,
        generation_config=generation_config,
        system_instruction=FULL_SYSTEM_PROMPT
    )

model = get_model()

# --- 8. UI Layout & CSS ---
st.set_page_config(page_title="Graphic Expert Bot", page_icon="🐬", layout="wide")

# (ส่วน CSS Ocean Theme ใส่ไว้ในฟังก์ชันเพื่อความเป็นระเบียบ)
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(-45deg, #e0c3fc, #ffdee9, #b5fffc, #8ec5fc, #c2e9fb);
        background-size: 400% 400%;
        animation: gradient_flow 15s ease infinite;
    }
    @keyframes gradient_flow {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    .stChatMessage { background-color: rgba(255, 255, 255, 0.4) !important; border-radius: 15px; }
</style>
""", unsafe_allow_html=True)

st.title("✨ น้องโลมา Graphic Bot 🐬🫧")

if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "model", "content": "บุ๋งๆๆ 🫧 สวัสดีค่ะ น้องโลมาพร้อมสรุปเนื้อหากราฟิกแบบจัดเต็มให้แล้วค่า 🐬"}]

# แสดงประวัติการแชท
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"], avatar="🐠" if msg["role"]=="user" else "🐬"):
        st.write(msg["content"])
        if "image_list" in msg:
            for img_data in msg["image_list"]:
                st.image(img_data, use_container_width=True)

# --- 9. Chat Input & Main Logic ---
if prompt := st.chat_input("สอบถามเรื่องกราฟิกได้เลย..."):
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🐠"):
        st.write(prompt)

    history_api = get_clean_history(st.session_state["messages"])
    chat_session = model.start_chat(history=history_api)

    with st.chat_message("model", avatar="🐬"):
        response_placeholder = st.empty()
        full_response = ""
        
        try:
            # 1. Streaming: พิมพ์คำตอบทีละตัว (ตอบยาวและครบตามสั่ง)
            response = chat_session.send_message(prompt, stream=True)
            for chunk in response:
                full_response += chunk.text
                response_placeholder.markdown(full_response + "▌")
            
            response_placeholder.markdown(full_response)

            # 2. Page Detection: เลือกดึงรูปแค่หน้าแรกที่เจอ
            page_matches = re.findall(r"\[PAGE:\s*(\d+)\]", full_response)
            images_to_save = []
            
            if page_matches:
                unique_pages = sorted(list(set(map(int, page_matches))))
                # เลือกเฉพาะหน้าแรกที่ AI ตรวจพบ เพื่อไม่ให้หน้าจอรก
                primary_page = unique_pages[0] 
                
                if primary_page in pdf_hybrid_images:
                    st.write(f"--- 🖼️ ภาพประกอบจากหน้า {primary_page} ---")
                    for img in pdf_hybrid_images[primary_page]:
                        st.image(img, use_container_width=True)
                        images_to_save.append(img)

            # บันทึกข้อมูลลง Session
            msg_data = {"role": "model", "content": full_response}
            if images_to_save:
                msg_data["image_list"] = images_to_save
            st.session_state["messages"].append(msg_data)

        except exceptions.ResourceExhausted:
            st.error("⏳ ระบบยุ่งเล็กน้อย (Quota เต็ม) รบกวนรอแป๊บเดียวนะคะ")
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {e}")