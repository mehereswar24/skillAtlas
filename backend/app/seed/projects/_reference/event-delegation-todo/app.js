const form = document.getElementById('add');
const input = document.getElementById('title');
const list = document.getElementById('list');

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const title = input.value.trim();
  if (!title) return;

  const item = document.createElement('li');
  item.className = 'todo';
  item.innerHTML = '<span class="text"></span><button class="remove" type="button">&times;</button>';
  // textContent, not innerHTML: a to-do called <img onerror=...> would execute.
  item.querySelector('.text').textContent = title;
  list.append(item);
  input.value = '';
});

// One delegated listener for the whole list, so items added later just work.
list.addEventListener('click', (event) => {
  const item = event.target.closest('li.todo');
  if (!item) return;

  if (event.target.closest('.remove')) {
    item.remove();
  } else if (event.target.closest('.text')) {
    item.classList.toggle('done');
  }
});
