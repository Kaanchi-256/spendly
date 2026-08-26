(function () {
    var trigger = document.getElementById('how-it-works-btn');
    var overlay = document.getElementById('video-modal');
    var closeBtn = document.getElementById('video-modal-close');
    var iframe = document.getElementById('video-modal-iframe');
    var videoSrc = 'https://www.youtube.com/embed/dQw4w9WgXcQ';

    if (!trigger || !overlay || !closeBtn || !iframe) return;

    function openModal() {
        iframe.src = videoSrc + '?autoplay=1';
        overlay.hidden = false;
    }

    function closeModal() {
        overlay.hidden = true;
        iframe.src = '';
    }

    trigger.addEventListener('click', openModal);
    closeBtn.addEventListener('click', closeModal);

    overlay.addEventListener('click', function (event) {
        if (event.target === overlay) closeModal();
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && !overlay.hidden) closeModal();
    });
})();
