@ 록맨 ZX 어드벤트 한글 훅 (ARMv5TE Thumb). zxhook.s 와 같고 F0 사슬(F0 FF.. xx, FF 마다 +0xFF)만 다르다.
@ 부팅 때 ARM9 autoload 로 HOOK_BASE 에 올라간다.
@ 기호: HDR, FONT, FABUF, KRTAB, TOGGLE, SCR0
@
@ 인코딩: 0x40~0x4F 리드 + 둘째 바이트(0x00~0xEF) -> 한글 코드 (리드-0x40)*240+둘째.
@ 한글 글리프는 압축(16바이트/자)해 상주: 한국어판에서 안 쓰는 font_jp.bin 글리프 칸들(폰트 파일에 포함되므로
@ 다시 읽혀도 복원)과 이 구역 뒤 빈 공간(~0x0219C000). 출력할 때 임시 칸에 풀어서 그린다.
@ 파일 읽기 금지: 서브 화면 문자열은 파일 로딩 콜백 안에서 그려져 동기 FS 호출이 화면을 깨뜨렸다(11/16 실측).
@ 아레나 뒤 0x0219C000 부터는 게임이 고정 버퍼로 쓴다(실측).
@ 폰트 헤더 폭이 12가 아니면(font_pal 등 다른 글꼴) 리드·폭 처리를 하지 않는다.
@ 글자 폭 = 글리프 0행 u16 의 위 4비트(0이면 12).

    .thumb
@ ---------------------------------------------------------------------------
@ 출력기 0x02080042 에서 bl. r0 = 현재 바이트, r1 = 출력기 프레임 sp.
@ 돌려줌: r1=1 이면 r0 = 글리프 번호(포인터는 마지막 바이트에), r1=0 이면 제어(r0 그대로).
hook_render:
    push {r4-r7, lr}
    mov r4, r1
    cmp r0, #0xf0
    beq 3f
    bhi 8f
    ldr r2, =HDR
    ldrh r2, [r2]
    cmp r2, #12
    bne 7f                  @ 다른 글꼴(font_pal 등): 원래 동작
    cmp r0, #0x40
    blo 5f
    cmp r0, #0x4f
    bhi 5f
    ldr r2, [r4, #0xc]
    ldrb r1, [r2, #1]
    cmp r1, #0xf0
    bhs 5f                  @ 둘째 바이트가 제어/종료면 리드가 아니다(일본어 가나 그대로)
    adds r2, #1
    str r2, [r4, #0xc]
    subs r0, #0x40
    movs r2, #240
    muls r0, r2
    adds r0, r0, r1
    bl kr_glyph
    b 5f
3:  ldr r2, [r4, #0xc]
    movs r0, #0xf0
31: adds r2, #1
    ldrb r1, [r2]
    adds r0, r0, r1
    cmp r1, #0xff
    beq 31b
    str r2, [r4, #0xc]
    ldr r2, =HDR
    ldrh r2, [r2]
    cmp r2, #12
    bne 7f
5:  ldr r1, =FONT
    lsls r2, r0, #5
    ldrh r2, [r1, r2]
    lsrs r2, r2, #12
    bne 6f
    movs r2, #12
6:  str r2, [r4, #0x18]
    movs r2, #2
    str r2, [r4, #0x50]
7:  movs r1, #1
    pop {r4-r7, pc}
8:  movs r1, #0
    pop {r4-r7, pc}

@ ---------------------------------------------------------------------------
@ r0 = 한글 코드 k -> r0 = 임시 칸 글리프 번호. 압축 글리프(16바이트: 11행 x 11비트, LSB 먼저)를
@ 영역 표(KRTAB: [주소, 글자 수]...)에서 찾아 임시 칸 2개(SCR0, SCR0+1)에 번갈아 풀어 둔다.
kr_glyph:
    push {r4-r7, lr}
    ldr r4, =KRTAB
1:  ldr r1, [r4, #4]
    cmp r0, r1
    blo 2f
    subs r0, r0, r1
    adds r4, #8
    b 1b
2:  ldr r5, [r4]
    lsls r0, r0, #4
    adds r5, r5, r0         @ r5 = 압축 데이터
    ldr r1, =TOGGLE
    ldrb r6, [r1]
    movs r2, #1
    eors r6, r2
    strb r6, [r1]
    ldr r1, =SCR0
    adds r6, r6, r1         @ r6 = 임시 칸 번호
    lsls r7, r6, #5
    ldr r1, =FONT
    adds r7, r7, r1         @ r7 = 임시 칸 주소
    ldr r1, =0xC000         @ 0행: 폭 12
    strh r1, [r7]
    movs r1, #0
    strh r1, [r7, #2]
    strh r1, [r7, #26]
    strh r1, [r7, #28]
    strh r1, [r7, #30]
    adds r7, #4             @ 2행부터
    movs r2, #0             @ 비트 위치
    movs r3, #11            @ 남은 행
3:  movs r0, #0             @ 행 값
    movs r4, #0             @ x
4:  lsrs r1, r2, #3
    ldrb r1, [r5, r1]
    push {r2}
    lsls r2, r2, #29
    lsrs r2, r2, #29
    lsrs r1, r1, r2
    pop {r2}
    movs r6, #1
    ands r1, r6
    lsls r1, r1, r4
    orrs r0, r1
    adds r2, #1
    adds r4, #1
    cmp r4, #11
    blo 4b
    strh r0, [r7]
    adds r7, #2
    subs r3, #1
    bne 3b
    ldr r1, =TOGGLE
    ldrb r0, [r1]
    ldr r1, =SCR0
    adds r0, r0, r1
    pop {r4-r7, pc}

@ ---------------------------------------------------------------------------
@ 0x02080464 대체: r0 = 문자열, r1 = n -> n 글자 뒤 포인터
skip_impl:
    cmp r1, #0
    beq 9f
1:  ldrb r2, [r0]
    cmp r2, #0xfd
    bhs 9f
    cmp r2, #0xf0
    bls 3f
    cmp r2, #0xf8
    bhi 2f
    adds r0, #1
    b 5f
2:  cmp r2, #0xf9
    bne 5f
    adds r0, #2
    b 5f
3:  cmp r1, #0
    beq 9f
    cmp r2, #0xf0
    beq 4f
    ldr r3, =HDR
    ldrh r3, [r3]
    cmp r3, #12
    bne 6f
    movs r3, r2
    subs r3, #0x40
    cmp r3, #0xf
    bhi 6f
    ldrb r3, [r0, #1]
    cmp r3, #0xf0
    bhs 6f
4:  adds r0, #1
    ldrb r3, [r0]
    cmp r3, #0xff
    beq 4b
6:  subs r1, #1
5:  adds r0, #1
    b 1b
9:  bx lr

@ ---------------------------------------------------------------------------
@ 0x02080510 대체: r0 = 문자열 -> 글자 수(s16). FA 는 FABUF 를 재귀로 센다.
count_impl:
    push {r4, r5, lr}
    mov r5, r0
    movs r4, #0
1:  ldrb r0, [r5]
    cmp r0, #0xfd
    bhs 9f
    cmp r0, #0xf0
    bhi 3f
    adds r4, #1
    cmp r0, #0xf0
    beq 2f
    ldr r1, =HDR
    ldrh r1, [r1]
    cmp r1, #12
    bne 8f
    movs r1, r0
    subs r1, #0x40
    cmp r1, #0xf
    bhi 8f
    ldrb r1, [r5, #1]
    cmp r1, #0xf0
    bhs 8f
2:  adds r5, #1
    ldrb r1, [r5]
    cmp r1, #0xff
    beq 2b
    b 8f
3:  cmp r0, #0xf8
    bhi 4f
    adds r5, #1
    b 8f
4:  cmp r0, #0xf9
    bne 5f
    adds r5, #2
    b 8f
5:  cmp r0, #0xfa
    bne 8f
    ldr r0, =FABUF
    bl count_impl
    adds r4, r4, r0
8:  adds r5, #1
    b 1b
9:  lsls r0, r4, #16
    asrs r0, r0, #16
    pop {r4, r5, pc}
    .ltorg
    .align 2
KRTAB:
    .word KRTAB_WORDS
TOGGLE:
    .word 0
