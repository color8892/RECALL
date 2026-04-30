const RECALL_SERVER_URL = "http://127.0.0.1:8085/capture";
let optionsOpening = false;

function openOptionsOnce() {
    if (optionsOpening) return;
    optionsOpening = true;
    chrome.runtime.openOptionsPage(() => {
        setTimeout(() => { optionsOpening = false; }, 3000);
    });
}

chrome.runtime.onInstalled.addListener(() => {
    chrome.storage.local.get(["rpc_token"], (result) => {
        if (!result.rpc_token) openOptionsOnce();
    });
});

chrome.runtime.onMessage.addListener((message) => {
    if (message.action !== "SEND_TO_PYTHON") return;

    chrome.storage.local.get(["rpc_token"], (result) => {
        const token = result.rpc_token;
        if (!token) {
            openOptionsOnce();
            return; 
        }
        
        fetch(RECALL_SERVER_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-RECALL-Token": token
            },
            body: JSON.stringify(message.payload),
        }).catch(err => console.log("RECALL Server error:", err));
    });
});
