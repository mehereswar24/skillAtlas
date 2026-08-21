const openButton = document.getElementById('open');
const modal = document.getElementById('modal');
const closeButton = document.getElementById('close');
const panel = modal.querySelector('.panel');

let previouslyFocused = null;

function focusable() {
  return [...panel.querySelectorAll('input, button')];
}

function openModal() {
  previouslyFocused = document.activeElement;
  modal.hidden = false;
  focusable()[0].focus();
}

function closeModal() {
  modal.hidden = true;
  if (previouslyFocused) previouslyFocused.focus();
}

openButton.addEventListener('click', openModal);
closeButton.addEventListener('click', closeModal);

document.addEventListener('keydown', (event) => {
  if (modal.hidden) return;

  if (event.key === 'Escape') {
    closeModal();
    return;
  }
  if (event.key !== 'Tab') return;

  const elements = focusable();
  const first = elements[0];
  const last = elements[elements.length - 1];

  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
});
