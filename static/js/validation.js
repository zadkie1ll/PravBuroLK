document.addEventListener('DOMContentLoaded', () => {
    const phoneInput = document.getElementById('phone');

    phoneInput.addEventListener('input', () => {
        let val = phoneInput.value;

        // убираем все пробелы и скобки
        val = val.replace(/\D/g, '');

        if (val.startsWith('8')) {
            val = '+7' + val.slice(1);
        } else if (!val.startsWith('7') && !val.startsWith('+7')) {
            val = '+7' + val;
        } else if (val.startsWith('7')) {
            val = '+7' + val.slice(1);
        }

        // ограничиваем длину до +7 + 10 цифр
        if (val.length > 12) {
            val = val.slice(0, 12);
        }

        phoneInput.value = val;
    });
});