#!/usr/bin/env python3
"""Read Korean numbers the way a Korean would.

Korean has two number systems and the counter picks which one. `3개` is *세 개*
(native), `3번` is *삼 번* (Sino-Korean). Nothing about the digit tells you which —
only the word after it does, so a TTS engine guessing from digits alone will get
roughly half of them wrong. Ours did: it read `3번` as *세 번*.

So we don't let it guess. Every number is spelled out in Hangul before the text
reaches the engine, and the counter decides the system.

Above twenty, native numerals stop sounding natural in technical speech — nobody
says *마흔일곱 번째 줄* — so we switch to Sino-Korean there regardless of counter.
"""

import re

SINO_DIGIT = ["영", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"]
SINO_UNIT = ["", "십", "백", "천"]
SINO_BIG = ["", "만", "억", "조"]

NATIVE = {
    1: "한", 2: "두", 3: "세", 4: "네", 5: "다섯", 6: "여섯", 7: "일곱",
    8: "여덟", 9: "아홉", 10: "열", 20: "스무",
}
NATIVE_TENS = {20: "스물", 30: "서른", 40: "마흔", 50: "쉰",
               60: "예순", 70: "일흔", 80: "여든", 90: "아흔"}

NATIVE_COUNTERS = {
    "개", "명", "사람", "마리", "살", "시", "시간", "가지", "번째",
    "벌", "권", "병", "잔", "장", "줄", "판", "채", "척", "통", "곳",
    "군데", "배", "쌍", "대", "조각", "켤레", "그루", "송이", "자루",
}
# 번 is the one that started this: `3번` means item three — 삼 번 — but the engine
# read it as 세 번, which is "three times". Both are real words; only the counter
# tells them apart, and in a coding agent 번 is always the label, never the count.
# 분 is minutes here, not the honorific for people, so it's Sino too.
SINO_COUNTERS = {
    "번", "초", "분", "년", "월", "일", "주", "개월", "원", "달러",
    "층", "도", "위", "회", "차", "호", "급", "점", "페이지", "쪽",
    "퍼센트", "인분", "킬로", "미터", "그램", "바이트",
}

NATIVE_MAX = 20  # past this, native reads as folksy rather than technical


def sino(n: int) -> str:
    if n == 0:
        return "영"
    out, group = [], 0
    while n:
        chunk, n = n % 10000, n // 10000
        if chunk:
            s = ""
            for i, d in enumerate(reversed(str(chunk))):
                d = int(d)
                if not d:
                    continue
                # 일십/일백/일천 are wrong — it's just 십/백/천.
                digit = "" if (d == 1 and i > 0) else SINO_DIGIT[d]
                s = digit + SINO_UNIT[i] + s
            out.append(s + SINO_BIG[group])
        group += 1
    return "".join(reversed(out))


def native(n: int) -> str:
    if n in NATIVE:
        return NATIVE[n]
    if n < 20:
        return "열" + NATIVE[n - 10]
    tens, ones = (n // 10) * 10, n % 10
    if tens in NATIVE_TENS:
        return NATIVE_TENS[tens] + (NATIVE[ones] if ones else "")
    return sino(n)


# Longest counter first: 시간 must beat 시, 번째 must beat 번, 개월 must beat 개.
# No trailing \W boundary — Korean particles (…을, …를, …이) are word characters, so
# requiring one would refuse to match the very sentences we care about.
COUNTERS = sorted(NATIVE_COUNTERS | SINO_COUNTERS, key=len, reverse=True)
NUMBER = re.compile(
    r"(?<![\w.])(\d[\d,]*)(?:\.(\d+))?\s*(" + "|".join(COUNTERS) + r")?(?!\d)"
)


def _sub(m: re.Match) -> str:
    whole, frac, counter = m.group(1).replace(",", ""), m.group(2), m.group(3)

    if frac:  # 3.2초 → 삼 점 이 초
        head = sino(int(whole)) + " 점 " + " ".join(SINO_DIGIT[int(d)] for d in frac)
        return f"{head} {counter}" if counter else head

    n = int(whole)
    if not counter:
        return sino(n)

    use_native = counter in NATIVE_COUNTERS and 1 <= n <= NATIVE_MAX
    return f"{native(n) if use_native else sino(n)} {counter}"


def normalize(text: str) -> str:
    """Digits → Hangul, so the engine never has to guess which number system."""
    return NUMBER.sub(_sub, text)


if __name__ == "__main__":
    CASES = [
        ("바로 3번 들어갈까요?", "바로 삼 번 들어갈까요?"),
        ("테스트 3개 통과했습니다.", "테스트 세 개 통과했습니다."),
        ("3번째 시도입니다.", "세 번째 시도입니다."),
        ("47번째 줄입니다.", "사십칠 번째 줄입니다."),
        ("빌드가 3.2초 걸렸습니다.", "빌드가 삼 점 이 초 걸렸습니다."),
        ("3분 남았습니다.", "삼 분 남았습니다."),
        ("3시간 걸립니다.", "세 시간 걸립니다."),
        ("파일 12개를 고쳤습니다.", "파일 열두 개를 고쳤습니다."),
        ("에이전트 20개를 띄웁니다.", "에이전트 스무 개를 띄웁니다."),
        ("커밋 1개 남았습니다.", "커밋 한 개 남았습니다."),
        ("2배 빨라졌습니다.", "두 배 빨라졌습니다."),
        ("3층에 있습니다.", "삼 층에 있습니다."),
        ("포트 7788을 씁니다.", "포트 칠천칠백팔십팔을 씁니다."),
        ("1,200원입니다.", "천이백 원입니다."),
    ]
    bad = 0
    for src, want in CASES:
        got = normalize(src)
        flag = "  " if got == want else "❌"
        bad += got != want
        print(f"{flag} {src}")
        print(f"   → {got}")
        if got != want:
            print(f"   기대: {want}")
    print(f"\n{len(CASES) - bad}/{len(CASES)} 통과")
