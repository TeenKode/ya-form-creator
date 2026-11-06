// Opera documents launchWebAuthFlow, but may omit the getRedirectURL helper.
// The callback remains an extension-specific Chromium interception URL.
export function redirectURL(identity, runtimeId) {
  if (typeof identity?.getRedirectURL === 'function') return identity.getRedirectURL('oauth');
  if (!/^[a-p]{32}$/.test(runtimeId ?? '')) throw new Error('Не удалось определить адрес возврата расширения.');
  return `https://${runtimeId}.chromiumapp.org/oauth`;
}

export function launchAuthFlow(identity, runtime, options) {
  return new Promise((resolve, reject) => {
    if (typeof identity?.launchWebAuthFlow !== 'function') {
      reject(new Error('Этот браузер не поддерживает вход через расширение.'));
      return;
    }
    try {
      const result = identity.launchWebAuthFlow(options, url => {
        const error = runtime.lastError;
        if (error || !url) reject(new Error('Вход не завершён.'));
        else resolve(url);
      });
      // Some Chromium versions return a Promise; others use only the callback.
      if (result?.then) result.then(resolve, reject);
    } catch (error) { reject(error); }
  });
}
