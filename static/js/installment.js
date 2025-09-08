document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("#installments button[data-amount]").forEach(button => {
    button.addEventListener("click", () => {
      if (!button.disabled) {
        const amount = button.getAttribute("data-amount");
        alert(`Оплата на сумму ${amount} ₽ будет проведена (здесь будет интеграция с платёжкой).`);
      }
    });
  });
});