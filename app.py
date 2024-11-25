import re
from datetime import datetime, timedelta
import json
import threading
import time
import google.generativeai as genai
import requests  # 날씨 API 호출에 사용


# Google API Key 설정
GOOGLE_API_KEY = "YOUR API KEY" # GEMINI에서 발급받은 API 키

# Generative AI 초기화
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-pro')
chat = model.start_chat(history=[])

# OpenWeatherMap API 설정
OPENWEATHER_API_KEY = "YOUR API KEY"  # OpenWeatherMap에서 발급받은 API 키
CITY_NAME = "Seoul"  # 기본 도시 이름

# 사용자 이름 저장
user_name = ""

# 스케줄 데이터 저장소
schedule_list = []
notified_schedules = set()  # 알림이 이미 된 스케줄의 ID를 저장

# 스케줄을 시간 순으로 정렬
def sort_schedules():
    """스케줄을 시간 순으로 정렬합니다."""
    global schedule_list
    schedule_list.sort(key=lambda x: x["time"])

# 스케줄 추가 함수
def add_schedule(title, datetime_str):
    try:
        # 유효하지 않은 날짜를 처리하기 위한 추가 예외 처리
        try:
            schedule_time = datetime.strptime(datetime_str.strip(), "%Y-%m-%d %H:%M")
        except ValueError:
            return "유효하지 않은 날짜입니다. 날짜를 확인하고 다시 입력해주세요."

        schedule_id = len(schedule_list) + 1
        schedule_list.append({"id": schedule_id, "title": title.strip(), "time": schedule_time})
        sort_schedules()  # 스케줄 추가 후 정렬
        save_schedules()
        return f"'{title}' 스케줄이 {schedule_time.strftime('%Y-%m-%d %H:%M')}에 추가되었습니다."
    except Exception as e:
        return f"스케줄 추가 중 오류가 발생했습니다: {e}"


def view_schedules():
    if not schedule_list:
        return f"{user_name}님, 현재 스케줄이 없습니다."
    response = f"{user_name}님, 현재 등록된 스케줄 (시간 순):\n"
    for idx, schedule in enumerate(schedule_list, 1):
        response += f"{idx}. {schedule['title']} - {schedule['time'].strftime('%Y-%m-%d %H:%M')}\n"
    return response.strip()

def view_weekly_schedules():
    today = datetime.now().date()
    end_of_week = today + timedelta(days=7)
    filtered_schedules = [
        schedule for schedule in schedule_list if today <= schedule["time"].date() <= end_of_week
    ]
    if not filtered_schedules:
        return f"{user_name}님, 이번 주에는 등록된 스케줄이 없습니다."
    response = f"{user_name}님, 이번 주 스케줄 (시간 순):\n"
    for idx, schedule in enumerate(filtered_schedules, 1):
        response += f"{idx}. {schedule['title']} - {schedule['time'].strftime('%Y-%m-%d %H:%M')}\n"
    return response.strip()

def view_monthly_summary():
    today = datetime.now().date()
    end_of_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    days = (end_of_month - today).days + 1

    summary = {}
    for day in (today + timedelta(days=i) for i in range(days)):
        count = sum(1 for schedule in schedule_list if schedule["time"].date() == day)
        summary[day] = count

    response = f"{user_name}님, 이번 달 요약입니다:\n"
    for date, count in sorted(summary.items()):
        response += f"- {date.strftime('%Y-%m-%d')}: {count}개의 스케줄\n"
    return response.strip()

def get_upcoming_event():
    now = datetime.now()
    upcoming_schedules = sorted(
        (schedule for schedule in schedule_list if schedule["time"] > now),
        key=lambda x: x["time"]
    )
    if upcoming_schedules:
        next_event = upcoming_schedules[0]
        return f"다가오는 주요 이벤트: '{next_event['title']}' ({next_event['time'].strftime('%Y-%m-%d %H:%M')})"
    return "다가오는 주요 이벤트가 없습니다."

def delete_schedule(index):
    try:
        index = int(index) - 1
        if 0 <= index < len(schedule_list):
            removed = schedule_list.pop(index)
            sort_schedules()  # 삭제 후 정렬 유지
            save_schedules()
            return f"{user_name}님, '{removed['title']}' 스케줄이 삭제되었습니다."
        else:
            return "유효하지 않은 번호입니다."
    except (ValueError, TypeError):
        return "삭제할 스케줄 번호를 정확히 입력해주세요."

# 스케줄 파일 저장/로드
def save_schedules():
    with open("schedules.json", "w", encoding="utf-8") as file:
        json.dump(schedule_list, file, ensure_ascii=False, indent=4, default=str)

def load_schedules():
    global schedule_list
    try:
        with open("schedules.json", "r", encoding="utf-8") as file:
            schedule_list = json.load(file)
            for idx, schedule in enumerate(schedule_list, start=1):
                schedule["id"] = idx
                schedule["time"] = datetime.fromisoformat(schedule["time"])
        sort_schedules()  # 불러온 후 정렬
    except FileNotFoundError:
        schedule_list = []

# 스케줄 알림 기능
def schedule_notifier():
    while True:
        now = datetime.now()
        for schedule in schedule_list:
            schedule_id = schedule["id"]
            schedule_time = schedule["time"]

            # 지나간 스케줄은 무시
            if schedule_time < now:
                continue

            # 5분 전 알림 조건
            if schedule_id not in notified_schedules and now >= schedule_time - timedelta(minutes=5):
                print(f"\n⏰ [알림] '{schedule['title']}' 스케줄이 곧 시작됩니다! ({schedule_time.strftime('%Y-%m-%d %H:%M')})")
                notified_schedules.add(schedule_id)
        time.sleep(10)  # 10초마다 확인

# 자연어 처리 함수
def process_natural_language(user_input):
    try:
        # 조회 명령 처리
        if "조회" in user_input:
            if "이번 주" in user_input:
                return "주간 조회", None, None
            elif "이번 달" in user_input:
                return "월간 요약", None, None
            else:
                return "전체 조회", None, None

        # 삭제 명령 처리
        if "삭제" in user_input:
            index_match = re.search(r"\d+", user_input)
            index = index_match.group() if index_match else None
            return "삭제", index, None

        # 추가 명령 처리
        date_obj = None

        # 오늘/내일 처리
        if "오늘" in user_input:
            date_obj = datetime.now().date()
        elif "내일" in user_input:
            date_obj = (datetime.now() + timedelta(days=1)).date()

        # 시간 처리
        time_match = re.search(r"(오전|오후)?\s?(\d{1,2})시\s?(\d{1,2}분)?", user_input)
        if time_match:
            hour = int(time_match.group(2))
            minute = int(time_match.group(3).replace("분", "")) if time_match.group(3) else 0
            if "오후" in time_match.group(1):
                hour += 12 if hour < 12 else 0

            if date_obj:
                date_obj = datetime.combine(date_obj, datetime.min.time()).replace(
                    hour=hour, minute=minute
                )
            else:
                date_obj = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)

        # 명시적 날짜와 시간 파싱
        date_time_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", user_input)
        if date_time_match:
            try:
                date_obj = datetime.strptime(date_time_match.group(), "%Y-%m-%d %H:%M")
            except ValueError:
                return "기타", None, None  # 잘못된 날짜 형식인 경우 처리

        # 제목 추출
        keywords = ["회의", "만남", "약속", "모임", "시험"]
        for keyword in keywords:
            pattern = rf"(\S+)?\s?{keyword}"
            match = re.search(pattern, user_input)
            if match:
                title = match.group(0).strip()
                if date_obj:
                    return "추가", title, date_obj.strftime("%Y-%m-%d %H:%M")

        # 명령어 이해 실패 시 기본값 반환
        return "기타", None, None

    except Exception as e:
        print(f"자연어 처리 오류: {e}")
        return "기타", None, None

    
# 오늘의 날씨를 가져오는 함수
def get_weather_today():
    """오늘의 날씨 정보를 가져옵니다."""
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={CITY_NAME}&appid={OPENWEATHER_API_KEY}&units=metric&lang=kr"
        response = requests.get(url)
        data = response.json()

        weather = data["weather"][0]["description"]  # 날씨 설명
        temp = data["main"]["temp"]  # 현재 온도
        return f"오늘의 날씨: {weather}, {temp}°C"
    except Exception as e:
        return "날씨 정보를 가져오는 데 실패했습니다."

# 특정 날짜의 날씨를 가져오는 함수
def get_weather_by_date(date):
    """특정 날짜의 날씨 정보를 가져옵니다."""
    try:
        url = f"http://api.openweathermap.org/data/2.5/forecast?q={CITY_NAME}&appid={OPENWEATHER_API_KEY}&units=metric&lang=kr"
        response = requests.get(url)
        data = response.json()

        forecast_list = data["list"]
        date_str = date.strftime("%Y-%m-%d")
        weather_data = [
            item
            for item in forecast_list
            if date_str in item["dt_txt"]
        ]

        if not weather_data:
            return f"{date_str}의 날씨 정보를 찾을 수 없습니다."

        # 가장 첫 번째 예보를 기준으로 날씨 표시
        weather = weather_data[0]["weather"][0]["description"]
        temp = weather_data[0]["main"]["temp"]
        return f"{date_str} 날씨: {weather}, {temp}°C"
    except Exception as e:
        return f"{date.strftime('%Y-%m-%d')}의 날씨 정보를 가져오는 데 실패했습니다."

# 스케줄 및 날씨를 함께 출력하는 함수
def view_schedules_with_weather():
    """스케줄과 해당 날짜의 날씨를 함께 표시합니다."""
    if not schedule_list:
        return f"{user_name}님, 현재 스케줄이 없습니다."

    response = f"{user_name}님, 현재 등록된 스케줄 및 날씨:\n"
    for idx, schedule in enumerate(schedule_list, 1):
        schedule_date = schedule["time"].date()
        weather = get_weather_by_date(schedule_date)
        response += f"{idx}. {schedule['title']} - {schedule['time'].strftime('%Y-%m-%d %H:%M')} ({weather})\n"
    return response.strip()

# AI 비서 시작
print("AI 비서가 시작되었습니다.")

# 사용자 이름 받기
user_name = input("AI 비서: 사용자의 이름을 입력해주세요: ").strip()
print(f"반갑습니다, {user_name}님! AI 비서를 시작합니다.")

#명령어 알려주기
print(
    """

사용 가능한 명령어:
1. 스케줄 추가: "<스케줄 명> <날짜 및 시간> 추가" 형식으로 입력 (예: "회의 2024-11-30 14:00 추가"). 
               혹은 오늘/내일 오전/오후 N시 <스케줄 명> 추가(예: 오늘 오전 9시 운동 약속 추가)
2. 전체 조회: 등록된 모든 스케줄을 확인합니다.
3. 이번 주 조회: 이번 주에 등록된 스케줄을 확인합니다.
4. 이번 달 요약: 이번 달의 스케줄 요약 정보를 확인합니다.
5. 스케줄 삭제: "<전체 조회>하여 나온 스케줄의 <번호>에 삭제 <번호>"로 스케줄을 삭제합니다 (예: "삭제 1").
6. 종료: "종료"를 입력하면 AI 비서를 종료합니다.
    """
)



# 스케줄 불러오기
load_schedules()

# 알림 스레드 시작
notifier_thread = threading.Thread(target=schedule_notifier, daemon=True)
notifier_thread.start()

# 대시보드 표시
print(get_weather_today())
print(view_schedules_with_weather())
print(get_upcoming_event())

while True:
    user_input = input(f"유저: ").strip()

    if user_input.lower() in ["exit", "종료"]:
        print(f"{user_name}님, AI 비서를 종료합니다. 안녕히 가세요!")
        break

    command, param1, param2 = process_natural_language(user_input)

    if command == "추가":
        print(add_schedule(param1, param2))
    elif command in ["조회", "전체 조회"]:
        print(view_schedules())
    elif command == "주간 조회":
        print(view_weekly_schedules())
    elif command == "월간 요약":
        print(view_monthly_summary())
    elif command == "삭제":
        if param1:
            print(delete_schedule(param1))
        else:
            print("삭제할 스케줄 번호를 입력해주세요.")
    elif command == "기타":
        print("AI 비서: 명령어를 이해하지 못했습니다. 다시 입력해주세요.")
    else:
        print(f"AI 비서: 알 수 없는 명령입니다.")
