# -*- coding: utf-8 -*-
"""Reusable XPath template definitions."""

XPATH_TEMPLATE_LIBRARY = [
    # login
    {
        "name": "아이디 입력 (name=username)",
        "category": "login",
        "xpath": "//input[@name='username']",
        "description": "로그인 ID 입력 필드 기본 패턴",
    },
    {
        "name": "아이디 입력 (id=id)",
        "category": "login",
        "xpath": "//*[@id='id']",
        "description": "국내 사이트에서 자주 쓰는 id 기반 로그인 입력",
    },
    {
        "name": "비밀번호 입력 (type=password)",
        "category": "login",
        "xpath": "//input[@type='password']",
        "description": "비밀번호 입력 필드 공통 패턴",
    },
    {
        "name": "로그인 버튼 (텍스트 포함)",
        "category": "login",
        "xpath": "//button[contains(normalize-space(.), '로그인')]",
        "description": "텍스트 기반 로그인 버튼",
    },
    {
        "name": "로그인 유지 체크박스",
        "category": "login",
        "xpath": "//input[@type='checkbox' and (contains(@name,'remember') or contains(@id,'remember'))]",
        "description": "remember/login 유지 체크박스 패턴",
    },
    # main
    {
        "name": "상단 검색 입력",
        "category": "main",
        "xpath": "//input[@type='search' or contains(@name,'search') or contains(@id,'search')]",
        "description": "검색 입력창 범용 패턴",
    },
    {
        "name": "메인 네비 메뉴 링크",
        "category": "main",
        "xpath": "//nav//a[@href]",
        "description": "상단 네비게이션 링크",
    },
    {
        "name": "공지/알림 배너 닫기",
        "category": "main",
        "xpath": "//button[contains(@class,'close') or contains(@aria-label,'close') or contains(@aria-label,'닫기')]",
        "description": "배너/팝업 닫기 버튼 패턴",
    },
    # booking
    {
        "name": "예매하기 버튼 (텍스트)",
        "category": "booking",
        "xpath": "//a[contains(.,'예매하기')] | //button[contains(.,'예매하기')]",
        "description": "예매 시작 버튼",
    },
    {
        "name": "날짜 선택 셀 (활성)",
        "category": "booking",
        "xpath": "//td[not(contains(@class,'disabled'))]//button",
        "description": "비활성 제외 날짜 버튼",
    },
    {
        "name": "회차 목록 아이템",
        "category": "booking",
        "xpath": "//ul[contains(@class,'round') or contains(@class,'time')]//li",
        "description": "회차/시간 목록 패턴",
    },
    {
        "name": "다음 단계 버튼",
        "category": "booking",
        "xpath": "//button[contains(.,'다음') or contains(.,'Next')]",
        "description": "다음 단계 이동 버튼",
    },
    # seat
    {
        "name": "좌석 iframe",
        "category": "seat",
        "xpath": "//iframe[contains(@id,'seat') or contains(@name,'seat')]",
        "description": "좌석 선택용 iframe",
    },
    {
        "name": "좌석 가능 요소 (title)",
        "category": "seat",
        "xpath": "//*[@title and string-length(normalize-space(@title)) > 0]",
        "description": "title 속성 기반 좌석 요소",
    },
    {
        "name": "좌석 등급 목록",
        "category": "seat",
        "xpath": "//ul[contains(@class,'grade') or contains(@id,'grade')]//li",
        "description": "좌석 등급 선택 목록",
    },
    {
        "name": "선택완료 버튼",
        "category": "seat",
        "xpath": "//button[contains(.,'선택완료') or contains(.,'확인')]",
        "description": "좌석 선택 완료 버튼",
    },
    # captcha
    {
        "name": "캡차 이미지",
        "category": "captcha",
        "xpath": "//img[contains(@id,'captcha') or contains(@src,'captcha')]",
        "description": "캡차 이미지 영역",
    },
    {
        "name": "캡차 입력 필드",
        "category": "captcha",
        "xpath": "//input[contains(@id,'captcha') or contains(@name,'captcha')]",
        "description": "캡차 문자열 입력 필드",
    },
    {
        "name": "캡차 새로고침 버튼",
        "category": "captcha",
        "xpath": "//a[contains(.,'새로고침')] | //button[contains(.,'새로고침')]",
        "description": "캡차 이미지 갱신 버튼",
    },
    # popup
    {
        "name": "모달 확인 버튼",
        "category": "popup",
        "xpath": "//div[contains(@class,'modal') or @role='dialog']//button[contains(.,'확인')]",
        "description": "모달 내 확인 버튼",
    },
    {
        "name": "모달 닫기 버튼",
        "category": "popup",
        "xpath": "//div[contains(@class,'modal') or @role='dialog']//button[contains(@class,'close') or contains(.,'닫기')]",
        "description": "모달/팝업 닫기 버튼",
    },
    {
        "name": "새 창 안내 체크박스",
        "category": "popup",
        "xpath": "//input[@type='checkbox' and (contains(.,'오늘') or contains(@name,'today') or contains(@id,'today'))]",
        "description": "오늘 하루 보지 않기 체크박스",
    },
    # common
    {
        "name": "공통 취소 버튼",
        "category": "common",
        "xpath": "//button[contains(.,'취소') or contains(.,'Cancel')]",
        "description": "취소/닫기 계열 버튼",
    },
    {
        "name": "공통 확인 버튼",
        "category": "common",
        "xpath": "//button[contains(.,'확인') or contains(.,'OK')]",
        "description": "확인/승인 계열 버튼",
    },
    {
        "name": "로딩 스피너",
        "category": "common",
        "xpath": "//*[contains(@class,'loading') or contains(@class,'spinner') or contains(@aria-busy,'true')]",
        "description": "로딩 상태 표시 요소",
    },
    # payment
    {
        "name": "결제 수단 라디오",
        "category": "payment",
        "xpath": "//input[@type='radio' and (contains(@name,'pay') or contains(@id,'pay'))]",
        "description": "결제수단 선택 라디오",
    },
    {
        "name": "결제 진행 버튼",
        "category": "payment",
        "xpath": "//button[contains(.,'결제') or contains(.,'Pay')]",
        "description": "최종 결제/결제하기 버튼",
    },
]
