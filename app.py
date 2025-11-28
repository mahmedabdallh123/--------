import streamlit as st
import pandas as pd
import json
import os
import io
import requests
import shutil
import re
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from base64 import b64decode

# محاولة استيراد PyGithub (لرفع التعديلات)
try:
    from github import Github
    GITHUB_AVAILABLE = True
except Exception:
    GITHUB_AVAILABLE = False

# ===============================
# ⚙ إعدادات التطبيق - نظام تتبع المصاريف
# ===============================
APP_CONFIG = {
    # إعدادات التطبيق العامة
    "APP_TITLE": "نظام تتبع المصاريف الشخصية",
    "APP_ICON": "💰",
    
    # إعدادات GitHub
    "REPO_NAME": "mahmedabdallh123/--------",
    "BRANCH": "main",
    "EXPENSES_FILE_PATH": "luva.xlsx",
    "LOCAL_EXPENSES_FILE": "luva.xlsx",
    
    # إعدادات الأمان
    "MAX_ACTIVE_USERS": 5,
    "SESSION_DURATION_MINUTES": 120,
    
    # إعدادات الواجهة
    "SHOW_TECH_SUPPORT_TO_ALL": True,
    "CUSTOM_TABS": ["💸 إضافة مصروف", "📊 عرض المصاريف", "📈 الإحصائيات والرسوم", "👥 إدارة المستخدمين", "📞 الدعم الفني"]
}

# ===============================
# 🗂 إعدادات الملفات
# ===============================
USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]

# إنشاء رابط GitHub تلقائياً من الإعدادات
EXPENSES_GITHUB_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['EXPENSES_FILE_PATH']}"

# -------------------------------
# 🧩 دوال مساعدة للملفات والحالة
# -------------------------------
def load_users():
    """تحميل بيانات المستخدمين من ملف JSON"""
    if not os.path.exists(USERS_FILE):
        default_users = {
            "admin": {
                "password": "1111", 
                "role": "admin", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"]
            },
            "user1": {
                "password": "12345", 
                "role": "data_entry", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["data_entry", "view_stats"]
            }
        }
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_users, f, indent=4, ensure_ascii=False)
        return default_users
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
            return users
    except Exception as e:
        st.error(f"❌ خطأ في ملف users.json: {e}")
        return {
            "admin": {"password": "1111", "role": "admin", "permissions": ["all"], "created_at": datetime.now().isoformat()}
        }

def save_users(users):
    """حفظ بيانات المستخدمين إلى ملف JSON"""
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"❌ خطأ في حفظ ملف users.json: {e}")
        return False

def load_state():
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4, ensure_ascii=False)
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)

def cleanup_sessions(state):
    now = datetime.now()
    changed = False
    for user, info in list(state.items()):
        if info.get("active") and "login_time" in info:
            try:
                login_time = datetime.fromisoformat(info["login_time"])
                if now - login_time > SESSION_DURATION:
                    info["active"] = False
                    info.pop("login_time", None)
                    changed = True
            except:
                info["active"] = False
                changed = True
    if changed:
        save_state(state)
    return state

def remaining_time(state, username):
    if not username or username not in state:
        return None
    info = state.get(username)
    if not info or not info.get("active"):
        return None
    try:
        lt = datetime.fromisoformat(info["login_time"])
        remaining = SESSION_DURATION - (datetime.now() - lt)
        if remaining.total_seconds() <= 0:
            return None
        return remaining
    except:
        return None

# -------------------------------
# 🔐 تسجيل الخروج
# -------------------------------
def logout_action():
    state = load_state()
    username = st.session_state.get("username")
    if username and username in state:
        state[username]["active"] = False
        state[username].pop("login_time", None)
        save_state(state)
    
    for key in list(st.session_state.keys()):
        if key != "rerun":
            st.session_state.pop(key)
    
    st.rerun()

# -------------------------------
# 🧠 واجهة تسجيل الدخول
# -------------------------------
def login_ui():
    users = load_users()
    state = cleanup_sessions(load_state())
    
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.user_role = None
        st.session_state.user_permissions = []

    st.title(f"{APP_CONFIG['APP_ICON']} تسجيل الدخول - {APP_CONFIG['APP_TITLE']}")

    username_input = st.selectbox("👤 اختر المستخدم", list(users.keys()))
    password = st.text_input("🔑 كلمة المرور", type="password")

    active_users = [u for u, v in state.items() if v.get("active")]
    active_count = len(active_users)
    st.caption(f"🔒 المستخدمون النشطون الآن: {active_count} / {MAX_ACTIVE_USERS}")

    if not st.session_state.logged_in:
        if st.button("تسجيل الدخول"):
            if username_input in users and users[username_input]["password"] == password:
                if username_input in active_users and username_input != "admin":
                    st.warning("⚠ هذا المستخدم مسجل دخول بالفعل.")
                    return False
                elif active_count >= MAX_ACTIVE_USERS and username_input != "admin":
                    st.error("🚫 الحد الأقصى للمستخدمين المتصلين حالياً.")
                    return False
                
                state[username_input] = {"active": True, "login_time": datetime.now().isoformat()}
                save_state(state)
                st.session_state.logged_in = True
                st.session_state.username = username_input
                st.session_state.user_role = users[username_input].get("role", "viewer")
                st.session_state.user_permissions = users[username_input].get("permissions", ["view_stats"])
                st.success(f"✅ تم تسجيل الدخول: {username_input} ({st.session_state.user_role})")
                st.rerun()
            else:
                st.error("❌ كلمة المرور غير صحيحة.")
        return False
    else:
        username = st.session_state.username
        user_role = st.session_state.user_role
        st.success(f"✅ مسجل الدخول كـ: {username} ({user_role})")
        rem = remaining_time(state, username)
        if rem:
            mins, secs = divmod(int(rem.total_seconds()), 60)
            st.info(f"⏳ الوقت المتبقي: {mins:02d}:{secs:02d}")
        else:
            st.warning("⏰ انتهت الجلسة، سيتم تسجيل الخروج.")
            logout_action()
        if st.button("🚪 تسجيل الخروج"):
            logout_action()
        return True

# -------------------------------
# 🔄 طرق جلب الملف من GitHub
# -------------------------------
def fetch_expenses_from_github():
    """تحميل ملف المصاريف من GitHub"""
    try:
        response = requests.get(EXPENSES_GITHUB_URL, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(APP_CONFIG["LOCAL_EXPENSES_FILE"], "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        try:
            st.cache_data.clear()
        except:
            pass
            
        return True
    except Exception as e:
        st.error(f"⚠ فشل التحديث من GitHub: {str(e)}")
        return False

# -------------------------------
# 📂 تحميل البيانات
# -------------------------------
@st.cache_data(show_spinner=False, ttl=300)
def load_expenses_data():
    """تحميل بيانات المصاريف"""
    if not os.path.exists(APP_CONFIG["LOCAL_EXPENSES_FILE"]):
        # إنشاء ملف جديد إذا لم يكن موجوداً
        create_new_expenses_file()
        return pd.DataFrame()
    
    try:
        df = pd.read_excel(APP_CONFIG["LOCAL_EXPENSES_FILE"])
        # تحويل التاريخ والوقت إذا كانا موجودين
        if 'التاريخ' in df.columns:
            df['التاريخ'] = pd.to_datetime(df['التاريخ']).dt.date
        if 'الوقت' in df.columns:
            df['الوقت'] = pd.to_datetime(df['الوقت']).dt.time
        return df
    except Exception as e:
        st.error(f"❌ خطأ في تحميل بيانات المصاريف: {str(e)}")
        return pd.DataFrame()

def create_new_expenses_file():
    """إنشاء ملف مصاريف جديد"""
    try:
        columns = [
            'التاريخ', 'الوقت', 'فئة المصروف', 'المبلغ', 'الوصف', 'ملاحظات'
        ]
        df = pd.DataFrame(columns=columns)
        df.to_excel(APP_CONFIG["LOCAL_EXPENSES_FILE"], index=False)
        return True
    except Exception as e:
        st.error(f"❌ خطأ في إنشاء ملف المصاريف: {str(e)}")
        return False

# -------------------------------
# 🔁 حفظ البيانات
# -------------------------------
def save_expenses_data(df, commit_message="تحديث بيانات المصاريف"):
    """حفظ بيانات المصاريف إلى ملف Excel"""
    try:
        df.to_excel(APP_CONFIG["LOCAL_EXPENSES_FILE"], index=False)
        
        try:
            st.cache_data.clear()
        except:
            pass

        return True
    except Exception as e:
        st.error(f"❌ خطأ في حفظ البيانات: {str(e)}")
        return False

def add_expense_record(df, category, amount, description="", notes=""):
    """إضافة سجل مصروف جديد"""
    now = datetime.now()
    
    new_record = {
        'التاريخ': now.date(),
        'الوقت': now.time(),
        'فئة المصروف': category,
        'المبلغ': amount,
        'الوصف': description,
        'ملاحظات': notes
    }
    
    new_df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
    return new_record, new_df

# -------------------------------
# 🧮 دوال مساعدة للنظام
# -------------------------------
def get_user_permissions(user_role, user_permissions):
    """الحصول على صلاحيات المستخدم"""
    if "all" in user_permissions:
        return {
            "can_input": True,
            "can_view_stats": True,
            "can_manage_users": True,
            "can_see_tech_support": True
        }
    elif "data_entry" in user_permissions:
        return {
            "can_input": True,
            "can_view_stats": True,
            "can_manage_users": False,
            "can_see_tech_support": APP_CONFIG["SHOW_TECH_SUPPORT_TO_ALL"]
        }
    else:  # viewer
        return {
            "can_input": False,
            "can_view_stats": True,
            "can_manage_users": False,
            "can_see_tech_support": APP_CONFIG["SHOW_TECH_SUPPORT_TO_ALL"]
        }

def get_expense_categories():
    """الحصول على فئات المصاريف"""
    default_categories = [
        "طعام", "مواصلات", "سكن", "تعليم", "تسوق", "ترفيه",
        "صحة", "فواتير", "ملابس", "سفر", "هدايا", "أخرى"
    ]
    return default_categories

def generate_expense_statistics(df, start_date, end_date):
    """توليد إحصائيات المصاريف"""
    if df.empty:
        return pd.DataFrame(), 0, 0
    
    # تصفية البيانات حسب الفترة
    mask = (df['التاريخ'] >= start_date) & (df['التاريخ'] <= end_date)
    filtered_df = df[mask]
    
    if filtered_df.empty:
        return pd.DataFrame(), 0, 0
    
    # إحصائيات حسب الفئة
    stats_by_category = filtered_df.groupby('فئة المصروف').agg({
        'المبلغ': ['count', 'sum', 'mean']
    }).round(2)
    
    stats_by_category.columns = ['عدد المصاريف', 'إجمالي المبلغ', 'متوسط المبلغ']
    stats_by_category = stats_by_category.reset_index()
    
    # الإجماليات
    total_expenses = filtered_df['المبلغ'].sum()
    average_expense = filtered_df['المبلغ'].mean()
    
    return stats_by_category, total_expenses, average_expense

def create_pie_chart(df, start_date, end_date):
    """إنشاء رسم بياني دائري للمصاريف"""
    if df.empty:
        return None
    
    # تصفية البيانات حسب الفترة
    mask = (df['التاريخ'] >= start_date) & (df['التاريخ'] <= end_date)
    filtered_df = df[mask]
    
    if filtered_df.empty:
        return None
    
    # تجميع البيانات حسب الفئة
    category_totals = filtered_df.groupby('فئة المصروف')['المبلغ'].sum().reset_index()
    
    # إنشاء الرسم البياني الدائري
    fig = px.pie(
        category_totals, 
        values='المبلغ', 
        names='فئة المصروف',
        title=f"توزيع المصاريف من {start_date} إلى {end_date}",
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    
    fig.update_traces(
        textposition='inside',
        textinfo='percent+label+value',
        hovertemplate='<b>%{label}</b><br>المبلغ: %{value:,.0f} جنيه<br>النسبة: %{percent}'
    )
    
    fig.update_layout(
        title_x=0.5,
        title_font_size=16,
        showlegend=True,
        height=500
    )
    
    return fig

def create_monthly_trend_chart(df):
    """إنشاء رسم بياني للمصاريف الشهرية"""
    if df.empty:
        return None
    
    # استخراج الشهر والسنة
    df['الشهر'] = pd.to_datetime(df['التاريخ']).dt.to_period('M')
    monthly_totals = df.groupby('الشهر')['المبلغ'].sum().reset_index()
    monthly_totals['الشهر'] = monthly_totals['الشهر'].astype(str)
    
    # إنشاء الرسم البياني
    fig = px.line(
        monthly_totals,
        x='الشهر',
        y='المبلغ',
        title='اتجاه المصاريف الشهرية',
        markers=True
    )
    
    fig.update_layout(
        title_x=0.5,
        xaxis_title='الشهر',
        yaxis_title='المبلغ (جنيه)',
        height=400
    )
    
    return fig

# -------------------------------
# 🖥 الواجهة الرئيسية
# -------------------------------
def main():
    st.set_page_config(
        page_title=APP_CONFIG["APP_TITLE"], 
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # شريط تسجيل الدخول
    with st.sidebar:
        st.header("👤 الجلسة")
        if not st.session_state.get("logged_in"):
            if not login_ui():
                return
        else:
            state = cleanup_sessions(load_state())
            username = st.session_state.username
            user_role = st.session_state.user_role
            rem = remaining_time(state, username)
            if rem:
                mins, secs = divmod(int(rem.total_seconds()), 60)
                st.success(f"👋 {username} | الدور: {user_role} | ⏳ {mins:02d}:{secs:02d}")
            else:
                logout_action()

        st.markdown("---")
        st.write("🔧 أدوات النظام:")
        
        if st.button("🔄 تحديث الملف من GitHub"):
            with st.spinner("جاري تحديث البيانات..."):
                if fetch_expenses_from_github():
                    st.success("✅ تم تحديث البيانات بنجاح")
                    st.rerun()
                else:
                    st.error("❌ فشل تحديث البيانات")
        
        if st.button("🗑 مسح الكاش"):
            try:
                st.cache_data.clear()
                st.success("✅ تم مسح الكاش بنجاح")
                st.rerun()
            except Exception as e:
                st.error(f"❌ خطأ في مسح الكاش: {str(e)}")
        
        st.markdown("---")
        if st.button("🚪 تسجيل الخروج"):
            logout_action()

    # تحميل البيانات
    expenses_df = load_expenses_data()

    # واجهة التبويبات الرئيسية
    st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")

    # التحقق من الصلاحيات
    username = st.session_state.get("username")
    user_role = st.session_state.get("user_role", "viewer")
    user_permissions = st.session_state.get("user_permissions", ["view_stats"])
    permissions = get_user_permissions(user_role, user_permissions)

    # تحديد التبويبات بناءً على الصلاحيات
    tab_names = ["📊 عرض المصاريف", "📈 الإحصائيات والرسوم"]
    
    if permissions["can_input"]:
        tab_names.insert(0, "💸 إضافة مصروف")
    
    if permissions["can_manage_users"]:
        tab_names.append("👥 إدارة المستخدمين")
    
    if permissions["can_see_tech_support"]:
        tab_names.append("📞 الدعم الفني")

    tabs = st.tabs(tab_names)

    # -------------------------------
    # Tab 1: إضافة مصروف
    # -------------------------------
    if permissions["can_input"] and "💸 إضافة مصروف" in tab_names:
        tab_index = tab_names.index("💸 إضافة مصروف")
        with tabs[tab_index]:
            st.header("💸 إضافة مصروف جديد")
            
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.info(f"🕒 سيتم تسجيل المصروف بتاريخ ووقت: {current_time}")
            
            with st.form("expense_entry_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    category = st.selectbox(
                        "📂 اختر فئة المصروف:",
                        get_expense_categories(),
                        key="category_select"
                    )
                    
                    custom_category = st.text_input(
                        "أو اكتب فئة جديدة:",
                        placeholder="اكتب فئة جديدة إذا لم تكن موجودة في القائمة"
                    )
                
                with col2:
                    amount = st.number_input(
                        "💰 المبلغ (جنيه):",
                        min_value=0.0,
                        step=1.0,
                        key="amount_input"
                    )
                    
                    description = st.text_input(
                        "📝 وصف المصروف:",
                        placeholder="وصف مختصر للمصروف"
                    )
                
                notes = st.text_area(
                    "📋 ملاحظات إضافية:",
                    placeholder="أي ملاحظات إضافية حول المصروف"
                )
                
                submitted = st.form_submit_button("💾 حفظ المصروف")
                
                if submitted:
                    if amount <= 0:
                        st.error("❌ يرجى إدخال مبلغ صحيح أكبر من الصفر")
                    else:
                        # استخدام الفئة المخصصة إذا تم إدخالها
                        final_category = custom_category if custom_category.strip() else category
                        
                        new_record, updated_df = add_expense_record(
                            expenses_df, final_category, amount, description, notes
                        )
                        
                        if save_expenses_data(updated_df, f"إضافة مصروف {final_category}"):
                            st.success(f"✅ تم حفظ المصروف بنجاح!")
                            st.json({
                                "الفئة": new_record['فئة المصروف'],
                                "المبلغ": f"{new_record['المبلغ']:,.2f} جنيه",
                                "التاريخ": str(new_record['التاريخ']),
                                "الوقت": str(new_record['الوقت'])
                            })
                            st.rerun()

    # -------------------------------
    # Tab 2: عرض المصاريف
    # -------------------------------
    view_tab_index = tab_names.index("📊 عرض المصاريف")
    with tabs[view_tab_index]:
        st.header("📊 عرض المصاريف")
        
        if expenses_df.empty:
            st.warning("⚠ لا توجد مصاريف مسجلة حتى الآن.")
        else:
            # خيارات التصفية
            st.subheader("🔍 تصفية البيانات")
            
            col1, col2 = st.columns(2)
            
            with col1:
                start_date = st.date_input(
                    "من تاريخ:",
                    value=datetime.now().date() - timedelta(days=30),
                    key="start_date"
                )
                
                # تصفية حسب الفئة
                all_categories = expenses_df['فئة المصروف'].unique()
                selected_categories = st.multiselect(
                    "اختر الفئات:",
                    all_categories,
                    default=all_categories
                )
            
            with col2:
                end_date = st.date_input(
                    "إلى تاريخ:",
                    value=datetime.now().date(),
                    key="end_date"
                )
                
                # تصفية حسب المبلغ
                min_amount = st.number_input(
                    "أقل مبلغ:",
                    min_value=0.0,
                    value=0.0,
                    step=10.0
                )
                
                max_amount = st.number_input(
                    "أعلى مبلغ:",
                    min_value=0.0,
                    value=float(expenses_df['المبلغ'].max()) if not expenses_df.empty else 1000.0,
                    step=10.0
                )
            
            # تطبيق التصفية
            filtered_df = expenses_df.copy()
            
            # تصفية حسب التاريخ
            filtered_df = filtered_df[
                (filtered_df['التاريخ'] >= start_date) & 
                (filtered_df['التاريخ'] <= end_date)
            ]
            
            # تصفية حسب الفئة
            if selected_categories:
                filtered_df = filtered_df[filtered_df['فئة المصروف'].isin(selected_categories)]
            
            # تصفية حسب المبلغ
            filtered_df = filtered_df[
                (filtered_df['المبلغ'] >= min_amount) & 
                (filtered_df['المبلغ'] <= max_amount)
            ]
            
            if filtered_df.empty:
                st.warning("⚠ لا توجد بيانات تطابق معايير التصفية")
            else:
                # عرض الإحصائيات السريعة
                total_filtered = filtered_df['المبلغ'].sum()
                avg_filtered = filtered_df['المبلغ'].mean()
                count_filtered = len(filtered_df)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("إجمالي المصاريف", f"{total_filtered:,.2f} جنيه")
                with col2:
                    st.metric("متوسط المصروف", f"{avg_filtered:,.2f} جنيه")
                with col3:
                    st.metric("عدد المصاريف", count_filtered)
                
                # عرض البيانات
                st.subheader("📋 بيانات المصاريف المصفاة")
                st.dataframe(filtered_df, use_container_width=True, height=400)
                
                # خيارات التصدير
                st.subheader("📥 تصدير البيانات")
                
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    filtered_df.to_excel(writer, sheet_name='المصاريف', index=False)
                
                st.download_button(
                    label="📥 تحميل البيانات كملف Excel",
                    data=buffer.getvalue(),
                    file_name=f"المصاريف_{start_date}إلى{end_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    # -------------------------------
    # Tab 3: الإحصائيات والرسوم
    # -------------------------------
    stats_tab_index = tab_names.index("📈 الإحصائيات والرسوم")
    with tabs[stats_tab_index]:
        st.header("📈 الإحصائيات والرسوم البيانية")
        
        if expenses_df.empty:
            st.warning("⚠ لا توجد بيانات لعرض الإحصائيات")
        else:
            # تحديد الفترة للإحصائيات
            col1, col2 = st.columns(2)
            with col1:
                stats_start_date = st.date_input(
                    "من تاريخ للإحصائيات:",
                    value=datetime.now().date() - timedelta(days=30),
                    key="stats_start"
                )
            with col2:
                stats_end_date = st.date_input(
                    "إلى تاريخ للإحصائيات:",
                    value=datetime.now().date(),
                    key="stats_end"
                )
            
            # توليد الإحصائيات
            stats_df, total_expenses, avg_expense = generate_expense_statistics(
                expenses_df, stats_start_date, stats_end_date
            )
            
            if not stats_df.empty:
                # عرض الإحصائيات العددية
                st.subheader("📊 الإحصائيات العددية")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("إجمالي المصاريف", f"{total_expenses:,.2f} جنيه")
                with col2:
                    st.metric("متوسط المصروف", f"{avg_expense:,.2f} جنيه")
                with col3:
                    st.metric("عدد المصاريف", len(stats_df))
                with col4:
                    st.metric("أعلى مصروف", f"{expenses_df['المبلغ'].max():,.2f} جنيه")
                
                # عرض جدول الإحصائيات
                st.dataframe(stats_df, use_container_width=True)
                
                # الرسوم البيانية
                st.subheader("📈 الرسوم البيانية")
                
                # الرسم البياني الدائري
                pie_chart = create_pie_chart(expenses_df, stats_start_date, stats_end_date)
                if pie_chart:
                    st.plotly_chart(pie_chart, use_container_width=True)
                
                # الرسم البياني الشهري
                monthly_chart = create_monthly_trend_chart(expenses_df)
                if monthly_chart:
                    st.plotly_chart(monthly_chart, use_container_width=True)
                
                # رسم بياني شريطي للفئات
                if not stats_df.empty:
                    bar_fig = px.bar(
                        stats_df,
                        x='فئة المصروف',
                        y='إجمالي المبلغ',
                        title='إجمالي المصاريف حسب الفئة',
                        color='فئة المصروف',
                        text='إجمالي المبلغ'
                    )
                    
                    bar_fig.update_layout(
                        title_x=0.5,
                        xaxis_title='فئة المصروف',
                        yaxis_title='المبلغ (جنيه)',
                        height=400,
                        showlegend=False
                    )
                    
                    bar_fig.update_traces(
                        texttemplate='%{text:,.0f}',
                        textposition='outside'
                    )
                    
                    st.plotly_chart(bar_fig, use_container_width=True)

    # -------------------------------
    # Tab إدارة المستخدمين
    # -------------------------------
    if permissions["can_manage_users"] and "👥 إدارة المستخدمين" in tab_names:
        tab_index = tab_names.index("👥 إدارة المستخدمين")
        with tabs[tab_index]:
            st.header("👥 إدارة المستخدمين")
            
            users = load_users()
            
            # عرض المستخدمين الحاليين
            st.subheader("📋 المستخدمين الحاليين")
            if users:
                user_data = []
                for username, info in users.items():
                    user_data.append({
                        "اسم المستخدم": username,
                        "الدور": info.get("role", "user"),
                        "الصلاحيات": ", ".join(info.get("permissions", [])),
                        "تاريخ الإنشاء": info.get("created_at", "غير معروف")
                    })
                
                users_df = pd.DataFrame(user_data)
                st.dataframe(users_df, use_container_width=True)
            
            # إضافة مستخدم جديد
            st.subheader("➕ إضافة مستخدم جديد")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                new_username = st.text_input("اسم المستخدم الجديد:")
            with col2:
                new_password = st.text_input("كلمة المرور:", type="password")
            with col3:
                user_role = st.selectbox("الدور:", ["admin", "data_entry", "viewer"])
            
            if st.button("إضافة مستخدم"):
                if not new_username.strip() or not new_password.strip():
                    st.warning("⚠ الرجاء إدخال اسم المستخدم وكلمة المرور.")
                elif new_username in users:
                    st.warning("⚠ هذا المستخدم موجود بالفعل.")
                else:
                    if user_role == "admin":
                        permissions_list = ["all"]
                    elif user_role == "data_entry":
                        permissions_list = ["data_entry", "view_stats"]
                    else:
                        permissions_list = ["view_stats"]
                    
                    users[new_username] = {
                        "password": new_password,
                        "role": user_role,
                        "permissions": permissions_list,
                        "created_at": datetime.now().isoformat()
                    }
                    if save_users(users):
                        st.success(f"✅ تم إضافة المستخدم '{new_username}' بنجاح.")
                        st.rerun()

    # -------------------------------
    # Tab الدعم الفني
    # -------------------------------
    if permissions["can_see_tech_support"] and "📞 الدعم الفني" in tab_names:
        tab_index = tab_names.index("📞 الدعم الفني")
        with tabs[tab_index]:
            st.header("📞 الدعم الفني")
            
            st.markdown("## 🛠 معلومات التطوير والدعم")
            st.markdown("تم تطوير هذا التطبيق بواسطة:")
            st.markdown("### م. محمد عبدالله")
            st.markdown("### رئيس قسم الكرد والمحطات")
            st.markdown("### مصنع بيل يارن للغزل")
            st.markdown("---")
            st.markdown("### معلومات الاتصال:")
            st.markdown("- 📧 البريد الإلكتروني: m.abdallah@bailyarn.com")
            st.markdown("- 📞 هاتف المصنع: 01000000000")
            st.markdown("---")
            st.markdown("### إصدار النظام:")
            st.markdown("- الإصدار: 1.0")
            st.markdown("- آخر تحديث: 2024")
            st.markdown("- النظام: نظام تتبع المصاريف الشخصية")
            
            st.info("""
            *ملاحظات مهمة:*
            - النظام يساعدك على تتبع جميع مصاريفك اليومية
            - يمكنك إضافة فئات مصاريف مخصصة حسب احتياجاتك
            - الرسوم البيانية تساعدك على فهم أنماط صرفك
            - في حالة وجود أي مشاكل، يرجى التواصل مع الدعم الفني
            """)

# التشغيل الرئيسي للتطبيق
if _name_ == "_main_":
    main()
