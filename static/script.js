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

// 「その他のやること」を開いたか閉じたかを覚えておく（ボタンを押して一覧に戻っても同じ状態にする）
document.addEventListener("DOMContentLoaded", () => {
  const others = document.getElementById("others");
  if (!others) return;
  try {
    if (localStorage.getItem("othersOpen") === "1") others.open = true;
  } catch (e) {}
  others.addEventListener("toggle", () => {
    try {
      localStorage.setItem("othersOpen", others.open ? "1" : "0");
    } catch (e) {}
  });
});

// ブラウザの「戻る」で戻ってきたときに、ボタンを元に戻す
window.addEventListener("pageshow", (e) => {
  if (e.persisted) location.reload();
});
