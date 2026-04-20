let windowId = null;

chrome.action.onClicked.addListener(() => {
  // 이미 창이 열려있으면 앞으로 가져오기
  if (windowId !== null) {
    chrome.windows.get(windowId, (win) => {
      if (chrome.runtime.lastError || !win) {
        openWindow();
      } else {
        chrome.windows.update(windowId, { focused: true });
      }
    });
  } else {
    openWindow();
  }
});

function openWindow() {
  chrome.windows.create(
    {
      url: chrome.runtime.getURL('popup.html'),
      type: 'popup',
      width: 560,
      height: 820,
    },
    (win) => {
      windowId = win.id;
    }
  );
}

chrome.windows.onRemoved.addListener((id) => {
  if (id === windowId) windowId = null;
});
