import streamlit as st
import pandas as pd
import os
import re
import random
from io import BytesIO

# --- 기본 설정 및 데이터 로딩 ---

st.set_page_config(page_title="GNU 시간표 도우미", layout="wide")
st.title("👨‍💻 경상국립대학교 2025학년도 2학기 시간표 도우미")

# README 내용을 앱 UI에 통합
st.markdown("""
📂 **[2025학년도 2학기 시간표 엑셀 파일 다운로드](https://github.com/youngchaurachacha/gnu-timetable/raw/refs/heads/main/%EA%B2%BD%EC%83%81%EA%B5%AD%EB%A6%BD%EB%8C%80%ED%95%99%EA%B5%90%202025%ED%95%99%EB%85%84%EB%8F%84%202%ED%95%99%EA%B8%B0%20%EC%8B%9C%EA%B0%84%ED%91%9C.xlsx)**
""")

with st.expander("✨ 주요 기능 및 사용 안내 (클릭하여 확인)"):
    st.markdown("""
    ### ⚠️ 중요 알림
    * **데이터 출처:** 본 시간표 정보는  [경상국립대학교 학사공지](https://www.gnu.ac.kr/main/na/ntt/selectNttInfo.do?mi=1127&bbsId=1029&nttSn=2547228)에 최초 공지된 PDF 파일을 기반으로 합니다.
    * **변동 가능성:** 학사 운영상 수업 시간표는 변경될 수 있습니다. **수강 신청 전 반드시 [통합 서비스](https://my.gnu.ac.kr)에서 최종 시간표를 확인**하시기 바랍니다.
    * **책임 한계:** 본 도우미를 통해 발생할 수 있는 시간표 오류나 수강 신청 불이익에 대해 개발자는 책임을 지지 않습니다.

    ---

    ### ✨ 주요 기능
    * **실시간 시간표 확인:** 2025학년도 2학기 모든 개설 강좌 정보를 필터링하며 확인합니다.
    * **나만의 시간표 구성:** 원하는 과목을 추가하여 개인 시간표를 시각적으로 구성하고, 색각 이상자를 고려한 선명한 색상으로 과목을 자동 구분합니다.
    * **자동 중복 검사 (핵심 기능 💡)**
        * **과목 중복 방지:** 이미 추가한 과목과 동일한 교과목코드의 다른 분반은 목록에서 자동 제외됩니다.
        * **시간 중복 방지:** 현재 시간표와 시간이 겹치는 모든 과목이 목록에서 자동 제외되어, 충돌 없는 시간표를 손쉽게 만들 수 있습니다.
    * **시간표 이미지 저장 🖼️:** 완성된 시간표를 깔끔한 이미지 파일(.png)로 다운로드하여 저장하거나 공유할 수 있습니다.
    * **편의 기능**
        * **동적 시간표 확장:** 토/일 수업이나 0교시, 야간 수업 추가 시 시간표 범위가 자동으로 확장됩니다.
        * **학점 자동 계산:** 선택한 과목들의 총 학점을 실시간으로 보여줍니다.
        * **전체 초기화:** 버튼 하나로 선택한 모든 과목을 삭제하고 처음부터 다시 시작할 수 있습니다.
        * **상세 정보 제공:** 과목명, 교수명, 분반, 학점, 수업 방식, 캠퍼스, 강의실, 원격 수업 방식, 비고 등 모든 정보를 한눈에 볼 수 있습니다.

    """)

# --- 색상 팔레트 (색각 이상자 고려, 명확히 구분되는 색상) ---
PREDEFINED_COLORS = [
    "#8dd3c7", "#ffffb3", "#bebada", "#fb8072", "#80b1d3", "#fdb462",
    "#b3de69", "#fccde5", "#d9d9d9", "#bc80bd", "#ccebc5", "#ffed6f"
]

@st.cache_data
def load_and_process_data(file_path, major_sheet, general_sheet):
    """
    원본 엑셀 파일에서 데이터를 읽고, 수업방식/영역구분 등 모든 정보를 포함하여 처리한다.
    (최적화) 각 과목의 모든 시간 슬롯을 미리 집합(set)으로 계산하여 'time_slots_set' 컬럼에 저장한다.
    """
    try:
        df_major = pd.read_excel(file_path, sheet_name=major_sheet)
        df_general = pd.read_excel(file_path, sheet_name=general_sheet)
    except Exception as e:
        st.error(f"엑셀 파일을 읽는 중 오류 발생: {e}")
        return None

    general_cols = ['교과목명', '교수명', '학점', '이수구분', '영역구분', '학과', '수강반번호', '강의시간/강의실', '캠퍼스구분', '교과목코드', '수업방법', '비고', '원격강의구분']
    major_cols = ['교과목명', '교수명', '학점', '이수구분', '학부(과)', '대상학년', '분반', '강의시간/강의실', '캠퍼스구분', '교과목코드', '수업방법', '비고', '원격강의구분']

    for col in general_cols:
        if col not in df_general.columns: df_general[col] = ''
    for col in major_cols:
        if col not in df_major.columns: df_major[col] = ''

    df_general_p = df_general[general_cols].copy()
    df_general_p.rename(columns={'학과': '학부(과)', '수강반번호': '분반'}, inplace=True)
    df_general_p['type'] = '교양'

    df_major_p = df_major[major_cols].copy()
    df_major_p['type'] = '전공'

    df_combined = pd.concat([df_general_p, df_major_p], ignore_index=True).dropna(subset=['교과목코드', '분반'])
    df_combined[['대상학년', '영역구분', '비고', '원격강의구분', '수업방법']] = df_combined[['대상학년', '영역구분', '비고', '원격강의구분', '수업방법']].fillna('')
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
    
    # 각 과목의 (요일, 교시) 튜플을 set으로 미리 만들어 저장한다.
    def create_time_slots_set(parsed_time_list):
        slots = set()
        if not isinstance(parsed_time_list, list): return slots
        for time_info in parsed_time_list:
            for period in time_info['periods']:
                slots.add((time_info['day'], period))
        return slots
    
    # 이 연산은 앱 로딩 시 한번만 실행된다.
    df_combined['time_slots_set'] = df_combined['parsed_time'].apply(create_time_slots_set)
    
    return df_combined

def get_available_courses(df, selected_codes):
    """
    (최적화된 버전) 선택된 과목 리스트를 기반으로 수강 가능한 과목 목록을 필터링한다.
    1. 동일 교과목코드 과목을 먼저 제외한다.
    2. 선택된 과목들의 모든 시간 슬롯을 하나의 큰 집합(my_busy_slots)으로 만든다.
    3. 전체 과목을 순회하며 각 과목의 시간 집합이 my_busy_slots과 겹치는지(isdisjoint) 확인한다.
    """
    if not selected_codes:
        return df

    # 1. 이미 선택한 '교과목코드'가 같은 과목들은 목록에서 제외
    my_course_codes = {code for code, no in selected_codes}
    available_df = df[~df['교과목코드'].isin(my_course_codes)]

    # 2. 내가 선택한 과목들이 차지하는 모든 시간 슬롯을 하나의 집합으로 통합
    my_courses_df = df[df.set_index(['교과목코드', '분반']).index.isin(selected_codes)]
    my_busy_slots = set().union(*my_courses_df['time_slots_set'])
    
    # 선택한 과목 중에 시간이 지정된 과목이 없으면 시간 필터링 불필요
    if not my_busy_slots:
        return available_df

    # 3. 남은 과목들 중, 나의 '바쁜 시간'과 겹치지 않는 과목만 최종 선택
    #    set.isdisjoint()는 두 집합이 겹치지 않으면 True를 반환. list 순회보다 훨씬 빠르다.
    is_available_time = available_df['time_slots_set'].apply(lambda course_slots: course_slots.isdisjoint(my_busy_slots))
    
    return available_df[is_available_time]

def format_display_string(x):
    """(통합 버전) 과목의 시리즈(행)를 받아 전공/교양에 맞춰 UI에 표시할 문자열을 생성한다."""
    # 공통 정보 구성
    method_campus_info = ""
    if pd.notna(x['수업방법']) and x['수업방법'].strip() != '':
        if ('대면' in x['수업방법'] or '혼합' in x['수업방법']) and pd.notna(x['캠퍼스구분']) and x['캠퍼스구분'].strip() != '':
            method_campus_info = f"/{x['수업방법']}({x['캠퍼스구분']})"
        else:
            method_campus_info = f"/{x['수업방법']}"
    
    remote_info = ""
    if ('비대면' in x['수업방법'] or '혼합' in x['수업방법']) and pd.notna(x['원격강의구분']) and x['원격강의구분'].strip() != '':
        remote_info = f"({x['원격강의구분']})"

    formatted_bunban = f"{int(x['분반']):03d}"
    formatted_hakjeom = f"{int(x['학점'])}학점" if x['학점'] == int(x['학점']) else f"{x['학점']}학점"
    time_display = x['강의시간/강의실'] if pd.notna(x['강의시간/강의실']) else "시간미지정"
    
    # 타입에 따른 분기 처리
    if x['type'] == '전공':
        type_specific_info = f"[{x['대상학년']}/{x['이수구분']}"
    else:  # '교양'
        area_info = f"/{x['영역구분']}" if pd.notna(x['영역구분']) and x['영역구분'].strip() else ""
        type_specific_info = f"[{x['이수구분']}{area_info}"
        
    # 최종 문자열 조합
    base_str = (f"{type_specific_info}{method_campus_info}{remote_info}] "
                f"{x['교과목명']} ({x['교수명']}, {formatted_bunban}반, {formatted_hakjeom}) / {time_display}")
    
    if pd.notna(x['비고']) and x['비고'].strip() != '':
        base_str += f" / 비고: {x['비고']}"
        
    return base_str

def format_list_item_string(x):
    method_campus_info = ""
    if pd.notna(x['수업방법']) and x['수업방법'].strip() != '':
        if ('대면' in x['수업방법'] or '혼합' in x['수업방법']) and pd.notna(x['캠퍼스구분']) and x['캠퍼스구분'].strip() != '':
            method_campus_info = f"/{x['수업방법']}({x['캠퍼스구분']})"
        else:
            method_campus_info = f"/{x['수업방법']}"

    remote_info = ""
    if ('비대면' in x['수업방법'] or '혼합' in x['수업방법']) and pd.notna(x['원격강의구분']) and x['원격강의구분'].strip() != '':
        remote_info = f"({x['원격강의구분']})"

    # formatted_bunban = f"{int(x['분반']):03d}" # 여기서는 제거
    # formatted_hakjeom = f"{int(x['학점'])}학점" if x['학점'] == int(x['학점']) else f"{x['학점']}학점" # 여기서는 제거

    time_display = x['강의시간/강의실'] if pd.notna(x['강의시간/강의실']) else "시간미지정"

    if x['type'] == '전공':
        type_specific_info = f"[{x['대상학년']}/{x['이수구분']}"
    else:
        area_info = f"/{x['영역구분']}" if pd.notna(x['영역구분']) and x['영역구분'].strip() else ""
        type_specific_info = f"[{x['이수구분']}{area_info}"

    # 이 부분에서 분반과 학점을 제외
    base_str = (f"{type_specific_info}{method_campus_info}{remote_info}] "
                f"{x['교과목명']} ({x['교수명']}) / {time_display}")

    if pd.notna(x['비고']) and x['비고'].strip() != '':
        base_str += f" / 비고: {x['비고']}"

    return base_str

def add_course_to_timetable(course_row):
    """선택된 과목(row)을 세션에 추가하고, 색상을 할당한 뒤 앱을 새로고침한다."""
    code, no = course_row['교과목코드'], course_row['분반']
    
    # 이미 추가된 과목인지 확인 (필수는 아니지만, 사용자 편의성을 위해 추가 가능)
    if (code, no) in st.session_state.my_courses:
        st.warning(f"'{course_row['교과목명']}' 과목은 이미 목록에 있습니다.")
        return

    st.session_state.my_courses.append((code, no))
    
    # 색상 맵에 과목명 없으면 새 색상 할당
    if course_row['교과목명'] not in st.session_state.color_map:
        next_color_index = len(st.session_state.color_map) % len(PREDEFINED_COLORS)
        st.session_state.color_map[course_row['교과목명']] = PREDEFINED_COLORS[next_color_index]
        
    st.success(f"'{course_row['교과목명']}' 과목을 추가했습니다.")
    st.rerun()

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
        # 필터링의 기반이 될 데이터프레임 정의
        all_majors_df = master_df[master_df['type'] == '전공']
        majors_df_to_display = available_df[available_df['type'] == '전공']
        
        # --- 1. 필터 위젯 배치 및 사용자 선택값 받기 ---
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            department_options = sorted(all_majors_df['학부(과)'].dropna().unique().tolist())
            selected_depts = st.multiselect("전공 학부(과)", department_options, key="depts_multiselect")

        # 사용자의 선택에 따라 다음 필터들의 '옵션'을 동적으로 만들기 위한 데이터프레임
        options_df = all_majors_df[all_majors_df['학부(과)'].isin(selected_depts)] if selected_depts else all_majors_df

        with col2:
            grade_options = sorted(options_df['대상학년'].dropna().unique(), key=lambda x: int(re.search(r'\d+', str(x)).group()) if re.search(r'\d+', str(x)) else 99)
            selected_grade = st.selectbox("학년", ["전체"] + grade_options, key="grade_select")

        if selected_grade != "전체":
            options_df = options_df[options_df['대상학년'] == selected_grade]

        with col3:
            type_options = sorted(options_df['이수구분'].dropna().unique().tolist())
            selected_course_type = st.selectbox("이수구분", ["전체"] + type_options, key="course_type_select")

        if selected_course_type != "전체":
            options_df = options_df[options_df['이수구분'] == selected_course_type]

        with col4:
            major_campus_options = sorted(options_df['캠퍼스구분'].dropna().unique().tolist())
            selected_major_campus = st.selectbox("캠퍼스", ["전체"] + major_campus_options, key="major_campus_select")

        # --- 2. 모든 필터 값을 사용해 최종 데이터 필터링 (간소화된 부분) ---
        # 하나의 변수(final_filtered_df)를 계속해서 필터링
        final_filtered_df = majors_df_to_display.copy() # 원본은 건드리지 않도록 복사
        if selected_depts:
            final_filtered_df = final_filtered_df[final_filtered_df['학부(과)'].isin(selected_depts)]
        if selected_grade != "전체":
            final_filtered_df = final_filtered_df[final_filtered_df['대상학년'] == selected_grade]
        if selected_course_type != "전체":
            final_filtered_df = final_filtered_df[final_filtered_df['이수구분'] == selected_course_type]
        if selected_major_campus != "전체":
            final_filtered_df = final_filtered_df[final_filtered_df['캠퍼스구분'] == selected_major_campus]

        st.write("---")

        if not selected_depts:
            st.info("먼저 전공 학부(과)를 선택해주세요.")
        else:
            sorted_df = pd.DataFrame(columns=final_filtered_df.columns)
            if not final_filtered_df.empty:
                temp_df = final_filtered_df.copy()
                temp_df['grade_num'] = temp_df['대상학년'].str.extract(r'(\d+)').astype(float).fillna(99)
                sorted_df = temp_df.sort_values(by=['grade_num', '이수구분', '교과목명'], ascending=[True, False, True])
            
            course_options = sorted_df.apply(format_display_string, axis=1).tolist() if not sorted_df.empty else []
            
            if not course_options:
                st.warning("선택한 조건에 현재 추가 가능한 전공 과목이 없습니다.")
            else:
                # options로는 데이터프레임의 '인덱스'를 사용한다.
                # format_func를 사용해 사용자에게는 포맷팅된 문자열을 보여준다.
                selected_index = st.selectbox(
                    "추가할 전공 과목 선택",
                    options=sorted_df.index,
                    format_func=lambda idx: format_display_string(sorted_df.loc[idx]),
                    key="major_select",
                    label_visibility="collapsed"
                )
                if st.button("전공 추가", key="add_major"):
                    # apply 없이 인덱스로 바로 행을 찾는다. (매우 빠름)
                    selected_row = sorted_df.loc[selected_index]
                    add_course_to_timetable(selected_row)

    with tab_general:
        # 필터링 기반 데이터 정의
        all_general_df = master_df[master_df['type'] == '교양']
        general_df_to_display = available_df[available_df['type'] == '교양']

        # --- 1. 필터 위젯 배치 및 사용자 선택값 받기 ---
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            cat_options = sorted(all_general_df['이수구분'].dropna().unique().tolist())
            selected_cat = st.selectbox("이수구분", ["전체"] + cat_options, key="cat_select")

        # 옵션 생성을 위한 데이터프레임
        options_df = all_general_df[all_general_df['이수구분'] == selected_cat] if selected_cat != "전체" else all_general_df

        with col2:
            if selected_cat == '일반선택':
                # '꿈·미래개척' 과목 필터링 옵션 (네이밍 수정)
                dream_options = ['전체', '꿈·미래개척만 보기', '꿈·미래개척 제외']
                selected_dream_filter = st.selectbox("꿈·미래개척 과목", dream_options, key="dream_filter_select")
                selected_area = "전체" # 영역구분 필터는 비활성화
            else:
                # 기존 영역구분 필터
                area_options = sorted([opt for opt in options_df['영역구분'].dropna().unique() if opt.strip()])
                selected_area = st.selectbox("영역구분", ["전체"] + area_options, key="area_select")
                selected_dream_filter = "전체" # 꿈·미래개척 필터는 비활성화

        if selected_area != "전체":
            options_df = options_df[options_df['영역구분'] == selected_area]

        with col3:
            method_options = sorted(options_df['수업방법'].dropna().unique().tolist())
            selected_method = st.selectbox("수업방법", ["전체"] + method_options, key="method_select")
        
        if selected_method != "전체":
            options_df = options_df[options_df['수업방법'] == selected_method]

        with col4:
            remote_options = sorted([opt for opt in options_df['원격강의구분'].dropna().unique() if opt.strip()])
            selected_remote = st.selectbox("원격강의구분", ["전체"] + remote_options, key="remote_select")
        
        if selected_remote != "전체":
            options_df = options_df[options_df['원격강의구분'] == selected_remote]

        with col5:
            campus_options = sorted(options_df['캠퍼스구분'].dropna().unique().tolist())
            selected_campus = st.selectbox("캠퍼스", ["전체"] + campus_options, key="general_campus_select")

        # --- 2. 모든 필터 값을 사용해 최종 데이터 필터링 ---
        final_filtered_gen_df = general_df_to_display.copy()

        # 각 필터를 독립적인 if문으로 분리하여 순차적으로 적용
        if selected_cat != "전체":
            final_filtered_gen_df = final_filtered_gen_df[final_filtered_gen_df['이수구분'] == selected_cat]

        # '일반선택'의 특수 필터 로직
        if selected_cat == '일반선택':
            if selected_dream_filter == '꿈·미래개척만 보기':
                final_filtered_gen_df = final_filtered_gen_df[final_filtered_gen_df['교과목명'] == '꿈·미래개척']
            elif selected_dream_filter == '꿈·미래개척 제외':
                final_filtered_gen_df = final_filtered_gen_df[final_filtered_gen_df['교과목명'] != '꿈·미래개척']
        # '일반선택'이 아닌 다른 교양의 '영역구분' 필터
        else:
            if selected_area != "전체":
                final_filtered_gen_df = final_filtered_gen_df[final_filtered_gen_df['영역구분'] == selected_area]

        # 나머지 공통 필터
        if selected_method != "전체":
            final_filtered_gen_df = final_filtered_gen_df[final_filtered_gen_df['수업방법'] == selected_method]
        if selected_remote != "전체":
            final_filtered_gen_df = final_filtered_gen_df[final_filtered_gen_df['원격강의구분'] == selected_remote]
        if selected_campus != "전체":
            final_filtered_gen_df = final_filtered_gen_df[final_filtered_gen_df['캠퍼스구분'] == selected_campus]

        st.write("---")
        
        if not final_filtered_gen_df.empty:
            sorted_gen_df = final_filtered_gen_df.sort_values(by=['이수구분', '영역구분', '수업방법', '원격강의구분', '교과목명'], ascending=True)
            course_options_gen = sorted_gen_df.apply(format_display_string, axis=1).tolist()
        else:
            course_options_gen = []
        
        if not course_options_gen:
            st.warning("해당 조건에 현재 추가 가능한 교양 과목이 없습니다.")
        else:
            selected_index_gen = st.selectbox(
                "추가할 교양 과목 선택",
                options=sorted_gen_df.index,
                format_func=lambda idx: format_display_string(sorted_gen_df.loc[idx]),
                key="general_select",
                label_visibility="collapsed"
            )
            if st.button("교양 추가", key="add_general"):
                selected_row = sorted_gen_df.loc[selected_index_gen]
                add_course_to_timetable(selected_row)

    st.divider()
    st.subheader("2. 나의 시간표")

    if not st.session_state.my_courses:
        st.info("과목을 추가하면 시간표가 여기에 표시됩니다.")
    else:
        my_courses_df = master_df[master_df.set_index(['교과목코드', '분반']).index.isin(st.session_state.my_courses)]

        days_order = ['월', '화', '수', '목', '금', '토', '일']
        days_to_display_set = set(['월', '화', '수', '목', '금'])
        for _, course in my_courses_df.iterrows():
            for time_info in course['parsed_time']:
                days_to_display_set.add(time_info['day'])
        days_to_display = [day for day in days_order if day in days_to_display_set]

        default_min_period, default_max_period = 1, 9
        all_periods = [p for _, course in my_courses_df.iterrows() for time_info in course['parsed_time'] for p in time_info['periods']]
        actual_max_period = max(all_periods) if all_periods else default_max_period
        actual_min_period = min(all_periods) if all_periods else default_min_period
        final_max_period = max(default_max_period, actual_max_period)
        final_min_period = min(default_min_period, actual_min_period)

        timetable_data = {}
        for p in range(final_min_period, final_max_period + 1):
            for d in days_to_display:
                timetable_data[(p, d)] = {"content": "", "color": "white", "span": 1, "is_visible": True}

        for _, course in my_courses_df.iterrows():
            if course['parsed_time']:
                color = st.session_state.color_map.get(course['교과목명'], "white")
                for time_info in course['parsed_time']:
                    if time_info['day'] not in days_to_display: continue
                    content = f"<b>{course['교과목명']}</b><br>{course['교수명']}<br>{time_info['room']}"
                    periods = sorted(time_info['periods'])
                    if not periods: continue
                    start_period, block_len = periods[0], 1
                    for i in range(1, len(periods)):
                        if periods[i] == periods[i-1] + 1:
                            block_len += 1
                        else:
                            if (start_period, time_info['day']) in timetable_data:
                                timetable_data[(start_period, time_info['day'])].update({"content": content, "color": color, "span": block_len})
                                for j in range(1, block_len):
                                    if (start_period + j, time_info['day']) in timetable_data:
                                        timetable_data[(start_period + j, time_info['day'])]["is_visible"] = False
                            start_period, block_len = periods[i], 1
                    if (start_period, time_info['day']) in timetable_data:
                        timetable_data[(start_period, time_info['day'])].update({"content": content, "color": color, "span": block_len})
                        for j in range(1, block_len):
                            if (start_period + j, time_info['day']) in timetable_data:
                                timetable_data[(start_period + j, time_info['day'])]["is_visible"] = False

        day_col_width = (100 - 10) / len(days_to_display)
        
        table_html = f"""<div id="timetable-to-capture"><table class="timetable"><tr><th width="10%">교시</th>"""
        for d in days_to_display: table_html += f'<th width="{day_col_width}%">{d}</th>'
        table_html += '</tr>'
        time_map = {i: f"{8+i:02d}:00" for i in range(16)}
        for p in range(final_min_period, final_max_period + 1):
            table_html += f'<tr><td>{p}교시<br>{time_map.get(p, "")}</td>'
            for d in days_to_display:
                cell = timetable_data.get((p, d))
                if cell and cell["is_visible"]:
                    table_html += f'<td rowspan="{cell["span"]}" style="background-color:{cell["color"]};">{cell["content"]}</td>'
            table_html += '</tr>'
        table_html += "</table></div>"
        
        button_html = """
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
        <button id="download-btn-component" class="download-btn">시간표 이미지로 저장</button>
        <div id="status-message" style="margin-top:10px;font-size:14px"></div>
        <script>
            document.getElementById('download-btn-component').onclick = function() {
                const element = document.getElementById("timetable-to-capture");
                const statusDiv = document.getElementById('status-message');
                if (element) {
                    statusDiv.innerText = '이미지 생성 중...';
                    statusDiv.style.color = 'blue';

                    // scale 값을 3으로 높여 해상도를 확보하고, 복잡한 리사이징 로직은 모두 제거합니다.
                    html2canvas(element, { scale: 3, useCORS: true, backgroundColor: '#ffffff' })
                    .then(canvas => {
                        // 리사이징 없이, 캡처된 캔버스를 그대로 사용합니다.
                        const link = document.createElement("a");
                        link.href = canvas.toDataURL("image/png");
                        link.download = "my_gnu_timetable.png";
                        
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);

                        statusDiv.innerText = '✅ 이미지 다운로드가 시작되었습니다.';
                        statusDiv.style.color = 'green';
                    }).catch(err => {
                        statusDiv.innerText = '❌ 이미지 생성 오류: ' + err;
                        statusDiv.style.color = 'red';
                    });
                } else {
                    statusDiv.innerText = '❌ 오류: 시간표 요소를 찾을 수 없습니다.';
                    statusDiv.style.color = 'red';
                }
            };
        </script>
        """
        
        combined_html = f"""
        <style>
        .timetable{{width:100%;border-collapse:collapse;table-layout:fixed;border-bottom:1px solid #e0e0e0}}
        .timetable th,.timetable td{{border:1px solid #e0e0e0;text-align:center;vertical-align:middle;padding:2px;height:50px;font-size:.75em;overflow:hidden;text-overflow:ellipsis;word-break:keep-all}}
        .timetable th{{background-color:#f0f2f6;font-weight:700}}
        .download-btn{{display:inline-block;padding:10px 20px;background-color:#007bff;color:#fff;text-align:center;text-decoration:none;border-radius:5px;border:none;cursor:pointer;font-size:16px;margin-top:20px}}
        .download-btn:hover{{background-color:#0056b3}}
        </style>
        {table_html}
        {button_html}
        """
        
        st.components.v1.html(combined_html, height=(final_max_period - final_min_period + 2) * 55 + 120)

        untimed_courses = [course for _, course in my_courses_df.iterrows() if not course['parsed_time']]
        if untimed_courses:
            st.write("**[시간 미지정 과목]**")
            for course in untimed_courses:
                remark_display = f" / 비고: {course['비고']}" if pd.notna(course['비고']) and course['비고'].strip() != '' else ''
                remote_info_display = f" ({course['원격강의구분']})" if ('비대면' in course['수업방법'] or '혼합' in course['수업방법']) and pd.notna(course['원격강의구분']) and course['원격강의구분'].strip() != '' else ''
                st.write(f"- [{course['수업방법']}{remote_info_display}] {course['교과목명']} ({course['교수명']}, {course['학점']}학점){remark_display}")
                        
        st.write("---")

        # 1. 목록 헤더 (한 줄 스타일) 및 전체 초기화 버튼
        list_col, button_col = st.columns([0.85, 0.15])
        with list_col:
            num_selected_courses = len(st.session_state.my_courses)
            total_credits = my_courses_df['학점'].sum()
            total_credits_str = str(int(total_credits)) if total_credits == int(total_credits) else f"{total_credits:.1f}"

            header_html = f"""
            <div style="display: flex; align-items: center; height: 40px; gap: 1.5rem;">
                <strong style="font-size: 1.1rem; white-space: nowrap;">선택한 과목 내역 [총 {num_selected_courses}건]</strong>
                <span class="bullet-item" style="display: flex; align-items: center; white-space: nowrap; color: #555;">
                    <span>신청학점 : {total_credits_str} 학점</span>
                </span>
                <span class="bullet-item" style="display: flex; align-items: center; white-space: nowrap; color: #555;">
                    <span>신청과목 : {num_selected_courses} 과목</span>
                </span>
            </div>
            """
            st.markdown(header_html, unsafe_allow_html=True)
            
        with button_col:
            if st.button("전체 초기화", type="primary", use_container_width=True):
                st.session_state.my_courses = []
                st.session_state.color_map = {}
                st.rerun()

        st.markdown("""
        <style>
            /* 복사 안 되는 글머리 기호 스타일 (헤더에 사용된 것) */
            .bullet-item::before {
                content: '●';
                font-size: 0.4em; /* 헤더 글머리 기호 크기 유지 */
                margin-right: 0.4rem;
                user-select: none;
            }

            /* 선택한 과목 목록의 글머리 기호 스타일 */
            .course-list-item::before {
                content: '●';
                font-size: 0.3em; /* 과목 목록 글머리 기호 크기 조정 */
                margin-right: 9px; /* 기존 하이픈과 동일한 간격 */
                user-select: none; /* 복사 안 되게 설정 */
            }
        </style>
        """, unsafe_allow_html=True)

        for index, (code, no) in enumerate(st.session_state.my_courses):
            course = master_df[(master_df['교과목코드'] == code) & (master_df['분반'] == no)].iloc[0]
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                # format_display_string 대신 format_list_item_string 호출
                display_str = format_list_item_string(course) 

                st.markdown(f"""
                <div style="display: flex; align-items: baseline;" class="course-list-item">
                    <div style="word-break: break-all; overflow-wrap: break-word;">
                        {display_str}
                        <div style="opacity: 0.7;">(교과목코드: {code}, 분반: {int(no):03d}, 학점: {int(course['학점']) if course['학점'] == int(course['학점']) else course['학점']}학점)</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                # 삭제 버튼의 key는 고유해야 하므로 index도 포함
                if st.button("제거", key=f"del-{code}-{no}-{index}", use_container_width=True, type="secondary"):
                    st.session_state.my_courses.pop(index)
                    st.rerun()
