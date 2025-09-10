document.addEventListener("DOMContentLoaded", function () {
  const generateBtn = document.getElementById('generateLinkBtn');
  const toast = document.getElementById('toast');
  const input = document.getElementById('refLink');
  const refLinkContainer = document.getElementById('refLinkContainer');

  if (!generateBtn) return; // на всякий случай

  generateBtn.addEventListener('click', function () {
    const refLink = this.dataset.link;  // <-- ссылка из data-link
    input.value = window.location.origin + refLink;
    refLinkContainer.classList.remove('hidden');

    navigator.clipboard.writeText(input.value).then(() => {
      toast.classList.remove('opacity-0');
      toast.classList.add('opacity-100');
      setTimeout(() => {
        toast.classList.remove('opacity-100');
        toast.classList.add('opacity-0');
      }, 3000);
    });

    this.classList.add('hidden');
  });
});