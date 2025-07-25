import streamlit as st
import pandas as pd
import os
import re

# --- 기본 설정 및 데이터 로딩 ---

st.set_page_config(page_title="GNU 시간표 도우미", layout="wide")
st.title("👨‍💻 경상국립대학교 시간표 도우미")

@st.cache_data
def load_and_process_data(file_path, major_sheet, general_sheet):
    """
    원본 엑셀 파일에서 데이터를 읽고, 학년 정보를 포함하여 처리한다.
    """
    try:
        df_major = pd.read_excel(file_path, sheet_name=major_sheet)
        df_general = pd.read_excel(file_path, sheet_name=general_sheet)
    except Exception as e:
        st.error(f"엑셀 파일을 읽는 중 오류 발생: {e}")
        return None

    # 교양 과목 처리
    df_general_p = df_general[['교과목명', '교수명', '학점', '이수구분', '학과', '수강반번호', '강의시간/강의실', '캠퍼스구분', '교과목코드']].copy()
    df_general_p.rename(columns={'학과': '학부(과)', '수강반번호': '분반'}, inplace=True)
    df_general_p['type'] = '교양'

    # 전공 과목 처리 (대상학년 컬럼 추가)
    df_major_p = df_major[['교과목명', '교수명', '학점', '이수구분', '학부(과)', '대상학년', '분반', '강의시간/강의실', '캠퍼스구분', '교과목코드']].copy()
    df_major_p['type'] = '전공'

    df_combined = pd.concat([df_general_p, df_major_p], ignore_index=True).dropna(subset=['교과목코드', '분반'])
    df_combined['대상학년'] = df_combined['대상학년'].fillna('') # 교양 과목의 빈 학년 정보 처리
    df_combined['교과목코드'] = df_combined['교과목코드'].astype(int)
    df_combined['분반'] = df_combined['분반'].astype(int)
    
    def parse_time(time_str):
        if not isinstance(time_str, str): return []
        parsed = []
        pattern = r'([월화수목금토일])([^월화수목금토일]*)'
        matches = re.finditer(pattern, time_str)
        for match in matches:
            day, details = match.group(1), match.group(2)
            room = (re.search(r'\[(.*?)\]', details).group(1) if re.search(r'\[(.*?)\]', details) else '')
            periods = [int(p) for p in re.findall(r'\d+', re.sub(r'\[.*?\]', '', details))]
            if periods: parsed.append({'day': day, 'periods': periods, 'room': room})
        return parsed

    df_combined['parsed_time'] = df_combined['강의시간/강의실'].apply(parse_time)
    return df_combined

def check_conflict(df, current_codes, new_code, new_no):
    new_course = df[(df['교과목코드'] == new_code) & (df['분반'] == new_no)].iloc[0]
    if not new_course['parsed_time']: return None
    for code, no in current_codes:
        existing_course = df[(df['교과목코드'] == code) & (df['분반'] == no)].iloc[0]
        if not existing_course['parsed_time']: continue
        for new_time in new_course['parsed_time']:
            for existing_time in existing_course['parsed_time']:
                if new_time['day'] == existing_time['day'] and set(new_time['periods']) & set(existing_time['periods']):
                    return existing_course['교과목명']
    return None

# --- 웹앱 UI 및 로직 ---

excel_file_path = '경상국립대학교 2025학년도 2학기 시간표.xlsx'
if not os.path.exists(excel_file_path):
    st.error(f"'{excel_file_path}' 파일을 찾을 수 없습니다. `app.py`와 같은 폴더에 엑셀 파일을 넣어주세요.")
    st.stop()

master_df = load_and_process_data(excel_file_path, '2학기 전공 시간표', '2학기 교양 시간표')

if master_df is not None:
    if 'my_courses' not in st.session_state:
        st.session_state.my_courses = []

    st.subheader("1. 과목 선택")
    
    tab_major, tab_general = st.tabs(["🎓 전공 과목 선택", "📚 교양 과목 선택"])

    with tab_major:
        majors_df = master_df[master_df['type'] == '전공']
        departments = sorted(majors_df['학부(과)'].dropna().unique().tolist())
        selected_depts = st.multiselect("전공 학부(과)를 모두 선택하세요.", departments)

        if selected_depts:
            filtered_df = majors_df[majors_df['학부(과)'].isin(selected_depts)]
            course_options = filtered_df.apply(lambda x: f"[{x['대상학년']}] {x['교과목명']} ({x['교수명']}, {x['분반']}반)", axis=1).tolist()
            selected_course_str = st.selectbox("추가할 전공 과목 선택", course_options, key="major_select")
            
            if st.button("전공 추가", key="add_major"):
                selected_row = filtered_df[filtered_df.apply(lambda x: f"[{x['대상학년']}] {x['교과목명']} ({x['교수명']}, {x['분반']}반)", axis=1) == selected_course_str].iloc[0]
                code, no = selected_row['교과목코드'], selected_row['분반']
                if (code, no) in st.session_state.my_courses:
                    st.warning("이미 추가된 과목입니다.")
                else:
                    conflict = check_conflict(master_df, st.session_state.my_courses, code, no)
                    if conflict:
                        st.error(f"시간 충돌: '{selected_row['교과목명']}'이(가) '{conflict}' 과목과 겹칩니다.")
                    else:
                        st.session_state.my_courses.append((code, no))
                        st.success(f"'{selected_row['교과목명']}' 과목을 추가했습니다.")
        else:
            st.info("먼저 전공 학부(과)를 선택해주세요.")

    with tab_general:
        general_df = master_df[master_df['type'] == '교양']
        course_options_gen = general_df.apply(lambda x: f"{x['교과목명']} ({x['교수명']}, {x['분반']}반, {x['학점']}학점)", axis=1).tolist()
        selected_course_str_gen = st.selectbox("추가할 교양 과목 선택", course_options_gen, key="general_select")

        if st.button("교양 추가", key="add_general"):
            selected_row = general_df[general_df.apply(lambda x: f"{x['교과목명']} ({x['교수명']}, {x['분반']}반, {x['학점']}학점)", axis=1) == selected_course_str_gen].iloc[0]
            code, no = selected_row['교과목코드'], selected_row['분반']
            if (code, no) in st.session_state.my_courses:
                st.warning("이미 추가된 과목입니다.")
            else:
                conflict = check_conflict(master_df, st.session_state.my_courses, code, no)
                if conflict:
                    st.error(f"시간 충돌: '{selected_row['교과목명']}'이(가) '{conflict}' 과목과 겹칩니다.")
                else:
                    st.session_state.my_courses.append((code, no))
                    st.success(f"'{selected_row['교과목명']}' 과목을 추가했습니다.")

    st.divider()
    st.subheader("2. 나의 시간표")

    if not st.session_state.my_courses:
        st.info("과목을 추가하면 시간표가 여기에 표시됩니다.")
    else:
        days = ['월', '화', '수', '목', '금', '토']
        timetable = pd.DataFrame(index=pd.MultiIndex.from_product([range(1, 13), ['과목명', '교수명', '강의실']]), columns=days).fillna('')
        untimed_courses = []
        my_courses_df = master_df[master_df.set_index(['교과목코드', '분반']).index.isin(st.session_state.my_courses)]
        
        for _, course in my_courses_df.iterrows():
            if course['parsed_time']:
                for time_info in course['parsed_time']:
                    for p in time_info['periods']:
                        if time_info['day'] in days and p in range(1, 13):
                            timetable.loc[(p, '과목명'), time_info['day']] = course['교과목명']
                            timetable.loc[(p, '교수명'), time_info['day']] = course['교수명']
                            timetable.loc[(p, '강의실'), time_info['day']] = time_info['room']
            else:
                untimed_courses.append(f"{course['교과목명']} ({course['교수명']}, {course['학점']}학점)")

        total_credits = my_courses_df['학점'].sum()
        st.metric("총 신청 학점", f"{total_credits} 학점")
        
        st.dataframe(timetable, height=1200)

        if untimed_courses:
            st.write("**[시간 미지정 과목]**")
            for uc in untimed_courses: st.write(f"- {uc}")

        st.write("---")
        st.write("**[선택한 과목 목록]**")
        for code, no in st.session_state.my_courses:
            course = master_df[(master_df['교과목코드'] == code) & (master_df['분반'] == no)].iloc[0]
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                grade_info = f"[{course['대상학년']}] " if course['type'] == '전공' else ""
                st.write(f"- {grade_info}{course['교과목명']} ({course['교수명']}, {course['분반']}반) [{course['type']}]")
            with col2:
                if st.button("제거", key=f"del-{code}-{no}"):
                    st.session_state.my_courses.remove((code, no))
                    st.rerun()
