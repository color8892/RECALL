document.addEventListener('DOMContentLoaded', () => {
    chrome.storage.local.get(['rpc_token'], (result) => {
        if (result.rpc_token) {
            document.getElementById('token').value = result.rpc_token;
        }
    });

    document.getElementById('save').addEventListener('click', () => {
        const token = document.getElementById('token').value.trim();
        const status = document.getElementById('status');
        if (!token) {
            status.textContent = '請先貼上 RECALL 主程式產生的 Token。';
            status.className = 'status error';
            return;
        }
        chrome.storage.local.set({ rpc_token: token }, () => {
            status.className = 'status';
            status.textContent = '設定已儲存！';
            setTimeout(() => { status.textContent = ''; }, 2000);
        });
    });
});
