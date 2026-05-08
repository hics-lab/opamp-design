# SPICE 실습 페이지 개발 Spec

새 세션에서 이 문서를 읽고 새로운 "SPICE 실습 페이지"를 구현한다. 기존 [opamp_design.html](opamp_design.html)(파라미터화된 5T OTA 전용 툴)과는 별개의 페이지이며, 학생이 **자유롭게 netlist를 작성하고 시뮬레이션 결과를 확인**하는 sandbox형 실습 도구다.

---

## 1. 목표

- 학생이 직접 SPICE netlist를 작성·수정·시뮬레이션하는 브라우저 기반 실습 페이지
- 시뮬레이션 엔진: **ngspice WASM** (이미 [ngspice.js](ngspice.js), [ngspice.wasm](ngspice.wasm) 보유)
- PDK 모델: **ETRI 0.5μm BSIM3v3** (root에 [etri_mos.lib](etri_mos.lib), 또는 기존 코드와 동일하게 HTML 내 상수로 임베드)
- 지원 해석: **`.tran`, `.dc`, `.ac`, `.noise`** 4가지

---

## 2. 파일 위치 / 이름

- **추천 경로**: `practice.html` (root)
- 이유: [opamp_design.html](opamp_design.html), [ngspice.js](ngspice.js), [ngspice.wasm](ngspice.wasm)이 모두 root에 있고, 새 페이지도 동일 root에 두면 ngspice WASM 로딩 경로 로직(`baseUrl = window.location.href`)을 그대로 재사용 가능

---

## 3. 레이아웃

좌우 2-pane 분할. 권장 비율 `1fr : 1.4fr` (기존 [opamp_design.html](opamp_design.html)의 결과 패널 비율과 동일).

```
┌────────────────────────────────────────────────────────────────────────┐
│ Header: SPICE 실습 페이지 | ETRI 0.5μm BSIM3v3 | [예제 로드 ▼] [도움말]  │
├──────────────────────────────────┬─────────────────────────────────────┤
│ LEFT (1fr)                       │ RIGHT (1.4fr)                        │
│                                  │                                      │
│ ┌────────────────────────────┐  │ ┌─────────────────────────────────┐  │
│ │ [▶ Run]  [Stop]  [Clear]   │  │ │ [Tran] [DC] [AC] [Noise] [Log] │  │
│ │ status: idle / running /   │  │ ├─────────────────────────────────┤  │
│ │         done (123 ms)      │  │ │                                 │  │
│ └────────────────────────────┘  │ │   <선택된 탭의 결과 차트/표>    │  │
│                                  │ │                                 │  │
│ ┌────────────────────────────┐  │ │   - 차트: Chart.js 또는         │  │
│ │ Netlist editor             │  │ │     기존 코드처럼 Canvas 직접   │  │
│ │ (textarea / CodeMirror)    │  │ │     그리기                      │  │
│ │                            │  │ │   - X/Y 축 라벨 자동 (해석별)   │  │
│ │ * 학생이 작성              │  │ │   - 다중 trace 색상 분리         │  │
│ │ .lib "/model.lib" MOS      │  │ │   - 마우스 호버 시 값 표시       │  │
│ │ V1 ...                     │  │ │                                 │  │
│ │ M1 ...                     │  │ │                                 │  │
│ │ .tran 1n 1u                │  │ └─────────────────────────────────┘  │
│ │ .end                       │  │                                      │
│ └────────────────────────────┘  │ [데이터 export: CSV]                 │
│                                  │                                      │
│ stdout/stderr (접이식):          │                                      │
│ ┌────────────────────────────┐  │                                      │
│ │ ngspice 로그...            │  │                                      │
│ └────────────────────────────┘  │                                      │
└──────────────────────────────────┴─────────────────────────────────────┘
```

---

## 4. 동작 모델 (중요)

**단일 Run 버튼 + 탭은 결과 dispatch 용도.**

- 학생은 netlist에 `.tran`, `.dc`, `.ac`, `.noise` 중 원하는 만큼 직접 작성 (여러 개 가능)
- Run 버튼 누르면 ngspice가 한 번 실행되어 모든 해석을 순차 수행
- 각 해석 결과를 별도 파일로 dump → JS에서 읽어 해당 탭에 표시
- 해당 탭에 데이터가 없으면 "이 해석은 netlist에 없습니다" 안내

**왜 이 방식인가**: SPICE의 자연스러운 사용 방식과 일치. 학생이 `.control ... .endc` 블록 작성을 학습하게 됨. "버튼별 분리"보다 교육 가치가 높다.

### Run 버튼 클릭 시 처리 흐름

1. Editor에서 netlist 텍스트 추출
2. 자동 보정: 학생이 `.control` 블록을 안 썼으면 분석 종류 자동 검출 후 wrapper 추가:
   ```
   .control
   run
   <검출된 해석마다> wrdata /tran.txt all
                    wrdata /dc.txt all
                    wrdata /ac.txt all
                    wrdata /noise.txt inoise_total onoise_total
   quit
   .endc
   ```
3. Web Worker에서 ngspice 실행 (기존 [opamp_design.html:1987-2050](opamp_design.html#L1987) 패턴 그대로)
4. postRun에서 4개 파일 각각 `FS.readFile` 시도 → 있는 것만 parsing
5. 각 탭에 데이터 dispatch, stdout은 Log 탭에 표시

---

## 5. 탭별 결과 표시 사양

| 탭 | X축 | Y축 | 비고 |
|---|---|---|---|
| **Tran** | time (s, log/lin 토글) | V/I (lin) | `.tran` 결과. multi-trace 지원 |
| **DC** | sweep var (lin) | V/I | `.dc` 결과. 1D sweep 우선, nested sweep은 후순위 |
| **AC** | freq (log) | mag (dB) + phase (deg) | Bode plot 2개 sub-chart |
| **Noise** | freq (log) | $\sqrt{\text{V}^2/\text{Hz}}$ (log) | input/output noise spectral density |
| **Log** | — | — | ngspice stdout/stderr 전체. 디버깅용 |

차트 라이브러리: 기존 코드는 Canvas 직접 그리기 사용 ([opamp_design.html:1277](opamp_design.html#L1277) 부근). 새 페이지에서는 Chart.js 도입도 검토 가능 — **새 세션에서 사용자에게 확인 필요**.

---

## 6. ngspice WASM 통합 (기존 코드 재사용)

기존 [opamp_design.html:1987-2050](opamp_design.html#L1987)의 Web Worker 패턴을 그대로 가져온다:

```js
const baseUrl = (() => {
  const href = window.location.href;
  return href.substring(0, href.lastIndexOf('/') + 1);
})();

const workerCode = `
self.onmessage = function(e) {
  var netlist = e.data.netlist, model = e.data.model;
  self.Module = {
    locateFile: function(p) { return '${baseUrl}' + p; },
    arguments: ['-b', '/sim.cir'],
    preRun: [function() {
      FS.writeFile('/sim.cir', netlist);
      FS.writeFile('/model.lib', model);
    }],
    print: function(t) { /* stdout 수집 */ },
    printErr: function(t) { /* stderr 수집 */ },
    postRun: [function() {
      var out = {};
      ['/tran.txt','/dc.txt','/ac.txt','/noise.txt'].forEach(function(p) {
        try { out[p] = FS.readFile(p, {encoding: 'utf8'}); } catch(e) {}
      });
      self.postMessage({type: 'done', files: out, log: collectedLog});
    }]
  };
  importScripts('${baseUrl}ngspice.js');
};`;
```

### 주의사항

- `/model.lib`은 ngspice WASM의 가상 파일시스템 경로. `FS.writeFile`로 미리 써두면 netlist에서 `.lib "/model.lib" MOS`로 참조 가능
- 모델 데이터 소스: 기존 `ETRI_LIB` 상수 ([opamp_design.html:1736-1761](opamp_design.html#L1736))를 그대로 복사하거나, 더 좋게는 별도 `.js` 파일로 추출해서 두 페이지가 공유
- **권장**: `etri_lib.js` 파일을 만들어 `window.ETRI_LIB = "..."`로 export, 두 HTML이 `<script src="etri_lib.js">`로 로드. 이 작업은 새 페이지 구현 시 선택 사항 (작업량이 늘면 일단 복사로 시작)

---

## 7. wrdata 결과 parsing

기존 [opamp_design.html:1939](opamp_design.html#L1939) `parseWrdata()` 함수의 패턴을 재사용. ngspice `wrdata` 형식:

- 변수 N개 → 2N열 (`x y1 x y2 ... x yN`, x열이 반복됨)
- 빈 줄 / `*` 시작 줄은 주석
- 각 행은 공백 구분 숫자

해석별 추가 처리:

- **AC**: ngspice는 `wrdata` 시 복소수를 `real imag` 두 컬럼으로 dump → `mag = sqrt(re² + im²)`, `phase = atan2(im, re) * 180/π` 계산 필요
- **Noise**: `inoise_spectrum`, `onoise_spectrum` 벡터를 `wrdata`로 dump
- **Tran/DC**: 그대로 사용

---

## 8. Critical 주의사항

### 8-1. Noise 시뮬레이션의 신뢰도 (반드시 UI에 명시)

**ETRI PDK MOS 모델에 noise 파라미터(NOIA/NOIB/NOIC/KF/AF/EF) 가 전혀 없다.** ngspice는 default 값(`KF=0`)으로 동작하므로:

- **Thermal noise**: 모델 물리식으로 자동 계산 → 신뢰 가능
- **Flicker (1/f) noise**: 사실상 0으로 나옴 → 저주파 input-referred noise는 **실제보다 수십~수백 배 낮게** 출력됨

Noise 탭에는 다음 배너를 항상 표시:
> 경고: ETRI 0.5μm 모델은 1/f noise 파라미터를 포함하지 않습니다. 본 결과는 thermal noise만 반영되어 저주파에서 실제값보다 크게 낮습니다.

선택적 기능으로 "1/f noise 파라미터 주입" 토글 제공 가능 (체크 시 NOIA/NOIB/NOIC를 0.5μm 일반값으로 모델에 추가하여 사용). 새 세션 시작 시 사용자에게 이 토글 필요 여부 확인 권장.

### 8-2. 실행 시간 / 무한루프 방지

- ngspice 실행에 timeout (예: 30초) 걸기. 초과 시 worker.terminate()
- AC sweep을 너무 광대역으로 잡으면 오래 걸림 → status에 진행 중 표시 필수

### 8-3. 보안: code injection

- Netlist는 ngspice WASM 안에서만 동작하므로 host 시스템에 영향 없음 (sandbox)
- 하지만 stdout/log를 `innerHTML`로 표시하면 XSS 가능 → 반드시 `textContent` 사용

---

## 9. 예제 netlist 프리셋 (Header의 "예제 로드" 드롭다운)

학생이 곧바로 시작할 수 있도록 예제 4종 내장:

1. **RC low-pass (.tran + .ac)** — SPICE 입문용
2. **NMOS common-source amp (.dc + .ac)** — small-signal 학습
3. **5T OTA (.dc + .ac + .noise)** — 기존 [5T_OTA/samples/5T_OTA_vicm_sweep.cir](5T_OTA/samples/5T_OTA_vicm_sweep.cir) 변형
4. **Diff pair tail current (.dc Vicm sweep)** — 동작점 분석 학습

각 예제는 JS 객체 배열로 정의하고, 드롭다운 선택 시 editor에 로드.

---

## 10. 새 세션 시작 시 사용자에게 확인할 것

새 세션 시작 시 implementation 시작 전에 다음 4가지를 한 번에 묻기 (AskUserQuestion):

1. **Editor**: 단순 `<textarea>` vs CodeMirror 도입 (CodeMirror가 syntax highlighting/줄번호 좋지만 dependency 추가)
2. **Chart**: Canvas 직접 (기존 코드 패턴 일관성) vs Chart.js (개발 빠름, 인터랙션 좋음)
3. **Noise 1/f 주입 토글**: 포함할지 여부
4. **모델 파일 공유 방식**: HTML에 복사 임베드 (간단) vs 별도 `etri_lib.js` 추출 후 양쪽 페이지에서 공유 (DRY)

---

## 11. 구현 순서 권장

1. Skeleton HTML/CSS — 좌우 분할 + 탭 + Run 버튼
2. ngspice 통합 + Run 동작 (Log 탭만 우선) — 동작 검증
3. wrdata parsing 유틸 — Tran 탭부터 가장 간단
4. DC 탭 (Tran과 거의 동일)
5. AC 탭 — 복소수 처리, dual sub-chart (mag/phase)
6. Noise 탭 + 경고 배너
7. 예제 프리셋 드롭다운
8. CSV export
9. 폴리시: status 표시, timeout, error 메시지

---

## 12. 참고 파일 인덱스

| 자산 | 경로 | 용도 |
|---|---|---|
| ngspice WASM | [ngspice.js](ngspice.js), [ngspice.wasm](ngspice.wasm) | 시뮬레이션 엔진 |
| MOS 모델 (전체) | [etri_mos.lib](etri_mos.lib) | PDK MOS 섹션 (참고용) |
| MOS 모델 (인라인 상수) | [opamp_design.html:1736-1761](opamp_design.html#L1736) | HTML에 임베드된 형태 (복사 권장) |
| ngspice Worker 패턴 | [opamp_design.html:1987-2050](opamp_design.html#L1987) | 그대로 재사용 |
| wrdata parser | [opamp_design.html:1939](opamp_design.html#L1939) | parseWrdata() 재사용 |
| Canvas 차트 패턴 | [opamp_design.html:1277](opamp_design.html#L1277) 부근 | Canvas 사용 시 참고 |
| 기존 5T OTA 페이지 | [opamp_design.html](opamp_design.html) | 스타일/UI 패턴 참고 |
| 5T OTA 샘플 netlist | [5T_OTA/samples/5T_OTA_vicm_sweep.cir](5T_OTA/samples/5T_OTA_vicm_sweep.cir) | 예제 프리셋 베이스 |
| PDK 전체 (참고) | [Model_Parameter/](Model_Parameter/), [NSPL_05CMOS_PDK_260224/](NSPL_05CMOS_PDK_260224/) | DIODE/BJT/RES/CAP 모델 필요 시 |
