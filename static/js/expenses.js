// expenses.js — confirm before a delete-expense form is submitted.

document.querySelectorAll('.expenses-delete-form, .edit-delete-form')
    .forEach(function (form) {
        form.addEventListener('submit', function (e) {
            if (!window.confirm('Delete this expense? This cannot be undone.')) {
                e.preventDefault();
            }
        });
    });
