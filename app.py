import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import streamlit as st
import matplotlib.pyplot as plt
from collections import Counter
import io

# تهيئة صفحة Streamlit
st.set_page_config(page_title="تحليل سجل الأحداث", layout="wide")
st.title("📊 تحليل سجل الأحداث الصناعية (Logbook Analysis)")
st.markdown("### حساب MTTR, MTBF وتكرارات الأحداث")

# CSS مخصص للعربية
st.markdown("""
<style>
    .stApp {
        direction: rtl;
        text-align: right;
    }
    .css-1d391kg {
        text-align: right;
    }
</style>
""", unsafe_allow_html=True)

# رفع الملف
uploaded_file = st.file_uploader("اختر ملف السجل (Logbook_YYYYMMDD.txt)", type="txt")

if uploaded_file is not None:
    try:
        # قراءة الملف
        content = uploaded_file.read().decode('utf-8')
        lines = content.split('\n')
        
        # معالجة البيانات
        data = []
        for line in lines:
            # تخطي الأسطر الفارغة أو رؤوس الجداول
            if line.startswith("=") or line.strip() == "":
                continue
            
            parts = line.split("\t")
            
            # التأكد من وجود 4 أعمدة
            while len(parts) < 4:
                parts.append("")
            
            # تنظيف البيانات
            cleaned_parts = [part.strip() for part in parts]
            
            # التأكد من وجود تاريخ ووقت
            if len(cleaned_parts) >= 2 and cleaned_parts[0] and cleaned_parts[1]:
                data.append(cleaned_parts[:4])
        
        # إنشاء DataFrame
        df = pd.DataFrame(data, columns=["Date", "Time", "Event", "Details"])
        
        # عرض عينة من البيانات
        with st.expander("عرض البيانات الأصلية (أول 100 سطر)"):
            st.dataframe(df.head(100), use_container_width=True)
        
        # تحويل التاريخ والوقت
        df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], 
                                       format='%d.%m.%Y %H:%M:%S', 
                                       errors='coerce')
        
        # إزالة الصفوف غير الصالحة
        df = df.dropna(subset=['DateTime']).sort_values('DateTime').reset_index(drop=True)
        
        # تعريف أنواع الأحداث
        failure_patterns = ['E', 'W', 'T']
        df['IsFailure'] = df['Event'].apply(lambda x: any(str(x).startswith(pattern) for pattern in failure_patterns))
        df['IsStoppage'] = df['Event'].astype(str).str.contains('stopped|Stopped|machine stopped', case=False, na=False)
        df['IsStartup'] = df['Event'].astype(str).str.contains('Starting speed|Automatic mode|starting', case=False, na=False)
        
        # ==================== قسم 1: حساب تكرارات الأحداث ====================
        st.subheader("📈 1. تحليل تكرارات الأحداث")
        
        event_counts = df['Event'].value_counts().reset_index()
        event_counts.columns = ['الحدث', 'عدد التكرارات']
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.markdown("**أكثر 20 حدث تكرارًا:**")
            st.dataframe(event_counts.head(20), use_container_width=True)
        
        with col2:
            # رسم بياني بسيط باستخدام matplotlib
            fig, ax = plt.subplots(figsize=(8, 10))
            top_20 = event_counts.head(20)
            y_pos = range(len(top_20))
            
            ax.barh(y_pos, top_20['عدد التكرارات'])
            ax.set_yticks(y_pos)
            ax.set_yticklabels(top_20['الحدث'], fontsize=8)
            ax.set_xlabel('عدد التكرارات')
            ax.set_title('أكثر 20 حدث تكرارًا')
            ax.invert_yaxis()  # أعلى تكرار في الأعلى
            
            plt.tight_layout()
            st.pyplot(fig)
        
        # ==================== قسم 2: حساب MTBF ====================
        st.subheader("⏱️ 2. حساب MTBF (متوسط الوقت بين الأعطال)")
        
        # البحث عن فترات التشغيل
        operation_periods = []
        current_start = None
        
        for i in range(len(df)):
            if df.iloc[i]['IsStartup'] and current_start is None:
                current_start = df.iloc[i]['DateTime']
            elif (df.iloc[i]['IsFailure'] or df.iloc[i]['IsStoppage']) and current_start is not None:
                current_end = df.iloc[i]['DateTime']
                operation_periods.append((current_start, current_end))
                current_start = None
        
        # حساب MTBF
        if operation_periods and len(operation_periods) > 1:
            time_between_failures = []
            for i in range(1, len(operation_periods)):
                time_diff = (operation_periods[i][0] - operation_periods[i-1][1]).total_seconds() / 60
                if time_diff > 0:
                    time_between_failures.append(time_diff)
            
            if time_between_failures:
                mttf = np.mean(time_between_failures)
                mttf_std = np.std(time_between_failures)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("MTBF", f"{mttf:.2f} دقيقة", 
                             delta=f"±{mttf_std:.2f}")
                with col2:
                    st.metric("الانحراف المعياري", f"{mttf_std:.2f} دقيقة")
                with col3:
                    st.metric("عدد فترات التشغيل", len(time_between_failures))
                
                # رسم توزيع MTBF
                fig2, ax2 = plt.subplots(figsize=(10, 4))
                ax2.hist(time_between_failures, bins=20, color='green', alpha=0.7)
                ax2.axvline(mttf, color='red', linestyle='--', 
                           label=f'MTBF: {mttf:.1f} دقيقة')
                ax2.set_xlabel('الوقت بين الأعطال (دقيقة)')
                ax2.set_ylabel('التكرار')
                ax2.set_title('توزيع الأوقات بين الأعطال')
                ax2.legend()
                ax2.grid(True, alpha=0.3)
                st.pyplot(fig2)
        
        # ==================== قسم 3: حساب MTTR ====================
        st.subheader("🔧 3. حساب MTTR (متوسط وقت الإصلاح)")
        
        repair_times = []
        
        for i in range(len(df) - 1):
            if df.iloc[i]['IsFailure'] or df.iloc[i]['IsStoppage']:
                failure_time = df.iloc[i]['DateTime']
                
                for j in range(i + 1, len(df)):
                    if df.iloc[j]['IsStartup']:
                        repair_time = df.iloc[j]['DateTime']
                        repair_duration = (repair_time - failure_time).total_seconds() / 60
                        if 0 < repair_duration < 1440:  # أقل من 24 ساعة
                            repair_times.append({
                                'العطل': df.iloc[i]['Event'],
                                'وقت العطل': failure_time,
                                'وقت الإصلاح': repair_time,
                                'مدة الإصلاح (دقيقة)': repair_duration
                            })
                        break
        
        if repair_times:
            repair_df = pd.DataFrame(repair_times)
            mttr = repair_df['مدة الإصلاح (دقيقة)'].mean()
            mttr_std = repair_df['مدة الإصلاح (دقيقة)'].std()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("MTTR", f"{mttr:.2f} دقيقة", 
                         delta=f"±{mttr_std:.2f}")
            with col2:
                st.metric("الانحراف المعياري", f"{mttr_std:.2f} دقيقة")
            with col3:
                st.metric("عدد حالات الإصلاح", len(repair_times))
            
            with st.expander("عرض تفاصيل فترات الإصلاح"):
                st.dataframe(repair_df, use_container_width=True)
            
            # رسم توزيع MTTR
            fig3, ax3 = plt.subplots(figsize=(10, 4))
            ax3.hist(repair_df['مدة الإصلاح (دقيقة)'], bins=20, color='red', alpha=0.7)
            ax3.axvline(mttr, color='blue', linestyle='--', 
                       label=f'MTTR: {mttr:.1f} دقيقة')
            ax3.set_xlabel('وقت الإصلاح (دقيقة)')
            ax3.set_ylabel('التكرار')
            ax3.set_title('توزيع أوقات الإصلاح')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
            st.pyplot(fig3)
        
        # ==================== قسم 4: التحليل الزمني ====================
        st.subheader("📅 4. التحليل الزمني بين الأحداث")
        
        # حساب الفترات الزمنية
        df['الفرق الزمني (دقيقة)'] = df['DateTime'].diff().dt.total_seconds() / 60
        
        with st.expander("عرض الفترات الزمنية بين الأحداث"):
            time_diff_df = df[['DateTime', 'Event', 'Details', 'الفرق الزمني (دقيقة)']].copy()
            st.dataframe(time_diff_df.head(50), use_container_width=True)
        
        # إحصائيات الفترات
        time_stats = df['الفرق الزمني (دقيقة)'].describe()
        st.markdown("**إحصائيات الفترات الزمنية:**")
        st.dataframe(time_stats.to_frame().T, use_container_width=True)
        
        # ==================== قسم 5: التحليل المتقدم ====================
        st.subheader("📊 5. تحليل متقدم")
        
        # تحليل حسب الوقت
        df['الساعة'] = df['DateTime'].dt.hour
        
        # توزيع الأحداث حسب الساعة
        hourly_events = df[df['IsFailure']].groupby('الساعة').size().reset_index()
        hourly_events.columns = ['الساعة', 'عدد الأحداث']
        
        fig4, ax4 = plt.subplots(figsize=(10, 4))
        ax4.plot(hourly_events['الساعة'], hourly_events['عدد الأحداث'], 
                marker='o', linewidth=2)
        ax4.set_xlabel('الساعة')
        ax4.set_ylabel('عدد الأحداث')
        ax4.set_title('توزيع الأحداث على مدار اليوم')
        ax4.set_xticks(range(0, 24, 2))
        ax4.grid(True, alpha=0.3)
        st.pyplot(fig4)
        
        # ==================== قسم 6: الملخص التنفيذي ====================
        st.subheader("📋 6. الملخص التنفيذي")
        
        # حساب المؤشرات الرئيسية
        total_events = len(df)
        failure_events_count = df['IsFailure'].sum()
        stoppage_events_count = df['IsStoppage'].sum()
        unique_events = df['Event'].nunique()
        
        # عرض البطاقات
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("إجمالي الأحداث", f"{total_events:,}")
        with col2:
            st.metric("أحداث إخفاق", f"{failure_events_count:,}")
        with col3:
            st.metric("أحداث توقف", f"{stoppage_events_count:,}")
        with col4:
            st.metric("أنواع الأحداث", f"{unique_events:,}")
        
        # حساب التوفر
        if 'time_between_failures' in locals() and time_between_failures and 'repair_times' in locals() and repair_times:
            total_uptime = sum(time_between_failures)
            total_downtime = sum(repair_df['مدة الإصلاح (دقيقة)']) if 'repair_df' in locals() else 0
            if total_uptime + total_downtime > 0:
                availability = (total_uptime / (total_uptime + total_downtime)) * 100
                st.metric("التوفر التشغيلي", f"{availability:.1f}%")
        
        # زر لحفظ النتائج
        if st.button("💾 حفظ النتائج في ملف Excel"):
            # إنشاء ملف Excel في الذاكرة
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='البيانات_الأصلية', index=False)
                
                if 'repair_df' in locals():
                    repair_df.to_excel(writer, sheet_name='أوقات_الإصلاح', index=False)
                
                event_counts.to_excel(writer, sheet_name='تكرارات_الأحداث', index=False)
                
                # إنشاء ملخص
                summary_data = {
                    'المؤشر': [
                        'إجمالي الأحداث',
                        'أحداث إخفاق',
                        'أحداث توقف',
                        'أنواع أحداث مختلفة'
                    ],
                    'القيمة': [
                        total_events,
                        failure_events_count,
                        stoppage_events_count,
                        unique_events
                    ]
                }
                
                if 'mttf' in locals():
                    summary_data['المؤشر'].append('MTBF (دقيقة)')
                    summary_data['القيمة'].append(round(mttf, 2))
                
                if 'mttr' in locals():
                    summary_data['المؤشر'].append('MTTR (دقيقة)')
                    summary_data['القيمة'].append(round(mttr, 2))
                
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='الملخص', index=False)
            
            output.seek(0)
            
            # زر التنزيل
            st.download_button(
                label="📥 تنزيل ملف Excel بالنتائج",
                data=output,
                file_name="نتائج_تحليل_السجل.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.success("تم إنشاء الملف بنجاح! اضغط على زر التنزيل أعلاه.")
        
    except Exception as e:
        st.error(f"حدث خطأ في معالجة الملف: {str(e)}")
        st.info("تأكد من أن الملف بنفس تنسيق المثال المرفق")

else:
    st.info("⬆️ يرجى رفع ملف السجل لبدء التحليل")
    
    # إضافة مثال توضيحي
    with st.expander("📋 مثال على تنسيق الملف المطلوب"):
        st.code("""
23.12.2024    19:06:26    Starting speed    ON
23.12.2024    19:06:56    Automatic mode    
23.12.2024    19:11:04    Thick spots    W0547
""", language="text")

# تعليمات التشغيل
with st.sidebar:
    st.markdown("### 🚀 كيفية التشغيل")
    st.markdown("""
    1. **تثبيت المتطلبات**:
    ```bash
    pip install streamlit pandas numpy matplotlib openpyxl
    ```
    
    2. **تشغيل التطبيق**:
    ```bash
    streamlit run app.py
    ```
    
    3. **رفع ملف السجل** عبر المتصفح
    
    ### 📊 المؤشرات المحسوبة:
    - **MTBF**: متوسط الوقت بين الأعطال
    - **MTTR**: متوسط وقت الإصلاح
    - **التوفر**: نسبة التشغيل
    - **توزيع الأحداث**: حسب النوع والوقت
    
    ### 📧 للدعم التقني:
    - تأكد من تثبيت المكتبات المطلوبة
    - تأكد من تنسيق الملف صحيح
    """)
    
