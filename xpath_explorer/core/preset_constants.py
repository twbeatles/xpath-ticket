# -*- coding: utf-8 -*-
"""Built-in site presets."""

SITE_PRESETS = {
    "인터파크": {
        "name": "인터파크 티켓 (NOL)",
        "url": "https://tickets.interpark.com",
        "login_url": "https://accounts.interpark.com/login/form/interpark",
        "description": "인터파크 티켓 예매 (야놀자 통합 로그인)",
        "items": [
            # 로그인 (2024년 12월 기준 - Cloudflare Turnstile 보호)
            {"name": "login_id", "xpath": '//input[@name="username"]', "category": "login", "desc": "아이디 입력 (name 속성)"},
            {"name": "login_pw", "xpath": '//input[@name="password"]', "category": "login", "desc": "비밀번호 입력 (name 속성)"},
            {"name": "login_submit", "xpath": '//button[contains(., "로그인")]', "category": "login", "desc": "로그인 버튼 (Cloudflare 인증 후 표시)"},
            {"name": "remember_me", "xpath": '//*[@id="rememberMe"]', "category": "login", "desc": "로그인 상태 유지 체크박스"},
            {"name": "old_login_btn", "xpath": '//button[contains(., "기존 인터파크")]', "category": "login", "desc": "기존 인터파크 계정 로그인 버튼"},
            # 메인 페이지
            {"name": "main_login_btn", "xpath": '//button[contains(@class, "login")]', "category": "main", "desc": "메인 페이지 로그인 버튼"},
            {"name": "search_input", "xpath": '//input[@type="search"]', "category": "main", "desc": "검색 입력창"},
            # 예매
            {"name": "book_button", "xpath": '//a[contains(@class, "is-primary")]', "category": "booking", "desc": "예매하기 버튼"},
            {"name": "book_button_alt", "xpath": '//a[contains(text(), "예매하기")]', "category": "booking", "desc": "예매 버튼 (텍스트)"},
            {"name": "date_area", "xpath": '//*[@id="productSide"]/div/div[1]', "category": "booking", "desc": "날짜 선택 영역"},
            {"name": "round_list", "xpath": '//ul[contains(@class, "roundList")]/li', "category": "booking", "desc": "회차 목록"},
            # 좌석 (iframe 내부)
            {"name": "seat_iframe", "xpath": "//*[@id='ifrmSeat']", "category": "seat", "desc": "좌석 iframe"},
            {"name": "seat_detail_frame", "xpath": "ifrmSeatDetail", "category": "seat", "desc": "좌석상세 iframe (name)"},
            {"name": "seat_area", "xpath": '//*[@id="divSeatArray"]', "category": "seat", "desc": "좌석 배열"},
            {"name": "seat_grade", "xpath": '//*[@id="divGrade"]', "category": "seat", "desc": "좌석 등급"},
            {"name": "next_step", "xpath": '//*[@id="NextStepImage"]', "category": "seat", "desc": "다음단계"},
            {"name": "seat_confirm", "xpath": '//*[@id="btnConfirm"]', "category": "seat", "desc": "좌석 확인"},
            # 캡차
            {"name": "captcha_img", "xpath": "//*[@id='imgCaptcha']", "category": "captcha", "desc": "캡차 이미지"},
            {"name": "captcha_input", "xpath": "//*[@id='txtCaptcha']", "category": "captcha", "desc": "캡차 입력"},
            {"name": "captcha_confirm", "xpath": '//a[contains(text(), "확인")]', "category": "captcha", "desc": "캡차 확인"},
            {"name": "captcha_reload", "xpath": '//a[contains(text(), "새로고침")]', "category": "captcha", "desc": "캡차 새로고침"},
        ]
    },
    "멜론티켓": {
        "name": "멜론티켓",
        "url": "https://ticket.melon.com",
        "login_url": "https://member.melon.com/muid/web/login/login_inform.htm",
        "description": "멜론티켓 예매 (카카오/멜론ID 로그인)",
        "items": [
            # 로그인 (2024년 12월 기준 - 검증됨)
            {"name": "melon_login_btn", "xpath": '//button[contains(@class, "melon")]', "category": "login", "desc": "멜론 ID 로그인 버튼 (폼 표시)"},
            {"name": "login_id", "xpath": '//*[@id="id"]', "category": "login", "desc": "아이디 입력"},
            {"name": "login_pw", "xpath": '//*[@id="pwd"]', "category": "login", "desc": "비밀번호 입력"},
            {"name": "login_submit", "xpath": '//*[@id="btnLogin"]', "category": "login", "desc": "로그인 버튼"},
            {"name": "kakao_login", "xpath": '//button[contains(@class, "kakao")]', "category": "login", "desc": "카카오 로그인 버튼"},
            # 예매
            {"name": "book_button", "xpath": '//a[contains(@class, "btn_book")]', "category": "booking", "desc": "예매하기"},
            {"name": "date_select", "xpath": '//div[contains(@class, "date_select")]', "category": "booking", "desc": "날짜 선택"},
            {"name": "time_select", "xpath": '//ul[contains(@class, "time_list")]/li', "category": "booking", "desc": "시간 선택"},
            # 좌석
            {"name": "seat_frame", "xpath": '//iframe[contains(@id, "seat")]', "category": "seat", "desc": "좌석 iframe"},
            {"name": "seat_area", "xpath": '//*[@id="seatArea"]', "category": "seat", "desc": "좌석 영역"},
            {"name": "next_btn", "xpath": '//button[contains(text(), "다음")]', "category": "seat", "desc": "다음 버튼"},
            {"name": "confirm_btn", "xpath": '//button[contains(text(), "선택완료")]', "category": "seat", "desc": "선택완료 버튼"},
        ]
    },
    "YES24": {
        "name": "YES24 티켓",
        "url": "https://ticket.yes24.com",
        "login_url": "https://www.yes24.com/Templates/FTLogin.aspx",
        "description": "YES24 티켓 예매",
        "items": [
            # 로그인 (2024년 12월 기준 - 검증됨)
            {"name": "login_id", "xpath": '//*[@id="SMemberID"]', "category": "login", "desc": "아이디 입력"},
            {"name": "login_pw", "xpath": '//*[@id="SMemberPassword"]', "category": "login", "desc": "비밀번호 입력"},
            {"name": "login_submit", "xpath": '//*[@id="btnLogin"]', "category": "login", "desc": "로그인 버튼"},
            {"name": "auto_login", "xpath": '//*[@id="chkAutoLogin"]', "category": "login", "desc": "자동 로그인 체크박스"},
            # 예매
            {"name": "book_button", "xpath": '//a[contains(@class, "btn_reserve")]', "category": "booking", "desc": "예매하기"},
            {"name": "calendar", "xpath": '//div[contains(@class, "calendar")]', "category": "booking", "desc": "캘린더"},
            {"name": "date_cell", "xpath": '//td[contains(@class, "sel")]', "category": "booking", "desc": "선택 가능한 날짜"},
            {"name": "time_list", "xpath": '//ul[@class="time-list"]/li', "category": "booking", "desc": "시간 목록"},
            {"name": "round_select", "xpath": '//select[@id="ddlRound"]', "category": "booking", "desc": "회차 선택 드롭다운"},
            # 좌석
            {"name": "seat_iframe", "xpath": '//iframe[@name="ifrmSeat"]', "category": "seat", "desc": "좌석 iframe"},
            {"name": "grade_list", "xpath": '//div[@class="grade-list"]//li', "category": "seat", "desc": "등급 목록"},
            {"name": "seat_available", "xpath": '//div[@title and string-length(@title)>0]', "category": "seat", "desc": "선택 가능한 좌석"},
            {"name": "confirm_btn", "xpath": '//button[contains(text(), "선택완료")]', "category": "seat", "desc": "선택완료"},
        ]
    },
    "티켓링크": {
        "name": "티켓링크 (봇 감지)",
        "url": "https://www.ticketlink.co.kr",
        "login_url": "https://www.ticketlink.co.kr/login",
        "description": "티켓링크 예매 (⚠️ 자동화 도구 감지 - 수동 확인 필요)",
        "items": [
            # 로그인 (봇 감지로 인해 자동화 제한)
            {"name": "login_id", "xpath": '//*[@id="userId"]', "category": "login", "desc": "ID 입력 (봇 감지 주의)"},
            {"name": "login_pw", "xpath": '//*[@id="userPwd"]', "category": "login", "desc": "PW 입력"},
            {"name": "login_submit", "xpath": '//button[@type="submit"]', "category": "login", "desc": "로그인"},
            # 예매
            {"name": "book_button", "xpath": '//a[contains(@class, "btn_book")]', "category": "booking", "desc": "예매"},
            {"name": "date_picker", "xpath": '//div[contains(@class, "datepicker")]', "category": "booking", "desc": "날짜"},
            # 좌석
            {"name": "seat_frame", "xpath": '//iframe[contains(@src, "seat")]', "category": "seat", "desc": "좌석 iframe"},
            {"name": "seat_map", "xpath": '//*[@id="seatMap"]', "category": "seat", "desc": "좌석맵"},
        ]
    },
    "네이버 예약": {
        "name": "네이버 예약",
        "url": "https://booking.naver.com",
        "login_url": "https://nid.naver.com/nidlogin.login",
        "description": "네이버 예약 (공연/전시)",
        "items": [
            # 로그인 (네이버 통합 로그인)
            {"name": "login_id", "xpath": '//*[@id="id"]', "category": "login", "desc": "네이버 아이디"},
            {"name": "login_pw", "xpath": '//*[@id="pw"]', "category": "login", "desc": "네이버 비밀번호"},
            {"name": "login_submit", "xpath": '//*[@id="log.login"]', "category": "login", "desc": "로그인 버튼"},
            # 예매
            {"name": "book_button", "xpath": '//button[contains(text(), "예약하기")]', "category": "booking", "desc": "예약하기 버튼"},
            {"name": "date_select", "xpath": '//div[contains(@class, "calendar")]//button', "category": "booking", "desc": "날짜 선택"},
        ]
    },
    "빈 템플릿": {
        "name": "새 사이트",
        "url": "",
        "login_url": "",
        "description": "사용자 정의 사이트",
        "items": []
    }
}
