import streamlit as st
import pandas as pd
import os
import re
import random

# --- 기본 설정 및 데이터 로딩 ---

st.set_page_config(page_title="GNU 시간표 도우미", layout="wide")
st.title("👨‍💻 경상국립대학교 시간표 도우미")

@st.cache_data
def load_and_process_data(file_path, major_sheet, general_sheet):
    """
    원본 엑셀 파일에서 데이터를 읽고, 수업방식/영역구분 등 모든 정보를 포함하여 처리한다.
    """
    try:
        df_major = pd.read_excel(file_path, sheet_name=major_sheet)
        df_general = pd.read_excel(file_path, sheet_name=general_sheet)
    except Exception as e:
        st.error(f"엑셀 파일을 읽는 중 오류 발생: {e}")
        return None

    general_cols = ['교과목명', '교수명', '학점', '이수구분', '영역구분', '학과', '수강반번호', '강의시간/강의실', '캠퍼스구분', '교과목코드', '수업방법']
    major_cols = ['교과목명', '교수명', '학점', '이수구분', '학부(과)', '대상학년', '분반', '강의시간/강의실', '캠퍼스구분', '교과목코드', '수업방법']

    df_general_p = df_general[general_cols].copy()
    df_general_p.rename(columns={'학과': '학부(과)', '수강반번호': '분반'}, inplace=True)
    df_general_p['type'] = '교양'

    df_major_p = df_major[major_cols].copy()
    df_major_p['type'] = '전공'

    df_combined = pd.concat([df_general_p, df_major_p], ignore_index=True).dropna(subset=['교과목코드', '분반'])
    df_combined[['대상학년', '영역구분']] = df_combined[['대상학년', '영역구분']].fillna('')
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
            if periods: parsed.append({'day': day, 'periods': sorted(periods), 'room': room})
        return parsed

    df_combined['parsed_time'] = df_combined['강의시간/강의실'].apply(parse_time)
    return df_combined

def get_available_courses(df, selected_codes):
    """
    전체 과목 목록과 현재 선택한 과목 코드를 받아, 시간이 겹치지 않는 과목 목록을 반환한다.
    """
    my_timed_schedule = [t for code, no in selected_codes for t in df.loc[(df['교과목코드'] == code) & (df['분반'] == no), 'parsed_time'].iloc[0]]

    available_mask = df.index.to_series().astype(bool)
    selected_indices = df[df.set_index(['교과목코드', '분반']).index.isin(selected_codes)].index
    available_mask.loc[selected_indices] = False

    for t in my_timed_schedule:
        day, periods = t['day'], set(t['periods'])
        possible_conflicts = df[available_mask & (df['parsed_time'].apply(lambda pts: any(p['day'] == day for p in pts)))].index
        for index in possible_conflicts:
            if any(p['day'] == day and set(p['periods']) & periods for p in df.loc[index, 'parsed_time']):
                available_mask.loc[index] = False
    
    return df[available_mask]

def format_time_for_display(parsed_time):
    """시간 정보를 간결한 문자열로 변환 (예: '월1,2 수3')"""
    if not parsed_time:
        return "시간미지정"
    
    time_str_parts = []
    for time_info in parsed_time:
        day = time_info['day']
        periods = ",".join(map(str, time_info['periods']))
        time_str_parts.append(f"{day}{periods}")
    return " ".join(time_str_parts)

def generate_random_color():
    """랜덤으로 밝은 톤의 배경색 생성"""
    return f"hsl({random.randint(0, 360)}, 70%, 85%)"

# --- 웹앱 UI 및 로직 ---

excel_file_path = '경상국립대학교 2025학년도 2학기 시간표.xlsx'
if not os.path.exists(excel_file_path):
    st.error(f"'{excel_file_path}' 파일을 찾을 수 없습니다. `app.py`와 같은 폴더에 엑셀 파일을 넣어주세요.")
    st.stop()

master_df = load_and_process_data(excel_file_path, '2학기 전공 시간표', '2학기 교양 시간표')

if master_df is not None:
    if 'my_courses' not in st.session_state:
        st.session_state.my_courses = []
    if 'color_map' not in st.session_state:
        st.session_state.color_map = {}

    available_df = get_available_courses(master_df, st.session_state.my_courses)

    st.subheader("1. 과목 선택")
    
    tab_major, tab_general = st.tabs(["🎓 전공 과목 선택", "📚 교양 과목 선택"])

    with tab_major:
        majors_df = available_df[available_df['type'] == '전공']
        departments = sorted(majors_df['학부(과)'].dropna().unique().tolist())
        selected_depts = st.multiselect("전공 학부(과)를 모두 선택하세요.", departments)

        if selected_depts:
            filtered_df = majors_df[majors_df['학부(과)'].isin(selected_depts)]
            course_options = filtered_df.apply(lambda x: f"[{x['대상학년']}/{x['이수구분']}/{x['수업방법']}] {x['교과목명']} ({x['교수명']}, {x['분반']}반) / {format_time_for_display(x['parsed_time'])}", axis=1).tolist()
            
            if not course_options:
                st.warning("선택한 학부에 현재 추가 가능한 전공 과목이 없습니다.")
            else:
                selected_course_str = st.selectbox("추가할 전공 과목 선택", course_options, key="major_select")
                if st.button("전공 추가", key="add_major"):
                    selected_row = filtered_df[filtered_df.apply(lambda x: f"[{x['대상학년']}/{x['이수구분']}/{x['수업방법']}] {x['교과목명']} ({x['교수명']}, {x['분반']}반) / {format_time_for_display(x['parsed_time'])}", axis=1) == selected_course_str].iloc[0]
                    code, no = selected_row['교과목코드'], selected_row['분반']
                    st.session_state.my_courses.append((code, no))
                    # --- 여기가 수정됨: 'course' -> 'selected_row' ---
                    if selected_row['교과목명'] not in st.session_state.color_map:
                         st.session_state.color_map[selected_row['교과목명']] = generate_random_color()
                    st.success(f"'{selected_row['교과목명']}' 과목을 추가했습니다.")
                    st.rerun()

    with tab_general:
        general_df = available_df[available_df['type'] == '교양']
        categories = sorted(general_df['이수구분'].dropna().unique().tolist())
        selected_cat = st.selectbox("교양 이수구분을 선택하세요.", categories, key="cat_select")

        if selected_cat:
            df_by_cat = general_df[general_df['이수구분'] == selected_cat]
            areas = sorted(df_by_cat['영역구분'].dropna().unique().tolist())
            selected_area = st.selectbox("영역구분을 선택하세요.", ["전체"] + areas, key="area_select")
            
            filtered_gen_df = df_by_cat if selected_area == "전체" else df_by_cat[df_by_cat['영역구분'] == selected_area]
            
            course_options_gen = filtered_gen_df.apply(lambda x: f"[{x['수업방법']}] {x['교과목명']} ({x['교수명']}, {x['분반']}반, {x['학점']}학점) / {format_time_for_display(x['parsed_time'])}", axis=1).tolist()

            if not course_options_gen:
                st.warning("해당 조건에 현재 추가 가능한 교양 과목이 없습니다.")
            else:
                selected_course_str_gen = st.selectbox("추가할 교양 과목 선택", course_options_gen, key="general_select")
                if st.button("교양 추가", key="add_general"):
                    selected_row = filtered_gen_df[filtered_gen_df.apply(lambda x: f"[{x['수업방법']}] {x['교과목명']} ({x['교수명']}, {x['분반']}반, {x['학점']}학점) / {format_time_for_display(x['parsed_time'])}", axis=1) == selected_course_str_gen].iloc[0]
                    code, no = selected_row['교과목코드'], selected_row['분반']
                    st.session_state.my_courses.append((code, no))
                    # --- 여기가 수정됨: 'course' -> 'selected_row' ---
                    if selected_row['교과목명'] not in st.session_state.color_map:
                         st.session_state.color_map[selected_row['교과목명']] = generate_random_color()
                    st.success(f"'{selected_row['교과목명']}' 과목을 추가했습니다.")
                    st.rerun()

    st.divider()
    st.subheader("2. 나의 시간표")

    if not st.session_state.my_courses:
        st.info("과목을 추가하면 시간표가 여기에 표시됩니다.")
    else:
        days = ['월', '화', '수', '목', '금', '토']
        html = """<style>.timetable { width: 100%; border-collapse: collapse; }.timetable th, .timetable td { border: 1px solid #e0e0e0; text-align: center; vertical-align: middle; padding: 2px; font-size: 0.8em; }.timetable th { background-color: #f0f2f6; }.row-3 { height: 2.2em; }</style><table class="timetable"><tr><th>교시</th><th>시간</th><th>월</th><th>화</th><th>수</th><th>목</th><th>금</th><th>토</th></tr>"""
        
        timetable_data = { (p, d): {"name": "", "prof": "", "room": "", "color": "white"} for p in range(1, 13) for d in days }
        my_courses_df = master_df[master_df.set_index(['교과목코드', '분반']).index.isin(st.session_state.my_courses)]
        untimed_courses = []

        for _, course_row in my_courses_df.iterrows():
            if course_row['parsed_time']:
                color = st.session_state.color_map.get(course_row['교과목명'], "white")
                for time_info in course_row['parsed_time']:
                    for p in time_info['periods']:
                        if time_info['day'] in days and p in range(1, 13):
                            timetable_data[(p, time_info['day'])] = {"name": course_row['교과목명'], "prof": course_row['교수명'], "room": time_info['room'], "color": color}
            else:
                untimed_courses.append(course_row)
        
        time_map = {p: f"{p+8:02d}:00~{p+8:02d}:50" for p in range(1, 13)}

        for p in range(1, 13):
            html += f'<tr><td rowspan="3">{p}</td><td rowspan="3">{time_map[p]}</td>'
            for d in days: html += f'<td style="background-color:{timetable_data[(p,d)]["color"]};">{timetable_data[(p,d)]["name"]}</td>'
            html += '</tr><tr>'
            for d in days: html += f'<td style="background-color:{timetable_data[(p,d)]["color"]};">{timetable_data[(p,d)]["prof"]}</td>'
            html += '</tr><tr>'
            for d in days: html += f'<td style="background-color:{timetable_data[(p,d)]["color"]};">{timetable_data[(p,d)]["room"]}</td>'
            html += '</tr>'
        
        html += "</table>"
        
        total_credits = my_courses_df['학점'].sum()
        st.metric("총 신청 학점", f"{total_credits} 학점")
        st.components.v1.html(html, height=1000, scrolling=True)

        if untimed_courses:
            st.write("**[시간 미지정 과목]**")
            for _, course_row in pd.DataFrame(untimed_courses).iterrows(): 
                st.write(f"- [{course_row['수업방법']}] {course_row['교과목명']} ({course_row['교수명']}, {course_row['학점']}학점)")

        st.write("---")
        st.write("**[선택한 과목 목록]**")
        for code, no in st.session_state.my_courses:
            course_row = master_df[(master_df['교과목코드'] == code) & (master_df['분반'] == no)].iloc[0]
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                grade_info = f"[{course_row['대상학년']}/{course_row['이수구분']}] " if course_row['type'] == '전공' else f"[{course_row['이수구분']}] "
                st.write(f"- {grade_info}{course_row['교과목명']} ({course_row['교수명']}) **[{course_row['수업방법']}]**")
                st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp; (교과목코드: {code}, 분반: {no})")
            with col2:
                if st.button("제거", key=f"del-{code}-{no}"):
                    st.session_state.my_courses.remove((code, no))
                    st.rerun()
