import os
import time
import re
import fitz  # PyMuPDF
import google.generativeai as genai
import streamlit as st
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import dotenv

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

# --- CSS ธีมพาสเทล ---
page_bg_img = """
<style>
[data-testid="stAppViewContainer"] {
    background-image: linear-gradient(to bottom right, #E0C3FC, #FFD1DC, #BDE0FE);
}
[data-testid="stHeader"] {
    background-color: rgba(0, 0, 0, 0);
}
[data-testid="stSidebar"] {
    background-color: #F3E5F5;
}
</style>
"""
st.markdown(page_bg_img, unsafe_allow_html=True)

# --- ระบบอ่านไฟล์ (Cache) ---
@st.cache_resource(show_spinner="กำลังอ่านไฟล์ PDF...")
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
                
                # Image extraction
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
            return "", {}
    return "", {}

pdf_text, pdf_hybrid_images = load_pdf_data_hybrid(pdf_filename)

# --- Prompt ---
FULL_SYSTEM_PROMPT = f"""
คุณคือ AI ผู้ช่วยตอบคำถามจากเอกสารที่แนบมานี้เท่านั้น (Document QA)
กฏ:
1. ใช้ข้อมูลจาก [CONTEXT] ด้านล่างนี้เท่านั้น
2. ห้ามใช้ความรู้ภายนอก
3. ถ้าไม่มีคำตอบให้บอกว่า "ขออภัย ไม่มีข้อมูลในเอกสาร"
4. อ้างอิงเลขหน้าเสมอ เช่น [PAGE: 5]

CONTEXT:
{pdf_text}
"""

# --- 🔥 ระบบเลือกโมเดลแบบ "อดทนรอ" (Retry Logic) 🔥 ---
@st.cache_resource(show_spinner="กำลังเชื่อมต่อ (อาจใช้เวลานิดนึง)...")
def setup_gemini_model():
    # เราจะใช้แค่ตัวเดียวที่เสถียรสุด เพื่อไม่ให้โควตากระจาย
    # gemini-2.0-flash คือตัว Standard ที่โควต้าเยอะสุด
    target_model = "gemini-2.0-flash" 
    
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            print(f"🔄 กำลังเชื่อมต่อ (ครั้งที่ {attempt+1})...")
            
            model = genai.GenerativeModel(
                model_name=target_model,
                safety_settings=SAFETY_SETTINGS,
                generation_config=generation_config,
                system_instruction=FULL_SYSTEM_PROMPT
            )
            # Ping Test
            model.generate_content("Hi")
            
            print(f"✅ เชื่อมต่อสำเร็จ!")
            return model, target_model
            
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                wait_time = 20 # รอ 20 วินาที
                print(f"⚠️ โควต้าเต็มชั่วคราว (429) กำลังรอ {wait_time} วินาที...")
                time.sleep(wait_time) 
            else:
                print(f"❌ Error อื่นๆ: {e}")
                # ถ้าไม่ใช่ 429 อาจจะเป็นที่เน็ต หรือโมเดล ให้ลองข้ามไปเลย
                break
    
    return None, None

model, active_model_name = setup_gemini_model()

if model is None:
    st.error("🚨 ระบบไม่สามารถเชื่อมต่อได้เนื่องจากโควต้าเต็ม (Rate Limit Exceeded)")
    st.warning("คำแนะนำ: กรุณารอประมาณ 5-10 นาที แล้วกด Refresh หรือเปลี่ยน API Key ใหม่")
    st.stop()

# --- UI ---
def clear_history():
    st.session_state["messages"] = [{"role": "model", "content": "สวัสดีค่ะ มีอะไรให้ช่วยไหมคะ?"}]
    st.rerun()

with st.sidebar:
    st.success(f"🤖 Connected: {active_model_name}") 
    if st.button("🗑️ ล้างประวัติ"): clear_history()

st.title("✨ น้อง Graphic Bot 🎨")

if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "model", "content": "สวัสดีค่ะ มีอะไรให้ช่วยไหมคะ?"}]

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"], avatar="🦄" if msg["role"] == "model" else "🐰"):
        st.write(msg["content"])
        if "image_list" in msg:
             for img in msg["image_list"]: st.image(img, use_container_width=True)

if prompt := st.chat_input():
    st.session_state["messages"].append({"role": "user", "content": prompt})
    st.chat_message("user", avatar="🐰").write(prompt)

    try:
        # Retry Logic ตอนคุยแชทด้วย
        response = None
        for _ in range(3):
            try:
                chat = model.start_chat(history=[{"role": m["role"], "parts": [m["content"]]} for m in st.session_state["messages"] if "content" in m])
                response = chat.send_message(prompt)
                break
            except Exception as e:
                if "429" in str(e):
                    time.sleep(10)
                    continue
                else:
                    st.error(f"Error: {e}")
                    break
        
        if response:
            text = response.text
            page_match = re.search(r"\[PAGE:\s*(\d+)\]", text)
            imgs = []
            p_num = None
            if page_match:
                p_num = int(page_match.group(1))
                imgs = pdf_hybrid_images.get(p_num, [])

            with st.chat_message("model", avatar="🦄"):
                st.write(text)
                for img in imgs: st.image(img, caption=f"หน้า {p_num}", use_container_width=True)
            
            st.session_state["messages"].append({"role": "model", "content": text, "image_list": imgs, "page_num_ref": p_num})
    except Exception as e:
        st.error("ระบบไม่ตอบสนอง (โควต้าเต็ม)")