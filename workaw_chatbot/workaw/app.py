import os
import re
import fitz  # PyMuPDF
import google.generativeai as genai
import streamlit as st
from prompt import PROMPT_WORKAW
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import dotenv

# --- Load Environment ---
dotenv.load_dotenv()

# --- CSS Theme ---
page_bg_img = """
<style>
[data-testid="stAppViewContainer"] {
    background-image: linear-gradient(to bottom right, #E0C3FC, #FFD1DC, #BDE0FE);
}
[data-testid="stHeader"] { background-color: rgba(0,0,0,0); }
[data-testid="stSidebar"] { background-color: #F3E5F5; }
</style>
"""
st.markdown(page_bg_img, unsafe_allow_html=True)
st.title("✨ น้อง Graphic Bot (โหมดตรวจสอบ) 🛠️")

# --- 🔧 ส่วนตรวจสอบระบบ (DIAGNOSTICS) ---
with st.expander("🔴 คลิกที่นี่เพื่อดูสถานะการเชื่อมต่อ (Debug Info)", expanded=True):
    st.write("### 1. ตรวจสอบ API Key")
    
    # 1. เช็คจาก .env
    env_key = os.getenv('GOOGLE_API_KEY')
    api_key_to_use = None
    
    if env_key:
        st.success(f"✅ พบ API Key ในระบบแล้ว (ขึ้นต้นด้วย: {env_key[:5]}...)")
        api_key_to_use = env_key
    else:
        st.error("❌ ไม่พบ API Key ใน Environment Variable (.env)")

    # 2. ช่องสำรองสำหรับกรอก Key เอง
    user_key = st.text_input("👇 หรือวาง API Key ของคุณตรงนี้เพื่อทดสอบทันที:", type="password")
    if user_key:
        api_key_to_use = user_key
        st.info("⚠️ กำลังใช้ Key ที่กรอกใหม่นี้แทน Key ในเครื่อง")

    st.write("### 2. ตรวจสอบโมเดลจาก Google")
    valid_model_name = None
    
    if api_key_to_use:
        try:
            genai.configure(api_key=api_key_to_use)
            
            # สั่งให้ Google List รายชื่อโมเดลมาให้ดูเลย ไม่ต้องเดา
            st.write("⏳ กำลังติดต่อ Google Server เพื่อขอรายชื่อโมเดล...")
            models_list = list(genai.list_models())
            
            found_models = []
            for m in models_list:
                # กรองเอาเฉพาะโมเดลที่ Chat ได้ (generateContent)
                if 'generateContent' in m.supported_generation_methods:
                    found_models.append(m.name)
            
            if found_models:
                st.success(f"✅ เชื่อมต่อสำเร็จ! โมเดลที่ใช้ได้: {found_models}")
                
                # ลำดับความชอบในการเลือกโมเดล (Flash -> Pro -> อื่นๆ)
                preferred_order = [
                    "models/gemini-1.5-flash", 
                    "models/gemini-1.5-flash-latest",
                    "models/gemini-1.5-flash-001",
                    "models/gemini-1.5-pro", 
                    "models/gemini-pro"
                ]
                
                # Logic การเลือกโมเดล
                for pref in preferred_order:
                    if pref in found_models:
                        valid_model_name = pref
                        break
                
                if not valid_model_name:
                    valid_model_name = found_models[0] # ถ้าไม่เจอตัวที่ชอบ เอาตัวแรกที่มี
                
                st.info(f"🚀 ระบบเลือกใช้โมเดล: **{valid_model_name}**")
            else:
                st.warning("⚠️ เชื่อมต่อได้ แต่บัญชีนี้ไม่มีสิทธิ์ใช้โมเดล Chat (generateContent)")
                
        except Exception as e:
            st.error(f"❌ API Key ผิดพลาด หรือ เชื่อมต่อไม่ได้: {e}")
            st.stop()
    else:
        st.warning("กรุณาใส่ API Key ก่อนเริ่มใช้งาน")
        st.stop()

# --- ถ้าผ่านจุดข้างบนมาได้ แสดงว่าเชื่อมต่อติดแล้ว ---

# --- Config Model ---
generation_config = {
    "temperature": 0.0,
    "top_p": 0.95,
    "max_output_tokens": 2048,
    "response_mime_type": "text/plain",
}

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
}

# สร้างโมเดลจากชื่อที่หาเจอจริงๆ
if valid_model_name:
    model = genai.GenerativeModel(
        model_name=valid_model_name,
        safety_settings=SAFETY_SETTINGS,
        generation_config=generation_config,
        system_instruction=PROMPT_WORKAW
    )

# --- PDF Loading Logic ---
@st.cache_resource
def load_pdf_data(file_path):
    if not os.path.exists(file_path):
        return None, {}
    
    try:
        doc = fitz.open(file_path)
        text_content = ""
        images_map = {}
        for i, page in enumerate(doc):
            text_content += f"\n[--- Page {i+1} START ---]\n{page.get_text()}\n[--- Page {i+1} END ---]\n"
            
            # ตัดรูปอย่างง่าย
            try:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                images_map[i+1] = [pix.tobytes("png")]
            except:
                pass
                
        return text_content, images_map
    except Exception as e:
        st.error(f"อ่าน PDF ไม่ได้: {e}")
        return None, {}

current_dir = os.path.dirname(os.path.abspath(__file__))
pdf_filename = os.path.join(current_dir, "Graphic.pdf")
pdf_text, pdf_images = load_pdf_data(pdf_filename)

if not pdf_text:
    st.error("⚠️ ไม่พบไฟล์ Graphic.pdf ในโฟลเดอร์เดียวกับ app.py")

# --- Chat Interface ---
if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "model", "content": "ระบบพร้อมใช้งานแล้วค่ะ (ผ่านการตรวจสอบ)"}]

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

if prompt := st.chat_input("ถามมาได้เลย..."):
    st.session_state["messages"].append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)
    
    if pdf_text and valid_model_name:
        full_prompt = f"{prompt}\nCONTEXT:\n{pdf_text}"
        
        try:
            response = model.generate_content(full_prompt)
            st.chat_message("model").write(response.text)
            st.session_state["messages"].append({"role": "model", "content": response.text})
        except Exception as e:
            st.error(f"Error: {e}")