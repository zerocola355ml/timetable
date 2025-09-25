/**
 * 웹브라우저 콘솔 디버깅 메시지 제어 시스템
 * 개발 환경과 운영 환경에서 콘솔 메시지를 선택적으로 출력할 수 있습니다.
 */

// 전역 디버깅 설정
window.DEBUG_CONFIG = {
    // 기본 설정 (환경변수나 서버에서 설정 가능)
    enabled: false,  // 기본값: 비활성화
    level: 'info',   // debug, info, warn, error
    showTimestamp: true,
    showModule: true
};

// 디버깅 레벨 정의
const DEBUG_LEVELS = {
    debug: 0,
    info: 1,
    warn: 2,
    error: 3
};

/**
 * 디버깅 메시지 출력 함수
 * @param {string} level - 로그 레벨 (debug, info, warn, error)
 * @param {string} module - 모듈명 (선택사항)
 * @param {...any} args - 출력할 메시지들
 */
function debugLog(level, module, ...args) {
    // 디버깅이 비활성화된 경우 아무것도 출력하지 않음
    if (!window.DEBUG_CONFIG.enabled) {
        return;
    }
    
    // 레벨 체크 (설정된 레벨보다 낮은 레벨은 출력하지 않음)
    const currentLevel = DEBUG_LEVELS[window.DEBUG_CONFIG.level] || DEBUG_LEVELS.info;
    const messageLevel = DEBUG_LEVELS[level] || DEBUG_LEVELS.info;
    
    if (messageLevel < currentLevel) {
        return;
    }
    
    // 타임스탬프 추가
    let prefix = '';
    if (window.DEBUG_CONFIG.showTimestamp) {
        const timestamp = new Date().toLocaleTimeString();
        prefix += `[${timestamp}] `;
    }
    
    // 모듈명 추가
    if (window.DEBUG_CONFIG.showModule && module) {
        prefix += `[${module}] `;
    }
    
    // 레벨별 출력
    const consoleMethod = console[level] || debugInfo;
    consoleMethod(prefix + args.join(' '), ...args);
}

/**
 * 편의 함수들
 */
window.debug = (...args) => debugLog('debug', null, ...args);
window.debugInfo = (...args) => debugLog('info', null, ...args);
window.debugWarn = (...args) => debugLog('warn', null, ...args);
window.debugError = (...args) => debugLog('error', null, ...args);

// 모듈별 디버깅 함수들
window.debugModule = (module) => ({
    debug: (...args) => debugLog('debug', module, ...args),
    info: (...args) => debugLog('info', module, ...args),
    warn: (...args) => debugLog('warn', module, ...args),
    error: (...args) => debugLog('error', module, ...args)
});

/**
 * 디버깅 설정 변경 함수
 * @param {Object} config - 새로운 설정
 */
window.setDebugConfig = function(config) {
    Object.assign(window.DEBUG_CONFIG, config);
    debugLog('info', 'DEBUG', `디버깅 설정이 변경되었습니다:`, window.DEBUG_CONFIG);
};

/**
 * 디버깅 활성화/비활성화 함수
 * @param {boolean} enabled - 활성화 여부
 */
window.setDebugEnabled = function(enabled) {
    window.DEBUG_CONFIG.enabled = enabled;
    debugLog('info', 'DEBUG', `디버깅이 ${enabled ? '활성화' : '비활성화'}되었습니다`);
};

/**
 * 디버깅 레벨 설정 함수
 * @param {string} level - 로그 레벨 (debug, info, warn, error)
 */
window.setDebugLevel = function(level) {
    if (DEBUG_LEVELS.hasOwnProperty(level)) {
        window.DEBUG_CONFIG.level = level;
        debugLog('info', 'DEBUG', `디버깅 레벨이 ${level}로 설정되었습니다`);
    } else {
        console.warn('유효하지 않은 디버깅 레벨:', level);
    }
};

/**
 * 디버깅 상태 확인 함수
 */
window.getDebugStatus = function() {
    return {
        enabled: window.DEBUG_CONFIG.enabled,
        level: window.DEBUG_CONFIG.level,
        config: { ...window.DEBUG_CONFIG }
    };
};

/**
 * 모든 디버깅 메시지 출력 함수 (디버깅 설정과 무관하게 항상 출력)
 */
window.debugForce = {
    log: (...args) => debugInfo('[FORCE]', ...args),
    info: (...args) => console.info('[FORCE]', ...args),
    warn: (...args) => console.warn('[FORCE]', ...args),
    error: (...args) => console.error('[FORCE]', ...args)
};

// 초기화 완료 메시지
console.log('🔧 웹브라우저 디버깅 시스템이 로드되었습니다.');
console.log('사용법:');
console.log('  - setDebugEnabled(true/false): 디버깅 활성화/비활성화');
console.log('  - setDebugLevel("debug"/"info"/"warn"/"error"): 로그 레벨 설정');
console.log('  - debug("메시지"): 디버깅 메시지 출력');
console.log('  - debugModule("모듈명").info("메시지"): 모듈별 디버깅 메시지');
console.log('  - getDebugStatus(): 현재 디버깅 상태 확인');
console.log('  - toggleDebug(): 디버깅 켜기/끄기 토글');
console.log('');
console.log('💡 빠른 사용법:');
console.log('  toggleDebug()           // 디버깅 켜기/끄기');
console.log('  setDebugLevel("debug")   // 모든 메시지 보기');
console.log('  setDebugLevel("info")    // 정보만 보기');
console.log('  getDebugStatus()         // 현재 상태 확인');
