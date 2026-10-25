// フォームを送ったら、ボタンを「処理中…」にして二重送信を防ぐ
document.addEventListener("submit", (e) => {
  // 削除の確認で「キャンセル」を押したときは何もしない
  if (e.defaultPrevented) return;

  const form = e.target;
  if (form.dataset.sending) {
    e.preventDefault();
    return;
  }
  form.dataset.sending = "1";

  const button = e.submitter || form.querySelector("button");
  if (button) {
    button.textContent = "処理中…";
    button.disabled = true;
  }
});

// ブラウザの「戻る」で戻ってきたときに、ボタンを元に戻す
window.addEventListener("pageshow", (e) => {
  if (e.persisted) location.reload();
});
