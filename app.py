import streamlit as st
import pandas as pd
import os
import re

# --- 기본 설정 및 데이터 로딩 ---

# 웹페이지 기본 설정
st.set_page_config(page_title="GNU 시간표 도우미", layout="wide")
st.title("👨‍💻 경상국립대학교 시간표 도우미")

# 데이터 로딩 함수 (캐싱 기능 추가로 성능 향상)
@st.cache_data
def load_and_process_data(file_path, major_sheet, general_sheet):
    try:
        df_major = pd.read_excel(file_path, sheet_name=major_sheet)
        df_general = pd.read_excel(file_path, sheet_name=general_sheet)
    except Exception as e:
        st.error(f"엑셀 파일을 읽는 중 오류 발생: {e}")
        return None

    df_general_p = df_general[['교과목명', '교수명', '학점', '이수구분', '학과', '수강반번호', '강의시간/강의실', '캠퍼스구분', '교과목코드']].copy()
    df_general_p.rename(columns={'학과': '학부(과)', '수강반번호': '분반'}, inplace=True)
    df_major_p = df_major[['교과목명', '교수명', '학점', '이수구분', '학부(과)', '분반', '강의시간/강의실', '캠퍼스구분', '교과목코드']].copy()
    
    df_combined = pd.concat([df_general_p, df_major_p], ignore_index=True).dropna(subset=['교과목코드', '분반'])
    df_combined['교과목코드'] = df_combined['교과목코드'].astype(int)
    df_combined['분반'] = df_combined['분반'].astype(int)
    df_combined['unique_id'] = df_combined['교과목코드'].astype(str) + '-' + df_combined['분반'].astype(str)

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

# --- 핵심 로직 함수들 (기존 코드와 거의 동일) ---

def check_conflict(df, current_codes, new_code, new_no):
    new_course = df[(df['교과목코드'] == new_code) & (df['분반'] == new_no)].iloc[0]
    if not new_course['parsed_time']: return None # 시간 미지정 과목은 충돌 없음
    for code, no in current_codes:
        existing_course = df[(df['교과목코드'] == code) & (df['분반'] == no)].iloc[0]
        if not existing_course['parsed_time']: continue
        for new_time in new_course['parsed_time']:
            for existing_time in existing_course['parsed_time']:
                if new_time['day'] == existing_time['day'] and set(new_time['periods']) & set(existing_time['periods']):
                    return existing_course['교과목명']
    return None

# --- 웹앱 UI 구성 ---

# 데이터 파일 경로 설정
excel_file_path = '경상국립대학교 2025학년도 2학기 시간표.xlsx'
if not os.path.exists(excel_file_path):
    st.error(f"'{excel_file_path}' 파일을 찾을 수 없습니다. `app.py`와 같은 폴더에 엑셀 파일을 넣어주세요.")
    st.stop()

master_df = load_and_process_data(excel_file_path, '2학기 전공 시간표', '2학기 교양 시간표')

if master_df is not None:
    # 세션 상태(session_state)를 사용해 선택한 과목 목록 유지
    if 'my_courses' not in st.session_state:
        st.session_state.my_courses = []

    # 1. 과목 선택 인터페이스
    st.subheader("1. 과목 선택")
    
    # 학부(과) 필터링
    departments = sorted(master_df['학부(과)'].dropna().unique().tolist())
    selected_dept = st.selectbox("학부(과) 선택", ["전체"] + departments)

    if selected_dept == "전체":
        filtered_df = master_df
    else:
        filtered_df = master_df[master_df['학부(과)'] == selected_dept]

    # 과목 선택 (검색 가능)
    course_options = filtered_df.apply(lambda x: f"{x['교과목명']} ({x['교수명']}, {x['분반']}반)", axis=1).tolist()
    selected_course_str = st.selectbox("추가할 과목 선택", course_options)
    
    if st.button("시간표에 추가"):
        selected_row = filtered_df[filtered_df.apply(lambda x: f"{x['교과목명']} ({x['교수명']}, {x['분반']}반)", axis=1) == selected_course_str].iloc[0]
        course_code_to_add = selected_row['교과목코드']
        class_no_to_add = selected_row['분반']
        
        # 중복 추가 방지
        if (course_code_to_add, class_no_to_add) in st.session_state.my_courses:
            st.warning("이미 추가된 과목입니다.")
        else:
            conflict_course = check_conflict(master_df, st.session_state.my_courses, course_code_to_add, class_no_to_add)
            if conflict_course:
                st.error(f"시간 충돌: '{selected_row['교과목명']}'이(가) '{conflict_course}' 과목과 시간이 겹칩니다.")
            else:
                st.session_state.my_courses.append((course_code_to_add, class_no_to_add))
                st.success(f"'{selected_row['교과목명']}' 과목을 추가했습니다.")

    # 2. 내 시간표 및 정보 표시
    st.subheader("2. 나의 시간표")

    if not st.session_state.my_courses:
        st.info("아직 추가된 과목이 없습니다.")
    else:
        # 시간표 DataFrame 생성
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

        # 총 학점 및 시간표 표시
        total_credits = my_courses_df['학점'].sum()
        st.metric("총 신청 학점", f"{total_credits} 학점")
        
        st.dataframe(timetable, height=1200)

        if untimed_courses:
            st.write("**[시간 미지정 과목]**")
            for uc in untimed_courses:
                st.write(f"- {uc}")

        # 선택한 과목 목록 및 제거 기능
        st.write("---")
        st.write("**[선택한 과목 목록]**")
        for code, no in st.session_state.my_courses:
            course = master_df[(master_df['교과목코드'] == code) & (master_df['분반'] == no)].iloc[0]
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                st.write(f"- {course['교과목명']} ({course['교수명']}, {course['분반']}반)")
            with col2:
                if st.button("제거", key=f"del-{code}-{no}"):
                    st.session_state.my_courses.remove((code, no))
                    st.experimental_rerun() # 페이지 새로고침
