# GPT 加強版 AI 助理
# 功能整合：搜尋摘要 / 任務拆解 / ToDo 排序 / GPT 郵件寄送 + 附件 / 記憶 / 分類 / 排程 / 多語 / 密碼加密記憶

import streamlit as st
import smtplib
import ssl
import csv
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from openai import OpenAI
import pandas as pd
import os
from ddgs import DDGS
from cryptography.fernet import Fernet
import json

# === 加密帳密儲存工具 ===
KEY_FILE = "secret.key"
DATA_FILE = "secrets.json"

def load_key():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
    else:
        with open(KEY_FILE, "rb") as f:
            key = f.read()
    return key

fernet = Fernet(load_key())

def save_credentials(email, password):
    data = {
        "email": fernet.encrypt(email.encode()).decode(),
        "password": fernet.encrypt(password.encode()).decode()
    }
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def load_credentials():
    if not os.path.exists(DATA_FILE):
        return "", ""
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
    email = fernet.decrypt(data["email"].encode()).decode()
    password = fernet.decrypt(data["password"].encode()).decode()
    return email, password

# === GPT 設定 ===
client = OpenAI(
    api_key=os.environ.get("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

def chatgpt(prompt):
    response = client.chat.completions.create(
        model="openai/gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        timeout=60
    )
    return response.choices[0].message.content

def search_duckduckgo(query, max_results=3):
    with DDGS() as ddgs:
        results = ddgs.text(query)
        return [r["body"] for r in results][:max_results]

def generate_email_content(subject, language="中文", tone="正式、有禮貌，以大學生身份撰寫"):
    suggest_title_prompt = f"請根據以下描述幫我擬一個中文信件主旨：{subject}"
    suggested_title = chatgpt(suggest_title_prompt).strip().replace("主旨：", "").replace("件名：", "").replace("「", "").replace("」", "")
    full_subject = suggested_title if suggested_title else subject
    lang_prefix = {
        "中文": "請用中文",
        "英文": "Please write",
        "日文": "日本語で"
    }[language]
    prompt = f"{lang_prefix} 撰寫一封 email，內容風格為 {tone}，主旨為 {full_subject}，請直接從信件開頭撰寫，不需重複主旨。"
    return full_subject, chatgpt(prompt)

def classify_email(subject, body):
    prompt = f"請判斷這封信的分類：\n主旨：{subject}\n內容：{body}\n分類（工作 / 學校 / 生活 / 其他）為："
    return chatgpt(prompt).strip()

def send_email(sender, password, receiver, subject, body, file=None):
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = receiver
    msg["Subject"] = subject
    msg.attach(MIMEText(body.replace("\n", "<br>"), "html", "utf-8"))

    if file:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(file.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={file.name}")
        msg.attach(part)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())

    log_file = "sent_log.csv"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    preview = body[:100].replace("\n", " ") + ("..." if len(body) > 100 else "")
    category = classify_email(subject, body)

    new_row = [now, sender, receiver, subject, preview, category]
    file_exists = os.path.exists(log_file)
    with open(log_file, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["時間", "寄件人", "收件人", "主旨", "內容摘要", "分類"])
        writer.writerow(new_row)

    return category

# === 聯絡人管理工具 ===
CONTACT_FILE = "contacts.json"

def load_contacts():
    if os.path.exists(CONTACT_FILE):
        with open(CONTACT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_contacts(data):
    with open(CONTACT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# === Streamlit UI ===
st.set_page_config(page_title="GPT AI 助理", page_icon="🤖")
st.title("🤖 超強 AI 助理")

option = st.selectbox("請選擇功能", [
    "🔍 搜尋摘要助理",
    "🧩 任務拆解助理",
    "🗂️ To-Do 排序助理",
    "📬 GPT 郵件寄送助理",
    "📁 聯絡人管理"
])

if option == "🔍 搜尋摘要助理":
    topic = st.text_input("請輸入你要研究的主題")
    if st.button("搜尋並摘要"):
        results = search_duckduckgo(topic)
        if not results:
            st.warning("找不到資料 QQ")
        else:
            combined = "\n\n".join(results)
            result = chatgpt(f"請根據以下資料撰寫一篇關於「{topic}」的摘要報告：\n{combined}")
            st.markdown(result)

elif option == "🧩 任務拆解助理":
    goal = st.text_input("請輸入你的最終目標")
    if st.button("拆解目標"):
        task_list = chatgpt(f"我想達成目標：{goal}，請將此目標拆解為可執行子任務：")
        st.markdown("### ✅ 任務清單：")
        st.text(task_list)

elif option == "📁 聯絡人管理":
    st.markdown("### 📁 聯絡人管理")
    contacts = load_contacts()
    new_name = st.text_input("聯絡人名稱")
    new_email = st.text_input("Email")
    if st.button("新增/更新聯絡人"):
        contacts[new_name] = new_email
        save_contacts(contacts)
        st.success("已儲存聯絡人！")
    if st.button("刪除這位聯絡人"):
        if new_name in contacts:
            del contacts[new_name]
            save_contacts(contacts)
            st.warning("已刪除！")
    st.markdown("### 現有聯絡人")
    st.json(contacts)

elif option == "🗂️ To-Do 排序助理":
    todo_input = st.text_area("請輸入你的待辦事項（每行一項）")
    if st.button("排序待辦"):
        tasks = [line for line in todo_input.strip().split("\n") if line.strip()]
        if tasks:
            prompt = "請根據以下待辦事項的「重要性與緊急性」排序：\n" + "\n".join(f"- {t}" for t in tasks)
            result = chatgpt(prompt)
            st.markdown("### 📋 排序後：")
            st.text(result)
        else:
            st.warning("你沒有輸入任何事項。")

elif option == "📬 GPT 郵件寄送助理":
    contacts = load_contacts()
    # 從 JSON 載入聯絡人清單（已移除重複區塊）
    st.markdown("用 GPT 幫你寫信，自動寄送並紀錄發信紀錄")
    saved_email, saved_pw = load_credentials()
    with st.form("mail_form"):
        sender_email = st.text_input("你的 Gmail（需開啟兩步驗證）", value=saved_email)
        app_password = st.text_input("應用程式密碼（非帳號密碼）", type="password", value=saved_pw)
        receiver_name = st.selectbox("選擇收件人（聯絡人）", list(contacts.keys()) + ["自訂輸入"])
        if receiver_name == "自訂輸入":
            receiver_email = st.text_input("收件人 Gmail")
        else:
              receiver_email = contacts[receiver_name]
        subject = st.text_input("📌 郵件主旨（輸入描述，GPT 將自動擬定主旨）")
        override_subject = st.checkbox("✏️ 使用 GPT 建議主旨後手動修改")
        language = st.selectbox("✏️ 郵件語言", ["中文", "英文", "日文"])
        remember = st.checkbox("記住這組帳密", value=True)
        tone = st.text_input("✒️ 語氣風格（例如：正式、有禮貌、活潑親切）", value="正式、有禮貌")
        generate_btn = st.form_submit_button("✏️ 生成郵件內容")

    if generate_btn and subject:
        with st.spinner("GPT 正在撰寫內容..."):
            subject, draft = generate_email_content(subject, language, tone)
            st.session_state["draft_subject"] = subject
            st.session_state["draft"] = draft

    if "draft" in st.session_state and "draft_subject" in st.session_state:
        st.markdown("### 📝 信件主旨（可編輯）")
        subject = st.text_input("", value=st.session_state["draft_subject"], label_visibility="collapsed")
        st.markdown("### 📄 郵件草稿")
        body = st.text_area("信件內容（可編輯）", value=st.session_state["draft"], height=300)
        attachment = st.file_uploader("📎 附件（可選）")
        delay = st.number_input("⏰ 幾秒後寄出（可設排程）", min_value=0, step=10)
        if st.button("📤 確認並寄出"):
            try:
                if body != st.session_state["draft"]:
                    with open("memory.csv", "a", newline="", encoding="utf-8") as f:
                        csv.writer(f).writerow([subject, st.session_state["draft"], body])
                if remember:
                    save_credentials(sender_email, app_password)
                st.info(f"等待 {delay} 秒後寄出...")
                import time
                time.sleep(delay)
                category = send_email(sender_email, app_password, receiver_email, subject, body, file=attachment)
                st.success(f"✅ 郵件成功寄出！（分類：{category}）")
                del st.session_state["draft"]
            except Exception as e:
                st.error(f"❌ 發送失敗：{e}")

    if os.path.exists("sent_log.csv"):
        df = pd.read_csv("sent_log.csv")
        keyword = st.text_input("🔍 搜尋紀錄（主旨/收件人）")
        if keyword:
            df = df[df["主旨"].str.contains(keyword) | df["收件人"].str.contains(keyword)]
        st.dataframe(df)

        df['時間'] = pd.to_datetime(df['時間'])
        df['日期'] = df['時間'].dt.date
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        df.groupby('日期').size().plot(ax=ax, marker='o')
        ax.set_title("每日寄信次數")
        ax.set_ylabel("數量")
        st.pyplot(fig)

        st.markdown("### 📊 分類統計")
        if "分類" in df.columns:
            st.bar_chart(df["分類"].value_counts())
