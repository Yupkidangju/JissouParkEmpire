/**
 * 실장석 공원 제국 - 게임 스크립트 (game.js)
 * [v0.1.0] 타이핑 효과, 메시지 자동 소멸, 수치 강조 등
 */

document.addEventListener('DOMContentLoaded', () => {
    // === 메시지 자동 소멸 (10초 후) ===
    const messages = document.querySelectorAll('.msg');
    messages.forEach((msg, i) => {
        setTimeout(() => {
            msg.style.opacity = '0';
            msg.style.transform = 'translateX(10px)';
            msg.style.transition = 'all 0.5s';
            setTimeout(() => msg.remove(), 500);
        }, 8000 + i * 1000); // 순차적으로 사라짐
    });

    // === 솎아내기 확인 다이얼로그 ===
    const cullButtons = document.querySelectorAll('.btn-cull');
    cullButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const form = btn.closest('form');
            const target = form.querySelector('[name="target_type"]').value;
            const count = form.querySelector('[name="count"]').value;
            const targetName = target === 'baby' ? '저실장' : '자실장';
            const emoji = target === 'baby' ? '🐛' : '👶';

            if (!confirm(`${emoji} ${targetName} ${count}마리를 정말 솎아내겠는 데스?\n\n"마마... 안 되는 데스/테츄..."`)) {
                e.preventDefault();
            }
        });
    });

    // === 콘페이토 반짝임 효과 ===
    const konpeitoLine = document.querySelector('.konpeito-line strong');
    if (konpeitoLine && parseInt(konpeitoLine.textContent) > 0) {
        setInterval(() => {
            konpeitoLine.style.textShadow = '0 0 12px rgba(255, 215, 0, 0.8)';
            setTimeout(() => {
                konpeitoLine.style.textShadow = '0 0 4px rgba(255, 215, 0, 0.4)';
            }, 300);
        }, 3000);
    }

    // === AP 경고 깜빡임 ===
    const apCount = document.querySelector('.ap-count');
    if (apCount && parseInt(apCount.textContent) === 0) {
        apCount.style.animation = 'gameoverPulse 1.5s infinite';
        apCount.style.color = '#ff4444';
    }

    // === NPC 대사 타이핑 효과 ===
    const greeting = document.querySelector('.greeting-bar .npc-speech');
    if (greeting) {
        const fullText = greeting.textContent;
        greeting.textContent = '';
        greeting.style.visibility = 'visible';
        let i = 0;
        const typeInterval = setInterval(() => {
            if (i < fullText.length) {
                greeting.textContent += fullText.charAt(i);
                i++;
            } else {
                clearInterval(typeInterval);
            }
        }, 30);
    }

    // === 숫자 입력 최소값 방어 ===
    const numInputs = document.querySelectorAll('.num-input');
    numInputs.forEach(input => {
        input.addEventListener('change', () => {
            const min = parseInt(input.min) || 0;
            const max = parseInt(input.max) || 999;
            let val = parseInt(input.value) || 0;
            if (val < min) val = min;
            if (val > max) val = max;
            input.value = val;
        });
    });

    // === 건설 드롭다운: 건물 설명 표시 ===
    const buildSelect = document.getElementById('build-select');
    const buildDesc = document.getElementById('build-desc');
    const buildDescs = {
        'cardboard_house': '🏠 따뜻한 골판지집! 수용 인원 +15',
        'unchi_hole': '🕳️ 냄새가 지독하지만 유용! 저실장 수용 +10',
        'storage_hole': '📦 자원을 더 많이 보관! 콘페+25, 음쓰+100, 자재+50',
        'wall': '🧱 든든한 방벽! 방어력 20% 보너스',
        'watchtower': '🗼 적 전투력 정찰 가능!'
    };
    if (buildSelect && buildDesc) {
        const updateDesc = () => {
            const key = buildSelect.value;
            buildDesc.textContent = buildDescs[key] || '건물을 선택하세요';
        };
        buildSelect.addEventListener('change', updateDesc);
        updateDesc(); // 초기 설명 표시
    }

    // === 침공 버튼 확인 다이얼로그 ===
    const attackBtns = document.querySelectorAll('.btn-attack-sm');
    attackBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const row = btn.closest('tr');
            const parkName = row ? row.querySelector('td').textContent.trim() : '???';
            if (!confirm(`⚔️ ${parkName} 공원을 침공하겠는 데스?!\n\n2AP를 소비합니다.`)) {
                e.preventDefault();
            }
        });
    });
});
