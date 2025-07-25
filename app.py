import streamlit as st
import pandas as pd
import os
import re
import random

# --- 기본 설정 및 데이터 로딩 ---

st.set_page_config(page_title="GNU 시간표 도우미", layout="wide")
st.title("👨‍💻 경상국립대학교 2025학년도 2학기 시간표 도우미")

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

    # '비고' 컬럼 추가 (엑셀 파일에 '비고' 열이 있어야 함)
    general_cols = ['교과목명', '교수명', '학점', '이수구분', '영역구분', '학과', '수강반번호', '강의시간/강의실', '캠퍼스구분', '교과목코드', '수업방법', '비고']
    major_cols = ['교과목명', '교수명', '학점', '이수구분', '학부(과)', '대상학년', '분반', '강의시간/강의실', '캠퍼스구분', '교과목코드', '수업방법', '비고']

    # 엑셀 파일에 해당 컬럼이 실제로 있는지 확인하고, 없으면 빈 값으로 처리
    # 이렇게 해야 '비고' 컬럼이 없어도 에러 없이 작동한다.
    for col in general_cols:
        if col not in df_general.columns:
            df_general[col] = ''
    for col in major_cols:
        if col not in df_major.columns:
            df_major[col] = ''


    df_general_p = df_general[general_cols].copy()
    df_general_p.rename(columns={'학과': '학부(과)', '수강반번호': '분반'}, inplace=True)
    df_general_p['type'] = '교양'

    df_major_p = df_major[major_cols].copy()
    df_major_p['type'] = '전공'

    df_combined = pd.concat([df_general_p, df_major_p], ignore_index=True).dropna(subset=['교과목코드', '분반'])
    df_combined[['대상학년', '영역구분']] = df_combined[['대상학년', '영역구분']].fillna('')
    # '비고' 컬럼도 NaN을 빈 문자열로 채워줘서 추후 출력 시 'nan'이 뜨는 것을 방지한다.
    df_combined['비고'] = df_combined['비고'].fillna('') 
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
    """
    전체 과목 목록과 현재 선택한 과목 코드를 받아,
    1. 이미 선택한 과목과 교과목코드가 같은 모든 과목(다른 분반 포함)
    2. 시간이 겹치는 과목
    을 제외하고 수강 가능한 과목 목록을 반환한다.
    """
    # 선택된 과목이 없으면 원본 데이터프레임을 그대로 반환.
    if not selected_codes:
        return df

    # 현재 내가 선택한 과목들의 시간 정보와 '교과목코드' 목록을 가져옴.
    my_timed_schedule = [t for code, no in selected_codes for t in df.loc[(df['교과목코드'] == code) & (df['분반'] == no), 'parsed_time'].iloc[0]]
    my_course_codes = {code for code, no in selected_codes}

    # 1. 이미 선택한 과목과 '교과목코드'가 같은 과목들을 먼저 제외시킴.
    #    df['교과목코드'].isin(my_course_codes)는 내가 선택한 코드와 같은 과목들을 True로 표시.
    #    '~' 연산자로 이를 뒤집어, 해당 과목들을 제외한 나머지 과목들만 True로 남김.
    available_mask = ~df['교과목코드'].isin(my_course_codes)

    # 2. 남은 과목들 중에서 시간이 겹치는 과목을 추가로 제외시킴.
    for t in my_timed_schedule:
        day, periods = t['day'], set(t['periods'])
        
        # 현재까지 선택 가능한 과목들(available_mask == True) 중에서,
        # 검사하려는 요일(day)에 수업이 있는 과목들의 인덱스를 찾음. (효율성)
        possible_conflicts_indices = df[available_mask & df['parsed_time'].apply(lambda pts: any(p['day'] == day for p in pts))].index

        # 해당 과목들을 하나씩 돌면서 실제로 시간이 겹치는지 최종 확인.
        for index in possible_conflicts_indices:
            # 과목의 parsed_time 리스트를 순회하며, 요일이 같고 교시가 하나라도 겹치는지 확인.
            # not set(p['periods']).isdisjoint(periods)는 두 집합에 공통 원소가 있는지 확인하는 효율적인 방법.
            if any(p['day'] == day and not set(p['periods']).isdisjoint(periods) for p in df.loc[index, 'parsed_time']):
                available_mask.loc[index] = False # 겹치면 선택 불가능(False) 처리.
    
    # 최종적으로 필터링된 마스크를 적용하여 수강 가능한 과목 목록을 반환.
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
    return f"hsl({random.randint(0, 360)}, 80%, 90%)"

def format_major_display_string(x):
    """전공 과목 선택 목록에 표시될 문자열을 포맷하는 함수"""
    # 전공 과목도 교양처럼 교수명, 분반, 학점 표시
    base_str = f"[{x['대상학년']}/{x['이수구분']}] {x['교과목명']} ({x['교수명']}, {x['분반']}반, {x['학점']}학점) / {format_time_for_display(x['parsed_time'])}"
    
    # 수업 방법이 '대면'/'혼합'을 포함하고, 캠퍼스구분 값이 실제로 존재할 경우에만 캠퍼스 정보 추가
    if ('대면' in x['수업방법'] or '혼합' in x['수업방법']) and pd.notna(x['캠퍼스구분']) and x['캠퍼스구분'].strip() != '':
        base_str = f"[{x['대상학년']}/{x['이수구분']}/{x['수업방법']}({x['캠퍼스구분']})] {x['교과목명']} ({x['교수명']}, {x['분반']}반, {x['학점']}학점) / {format_time_for_display(x['parsed_time'])}"
    else:
        # 비대면 등 캠퍼스 정보가 없는 경우
        base_str = f"[{x['대상학년']}/{x['이수구분']}/{x['수업방법']}] {x['교과목명']} ({x['교수명']}, {x['분반']}반, {x['학점']}학점) / {format_time_for_display(x['parsed_time'])}"
        
    # 비고 내용이 있다면 추가
    if pd.notna(x['비고']) and x['비고'].strip() != '':
        base_str += f" / 비고: {x['비고']}"
    return base_str

def format_general_display_string(x):
    """교양 과목 선택 목록에 표시될 문자열을 포맷하는 함수"""
    # 균형교양/핵심교양의 경우 영역 구분도 선택란에 뜨도록 수정
    # 캠퍼스는 수업(캠퍼스)로 되게끔 수정
    campus_info = ""
    if ('대면' in x['수업방법'] or '혼합' in x['수업방법']) and pd.notna(x['캠퍼스구분']) and x['캠퍼스구분'].strip() != '':
        campus_info = f"({x['캠퍼스구분']})"
    
    area_info = f"/{x['영역구분']}" if x['영역구분'] and x['영역구분'].strip() != '' else ""

    base_str = f"[{x['이수구분']}{area_info}/{x['수업방법']}{campus_info}] {x['교과목명']} ({x['교수명']}, {x['분반']}반, {x['학점']}학점) / {format_time_for_display(x['parsed_time'])}"

    # 비고 내용이 있다면 추가
    if pd.notna(x['비고']) and x['비고'].strip() != '':
        base_str += f" / 비고: {x['비고']}"
    return base_str

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
    
    with tab_major:
        majors_df = available_df[available_df['type'] == '전공']
        
        col1, col2, col3 = st.columns([0.5, 0.25, 0.25])
        
        with col1:
            department_options = sorted(majors_df['학부(과)'].dropna().unique().tolist())
            selected_depts = st.multiselect("전공 학부(과)", department_options, key="depts_multiselect")

        df_after_dept = majors_df
        if selected_depts:
            df_after_dept = majors_df[majors_df['학부(과)'].isin(selected_depts)]

        with col2:
            grade_options = sorted(
                df_after_dept['대상학년'].dropna().unique(),
                key=lambda x: int(re.search(r'\d+', str(x)).group()) if re.search(r'\d+', str(x)) else 99
            )
            selected_grade = st.selectbox("학년", ["전체"] + grade_options, key="grade_select")

        df_after_grade = df_after_dept
        if selected_grade != "전체":
            df_after_grade = df_after_dept[df_after_dept['대상학년'] == selected_grade]

        with col3:
            type_options = sorted(df_after_grade['이수구분'].dropna().unique().tolist())
            selected_course_type = st.selectbox("이수구분", ["전체"] + type_options, key="course_type_select")

        final_filtered_df = df_after_grade
        if selected_course_type != "전체":
            final_filtered_df = final_filtered_df[final_filtered_df['이수구분'] == selected_course_type]
        
        st.write("---")

        if not selected_depts:
            st.info("먼저 전공 학부(과)를 선택해주세요.")
        else:
            if not final_filtered_df.empty:
                temp_df = final_filtered_df.copy()
                temp_df['grade_num'] = temp_df['대상학년'].str.extract(r'(\d+)').astype(float).fillna(99)
                
                sorted_df = temp_df.sort_values(
                    by=['grade_num', '이수구분', '교과목명'],
                    ascending=[True, False, True]
                )
            else:
                sorted_df = final_filtered_df

            course_options = sorted_df.apply(format_major_display_string, axis=1).tolist()
            
            if not course_options:
                st.warning("선택한 조건에 현재 추가 가능한 전공 과목이 없습니다.")
            else:
                selected_course_str = st.selectbox("추가할 전공 과목 선택", course_options, key="major_select", label_visibility="collapsed")
                if st.button("전공 추가", key="add_major"):
                    selected_row = sorted_df[sorted_df.apply(format_major_display_string, axis=1) == selected_course_str].iloc[0]
                    code, no = selected_row['교과목코드'], selected_row['분반']
                    st.session_state.my_courses.append((code, no))
                    if selected_row['교과목명'] not in st.session_state.color_map:
                        st.session_state.color_map[selected_row['교과목명']] = generate_random_color()
                    st.success(f"'{selected_row['교과목명']}' 과목을 추가했습니다.")
                    st.rerun()

    with tab_general:
        general_df = available_df[available_df['type'] == '교양']
        
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            cat_options = sorted(general_df['이수구분'].dropna().unique().tolist())
            selected_cat = st.selectbox("이수구분", ["전체"] + cat_options, key="cat_select")

        df_after_cat = general_df
        if selected_cat != "전체":
            df_after_cat = general_df[general_df['이수구분'] == selected_cat]

        df_after_sub_cat = df_after_cat
        if selected_cat == '일반선택':
            with col2:
                sub_cat_options = ['전체', '꿈·미래개척', '그 외 일반선택']
                selected_sub_cat = st.selectbox("일반선택 세부 유형", sub_cat_options, key="sub_cat_select")
                if selected_sub_cat == '꿈·미래개척':
                    df_after_sub_cat = df_after_cat[df_after_cat['교과목명'] == '꿈·미래개척']
                elif selected_sub_cat == '그 외 일반선택':
                    df_after_sub_cat = df_after_cat[df_after_cat['교과목명'] != '꿈·미래개척']
        
        area_col, method_col = (col2, col3) if selected_cat != '일반선택' else (col3, col4)

        with area_col:
            area_options = sorted(df_after_sub_cat['영역구분'].dropna().unique().tolist())
            selected_area = st.selectbox("영역구분", ["전체"] + area_options, key="area_select")

        df_after_area = df_after_sub_cat
        if selected_area != "전체":
            df_after_area = df_after_sub_cat[df_after_sub_cat['영역구분'] == selected_area]

        with method_col:
            method_options = sorted(df_after_area['수업방법'].dropna().unique().tolist())
            selected_method = st.selectbox("수업방법", ["전체"] + method_options, key="method_select")

        final_filtered_gen_df = df_after_area
        if selected_method != "전체":
            final_filtered_gen_df = df_after_area[df_after_area['수업방법'] == selected_method]

        st.write("---")
        
        if not final_filtered_gen_df.empty: # DataFrame이 비어있지 않을 때만 정렬 및 apply 수행
            sorted_gen_df = final_filtered_gen_df.sort_values(
                by=['수업방법', '교과목명'], ascending=[False, True]
            )
            course_options_gen = sorted_gen_df.apply(format_general_display_string, axis=1).tolist()
        else: # DataFrame이 비어있으면 빈 리스트로 초기화
            sorted_gen_df = final_filtered_gen_df # 빈 DataFrame 유지
            course_options_gen = []
        
        if not course_options_gen:
            st.warning("해당 조건에 현재 추가 가능한 교양 과목이 없습니다.")
        else:
            selected_course_str_gen = st.selectbox("추가할 교양 과목 선택", course_options_gen, key="general_select", label_visibility="collapsed")
            if st.button("교양 추가", key="add_general"):
                selected_row = sorted_gen_df[sorted_gen_df.apply(format_general_display_string, axis=1) == selected_course_str_gen].iloc[0]
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
        my_courses_df = master_df[master_df.set_index(['교과목코드', '분반']).index.isin(st.session_state.my_courses)]
        
        # 1. 요일 목록 생성
        all_class_days = set()
        for _, course in my_courses_df.iterrows():
            for time_info in course['parsed_time']:
                all_class_days.add(time_info['day'])

        days_to_display = ['월', '화', '수', '목', '금']
        if '토' in all_class_days: days_to_display.append('토')
        if '일' in all_class_days: days_to_display.append('일')

        # 2. 최종 표시될 최대 교시 동적으로 계산
        default_max_period = 9 # 기본적으로 9교시까지 표시
        
        # 현재 선택된 과목들 중 가장 늦은 교시를 찾는다.
        all_periods = [p for _, course in my_courses_df.iterrows() for time_info in course['parsed_time'] for p in time_info['periods']]
        
        # 실제 데이터에 있는 최대 교시 (과목이 없다면 0)
        actual_max_period_in_data = max(all_periods) if all_periods else 0 
        
        # 최종적으로 시간표에 표시될 최대 교시는 기본값(9)과 실제 데이터의 최대 교시 중 더 큰 값으로 설정한다.
        final_display_max_period = max(default_max_period, actual_max_period_in_data)

        # 3. 최종 표시될 최대 교시에 맞춰 시간표 격자 생성
        timetable_data = {}
        for p in range(1, final_display_max_period + 1): # <-- final_display_max_period 사용
            for d in days_to_display:
                timetable_data[(p, d)] = {"content": "", "color": "white", "span": 1, "is_visible": True}

        # 4. 시간표에 과목 정보 채우기 (KeyError 방지 로직 포함)
        for _, course in my_courses_df.iterrows():
            if course['parsed_time']:
                color = st.session_state.color_map.get(course['교과목명'], "white")
                for time_info in course['parsed_time']:
                    if time_info['day'] not in days_to_display:
                        continue
                        
                    content = f"<b>{course['교과목명']}</b><br>{course['교수명']}<br>{time_info['room']}"
                    periods = sorted(time_info['periods'])
                    if not periods: continue
                    
                    start_period, block_len = periods[0], 1
                    for i in range(1, len(periods)):
                        if periods[i] == periods[i-1] + 1:
                            block_len += 1
                        else:
                            # 생성된 시간표 격자 안에 있는 키인지 확인 후 업데이트
                            if (start_period, time_info['day']) in timetable_data:
                                timetable_data[(start_period, time_info['day'])].update({"content": content, "color": color, "span": block_len})
                                for j in range(1, block_len): 
                                    if (start_period + j, time_info['day']) in timetable_data:
                                        timetable_data[(start_period + j, time_info['day'])]["is_visible"] = False
                            start_period, block_len = periods[i], 1
                    
                    # 마지막 시간 블록 처리
                    if (start_period, time_info['day']) in timetable_data:
                        timetable_data[(start_period, time_info['day'])].update({"content": content, "color": color, "span": block_len})
                        for j in range(1, block_len):
                            if (start_period + j, time_info['day']) in timetable_data:
                                timetable_data[(start_period + j, time_info['day'])]["is_visible"] = False

        day_col_width = (100 - 5 - 10) / len(days_to_display)
        html = f"""
        <style>
        .timetable {{ 
            width: 100%; 
            border-collapse: collapse; 
            table-layout: fixed; 
            border-bottom: 1px solid #e0e0e0;
        }}
        .timetable th, .timetable td {{ 
            border: 1px solid #e0e0e0; 
            text-align: center; 
            vertical-align: middle; 
            padding: 2px;
            height: 50px;
            font-size: 0.75em;
            overflow: hidden;
            text-overflow: ellipsis;
            word-break: keep-all;
        }}
        .timetable th {{ background-color: #f0f2f6; font-weight: bold; }}
        </style>
        <table class="timetable">
        <tr>
        <th width="5%">교시</th>
        <th width="10%">시간</th>
        """
        for d in days_to_display:
            html += f'<th width="{day_col_width}%">{d}</th>'
        html += '</tr>'

        time_map = {p: f"{p+8:02d}:00" for p in range(1, final_display_max_period + 1)}
        
        # 최종 표시될 최대 교시까지 반복하여 HTML 테이블 행 생성
        for p in range(1, final_display_max_period + 1): # <-- 이 부분을 final_display_max_period 사용
            html += '<tr>'
            html += f'<td>{p}</td><td>{time_map.get(p, "")}</td>'
            for d in days_to_display:
                cell = timetable_data.get((p, d))
                if cell and cell["is_visible"]:
                    html += f'<td rowspan="{cell["span"]}" style="background-color:{cell["color"]};">{cell["content"]}</td>'
            html += '</tr>'
        
        html += "</table>"
        
        total_credits = my_courses_df['학점'].sum()
        st.metric("총 신청 학점", f"{total_credits} 학점")
        
        # 최종 표시될 최대 교시에 맞춰 테이블 높이 조정
        table_height = (final_display_max_period * 55) + 60 # <-- final_display_max_period 사용
        st.components.v1.html(html, height=table_height, scrolling=True)

        untimed_courses = [course for _, course in my_courses_df.iterrows() if not course['parsed_time']]
        if untimed_courses:
            st.write("**[시간 미지정 과목]**")
            for course in untimed_courses: 
                # 시간 미지정 과목에도 비고 정보 추가
                remark_display = f" / 비고: {course['비고']}" if pd.notna(course['비고']) and course['비고'].strip() != '' else ''
                st.write(f"- [{course['수업방법']}] {course['교과목명']} ({course['교수명']}, {course['학점']}학점){remark_display}")
        st.write("---")
        st.write("**[선택한 과목 목록]**")
        for code, no in st.session_state.my_courses:
            course = master_df[(master_df['교과목코드'] == code) & (master_df['분반'] == no)].iloc[0]
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                # 전공/교양에 따라 기본 정보 문자열 생성
                # 수정된 부분: 아래 출력 형식은 이미 위에서 format_major_display_string, format_general_display_string으로 처리되므로,
                # 이 부분에서는 간단하게 과목명, 교수명, 학점, 분반, 수업방식(캠퍼스), 비고를 포함하도록 재구성
                
                # 수업방법 및 캠퍼스 정보 포맷팅
                method_campus_info = ""
                if pd.notna(course['수업방법']) and course['수업방법'].strip() != '':
                    if ('대면' in course['수업방법'] or '혼합' in course['수업방법']) and pd.notna(course['캠퍼스구분']) and course['캠퍼스구분'].strip() != '':
                        method_campus_info = f"[{course['수업방법']}({course['캠퍼스구분']})]"
                    else:
                        method_campus_info = f"[{course['수업방법']}]"

                # 영역구분 정보 (교양 과목일 경우에만)
                area_info = ""
                if course['type'] == '교양' and pd.notna(course['영역구분']) and course['영역구분'].strip() != '':
                    area_info = f"/{course['영역구분']}"

                # 이수구분 정보
                course_type_info = f"[{course['이수구분']}{area_info}]"

                # 비고 내용 추가
                remark_display_str = ""
                if pd.notna(course['비고']) and course['비고'].strip() != '':
                    remark_display_str = f" / **[비고: {course['비고']}]**"

                # 최종으로 화면에 표시될 문자열 생성
                display_str = (
                    f"- {course_type_info} {course['교과목명']} "
                    f"({course['교수명']}, {course['분반']}반, {course['학점']}학점) "
                    f"{method_campus_info}{remark_display_str}"
                )
                
                # 완성된 문자열을 출력
                st.write(display_str)
                st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; (교과목코드: {code}, 분반: {no})")
            with col2:
                if st.button("제거", key=f"del-{code}-{no}"):
                    st.session_state.my_courses.remove((code, no))
                    st.rerun()
