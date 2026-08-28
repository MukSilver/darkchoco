# vendor

외부 CDN을 쓰지 않습니다. 오프라인 시연에서 화면이 떠야 하므로 저장소에 넣습니다.

| 파일 | 무엇 | 출처 |
| --- | --- | --- |
| `three.module.min.js` | three.js r180 본체 | unpkg `three@0.180.0/build/` |
| `three.core.min.js` | 위가 참조하는 코어 | 같음 |
| `OrbitControls.js` | 궤도 조작 (import 경로만 고침) | `three@0.180.0/examples/jsm/controls/` |

합계 약 748KB. 라이선스 MIT.

**왜 three.js 인가.** 지도만 씁니다. 회전하는 두 층 판에 실제 조명과 그림자를 넣으려면
Canvas 2D 평면 셰이딩으로는 흉내만 낼 수 있고 만들 수는 없습니다.
직교(orthographic) 카메라를 쓰므로 「면적 = 사고 수」 약속은 회전해도 지켜집니다.

가이드라인과 첫 화면은 three.js 를 읽지 않습니다.
