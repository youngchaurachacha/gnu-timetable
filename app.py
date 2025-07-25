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
            periods = sorted([int(p) for p in re.findall(r'\d+', re.sub(r'\[.*?\]', '', details))])
            if periods: parsed.append({'day': day, 'periods': periods, 'room': room})
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
    if not parsed_time: return "시간미지정"
    time_str_parts = [f"{t['day']}{','.join(map(str, t['periods']))}" for t in parsed_time]
    return " ".join(time_str_parts)

def generate_random_color():
    """랜덤으로 밝은 톤의 배경색 생성"""
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
    # (탭 로직은 이전과 동일하여 생략)

    st.divider()
    st.subheader("2. 나의 시간표")

    if not st.session_state.my_courses:
        st.info("과목을 추가하면 시간표가 여기에 표시됩니다.")
    else:
        # --- 여기가 수정된 시간표 생성 로직 ---
        days = ['월', '화', '수', '목', '금', '토']
        my_courses_df = master_df[master_df.set_index(['교과목코드', '분반']).index.isin(st.session_state.my_courses)]
        
        # 1. 시간표 데이터 초기화
        timetable_data = {}
        for p in range(1, 13):
            for d in days:
                timetable_data[(p, d)] = {"name": "", "prof": "", "room": "", "color": "white", "span": 1, "is_visible": True}

        # 2. 시간표 데이터 채우기 및 연강 계산
        for _, course in my_courses_df.iterrows():
            color = st.session_state.color_map.get(course['교과목명'], "white")
            if course['parsed_time']:
                for time_info in course['parsed_time']:
                    # 연속된 교시 찾기
                    periods = sorted(time_info['periods'])
                    if not periods: continue
                    
                    blocks = []
                    current_block = [periods[0]]
                    for i in range(1, len(periods)):
                        if periods[i] == periods[i-1] + 1:
                            current_block.append(periods[i])
                        else:
                            blocks.append(current_block)
                            current_block = [periods[i]]
                    blocks.append(current_block)
                    
                    # 블록별로 시간표에 데이터 채우기
                    for block in blocks:
                        start_period = block[0]
                        span = len(block)
                        if time_info['day'] in days and start_period in range(1, 13):
                            timetable_data[(start_period, time_info['day'])] = {"name": course['교과목명'], "prof": course['교수명'], "room": time_info['room'], "color": color, "span": span, "is_visible": True}
                            for i in range(1, span):
                                if start_period + i <= 12:
                                    timetable_data[(start_period + i, time_info['day'])]["is_visible"] = False
        
        # 3. HTML 생성
        html = """<style>.timetable { width: 100%; border-collapse: collapse; }.timetable th, .timetable td { border: 1px solid #e0e0e0; text-align: center; vertical-align: middle; padding: 4px; height: 25px; font-size: 0.9em; }.timetable th { background-color: #f0f2f6; }</style><table class="timetable"><tr><th>교시</th><th>시간</th><th>월</th><th>화</th><th>수</th><th>목</th><th>금</th><th>토</th></tr>"""
        time_map = {p: f"{p+8:02d}:00~{p+8:02d}:50" for p in range(1, 13)}

        for p in range(1, 13):
            if any(timetable_data[(p, d)]["is_visible"] for d in days):
                html += '<tr>'
                # 교시와 시간은 첫번째 보이는 행에만 rowspan 적용
                if timetable_data[(p, days[0])]["is_visible"]: # 기준을 월요일로 잡음
                     html += f'<td rowspan={timetable_data[(p,days[0])].get("span", 1)}>{p}</td>'
                     html += f'<td rowspan={timetable_data[(p,days[0])].get("span", 1)}>{time_map[p]}</td>'

                for d in days:
                    cell = timetable_data[(p, d)]
                    if cell["is_visible"]:
                        span = cell.get("span", 1)
                        html += f'<td rowspan="{span}" style="background-color:{cell["color"]};">{cell["name"]}<br>{cell["prof"]}<br>{cell["room"]}</td>'
                html += '</tr>'
                # rowspan에 따라 빈 tr 생성
                for i in range(1, timetable_data[(p,days[0])].get("span", 1)):
                    html += '<tr></tr>'

        html += "</table>"
        
        total_credits = my_courses_df['학점'].sum()
        st.metric("총 신청 학점", f"{total_credits} 학점")
        st.components.v1.html(html, height=1000, scrolling=True)
        # (이하 미지정 과목 및 선택 목록 표시는 이전과 동일)
