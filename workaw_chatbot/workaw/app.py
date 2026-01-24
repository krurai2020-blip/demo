import os
import re
import time
import random
import fitz  # PyMuPDF
import google.generativeai as genai
from google.api_core import exceptions # เพิ่ม library สำหรับจับ Error
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
    "max_output_tokens": 2500,
    "response_mime_type": "text/plain",
}


SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
}

# --- 🫧 ฟังก์ชันสร้างฟองอากาศ ---
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

bubbles_html_code = create_bubbles()

# --- 🦄 CSS ธีม Pastel Ocean Dream (ม่วง-ชมพู-ฟ้า) 🦄 ---
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
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span {{ color: #5a4b6e !important; }}
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
{bubbles_html_code}
"""
st.markdown(animated_ocean_css, unsafe_allow_html=True)

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
คุณคือ AI ผู้ช่วยตอบคำถามจากเอกสาร (Document QA) ที่ละเอียดรอบคอบ
**Strict Rules:**
1. ตอบโดยใช้ข้อมูลใน [CONTEXT] ด้านล่างนี้เท่านั้น
2. ห้ามใช้ความรู้นอกเหนือจากเอกสาร หรือความรู้ทั่วไป
3. **หากเนื้อหาในเอกสารมีความยาว ให้ตอบออกมาให้ครบถ้วนทุกประเด็น "ห้ามย่อความ" และ "ห้ามตัดทอนเนื้อหา"** <--- เพิ่มตรงนี้
4. หากข้อมูลกระจายอยู่หลายหน้า ให้นำมารวมกันให้ครบ
5. ระบุเลขหน้าเสมอ เช่น [PAGE: 5]

[CONTEXT]:
{pdf_text}
"""

# --- 🔥 ฟังก์ชันเช็ค Error (Debug Mode) 🔥 ---
@st.cache_resource(show_spinner="กำลังเชื่อมต่อสมอง AI...")
def setup_gemini_model():
    candidate_models = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-flash-latest"
    ]  
    error_logs = [] 
    for model_name in candidate_models:
        try:
            # Test ping
            test_model = genai.GenerativeModel(
                model_name=model_name,
                safety_settings=SAFETY_SETTINGS,
                generation_config=generation_config
            )
            test_model.generate_content("Hi")           
            
            # Create Real Model
            real_model = genai.GenerativeModel(
                model_name=model_name,
                safety_settings=SAFETY_SETTINGS,
                generation_config=generation_config,
                system_instruction=FULL_SYSTEM_PROMPT
            )           
            return real_model, model_name  
        except Exception as e:
            error_msg = f"❌ {model_name}: {str(e)}"
            print(error_msg)
            error_logs.append(error_msg)
            continue 
    
    st.error("⚠️ เชื่อมต่อไม่ได้ ดูรายละเอียดด้านล่าง:")
    for err in error_logs:
        st.code(err, language='text')    
    return None, None

model, active_model_name = setup_gemini_model()

if model is None:
    st.error("🚨 ไม่สามารถเชื่อมต่อกับ Gemini ได้เลย (กรุณาเช็ค API Key หรือลองใหม่อีกครั้งใน 1 นาที)")
    st.stop()

# --- 🚀 ฟังก์ชันส่งข้อความแบบมี Retry (แก้ 429) ---
def send_message_with_retry(chat_session, prompt_text, retries=3):
    """
    พยายามส่งข้อความ และถ้าระบบแจ้งว่า Quota เต็ม (429) จะรอแล้วส่งใหม่
    """
    for attempt in range(retries):
        try:
            response = chat_session.send_message(prompt_text)
            return response
        except exceptions.ResourceExhausted as e:
            wait_time = 10 * (attempt + 1) # รอ 10s, 20s, 30s...
            st.toast(f"⏳ ระบบกำลังยุ่ง (429) รอสักครู่ {wait_time} วินาที...", icon="🐢")
            time.sleep(wait_time)
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {e}")
            return None
    
    st.error("❌ หมดเวลาเชื่อมต่อ กรุณาลองใหม่ภายหลัง")
    return None

# --- UI & Chat Logic ---
def clear_history():
    st.session_state["messages"] = [{"role": "model", "content": "บุ๋งๆๆ 🫧 สวัสดีค่ะ น้องโลมา AI โปรแกรมคอมพิวเตอร์กราฟิกพร้อมให้บริการแล้วค่า 🐬"}]
    st.rerun()

with st.sidebar:
    st.success(f"⚓ Connected: {active_model_name}")
    if st.button("🗑️ ล้างประวัติ"): clear_history()

st.title("✨ น้องโลมา Graphic Bot 🐬🫧")

if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "model", "content": "บุ๋งๆๆ 🫧 สวัสดีค่ะ น้องโลมา AI โปรแกรมคอมพิวเตอร์กราฟิกพร้อมให้บริการแล้วค่า 🐬"}]

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
        # ✅ ตัดประวัติการแชท: เอาแค่ 10 ข้อความล่าสุดเพื่อประหยัด Token
        recent_history = st.session_state["messages"][-10:] if len(st.session_state["messages"]) > 10 else st.session_state["messages"]
        
        history_api = [{"role": m["role"], "parts": [{"text": m["content"]}]} for m in recent_history if "content" in m]
        
        chat_session = model.start_chat(history=history_api)
        strict_prompt = f"{prompt}\n(คำสั่งลับ: ค้นหาคำตอบจาก Context เท่านั้น และระบุเลขหน้า [PAGE: x])"
        
        # ✅ เรียกใช้ฟังก์ชัน Retry แทน send_message ปกติ
        with st.spinner("น้องโลมาแอบไปอ่านหนังสือมาตอบ... 📖"):
            response = send_message_with_retry(chat_session, strict_prompt)
        
        if response:
            response_text = response.text
            
            # Extract Images
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