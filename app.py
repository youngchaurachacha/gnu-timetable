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
    # (이전과 동일)
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
            periods = sorted([int(p) for p in re.findall(r'\d+', re.sub(r'\[.*?\]', '', details))])
            if periods: parsed.append({'day': day, 'periods': periods, 'room': room})
        return parsed
    df_combined['parsed_time'] = df_combined['강의시간/강의실'].apply(parse_time)
    return df_combined

def get_available_courses(df, selected_codes):
    # (이전과 동일)
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
    # (이전과 동일)
    if not parsed_time: return "시간미지정"
    time_str_parts = [f"{t['day']}{','.join(map(str, t['periods']))}" for t in parsed_time]
    return " ".join(time_str_parts)

def generate_random_color():
    # (이전과 동일)
    return f"hsl({random.randint(0, 360)}, 80%, 90%)"

# --- 웹앱 UI 및 로직 ---

excel_file_path = '경상국립대학교 2025학년도 2학기 시간표.xlsx'
if not os.path.exists(excel_file_path):
    st.error(f"'{excel_file_path}' 파일을 찾을 수 없습니다. `app.py`와 같은 폴더에 엑셀 파일을 넣어주세요.")
    st.stop()

master_df = load_and_process_data(excel_file_path, '2학기 전공 시간표', '2학기 교양 시간표')

if master_df is not None:
    if 'my_courses' not in st.session_state: st.session_state.my_courses = []
    if 'color_map' not in st.session_state: st.session_state.color_map = {}

    available_df = get_available_courses(master_df, st.session_state.my_courses)

    st.subheader("1. 과목 선택")
    
    tab_major, tab_general = st.tabs(["🎓 전공 과목 선택", "📚 교양 과목 선택"])
    
    # --- 여기가 수정된 전공 탭 로직 ---
    with tab_major:
        majors_df = available_df[available_df['type'] == '전공']
        
        # --- 1. 필터 위젯 배치 ---
        col1, col2, col3 = st.columns([0.5, 0.25, 0.25])
        
        with col1:
            department_options = sorted(majors_df['학부(과)'].dropna().unique().tolist())
            selected_depts = st.multiselect("전공 학부(과)", department_options)

        # --- 2. 데이터 순차적 필터링 ---
        # 학부(과) 선택에 따라 필터링
        if selected_depts:
            filtered_df = majors_df[majors_df['학부(과)'].isin(selected_depts)]
        else:
            filtered_df = majors_df
        
        # 학년 필터 (선택된 학부(과) 내에서만 옵션 표시)
        with col2:
            grade_options = sorted(filtered_df['대상학년'].dropna().unique(), key=lambda x: int(re.search(r'\d+', str(x)).group()) if re.search(r'\d+', str(x)) else 0)
            selected_grade = st.selectbox("학년", ["전체"] + grade_options, key="grade_select")
        
        if selected_grade != "전체":
            filtered_df = filtered_df[filtered_df['대상학년'] == selected_grade]

        # 이수구분 필터 (위 필터들을 거친 결과 내에서만 옵션 표시)
        with col3:
            type_options = sorted(filtered_df['이수구분'].dropna().unique().tolist())
            selected_course_type = st.selectbox("이수구분", ["전체"] + type_options, key="course_type_select")

        if selected_course_type != "전체":
            filtered_df = filtered_df[filtered_df['이수구분'] == selected_course_type]
        
        st.write("---")

        # --- 3. 최종 결과 표시 ---
        if not selected_depts:
            st.info("먼저 전공 학부(과)를 선택해주세요.")
        else:
            course_options = filtered_df.apply(lambda x: f"[{x['대상학년']}/{x['이수구분']}/{x['수업방법']}] {x['교과목명']} ({x['교수명']}, {x['분반']}반) / {format_time_for_display(x['parsed_time'])}", axis=1).tolist()
            if not course_options:
                st.warning("선택한 조건에 현재 추가 가능한 전공 과목이 없습니다.")
            else:
                selected_course_str = st.selectbox("추가할 전공 과목 선택", course_options, key="major_select", label_visibility="collapsed")
                if st.button("전공 추가", key="add_major"):
                    selected_row = filtered_df[filtered_df.apply(lambda x: f"[{x['대상학년']}/{x['이수구분']}/{x['수업방법']}] {x['교과목명']} ({x['교수명']}, {x['분반']}반) / {format_time_for_display(x['parsed_time'])}", axis=1) == selected_course_str].iloc[0]
                    code, no = selected_row['교과목코드'], selected_row['분반']
                    st.session_state.my_courses.append((code, no))
                    if selected_row['교과목명'] not in st.session_state.color_map:
                        st.session_state.color_map[selected_row['교과목명']] = generate_random_color()
                    st.success(f"'{selected_row['교과목명']}' 과목을 추가했습니다.")
                    st.rerun()

    with tab_general:
        # (교양 탭 로직은 이전과 동일)
        general_df = available_df[available_df['type'] == '교양']
        filtered_gen_df = general_df.copy()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            categories = sorted(general_df['이수구분'].dropna().unique().tolist())
            selected_cat = st.selectbox("이수구분", ["전체"] + categories, key="cat_select")
            if selected_cat != "전체":
                filtered_gen_df = filtered_gen_df[filtered_gen_df['이수구분'] == selected_cat]
        area_col, method_col = (col2, col3) if selected_cat != '일반선택' else (col3, col4)
        if selected_cat == '일반선택':
            with col2:
                sub_cat_options = ['전체', '꿈·미래개척', '그 외 일반선택']
                selected_sub_cat = st.selectbox("일반선택 세부 유형", sub_cat_options, key="sub_cat_select")
                if selected_sub_cat == '꿈·미래개척':
                    filtered_gen_df = filtered_gen_df[filtered_gen_df['교과목명'] == '꿈·미래개척']
                elif selected_sub_cat == '그 외 일반선택':
                    filtered_gen_df = filtered_gen_df[filtered_gen_df['교과목명'] != '꿈·미래개척']
        with area_col:
            areas = sorted(filtered_gen_df['영역구분'].dropna().unique().tolist())
            if areas:
                selected_area = st.selectbox("영역구분", ["전체"] + areas, key="area_select")
                if selected_area != "전체":
                    filtered_gen_df = filtered_gen_df[filtered_gen_df['영역구분'] == selected_area]
        with method_col:
            methods = sorted(filtered_gen_df['수업방법'].dropna().unique().tolist())
            selected_method = st.selectbox("수업방법", ["전체"] + methods, key="method_select")
            if selected_method != "전체":
                filtered_gen_df = filtered_gen_df[filtered_gen_df['수업방법'] == selected_method]
        st.write("---")
        course_options_gen = filtered_gen_df.apply(lambda x: f"[{x['수업방법']}] {x['교과목명']} ({x['교수명']}, {x['분반']}반, {x['학점']}학점) / {format_time_for_display(x['parsed_time'])}", axis=1).tolist()
        if not course_options_gen:
            st.warning("해당 조건에 현재 추가 가능한 교양 과목이 없습니다.")
        else:
            selected_course_str_gen = st.selectbox("추가할 교양 과목 선택", course_options_gen, key="general_select", label_visibility="collapsed")
            if st.button("교양 추가", key="add_general"):
                selected_row = filtered_gen_df[filtered_gen_df.apply(lambda x: f"[{x['수업방법']}] {x['교과목명']} ({x['교수명']}, {x['분반']}반, {x['학점']}학점) / {format_time_for_display(x['parsed_time'])}", axis=1) == selected_course_str_gen].iloc[0]
                code, no = selected_row['교과목코드'], selected_row['분반']
                st.session_state.my_courses.append((code, no))
                if selected_row['교과목명'] not in st.session_state.color_map:
                    st.session_state.color_map[selected_row['교과목명']] = generate_random_color()
                st.success(f"'{selected_row['교과목명']}' 과목을 추가했습니다.")
                st.rerun()

    st.divider()
    st.subheader("2. 나의 시간표")

    if not st.session_state.my_courses:
        st.info("과목을 추가하면 시간표가 여기에 표시됩니다.")
    else:
        # (시간표 HTML 생성 및 표시는 이전과 동일)
        days = ['월', '화', '수', '목', '금', '토']
        my_courses_df = master_df[master_df.set_index(['교과목코드', '분반']).index.isin(st.session_state.my_courses)]
        timetable_data = {}
        for p in range(1, 13):
            for d in days:
                timetable_data[(p, d)] = {"content": "", "color": "white", "span": 1, "is_visible": True}
        for _, course in my_courses_df.iterrows():
            if course['parsed_time']:
                color = st.session_state.color_map.get(course['교과목명'], "white")
                for time_info in course['parsed_time']:
                    content = f"<b>{course['교과목명']}</b><br>{course['교수명']}<br>({time_info['room']})"
                    periods = sorted(time_info['periods'])
                    if not periods: continue
                    start_period, block_len = periods[0], 1
                    for i in range(1, len(periods)):
                        if periods[i] == periods[i-1] + 1:
                            block_len += 1
                        else:
                            timetable_data[(start_period, time_info['day'])].update({"content": content, "color": color, "span": block_len})
                            for j in range(1, block_len): 
                                if start_period + j <= 12: timetable_data[(start_period + j, time_info['day'])]["is_visible"] = False
                            start_period, block_len = periods[i], 1
                    timetable_data[(start_period, time_info['day'])].update({"content": content, "color": color, "span": block_len})
                    for j in range(1, block_len):
                        if start_period + j <= 12: timetable_data[(start_period + j, time_info['day'])]["is_visible"] = False
        html = """<style>.timetable { width: 100%; border-collapse: collapse; table-layout: fixed; }.timetable th, .timetable td { border: 1px solid #e0e0e0; text-align: center; vertical-align: middle; padding: 5px; height: 80px; font-size: 0.85em; }.timetable th { background-color: #f0f2f6; }</style><table class="timetable"><tr><th width="6%">교시</th><th width="12%">시간</th><th width="13.6%">월</th><th width="13.6%">화</th><th width="13.6%">수</th><th width="13.6%">목</th><th width="13.6%">금</th><th width="13.6%">토</th></tr>"""
        time_map = {p: f"{p+8:02d}:00" for p in range(1, 13)}
        for p in range(1, 13):
            if not any(timetable_data[(p, d)]["is_visible"] for d in days): continue
            html += '<tr>'
            html += f'<td>{p}</td><td>{time_map[p]}</td>'
            for d in days:
                cell = timetable_data[(p, d)]
                if cell["is_visible"]:
                    html += f'<td rowspan="{cell["span"]}" style="background-color:{cell["color"]};">{cell["content"]}</td>'
            html += '</tr>'
        html += "</table>"
        total_credits = my_courses_df['학점'].sum()
        st.metric("총 신청 학점", f"{total_credits} 학점")
        st.components.v1.html(html, height=1050, scrolling=True)
        untimed_courses = [course for _, course in my_courses_df.iterrows() if not course['parsed_time']]
        if untimed_courses:
            st.write("**[시간 미지정 과목]**")
            for course in untimed_courses: 
                st.write(f"- [{course['수업방법']}] {course['교과목명']} ({course['교수명']}, {course['학점']}학점)")
        st.write("---")
        st.write("**[선택한 과목 목록]**")
        for code, no in st.session_state.my_courses:
            course = master_df[(master_df['교과목코드'] == code) & (master_df['분반'] == no)].iloc[0]
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                grade_info = f"[{course['대상학년']}/{course['이수구분']}] " if course['type'] == '전공' else f"[{course['이수구분']}] "
                st.write(f"- {grade_info}{course['교과목명']} ({course['교수명']}) **[{course['수업방법']}]**")
                st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp; (교과목코드: {code}, 분반: {no})")
            with col2:
                if st.button("제거", key=f"del-{code}-{no}"):
                    st.session_state.my_courses.remove((code, no))
                    st.rerun()
