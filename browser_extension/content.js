// 負責網頁內容擷取與變化監控 (Content Script)

(function() {
    let lastUrl = location.href;
    let lastContent = "";
    let debounceTimer = null;

    // 取得網頁正文並過濾雜訊
    function getCleanContent() {
        try {
            const body = document.body.cloneNode(true);
            const removes = ['script', 'style', 'nav', 'footer', 'header', 'iframe', 'noscript', 'video', 'audio'];
            removes.forEach(s => body.querySelectorAll(s).forEach(e => e.remove()));
            return body.innerText.replace(/\s+/g, ' ').trim();
        } catch (e) { return ""; }
    }

    // 傳送網頁資訊給 Background Script
    function sendToRecall() {
        const currentUrl = location.href;
        const currentContent = getCleanContent();
        
        // 只有在網址變更或內容顯著變化時才傳送
        if (currentUrl === lastUrl && Math.abs(currentContent.length - lastContent.length) < 50) return;

        lastUrl = currentUrl;
        lastContent = currentContent;

        chrome.runtime.sendMessage({
            action: "SEND_TO_PYTHON",
            payload: {
                title: document.title,
                url: currentUrl,
                content: currentContent.substring(0, 3000)
            }
        });
    }

    // 防抖處理 (避免頻繁觸發)
    function debouncedSendToRecall() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(sendToRecall, 3000);
    }

    // 監聽網頁 DOM 變化 (MutationObserver)
    const observer = new MutationObserver(() => debouncedSendToRecall());
    if (document.body) {
        observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    } else {
        document.addEventListener('DOMContentLoaded', () => {
            observer.observe(document.body, { childList: true, subtree: true, characterData: true });
        });
    }

    // 處理單頁面應用 (SPA) 路由變化
    window.addEventListener("popstate", debouncedSendToRecall);
    (function(history){
        const pushState = history.pushState;
        history.pushState = function() {
            const ret = pushState.apply(history, arguments);
            window.dispatchEvent(new Event('locationchange'));
            return ret;
        };
        const replaceState = history.replaceState;
        history.replaceState = function() {
            const ret = replaceState.apply(history, arguments);
            window.dispatchEvent(new Event('locationchange'));
            return ret;
        };
    })(window.history);

    window.addEventListener('locationchange', debouncedSendToRecall);

    // 初始化執行
    sendToRecall();
})();
