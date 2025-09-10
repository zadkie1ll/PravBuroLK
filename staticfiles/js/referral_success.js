document.addEventListener('DOMContentLoaded', () => {
    const circle = document.getElementById('check-circle');
    const check = circle.querySelector('svg');
    const text = document.getElementById('success-text');

    // Анимация круга
    setTimeout(() => {
        circle.classList.remove('scale-0', 'opacity-0');
        circle.classList.add('scale-100', 'opacity-100', 'transition', 'duration-700', 'ease-out');
    }, 200);

    // Анимация галочки
    setTimeout(() => {
        check.classList.remove('scale-0', 'opacity-0');
        check.classList.add('scale-100', 'opacity-100', 'transition', 'duration-500', 'ease-out');
    }, 900);

    // Анимация текста
    setTimeout(() => {
        text.classList.remove('opacity-0');
        text.classList.add('opacity-100', 'transition', 'duration-700', 'ease-out');
    }, 1200);
});